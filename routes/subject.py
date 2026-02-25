"""
subject.py - 과세특 관련 API (기초작업, 작성, 파일, 공통사항, AI생성)
+ 학교별 과목 목록, 학생 과제제출 조회
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

subject_bp = Blueprint('subject', __name__)


# ============================================
# 학급 학생 목록 (과세특용)
# ============================================
@subject_bp.route('/api/subject/students', methods=['GET'])
def get_subject_students():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)

        if not all([school_id, class_grade, class_no]):
            return jsonify({'success': False, 'message': '학급 정보가 필요합니다.'})

        # [보안] 학생/학부모: 본인 반만 조회 가능
        user_role = session.get('user_role')
        if user_role in ('student', 'parent'):
            if class_grade != session.get('class_grade') or class_no != session.get('class_no'):
                return jsonify({'success': False, 'message': '본인 학급만 조회할 수 있습니다.'}), 403

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT member_id, member_name, class_grade, class_no, class_num
            FROM stu_all
            WHERE school_id = %s AND class_grade = %s AND class_no = %s
            ORDER BY CAST(class_num AS UNSIGNED)
        """, (school_id, class_grade, class_no))

        students = []
        for row in cursor.fetchall():
            students.append({
                'member_id': row['member_id'],
                'member_name': row['member_name'],
                'class_grade': row['class_grade'],
                'class_no': row['class_no'],
                'class_num': row['class_num']
            })

        return jsonify({'success': True, 'students': students})

    except Exception as e:
        print(f"학생 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '학생 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 기록 조회 (학생 1명)
# ============================================
@subject_bp.route('/api/subject/record/get', methods=['GET'])
def get_subject_record():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        subject_name = sanitize_input(request.args.get('subject_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([student_id, subject_name]):
            return jsonify({'success': False, 'message': '학생 및 과목 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """
            SELECT id, base_data, content, status, updated_at
            FROM subject_record
            WHERE school_id = %s AND student_id = %s AND subject_name = %s
        """
        params = [school_id, student_id, subject_name]

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
# 과세특 기초자료 저장
# ============================================
@subject_bp.route('/api/subject/base/save', methods=['POST'])
def save_subject_base():
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
        subject_name = sanitize_input(data.get('subject_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        base_data = sanitize_html(data.get('base_data', ''))

        if not all([school_id, student_id, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM subject_record
            WHERE school_id = %s AND student_id = %s AND subject_name = %s
                  AND record_year = %s AND record_semester = %s
        """, (school_id, student_id, subject_name, record_year, record_semester))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE subject_record SET base_data = %s, member_school = %s, teacher_id = %s, teacher_name = %s,
                       student_name = %s, class_grade = %s, class_no = %s, class_num = %s,
                       updated_at = NOW()
                WHERE id = %s
            """, (base_data, member_school, teacher_id, teacher_name, student_name, class_grade, class_no, class_num, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO subject_record
                (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                 subject_name, class_grade, class_no, class_num,
                 record_year, record_semester, base_data, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', NOW(), NOW())
            """, (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                  subject_name, class_grade, class_no, class_num,
                  record_year, record_semester, base_data))

        conn.commit()
        return jsonify({'success': True, 'message': '기초자료가 저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"기초자료 저장 오류: {e}")
        return jsonify({'success': False, 'message': '저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 내용 저장
# ============================================
@subject_bp.route('/api/subject/write/save', methods=['POST'])
def save_subject_write():
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
        subject_name = sanitize_input(data.get('subject_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        content = sanitize_html(data.get('content', ''))
        status = sanitize_input(data.get('status'), 20) or 'draft'

        if not all([school_id, student_id, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM subject_record
            WHERE school_id = %s AND student_id = %s AND subject_name = %s
                  AND record_year = %s AND record_semester = %s
        """, (school_id, student_id, subject_name, record_year, record_semester))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE subject_record SET content = %s, status = %s, member_school = %s, teacher_id = %s, teacher_name = %s,
                       student_name = %s, class_grade = %s, class_no = %s, class_num = %s,
                       updated_at = NOW()
                WHERE id = %s
            """, (content, status, member_school, teacher_id, teacher_name, student_name, class_grade, class_no, class_num, existing['id']))
        else:
            cursor.execute("""
                INSERT INTO subject_record
                (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                 subject_name, class_grade, class_no, class_num,
                 record_year, record_semester, content, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (school_id, member_school, teacher_id, teacher_name, student_id, student_name,
                  subject_name, class_grade, class_no, class_num,
                  record_year, record_semester, content, status))

        conn.commit()
        status_text = '저장' if status == 'complete' else '임시저장'
        return jsonify({'success': True, 'message': f'과세특이 {status_text}되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"과세특 저장 오류: {e}")
        return jsonify({'success': False, 'message': '저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 상태 목록 (학급 전체)
# ============================================
@subject_bp.route('/api/subject/record/status-list', methods=['GET'])
def get_subject_record_status():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        subject_name = sanitize_input(request.args.get('subject_name'), 100)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, subject_name, class_grade, class_no]):
            return jsonify({'success': False, 'message': '필수 조건이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT member_id, member_name, class_grade, class_no, class_num
            FROM stu_all
            WHERE school_id = %s AND class_grade = %s AND class_no = %s
            ORDER BY CAST(class_num AS UNSIGNED)
        """, (school_id, class_grade, class_no))
        students = cursor.fetchall()

        result = []
        for s in students:
            query = """SELECT status FROM subject_record
                       WHERE school_id = %s AND student_id = %s AND subject_name = %s"""
            params = [school_id, s['member_id'], subject_name]
            if record_year:
                query += " AND record_year = %s"
                params.append(record_year)
            if record_semester:
                query += " AND record_semester = %s"
                params.append(record_semester)

            cursor.execute(query, params)
            rec = cursor.fetchone()
            result.append({
                'member_id': s['member_id'],
                'member_name': s['member_name'],
                'class_grade': s['class_grade'],
                'class_no': s['class_no'],
                'class_num': s['class_num'],
                'status': rec['status'] if rec else 'none'
            })

        return jsonify({'success': True, 'students': result})

    except Exception as e:
        print(f"과세특 상태 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과목 공통사항 목록
# ============================================
@subject_bp.route('/api/subject/common/list', methods=['GET'])
def list_subject_common():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        subject_name = sanitize_input(request.args.get('subject_name'), 100)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """SELECT id, activity_type, title, content, activity_date, created_at
                   FROM subject_common_activity
                   WHERE school_id = %s AND subject_name = %s"""
        params = [school_id, subject_name]

        # [보안] 교사는 작성 본인만 조회
        if session.get('user_role') == 'teacher':
            query += " AND teacher_id = %s"
            params.append(session.get('user_id'))

        if class_grade:
            query += " AND class_grade = %s"
            params.append(class_grade)
        if class_no:
            query += " AND class_no = %s"
            params.append(class_no)
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
        print(f"공통사항 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과목 공통사항 등록
# ============================================
@subject_bp.route('/api/subject/common/create', methods=['POST'])
def create_subject_common():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        # [보안] school_id, teacher_id 등은 세션에서 가져옴 (클라이언트 위조 방지)
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        member_school = session.get('user_school') or sanitize_input(data.get('member_school'), 100)
        teacher_id = session.get('user_id') or sanitize_input(data.get('teacher_id'), 50)
        teacher_name = session.get('user_name') or sanitize_input(data.get('teacher_name'), 100)
        subject_name = sanitize_input(data.get('subject_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        from datetime import datetime as dt_cls
        record_year = sanitize_input(data.get('record_year'), 4) or str(dt_cls.now().year)
        record_semester = sanitize_input(data.get('record_semester'), 1) or ('1' if dt_cls.now().month <= 7 else '2')
        activity_type = sanitize_input(data.get('activity_type'), 50) or '수업활동'
        title = sanitize_html(data.get('title', ''), 200)
        content = sanitize_html(data.get('content', ''))
        activity_date = sanitize_input(data.get('activity_date'), 10)

        if not all([school_id, subject_name, title]):
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        # class_grade/class_no 미전달 시 tea_all에서 조회
        if teacher_id and (not class_grade or not class_no):
            try:
                t_cur = conn.cursor()
                t_cur.execute("SELECT class_grade, class_no FROM tea_all WHERE member_id = %s", (teacher_id,))
                t_row = t_cur.fetchone()
                if t_row:
                    if not class_grade:
                        class_grade = str(t_row['class_grade']) if t_row['class_grade'] else ''
                    if not class_no:
                        class_no = str(t_row['class_no']) if t_row['class_no'] else ''
                t_cur.close()
            except Exception:
                pass

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subject_common_activity
            (school_id, member_school, teacher_id, teacher_name, subject_name, class_grade, class_no,
             record_year, record_semester, activity_type, title, content, activity_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school, teacher_id, teacher_name, subject_name, class_grade, class_no,
              record_year, record_semester, activity_type, title, content, activity_date or None))
        conn.commit()

        return jsonify({'success': True, 'message': '공통사항이 등록되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"공통사항 등록 오류: {e}")
        return jsonify({'success': False, 'message': '등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과목 공통사항 삭제
# ============================================
@subject_bp.route('/api/subject/common/delete', methods=['POST'])
def delete_subject_common():
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
        # [보안] 소유자 검증
        cursor.execute("SELECT teacher_id FROM subject_common_activity WHERE id = %s", (common_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        if row['teacher_id'] != session.get('user_id'):
            return jsonify({'success': False, 'message': '본인이 작성한 데이터만 삭제할 수 있습니다.'}), 403
        cursor.execute("DELETE FROM subject_common_activity WHERE id = %s", (common_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '공통사항이 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 파일 업로드
# ============================================
@subject_bp.route('/api/subject/file/upload', methods=['POST'])
def upload_subject_file():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.form.get('school_id'), 50)
        member_school = session.get('user_school') or sanitize_input(request.form.get('member_school'), 100)
        teacher_id = session.get('user_id') or sanitize_input(request.form.get('teacher_id'), 50)
        teacher_name = session.get('user_name') or sanitize_input(request.form.get('teacher_name'), 100)
        student_id = sanitize_input(request.form.get('student_id'), 50)
        student_name = sanitize_input(request.form.get('student_name'), 100)
        subject_name = sanitize_input(request.form.get('subject_name'), 100)
        from datetime import datetime as dt_cls
        record_year = sanitize_input(request.form.get('record_year'), 4) or str(dt_cls.now().year)
        record_semester = sanitize_input(request.form.get('record_semester'), 1) or ('1' if dt_cls.now().month <= 7 else '2')

        if not all([school_id, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다. (school_id, subject_name 필수)'})

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
        remote_path = f"/data/subject/{school_id}/{subject_name}/{student_id}/{safe_filename}"

        if not sftp_upload_file(file_data, remote_path):
            return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subject_files
            (school_id, member_school, teacher_id, subject_name, student_id, student_name,
             record_year, record_semester, file_name, original_name, file_path, file_size,
             file_type, uploaded_by, uploaded_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school, teacher_id, subject_name, student_id, student_name,
              record_year, record_semester, safe_filename, original_name, remote_path, file_size,
              file_ext, teacher_id, teacher_name))
        conn.commit()

        return jsonify({'success': True, 'message': f'"{original_name}" 업로드 완료'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"파일 업로드 오류: {e}")
        return jsonify({'success': False, 'message': '업로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 파일 목록
# ============================================
@subject_bp.route('/api/subject/file/list', methods=['GET'])
def list_subject_files():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        subject_name = sanitize_input(request.args.get('subject_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not school_id or not subject_name:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다. (school_id, subject_name)'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # [보안] 교사는 student_id 없이 본인 업로드 전체 조회 가능
        if session.get('user_role') == 'teacher':
            query = """SELECT id, original_name, file_size, created_at
                       FROM subject_files
                       WHERE school_id = %s AND subject_name = %s AND teacher_id = %s"""
            params = [school_id, subject_name, session.get('user_id')]
            if student_id:
                query += " AND student_id = %s"
                params.append(student_id)
        else:
            if not student_id:
                return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다. (student_id)'})
            query = """SELECT id, original_name, file_size, created_at
                       FROM subject_files
                       WHERE school_id = %s AND student_id = %s AND subject_name = %s"""
            params = [school_id, student_id, subject_name]

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
        print(f"파일 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 파일 다운로드
# ============================================
@subject_bp.route('/api/subject/file/download/<int:file_id>', methods=['GET'])
def download_subject_file(file_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT file_path, original_name FROM subject_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'})

        file_data = sftp_download_file(result['file_path'])
        if not file_data:
            return jsonify({'success': False, 'message': '서버에서 파일을 찾을 수 없습니다.'})

        return send_file(io.BytesIO(file_data), as_attachment=True, download_name=result['original_name'])

    except Exception as e:
        print(f"파일 다운로드 오류: {e}")
        return jsonify({'success': False, 'message': '다운로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 파일 삭제
# ============================================
@subject_bp.route('/api/subject/file/delete', methods=['POST'])
def delete_subject_file():
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
        # [보안] 소유자 검증
        cursor.execute("SELECT file_path, teacher_id FROM subject_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        if result['teacher_id'] != session.get('user_id'):
            return jsonify({'success': False, 'message': '본인이 업로드한 파일만 삭제할 수 있습니다.'}), 403

        if result['file_path']:
            sftp_remove_file(result['file_path'])

        cursor.execute("DELETE FROM subject_files WHERE id = %s", (file_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '파일이 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학교별 과목 목록 (timetable_data → cours_subject 순으로 조회)
# ============================================
@subject_bp.route('/api/subject/options', methods=['GET'])
@subject_bp.route('/api/subject/list', methods=['GET'])
def get_subject_options():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        subjects = set()

        # 1순위: timetable_data (학교별 실제 편성 과목)
        cursor.execute(
            "SELECT DISTINCT TRIM(subject) AS subj FROM timetable_data "
            "WHERE school_id = %s AND subject IS NOT NULL AND TRIM(subject) != ''",
            (school_id,)
        )
        for row in cursor.fetchall():
            subjects.add(row['subj'])

        # 2순위: timetable_data가 없으면 timetable_stu에서 추출 (TRIM 적용)
        if not subjects:
            for i in range(1, 13):
                cursor.execute(
                    f"SELECT DISTINCT TRIM(subject{i}) AS subj FROM timetable_stu "
                    f"WHERE school_id = %s AND subject{i} IS NOT NULL AND TRIM(subject{i}) != ''",
                    (school_id,)
                )
                for row in cursor.fetchall():
                    subjects.add(row['subj'])

        # 3순위: 둘 다 없으면 cours_subject 교육과정에서 가져오기 (학교급 자동 판별)
        if not subjects:
            # schoolinfo에서 학교급 조회
            sl = '고등'
            cursor.execute("SELECT school_level FROM schoolinfo WHERE school_id = %s", (school_id,))
            si_row = cursor.fetchone()
            if si_row and si_row.get('school_level'):
                level_val = si_row['school_level']
                if level_val in ('middle', '중', '중학교'):
                    sl = '중학교'
                elif level_val in ('elementary', '초', '초등', '초등학교'):
                    sl = '초등'
            cursor.execute(
                "SELECT DISTINCT subject FROM cours_subject "
                "WHERE school_level = %s AND subject IS NOT NULL AND subject != '' "
                "ORDER BY subject",
                (sl,)
            )
            for row in cursor.fetchall():
                subjects.add(row['subject'])

        sorted_subjects = sorted(subjects)
        return jsonify({'success': True, 'subjects': sorted_subjects})

    except Exception as e:
        print(f"과목 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '과목 목록 조회 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생의 과목별 제출 과제 조회 (과세특 작성 참고용)
# ============================================
@subject_bp.route('/api/subject/student-submissions', methods=['GET'])
def get_student_subject_submissions():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        subject_name = sanitize_input(request.args.get('subject_name'), 100)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, student_id, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """
            SELECT sa.title AS assignment_title, sa.description AS assignment_desc,
                   ss.file_name, ss.comment, ss.submitted_at
            FROM subject_submission ss
            JOIN subject_assignment sa ON ss.assignment_id = sa.id
            WHERE sa.school_id = %s AND ss.student_id = %s AND sa.subject_name = %s
        """
        params = [school_id, student_id, subject_name]

        if record_year:
            query += " AND sa.record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND sa.record_semester = %s"
            params.append(record_semester)

        query += " ORDER BY ss.submitted_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        submissions = []
        for r in rows:
            submissions.append({
                'assignment_title': r['assignment_title'] or '',
                'assignment_desc': r['assignment_desc'] or '',
                'file_name': r['file_name'] or '',
                'comment': r['comment'] or '',
                'submitted_at': r['submitted_at'].strftime('%Y-%m-%d %H:%M') if r['submitted_at'] else ''
            })

        return jsonify({'success': True, 'submissions': submissions})

    except Exception as e:
        print(f"학생 과제제출 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과세특 AI 생성 (제출 과제 + 교사 첨부파일 포함)
# ============================================
@subject_bp.route('/api/subject/generate', methods=['POST'])
def generate_subject_record():
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = data.get('student_name', '')
        subject_name = data.get('subject_name', '')
        class_grade = data.get('class_grade', '')
        class_no = data.get('class_no', '')
        base_data = sanitize_html(data.get('base_data', ''))
        common_activities = data.get('common_activities', [])
        submission_data = sanitize_html(data.get('submission_data', ''))
        byte_limit = int(data.get('byte_limit', 1500))
        school_id = sanitize_input(data.get('school_id'), 50)
        school_level = data.get('school_level', 'high')
        free_semester = data.get('free_semester', False)

        if not all([member_id, student_name, subject_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        success, msg, new_point = check_and_deduct_point(
            member_id, AI_POINT_COST, 'subject_record',
            school_id=school_id, student_id=student_id
        )
        if not success:
            return jsonify({'success': False, 'message': msg, 'point_error': True})

        common_text = ''
        if common_activities:
            common_text = '\n'.join([
                f"- [{act.get('date','')}] {act.get('type','')}: {act.get('title','')} - {act.get('content','')}"
                for act in common_activities
            ])

        # 파일 타입 분류 상수
        TEXT_EXTS = {'txt', 'csv', 'md'}
        IMAGE_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
        IMAGE_MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp'}
        PDF_EXTS = {'pdf'}

        # DB에서 제출 과제 조회 + 파일 내용 읽기
        submission_text = submission_data
        file_parts = []

        if school_id and student_id:
            conn2 = None
            cursor2 = None
            try:
                conn2 = get_db_connection()
                if conn2:
                    cursor2 = conn2.cursor()

                    # (A) 학생 제출 과제 파일
                    if not submission_text:
                        cursor2.execute("""
                            SELECT sa.title, sa.description, ss.comment, ss.submitted_at,
                                   ss.file_name, ss.file_path
                            FROM subject_submission ss
                            JOIN subject_assignment sa ON ss.assignment_id = sa.id
                            WHERE sa.school_id = %s AND ss.student_id = %s AND sa.subject_name = %s
                            ORDER BY ss.submitted_at DESC LIMIT 10
                        """, (school_id, student_id, subject_name))
                        sub_rows = cursor2.fetchall()
                        if sub_rows:
                            text_parts = []
                            for sr in sub_rows:
                                part = f"- 과제 '{sr['title']}'"
                                if sr['description']:
                                    part += f" ({sr['description']})"
                                if sr['comment']:
                                    part += f": {sr['comment']}"
                                text_parts.append(part)

                                fpath = sr.get('file_path', '')
                                fname = sr.get('file_name', '')
                                if fpath and fname:
                                    ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
                                    file_data_bytes = sftp_download_file(fpath)
                                    if not file_data_bytes:
                                        continue

                                    # 최소 크기 검증 (손상/빈 파일 방지)
                                    if ext in (PDF_EXTS | IMAGE_EXTS) and len(file_data_bytes) < 100:
                                        text_parts.append(f"  [제출파일: {fname}] (파일손상-스킵)")
                                        continue

                                    if ext in TEXT_EXTS:
                                        try:
                                            text_content = file_data_bytes.decode('utf-8')
                                            text_parts.append(f"  [제출파일: {fname}]\n{text_content}")
                                        except UnicodeDecodeError:
                                            try:
                                                text_content = file_data_bytes.decode('euc-kr')
                                                text_parts.append(f"  [제출파일: {fname}]\n{text_content}")
                                            except:
                                                text_parts.append(f"  [제출파일: {fname}] (내용 읽기 불가)")

                                    elif ext in IMAGE_EXTS:
                                        b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                                        mime = IMAGE_MIME.get(ext, 'image/jpeg')
                                        file_parts.append({"inline_data": {"mime_type": mime, "data": b64}})
                                        file_parts.append({"text": f"(위 이미지는 과제 '{sr['title']}' 제출파일 '{fname}'입니다)"})

                                    elif ext in PDF_EXTS:
                                        b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                                        file_parts.append({"inline_data": {"mime_type": "application/pdf", "data": b64}})
                                        file_parts.append({"text": f"(위 PDF는 과제 '{sr['title']}' 제출파일 '{fname}'입니다)"})

                                    else:
                                        text_parts.append(f"  [제출파일: {fname}] (내용 읽기 불가)")

                            submission_text = '\n'.join(text_parts)

                    # (B) 교사 첨부파일 (subject_files)
                    teacher_file_text = ''
                    teacher_file_text_parts = []
                    skipped_files = []

                    cursor2.execute("""
                        SELECT original_name, file_path, file_type FROM subject_files
                        WHERE school_id = %s AND student_id = %s AND subject_name = %s
                        ORDER BY created_at DESC LIMIT 5
                    """, (school_id, student_id, subject_name))
                    file_rows = cursor2.fetchall()

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
                                teacher_file_text_parts.append(f"[첨부파일: {fname}]\n{text_content}")
                            except UnicodeDecodeError:
                                try:
                                    text_content = file_data_bytes.decode('euc-kr')
                                    teacher_file_text_parts.append(f"[첨부파일: {fname}]\n{text_content}")
                                except:
                                    skipped_files.append(fname)

                        elif ext in IMAGE_EXTS:
                            b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                            mime = IMAGE_MIME.get(ext, 'image/jpeg')
                            file_parts.append({"inline_data": {"mime_type": mime, "data": b64}})
                            file_parts.append({"text": f"(위 이미지는 교사 첨부파일 '{fname}'입니다)"})

                        elif ext in PDF_EXTS:
                            b64 = base64.b64encode(file_data_bytes).decode('utf-8')
                            file_parts.append({"inline_data": {"mime_type": "application/pdf", "data": b64}})
                            file_parts.append({"text": f"(위 PDF는 교사 첨부파일 '{fname}'입니다)"})

                        else:
                            skipped_files.append(fname)

                    if teacher_file_text_parts:
                        teacher_file_text = '\n\n'.join(teacher_file_text_parts)
                    if skipped_files:
                        teacher_file_text += ('\n' if teacher_file_text else '') + '\n'.join(
                            [f"- 첨부파일(내용 읽기 불가): {fn}" for fn in skipped_files]
                        )

            except Exception as e:
                print(f"AI생성 - 과세특 파일 조회/다운로드 오류: {e}")
                teacher_file_text = ''
            finally:
                if cursor2: cursor2.close()
                if conn2: conn2.close()
        else:
            teacher_file_text = ''

        char_inst = byte_instruction(byte_limit)

        # 공통 학생정보/자료 블록
        common_info_block = f"""[학생 정보]
- 이름: {student_name} (작성 시 이름 및 지칭어 사용 금지, 주어 생략하고 바로 서술)
- 학년/반: {class_grade}학년 {class_no}반
- 과목: {subject_name}

[기초자료 - 교사 메모]
{base_data if base_data else '(등록된 기초자료 없음)'}

[과목 공통활동]
{common_text if common_text else '(등록된 공통활동 없음)'}

[학생 제출 과제]
{submission_text if submission_text else '(제출된 과제 없음)'}

[교사 첨부 파일/자료]
{teacher_file_text if teacher_file_text else '(첨부 파일 없음)'}

[작성 분량]
{char_inst}"""

        if school_level == 'middle':
            free_semester_instruction = ''
            if free_semester:
                free_semester_instruction = """
[자유학기 특별 지시]
- 이 학생은 자유학기제 적용 대상입니다.
- 반드시 작성 내용 맨 앞에 "(자유학기)" 접두사를 붙여 시작하세요.
- 성취도(A~E)를 언급하지 마세요. 과정 중심 평가만 서술합니다.
- 학생의 참여도, 흥미, 태도 변화, 성장 과정에 초점을 두어 서술하세요.
"""
            prompt = f"""당신은 대한민국 중학교에서 20년 이상 근무한 베테랑 교과 담당 교사입니다.
중학생의 성장과 발전 가능성을 잘 포착하여 '교과학습발달상황 - 세부능력 및 특기사항(과세특)'을 작성하는 전문가입니다.
아래 학생의 기초자료와 과목 공통사항을 바탕으로 과세특을 작성해주세요.

{MIDDLE_SUBJECT_WRITING_RULES}

{common_info_block}
{free_semester_instruction}
위 정보를 바탕으로 '{subject_name}' 과목의 세부능력 및 특기사항을 작성해주세요.
기초자료, 공통활동, 제출 과제, 교사 첨부파일을 모두 참고하여 종합적으로 서술하세요.
태그 없이 본문만 출력하세요. 절대 학생 이름이나 지칭어를 포함하지 마세요.

[서술 방법]
- 수업 내 관심/참여 → 탐구/활동 과정 → 성장/변화 → 잠재력/태도 평가 흐름으로 작성
- 교과 내용을 일상생활이나 다른 과목과 연결하여 통합적 사고를 보여줄 것
- 학습 과정에서의 시행착오와 이를 극복한 경험을 긍정적으로 서술
- 학습 의욕, 성실성, 협동심, 자기주도 학습 역량, 잠재력 등이 구체적 행동으로 드러나도록 작성
- 또래와의 협력, 소통, 배려 등 공동체 역량을 자연스럽게 포함"""
        else:
            prompt = f"""당신은 대한민국 고등학교에서 20년 이상 근무한 베테랑 교과 담당 교사입니다.
학생부종합전형에서 높은 평가를 받는 '교과학습발달상황 - 세부능력 및 특기사항(과세특)'을 작성하는 전문가입니다.
아래 학생의 기초자료와 과목 공통사항을 바탕으로 과세특을 작성해주세요.

{SUBJECT_WRITING_RULES}

{common_info_block}

위 정보를 바탕으로 '{subject_name}' 과목의 세부능력 및 특기사항을 작성해주세요.
기초자료, 공통활동, 제출 과제, 교사 첨부파일을 모두 참고하여 종합적으로 서술하세요.
태그 없이 본문만 출력하세요. 절대 학생 이름이나 지칭어를 포함하지 마세요.

[서술 방법]
- 수업 내용에 대한 관심/이해 → 자기주도적 심화 탐구 → 구체적 결과물(보고서, 발표 등) → 교과 역량 평가 흐름으로 작성
- 교과 내용을 실생활 문제나 타 학문과 연결하여 확장적 사고를 보여줄 것
- 탐구 과정에서의 오차, 한계점, 개선 방향을 스스로 인식하는 비판적 사고를 드러낼 것
- 학업적 끈기, 지적 호기심, 논리적 사고력, 의사소통 능력 등 교과 역량이 구체적 행동으로 드러나도록 작성"""

        ai_text, err = call_gemini(prompt, file_parts=file_parts if file_parts else None)
        if err:
            return jsonify({'success': False, 'message': err, 'new_point': new_point})

        if calc_neis_bytes(ai_text) > byte_limit:
            print(f"과세특 바이트 초과: {calc_neis_bytes(ai_text)}B > {byte_limit}B → 재요약")
            ai_text = resummarize(ai_text, byte_limit, subject_name)

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
        print(f"과세특 AI 생성 오류: {e}")
        return jsonify({'success': False, 'message': '과세특 생성 중 오류가 발생했습니다.'})