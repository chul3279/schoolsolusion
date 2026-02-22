from flask import Blueprint, request, jsonify, session, send_file
from utils.db import get_db_connection, sanitize_input
from datetime import datetime, date, timedelta
import paramiko
import io

academy_bp = Blueprint('academy', __name__)


# ============================================
# 원장: 내 학원 목록 조회
# ============================================
@academy_bp.route('/api/academy/my-academies', methods=['GET'])
def get_my_academies():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        if user_role == 'director':
            cursor.execute("""
                SELECT academy_id, academy_name, address, tel, status, created_at
                FROM academy_info
                WHERE director_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
        elif user_role == 'instructor':
            cursor.execute("""
                SELECT ai.academy_id, ai.academy_name, ai.address, ai.tel, ai.status, ai.created_at,
                       ainst.status AS instructor_status
                FROM academy_instructor ainst
                JOIN academy_info ai ON ainst.academy_id = ai.academy_id
                WHERE ainst.member_id = %s
                ORDER BY ai.created_at DESC
            """, (user_id,))
        else:
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        academies = cursor.fetchall()
        for a in academies:
            if a.get('created_at') and hasattr(a['created_at'], 'strftime'):
                a['created_at'] = a['created_at'].strftime('%Y-%m-%d')
            aid = a['academy_id']
            cursor.execute("SELECT COUNT(*) as cnt FROM academy_instructor WHERE academy_id = %s AND status = 'approved'", (aid,))
            a['instructor_count'] = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM academy_class WHERE academy_id = %s", (aid,))
            a['class_count'] = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM academy_enrollment WHERE academy_id = %s AND status = 'active'", (aid,))
            a['student_count'] = cursor.fetchone()['cnt']

        return jsonify({'success': True, 'academies': academies})

    except Exception as e:
        print(f"학원 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '학원 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 학원 추가 생성
# ============================================
@academy_bp.route('/api/academy/create', methods=['POST'])
def create_academy():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '원장만 학원을 개설할 수 있습니다.'}), 403

        data = request.get_json()
        academy_name = sanitize_input(data.get('academy_name'), 100)
        address = sanitize_input(data.get('address'), 200)
        tel = sanitize_input(data.get('tel'), 20)

        if not academy_name:
            return jsonify({'success': False, 'message': '학원명을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO academy_info (academy_name, director_id, address, tel)
            VALUES (%s, %s, %s, %s)
        """, (academy_name, user_id, address or '', tel or ''))
        conn.commit()

        return jsonify({'success': True, 'message': '학원이 개설되었습니다.', 'academy_id': cursor.lastrowid})

    except Exception as e:
        if conn: conn.rollback()
        print(f"학원 개설 오류: {e}")
        return jsonify({'success': False, 'message': '학원 개설 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 학원 정보 수정
# ============================================
@academy_bp.route('/api/academy/update', methods=['POST'])
def update_academy():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        academy_name = sanitize_input(data.get('academy_name'), 100)
        address = sanitize_input(data.get('address'), 200)
        tel = sanitize_input(data.get('tel'), 20)

        if not academy_id or not academy_name:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 학원인지 확인
        cursor.execute("SELECT academy_id FROM academy_info WHERE academy_id = %s AND director_id = %s", (academy_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '본인의 학원만 수정할 수 있습니다.'}), 403

        cursor.execute("""
            UPDATE academy_info SET academy_name = %s, address = %s, tel = %s
            WHERE academy_id = %s AND director_id = %s
        """, (academy_name, address or '', tel or '', academy_id, user_id))
        conn.commit()

        return jsonify({'success': True, 'message': '학원 정보가 수정되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '학원 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 강사 가입 신청 목록 조회
# ============================================
@academy_bp.route('/api/academy/instructors', methods=['GET'])
def get_instructors():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 학원 확인
        cursor.execute("SELECT academy_id FROM academy_info WHERE academy_id = %s AND director_id = %s", (academy_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        cursor.execute("""
            SELECT ainst.id, ainst.member_id, ainst.status, ainst.created_at,
                   m.member_name, m.member_tel, m.member_email
            FROM academy_instructor ainst
            JOIN member m ON ainst.member_id = m.member_id
            WHERE ainst.academy_id = %s
            ORDER BY FIELD(ainst.status, 'pending', 'approved', 'rejected'), ainst.created_at DESC
        """, (academy_id,))
        instructors = cursor.fetchall()

        for inst in instructors:
            if inst.get('created_at') and hasattr(inst['created_at'], 'strftime'):
                inst['created_at'] = inst['created_at'].strftime('%Y-%m-%d')

        return jsonify({'success': True, 'instructors': instructors})

    except Exception as e:
        print(f"강사 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '강사 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 강사 승인/거절
# ============================================
@academy_bp.route('/api/academy/instructor/approve', methods=['POST'])
def approve_instructor():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        instructor_record_id = data.get('id')
        action = data.get('action')  # 'approved' or 'rejected'

        if action not in ('approved', 'rejected'):
            return jsonify({'success': False, 'message': '올바른 작업을 선택해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 학원의 강사인지 확인
        cursor.execute("""
            SELECT ainst.id FROM academy_instructor ainst
            JOIN academy_info ai ON ainst.academy_id = ai.academy_id
            WHERE ainst.id = %s AND ai.director_id = %s
        """, (instructor_record_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        cursor.execute("UPDATE academy_instructor SET status = %s WHERE id = %s", (action, instructor_record_id))
        conn.commit()

        msg = '강사가 승인되었습니다.' if action == 'approved' else '강사 신청이 거절되었습니다.'
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '처리 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 반(강좌) 관리 - 목록 조회
# ============================================
@academy_bp.route('/api/academy/classes', methods=['GET'])
def get_academy_classes():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        cursor.execute("""
            SELECT ac.id, ac.class_name, ac.subject, ac.instructor_id, ac.schedule,
                   ac.start_date, ac.end_date, ac.auto_delete_at, ac.created_at,
                   m.member_name AS instructor_name
            FROM academy_class ac
            LEFT JOIN member m ON ac.instructor_id = m.member_id
            WHERE ac.academy_id = %s
            ORDER BY ac.class_name
        """, (academy_id,))
        classes = cursor.fetchall()

        today = date.today()
        for c in classes:
            if c.get('created_at') and hasattr(c['created_at'], 'strftime'):
                c['created_at'] = c['created_at'].strftime('%Y-%m-%d')
            for df in ('start_date', 'end_date', 'auto_delete_at'):
                if c.get(df) and hasattr(c[df], 'strftime'):
                    c[df] = c[df].strftime('%Y-%m-%d')

            # 수강 상태 계산
            sd = c.get('start_date')
            ed = c.get('end_date')
            if sd and ed:
                sd_d = datetime.strptime(sd, '%Y-%m-%d').date() if isinstance(sd, str) else sd
                ed_d = datetime.strptime(ed, '%Y-%m-%d').date() if isinstance(ed, str) else ed
                if today < sd_d:
                    c['period_status'] = 'upcoming'
                elif today <= ed_d:
                    c['period_status'] = 'active'
                else:
                    ad = c.get('auto_delete_at')
                    if ad:
                        ad_d = datetime.strptime(ad, '%Y-%m-%d').date() if isinstance(ad, str) else ad
                        days_left = (ad_d - today).days
                        c['period_status'] = 'expiring'
                        c['days_until_delete'] = max(0, days_left)
                    else:
                        c['period_status'] = 'ended'
            else:
                c['period_status'] = 'no_period'

            # 수강생 수
            cursor.execute("SELECT COUNT(*) as cnt FROM academy_enrollment WHERE class_id = %s AND status = 'active'", (c['id'],))
            cnt = cursor.fetchone()
            c['student_count'] = cnt['cnt'] if cnt else 0

        return jsonify({'success': True, 'classes': classes})

    except Exception as e:
        print(f"반 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '반 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 반(강좌) 생성
# ============================================
@academy_bp.route('/api/academy/class/create', methods=['POST'])
def create_academy_class():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        class_name = sanitize_input(data.get('class_name'), 100)
        subject = sanitize_input(data.get('subject'), 50)
        instructor_id = sanitize_input(data.get('instructor_id'), 50)
        schedule = sanitize_input(data.get('schedule'), 200)
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not academy_id or not class_name:
            return jsonify({'success': False, 'message': '학원과 반 이름은 필수입니다.'})

        # 수강기간 검증
        auto_delete_at = None
        if start_date and end_date:
            try:
                sd = datetime.strptime(start_date, '%Y-%m-%d').date()
                ed = datetime.strptime(end_date, '%Y-%m-%d').date()
                if sd > ed:
                    return jsonify({'success': False, 'message': '시작일이 종료일보다 늦을 수 없습니다.'})
                auto_delete_at = (ed + timedelta(days=7)).strftime('%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'message': '날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 학원 확인
        cursor.execute("SELECT academy_id FROM academy_info WHERE academy_id = %s AND director_id = %s", (academy_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        cursor.execute("""
            INSERT INTO academy_class (academy_id, class_name, subject, instructor_id, schedule, start_date, end_date, auto_delete_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (academy_id, class_name, subject or '', instructor_id or None, schedule or '',
              start_date or None, end_date or None, auto_delete_at))
        conn.commit()

        return jsonify({'success': True, 'message': '반이 생성되었습니다.', 'class_id': cursor.lastrowid})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '반 생성 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장: 반(강좌) 삭제
# ============================================
@academy_bp.route('/api/academy/class/delete', methods=['POST'])
def delete_academy_class():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        class_id = data.get('class_id')

        if not class_id:
            return jsonify({'success': False, 'message': '반 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 학원의 반인지 확인
        cursor.execute("""
            SELECT ac.id FROM academy_class ac
            JOIN academy_info ai ON ac.academy_id = ai.academy_id
            WHERE ac.id = %s AND ai.director_id = %s
        """, (class_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        cursor.execute("DELETE FROM academy_class WHERE id = %s", (class_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '반이 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '반 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 원장/강사: 수강생 목록 조회
# ============================================
@academy_bp.route('/api/academy/students', methods=['GET'])
def get_academy_students():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        academy_id = request.args.get('academy_id')
        class_id = request.args.get('class_id')

        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        query = """
            SELECT ae.id, ae.member_id, ae.class_id, ae.status, ae.enrolled_at,
                   m.member_name, m.member_tel,
                   ac.class_name
            FROM academy_enrollment ae
            JOIN member m ON ae.member_id = m.member_id
            LEFT JOIN academy_class ac ON ae.class_id = ac.id
            WHERE ae.academy_id = %s
        """
        params = [academy_id]

        if class_id:
            query += " AND ae.class_id = %s"
            params.append(class_id)

        query += " ORDER BY m.member_name"
        cursor.execute(query, params)
        students = cursor.fetchall()

        for s in students:
            if s.get('enrolled_at') and hasattr(s['enrolled_at'], 'strftime'):
                s['enrolled_at'] = s['enrolled_at'].strftime('%Y-%m-%d')

        return jsonify({'success': True, 'students': students})

    except Exception as e:
        print(f"수강생 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '수강생 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 반(강좌) 수정
# ============================================
@academy_bp.route('/api/academy/class/update', methods=['POST'])
def update_academy_class():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id or session.get('user_role') != 'director':
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        class_id = data.get('class_id')
        class_name = sanitize_input(data.get('class_name'), 100)
        subject = sanitize_input(data.get('subject'), 50)
        instructor_id = sanitize_input(data.get('instructor_id'), 50)
        schedule = sanitize_input(data.get('schedule'), 200)
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if not class_id or not class_name:
            return jsonify({'success': False, 'message': '반 ID와 이름은 필수입니다.'})

        auto_delete_at = None
        if start_date and end_date:
            try:
                sd = datetime.strptime(start_date, '%Y-%m-%d').date()
                ed = datetime.strptime(end_date, '%Y-%m-%d').date()
                if sd > ed:
                    return jsonify({'success': False, 'message': '시작일이 종료일보다 늦을 수 없습니다.'})
                auto_delete_at = (ed + timedelta(days=7)).strftime('%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'message': '날짜 형식이 올바르지 않습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        cursor.execute("""
            SELECT ac.id FROM academy_class ac
            JOIN academy_info ai ON ac.academy_id = ai.academy_id
            WHERE ac.id = %s AND ai.director_id = %s
        """, (class_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        cursor.execute("""
            UPDATE academy_class
            SET class_name = %s, subject = %s, instructor_id = %s, schedule = %s,
                start_date = %s, end_date = %s, auto_delete_at = %s
            WHERE id = %s
        """, (class_name, subject or '', instructor_id or None, schedule or '',
              start_date or None, end_date or None, auto_delete_at, class_id))
        conn.commit()

        return jsonify({'success': True, 'message': '반 정보가 수정되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"반 수정 오류: {e}")
        return jsonify({'success': False, 'message': '반 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 검색 (수강생 등록용)
# ============================================
@academy_bp.route('/api/academy/search-students', methods=['GET'])
def search_students():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        query = request.args.get('query', '').strip()
        if not query or len(query) < 2:
            return jsonify({'success': False, 'message': '검색어는 2자 이상 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        search_term = f'%{query}%'
        cursor.execute("""
            SELECT m.member_id, m.member_name, m.member_tel, m.member_school
            FROM member m
            WHERE m.member_roll = 'student'
              AND (m.member_name LIKE %s OR m.member_id LIKE %s)
            LIMIT 20
        """, (search_term, search_term))
        students = cursor.fetchall()

        return jsonify({'success': True, 'students': students})

    except Exception as e:
        print(f"학생 검색 오류: {e}")
        return jsonify({'success': False, 'message': '학생 검색 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원에 학생 등록
# ============================================
@academy_bp.route('/api/academy/student/register', methods=['POST'])
def register_student():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        member_ids = data.get('member_ids', [])
        class_id = data.get('class_id')

        if not academy_id or not member_ids:
            return jsonify({'success': False, 'message': '학원 ID와 학생 목록이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 학원 권한 확인
        if user_role == 'director':
            cursor.execute("SELECT academy_id FROM academy_info WHERE academy_id = %s AND director_id = %s", (academy_id, user_id))
        else:
            cursor.execute("SELECT id FROM academy_instructor WHERE academy_id = %s AND member_id = %s AND status = 'approved'", (academy_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        registered = 0
        for mid in member_ids:
            mid = str(mid).strip()
            if not mid:
                continue
            # 중복 확인
            cursor.execute("""
                SELECT id FROM academy_enrollment
                WHERE member_id = %s AND academy_id = %s AND status = 'active'
                  AND (class_id = %s OR class_id IS NULL)
            """, (mid, academy_id, class_id or None))
            if cursor.fetchone():
                continue
            cursor.execute("""
                INSERT INTO academy_enrollment (member_id, academy_id, class_id, status)
                VALUES (%s, %s, %s, 'active')
            """, (mid, academy_id, class_id or None))
            registered += 1

        conn.commit()
        return jsonify({'success': True, 'message': f'{registered}명이 등록되었습니다.', 'registered': registered})

    except Exception as e:
        if conn: conn.rollback()
        print(f"학생 등록 오류: {e}")
        return jsonify({'success': False, 'message': '학생 등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수강생 반 배정
# ============================================
@academy_bp.route('/api/academy/student/enroll', methods=['POST'])
def enroll_student_to_class():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        enrollment_id = data.get('enrollment_id')
        class_id = data.get('class_id')

        if not enrollment_id:
            return jsonify({'success': False, 'message': '등록 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("UPDATE academy_enrollment SET class_id = %s WHERE id = %s", (class_id or None, enrollment_id))
        conn.commit()

        return jsonify({'success': True, 'message': '반이 배정되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '반 배정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수강생 제거
# ============================================
@academy_bp.route('/api/academy/student/unenroll', methods=['POST'])
def unenroll_student():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        enrollment_id = data.get('enrollment_id')

        if not enrollment_id:
            return jsonify({'success': False, 'message': '등록 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("UPDATE academy_enrollment SET status = 'inactive' WHERE id = %s", (enrollment_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '수강생이 제거되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '처리 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 공지사항 - 목록
# ============================================
@academy_bp.route('/api/academy/notice/list', methods=['GET'])
def get_academy_notices():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, academy_id, author_id, author_name, title,
                   LEFT(message, 100) AS message_preview, created_at, updated_at
            FROM academy_notice
            WHERE academy_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (academy_id,))
        notices = cursor.fetchall()

        for n in notices:
            for df in ('created_at', 'updated_at'):
                if n.get(df) and hasattr(n[df], 'strftime'):
                    n[df] = n[df].strftime('%Y-%m-%d %H:%M')

        return jsonify({'success': True, 'notices': notices})

    except Exception as e:
        print(f"공지 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '공지 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 공지사항 - 상세
# ============================================
@academy_bp.route('/api/academy/notice/detail', methods=['GET'])
def get_academy_notice_detail():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        notice_id = request.args.get('id')
        if not notice_id:
            return jsonify({'success': False, 'message': '공지 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM academy_notice WHERE id = %s", (notice_id,))
        notice = cursor.fetchone()
        if not notice:
            return jsonify({'success': False, 'message': '공지를 찾을 수 없습니다.'})

        for df in ('created_at', 'updated_at'):
            if notice.get(df) and hasattr(notice[df], 'strftime'):
                notice[df] = notice[df].strftime('%Y-%m-%d %H:%M')

        return jsonify({'success': True, 'notice': notice})

    except Exception as e:
        print(f"공지 상세 조회 오류: {e}")
        return jsonify({'success': False, 'message': '공지 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 공지사항 - 작성
# ============================================
@academy_bp.route('/api/academy/notice/create', methods=['POST'])
def create_academy_notice():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        title = sanitize_input(data.get('title'), 200)
        message = data.get('message', '').strip()
        correct_no = sanitize_input(data.get('correct_no'), 20)

        if not academy_id or not title or not message or not correct_no:
            return jsonify({'success': False, 'message': '학원, 제목, 내용, 수정비밀번호는 필수입니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 작성자 이름 조회
        cursor.execute("SELECT member_name FROM member WHERE member_id = %s", (user_id,))
        member = cursor.fetchone()
        author_name = member['member_name'] if member else user_id

        cursor.execute("""
            INSERT INTO academy_notice (academy_id, author_id, author_name, title, message, correct_no)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (academy_id, user_id, author_name, title, message, correct_no))
        conn.commit()

        return jsonify({'success': True, 'message': '공지가 등록되었습니다.', 'notice_id': cursor.lastrowid})

    except Exception as e:
        if conn: conn.rollback()
        print(f"공지 작성 오류: {e}")
        return jsonify({'success': False, 'message': '공지 작성 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 공지사항 - 수정
# ============================================
@academy_bp.route('/api/academy/notice/update', methods=['POST'])
def update_academy_notice():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        notice_id = data.get('id')
        title = sanitize_input(data.get('title'), 200)
        message = data.get('message', '').strip()
        correct_no = sanitize_input(data.get('correct_no'), 20)

        if not notice_id or not title or not message or not correct_no:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        cursor.execute("SELECT correct_no FROM academy_notice WHERE id = %s", (notice_id,))
        notice = cursor.fetchone()
        if not notice:
            return jsonify({'success': False, 'message': '공지를 찾을 수 없습니다.'})
        if notice['correct_no'] != correct_no:
            return jsonify({'success': False, 'message': '수정 비밀번호가 일치하지 않습니다.'})

        cursor.execute("""
            UPDATE academy_notice SET title = %s, message = %s, updated_at = NOW()
            WHERE id = %s
        """, (title, message, notice_id))
        conn.commit()

        return jsonify({'success': True, 'message': '공지가 수정되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '공지 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 공지사항 - 삭제
# ============================================
@academy_bp.route('/api/academy/notice/delete', methods=['POST'])
def delete_academy_notice():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        notice_id = data.get('id')
        correct_no = sanitize_input(data.get('correct_no'), 20)

        if not notice_id or not correct_no:
            return jsonify({'success': False, 'message': '공지 ID와 비밀번호가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        cursor.execute("SELECT correct_no FROM academy_notice WHERE id = %s", (notice_id,))
        notice = cursor.fetchone()
        if not notice:
            return jsonify({'success': False, 'message': '공지를 찾을 수 없습니다.'})
        if notice['correct_no'] != correct_no:
            return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'})

        cursor.execute("DELETE FROM academy_notice WHERE id = %s", (notice_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '공지가 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '공지 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생/학부모용 - 내 학원 공지 조회
# ============================================
@academy_bp.route('/api/academy/my-notices', methods=['GET'])
def get_my_academy_notices():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        if user_role == 'parent':
            # 학부모: 자녀의 학원 공지 조회
            cursor.execute("""
                SELECT DISTINCT an.id, an.academy_id, an.title, an.author_name, an.created_at,
                       ai.academy_name
                FROM academy_notice an
                JOIN academy_info ai ON an.academy_id = ai.academy_id
                WHERE an.academy_id IN (
                    SELECT DISTINCT ae.academy_id FROM academy_enrollment ae
                    JOIN fm_all f ON ae.member_id = CONCAT(f.child_name, '_child')
                    WHERE f.member_id = %s AND ae.status = 'active'
                    UNION
                    SELECT DISTINCT ae.academy_id FROM academy_enrollment ae
                    JOIN stu_all s ON ae.member_id = s.member_id
                    JOIN fm_all f ON s.member_name = f.child_name
                    WHERE f.member_id = %s AND ae.status = 'active'
                )
                ORDER BY an.created_at DESC LIMIT 20
            """, (user_id, user_id))
        else:
            # 학생: 본인 소속 학원 공지
            cursor.execute("""
                SELECT DISTINCT an.id, an.academy_id, an.title, an.author_name, an.created_at,
                       ai.academy_name
                FROM academy_notice an
                JOIN academy_info ai ON an.academy_id = ai.academy_id
                WHERE an.academy_id IN (
                    SELECT DISTINCT academy_id FROM academy_enrollment
                    WHERE member_id = %s AND status = 'active'
                )
                ORDER BY an.created_at DESC LIMIT 20
            """, (user_id,))

        notices = cursor.fetchall()
        for n in notices:
            if n.get('created_at') and hasattr(n['created_at'], 'strftime'):
                n['created_at'] = n['created_at'].strftime('%Y-%m-%d %H:%M')

        return jsonify({'success': True, 'notices': notices})

    except Exception as e:
        print(f"내 학원 공지 조회 오류: {e}")
        return jsonify({'success': False, 'message': '공지 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 포인트 잔액 조회
# ============================================
@academy_bp.route('/api/academy/point/balance', methods=['GET'])
def get_academy_point_balance():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT point FROM academy_info WHERE academy_id = %s", (academy_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '학원 정보를 찾을 수 없습니다.'})

        return jsonify({'success': True, 'point': row['point'] or 0})

    except Exception as e:
        print(f"포인트 조회 오류: {e}")
        return jsonify({'success': False, 'message': '포인트 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 포인트 차감
# ============================================
@academy_bp.route('/api/academy/point/deduct', methods=['POST'])
def deduct_academy_point():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        amount = data.get('amount', 0)
        reason = sanitize_input(data.get('reason'), 100)

        try:
            amount = int(amount)
        except:
            return jsonify({'success': False, 'message': '유효하지 않은 금액입니다.'})

        if amount <= 0:
            return jsonify({'success': False, 'message': '차감 금액은 0보다 커야 합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        conn.begin()

        cursor.execute("SELECT point FROM academy_info WHERE academy_id = %s FOR UPDATE", (academy_id,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            return jsonify({'success': False, 'message': '학원 정보를 찾을 수 없습니다.'})

        current_point = row['point'] or 0
        if current_point < amount:
            conn.rollback()
            return jsonify({'success': False, 'message': f'포인트가 부족합니다. (현재: {current_point:,}P, 필요: {amount:,}P)'})

        new_point = current_point - amount
        cursor.execute("UPDATE academy_info SET point = %s WHERE academy_id = %s", (new_point, academy_id))

        try:
            cursor.execute("""
                INSERT INTO point_history (member_id, academy_id, point_change, point_type, description, created_at)
                VALUES (%s, %s, %s, 'deduct', %s, NOW())
            """, (user_id, academy_id, -amount, reason or '학원 포인트 차감'))
        except Exception as hist_err:
            print(f"포인트 이력 기록 오류 (무시): {hist_err}")

        conn.commit()
        return jsonify({'success': True, 'message': f'{amount:,}P가 차감되었습니다.', 'new_point': new_point})

    except Exception as e:
        print(f"포인트 차감 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '포인트 차감 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 생기부 공유 요청 (강사 → 학생)
# ============================================
@academy_bp.route('/api/academy/record/request', methods=['POST'])
def request_record_share():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        record_id = data.get('record_id')
        academy_id = data.get('academy_id')
        student_id = data.get('student_id')

        if record_id is None or academy_id is None or not student_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        record_id = int(record_id)
        academy_id = int(academy_id)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 학생이 이 학원에 등록되어 있는지 확인
        cursor.execute("""
            SELECT id FROM academy_enrollment
            WHERE member_id = %s AND academy_id = %s AND status = 'active'
        """, (student_id, academy_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '해당 학생은 이 학원에 등록되어 있지 않습니다.'})

        # 이미 요청 존재 확인
        cursor.execute("""
            SELECT id, share_status FROM academy_record_share
            WHERE record_id = %s AND academy_id = %s
        """, (record_id, academy_id))
        existing = cursor.fetchone()
        if existing:
            if existing['share_status'] == 'approved':
                return jsonify({'success': False, 'message': '이미 공유가 승인되었습니다.'})
            elif existing['share_status'] == 'requested':
                return jsonify({'success': False, 'message': '이미 공유 요청이 대기 중입니다.'})
            else:
                cursor.execute("""
                    UPDATE academy_record_share SET share_status = 'requested', requested_by = %s, requested_at = NOW()
                    WHERE id = %s
                """, (user_id, existing['id']))
                conn.commit()
                return jsonify({'success': True, 'message': '공유 요청이 재전송되었습니다.'})

        cursor.execute("""
            INSERT INTO academy_record_share (record_id, academy_id, student_id, requested_by, share_status)
            VALUES (%s, %s, %s, %s, 'requested')
        """, (record_id, academy_id, student_id, user_id))
        conn.commit()

        return jsonify({'success': True, 'message': '공유 요청이 전송되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"공유 요청 오류: {e}")
        return jsonify({'success': False, 'message': '공유 요청 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 생기부 공유 대기 목록 (학생용)
# ============================================
@academy_bp.route('/api/academy/record/pending', methods=['GET'])
def get_pending_record_shares():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT ars.id, ars.record_id, ars.academy_id, ars.share_status,
                   ars.requested_by, ars.requested_at,
                   ai.academy_name,
                   asr.file_name,
                   m.member_name AS requester_name
            FROM academy_record_share ars
            JOIN academy_info ai ON ars.academy_id = ai.academy_id
            JOIN admission_student_record asr ON ars.record_id = asr.id
            LEFT JOIN member m ON ars.requested_by = m.member_id
            WHERE ars.student_id = %s AND ars.share_status = 'requested'
            ORDER BY ars.requested_at DESC
        """, (user_id,))
        pending = cursor.fetchall()

        for p in pending:
            if p.get('requested_at') and hasattr(p['requested_at'], 'strftime'):
                p['requested_at'] = p['requested_at'].strftime('%Y-%m-%d %H:%M')

        return jsonify({'success': True, 'pending': pending})

    except Exception as e:
        print(f"대기 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 생기부 공유 승인/거절 (학생)
# ============================================
@academy_bp.route('/api/academy/record/approve', methods=['POST'])
def approve_record_share():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        data = request.get_json()
        share_id = data.get('share_id')
        action = data.get('action')  # 'approved' or 'rejected'

        if action not in ('approved', 'rejected'):
            return jsonify({'success': False, 'message': '올바른 작업을 선택해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 본인 생기부인지 확인
        cursor.execute("SELECT id FROM academy_record_share WHERE id = %s AND student_id = %s", (share_id, user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        if action == 'approved':
            cursor.execute("UPDATE academy_record_share SET share_status = 'approved', approved_at = NOW() WHERE id = %s", (share_id,))
        else:
            cursor.execute("UPDATE academy_record_share SET share_status = 'rejected' WHERE id = %s", (share_id,))
        conn.commit()

        msg = '공유가 승인되었습니다.' if action == 'approved' else '공유 요청이 거절되었습니다.'
        return jsonify({'success': True, 'message': msg})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '처리 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 공유된 생기부 목록 (강사/원장용)
# ============================================
@academy_bp.route('/api/academy/record/shared', methods=['GET'])
def get_shared_records():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT asr.id AS record_id, asr.file_name, asr.file_size, asr.upload_date,
                   ars.student_id, ars.share_status, ars.approved_at,
                   m.member_name AS student_name
            FROM academy_record_share ars
            JOIN admission_student_record asr ON ars.record_id = asr.id
            JOIN member m ON ars.student_id = m.member_id
            WHERE ars.academy_id = %s AND ars.share_status = 'approved'
            ORDER BY ars.approved_at DESC
        """, (academy_id,))
        records = cursor.fetchall()

        for r in records:
            for df in ('upload_date', 'approved_at'):
                if r.get(df) and hasattr(r[df], 'strftime'):
                    r[df] = r[df].strftime('%Y-%m-%d')

        return jsonify({'success': True, 'records': records})

    except Exception as e:
        print(f"공유 생기부 목록 오류: {e}")
        return jsonify({'success': False, 'message': '조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 공유된 생기부 다운로드
# ============================================
@academy_bp.route('/api/academy/record/download/<int:record_id>', methods=['GET'])
def download_shared_record(record_id):
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        academy_id = request.args.get('academy_id')
        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # 승인된 공유 확인
        cursor.execute("""
            SELECT asr.file_path, asr.file_name
            FROM academy_record_share ars
            JOIN admission_student_record asr ON ars.record_id = asr.id
            WHERE ars.record_id = %s AND ars.academy_id = %s AND ars.share_status = 'approved'
        """, (record_id, academy_id))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '접근 권한이 없거나 파일을 찾을 수 없습니다.'}), 403

        # SFTP 다운로드
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('10.10.0.4', port=22, username='school_user', password='3279')
        sftp = ssh.open_sftp()

        file_data = io.BytesIO()
        sftp.getfo(row['file_path'], file_data)
        file_data.seek(0)

        sftp.close()
        ssh.close()

        return send_file(
            file_data,
            as_attachment=True,
            download_name=row['file_name'],
            mimetype='application/octet-stream'
        )

    except Exception as e:
        print(f"생기부 다운로드 오류: {e}")
        return jsonify({'success': False, 'message': '파일 다운로드 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 일정 목록 조회
# ============================================
@academy_bp.route('/api/academy/schedule/list', methods=['GET'])
def get_academy_schedule_list():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        academy_id = request.args.get('academy_id')
        year = request.args.get('year')
        month = request.args.get('month')

        if not academy_id:
            return jsonify({'success': False, 'message': '학원 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        query = """
            SELECT id, member_id, member_name, read_roll, schedule_date, title, content, created_at
            FROM academy_schedule
            WHERE academy_id = %s
            AND (
                (read_roll = 'self' AND member_id = %s)
                OR FIND_IN_SET('self', read_roll) > 0 AND member_id = %s
                OR FIND_IN_SET(%s, read_roll) > 0
                OR read_roll = 'all'
            )
        """
        params = [academy_id, user_id, user_id, user_role]

        if year and month:
            query += " AND YEAR(schedule_date) = %s AND MONTH(schedule_date) = %s"
            params.extend([year, month])

        query += " ORDER BY schedule_date ASC"
        cursor.execute(query, params)
        schedules = cursor.fetchall()

        schedule_list = []
        for s in schedules:
            schedule_list.append({
                'id': s['id'],
                'member_id': s['member_id'],
                'member_name': s['member_name'],
                'read_roll': s['read_roll'],
                'schedule_date': s['schedule_date'].strftime('%Y-%m-%d %H:%M') if s['schedule_date'] else '',
                'date_only': s['schedule_date'].strftime('%Y-%m-%d') if s['schedule_date'] else '',
                'day': s['schedule_date'].day if s['schedule_date'] else 0,
                'title': s['title'],
                'content': s['content'] or '',
                'created_at': s['created_at'].strftime('%Y-%m-%d %H:%M') if s['created_at'] else ''
            })

        return jsonify({'success': True, 'schedules': schedule_list})

    except Exception as e:
        print(f"학원 일정 조회 오류: {e}")
        return jsonify({'success': False, 'message': '일정 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 일정 등록
# ============================================
@academy_bp.route('/api/academy/schedule/create', methods=['POST'])
def create_academy_schedule():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        academy_id = data.get('academy_id')
        member_name = data.get('member_name', '')
        read_roll = data.get('read_roll', 'self')
        schedule_date = data.get('schedule_date')
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()

        if not all([academy_id, schedule_date, title]):
            return jsonify({'success': False, 'message': '필수 항목을 모두 입력해주세요.'})

        # 원장: 모든 read_roll 가능, 강사: self/instructor만
        if user_role == 'director':
            allowed = {'self', 'director', 'instructor', 'student', 'parent'}
        else:
            allowed = {'self', 'instructor'}
        parts = [p.strip() for p in read_roll.split(',') if p.strip() in allowed]
        read_roll = ','.join(parts) if parts else 'self'

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO academy_schedule (academy_id, member_id, member_name, read_roll, schedule_date, title, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (academy_id, user_id, member_name, read_roll, schedule_date, title, content))
        conn.commit()

        return jsonify({'success': True, 'message': '일정이 등록되었습니다.'})

    except Exception as e:
        print(f"학원 일정 등록 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 일정 수정
# ============================================
@academy_bp.route('/api/academy/schedule/update', methods=['POST'])
def update_academy_schedule():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role not in ('director', 'instructor'):
            return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

        data = request.get_json()
        schedule_id = data.get('id')
        read_roll = data.get('read_roll', 'self')
        schedule_date = data.get('schedule_date')
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()

        if not all([schedule_id, schedule_date, title]):
            return jsonify({'success': False, 'message': '필수 항목을 모두 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT member_id FROM academy_schedule WHERE id = %s", (schedule_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '일정을 찾을 수 없습니다.'})
        if row['member_id'] != user_id:
            return jsonify({'success': False, 'message': '본인의 일정만 수정할 수 있습니다.'})

        if user_role == 'director':
            allowed = {'self', 'director', 'instructor', 'student', 'parent'}
        else:
            allowed = {'self', 'instructor'}
        parts = [p.strip() for p in read_roll.split(',') if p.strip() in allowed]
        read_roll = ','.join(parts) if parts else 'self'

        cursor.execute("""
            UPDATE academy_schedule SET schedule_date = %s, title = %s, content = %s, read_roll = %s
            WHERE id = %s AND member_id = %s
        """, (schedule_date, title, content, read_roll, schedule_id, user_id))
        conn.commit()

        return jsonify({'success': True, 'message': '일정이 수정되었습니다.'})

    except Exception as e:
        print(f"학원 일정 수정 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학원 일정 삭제
# ============================================
@academy_bp.route('/api/academy/schedule/delete', methods=['POST'])
def delete_academy_schedule():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

        data = request.get_json()
        schedule_id = data.get('id')

        if not schedule_id:
            return jsonify({'success': False, 'message': '일정 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT member_id FROM academy_schedule WHERE id = %s", (schedule_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '일정을 찾을 수 없습니다.'})
        if row['member_id'] != user_id:
            return jsonify({'success': False, 'message': '본인의 일정만 삭제할 수 있습니다.'})

        cursor.execute("DELETE FROM academy_schedule WHERE id = %s", (schedule_id,))
        conn.commit()

        return jsonify({'success': True, 'message': '일정이 삭제되었습니다.'})

    except Exception as e:
        print(f"학원 일정 삭제 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
