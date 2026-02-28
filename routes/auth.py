from flask import Blueprint, render_template, request, jsonify, session, redirect
import re
import json
from utils.db import get_db_connection, sanitize_input, validate_phone, validate_birth, hash_password, verify_password
from utils.email_util import generate_temp_password, send_temp_password_email, mask_email, mask_member_id

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    return render_template('index.html')

@auth_bp.route('/signup')
def signup_page():
    return render_template('signup.html')

import time as _time

_schools_cache = {'data': None, 'ts': 0}

@auth_bp.route('/api/schools', methods=['GET'])
def get_schools():
    # 학교 목록은 거의 바뀌지 않으므로 10분 캐싱
    now = _time.time()
    if _schools_cache['data'] and now - _schools_cache['ts'] < 600:
        return _schools_cache['data']

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT school_id, member_school, region, school_level FROM schoolinfo ORDER BY member_school")
        schools = cursor.fetchall()

        resp = jsonify({'success': True, 'schools': schools})
        _schools_cache['data'] = resp
        _schools_cache['ts'] = now
        return resp

    except Exception as e:
        return jsonify({'success': False, 'message': '학교 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/signup', methods=['POST'])
def signup():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        
        member_name = sanitize_input(data.get('member_name'), 50)
        member_birth = sanitize_input(data.get('member_birth'), 10)
        member_email = sanitize_input(data.get('member_email'), 100)
        member_tel = sanitize_input(data.get('member_tel'), 20)
        member_add = sanitize_input(data.get('member_add'), 200)
        login_id = sanitize_input(data.get('login_id'), 50)
        password = data.get('password')
        
        member_roll = sanitize_input(data.get('member_roll'), 50)
        
        member_school = sanitize_input(data.get('member_school'), 100)
        school_id = sanitize_input(data.get('school_id'), 50)
        
        stu_grade = sanitize_input(data.get('stu_grade'), 10)
        stu_class = sanitize_input(data.get('stu_class'), 10)
        stu_number = sanitize_input(data.get('stu_number'), 10)
        
        children = data.get('children', [])
        
        if not all([member_name, member_birth, member_email, member_tel, member_add, login_id, password, member_roll]):
            return jsonify({'success': False, 'message': '모든 필수 항목을 입력해주세요.'})

        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, member_email):
            return jsonify({'success': False, 'message': '올바른 이메일 형식을 입력해주세요.'})
        
        roles = [r.strip() for r in member_roll.split(',')]
        valid_roles = ['teacher', 'student', 'parent']
        for r in roles:
            if r not in valid_roles:
                return jsonify({'success': False, 'message': '올바른 역할을 선택해주세요.'})
        
        if 'student' in roles and len(roles) > 1:
            return jsonify({'success': False, 'message': '학생은 다른 역할과 동시 선택할 수 없습니다.'})
        
        if set(roles) not in [{'teacher'}, {'student'}, {'parent'}, {'teacher', 'parent'}]:
            return jsonify({'success': False, 'message': '올바른 역할 조합이 아닙니다.'})
        
        if ('teacher' in roles or 'student' in roles) and not member_school:
            return jsonify({'success': False, 'message': '소속 학교를 선택해주세요.'})
        
        if 'teacher' in roles and not member_school:
            return jsonify({'success': False, 'message': '소속 학교를 선택해주세요.'})
        
        if not validate_phone(member_tel):
            return jsonify({'success': False, 'message': '올바른 전화번호 형식을 입력해주세요.'})
        
        if not validate_birth(member_birth):
            return jsonify({'success': False, 'message': '생년월일은 YYYY-MM-DD 형식으로 입력해주세요.'})
        
        if 'student' in roles:
            if not all([stu_grade, stu_class, stu_number]):
                return jsonify({'success': False, 'message': '학급 정보를 모두 입력해주세요.'})
        
        if 'parent' in roles:
            if not children or len(children) == 0:
                return jsonify({'success': False, 'message': '자녀 정보를 1명 이상 입력해주세요.'})
            for i, child in enumerate(children):
                c_name = child.get('child_name', '').strip()
                c_birth = child.get('child_birth', '').strip()
                c_school = child.get('child_school', '').strip()
                c_grade = child.get('stu_grade', '').strip()
                c_class = child.get('stu_class', '').strip()
                c_number = child.get('stu_number', '').strip()
                if not all([c_name, c_birth, c_school, c_grade, c_class, c_number]):
                    return jsonify({'success': False, 'message': f'자녀 {i+1}의 정보를 모두 입력해주세요.'})
                if not validate_birth(c_birth):
                    return jsonify({'success': False, 'message': f'자녀 {i+1}의 생년월일 형식이 올바르지 않습니다.'})
        
        if len(password) < 8:
            return jsonify({'success': False, 'message': '비밀번호는 8자 이상이어야 합니다.'})
        
        if not re.match(r'^[a-zA-Z0-9_]{4,50}$', login_id):
            return jsonify({'success': False, 'message': '아이디는 4~50자의 영문, 숫자, 언더스코어만 사용 가능합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        conn.begin()  # 트랜잭션 시작 — 모든 INSERT를 하나로 묶음

        cursor.execute("SELECT member_id FROM member WHERE member_id = %s", (login_id,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 사용중인 아이디입니다.'})

        cursor.execute("SELECT member_id FROM member WHERE member_email = %s", (member_email,))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 등록된 이메일입니다.'})

        if member_school and not school_id:
            cursor.execute("SELECT school_id FROM schoolinfo WHERE member_school = %s", (member_school,))
            school_info = cursor.fetchone()
            if school_info:
                school_id = school_info.get('school_id')
            else:
                return jsonify({'success': False, 'message': '존재하지 않는 학교입니다.'})
        elif school_id:
            cursor.execute("SELECT school_id FROM schoolinfo WHERE school_id = %s", (school_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'message': '존재하지 않는 학교입니다.'})
        
        if roles == ['parent'] and children:
            first_child = children[0]
            if not member_school:
                member_school = first_child.get('child_school', '')
                school_id = first_child.get('child_school_id', '')
                if member_school and not school_id:
                    cursor.execute("SELECT school_id FROM schoolinfo WHERE member_school = %s", (member_school,))
                    si = cursor.fetchone()
                    if si:
                        school_id = si.get('school_id')
        
        sorted_roles = sorted(roles)
        member_roll_str = ','.join(sorted_roles)
        
        first_child_name = None
        first_child_birth = None
        if 'parent' in roles and children:
            first_child_name = children[0].get('child_name', '')
            first_child_birth = children[0].get('child_birth', '')
        
        hashed_password = password
        
        # member + 역할별 테이블을 단일 트랜잭션으로 처리
        cursor.execute("""
            INSERT INTO member
            (member_id, member_sn, member_name, member_birth, member_email, member_school, school_id,
             member_roll, member_add, member_tel, child_name, child_birth)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            login_id, hashed_password, member_name, member_birth, member_email,
            member_school or '', school_id or '',
            member_roll_str, member_add, member_tel,
            first_child_name, first_child_birth
        ))

        if 'teacher' in roles:
            cursor.execute("SELECT id FROM tea_all WHERE member_id = %s", (login_id,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE tea_all SET member_name = %s, member_school = %s, school_id = %s,
                        member_birth = %s, member_tel = %s
                    WHERE member_id = %s
                """, (member_name, member_school, school_id, member_birth, member_tel, login_id))
            else:
                cursor.execute("""
                    INSERT INTO tea_all (member_id, member_name, member_school, school_id, member_birth, member_tel)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (login_id, member_name, member_school, school_id, member_birth, member_tel))

        if 'student' in roles:
            cursor.execute("SELECT id FROM stu_all WHERE member_id = %s", (login_id,))
            existing = cursor.fetchone()
            if not existing and school_id and stu_grade and stu_class and stu_number:
                cursor.execute("""
                    SELECT id FROM stu_all
                    WHERE school_id = %s AND class_grade = %s AND class_no = %s AND class_num = %s
                      AND (member_id = '' OR member_id IS NULL)
                    LIMIT 1
                """, (school_id, stu_grade, stu_class, stu_number))
                existing = cursor.fetchone()
            if existing:
                cursor.execute("""
                    UPDATE stu_all SET member_id = %s, member_name = %s, member_school = %s, school_id = %s,
                        member_birth = %s, member_tel = %s,
                        class_grade = %s, class_no = %s, class_num = %s
                    WHERE id = %s
                """, (login_id, member_name, member_school, school_id, member_birth, member_tel,
                      stu_grade, stu_class, stu_number, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO stu_all (member_id, member_name, member_school, school_id, member_birth, member_tel,
                        class_grade, class_no, class_num)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (login_id, member_name, member_school, school_id, member_birth, member_tel,
                      stu_grade, stu_class, stu_number))

        if 'parent' in roles:
            cursor.execute("DELETE FROM fm_all WHERE member_id = %s", (login_id,))

            for child in children:
                c_name = child.get('child_name', '').strip()
                c_birth = child.get('child_birth', '').strip()
                c_school = child.get('child_school', '').strip()
                c_school_id = child.get('child_school_id', '').strip()
                c_grade = child.get('stu_grade', '').strip()
                c_class = child.get('stu_class', '').strip()
                c_number = child.get('stu_number', '').strip()

                if c_school and not c_school_id:
                    cursor.execute("SELECT school_id FROM schoolinfo WHERE member_school = %s", (c_school,))
                    si = cursor.fetchone()
                    if si:
                        c_school_id = si.get('school_id')

                cursor.execute("""
                    INSERT INTO fm_all (member_id, member_name, member_school, school_id,
                        member_birth, member_tel, child_name, child_birth,
                        class_grade, class_no, class_num)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (login_id, member_name, c_school, c_school_id,
                      member_birth, member_tel, c_name, c_birth,
                      c_grade, c_class, c_number))

        conn.commit()
        return jsonify({'success': True, 'message': '회원가입이 완료되었습니다.'})
        
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
        import traceback
        print(f"[SIGNUP ERROR] member_id={login_id}, error={e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'회원가입 처리 중 오류가 발생했습니다. ({type(e).__name__})'})
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

# ============================================
# 아이디 찾기 API
# ============================================
@auth_bp.route('/api/find-id', methods=['POST'])
def find_id():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_name = sanitize_input(data.get('member_name'), 50)
        member_email = sanitize_input(data.get('member_email'), 100)
        member_birth = sanitize_input(data.get('member_birth'), 10)

        if not all([member_name, member_email, member_birth]):
            return jsonify({'success': False, 'message': '모든 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT member_id FROM member
            WHERE member_name = %s AND member_email = %s AND member_birth = %s
        """, (member_name, member_email, member_birth))

        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '일치하는 회원 정보가 없습니다.'})

        masked_id = mask_member_id(result['member_id'])
        return jsonify({'success': True, 'masked_id': masked_id, 'message': f'아이디는 {masked_id} 입니다.'})

    except Exception as e:
        print(f"아이디 찾기 오류: {e}")
        return jsonify({'success': False, 'message': '아이디 찾기 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 비밀번호 찾기 API (임시 비밀번호 이메일 발송)
# ============================================
@auth_bp.route('/api/find-password', methods=['POST'])
def find_password():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)
        member_email = sanitize_input(data.get('member_email'), 100)

        if not all([member_id, member_email]):
            return jsonify({'success': False, 'message': '모든 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT member_id, member_name, member_email FROM member
            WHERE member_id = %s AND member_email = %s
        """, (member_id, member_email))

        result = cursor.fetchone()
        if not result:
            return jsonify({'success': False, 'message': '일치하는 회원 정보가 없습니다.'})

        # 기존 비밀번호 백업 (이메일 발송 실패 시 복원용)
        cursor.execute("SELECT member_sn FROM member WHERE member_id = %s", (member_id,))
        old_pw_row = cursor.fetchone()
        old_password = old_pw_row['member_sn'] if old_pw_row else None

        # 임시 비밀번호 생성 및 DB 업데이트
        temp_password = generate_temp_password()
        conn.begin()
        cursor.execute("UPDATE member SET member_sn = %s WHERE member_id = %s", (temp_password, member_id))
        conn.commit()

        # 이메일 발송
        email_sent = send_temp_password_email(
            to_email=result['member_email'],
            member_name=result['member_name'],
            member_id=member_id,
            temp_password=temp_password
        )

        if not email_sent:
            # 이메일 발송 실패 시 비밀번호 복원
            try:
                cursor.execute("UPDATE member SET member_sn = %s WHERE member_id = %s", (old_password, member_id))
                conn.commit()
            except Exception:
                pass
            return jsonify({'success': False, 'message': '이메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.'})

        masked = mask_email(result['member_email'])
        return jsonify({'success': True, 'message': f'{masked}(으)로 임시 비밀번호가 발송되었습니다.'})

    except Exception as e:
        print(f"비밀번호 찾기 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '비밀번호 찾기 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 로그인 처리 API
# ============================================
@auth_bp.route('/login_process', methods=['POST'])
def login_process():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        login_id = sanitize_input(data.get('login_id'), 50)
        password = data.get('password')

        if not login_id or not password:
            return jsonify({'success': False, 'message': '아이디와 비밀번호를 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.member_id, m.member_sn, m.member_name, m.member_roll, m.member_school, m.school_id,
                   s.school_id AS schoolinfo_school_id, s.school_level
            FROM member m
            LEFT JOIN schoolinfo s ON m.member_school = s.member_school
            WHERE m.member_id = %s
        """, (login_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'success': False, 'message': '아이디 또는 비밀번호가 일치하지 않습니다.'})
        
        stored_password = user['member_sn']
        if password != stored_password and not verify_password(password, stored_password):
            return jsonify({'success': False, 'message': '아이디 또는 비밀번호가 일치하지 않습니다.'})
        
        member_roll = user.get('member_roll', '')
        roles = [r.strip() for r in member_roll.split(',') if r.strip()]
        
        school_id = user.get('school_id') or user.get('schoolinfo_school_id') or ''
        school_level = user.get('school_level', 'high')
        level_map = {'mid': 'middleschool', 'high': 'highschool', 'special': 'specialschool', 'etc': 'etc'}
        school_folder = level_map.get(school_level, 'highschool')
        
        session['authenticated_user_id'] = user['member_id']
        session['authenticated_user_name'] = user['member_name']
        
        if len(roles) == 1:
            role = roles[0]
            
            # 학부모: fm_all에서 자녀 정보 조회
            if role == 'parent':
                cursor.execute("""
                    SELECT id, child_name, child_birth, member_school, school_id,
                           class_grade, class_no, class_num
                    FROM fm_all WHERE member_id = %s
                """, (login_id,))
                children_rows = cursor.fetchall()
                
                children_list = []
                for ch in children_rows:
                    cb = ch.get('child_birth')
                    if cb and hasattr(cb, 'strftime'):
                        cb = cb.strftime('%Y-%m-%d')
                    children_list.append({
                        'id': ch.get('id'),
                        'child_name': ch.get('child_name', ''),
                        'child_birth': cb or '',
                        'member_school': ch.get('member_school', ''),
                        'school_id': ch.get('school_id', ''),
                        'class_grade': ch.get('class_grade', ''),
                        'class_no': ch.get('class_no', ''),
                        'class_num': ch.get('class_num', '')
                    })
                
                if len(children_list) > 1:
                    return jsonify({
                        'success': True,
                        'requires_child_select': True,
                        'user': {
                            'member_id': user['member_id'],
                            'member_name': user['member_name'],
                            'member_roll': role
                        },
                        'children': children_list
                    })
                elif len(children_list) == 1:
                    child = children_list[0]
                    c_school_id = child.get('school_id', '')
                    c_school = child.get('member_school', '')

                    c_school_folder = school_folder
                    if c_school:
                        cursor.execute("SELECT school_level FROM schoolinfo WHERE member_school = %s", (c_school,))
                        si = cursor.fetchone()
                        if si:
                            c_school_folder = level_map.get(si.get('school_level', 'high'), 'highschool')

                    # IDOR 방어: 자녀의 학생 member_id 목록 조회
                    children_ids = []
                    for ch in children_list:
                        if ch.get('school_id') and ch.get('class_grade') and ch.get('class_no') and ch.get('class_num'):
                            cursor.execute(
                                "SELECT member_id FROM stu_all WHERE school_id=%s AND class_grade=%s AND class_no=%s AND class_num=%s",
                                (ch['school_id'], ch['class_grade'], ch['class_no'], ch['class_num'])
                            )
                            stu_row = cursor.fetchone()
                            if stu_row:
                                children_ids.append(str(stu_row['member_id']))

                    session['user_id'] = user['member_id']
                    session['user_name'] = user['member_name']
                    session['user_role'] = role
                    session['user_school'] = c_school or user.get('member_school', '')
                    session['school_id'] = c_school_id or school_id
                    session['selected_child_id'] = child.get('id')
                    session['selected_child_name'] = child.get('child_name', '')
                    session['children_ids'] = children_ids
                    session['class_grade'] = child.get('class_grade', '')
                    session['class_no'] = child.get('class_no', '')
                    
                    return jsonify({
                        'success': True,
                        'user': {
                            'member_id': user['member_id'],
                            'member_name': user['member_name'],
                            'member_roll': role,
                            'member_school': c_school or user.get('member_school', ''),
                            'school_id': c_school_id or school_id,
                            'school_folder': c_school_folder
                        }
                    })
                else:
                    session['user_id'] = user['member_id']
                    session['user_name'] = user['member_name']
                    session['user_role'] = role
                    session['user_school'] = user.get('member_school', '')
                    session['school_id'] = school_id
                    session['children_ids'] = []

                    return jsonify({
                        'success': True,
                        'user': {
                            'member_id': user['member_id'],
                            'member_name': user['member_name'],
                            'member_roll': role,
                            'member_school': user.get('member_school', ''),
                            'school_id': school_id,
                            'school_folder': school_folder
                        }
                    })
            
            # 학생: stu_all에서 학급 정보 조회
            elif role == 'student':
                cursor.execute("""
                    SELECT class_grade, class_no, class_num, point
                    FROM stu_all WHERE school_id = %s AND member_id = %s
                """, (school_id, login_id))
                stu_info = cursor.fetchone()
                
                stu_class_grade = ''
                stu_class_no = ''
                stu_class_num = ''
                stu_point = 0
                if stu_info:
                    stu_class_grade = stu_info.get('class_grade') or ''
                    stu_class_no = stu_info.get('class_no') or ''
                    stu_class_num = stu_info.get('class_num') or ''
                    stu_point = stu_info.get('point') or 0
                
                session['user_id'] = user['member_id']
                session['user_name'] = user['member_name']
                session['user_role'] = role
                session['user_school'] = user.get('member_school', '')
                session['school_id'] = school_id
                session['class_grade'] = stu_class_grade
                session['class_no'] = stu_class_no

                return jsonify({
                    'success': True,
                    'user': {
                        'member_id': user['member_id'],
                        'member_name': user['member_name'],
                        'member_roll': role,
                        'member_school': user.get('member_school', ''),
                        'school_id': school_id,
                        'school_folder': school_folder,
                        'class_grade': stu_class_grade,
                        'class_no': stu_class_no,
                        'class_num': stu_class_num,
                        'point': stu_point
                    }
                })
            
            # 교사: tea_all에서 학급 정보 조회 후 세션 설정
            else:
                tea_class_grade = ''
                tea_class_no = ''
                tea_department = ''
                try:
                    cursor.execute("""
                        SELECT class_grade, class_no, department
                        FROM tea_all WHERE member_id = %s AND school_id = %s
                    """, (login_id, school_id))
                    tea_info = cursor.fetchone()
                    if tea_info:
                        tea_class_grade = tea_info.get('class_grade') or ''
                        tea_class_no = tea_info.get('class_no') or ''
                        tea_department = tea_info.get('department') or ''
                except:
                    pass

                session['user_id'] = user['member_id']
                session['user_name'] = user['member_name']
                session['user_role'] = role
                session['user_school'] = user.get('member_school', '')
                session['school_id'] = school_id
                session['class_grade'] = tea_class_grade
                session['class_no'] = tea_class_no
                session['department'] = tea_department

                return jsonify({
                    'success': True,
                    'user': {
                        'member_id': user['member_id'],
                        'member_name': user['member_name'],
                        'member_roll': role,
                        'member_school': user.get('member_school', ''),
                        'school_id': school_id,
                        'school_folder': school_folder,
                        'class_grade': tea_class_grade,
                        'class_no': tea_class_no,
                        'department': tea_department
                    }
                })
        
        # 복수 역할: 역할 선택 화면
        else:
            return jsonify({
                'success': True,
                'requires_role_select': True,
                'user': {
                    'member_id': user['member_id'],
                    'member_name': user['member_name'],
                    'member_roll': member_roll
                },
                'roles': roles
            })

    except Exception as e:
        return jsonify({'success': False, 'message': '로그인 처리 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/select-role', methods=['POST'])
def select_role():
    conn = None
    cursor = None
    try:
        authenticated_user_id = session.get('authenticated_user_id')
        if not authenticated_user_id:
            return jsonify({'success': False, 'message': '인증 정보가 없습니다. 다시 로그인해주세요.'})
        
        data = request.get_json()
        selected_role = sanitize_input(data.get('selected_role'), 20)
        
        if selected_role not in ['teacher', 'parent']:
            return jsonify({'success': False, 'message': '올바른 역할을 선택해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.member_id, m.member_name, m.member_roll, m.member_school, m.school_id,
                   s.school_level
            FROM member m
            LEFT JOIN schoolinfo s ON m.member_school = s.member_school
            WHERE m.member_id = %s
        """, (authenticated_user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'})
        
        user_roles = [r.strip() for r in user.get('member_roll', '').split(',')]
        if selected_role not in user_roles:
            return jsonify({'success': False, 'message': '해당 역할 권한이 없습니다.'})
        
        level_map = {'mid': 'middleschool', 'high': 'highschool', 'special': 'specialschool', 'etc': 'etc'}
        school_level = user.get('school_level', 'high')
        school_folder = level_map.get(school_level, 'highschool')
        school_id = user.get('school_id', '')
        
        if selected_role == 'teacher':
            tea_class_grade = ''
            tea_class_no = ''
            tea_department = ''
            try:
                cursor.execute("""
                    SELECT class_grade, class_no, department
                    FROM tea_all WHERE member_id = %s AND school_id = %s
                """, (authenticated_user_id, school_id))
                tea_info = cursor.fetchone()
                if tea_info:
                    tea_class_grade = tea_info.get('class_grade') or ''
                    tea_class_no = tea_info.get('class_no') or ''
                    tea_department = tea_info.get('department') or ''
            except:
                pass

            session['user_id'] = user['member_id']
            session['user_name'] = user['member_name']
            session['user_role'] = 'teacher'
            session['user_school'] = user.get('member_school', '')
            session['school_id'] = school_id
            session['class_grade'] = tea_class_grade
            session['class_no'] = tea_class_no
            session['department'] = tea_department

            session.pop('authenticated_user_id', None)
            session.pop('authenticated_user_name', None)

            return jsonify({
                'success': True,
                'user': {
                    'member_id': user['member_id'],
                    'member_name': user['member_name'],
                    'member_roll': 'teacher',
                    'member_school': user.get('member_school', ''),
                    'school_id': school_id,
                    'school_folder': school_folder,
                    'class_grade': tea_class_grade,
                    'class_no': tea_class_no,
                    'department': tea_department
                }
            })
        
        if selected_role == 'parent':
            cursor.execute("""
                SELECT id, child_name, child_birth, member_school, school_id,
                       class_grade, class_no, class_num
                FROM fm_all WHERE member_id = %s
            """, (authenticated_user_id,))
            children_rows = cursor.fetchall()
            
            children_list = []
            for ch in children_rows:
                cb = ch.get('child_birth')
                if cb and hasattr(cb, 'strftime'):
                    cb = cb.strftime('%Y-%m-%d')
                children_list.append({
                    'id': ch.get('id'),
                    'child_name': ch.get('child_name', ''),
                    'child_birth': cb or '',
                    'member_school': ch.get('member_school', ''),
                    'school_id': ch.get('school_id', ''),
                    'class_grade': ch.get('class_grade', ''),
                    'class_no': ch.get('class_no', ''),
                    'class_num': ch.get('class_num', '')
                })
            
            if len(children_list) > 1:
                return jsonify({
                    'success': True,
                    'requires_child_select': True,
                    'user': {
                        'member_id': user['member_id'],
                        'member_name': user['member_name'],
                        'member_roll': 'parent'
                    },
                    'children': children_list
                })
            elif len(children_list) == 1:
                child = children_list[0]
                c_school = child.get('member_school', '')
                c_school_id = child.get('school_id', '')
                
                c_school_folder = school_folder
                if c_school:
                    cursor.execute("SELECT school_level FROM schoolinfo WHERE member_school = %s", (c_school,))
                    si = cursor.fetchone()
                    if si:
                        c_school_folder = level_map.get(si.get('school_level', 'high'), 'highschool')
                
                session['user_id'] = user['member_id']
                session['user_name'] = user['member_name']
                session['user_role'] = 'parent'
                session['user_school'] = c_school or user.get('member_school', '')
                session['school_id'] = c_school_id or school_id
                session['selected_child_id'] = child.get('id')
                session['selected_child_name'] = child.get('child_name', '')
                
                session.pop('authenticated_user_id', None)
                session.pop('authenticated_user_name', None)
                
                return jsonify({
                    'success': True,
                    'user': {
                        'member_id': user['member_id'],
                        'member_name': user['member_name'],
                        'member_roll': 'parent',
                        'member_school': c_school or user.get('member_school', ''),
                        'school_id': c_school_id or school_id,
                        'school_folder': c_school_folder
                    }
                })
            else:
                session['user_id'] = user['member_id']
                session['user_name'] = user['member_name']
                session['user_role'] = 'parent'
                session['user_school'] = user.get('member_school', '')
                session['school_id'] = school_id
                
                session.pop('authenticated_user_id', None)
                session.pop('authenticated_user_name', None)
                
                return jsonify({
                    'success': True,
                    'user': {
                        'member_id': user['member_id'],
                        'member_name': user['member_name'],
                        'member_roll': 'parent',
                        'member_school': user.get('member_school', ''),
                        'school_id': school_id,
                        'school_folder': school_folder
                    }
                })
    
    except Exception as e:
        return jsonify({'success': False, 'message': '역할 선택 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/select-child', methods=['POST'])
def select_child():
    conn = None
    cursor = None
    try:
        authenticated_user_id = session.get('authenticated_user_id')
        if not authenticated_user_id:
            return jsonify({'success': False, 'message': '인증 정보가 없습니다. 다시 로그인해주세요.'})
        
        data = request.get_json()
        child_id = data.get('child_id')
        
        if not child_id:
            return jsonify({'success': False, 'message': '자녀를 선택해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT f.id, f.child_name, f.child_birth, f.member_school, f.school_id,
                   f.class_grade, f.class_no, f.class_num,
                   m.member_name
            FROM fm_all f
            JOIN member m ON f.member_id = m.member_id
            WHERE f.id = %s AND f.member_id = %s
        """, (child_id, authenticated_user_id))
        child = cursor.fetchone()
        
        if not child:
            return jsonify({'success': False, 'message': '자녀 정보를 찾을 수 없습니다.'})
        
        c_school = child.get('member_school', '')
        c_school_id = child.get('school_id', '')
        
        level_map = {'mid': 'middleschool', 'high': 'highschool', 'special': 'specialschool', 'etc': 'etc'}
        school_folder = 'highschool'
        if c_school:
            cursor.execute("SELECT school_level FROM schoolinfo WHERE member_school = %s", (c_school,))
            si = cursor.fetchone()
            if si:
                school_folder = level_map.get(si.get('school_level', 'high'), 'highschool')
        
        # IDOR 방어: 모든 자녀의 학생 member_id 목록 조회
        cursor.execute(
            "SELECT school_id, class_grade, class_no, class_num FROM fm_all WHERE member_id = %s",
            (authenticated_user_id,)
        )
        all_children = cursor.fetchall()
        children_ids = []
        for ch in all_children:
            if ch.get('school_id') and ch.get('class_grade') and ch.get('class_no') and ch.get('class_num'):
                cursor.execute(
                    "SELECT member_id FROM stu_all WHERE school_id=%s AND class_grade=%s AND class_no=%s AND class_num=%s",
                    (ch['school_id'], ch['class_grade'], ch['class_no'], ch['class_num'])
                )
                stu_row = cursor.fetchone()
                if stu_row:
                    children_ids.append(str(stu_row['member_id']))

        session['user_id'] = authenticated_user_id
        session['user_name'] = child.get('member_name', '')
        session['user_role'] = 'parent'
        session['user_school'] = c_school
        session['school_id'] = c_school_id
        session['selected_child_id'] = child.get('id')
        session['selected_child_name'] = child.get('child_name', '')
        session['children_ids'] = children_ids
        session['class_grade'] = child.get('class_grade', '')
        session['class_no'] = child.get('class_no', '')

        session.pop('authenticated_user_id', None)
        session.pop('authenticated_user_name', None)
        
        return jsonify({
            'success': True,
            'user': {
                'member_id': authenticated_user_id,
                'member_name': child.get('member_name', ''),
                'member_roll': 'parent',
                'member_school': c_school,
                'school_id': c_school_id,
                'school_folder': school_folder,
                'selected_child_name': child.get('child_name', '')
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': '자녀 선택 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/logout')
def logout():
    session.clear()
    return jsonify({'success': True, 'message': '로그아웃되었습니다.'})

@auth_bp.route('/api/member/verify-password', methods=['POST'])
def verify_member_password():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)
        password = data.get('password')
        
        if not member_id or not password:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        cursor.execute("SELECT member_sn FROM member WHERE member_id = %s", (member_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'})
        
        stored_password = result['member_sn']
        if password == stored_password or verify_password(password, stored_password):
            return jsonify({'success': True, 'message': '비밀번호가 확인되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': '비밀번호 확인 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/member/info', methods=['GET'])
def get_member_info():
    conn = None
    cursor = None
    try:
        member_id = sanitize_input(request.args.get('member_id'), 50)

        if not member_id:
            return jsonify({'success': False, 'message': '회원 ID가 필요합니다.'})

        # [보안] 본인 여부 판별
        session_user_id = session.get('user_id')
        is_self = (member_id == session_user_id)
        requester_role = session.get('user_role', '')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        cursor.execute("""
            SELECT member_id, member_name, member_birth, member_school, school_id,
                   member_roll, member_add, member_tel, child_name, child_birth
            FROM member WHERE member_id = %s
        """, (member_id,))
        member = cursor.fetchone()

        if not member:
            return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'})

        member_birth = member.get('member_birth')
        if member_birth and hasattr(member_birth, 'strftime'):
            member_birth = member_birth.strftime('%Y-%m-%d')

        child_birth = member.get('child_birth')
        if child_birth and hasattr(child_birth, 'strftime'):
            child_birth = child_birth.strftime('%Y-%m-%d')

        member_roll = member.get('member_roll', '')
        roles = [r.strip() for r in member_roll.split(',') if r.strip()]

        # [보안] 본인이면 전체 정보, 타인이면 제한된 정보만 반환
        if is_self:
            response_data = {
                'member_id': member.get('member_id') or '',
                'member_name': member.get('member_name') or '',
                'member_birth': member_birth or '',
                'member_school': member.get('member_school') or '',
                'school_id': member.get('school_id') or '',
                'member_roll': member_roll,
                'roles': roles,
                'member_add': member.get('member_add') or '',
                'member_tel': member.get('member_tel') or '',
                'child_name': member.get('child_name') or '',
                'child_birth': child_birth or ''
            }
        else:
            # 타인 정보: 이름, 학교, 역할만 반환 (주소/전화/생년월일 제외)
            response_data = {
                'member_id': member.get('member_id') or '',
                'member_name': member.get('member_name') or '',
                'member_birth': '',
                'member_school': member.get('member_school') or '',
                'school_id': member.get('school_id') or '',
                'member_roll': member_roll,
                'roles': roles,
                'member_add': '',
                'member_tel': '',
                'child_name': '',
                'child_birth': ''
            }
        
        if 'teacher' in roles:
            cursor.execute("""
                SELECT department, department_position, class_grade, class_no
                FROM tea_all WHERE member_id = %s
            """, (member_id,))
            role_info = cursor.fetchone()
            if role_info:
                response_data['teacher_info'] = {
                    'department': role_info.get('department') or '',
                    'department_position': role_info.get('department_position') or '',
                    'class_grade': role_info.get('class_grade') or '',
                    'class_no': role_info.get('class_no') or ''
                }
                response_data['department'] = role_info.get('department') or ''
                response_data['department_position'] = role_info.get('department_position') or ''
                if 'student' not in roles and 'parent' not in roles:
                    response_data['class_grade'] = role_info.get('class_grade') or ''
                    response_data['class_no'] = role_info.get('class_no') or ''
                
        if 'student' in roles:
            cursor.execute("""
                SELECT class_grade, class_no, class_num
                FROM stu_all WHERE member_id = %s
            """, (member_id,))
            role_info = cursor.fetchone()
            if role_info:
                response_data['class_grade'] = role_info.get('class_grade') or ''
                response_data['class_no'] = role_info.get('class_no') or ''
                response_data['class_num'] = role_info.get('class_num') or ''
                
        if 'parent' in roles:
            cursor.execute("""
                SELECT id, child_name, child_birth, member_school, school_id,
                       class_grade, class_no, class_num
                FROM fm_all WHERE member_id = %s
            """, (member_id,))
            children_rows = cursor.fetchall()
            
            children_list = []
            for ch in children_rows:
                cb = ch.get('child_birth')
                if cb and hasattr(cb, 'strftime'):
                    cb = cb.strftime('%Y-%m-%d')
                children_list.append({
                    'id': ch.get('id'),
                    'child_name': ch.get('child_name', ''),
                    'child_birth': cb or '',
                    'member_school': ch.get('member_school', ''),
                    'school_id': ch.get('school_id', ''),
                    'class_grade': ch.get('class_grade', ''),
                    'class_no': ch.get('class_no', ''),
                    'class_num': ch.get('class_num', '')
                })
            response_data['children'] = children_list
            
            if children_list:
                first = children_list[0]
                response_data['child_name'] = first.get('child_name', '')
                response_data['child_birth'] = first.get('child_birth', '')
                if 'student' not in roles:
                    response_data['class_grade'] = first.get('class_grade', '')
                    response_data['class_no'] = first.get('class_no', '')
                    response_data['class_num'] = first.get('class_num', '')
        
        return jsonify({
            'success': True,
            'member': response_data
        })
            
    except Exception as e:
        return jsonify({'success': False, 'message': '회원정보 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/member/update', methods=['POST'])
def update_member_info():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        
        member_id = sanitize_input(data.get('member_id'), 50)
        member_name = sanitize_input(data.get('member_name'), 50)
        member_birth = sanitize_input(data.get('member_birth'), 10)
        member_tel = sanitize_input(data.get('member_tel'), 20)
        member_add = sanitize_input(data.get('member_add'), 200)
        
        member_school = sanitize_input(data.get('member_school'), 100)
        school_id = sanitize_input(data.get('school_id'), 50)
        
        child_name = sanitize_input(data.get('child_name'), 50)
        child_birth = sanitize_input(data.get('child_birth'), 10)
        
        department = sanitize_input(data.get('department'), 50)
        department_position = sanitize_input(data.get('department_position'), 50)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        class_num = sanitize_input(data.get('class_num'), 10)
        
        if not member_id:
            return jsonify({'success': False, 'message': '회원 ID가 필요합니다.'})

        if not member_name:
            return jsonify({'success': False, 'message': '이름은 필수 항목입니다.'})

        if member_tel and not validate_phone(member_tel):
            return jsonify({'success': False, 'message': '올바른 전화번호 형식을 입력해주세요.'})

        if member_birth and not validate_birth(member_birth):
            return jsonify({'success': False, 'message': '생년월일은 YYYY-MM-DD 형식으로 입력해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT member_roll, school_id FROM member WHERE member_id = %s", (member_id,))
        existing = cursor.fetchone()
        
        if not existing:
            return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'})
        
        member_roll = existing.get('member_roll', '')
        roles = [r.strip() for r in member_roll.split(',') if r.strip()]
        
        if member_school and not school_id:
            cursor.execute("SELECT school_id FROM schoolinfo WHERE member_school = %s", (member_school,))
            school_info = cursor.fetchone()
            if school_info:
                school_id = school_info.get('school_id')
            else:
                return jsonify({'success': False, 'message': '존재하지 않는 학교입니다.'})
        
        if 'parent' in roles and child_birth and not validate_birth(child_birth):
            return jsonify({'success': False, 'message': '자녀 생년월일은 YYYY-MM-DD 형식으로 입력해주세요.'})
        
        if 'parent' in roles:
            cursor.execute("""
                UPDATE member 
                SET member_name = %s, member_birth = %s, member_tel = %s, member_add = %s,
                    member_school = %s, school_id = %s, child_name = %s, child_birth = %s, 
                    updated_at = NOW()
                WHERE member_id = %s
            """, (member_name, member_birth, member_tel, member_add, 
                  member_school, school_id, child_name, child_birth, member_id))
        else:
            cursor.execute("""
                UPDATE member 
                SET member_name = %s, member_birth = %s, member_tel = %s, member_add = %s,
                    member_school = %s, school_id = %s, updated_at = NOW()
                WHERE member_id = %s
            """, (member_name, member_birth, member_tel, member_add, 
                  member_school, school_id, member_id))
        
        if 'teacher' in roles:
            cursor.execute("""
                UPDATE tea_all 
                SET member_name = %s, member_birth = %s, member_tel = %s,
                    member_school = %s, school_id = %s,
                    department = %s, department_position = %s, 
                    class_grade = %s, class_no = %s
                WHERE member_id = %s
            """, (member_name, member_birth, member_tel, 
                  member_school, school_id,
                  department, department_position, 
                  class_grade, class_no, member_id))
                  
        if 'student' in roles:
            cursor.execute("""
                UPDATE stu_all 
                SET member_name = %s, member_birth = %s, member_tel = %s,
                    member_school = %s, school_id = %s,
                    class_grade = %s, class_no = %s, class_num = %s
                WHERE member_id = %s
            """, (member_name, member_birth, member_tel,
                  member_school, school_id,
                  class_grade, class_no, class_num, member_id))
                  
        if 'parent' in roles:
            cursor.execute("""
                UPDATE fm_all 
                SET member_name = %s, member_birth = %s, member_tel = %s,
                    member_school = %s, school_id = %s,
                    child_name = %s, child_birth = %s,
                    class_grade = %s, class_no = %s, class_num = %s
                WHERE member_id = %s
            """, (member_name, member_birth, member_tel,
                  member_school, school_id,
                  child_name, child_birth,
                  class_grade, class_no, class_num, member_id))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': '회원정보가 수정되었습니다.'})
        
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '회원정보 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@auth_bp.route('/api/teacher/update-class-info', methods=['POST'])
def update_teacher_class_info():
    """교사 담임/부서 정보만 업데이트하는 전용 API"""
    # [보안] 교사만 호출 가능
    if session.get('user_role') != 'teacher':
        return jsonify({'success': False, 'message': '교사만 수정할 수 있습니다.'}), 403

    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)

        if not member_id:
            return jsonify({'success': False, 'message': '회원 ID가 필요합니다.'})

        # [보안] 본인 정보만 수정 가능
        if member_id != session.get('user_id'):
            return jsonify({'success': False, 'message': '본인 정보만 수정할 수 있습니다.'}), 403

        department = sanitize_input(data.get('department'), 50) or ''
        department_position = sanitize_input(data.get('department_position'), 50) or ''
        class_grade = sanitize_input(data.get('class_grade'), 10) or ''
        class_no = sanitize_input(data.get('class_no'), 10) or ''

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        # tea_all에 해당 교사가 있는지 확인
        cursor.execute("SELECT id FROM tea_all WHERE member_id = %s", (member_id,))
        existing = cursor.fetchone()

        if not existing:
            return jsonify({'success': False, 'message': '교사 정보를 찾을 수 없습니다.'})

        cursor.execute("""
            UPDATE tea_all
            SET department = %s, department_position = %s,
                class_grade = %s, class_no = %s
            WHERE member_id = %s
        """, (department, department_position, class_grade, class_no, member_id))

        conn.commit()
        return jsonify({'success': True, 'message': '저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@auth_bp.route('/api/member/change-password', methods=['POST'])
def change_member_password():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or session.get('member_id')
        if not member_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not all([current_password, new_password]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})
        
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': '비밀번호는 8자 이상이어야 합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT member_sn FROM member WHERE member_id = %s", (member_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': '회원 정보를 찾을 수 없습니다.'})
        
        stored_password = result['member_sn']
        if current_password != stored_password and not verify_password(current_password, stored_password):
            return jsonify({'success': False, 'message': '현재 비밀번호가 일치하지 않습니다.'})
        
        cursor.execute("UPDATE member SET member_sn = %s, updated_at = NOW() WHERE member_id = %s", (new_password, member_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': '비밀번호가 변경되었습니다.'})
        
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '비밀번호 변경 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()