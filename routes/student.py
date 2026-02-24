from flask import Blueprint, render_template, request, jsonify, session, redirect
from functools import wraps
from utils.db import get_db_connection, sanitize_input

student_bp = Blueprint('student', __name__)

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
# 학생 페이지
# ============================================
@student_bp.route('/student')
@login_required
def student_page():
    return redirect('/highschool/st.html')

# ============================================
# 학생 정보 조회 API
# ============================================
@student_bp.route('/api/student/info', methods=['GET'])
def get_student_info():
    conn = None
    cursor = None
    try:
        member_id = sanitize_input(request.args.get('member_id'), 50)
        
        if not member_id:
            return jsonify({'success': False, 'message': '세션이 만료되었습니다. 다시 로그인해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM stu_all WHERE member_id = %s", (member_id,))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'success': False, 'message': '학생 정보를 찾을 수 없습니다.'})
        
        school_level = ''
        region = ''
        school_id = student.get('school_id') or ''
        member_school = student.get('member_school') or ''
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
        
        point_raw = student.get('point')
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
            'student': {
                'id': student.get('id'),
                'member_id': student.get('member_id') or '',
                'member_name': student.get('member_name') or '',
                'member_school': student.get('member_school') or '',
                'school_id': school_id,
                'class_grade': student.get('stu_grade') or student.get('class_grade') or '',
                'class_no': student.get('stu_class') or student.get('class_no') or '',
                'class_num': student.get('stu_number') or student.get('class_num') or '',
                'point': point,
                'school_level': school_level,
                'region': region
            }
        })
            
    except Exception as e:
        print(f"학생 정보 조회 오류: {e}")
        return jsonify({'success': False, 'message': '학생 정보 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
