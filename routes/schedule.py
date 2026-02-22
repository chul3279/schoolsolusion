from flask import Blueprint, request, jsonify
from utils.db import get_db_connection, sanitize_input

schedule_bp = Blueprint('schedule', __name__)

# ============================================
# 일정 목록 조회 API
# ============================================
@schedule_bp.route('/api/schedule/list', methods=['GET'])
def get_schedule_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        member_id = sanitize_input(request.args.get('member_id'), 50)
        member_roll = sanitize_input(request.args.get('member_roll'), 20)
        year = sanitize_input(request.args.get('year'), 4)
        month = sanitize_input(request.args.get('month'), 2)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            query = """
                SELECT id, member_id, member_name, read_roll, schedule_date, title, content, created_at
                FROM schedule
                WHERE school_id = %s
                AND (
                    (read_roll = 'self' AND member_id = %s)
                    OR FIND_IN_SET('self', read_roll) > 0 AND member_id = %s
                    OR FIND_IN_SET(%s, read_roll) > 0
                    OR read_roll = 'all'
                )
            """
            params = [school_id, member_id, member_id, member_roll]
        else:
            query = """
                SELECT id, member_id, member_name, read_roll, schedule_date, title, content, created_at
                FROM schedule
                WHERE member_school = %s
                AND (
                    (read_roll = 'self' AND member_id = %s)
                    OR FIND_IN_SET('self', read_roll) > 0 AND member_id = %s
                    OR FIND_IN_SET(%s, read_roll) > 0
                    OR read_roll = 'all'
                )
            """
            params = [member_school, member_id, member_id, member_roll]
        
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
        print(f"일정 조회 오류: {e}")
        return jsonify({'success': False, 'message': '일정 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 일정 등록 API
# ============================================
@schedule_bp.route('/api/schedule/create', methods=['POST'])
def create_schedule():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        member_id = sanitize_input(data.get('member_id'), 50)
        member_name = sanitize_input(data.get('member_name'), 100)
        member_roll = sanitize_input(data.get('member_roll'), 20)
        read_roll = sanitize_input(data.get('read_roll'), 100)
        schedule_date = sanitize_input(data.get('schedule_date'), 20)
        title = sanitize_input(data.get('title'), 200)
        content = sanitize_input(data.get('content'), 2000)
        
        if not all([member_school, member_id, member_name, schedule_date, title]):
            return jsonify({'success': False, 'message': '필수 항목을 모두 입력해주세요.'})
        
        # 교사만 공개 대상 설정 가능, 학생/학부모는 자동으로 self
        if member_roll != 'teacher':
            read_roll = 'self'
        else:
            # 유효한 값만 허용
            allowed = {'self', 'teacher', 'student', 'parent'}
            parts = [p.strip() for p in read_roll.split(',') if p.strip() in allowed]
            read_roll = ','.join(parts) if parts else 'self'
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        query = """
            INSERT INTO schedule (school_id, member_school, member_id, member_name, read_roll, schedule_date, title, content, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (school_id, member_school, member_id, member_name, read_roll, schedule_date, title, content))
        conn.commit()
        
        return jsonify({'success': True, 'message': '일정이 등록되었습니다.'})
        
    except Exception as e:
        print(f"일정 등록 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 등록 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 일정 수정 API
# ============================================
@schedule_bp.route('/api/schedule/update', methods=['POST'])
def update_schedule():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        schedule_id = sanitize_input(data.get('id'), 20)
        member_id = sanitize_input(data.get('member_id'), 50)
        member_roll = sanitize_input(data.get('member_roll'), 20)
        read_roll = sanitize_input(data.get('read_roll'), 100)
        schedule_date = sanitize_input(data.get('schedule_date'), 20)
        title = sanitize_input(data.get('title'), 200)
        content = sanitize_input(data.get('content'), 2000)
        
        if not all([schedule_id, member_id, schedule_date, title]):
            return jsonify({'success': False, 'message': '필수 항목을 모두 입력해주세요.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT member_id FROM schedule WHERE id = %s", (schedule_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': '일정을 찾을 수 없습니다.'})
        
        if result['member_id'] != member_id:
            return jsonify({'success': False, 'message': '본인의 일정만 수정할 수 있습니다.'})
        
        if member_roll != 'teacher':
            read_roll = 'self'
        else:
            allowed = {'self', 'teacher', 'student', 'parent'}
            parts = [p.strip() for p in read_roll.split(',') if p.strip() in allowed]
            read_roll = ','.join(parts) if parts else 'self'
        
        query = """
            UPDATE schedule 
            SET schedule_date = %s, title = %s, content = %s, read_roll = %s
            WHERE id = %s AND member_id = %s
        """
        cursor.execute(query, (schedule_date, title, content, read_roll, schedule_id, member_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': '일정이 수정되었습니다.'})
        
    except Exception as e:
        print(f"일정 수정 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 일정 삭제 API
# ============================================
@schedule_bp.route('/api/schedule/delete', methods=['POST'])
def delete_schedule():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        schedule_id = sanitize_input(data.get('id'), 20)
        member_id = sanitize_input(data.get('member_id'), 50)
        
        if not schedule_id or not member_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT member_id FROM schedule WHERE id = %s", (schedule_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': '일정을 찾을 수 없습니다.'})
        
        if result['member_id'] != member_id:
            return jsonify({'success': False, 'message': '본인의 일정만 삭제할 수 있습니다.'})
        
        cursor.execute("DELETE FROM schedule WHERE id = %s", (schedule_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': '일정이 삭제되었습니다.'})
        
    except Exception as e:
        print(f"일정 삭제 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '일정 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()