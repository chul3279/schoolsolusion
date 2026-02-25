"""
club.py - 동아리 관련 API (목록, 등록, 삭제, 학생관리, 기초작업, 작성, 파일, 공통사항, AI생성)
"""
import io
import os
import time
import base64
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, session
import requests as http_requests

from routes.subject_utils import (
    get_db_connection, sanitize_input, sanitize_html,
    sftp_upload_file, sftp_download_file, sftp_remove_file, sftp_makedirs,
    allowed_file,
    call_gemini, resummarize, calc_neis_bytes, byte_instruction,
    check_and_deduct_point,
    SUBJECT_WRITING_RULES, MIDDLE_SUBJECT_WRITING_RULES, AI_POINT_COST
)

club_bp = Blueprint('club', __name__)


# ============================================
# [보안] 동아리 담당 교사 권한 확인 헬퍼
# ============================================
def is_club_authorized(cursor, school_id, club_name, user_id):
    """동아리 담당 교사 여부 확인 (생성자 + 추가 권한 교사)"""
    cursor.execute("""
        SELECT teacher_id, authorized_teachers
        FROM club_list
        WHERE school_id = %s AND club_name = %s
        ORDER BY id DESC LIMIT 1
    """, (school_id, club_name))
    row = cursor.fetchone()
    if not row:
        return False
    if user_id == row['teacher_id']:
        return True
    auth = row.get('authorized_teachers') or ''
    return user_id in [t.strip() for t in auth.split(',') if t.strip()]


# ============================================
# 동아리 목록
# ============================================
@club_bp.route('/api/club/list', methods=['GET'])
def get_club_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not school_id:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """SELECT id, club_name, teacher_name, description, created_at
                   FROM club_list WHERE school_id = %s"""
        params = [school_id]

        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)

        query += " ORDER BY club_name"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        clubs = []
        for r in rows:
            cursor.execute("SELECT COUNT(*) as cnt FROM club_record WHERE school_id = %s AND club_name = %s AND record_year = %s AND record_semester = %s",
                           (school_id, r['club_name'], record_year or '', record_semester or ''))
            cnt = cursor.fetchone()['cnt']
            clubs.append({
                'id': r['id'],
                'club_name': r['club_name'],
                'teacher_name': r['teacher_name'] or '',
                'description': r['description'] or '',
                'student_count': cnt,
                'created_at': r['created_at'].strftime('%Y-%m-%d') if r['created_at'] else ''
            })

        return jsonify({'success': True, 'clubs': clubs})

    except Exception as e:
        print(f"동아리 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 등록
# ============================================
@club_bp.route('/api/club/create', methods=['POST'])
def create_club():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        # [보안] school_id, teacher_id 등은 세션에서 가져옴 (클라이언트 위조 방지)
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        member_school = session.get('user_school') or sanitize_input(data.get('member_school'), 100)
        club_name = data.get('club_name', '').strip()
        teacher_id = session.get('user_id') or sanitize_input(data.get('teacher_id'), 50)
        teacher_name = session.get('user_name') or sanitize_input(data.get('teacher_name'), 100)
        description = sanitize_html(data.get('description', ''), 500)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)

        if not all([school_id, club_name]):
            return jsonify({'success': False, 'message': '동아리 이름을 입력해주세요.'})

        if not record_year or not record_semester:
            return jsonify({'success': False, 'message': '학년도와 학기를 선택해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM club_list
                          WHERE school_id = %s AND club_name = %s AND record_year = %s AND record_semester = %s""",
                       (school_id, club_name, record_year, record_semester))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': f'"{club_name}" 동아리가 이미 존재합니다.'})

        cursor.execute("""
            INSERT INTO club_list
            (school_id, member_school, club_name, teacher_id, teacher_name, description,
             record_year, record_semester, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school, club_name, teacher_id, teacher_name, description,
              record_year, record_semester))
        conn.commit()

        return jsonify({'success': True, 'message': f'"{club_name}" 동아리가 등록되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 등록 오류: {e}")
        return jsonify({'success': False, 'message': '등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 삭제
# ============================================
@club_bp.route('/api/club/delete', methods=['POST'])
def delete_club():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        club_id = sanitize_input(data.get('id'), 20)

        if not club_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 소유자 검증 — 생성자 + authorized_teachers 확인
        cursor.execute("SELECT teacher_id, authorized_teachers, school_id, club_name FROM club_list WHERE id = %s", (club_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        user_id = session.get('user_id')
        is_owner = (row['teacher_id'] == user_id)
        auth_teachers = row.get('authorized_teachers') or ''
        is_auth = user_id in [t.strip() for t in auth_teachers.split(',') if t.strip()]
        if not is_owner and not is_auth:
            return jsonify({'success': False, 'message': '담당 교사만 동아리를 삭제할 수 있습니다.'}), 403
        cursor.execute("DELETE FROM club_list WHERE id = %s", (club_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '동아리가 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 학생 목록
# ============================================
@club_bp.route('/api/club/students', methods=['GET'])
def get_club_students():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        club_name = sanitize_input(request.args.get('club_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 동아리 담당자만 학생 목록 조회
        if session.get('user_role') == 'teacher' and not is_club_authorized(cursor, school_id, club_name, session.get('user_id')):
            return jsonify({'success': False, 'message': '담당 교사만 조회할 수 있습니다.'}), 403
        query = """SELECT id, student_id, student_name, class_grade, class_no, class_num
                   FROM club_record WHERE school_id = %s AND club_name = %s"""
        params = [school_id, club_name]

        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)

        query += " ORDER BY class_grade, CAST(class_no AS UNSIGNED), CAST(class_num AS UNSIGNED)"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        students = []
        for r in rows:
            students.append({
                'id': r['id'],
                'student_id': r['student_id'],
                'student_name': r['student_name'],
                'class_grade': r['class_grade'],
                'class_no': r['class_no'],
                'class_num': r['class_num']
            })

        return jsonify({'success': True, 'students': students})

    except Exception as e:
        print(f"동아리 학생 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 학생 추가
# ============================================
@club_bp.route('/api/club/student/add', methods=['POST'])
def add_club_student():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        teacher_id = sanitize_input(data.get('teacher_id'), 50)
        teacher_name = sanitize_input(data.get('teacher_name'), 100)
        club_name = sanitize_input(data.get('club_name'), 100)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = sanitize_input(data.get('student_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)

        if not all([school_id, club_name, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM club_record
                          WHERE school_id = %s AND club_name = %s AND student_id = %s
                                AND record_year = %s AND record_semester = %s""",
                       (school_id, club_name, student_id, record_year, record_semester))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 등록된 학생입니다.'})

        cursor.execute("""
            INSERT INTO club_record
            (school_id, member_school, club_name, teacher_id, teacher_name,
             student_id, student_name, class_grade, class_no, class_num,
             record_year, record_semester, base_data, content, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '', '', 'draft', NOW(), NOW())
        """, (school_id, member_school, club_name, teacher_id, teacher_name,
              student_id, student_name, class_grade, class_no, class_num,
              record_year, record_semester))
        conn.commit()

        return jsonify({'success': True, 'message': f'{student_name} 학생이 등록되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 학생 추가 오류: {e}")
        return jsonify({'success': False, 'message': '등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 기록 조회
# ============================================
@club_bp.route('/api/club/record/get', methods=['GET'])
def get_club_record():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        club_name = sanitize_input(request.args.get('club_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([student_id, club_name]):
            return jsonify({'success': False, 'message': '학생 및 동아리 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 동아리 담당자만 기록 조회
        if session.get('user_role') == 'teacher' and not is_club_authorized(cursor, school_id, club_name, session.get('user_id')):
            return jsonify({'success': False, 'message': '담당 교사만 조회할 수 있습니다.'}), 403
        query = """SELECT id, base_data, content, status, updated_at
                   FROM club_record
                   WHERE school_id = %s AND student_id = %s AND club_name = %s"""
        params = [school_id, student_id, club_name]

        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)

        cursor.execute(query, params)
        record = cursor.fetchone()

        if record:
            return jsonify({
                'success': True,
                'record': {
                    'id': record['id'],
                    'base_data': record['base_data'] or '',
                    'content': record['content'] or '',
                    'status': record['status'],
                    'updated_at': record['updated_at'].strftime('%Y-%m-%d %H:%M') if record['updated_at'] else ''
                }
            })
        else:
            return jsonify({'success': True, 'record': None})

    except Exception as e:
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 기초자료 저장
# ============================================
@club_bp.route('/api/club/base/save', methods=['POST'])
def save_club_base():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        teacher_id = sanitize_input(data.get('teacher_id'), 50)
        teacher_name = sanitize_input(data.get('teacher_name'), 100)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = sanitize_input(data.get('student_name'), 100)
        club_name = sanitize_input(data.get('club_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        base_data = sanitize_html(data.get('base_data', ''))

        if not all([school_id, student_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM club_record
                          WHERE school_id = %s AND student_id = %s AND club_name = %s
                                AND record_year = %s AND record_semester = %s""",
                       (school_id, student_id, club_name, record_year, record_semester))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""UPDATE club_record SET base_data = %s, member_school = %s, teacher_id = %s, teacher_name = %s,
                              student_name = %s, class_grade = %s, class_no = %s, class_num = %s,
                              updated_at = NOW() WHERE id = %s""",
                           (base_data, member_school, teacher_id, teacher_name, student_name, class_grade, class_no, class_num, existing['id']))
        else:
            cursor.execute("""INSERT INTO club_record
                              (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                               club_name, class_grade, class_no, class_num,
                               record_year, record_semester, base_data, status, created_at, updated_at)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', NOW(), NOW())""",
                           (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                            club_name, class_grade, class_no, class_num,
                            record_year, record_semester, base_data))
        conn.commit()
        return jsonify({'success': True, 'message': '기초자료가 저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 기초자료 저장 오류: {e}")
        return jsonify({'success': False, 'message': '저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 내용 저장
# ============================================
@club_bp.route('/api/club/write/save', methods=['POST'])
def save_club_write():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        teacher_id = sanitize_input(data.get('teacher_id'), 50)
        teacher_name = sanitize_input(data.get('teacher_name'), 100)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = sanitize_input(data.get('student_name'), 100)
        club_name = sanitize_input(data.get('club_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        content = sanitize_html(data.get('content', ''))
        status = sanitize_input(data.get('status'), 20) or 'draft'

        if not all([school_id, student_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM club_record
                          WHERE school_id = %s AND student_id = %s AND club_name = %s
                                AND record_year = %s AND record_semester = %s""",
                       (school_id, student_id, club_name, record_year, record_semester))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""UPDATE club_record SET content = %s, status = %s, member_school = %s, teacher_id = %s, teacher_name = %s,
                              student_name = %s, class_grade = %s, class_no = %s, class_num = %s,
                              updated_at = NOW() WHERE id = %s""",
                           (content, status, member_school, teacher_id, teacher_name, student_name, class_grade, class_no, class_num, existing['id']))
        else:
            cursor.execute("""INSERT INTO club_record
                              (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                               club_name, class_grade, class_no, class_num,
                               record_year, record_semester, content, status, created_at, updated_at)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())""",
                           (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                            club_name, class_grade, class_no, class_num,
                            record_year, record_semester, content, status))
        conn.commit()
        status_text = '저장' if status == 'complete' else '임시저장'
        return jsonify({'success': True, 'message': f'동아리 기록이 {status_text}되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 저장 오류: {e}")
        return jsonify({'success': False, 'message': '저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 상태 목록
# ============================================
@club_bp.route('/api/club/record/status-list', methods=['GET'])
def get_club_record_status():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        club_name = sanitize_input(request.args.get('club_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, club_name]):
            return jsonify({'success': False, 'message': '필수 조건이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 동아리 담당자만 상태 조회
        if session.get('user_role') == 'teacher' and not is_club_authorized(cursor, school_id, club_name, session.get('user_id')):
            return jsonify({'success': False, 'message': '담당 교사만 조회할 수 있습니다.'}), 403
        query = """SELECT student_id, student_name, class_grade, class_no, class_num, status
                   FROM club_record WHERE school_id = %s AND club_name = %s"""
        params = [school_id, club_name]
        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)
        query += " ORDER BY class_grade, CAST(class_no AS UNSIGNED), CAST(class_num AS UNSIGNED)"
        cursor.execute(query, params)
        students = cursor.fetchall()

        result = []
        for s in students:
            result.append({
                'member_id': s['student_id'],
                'member_name': s['student_name'],
                'class_grade': s['class_grade'],
                'class_no': s['class_no'],
                'class_num': s['class_num'],
                'status': s['status'] or 'none'
            })

        return jsonify({'success': True, 'students': result})

    except Exception as e:
        print(f"동아리 상태 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 공통사항 등록
# ============================================
@club_bp.route('/api/club/common/create', methods=['POST'])
def create_club_common():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        # [보안] school_id, teacher_id 등은 세션에서 가져옴 (클라이언트 위조 방지)
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        member_school = session.get('user_school') or sanitize_input(data.get('member_school'), 100)
        teacher_id = session.get('user_id') or sanitize_input(data.get('teacher_id'), 50)
        teacher_name = session.get('user_name') or sanitize_input(data.get('teacher_name'), 100)
        club_name = sanitize_input(data.get('club_name'), 100)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        activity_type = sanitize_input(data.get('activity_type'), 50) or '동아리활동'
        title = sanitize_html(data.get('title', ''), 200)
        content = sanitize_html(data.get('content', ''))
        activity_date = sanitize_input(data.get('activity_date'), 10)

        if not all([school_id, club_name, title]):
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO club_common_activity
            (school_id, member_school, teacher_id, teacher_name, club_name, record_year, record_semester,
             activity_type, title, content, activity_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school, teacher_id, teacher_name, club_name, record_year, record_semester,
              activity_type, title, content, activity_date or None))
        conn.commit()
        return jsonify({'success': True, 'message': '공통사항이 등록되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 공통사항 등록 오류: {e}")
        return jsonify({'success': False, 'message': '등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 공통사항 목록
# ============================================
@club_bp.route('/api/club/common/list', methods=['GET'])
def list_club_common():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        club_name = sanitize_input(request.args.get('club_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 동아리 담당자만 공통사항 조회
        if session.get('user_role') == 'teacher' and not is_club_authorized(cursor, school_id, club_name, session.get('user_id')):
            return jsonify({'success': False, 'message': '담당 교사만 조회할 수 있습니다.'}), 403
        query = """SELECT id, activity_type, title, content, activity_date, created_at
                   FROM club_common_activity WHERE school_id = %s AND club_name = %s"""
        params = [school_id, club_name]
        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)
        query += " ORDER BY activity_date DESC, created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        activities = []
        for r in rows:
            activities.append({
                'id': r['id'],
                'activity_type': r['activity_type'] or '',
                'title': r['title'] or '',
                'content': r['content'] or '',
                'activity_date': r['activity_date'] or '',
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else ''
            })
        return jsonify({'success': True, 'activities': activities})

    except Exception as e:
        print(f"동아리 공통사항 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 공통사항 삭제
# ============================================
@club_bp.route('/api/club/common/delete', methods=['POST'])
def delete_club_common():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        common_id = sanitize_input(data.get('id'), 20)
        if not common_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 동아리 담당 교사 검증 (작성자 본인 또는 동아리 담당교사)
        cursor.execute("SELECT club_name, school_id, teacher_id FROM club_common_activity WHERE id = %s", (common_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        user_id = session.get('user_id')
        is_author = (row.get('teacher_id') == user_id)
        if not is_author and not is_club_authorized(cursor, row['school_id'], row['club_name'], user_id):
            return jsonify({'success': False, 'message': '담당 교사만 삭제할 수 있습니다.'}), 403
        cursor.execute("DELETE FROM club_common_activity WHERE id = %s", (common_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '공통사항이 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 파일 업로드
# ============================================
@club_bp.route('/api/club/file/upload', methods=['POST'])
def upload_club_file():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.form.get('school_id'), 50)
        member_school = sanitize_input(request.form.get('member_school'), 100)
        teacher_id = sanitize_input(request.form.get('teacher_id'), 50)
        teacher_name = sanitize_input(request.form.get('teacher_name'), 100)
        student_id = sanitize_input(request.form.get('student_id'), 50)
        student_name = sanitize_input(request.form.get('student_name'), 100)
        club_name = sanitize_input(request.form.get('club_name'), 100)
        from datetime import datetime as dt_cls
        record_year = sanitize_input(request.form.get('record_year'), 4) or str(dt_cls.now().year)
        record_semester = sanitize_input(request.form.get('record_semester'), 1) or ('1' if dt_cls.now().month <= 7 else '2')

        if not all([school_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다. (school_id, club_name 필수)'})

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '파일이 없습니다.'})

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})

        file_data = file.read()
        file_size = len(file_data)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'success': False, 'message': '파일 크기는 10MB를 초과할 수 없습니다.'})

        original_name = file.filename
        file_ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{original_name}"
        remote_path = f"/data/club/{school_id}/{club_name}/{student_id}/{safe_filename}"

        if not sftp_upload_file(file_data, remote_path):
            return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO club_files
            (school_id, member_school, teacher_id, club_name, student_id, student_name,
             record_year, record_semester, file_name, original_name, file_path, file_size,
             file_type, uploaded_by, uploaded_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school, teacher_id, club_name, student_id, student_name,
              record_year, record_semester, safe_filename, original_name, remote_path, file_size,
              file_ext, teacher_id, teacher_name))
        conn.commit()
        return jsonify({'success': True, 'message': f'"{original_name}" 업로드 완료'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 파일 업로드 오류: {e}")
        return jsonify({'success': False, 'message': '업로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 파일 목록
# ============================================
@club_bp.route('/api/club/file/list', methods=['GET'])
def list_club_files():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        club_name = sanitize_input(request.args.get('club_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not school_id or not club_name:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다: school_id, club_name'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 동아리 담당자만 파일 조회 (student_id 선택)
        if session.get('user_role') == 'teacher':
            if not is_club_authorized(cursor, school_id, club_name, session.get('user_id')):
                return jsonify({'success': False, 'message': '담당 교사만 조회할 수 있습니다.'}), 403
            query = """SELECT id, original_name, file_size, created_at
                       FROM club_files WHERE school_id = %s AND club_name = %s"""
            params = [school_id, club_name]
            if student_id:
                query += " AND student_id = %s"
                params.append(student_id)
        else:
            if not student_id:
                return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다: student_id'})
            query = """SELECT id, original_name, file_size, created_at
                       FROM club_files WHERE school_id = %s AND student_id = %s AND club_name = %s"""
            params = [school_id, student_id, club_name]
        if record_year:
            query += " AND record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND record_semester = %s"
            params.append(record_semester)
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        files = []
        for r in rows:
            files.append({
                'id': r['id'],
                'file_name': r['original_name'],
                'file_size': r['file_size'],
                'uploaded_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else ''
            })
        return jsonify({'success': True, 'files': files})

    except Exception as e:
        print(f"동아리 파일 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 파일 다운로드
# ============================================
@club_bp.route('/api/club/file/download/<int:file_id>', methods=['GET'])
def download_club_file(file_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, original_name FROM club_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'})
        file_data = sftp_download_file(result['file_path'])
        if not file_data:
            return jsonify({'success': False, 'message': '서버에서 파일을 찾을 수 없습니다.'})
        return send_file(io.BytesIO(file_data), as_attachment=True, download_name=result['original_name'])
    except Exception as e:
        print(f"동아리 파일 다운로드 오류: {e}")
        return jsonify({'success': False, 'message': '다운로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 파일 삭제
# ============================================
@club_bp.route('/api/club/file/delete', methods=['POST'])
def delete_club_file():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        file_id = sanitize_input(data.get('id'), 20)
        if not file_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        # [보안] 동아리 담당 교사 검증 (업로더 본인 또는 동아리 담당교사)
        cursor.execute("SELECT file_path, club_name, school_id, teacher_id, uploaded_by FROM club_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        user_id = session.get('user_id')
        is_uploader = (result.get('teacher_id') == user_id or result.get('uploaded_by') == user_id)
        if not is_uploader and not is_club_authorized(cursor, result['school_id'], result['club_name'], user_id):
            return jsonify({'success': False, 'message': '담당 교사만 삭제할 수 있습니다.'}), 403
        if result['file_path']:
            sftp_remove_file(result['file_path'])
        cursor.execute("DELETE FROM club_files WHERE id = %s", (file_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '파일이 삭제되었습니다.'})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 동아리 AI 생성 (파일 정보 포함)
# ============================================
@club_bp.route('/api/club/generate', methods=['POST'])
def generate_club_record():
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = data.get('student_name', '')
        club_name = data.get('club_name', '')
        class_grade = data.get('class_grade', '')
        class_no = data.get('class_no', '')
        base_data = data.get('base_data', '')
        common_activities = data.get('common_activities', [])
        byte_limit = int(data.get('byte_limit', 1500))
        school_id = sanitize_input(data.get('school_id'), 50)
        school_level = data.get('school_level', 'high')

        if not all([member_id, student_name, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        success, msg, new_point = check_and_deduct_point(member_id, AI_POINT_COST, 'club_record', school_id=school_id, student_id=student_id)
        if not success:
            return jsonify({'success': False, 'message': msg, 'point_error': True})

        common_text = ''
        if common_activities:
            common_text = '\n'.join([
                f"- [{act.get('date','')}] {act.get('type','')}: {act.get('title','')} - {act.get('content','')}"
                for act in common_activities
            ])

        # 파일 내용 읽기 (SFTP 다운로드 → 타입별 분류)
        file_text = ''
        file_parts = []
        TEXT_EXTS = {'txt', 'csv', 'md'}
        IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        IMAGE_MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        PDF_EXTS = {'pdf'}

        if school_id and student_id:
            conn2 = None
            cursor2 = None
            try:
                conn2 = get_db_connection()
                if conn2:
                    cursor2 = conn2.cursor()
                    cursor2.execute("""
                        SELECT original_name, file_path, file_type FROM club_files
                        WHERE school_id = %s AND student_id = %s AND club_name = %s
                        ORDER BY created_at DESC LIMIT 5
                    """, (school_id, student_id, club_name))
                    file_rows = cursor2.fetchall()

                    text_contents = []
                    skipped_files = []

                    for fr in file_rows:
                        ext = (fr.get('file_type') or '').lower()
                        fpath = fr.get('file_path', '')
                        fname = fr.get('original_name', '')

                        file_data_bytes = sftp_download_file(fpath)
                        if not file_data_bytes:
                            continue

                        # 최소 크기 검증 (손상/빈 파일 방지)
                        if ext in (PDF_EXTS | IMAGE_EXTS) and len(file_data_bytes) < 100:
                            skipped_files.append(f"{fname}(파일손상)")
                            continue

                        if ext in TEXT_EXTS:
                            try:
                                text_content = file_data_bytes.decode('utf-8')
                                text_contents.append(f"[파일: {fname}]\n{text_content}")
                            except UnicodeDecodeError:
                                try:
                                    text_content = file_data_bytes.decode('euc-kr')
                                    text_contents.append(f"[파일: {fname}]\n{text_content}")
                                except:
                                    skipped_files.append(fname)

                        elif ext in IMAGE_EXTS:
                            b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                            mime = IMAGE_MIME.get(ext, 'image/jpeg')
                            file_parts.append({"inline_data": {"mime_type": mime, "data": b64}})
                            file_parts.append({"text": f"(위 이미지는 '{fname}' 파일입니다)"})

                        elif ext in PDF_EXTS:
                            b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                            file_parts.append({"inline_data": {"mime_type": "application/pdf", "data": b64}})
                            file_parts.append({"text": f"(위 PDF는 '{fname}' 파일입니다)"})

                        else:
                            skipped_files.append(fname)

                    if text_contents:
                        file_text = '\n\n'.join(text_contents)
                    if skipped_files:
                        file_text += ('\n' if file_text else '') + '\n'.join([f"- 첨부파일(내용 읽기 불가): {fn}" for fn in skipped_files])

            except Exception as e:
                print(f"AI생성 - 동아리 파일 조회/다운로드 오류: {e}")
            finally:
                if cursor2: cursor2.close()
                if conn2: conn2.close()

        char_inst = byte_instruction(byte_limit)

        # 공통 정보 블록
        common_info_block = f"""[학생 정보]
- 이름: {student_name} (작성 시 이름 및 지칭어 사용 금지, 주어 생략하고 바로 서술)
- 학년/반: {class_grade}학년 {class_no}반
- 동아리: {club_name}

[기초자료 - 교사 메모]
{base_data if base_data else '(등록된 기초자료 없음)'}

[동아리 공통활동]
{common_text if common_text else '(등록된 공통활동 없음)'}

[첨부 파일/제출 자료]
{file_text if file_text else '(첨부 파일 없음)'}

[작성 분량]
{char_inst}"""

        if school_level == 'middle':
            prompt = f"""당신은 대한민국 중학교에서 20년 이상 근무한 베테랑 동아리 지도 교사입니다.
중학생의 성장과 변화를 잘 포착하여 '창의적 체험활동 - 동아리활동' 기록을 작성하는 전문가입니다.
아래 학생의 기초자료와 동아리 공통사항을 바탕으로 동아리 활동 기록을 작성해주세요.

{MIDDLE_SUBJECT_WRITING_RULES}

{common_info_block}

위 정보를 바탕으로 '{club_name}' 동아리 활동 기록을 작성해주세요.
기초자료, 공통활동, 첨부 자료를 모두 참고하여 종합적으로 서술하세요.
태그 없이 본문만 출력하세요. 절대 학생 이름이나 지칭어를 포함하지 마세요.

[포함 요소]
- 동아리 내에서의 역할과 참여 태도
- 구체적인 활동 사례와 에피소드
- 활동을 통한 성장과 변화
- 또래와의 협력, 소통, 배려
- 동아리 활동을 통해 발견한 흥미와 잠재력

[서술 방법]
- 동아리 활동 참여 계기 → 구체적 역할·참여 과정 → 성장/변화 → 잠재력·태도 평가 흐름으로 작성
- 활동 과정에서의 시행착오와 이를 극복한 경험을 긍정적으로 서술
- 또래와의 협력, 소통, 배려 등 공동체 역량이 구체적 행동 사례로 드러나도록 작성
- 학생의 흥미, 적극성, 성실성, 성장 가능성이 자연스럽게 드러나도록 서술"""
        else:
            prompt = f"""당신은 대한민국 고등학교에서 20년 이상 근무한 베테랑 동아리 지도 교사입니다.
학생부종합전형에서 높은 평가를 받는 '창의적 체험활동 - 동아리활동' 기록을 작성하는 전문가입니다.
아래 학생의 기초자료와 동아리 공통사항을 바탕으로 동아리 활동 기록을 작성해주세요.

{SUBJECT_WRITING_RULES}

{common_info_block}

위 정보를 바탕으로 '{club_name}' 동아리 활동 기록을 작성해주세요.
기초자료, 공통활동, 첨부 자료를 모두 참고하여 종합적으로 서술하세요.
태그 없이 본문만 출력하세요. 절대 학생 이름이나 지칭어를 포함하지 마세요.

[포함 요소]
- 동아리 내에서의 역할과 참여 태도
- 구체적인 활동 사례와 에피소드
- 활동을 통한 역량 발전과 성장 변화
- 공동체 내 기여와 협력 능력
- 동아리 활동과 연계된 학업·진로 탐색 노력

[서술 방법]
- 동아리 활동 참여 계기 → 구체적 역할·기여 → 탐구/활동 결과물 → 역량·성장 평가 흐름으로 작성
- 활동 과정에서의 문제 해결 과정과 자기주도적 노력을 구체적 에피소드로 서술
- 동아리 활동을 통해 배운 내용을 교과 학습이나 진로 탐색과 연결하여 확장적으로 서술
- 협력, 리더십, 의사소통 등 공동체 역량이 구체적 행동 사례로 드러나도록 작성"""

        ai_text, err = call_gemini(prompt, file_parts=file_parts if file_parts else None)
        if err:
            return jsonify({'success': False, 'message': err, 'new_point': new_point})

        if calc_neis_bytes(ai_text) > byte_limit:
            print(f"동아리 바이트 초과: {calc_neis_bytes(ai_text)}B > {byte_limit}B → 재요약")
            ai_text = resummarize(ai_text, byte_limit, club_name)

        return jsonify({
            'success': True,
            'content': ai_text.strip(),
            'bytes': calc_neis_bytes(ai_text.strip()),
            'new_point': new_point,
            'point_used': AI_POINT_COST
        })

    except http_requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'AI 서비스 응답 시간이 초과되었습니다.'})
    except Exception as e:
        print(f"동아리 AI 생성 오류: {e}")
        return jsonify({'success': False, 'message': '동아리 기록 생성 중 오류가 발생했습니다.'})


# ============================================
# [보안] 동아리 권한 부여 API
# ============================================
@club_bp.route('/api/club/authorize', methods=['POST'])
def club_authorize():
    """동아리 공동 관리 교사 권한 부여 - 생성자만 가능"""
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id')
        user_id = session.get('user_id')
        data = request.get_json()
        club_name = sanitize_input(data.get('club_name'), 100)
        target_teacher_id = sanitize_input(data.get('target_teacher_id'), 50)

        if not all([school_id, user_id, club_name, target_teacher_id]):
            return jsonify({'success': False, 'message': '필수 파라미터가 누락되었습니다.'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, teacher_id, authorized_teachers
            FROM club_list
            WHERE school_id = %s AND club_name = %s
            ORDER BY id DESC LIMIT 1
        """, (school_id, club_name))
        row = cursor.fetchone()

        if not row:
            return jsonify({'success': False, 'message': '동아리를 찾을 수 없습니다.'}), 404
        if row['teacher_id'] != user_id:
            return jsonify({'success': False, 'message': '동아리 생성자만 권한을 부여할 수 있습니다.'}), 403

        auth = row.get('authorized_teachers') or ''
        auth_list = [t.strip() for t in auth.split(',') if t.strip()]
        if target_teacher_id not in auth_list:
            auth_list.append(target_teacher_id)

        cursor.execute("UPDATE club_list SET authorized_teachers = %s WHERE id = %s",
                       (','.join(auth_list), row['id']))
        conn.commit()
        return jsonify({'success': True, 'message': f'{target_teacher_id} 교사에게 권한을 부여했습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 권한 부여 오류: {e}")
        return jsonify({'success': False, 'message': '권한 부여 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# [보안] 동아리 권한 회수 API
# ============================================
@club_bp.route('/api/club/unauthorize', methods=['POST'])
def club_unauthorize():
    """동아리 공동 관리 교사 권한 회수 - 생성자만 가능"""
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id')
        user_id = session.get('user_id')
        data = request.get_json()
        club_name = sanitize_input(data.get('club_name'), 100)
        target_teacher_id = sanitize_input(data.get('target_teacher_id'), 50)

        if not all([school_id, user_id, club_name, target_teacher_id]):
            return jsonify({'success': False, 'message': '필수 파라미터가 누락되었습니다.'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, teacher_id, authorized_teachers
            FROM club_list
            WHERE school_id = %s AND club_name = %s
            ORDER BY id DESC LIMIT 1
        """, (school_id, club_name))
        row = cursor.fetchone()

        if not row:
            return jsonify({'success': False, 'message': '동아리를 찾을 수 없습니다.'}), 404
        if row['teacher_id'] != user_id:
            return jsonify({'success': False, 'message': '동아리 생성자만 권한을 회수할 수 있습니다.'}), 403

        auth = row.get('authorized_teachers') or ''
        auth_list = [t.strip() for t in auth.split(',') if t.strip() and t.strip() != target_teacher_id]

        cursor.execute("UPDATE club_list SET authorized_teachers = %s WHERE id = %s",
                       (','.join(auth_list) if auth_list else None, row['id']))
        conn.commit()
        return jsonify({'success': True, 'message': f'{target_teacher_id} 교사의 권한을 회수했습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"동아리 권한 회수 오류: {e}")
        return jsonify({'success': False, 'message': '권한 회수 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
