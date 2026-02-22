from flask import Blueprint, request, jsonify
from utils.db import get_db_connection, sanitize_input

meal_bp = Blueprint('meal', __name__)

# ============================================
# 급식 정보 조회 API (오늘)
# ============================================
@meal_bp.route('/api/meal/today', methods=['GET'])
def get_today_meal():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        month = sanitize_input(request.args.get('month'), 2)
        day = sanitize_input(request.args.get('day'), 2)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not month or not day:
            return jsonify({'success': False, 'message': '날짜 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            query = "SELECT id, school_id, member_school, month, day, menu FROM school_meal WHERE school_id = %s AND month = %s AND day = %s"
            cursor.execute(query, (school_id, month, day))
        else:
            query = "SELECT id, school_id, member_school, month, day, menu FROM school_meal WHERE member_school = %s AND month = %s AND day = %s"
            cursor.execute(query, (member_school, month, day))
        
        meal = cursor.fetchone()
        
        if meal:
            return jsonify({'success': True, 'meal': {
                'id': meal['id'],
                'school_id': meal.get('school_id'),
                'member_school': meal.get('member_school'),
                'month': meal.get('month'),
                'day': meal.get('day'),
                'menu': meal.get('menu')
            }})
        else:
            return jsonify({'success': False, 'message': '급식 정보가 없습니다.'})
            
    except Exception as e:
        print(f"급식 정보 조회 오류: {e}")
        return jsonify({'success': False, 'message': '급식 정보 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 급식 월간 목록 조회 API
# ============================================
@meal_bp.route('/api/meal/month', methods=['GET'])
def get_month_meals():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        year = sanitize_input(request.args.get('year'), 4)
        month = sanitize_input(request.args.get('month'), 2)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not year or not month:
            return jsonify({'success': False, 'message': '년월 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            query = "SELECT id, day, menu FROM school_meal WHERE school_id = %s AND month = %s ORDER BY day"
            cursor.execute(query, (school_id, month))
        else:
            query = "SELECT id, day, menu FROM school_meal WHERE member_school = %s AND month = %s ORDER BY day"
            cursor.execute(query, (member_school, month))
        
        meals = cursor.fetchall()
        
        meal_dict = {}
        for m in meals:
            meal_dict[str(m['day'])] = {
                'id': m['id'],
                'menu': m['menu'] or ''
            }
        
        return jsonify({'success': True, 'meals': meal_dict, 'year': year, 'month': month})
        
    except Exception as e:
        print(f"급식 월간 조회 오류: {e}")
        return jsonify({'success': False, 'message': '급식 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 급식 월간 저장 API
# ============================================
@meal_bp.route('/api/meal/save', methods=['POST'])
def save_month_meals():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        year = sanitize_input(data.get('year'), 4)
        month = sanitize_input(data.get('month'), 2)
        meals = data.get('meals', {})
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not year or not month:
            return jsonify({'success': False, 'message': '년월 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            cursor.execute("DELETE FROM school_meal WHERE school_id = %s AND month = %s", (school_id, month))
        else:
            cursor.execute("DELETE FROM school_meal WHERE member_school = %s AND month = %s", (member_school, month))
        
        insert_count = 0
        for day, menu in meals.items():
            if menu and menu.strip():
                query = """
                    INSERT INTO school_meal (school_id, member_school, month, day, menu)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (school_id, member_school, month, int(day), menu.strip()))
                insert_count += 1
        
        conn.commit()
        
        return jsonify({'success': True, 'message': f'{month}월 급식 {insert_count}일분이 저장되었습니다.'})
        
    except Exception as e:
        print(f"급식 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '급식 저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
