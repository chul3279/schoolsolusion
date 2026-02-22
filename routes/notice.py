from flask import Blueprint, request, jsonify
from utils.db import get_db_connection, sanitize_input

notice_bp = Blueprint('notice', __name__)

# ============================================
# ê³µì§€ì‚¬í•­ ëª©ë¡ ì¡°íšŒ API
# ============================================
@notice_bp.route('/api/notice/list', methods=['GET'])
def get_notice_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': 'í•™êµ ì •ë³´ê°€ ì—†ìŠµë‹ˆë‹¤.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        keyword = sanitize_input(request.args.get('keyword'), 100)
        keyword_filter = ""
        keyword_params = []
        if keyword:
            keyword_filter = " AND (title LIKE %s OR message LIKE %s)"
            keyword_params = [f'%{keyword}%', f'%{keyword}%']

        if school_id:
            query = """
                SELECT id, member_name, title, message, created_at
                FROM notice
                WHERE school_id = %s""" + keyword_filter + """
                ORDER BY created_at DESC
                LIMIT 50
            """
            cursor.execute(query, [school_id] + keyword_params)
        else:
            query = """
                SELECT id, member_name, title, message, created_at
                FROM notice
                WHERE member_school = %s""" + keyword_filter + """
                ORDER BY created_at DESC
                LIMIT 50
            """
            cursor.execute(query, [member_school] + keyword_params)
        
        notices = cursor.fetchall()
        
        notice_list = []
        total = len(notices)
        for idx, n in enumerate(notices):
            notice_list.append({
                'id': n['id'],
                'row_num': total - idx,
                'member_name': n['member_name'],
                'title': n['title'],
                'message': n['message'],
                'created_at': n['created_at'].strftime('%Y-%m-%d %H:%M') if n['created_at'] else ''
            })
        
        return jsonify({'success': True, 'notices': notice_list})
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ì¡°íšŒ ì˜¤ë¥˜: {e}")
        return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ ì¡°íšŒ ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# ê³µì§€ì‚¬í•­ ìƒì„¸ ì¡°íšŒ API
# ============================================
@notice_bp.route('/api/notice/detail', methods=['GET'])
def get_notice_detail():
    conn = None
    cursor = None
    try:
        notice_id = sanitize_input(request.args.get('id'), 20)
        
        if not notice_id:
            return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ IDê°€ í•„ìš”í•©ë‹ˆë‹¤.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, member_name, school_id, member_school, title, message, created_at
            FROM notice WHERE id = %s
        """, (notice_id,))
        notice = cursor.fetchone()
        
        if not notice:
            return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ì„ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤.'})
        
        return jsonify({
            'success': True,
            'notice': {
                'id': notice['id'],
                'member_name': notice['member_name'],
                'school_id': notice['school_id'],
                'member_school': notice['member_school'],
                'title': notice['title'],
                'message': notice['message'],
                'created_at': notice['created_at'].strftime('%Y-%m-%d %H:%M') if notice['created_at'] else ''
            }
        })
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ìƒì„¸ ì¡°íšŒ ì˜¤ë¥˜: {e}")
        return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ ì¡°íšŒ ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# ê³µì§€ì‚¬í•­ ë“±ë¡ API
# ============================================
@notice_bp.route('/api/notice/create', methods=['POST'])
def create_notice():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_name = sanitize_input(data.get('member_name'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        school_id = sanitize_input(data.get('school_id'), 50)
        title = sanitize_input(data.get('title'), 200)
        message = sanitize_input(data.get('message'), 5000)
        correct_no = sanitize_input(data.get('correct_no'), 20)
        
        if not all([member_name, member_school, title, message]):
            return jsonify({'success': False, 'message': 'í•„ìˆ˜ í•­ëª©ì„ ëª¨ë‘ ìž…ë ¥í•´ì£¼ì„¸ìš”.'})
        
        if not correct_no or len(correct_no) < 4:
            return jsonify({'success': False, 'message': 'ìˆ˜ì •/ì‚­ì œìš© ë¹„ë°€ë²ˆí˜¸ë¥¼ 4ìžë¦¬ ì´ìƒ ìž…ë ¥í•´ì£¼ì„¸ìš”.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        query = """
            INSERT INTO notice (member_name, school_id, member_school, title, message, correct_no, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (member_name, school_id, member_school, title, message, correct_no))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'ê³µì§€ì‚¬í•­ì´ ë“±ë¡ë˜ì—ˆìŠµë‹ˆë‹¤.'})
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ë“±ë¡ ì˜¤ë¥˜: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ ë“±ë¡ ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# ê³µì§€ì‚¬í•­ ë¹„ë°€ë²ˆí˜¸ í™•ì¸ API
# ============================================
@notice_bp.route('/api/notice/verify', methods=['POST'])
def verify_notice_password():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        notice_id = sanitize_input(data.get('id'), 20)
        correct_no = sanitize_input(data.get('correct_no'), 20)
        
        if not notice_id or not correct_no:
            return jsonify({'success': False, 'message': 'í•„ìˆ˜ ì •ë³´ê°€ ëˆ„ë½ë˜ì—ˆìŠµë‹ˆë‹¤.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT correct_no FROM notice WHERE id = %s", (notice_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ì„ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤.'})
        
        if result['correct_no'] == correct_no:
            return jsonify({'success': True, 'message': 'ë¹„ë°€ë²ˆí˜¸ê°€ í™•ì¸ë˜ì—ˆìŠµë‹ˆë‹¤.'})
        else:
            return jsonify({'success': False, 'message': 'ë¹„ë°€ë²ˆí˜¸ê°€ ì¼ì¹˜í•˜ì§€ ì•ŠìŠµë‹ˆë‹¤.'})
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ë¹„ë°€ë²ˆí˜¸ í™•ì¸ ì˜¤ë¥˜: {e}")
        return jsonify({'success': False, 'message': 'ë¹„ë°€ë²ˆí˜¸ í™•ì¸ ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# ê³µì§€ì‚¬í•­ ìˆ˜ì • API
# ============================================
@notice_bp.route('/api/notice/update', methods=['POST'])
def update_notice():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        notice_id = sanitize_input(data.get('id'), 20)
        title = sanitize_input(data.get('title'), 200)
        message = sanitize_input(data.get('message'), 5000)
        correct_no = sanitize_input(data.get('correct_no'), 20)
        
        if not all([notice_id, title, message, correct_no]):
            return jsonify({'success': False, 'message': 'í•„ìˆ˜ í•­ëª©ì„ ëª¨ë‘ ìž…ë ¥í•´ì£¼ì„¸ìš”.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT correct_no FROM notice WHERE id = %s", (notice_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ì„ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤.'})
        
        if result['correct_no'] != correct_no:
            return jsonify({'success': False, 'message': 'ë¹„ë°€ë²ˆí˜¸ê°€ ì¼ì¹˜í•˜ì§€ ì•ŠìŠµë‹ˆë‹¤.'})
        
        cursor.execute("""
            UPDATE notice SET title = %s, message = %s WHERE id = %s
        """, (title, message, notice_id))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'ê³µì§€ì‚¬í•­ì´ ìˆ˜ì •ë˜ì—ˆìŠµë‹ˆë‹¤.'})
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ìˆ˜ì • ì˜¤ë¥˜: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ ìˆ˜ì • ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# ê³µì§€ì‚¬í•­ ì‚­ì œ API
# ============================================
@notice_bp.route('/api/notice/delete', methods=['POST'])
def delete_notice():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        notice_id = sanitize_input(data.get('id'), 20)
        correct_no = sanitize_input(data.get('correct_no'), 20)
        
        if not notice_id or not correct_no:
            return jsonify({'success': False, 'message': 'í•„ìˆ˜ ì •ë³´ê°€ ëˆ„ë½ë˜ì—ˆìŠµë‹ˆë‹¤.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'ë°ì´í„°ë² ì´ìŠ¤ ì—°ê²° ì˜¤ë¥˜'})
        
        cursor = conn.cursor()
        
        cursor.execute("SELECT correct_no FROM notice WHERE id = %s", (notice_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ì„ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤.'})
        
        if result['correct_no'] != correct_no:
            return jsonify({'success': False, 'message': 'ë¹„ë°€ë²ˆí˜¸ê°€ ì¼ì¹˜í•˜ì§€ ì•ŠìŠµë‹ˆë‹¤.'})
        
        cursor.execute("DELETE FROM notice WHERE id = %s", (notice_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'ê³µì§€ì‚¬í•­ì´ ì‚­ì œë˜ì—ˆìŠµë‹ˆë‹¤.'})
        
    except Exception as e:
        print(f"ê³µì§€ì‚¬í•­ ì‚­ì œ ì˜¤ë¥˜: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': 'ê³µì§€ì‚¬í•­ ì‚­ì œ ì¤‘ ì˜¤ë¥˜ê°€ ë°œìƒí–ˆìŠµë‹ˆë‹¤.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 새 알림 체크 API (폴링용 경량 조회)
# ============================================
@notice_bp.route('/api/notifications/check', methods=['GET'])
def check_new_notifications():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        member_id = sanitize_input(request.args.get('member_id'), 50)
        member_roll = sanitize_input(request.args.get('member_roll'), 20)
        since = sanitize_input(request.args.get('since'), 30)

        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 없습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        new_notices = []
        new_schedules = []

        if since:
            if school_id:
                cursor.execute("""
                    SELECT id, title, member_name, created_at
                    FROM notice
                    WHERE school_id = %s AND created_at > %s
                    ORDER BY created_at DESC LIMIT 10
                """, (school_id, since))
            else:
                cursor.execute("""
                    SELECT id, title, member_name, created_at
                    FROM notice
                    WHERE member_school = %s AND created_at > %s
                    ORDER BY created_at DESC LIMIT 10
                """, (member_school, since))

            for n in cursor.fetchall():
                new_notices.append({
                    'id': n['id'],
                    'title': n['title'],
                    'member_name': n['member_name'],
                    'created_at': n['created_at'].strftime('%Y-%m-%d %H:%M') if n['created_at'] else ''
                })

        if since and member_id:
            if school_id:
                cursor.execute("""
                    SELECT id, title, member_name, created_at
                    FROM schedule
                    WHERE school_id = %s AND created_at > %s
                    AND (
                        (read_roll = 'self' AND member_id = %s)
                        OR FIND_IN_SET(%s, read_roll) > 0
                        OR read_roll = 'all'
                    )
                    ORDER BY created_at DESC LIMIT 10
                """, (school_id, since, member_id, member_roll))
            else:
                cursor.execute("""
                    SELECT id, title, member_name, created_at
                    FROM schedule
                    WHERE member_school = %s AND created_at > %s
                    AND (
                        (read_roll = 'self' AND member_id = %s)
                        OR FIND_IN_SET(%s, read_roll) > 0
                        OR read_roll = 'all'
                    )
                    ORDER BY created_at DESC LIMIT 10
                """, (member_school, since, member_id, member_roll))

            for s in cursor.fetchall():
                new_schedules.append({
                    'id': s['id'],
                    'title': s['title'],
                    'member_name': s['member_name'],
                    'created_at': s['created_at'].strftime('%Y-%m-%d %H:%M') if s['created_at'] else ''
                })

        cursor.execute("SELECT NOW() as now")
        server_now = cursor.fetchone()['now'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'success': True,
            'new_notices': new_notices,
            'new_schedules': new_schedules,
            'server_time': server_now
        })

    except Exception as e:
        print(f"알림 체크 오류: {e}")
        return jsonify({'success': False, 'message': '알림 체크 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()