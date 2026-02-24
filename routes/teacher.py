from flask import Blueprint, render_template, request, jsonify, session, redirect
from functools import wraps
from utils.db import get_db_connection, sanitize_input

teacher_bp = Blueprint('teacher', __name__)

# ============================================
# 세션 체크 데코레이터
# ============================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# 교사 페이지
# ============================================
@teacher_bp.route('/teacher')
@login_required
def teacher_page():
    return redirect('/highschool/tea.html')

# ============================================
# 교사 정보 조회 API
# ============================================
@teacher_bp.route('/api/teacher/info', methods=['GET'])
def get_teacher_info():
    conn = None
    cursor = None
    try:
        member_id = sanitize_input(request.args.get('member_id'), 50)

        # 세션 fallback: query param 없으면 세션에서 user_id 사용
        if not member_id:
            member_id = session.get('user_id')
        if not member_id:
            return jsonify({'success': False, 'message': '세션이 만료되었습니다. 다시 로그인해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tea_all WHERE member_id = %s", (member_id,))
        teacher = cursor.fetchone()
        
        if not teacher:
            return jsonify({'success': False, 'message': '교사 정보를 찾을 수 없습니다.'})
        
        school_level = ''
        region = ''
        school_id = teacher.get('school_id') or ''
        member_school = teacher.get('member_school') or ''
        try:
            cursor.execute("SELECT school_id, school_level, region FROM schoolinfo WHERE member_school = %s", (member_school,))
            school_info = cursor.fetchone()
            if school_info:
                school_level = school_info.get('school_level') or ''
                region = school_info.get('region') or ''
                if not school_id:
                    school_id = school_info.get('school_id') or ''
        except:
            pass
        
        point_raw = teacher.get('point')
        if point_raw is None or point_raw == '':
            point = 0
        elif str(point_raw).strip().lower() == 'free':
            point = 'free'
        else:
            try:
                point = int(str(point_raw).replace(',', ''))
            except:
                point = 0
        
        return jsonify({
            'success': True,
            'teacher': {
                'id': teacher.get('id'),
                'member_id': teacher.get('member_id') or '',
                'member_name': teacher.get('member_name') or '',
                'member_school': teacher.get('member_school') or '',
                'school_id': school_id,
                'class_grade': teacher.get('class_grade') or '',
                'class_no': teacher.get('class_no') or '',
                'department': teacher.get('department') or '',
                'point': point,
                'school_level': school_level,
                'region': region
            }
        })
            
    except Exception as e:
        print(f"교사 정보 조회 오류: {e}")
        return jsonify({'success': False, 'message': '교사 정보 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 포인트 충전 API (교사)
# ============================================
@teacher_bp.route('/api/teacher/charge-point', methods=['POST'])
def charge_teacher_point():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        amount = data.get('amount', 0)

        # IDOR 방어: 세션 사용자 ID 사용
        member_id = session.get('user_id')
        if not member_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        try:
            amount = int(amount)
            if amount <= 0 or amount > 10000000:
                raise ValueError("Invalid amount")
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': '충전 금액이 올바르지 않습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        conn.begin()  # 트랜잭션 시작 (autocommit 환경에서 롤백 보장)

        cursor.execute("SELECT point FROM tea_all WHERE member_id = %s", (member_id,))
        result = cursor.fetchone()

        if not result:
            conn.rollback()
            return jsonify({'success': False, 'message': '교사 정보를 찾을 수 없습니다.'})

        current_point_raw = result.get('point')
        str_point = str(current_point_raw).strip() if current_point_raw is not None else ""

        # Free 사용자 보호: 충전 시 free 상태 유지
        if str_point.lower() == 'free':
            conn.rollback()
            return jsonify({'success': True, 'message': 'Free 사용자는 충전이 불필요합니다.', 'new_point': 'free'})

        if not str_point:
            current_point = 0
        else:
            try:
                current_point = int(str_point.replace(',', ''))
            except (ValueError, TypeError):
                current_point = 0

        new_point = current_point + amount

        cursor.execute("UPDATE tea_all SET point = %s WHERE member_id = %s", (new_point, member_id))

        # 포인트 이력 기록
        try:
            cursor.execute("""
                INSERT INTO point_history (member_id, point_change, point_type, description, created_at)
                VALUES (%s, %s, 'charge', '포인트 충전', NOW())
            """, (member_id, amount))
        except Exception as hist_err:
            print(f"충전 이력 기록 오류 (무시): {hist_err}")

        conn.commit()

        return jsonify({'success': True, 'message': f'{amount:,}P가 충전되었습니다.', 'new_point': new_point})

    except Exception as e:
        print(f"포인트 충전 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '포인트 충전 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 같은 학교 교사 목록 조회 API
# ============================================
@teacher_bp.route('/api/teachers/list', methods=['GET'])
def get_teachers_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            cursor.execute("""
                SELECT id, member_id, member_name, member_school, member_birth,
                       department, department_position, class_grade, class_no
                FROM tea_all
                WHERE school_id = %s
                ORDER BY member_name
            """, (school_id,))
        else:
            cursor.execute("""
                SELECT id, member_id, member_name, member_school, member_birth,
                       department, department_position, class_grade, class_no
                FROM tea_all
                WHERE member_school = %s
                ORDER BY member_name
            """, (member_school,))
        
        teachers = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'data': teachers,
            'count': len(teachers)
        })
        
    except Exception as e:
        print(f"교사 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'교사 목록 조회 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 교사 일괄 수정 API
# ============================================
@teacher_bp.route('/api/teachers/update-batch', methods=['POST'])
def update_teachers_batch():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        teachers_list = data.get('teachers', [])

        if not teachers_list:
            return jsonify({'success': False, 'message': '수정할 교사 정보가 없습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        updated = 0

        for t in teachers_list:
            member_id = sanitize_input(t.get('member_id'), 50)
            if not member_id:
                continue

            fields = []
            values = []

            if 'member_name' in t:
                fields.append('member_name = %s')
                values.append(sanitize_input(t['member_name'], 100))
            if 'department' in t:
                fields.append('department = %s')
                values.append(sanitize_input(t['department'], 100))
            if 'department_position' in t:
                fields.append('department_position = %s')
                values.append(sanitize_input(t['department_position'], 50))
            if 'class_grade' in t:
                fields.append('class_grade = %s')
                values.append(sanitize_input(str(t['class_grade']), 10) if t['class_grade'] else None)
            if 'class_no' in t:
                fields.append('class_no = %s')
                values.append(sanitize_input(str(t['class_no']), 50) if t['class_no'] else None)

            if fields:
                values.append(member_id)
                query = f"UPDATE tea_all SET {', '.join(fields)} WHERE member_id = %s"
                cursor.execute(query, values)
                updated += cursor.rowcount

        conn.commit()
        return jsonify({'success': True, 'message': f'{updated}명의 교사 정보가 수정되었습니다.', 'updated': updated})

    except Exception as e:
        print(f"교사 일괄 수정 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'교사 정보 수정 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 같은 학교 교사 목록 API (시간표 작성용)
# ============================================
@teacher_bp.route('/api/teachers/by-school', methods=['GET'])
def get_teachers_by_school():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            cursor.execute("""
                SELECT id, member_id, member_name, member_school, member_birth,
                       department, department_position, class_grade, class_no, point
                FROM tea_all
                WHERE school_id = %s
                ORDER BY member_name
            """, (school_id,))
        else:
            cursor.execute("""
                SELECT id, member_id, member_name, member_school, member_birth,
                       department, department_position, class_grade, class_no, point
                FROM tea_all
                WHERE member_school = %s
                ORDER BY member_name
            """, (member_school,))
        
        teachers = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'teachers': teachers,
            'count': len(teachers)
        })
        
    except Exception as e:
        print(f"학교 교사 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'교사 목록 조회 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
