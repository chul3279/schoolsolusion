"""
assignment.py - 과제 출제/제출 API + 학생 동아리 파일 제출
교사: 과제 출제, 목록, 삭제, 제출현황, 제출파일 다운로드
학생: 수강과목 조회, 과제목록, 과제 제출, 동아리 목록, 동아리 파일 업로드/조회/삭제
"""
import io
import os
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, session

from routes.subject_utils import (
    get_db_connection, sanitize_input, sanitize_html,
    sftp_upload_file, sftp_download_file, sftp_remove_file,
    allowed_file
)

assignment_bp = Blueprint('assignment', __name__)


# ============================================
# 과제 출제 (교사)
# ============================================
@assignment_bp.route('/api/subject/assignment/create', methods=['POST'])
def create_assignment():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        # [보안] school_id, teacher_id 등은 세션에서 가져옴 (클라이언트 위조 방지)
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        teacher_id = session.get('user_id') or sanitize_input(data.get('teacher_id'), 50)
        teacher_name = session.get('user_name') or sanitize_input(data.get('teacher_name'), 100)
        subject_name = sanitize_input(data.get('subject_name'), 100)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        record_year = sanitize_input(data.get('record_year'), 4)
        record_semester = sanitize_input(data.get('record_semester'), 1)
        title = sanitize_html(data.get('title', ''), 200)
        description = sanitize_html(data.get('description', ''), 2000)
        due_date = sanitize_input(data.get('due_date'), 10)

        if not all([school_id, teacher_id, subject_name, class_grade, class_no, title]):
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subject_assignment
            (school_id, teacher_id, teacher_name, subject_name, class_grade, class_no,
             record_year, record_semester, title, description, due_date, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, teacher_id, teacher_name, subject_name, class_grade, class_no,
              record_year, record_semester, title, description, due_date or None))
        conn.commit()

        # 푸시 알림
        try:
            from utils.push_helper import send_push_to_class
            send_push_to_class(school_id, class_grade, class_no, f'새 과제 - {subject_name}', title, '/highschool/st/lesson_activity.html', ['student', 'parent'])
        except Exception as pe:
            print(f"[Assignment] Push error: {pe}")

        return jsonify({'success': True, 'message': f'과제 "{title}"이(가) 등록되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"과제 등록 오류: {e}")
        return jsonify({'success': False, 'message': '과제 등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과제 목록 조회 (교사용)
# ============================================
@assignment_bp.route('/api/subject/assignment/list', methods=['GET'])
def list_assignments():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        subject_name = request.args.get('subject_name', '')
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not school_id:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """SELECT id, teacher_name, subject_name, class_grade, class_no,
                          title, description, due_date, created_at
                   FROM subject_assignment WHERE school_id = %s"""
        params = [school_id]

        # [보안] 교사는 출제 본인만 조회
        if session.get('user_role') == 'teacher':
            query += " AND teacher_id = %s"
            params.append(session.get('user_id'))

        if subject_name:
            query += " AND subject_name = %s"
            params.append(subject_name)
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

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        assignments = []
        for r in rows:
            cursor.execute("SELECT COUNT(*) as cnt FROM subject_submission WHERE assignment_id = %s", (r['id'],))
            sub_cnt = cursor.fetchone()['cnt']
            assignments.append({
                'id': r['id'],
                'teacher_name': r['teacher_name'],
                'subject_name': r['subject_name'],
                'class_grade': r['class_grade'],
                'class_no': r['class_no'],
                'title': r['title'],
                'description': r['description'] or '',
                'due_date': r['due_date'].strftime('%Y-%m-%d') if r['due_date'] else '',
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else '',
                'submission_count': sub_cnt
            })

        return jsonify({'success': True, 'assignments': assignments})

    except Exception as e:
        print(f"과제 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '과제 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과제 삭제 (교사)
# ============================================
@assignment_bp.route('/api/subject/assignment/delete', methods=['POST'])
def delete_assignment():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        assignment_id = sanitize_input(data.get('id'), 20)
        if not assignment_id:
            return jsonify({'success': False, 'message': 'ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 소유자 검증
        cursor.execute("SELECT teacher_id FROM subject_assignment WHERE id = %s", (assignment_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '데이터를 찾을 수 없습니다.'}), 404
        if row['teacher_id'] != session.get('user_id'):
            return jsonify({'success': False, 'message': '본인이 출제한 과제만 삭제할 수 있습니다.'}), 403
        cursor.execute("DELETE FROM subject_assignment WHERE id = %s", (assignment_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '과제가 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 수강 과목 조회
# ============================================
@assignment_bp.route('/api/student/my-subjects', methods=['GET'])
def get_student_subjects():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_id = sanitize_input(request.args.get('student_id') or request.args.get('member_id'), 50)

        if not all([school_id, member_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM timetable_stu WHERE school_id = %s AND member_id = %s", (school_id, member_id))
        row = cursor.fetchone()

        subjects = set()
        if row:
            for i in range(1, 13):
                val = row.get(f'subject{i}')
                if val and val.strip():
                    subjects.add(val.strip())

        cursor.execute("SELECT class_grade, class_no, class_num FROM stu_all WHERE school_id = %s AND member_id = %s", (school_id, member_id))
        stu = cursor.fetchone()
        grade = stu['class_grade'] if stu and stu.get('class_grade') else ''
        class_no = stu['class_no'] if stu and stu.get('class_no') else ''
        student_num = stu['class_num'] if stu and stu.get('class_num') else ''

        return jsonify({
            'success': True,
            'subjects': [{'name': s} for s in sorted(subjects)],
            'grade': grade,
            'class_no': class_no,
            'student_num': student_num
        })

    except Exception as e:
        print(f"학생 과목 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 과제 목록
# ============================================
@assignment_bp.route('/api/student/my-assignments', methods=['GET'])
def get_student_assignments():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_id = sanitize_input(request.args.get('student_id') or request.args.get('member_id'), 50)
        subject_name = request.args.get('subject_name', '')

        if not all([school_id, member_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT class_grade, class_no FROM stu_all WHERE school_id = %s AND member_id = %s", (school_id, member_id))
        stu = cursor.fetchone()
        if not stu:
            return jsonify({'success': True, 'assignments': []})

        query = """SELECT id, subject_name, teacher_name, title, description, due_date, created_at
                   FROM subject_assignment
                   WHERE school_id = %s AND class_grade = %s AND class_no = %s"""
        params = [school_id, stu['class_grade'], stu['class_no']]

        if subject_name:
            query += " AND subject_name = %s"
            params.append(subject_name)

        keyword = sanitize_input(request.args.get('keyword'), 100)
        if keyword:
            query += " AND (title LIKE %s OR description LIKE %s)"
            params.extend([f'%{keyword}%', f'%{keyword}%'])

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        assignments = []
        for r in rows:
            cursor.execute("SELECT id, file_name, submitted_at FROM subject_submission WHERE assignment_id = %s AND student_id = %s",
                           (r['id'], member_id))
            sub = cursor.fetchone()
            assignments.append({
                'id': r['id'],
                'subject_name': r['subject_name'],
                'teacher_name': r['teacher_name'] or '',
                'title': r['title'],
                'description': r['description'] or '',
                'due_date': r['due_date'].strftime('%Y-%m-%d') if r['due_date'] else '',
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else '',
                'submitted': bool(sub),
                'submission_file': sub['file_name'] if sub else '',
                'submission_date': sub['submitted_at'].strftime('%Y-%m-%d %H:%M') if sub and sub['submitted_at'] else ''
            })

        return jsonify({'success': True, 'assignments': assignments})

    except Exception as e:
        print(f"학생 과제 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 과제 제출
# ============================================
@assignment_bp.route('/api/subject/submission/upload', methods=['POST'])
@assignment_bp.route('/api/subject/submission/submit', methods=['POST'])
@assignment_bp.route('/api/subject/submission/create', methods=['POST'])
def submit_assignment():
    conn = None
    cursor = None
    try:
        # form-data와 JSON body 모두 지원
        json_data = request.get_json(silent=True) or {}
        def _f(key, default=''):
            return request.form.get(key) or json_data.get(key, default)

        assignment_id = sanitize_input(_f('assignment_id') or _f('id'), 20)
        student_id = sanitize_input(_f('student_id') or _f('member_id') or session.get('user_id'), 50)
        student_name = sanitize_input(_f('student_name') or _f('member_name') or session.get('user_name', ''), 100)
        comment = (_f('comment') or _f('content') or _f('submission_text', '')).strip()

        if not all([assignment_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '파일이 없습니다. multipart/form-data 형식으로 file 필드를 포함해주세요.'})

        file = request.files['file']
        if not file or not file.filename:
            return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})

        file_data = file.read()
        file_size = len(file_data)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'success': False, 'message': '파일 크기는 10MB를 초과할 수 없습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""SELECT school_id, subject_name, class_grade, class_no, record_year, record_semester
                          FROM subject_assignment WHERE id = %s""", (assignment_id,))
        assignment = cursor.fetchone()
        if not assignment:
            return jsonify({'success': False, 'message': '과제를 찾을 수 없습니다.'})

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{file.filename}"
        remote_path = f"/data/subject/{assignment['school_id']}/submissions/{assignment_id}/{student_id}/{safe_filename}"

        if not sftp_upload_file(file_data, remote_path):
            return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

        cursor.execute("""SELECT id FROM subject_submission WHERE assignment_id = %s AND student_id = %s""",
                       (assignment_id, student_id))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""UPDATE subject_submission SET file_name = %s, file_path = %s, file_size = %s,
                              comment = %s, school_id = %s, subject_name = %s, class_grade = %s, class_no = %s,
                              record_year = %s, record_semester = %s, submitted_at = NOW() WHERE id = %s""",
                           (file.filename, remote_path, file_size, comment,
                            assignment['school_id'], assignment['subject_name'],
                            assignment['class_grade'], assignment['class_no'],
                            assignment['record_year'], assignment['record_semester'], existing['id']))
        else:
            cursor.execute("""INSERT INTO subject_submission
                              (assignment_id, school_id, student_id, student_name, subject_name,
                               class_grade, class_no, record_year, record_semester,
                               file_name, file_path, file_size, comment, submitted_at)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                           (assignment_id, assignment['school_id'], student_id, student_name,
                            assignment['subject_name'], assignment['class_grade'], assignment['class_no'],
                            assignment['record_year'], assignment['record_semester'],
                            file.filename, remote_path, file_size, comment))
        conn.commit()
        return jsonify({'success': True, 'message': '과제가 제출되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"과제 제출 오류: {e}")
        return jsonify({'success': False, 'message': '제출 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 제출 목록 조회 (교사)
# ============================================
@assignment_bp.route('/api/subject/submission/list', methods=['GET'])
def list_submissions():
    conn = None
    cursor = None
    try:
        assignment_id = sanitize_input(request.args.get('assignment_id'), 20)
        if not assignment_id:
            return jsonify({'success': False, 'message': '과제 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        # [보안] 교사는 출제 본인의 과제 제출물만 조회
        if session.get('user_role') == 'teacher':
            cursor.execute("SELECT teacher_id FROM subject_assignment WHERE id = %s", (assignment_id,))
            assignment_row = cursor.fetchone()
            if not assignment_row:
                return jsonify({'success': False, 'message': '과제를 찾을 수 없습니다.'}), 404
            if assignment_row['teacher_id'] != session.get('user_id'):
                return jsonify({'success': False, 'message': '본인이 출제한 과제의 제출물만 조회할 수 있습니다.'}), 403
        cursor.execute("""
            SELECT id, student_id, student_name, file_name, file_size, comment, submitted_at
            FROM subject_submission WHERE assignment_id = %s ORDER BY submitted_at DESC
        """, (assignment_id,))
        rows = cursor.fetchall()

        submissions = []
        for r in rows:
            submissions.append({
                'id': r['id'],
                'student_id': r['student_id'],
                'student_name': r['student_name'],
                'file_name': r['file_name'],
                'file_size': r['file_size'],
                'comment': r['comment'] or '',
                'submitted_at': r['submitted_at'].strftime('%Y-%m-%d %H:%M') if r['submitted_at'] else ''
            })
        return jsonify({'success': True, 'submissions': submissions})

    except Exception as e:
        print(f"제출 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '제출 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 제출 파일 다운로드 (교사)
# ============================================
@assignment_bp.route('/api/subject/submission/download/<int:submission_id>', methods=['GET'])
def download_submission(submission_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, file_name FROM subject_submission WHERE id = %s", (submission_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '제출물을 찾을 수 없습니다.'})
        file_data = sftp_download_file(result['file_path'])
        if not file_data:
            return jsonify({'success': False, 'message': '서버에서 파일을 찾을 수 없습니다.'})
        return send_file(io.BytesIO(file_data), as_attachment=True, download_name=result['file_name'])
    except Exception as e:
        print(f"제출 파일 다운로드 오류: {e}")
        return jsonify({'success': False, 'message': '파일 다운로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 소속 동아리 목록
# ============================================
@assignment_bp.route('/api/student/my-clubs', methods=['GET'])
def get_student_clubs():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id') or request.args.get('member_id'), 50)
        record_year = sanitize_input(request.args.get('record_year'), 4)
        record_semester = sanitize_input(request.args.get('record_semester'), 1)

        if not all([school_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        query = """SELECT cr.club_name, cr.teacher_name,
                          cl.description
                   FROM club_record cr
                   LEFT JOIN club_list cl ON cr.school_id = cl.school_id
                        AND cr.club_name = cl.club_name
                        AND cr.record_year = cl.record_year
                        AND cr.record_semester = cl.record_semester
                   WHERE cr.school_id = %s AND cr.student_id = %s"""
        params = [school_id, student_id]

        if record_year:
            query += " AND cr.record_year = %s"
            params.append(record_year)
        if record_semester:
            query += " AND cr.record_semester = %s"
            params.append(record_semester)

        query += " ORDER BY cr.club_name"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        clubs = []
        for r in rows:
            cursor.execute("""SELECT COUNT(*) as cnt FROM club_files
                              WHERE school_id = %s AND student_id = %s AND club_name = %s""",
                           (school_id, student_id, r['club_name']))
            file_cnt = cursor.fetchone()['cnt']
            clubs.append({
                'club_name': r['club_name'],
                'teacher_name': r['teacher_name'] or '',
                'description': r['description'] or '',
                'file_count': file_cnt
            })

        return jsonify({'success': True, 'clubs': clubs})

    except Exception as e:
        print(f"학생 동아리 목록 오류: {e}")
        return jsonify({'success': False, 'message': '동아리 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 동아리 파일 목록
# ============================================
@assignment_bp.route('/api/student/club-files', methods=['GET'])
def get_student_club_files():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        club_name = request.args.get('club_name', '')

        if not all([school_id, student_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, original_name, file_size, uploaded_by, uploaded_name, created_at
            FROM club_files
            WHERE school_id = %s AND student_id = %s AND club_name = %s
            ORDER BY created_at DESC
        """, (school_id, student_id, club_name))
        rows = cursor.fetchall()

        files = []
        for r in rows:
            files.append({
                'id': r['id'],
                'file_name': r['original_name'],
                'file_size': r['file_size'],
                'uploaded_by': r['uploaded_by'] or '',
                'uploaded_name': r['uploaded_name'] or '',
                'is_mine': (r['uploaded_by'] == student_id),
                'uploaded_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r['created_at'] else ''
            })

        return jsonify({'success': True, 'files': files})

    except Exception as e:
        print(f"학생 동아리 파일 목록 오류: {e}")
        return jsonify({'success': False, 'message': '파일 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 동아리 파일 업로드
# ============================================
@assignment_bp.route('/api/student/club-file/upload', methods=['POST'])
def upload_student_club_file():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.form.get('school_id'), 50)
        member_school = sanitize_input(request.form.get('member_school'), 100)
        student_id = sanitize_input(request.form.get('student_id'), 50)
        student_name = sanitize_input(request.form.get('student_name'), 100)
        club_name = request.form.get('club_name', '').strip()
        record_year = sanitize_input(request.form.get('record_year'), 4) or '2026'
        record_semester = sanitize_input(request.form.get('record_semester'), 1) or '1'

        if not all([school_id, student_id, club_name]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

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

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 학생이 해당 동아리 소속인지 확인
        cursor.execute("""SELECT id FROM club_record
                          WHERE school_id = %s AND student_id = %s AND club_name = %s""",
                       (school_id, student_id, club_name))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '해당 동아리에 소속되어 있지 않습니다.'})

        # teacher_id 조회
        cursor.execute("""SELECT teacher_id FROM club_list
                          WHERE school_id = %s AND club_name = %s
                          AND record_year = %s AND record_semester = %s LIMIT 1""",
                       (school_id, club_name, record_year, record_semester))
        club_info = cursor.fetchone()
        teacher_id = club_info['teacher_id'] if club_info else ''

        original_name = file.filename
        file_ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{original_name}"
        remote_path = f"/data/club/{school_id}/{club_name}/{student_id}/{safe_filename}"

        if not sftp_upload_file(file_data, remote_path):
            return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

        cursor.execute("""
            INSERT INTO club_files
            (school_id, member_school, teacher_id, club_name, student_id, student_name,
             record_year, record_semester, file_name, original_name, file_path, file_size,
             file_type, uploaded_by, uploaded_name, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (school_id, member_school or '', teacher_id, club_name, student_id, student_name,
              record_year, record_semester,
              safe_filename, original_name, remote_path, file_size,
              file_ext, student_id, student_name))
        conn.commit()

        return jsonify({'success': True, 'message': f'"{original_name}" 업로드 완료'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"학생 동아리 파일 업로드 오류: {e}")
        return jsonify({'success': False, 'message': '업로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 동아리 파일 삭제 (본인 업로드 파일만)
# ============================================
@assignment_bp.route('/api/student/club-file/delete', methods=['POST'])
def delete_student_club_file():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        file_id = sanitize_input(data.get('id'), 20)
        student_id = sanitize_input(data.get('student_id'), 50)

        if not all([file_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT file_path, uploaded_by FROM club_files WHERE id = %s", (file_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'})

        if result['uploaded_by'] != student_id:
            return jsonify({'success': False, 'message': '본인이 업로드한 파일만 삭제할 수 있습니다.'})

        if result['file_path']:
            sftp_remove_file(result['file_path'])

        cursor.execute("DELETE FROM club_files WHERE id = %s", (file_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '파일이 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"학생 동아리 파일 삭제 오류: {e}")
        return jsonify({'success': False, 'message': '삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()