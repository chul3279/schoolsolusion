"""
SchoolUs 출결 관리 API
- /api/attendance/sheet: 반+날짜별 출석부
- /api/attendance/save: 일괄 출결 저장
- /api/attendance/student-history: 학생별 출결 이력
- /api/attendance/monthly: 월간 출결 요약
- /api/attendance/stats: 반 출결 통계
- /api/attendance/my: 내 출결 현황 (학생용)
- /api/attendance/child: 자녀 출결 현황 (학부모용)
"""

from flask import Blueprint, request, jsonify, session
from utils.db import get_db_connection, sanitize_input

attendance_bp = Blueprint('attendance', __name__)


# ============================================
# 출석부 조회 (교사용)
# ============================================
@attendance_bp.route('/api/attendance/sheet', methods=['GET'])
def get_attendance_sheet():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        att_date = sanitize_input(request.args.get('date'), 10)

        if not all([school_id, class_grade, class_no, att_date]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT sa.member_id, m.member_name, sa.class_num,
                   a.status AS att_status, a.memo AS att_memo
            FROM stu_all sa
            JOIN member m ON sa.member_id = m.member_id
            LEFT JOIN attendance a ON a.student_id = sa.member_id
              AND a.school_id = sa.school_id AND a.attendance_date = %s
            WHERE sa.school_id = %s AND sa.class_grade = %s AND sa.class_no = %s
            ORDER BY CAST(sa.class_num AS UNSIGNED)
        """, (att_date, school_id, class_grade, class_no))

        students = []
        for row in cursor.fetchall():
            students.append({
                'member_id': row['member_id'],
                'member_name': row['member_name'],
                'class_num': row.get('class_num', ''),
                'status': row['att_status'] or '',
                'memo': row['att_memo'] or ''
            })

        return jsonify({'success': True, 'students': students, 'date': att_date})

    except Exception as e:
        print(f"출석부 조회 오류: {e}")
        return jsonify({'success': False, 'message': '출석부 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 출결 일괄 저장 (교사용)
# ============================================
@attendance_bp.route('/api/attendance/save', methods=['POST'])
def save_attendance():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        att_date = sanitize_input(data.get('date'), 10)
        records = data.get('records', [])
        teacher_id = session.get('user_id')

        if not all([school_id, class_grade, class_no, att_date]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        if not records:
            return jsonify({'success': False, 'message': '저장할 출결 데이터가 없습니다.'})

        valid_statuses = {'present', 'absent', 'late', 'early_leave', 'sick'}

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        saved = 0
        absent_students = []
        for rec in records:
            student_id = sanitize_input(rec.get('student_id'), 50)
            status = rec.get('status', 'present')
            memo = sanitize_input(rec.get('memo', ''), 200)

            if not student_id or status not in valid_statuses:
                continue

            cursor.execute("""
                INSERT INTO attendance (school_id, class_grade, class_no, student_id, attendance_date, status, memo, checked_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status=VALUES(status), memo=VALUES(memo), checked_by=VALUES(checked_by)
            """, (school_id, class_grade, class_no, student_id, att_date, status, memo, teacher_id))
            saved += 1

            if status in ('absent', 'late', 'sick'):
                absent_students.append({'student_id': student_id, 'status': status})

        conn.commit()

        # 결석/지각/병결 시 학부모에게 푸시 알림
        if absent_students:
            try:
                from utils.push_helper import send_push_to_student
                status_names = {'absent': '결석', 'late': '지각', 'sick': '병결', 'early_leave': '조퇴'}
                for s in absent_students:
                    status_name = status_names.get(s['status'], s['status'])
                    send_push_to_student(
                        school_id, s['student_id'],
                        f'출결 알림 - {status_name}',
                        f'자녀가 오늘 {status_name} 처리되었습니다.',
                        '/highschool/fm_homeroom.html'
                    )
            except Exception as pe:
                print(f"[Attendance] Push error: {pe}")

        return jsonify({'success': True, 'message': f'{saved}명 출결 저장 완료', 'saved': saved})

    except Exception as e:
        print(f"출결 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '출결 저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생별 출결 이력
# ============================================
@attendance_bp.route('/api/attendance/student-history', methods=['GET'])
def get_student_history():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        start_date = sanitize_input(request.args.get('start_date'), 10)
        end_date = sanitize_input(request.args.get('end_date'), 10)

        if not all([school_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        query = "SELECT attendance_date, status, memo FROM attendance WHERE school_id = %s AND student_id = %s"
        params = [school_id, student_id]

        if start_date:
            query += " AND attendance_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND attendance_date <= %s"
            params.append(end_date)

        query += " ORDER BY attendance_date DESC LIMIT 100"
        cursor.execute(query, params)

        history = [{'date': r['attendance_date'].strftime('%Y-%m-%d'), 'status': r['status'], 'memo': r['memo'] or ''} for r in cursor.fetchall()]

        return jsonify({'success': True, 'history': history})

    except Exception as e:
        print(f"출결 이력 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 월간 출결 요약 (캘린더용)
# ============================================
@attendance_bp.route('/api/attendance/monthly', methods=['GET'])
def get_monthly_summary():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        month = sanitize_input(request.args.get('month'), 7)  # YYYY-MM

        if not all([school_id, class_grade, class_no, month]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 해당 월의 일별 출결 집계
        cursor.execute("""
            SELECT attendance_date,
                   SUM(status = 'present') AS present_cnt,
                   SUM(status = 'absent') AS absent_cnt,
                   SUM(status = 'late') AS late_cnt,
                   SUM(status = 'early_leave') AS early_leave_cnt,
                   SUM(status = 'sick') AS sick_cnt,
                   COUNT(*) AS total_cnt
            FROM attendance
            WHERE school_id = %s AND class_grade = %s AND class_no = %s
              AND DATE_FORMAT(attendance_date, '%%Y-%%m') = %s
            GROUP BY attendance_date
            ORDER BY attendance_date
        """, (school_id, class_grade, class_no, month))

        daily = []
        for r in cursor.fetchall():
            total = int(r['total_cnt'] or 0)
            present = int(r['present_cnt'] or 0)
            daily.append({
                'date': r['attendance_date'].strftime('%Y-%m-%d'),
                'present': present,
                'absent': int(r['absent_cnt'] or 0),
                'late': int(r['late_cnt'] or 0),
                'early_leave': int(r['early_leave_cnt'] or 0),
                'sick': int(r['sick_cnt'] or 0),
                'total': total,
                'rate': round(present / total * 100, 1) if total > 0 else 0
            })

        return jsonify({'success': True, 'daily': daily, 'month': month})

    except Exception as e:
        print(f"월간 출결 요약 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 반 출결 통계
# ============================================
@attendance_bp.route('/api/attendance/stats', methods=['GET'])
def get_attendance_stats():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        month = sanitize_input(request.args.get('month'), 7)

        if not all([school_id, class_grade, class_no]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        date_filter = ""
        date_params = []
        if month:
            date_filter = " AND DATE_FORMAT(a.attendance_date, '%%Y-%%m') = %s"
            date_params = [month]

        cursor.execute("""
            SELECT sa.member_id, m.member_name, sa.class_num,
                   SUM(a.status = 'present') AS present_cnt,
                   SUM(a.status = 'absent') AS absent_cnt,
                   SUM(a.status = 'late') AS late_cnt,
                   SUM(a.status = 'early_leave') AS early_leave_cnt,
                   SUM(a.status = 'sick') AS sick_cnt,
                   COUNT(a.id) AS total_cnt
            FROM stu_all sa
            JOIN member m ON sa.member_id = m.member_id
            LEFT JOIN attendance a ON a.student_id = sa.member_id AND a.school_id = sa.school_id""" + date_filter + """
            WHERE sa.school_id = %s AND sa.class_grade = %s AND sa.class_no = %s
            GROUP BY sa.member_id, m.member_name, sa.class_num
            ORDER BY CAST(sa.class_num AS UNSIGNED)
        """, date_params + [school_id, class_grade, class_no])

        stats = []
        for r in cursor.fetchall():
            total = int(r['total_cnt'] or 0)
            present = int(r['present_cnt'] or 0)
            stats.append({
                'member_id': r['member_id'],
                'member_name': r['member_name'],
                'class_num': r.get('class_num', ''),
                'present': present,
                'absent': int(r['absent_cnt'] or 0),
                'late': int(r['late_cnt'] or 0),
                'early_leave': int(r['early_leave_cnt'] or 0),
                'sick': int(r['sick_cnt'] or 0),
                'total': total,
                'rate': round(present / total * 100, 1) if total > 0 else 0
            })

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        print(f"출결 통계 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 내 출결 현황 (학생용)
# ============================================
@attendance_bp.route('/api/attendance/my', methods=['GET'])
def get_my_attendance():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        student_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)
        month = sanitize_input(request.args.get('month'), 7)

        if not all([school_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 이번 달 요약
        if not month:
            from datetime import datetime
            month = datetime.now().strftime('%Y-%m')

        cursor.execute("""
            SELECT
                SUM(status = 'present') AS present_cnt,
                SUM(status = 'absent') AS absent_cnt,
                SUM(status = 'late') AS late_cnt,
                SUM(status = 'early_leave') AS early_leave_cnt,
                SUM(status = 'sick') AS sick_cnt,
                COUNT(*) AS total_cnt
            FROM attendance
            WHERE school_id = %s AND student_id = %s
              AND DATE_FORMAT(attendance_date, '%%Y-%%m') = %s
        """, (school_id, student_id, month))
        summary = cursor.fetchone()

        # 최근 이력
        cursor.execute("""
            SELECT attendance_date, status, memo
            FROM attendance
            WHERE school_id = %s AND student_id = %s
            ORDER BY attendance_date DESC LIMIT 10
        """, (school_id, student_id))
        recent = [{'date': r['attendance_date'].strftime('%Y-%m-%d'), 'status': r['status'], 'memo': r['memo'] or ''} for r in cursor.fetchall()]

        return jsonify({
            'success': True,
            'month': month,
            'summary': {
                'present': int(summary['present_cnt'] or 0) if summary else 0,
                'absent': int(summary['absent_cnt'] or 0) if summary else 0,
                'late': int(summary['late_cnt'] or 0) if summary else 0,
                'early_leave': int(summary['early_leave_cnt'] or 0) if summary else 0,
                'sick': int(summary['sick_cnt'] or 0) if summary else 0,
                'total': int(summary['total_cnt'] or 0) if summary else 0
            },
            'recent': recent
        })

    except Exception as e:
        print(f"내 출결 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 자녀 출결 현황 (학부모용)
# ============================================
@attendance_bp.route('/api/attendance/child', methods=['GET'])
def get_child_attendance():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        month = sanitize_input(request.args.get('month'), 7)

        if not all([school_id, student_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        if not month:
            from datetime import datetime
            month = datetime.now().strftime('%Y-%m')

        cursor.execute("""
            SELECT
                SUM(status = 'present') AS present_cnt,
                SUM(status = 'absent') AS absent_cnt,
                SUM(status = 'late') AS late_cnt,
                SUM(status = 'early_leave') AS early_leave_cnt,
                SUM(status = 'sick') AS sick_cnt,
                COUNT(*) AS total_cnt
            FROM attendance
            WHERE school_id = %s AND student_id = %s
              AND DATE_FORMAT(attendance_date, '%%Y-%%m') = %s
        """, (school_id, student_id, month))
        summary = cursor.fetchone()

        cursor.execute("""
            SELECT attendance_date, status, memo
            FROM attendance
            WHERE school_id = %s AND student_id = %s
            ORDER BY attendance_date DESC LIMIT 10
        """, (school_id, student_id))
        recent = [{'date': r['attendance_date'].strftime('%Y-%m-%d'), 'status': r['status'], 'memo': r['memo'] or ''} for r in cursor.fetchall()]

        return jsonify({
            'success': True,
            'month': month,
            'summary': {
                'present': int(summary['present_cnt'] or 0) if summary else 0,
                'absent': int(summary['absent_cnt'] or 0) if summary else 0,
                'late': int(summary['late_cnt'] or 0) if summary else 0,
                'early_leave': int(summary['early_leave_cnt'] or 0) if summary else 0,
                'sick': int(summary['sick_cnt'] or 0) if summary else 0,
                'total': int(summary['total_cnt'] or 0) if summary else 0
            },
            'recent': recent
        })

    except Exception as e:
        print(f"자녀 출결 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
