"""
SchoolUs 방과후학교 API
- /api/afterschool/list: 프로그램 목록
- /api/afterschool/create: 프로그램 개설
- /api/afterschool/detail: 상세 + 수강생
- /api/afterschool/update: 수정 (모집중)
- /api/afterschool/delete: 삭제 (모집중)
- /api/afterschool/confirm: 신청 일괄 승인/거절
- /api/afterschool/start: confirmed → ongoing
- /api/afterschool/complete: ongoing → completed
- /api/afterschool/apply: 학생 신청
- /api/afterschool/my-programs: 학생용 내 신청
- /api/afterschool/session/save: 회차 정보 저장
- /api/afterschool/attendance/save: 출결 저장
- /api/afterschool/attendance/sheet: 회차별 출석부
- /api/afterschool/attendance/full: 전체 출석부 매트릭스
"""

from flask import Blueprint, request, jsonify, session
from utils.db import get_db_connection, sanitize_input, sanitize_html
import json

afterschool_bp = Blueprint('afterschool', __name__)


# ============================================
# 프로그램 목록
# ============================================
@afterschool_bp.route('/api/afterschool/list', methods=['GET'])
def list_programs():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        status_filter = sanitize_input(request.args.get('status'), 20)

        if not school_id:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        query = """
            SELECT ap.*,
                   (SELECT COUNT(*) FROM afterschool_enrollment ae WHERE ae.program_id = ap.id AND ae.status IN ('applied','approved')) AS enrolled_count
            FROM afterschool_program ap
            WHERE ap.school_id = %s
        """
        params = [school_id]

        if status_filter:
            query += " AND ap.status = %s"
            params.append(status_filter)

        query += " ORDER BY ap.created_at DESC"
        cursor.execute(query, params)

        programs = []
        for p in cursor.fetchall():
            programs.append({
                'id': p['id'],
                'program_name': p['program_name'],
                'description': p.get('description') or '',
                'instructor_name': p.get('instructor_name') or '',
                'target_grades': p['target_grades'],
                'max_students': p['max_students'],
                'total_sessions': p['total_sessions'],
                'day_of_week': p.get('day_of_week') or '',
                'time_slot': p.get('time_slot') or '',
                'start_date': p['start_date'].strftime('%Y-%m-%d') if p.get('start_date') else '',
                'end_date': p['end_date'].strftime('%Y-%m-%d') if p.get('end_date') else '',
                'status': p['status'],
                'enrolled_count': int(p['enrolled_count'] or 0),
                'created_at': p['created_at'].strftime('%Y-%m-%d') if p.get('created_at') else ''
            })

        return jsonify({'success': True, 'programs': programs})

    except Exception as e:
        print(f"방과후 목록 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 프로그램 개설
# ============================================
@afterschool_bp.route('/api/afterschool/create', methods=['POST'])
def create_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        program_name = sanitize_html(data.get('program_name') or data.get('name') or '', 200)
        description = sanitize_html(data.get('description', ''), 2000)
        instructor_name = sanitize_input(data.get('instructor_name') or data.get('teacher_name') or '', 100)
        target_grades = sanitize_input(data.get('target_grades') or data.get('target_grade') or 'all', 50)
        max_students = int(data.get('max_students') or data.get('max') or 30)
        total_sessions = int(data.get('total_sessions') or data.get('sessions') or 10)
        day_of_week = sanitize_input(data.get('day_of_week') or data.get('dow') or '', 20)
        # time_slot: 직접 전달 또는 start_time+end_time 조합
        time_slot = sanitize_input(data.get('time_slot') or '', 50)
        if not time_slot and data.get('start_time') and data.get('end_time'):
            time_slot = f"{data.get('start_time')}~{data.get('end_time')}"
        start_date = sanitize_input(data.get('start_date'), 10)
        end_date = sanitize_input(data.get('end_date'), 10)
        created_by = session.get('user_id')

        if not school_id or not program_name or not start_date or not end_date:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO afterschool_program
            (school_id, program_name, description, instructor_name, target_grades,
             max_students, total_sessions, day_of_week, time_slot, start_date, end_date, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, program_name, description, instructor_name, target_grades,
              max_students, total_sessions, day_of_week, time_slot, start_date, end_date, created_by))

        return jsonify({'success': True, 'message': '프로그램이 등록되었습니다.', 'program_id': cursor.lastrowid})

    except Exception as e:
        print(f"방과후 생성 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 프로그램 상세 + 수강생
# ============================================
@afterschool_bp.route('/api/afterschool/detail', methods=['GET'])
def get_program_detail():
    conn = None
    cursor = None
    try:
        program_id = sanitize_input(request.args.get('id'), 20)
        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})

        # 수강생 목록
        cursor.execute("""
            SELECT ae.*, m.member_name
            FROM afterschool_enrollment ae
            LEFT JOIN member m ON ae.student_id = m.member_id
            WHERE ae.program_id = %s
            ORDER BY ae.class_grade, ae.class_no, ae.class_num
        """, (program_id,))
        enrollments = []
        for e in cursor.fetchall():
            enrollments.append({
                'id': e['id'],
                'student_id': e['student_id'],
                'student_name': e.get('student_name') or e.get('member_name') or '',
                'class_grade': e.get('class_grade') or '',
                'class_no': e.get('class_no') or '',
                'class_num': e.get('class_num') or '',
                'status': e['status'],
                'applied_at': e['applied_at'].strftime('%Y-%m-%d %H:%M') if e.get('applied_at') else ''
            })

        # 회차 정보
        cursor.execute("SELECT * FROM afterschool_session WHERE program_id = %s ORDER BY session_no", (program_id,))
        sessions = []
        for s in cursor.fetchall():
            sessions.append({
                'session_no': s['session_no'],
                'session_date': s['session_date'].strftime('%Y-%m-%d') if s.get('session_date') else '',
                'topic': s.get('topic') or ''
            })

        program = {
            'id': p['id'],
            'program_name': p['program_name'],
            'description': p.get('description') or '',
            'instructor_name': p.get('instructor_name') or '',
            'target_grades': p['target_grades'],
            'max_students': p['max_students'],
            'total_sessions': p['total_sessions'],
            'day_of_week': p.get('day_of_week') or '',
            'time_slot': p.get('time_slot') or '',
            'start_date': p['start_date'].strftime('%Y-%m-%d') if p.get('start_date') else '',
            'end_date': p['end_date'].strftime('%Y-%m-%d') if p.get('end_date') else '',
            'status': p['status'],
            'survey_id': p.get('survey_id'),
            'created_at': p['created_at'].strftime('%Y-%m-%d') if p.get('created_at') else ''
        }

        return jsonify({'success': True, 'program': program, 'enrollments': enrollments, 'sessions': sessions})

    except Exception as e:
        print(f"방과후 상세 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 프로그램 수정 (모집중만)
# ============================================
@afterschool_bp.route('/api/afterschool/update', methods=['POST'])
def update_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('id'), 20)
        program_name = sanitize_html(data.get('program_name') or data.get('name') or '', 200)
        description = sanitize_html(data.get('description', ''), 2000)
        instructor_name = sanitize_input(data.get('instructor_name') or data.get('teacher_name') or '', 100)
        target_grades = sanitize_input(data.get('target_grades') or data.get('target_grade') or 'all', 50)
        max_students = int(data.get('max_students') or data.get('max') or 30)
        total_sessions = int(data.get('total_sessions') or data.get('sessions') or 10)
        day_of_week = sanitize_input(data.get('day_of_week') or data.get('dow') or '', 20)
        time_slot = sanitize_input(data.get('time_slot') or '', 50)
        if not time_slot and data.get('start_time') and data.get('end_time'):
            time_slot = f"{data.get('start_time')}~{data.get('end_time')}"
        start_date = sanitize_input(data.get('start_date'), 10)
        end_date = sanitize_input(data.get('end_date'), 10)

        if not program_id or not program_name:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if p['status'] != 'recruiting':
            return jsonify({'success': False, 'message': '모집중인 프로그램만 수정할 수 있습니다.'})

        cursor.execute("""
            UPDATE afterschool_program SET
            program_name=%s, description=%s, instructor_name=%s, target_grades=%s,
            max_students=%s, total_sessions=%s, day_of_week=%s, time_slot=%s,
            start_date=%s, end_date=%s
            WHERE id=%s
        """, (program_name, description, instructor_name, target_grades,
              max_students, total_sessions, day_of_week, time_slot,
              start_date, end_date, program_id))

        return jsonify({'success': True, 'message': '프로그램이 수정되었습니다.'})

    except Exception as e:
        print(f"방과후 수정 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 프로그램 삭제 (모집중만)
# ============================================
@afterschool_bp.route('/api/afterschool/delete', methods=['POST'])
def delete_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('id'), 20)

        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if p['status'] != 'recruiting':
            return jsonify({'success': False, 'message': '모집중인 프로그램만 삭제할 수 있습니다.'})

        cursor.execute("DELETE FROM afterschool_program WHERE id = %s", (program_id,))
        return jsonify({'success': True, 'message': '프로그램이 삭제되었습니다.'})

    except Exception as e:
        print(f"방과후 삭제 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 신청 일괄 승인/거절 → confirmed
# ============================================
@afterschool_bp.route('/api/afterschool/confirm', methods=['POST'])
def confirm_enrollments():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('program_id'), 20)
        enrollments = data.get('enrollments', [])  # [{enrollment_id, status}]

        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        conn.begin()

        for e in enrollments:
            eid = sanitize_input(e.get('enrollment_id'), 20)
            st = e.get('status', 'approved')
            if st not in ('approved', 'rejected'):
                st = 'approved'
            if eid:
                if st == 'approved':
                    cursor.execute("UPDATE afterschool_enrollment SET status=%s, approved_at=NOW() WHERE id=%s AND program_id=%s", (st, eid, program_id))
                else:
                    cursor.execute("UPDATE afterschool_enrollment SET status=%s WHERE id=%s AND program_id=%s", (st, eid, program_id))

        # 프로그램 상태를 confirmed로
        cursor.execute("UPDATE afterschool_program SET status='confirmed' WHERE id=%s AND status='recruiting'", (program_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '수강 확정이 완료되었습니다.'})

    except Exception as e:
        print(f"방과후 확정 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '수강 확정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# confirmed → ongoing
# ============================================
@afterschool_bp.route('/api/afterschool/start', methods=['POST'])
def start_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('id'), 20)

        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if p['status'] != 'confirmed':
            return jsonify({'success': False, 'message': '확정된 프로그램만 시작할 수 있습니다.'})

        cursor.execute("UPDATE afterschool_program SET status='ongoing' WHERE id=%s", (program_id,))
        return jsonify({'success': True, 'message': '프로그램이 시작되었습니다.'})

    except Exception as e:
        print(f"방과후 시작 오류: {e}")
        return jsonify({'success': False, 'message': '프로그램 시작 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# ongoing → completed (만족도 설문 자동 생성 옵션)
# ============================================
@afterschool_bp.route('/api/afterschool/complete', methods=['POST'])
def complete_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('id'), 20)
        create_survey = data.get('create_survey', False)

        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if p['status'] != 'ongoing':
            return jsonify({'success': False, 'message': '진행중인 프로그램만 완료 처리할 수 있습니다.'})

        conn.begin()

        survey_id = None
        if create_survey:
            # 만족도 설문 자동 생성
            cursor.execute("""
                INSERT INTO survey (school_id, title, description, target_role, target_grades, status, created_by)
                VALUES (%s, %s, %s, 'student', %s, 'active', %s)
            """, (p['school_id'],
                  f"[방과후] {p['program_name']} 만족도 조사",
                  f"{p['program_name']} 프로그램에 대한 만족도 조사입니다.",
                  p['target_grades'],
                  session.get('user_id')))
            survey_id = cursor.lastrowid

            # 기본 만족도 문항 추가
            default_questions = [
                ('프로그램 전반적인 만족도를 평가해주세요.', 'rating', json.dumps({"min": 1, "max": 5})),
                ('수업 내용은 유익했나요?', 'single', json.dumps(["매우 그렇다", "그렇다", "보통", "아니다", "매우 아니다"])),
                ('강사의 수업 진행은 어떠했나요?', 'single', json.dumps(["매우 좋음", "좋음", "보통", "부족", "매우 부족"])),
                ('개선할 점이나 건의사항을 자유롭게 작성해주세요.', 'text', None)
            ]
            for i, (qt, qtype, opts) in enumerate(default_questions):
                cursor.execute("""
                    INSERT INTO survey_question (survey_id, question_order, question_text, question_type, options, required)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (survey_id, i + 1, qt, qtype, opts, 1 if qtype != 'text' else 0))

            cursor.execute("UPDATE survey SET started_at=NOW() WHERE id=%s", (survey_id,))

        cursor.execute("UPDATE afterschool_program SET status='completed', survey_id=%s WHERE id=%s", (survey_id, program_id))
        conn.commit()

        msg = '프로그램이 완료 처리되었습니다.'
        if survey_id:
            msg += ' 만족도 설문이 자동 생성되었습니다.'

        return jsonify({'success': True, 'message': msg, 'survey_id': survey_id})

    except Exception as e:
        print(f"방과후 완료 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '프로그램 완료 처리 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 신청
# ============================================
@afterschool_bp.route('/api/afterschool/apply', methods=['POST'])
def apply_program():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('program_id'), 20)
        user_id = session.get('user_id')
        user_role = session.get('user_role')

        if not user_id or user_role != 'student':
            return jsonify({'success': False, 'message': '학생만 신청할 수 있습니다.'})
        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 프로그램 확인
        cursor.execute("SELECT * FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if p['status'] != 'recruiting':
            return jsonify({'success': False, 'message': '현재 모집중인 프로그램이 아닙니다.'})

        # 학년 확인
        user_grade = session.get('class_grade', '')
        if p['target_grades'] != 'all':
            allowed = [g.strip() for g in p['target_grades'].split(',')]
            if user_grade not in allowed:
                return jsonify({'success': False, 'message': '대상 학년이 아닙니다.'})

        # 정원 확인
        cursor.execute("SELECT COUNT(*) AS cnt FROM afterschool_enrollment WHERE program_id=%s AND status IN ('applied','approved')", (program_id,))
        current = int(cursor.fetchone()['cnt'] or 0)
        if current >= p['max_students']:
            return jsonify({'success': False, 'message': '정원이 초과되었습니다.'})

        # 중복 신청 확인
        cursor.execute("SELECT id FROM afterschool_enrollment WHERE program_id=%s AND student_id=%s", (program_id, user_id))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 신청한 프로그램입니다.'})

        # 학생 정보 조회
        cursor.execute("SELECT sa.member_name, sa.class_grade, sa.class_no, sa.class_num FROM stu_all sa WHERE sa.member_id = %s AND sa.school_id = %s", (user_id, p['school_id']))
        stu = cursor.fetchone()
        student_name = stu['member_name'] if stu else ''
        class_grade = stu.get('class_grade', '') if stu else ''
        class_no = stu.get('class_no', '') if stu else ''
        class_num = stu.get('class_num', '') if stu else ''

        cursor.execute("""
            INSERT INTO afterschool_enrollment (program_id, student_id, student_name, class_grade, class_no, class_num)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (program_id, user_id, student_name, class_grade, class_no, class_num))

        return jsonify({'success': True, 'message': '신청이 완료되었습니다.'})

    except Exception as e:
        print(f"방과후 신청 오류: {e}")
        return jsonify({'success': False, 'message': '신청 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수강 취소 (학생 본인 또는 교사)
# ============================================
@afterschool_bp.route('/api/afterschool/cancel', methods=['POST'])
def cancel_enrollment():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('program_id'), 20)
        enrollment_id = sanitize_input(data.get('enrollment_id'), 20)
        student_id = sanitize_input(data.get('student_id'), 50)
        user_id = session.get('user_id')
        user_role = session.get('user_role')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # enrollment 조회 조건: enrollment_id 또는 (program_id + student_id)
        if enrollment_id:
            cursor.execute("SELECT * FROM afterschool_enrollment WHERE id = %s", (enrollment_id,))
        elif program_id and student_id:
            cursor.execute("SELECT * FROM afterschool_enrollment WHERE program_id = %s AND student_id = %s", (program_id, student_id))
        elif program_id and user_role == 'student':
            cursor.execute("SELECT * FROM afterschool_enrollment WHERE program_id = %s AND student_id = %s", (program_id, user_id))
        else:
            return jsonify({'success': False, 'message': '취소할 수강 정보가 필요합니다.'})

        enrollment = cursor.fetchone()
        if not enrollment:
            return jsonify({'success': False, 'message': '수강 신청 내역을 찾을 수 없습니다.'})

        # 권한 확인: 학생 본인 또는 교사
        if user_role == 'student' and enrollment['student_id'] != user_id:
            return jsonify({'success': False, 'message': '본인의 수강만 취소할 수 있습니다.'})

        # 프로그램 상태 확인
        cursor.execute("SELECT status FROM afterschool_program WHERE id = %s", (enrollment['program_id'],))
        prog = cursor.fetchone()
        if not prog:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})
        if prog['status'] not in ('recruiting', 'confirmed'):
            return jsonify({'success': False, 'message': '진행중이거나 완료된 프로그램은 취소할 수 없습니다.'})

        # 이미 취소된 상태 확인
        if enrollment['status'] == 'withdrawn':
            return jsonify({'success': False, 'message': '이미 취소된 수강입니다.'})

        cursor.execute("UPDATE afterschool_enrollment SET status = 'withdrawn' WHERE id = %s", (enrollment['id'],))
        return jsonify({'success': True, 'message': '수강이 취소되었습니다.'})

    except Exception as e:
        print(f"방과후 수강 취소 오류: {e}")
        return jsonify({'success': False, 'message': '수강 취소 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생용 내 신청 목록
# ============================================
@afterschool_bp.route('/api/afterschool/my-programs', methods=['GET'])
def my_programs():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        school_id = session.get('school_id')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ap.id, ap.program_name, ap.instructor_name, ap.day_of_week, ap.time_slot,
                   ap.start_date, ap.end_date, ap.status AS program_status,
                   ae.status AS enrollment_status, ae.applied_at
            FROM afterschool_enrollment ae
            JOIN afterschool_program ap ON ae.program_id = ap.id
            WHERE ae.student_id = %s AND ap.school_id = %s
            ORDER BY ae.applied_at DESC
        """, (user_id, school_id))

        programs = []
        for r in cursor.fetchall():
            programs.append({
                'id': r['id'],
                'program_name': r['program_name'],
                'instructor_name': r.get('instructor_name') or '',
                'day_of_week': r.get('day_of_week') or '',
                'time_slot': r.get('time_slot') or '',
                'start_date': r['start_date'].strftime('%Y-%m-%d') if r.get('start_date') else '',
                'end_date': r['end_date'].strftime('%Y-%m-%d') if r.get('end_date') else '',
                'program_status': r['program_status'],
                'enrollment_status': r['enrollment_status'],
                'applied_at': r['applied_at'].strftime('%Y-%m-%d') if r.get('applied_at') else ''
            })

        return jsonify({'success': True, 'programs': programs})

    except Exception as e:
        print(f"내 방과후 목록 오류: {e}")
        return jsonify({'success': False, 'message': '목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 회차 정보 저장
# ============================================
@afterschool_bp.route('/api/afterschool/session/save', methods=['POST'])
def save_session():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('program_id'), 20)
        session_no = int(data.get('session_no', 0))
        session_date = sanitize_input(data.get('session_date'), 10)
        topic = sanitize_html(data.get('topic', ''), 200)

        if not program_id or not session_no or not session_date:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO afterschool_session (program_id, session_no, session_date, topic)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE session_date=VALUES(session_date), topic=VALUES(topic)
        """, (program_id, session_no, session_date, topic))

        return jsonify({'success': True, 'message': '회차 정보가 저장되었습니다.'})

    except Exception as e:
        print(f"방과후 회차 저장 오류: {e}")
        return jsonify({'success': False, 'message': '회차 정보 저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 회차별 출결 저장
# ============================================
@afterschool_bp.route('/api/afterschool/attendance/save', methods=['POST'])
def save_attendance():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        program_id = sanitize_input(data.get('program_id'), 20)
        session_no = int(data.get('session_no', 0))
        session_date = sanitize_input(data.get('session_date'), 10)
        records = data.get('records', [])

        if not program_id or not session_no or not session_date:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        valid_statuses = {'present', 'absent', 'late', 'excused'}

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        conn.begin()

        # 회차 정보 자동 생성/업데이트
        cursor.execute("""
            INSERT INTO afterschool_session (program_id, session_no, session_date)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE session_date=VALUES(session_date)
        """, (program_id, session_no, session_date))

        saved = 0
        for rec in records:
            enrollment_id = sanitize_input(rec.get('enrollment_id'), 20)
            status = rec.get('status', 'present')
            memo = sanitize_input(rec.get('memo', ''), 200)

            if not enrollment_id or status not in valid_statuses:
                continue

            cursor.execute("""
                INSERT INTO afterschool_attendance (program_id, enrollment_id, session_no, session_date, status, memo)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), memo=VALUES(memo), session_date=VALUES(session_date)
            """, (program_id, enrollment_id, session_no, session_date, status, memo))
            saved += 1

        conn.commit()
        return jsonify({'success': True, 'message': f'{saved}명 출결 저장 완료'})

    except Exception as e:
        print(f"방과후 출결 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '출결 저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 회차별 출석부
# ============================================
@afterschool_bp.route('/api/afterschool/attendance/sheet', methods=['GET'])
def get_attendance_sheet():
    conn = None
    cursor = None
    try:
        program_id = sanitize_input(request.args.get('program_id'), 20)
        session_no = sanitize_input(request.args.get('session_no'), 10)

        if not program_id or not session_no:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ae.id AS enrollment_id, ae.student_id, ae.student_name, ae.class_grade, ae.class_no, ae.class_num,
                   aa.status AS att_status, aa.memo AS att_memo
            FROM afterschool_enrollment ae
            LEFT JOIN afterschool_attendance aa ON aa.enrollment_id = ae.id AND aa.session_no = %s
            WHERE ae.program_id = %s AND ae.status = 'approved'
            ORDER BY ae.class_grade, ae.class_no, CAST(ae.class_num AS UNSIGNED)
        """, (session_no, program_id))

        students = []
        for r in cursor.fetchall():
            students.append({
                'enrollment_id': r['enrollment_id'],
                'student_name': r['student_name'] or '',
                'class_grade': r.get('class_grade') or '',
                'class_no': r.get('class_no') or '',
                'class_num': r.get('class_num') or '',
                'status': r['att_status'] or '',
                'memo': r['att_memo'] or ''
            })

        # 회차 정보
        cursor.execute("SELECT * FROM afterschool_session WHERE program_id=%s AND session_no=%s", (program_id, session_no))
        sess = cursor.fetchone()
        session_info = {
            'session_no': int(session_no),
            'session_date': sess['session_date'].strftime('%Y-%m-%d') if sess and sess.get('session_date') else '',
            'topic': sess.get('topic', '') if sess else ''
        }

        return jsonify({'success': True, 'students': students, 'session_info': session_info})

    except Exception as e:
        print(f"방과후 출석부 오류: {e}")
        return jsonify({'success': False, 'message': '출석부 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 전체 출석부 매트릭스 (인쇄용)
# ============================================
@afterschool_bp.route('/api/afterschool/attendance/full', methods=['GET'])
def get_full_attendance():
    conn = None
    cursor = None
    try:
        program_id = sanitize_input(request.args.get('program_id'), 20)

        if not program_id:
            return jsonify({'success': False, 'message': '프로그램 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 프로그램 정보
        cursor.execute("SELECT * FROM afterschool_program WHERE id = %s", (program_id,))
        p = cursor.fetchone()
        if not p:
            return jsonify({'success': False, 'message': '프로그램을 찾을 수 없습니다.'})

        # 승인된 수강생
        cursor.execute("""
            SELECT id AS enrollment_id, student_name, class_grade, class_no, class_num
            FROM afterschool_enrollment
            WHERE program_id = %s AND status = 'approved'
            ORDER BY class_grade, class_no, CAST(class_num AS UNSIGNED)
        """, (program_id,))
        students = cursor.fetchall()

        # 회차 정보
        cursor.execute("SELECT session_no, session_date, topic FROM afterschool_session WHERE program_id = %s ORDER BY session_no", (program_id,))
        sessions = []
        for s in cursor.fetchall():
            sessions.append({
                'session_no': s['session_no'],
                'session_date': s['session_date'].strftime('%Y-%m-%d') if s.get('session_date') else '',
                'topic': s.get('topic') or ''
            })

        # 전체 출결 데이터
        cursor.execute("""
            SELECT enrollment_id, session_no, status
            FROM afterschool_attendance
            WHERE program_id = %s
        """, (program_id,))
        att_map = {}
        for a in cursor.fetchall():
            key = f"{a['enrollment_id']}_{a['session_no']}"
            att_map[key] = a['status']

        # 매트릭스 구성
        matrix = []
        for stu in students:
            row = {
                'student_name': stu['student_name'] or '',
                'class_info': f"{stu.get('class_grade','')}-{stu.get('class_no','')}-{stu.get('class_num','')}",
                'attendance': []
            }
            for s in sessions:
                key = f"{stu['enrollment_id']}_{s['session_no']}"
                row['attendance'].append(att_map.get(key, ''))
            matrix.append(row)

        return jsonify({
            'success': True,
            'program': {
                'program_name': p['program_name'],
                'instructor_name': p.get('instructor_name') or '',
                'day_of_week': p.get('day_of_week') or '',
                'time_slot': p.get('time_slot') or '',
                'start_date': p['start_date'].strftime('%Y-%m-%d') if p.get('start_date') else '',
                'end_date': p['end_date'].strftime('%Y-%m-%d') if p.get('end_date') else ''
            },
            'sessions': sessions,
            'matrix': matrix
        })

    except Exception as e:
        print(f"방과후 전체 출석부 오류: {e}")
        return jsonify({'success': False, 'message': '전체 출석부 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
