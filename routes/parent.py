from flask import Blueprint, render_template, request, jsonify, session, redirect
from functools import wraps
from utils.db import get_db_connection, sanitize_input

parent_bp = Blueprint('parent', __name__)

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
# 학부모 페이지
# ============================================
@parent_bp.route('/parent')
@login_required
def parent_page():
    return redirect('/highschool/fm.html')

# ============================================
# 학부모 정보 조회 API
# ============================================
@parent_bp.route('/api/parent/info', methods=['GET'])
def get_parent_info():
    conn = None
    cursor = None
    try:
        member_id = sanitize_input(request.args.get('member_id'), 50)
        
        if not member_id:
            return jsonify({'success': False, 'message': '로그인 정보가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM fm_all WHERE member_id = %s", (member_id,))
        parent = cursor.fetchone()
        
        if not parent:
            return jsonify({'success': False, 'message': '학부모 정보를 찾을 수 없습니다.'})
        
        school_id = parent.get('school_id') or ''
        member_school = parent.get('member_school') or ''
        
        child = {
            'member_name': parent.get('child_name') or '',
            'class_grade': parent.get('class_grade') or '',
            'class_no': parent.get('class_no') or '',
            'class_num': parent.get('class_num') or ''
        }
        
        school_level = ''
        region = ''
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
        
        point_raw = parent.get('point')
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
            'parent': {
                'id': parent.get('id'),
                'member_id': parent.get('member_id') or '',
                'member_name': parent.get('member_name') or '',
                'member_school': parent.get('member_school') or '',
                'school_id': school_id,
                'child_name': parent.get('child_name') or '',
                'point': point,
                'school_level': school_level,
                'region': region
            },
            'child': child
        })
            
    except Exception as e:
        print(f"학부모 정보 조회 오류: {e}")
        return jsonify({'success': False, 'message': '학부모 정보 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
