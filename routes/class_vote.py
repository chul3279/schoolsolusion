"""
SchoolUs 학급투표 API
- /api/class-vote/list: 투표 목록 (교사용)
- /api/class-vote/create: 투표 생성 (draft)
- /api/class-vote/detail: 투표 상세 + 선택지 + 결과
- /api/class-vote/update: 투표 수정 (draft만)
- /api/class-vote/delete: 투표 삭제 (draft/closed)
- /api/class-vote/start: 투표 개시 (draft → active)
- /api/class-vote/close: 투표 종료 (active → closed)
- /api/class-vote/respond: 학생/학부모 투표 참여
- /api/class-vote/my-votes: 내 학급 활성 투표 목록 (학생/학부모용)
"""

from flask import Blueprint, request, jsonify, session
from utils.db import get_db_connection, sanitize_input, sanitize_html

class_vote_bp = Blueprint('class_vote', __name__)


# ============================================
# 투표 목록 (교사용)
# ============================================
@class_vote_bp.route('/api/class-vote/list', methods=['GET'])
def list_votes():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id')
        class_grade = sanitize_input(request.args.get('class_grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)

        if not school_id or not class_grade or not class_no:
            return jsonify({'success': False, 'message': '학급 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT v.*,
                (SELECT COUNT(DISTINCT respondent_id) FROM class_vote_response WHERE vote_id = v.id) AS response_count,
                (SELECT COUNT(*) FROM class_vote_option WHERE vote_id = v.id) AS option_count
            FROM class_vote v
            WHERE v.school_id = %s AND v.class_grade = %s AND v.class_no = %s
            ORDER BY v.created_at DESC
        """, (school_id, class_grade, class_no))

        votes = []
        for r in cursor.fetchall():
            votes.append({
                'id': r['id'],
                'title': r['title'],
                'description': r.get('description') or '',
                'vote_type': r['vote_type'],
                'target_role': r['target_role'],
                'status': r['status'],
                'response_count': r['response_count'],
                'option_count': r['option_count'],
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M') if r.get('created_at') else '',
                'started_at': r['started_at'].strftime('%Y-%m-%d %H:%M') if r.get('started_at') else '',
                'closed_at': r['closed_at'].strftime('%Y-%m-%d %H:%M') if r.get('closed_at') else ''
            })

        return jsonify({'success': True, 'votes': votes})

    except Exception as e:
        print(f"투표 목록 오류: {e}")
        return jsonify({'success': False, 'message': '목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 생성
# ============================================
@class_vote_bp.route('/api/class-vote/create', methods=['POST'])
def create_vote():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        school_id = session.get('school_id')
        data = request.get_json()

        title = sanitize_html(data.get('title', ''), 200)
        description = sanitize_html(data.get('description', ''), 1000)
        vote_type = sanitize_input(data.get('vote_type', 'single'), 20)
        target_role = sanitize_input(data.get('target_role', 'student'), 20)
        class_grade = sanitize_input(data.get('class_grade'), 10)
        class_no = sanitize_input(data.get('class_no'), 10)
        options = data.get('options', [])

        if not title:
            return jsonify({'success': False, 'message': '투표 제목을 입력해주세요.'})
        if not class_grade or not class_no:
            return jsonify({'success': False, 'message': '학급 정보가 필요합니다.'})
        if vote_type not in ('single', 'multiple'):
            return jsonify({'success': False, 'message': '유효하지 않은 투표 유형입니다.'})
        if target_role not in ('student', 'parent', 'both'):
            return jsonify({'success': False, 'message': '유효하지 않은 투표 대상입니다.'})
        if len(options) < 2:
            return jsonify({'success': False, 'message': '선택지는 최소 2개 이상 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO class_vote (school_id, class_grade, class_no, title, description, vote_type, target_role, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, class_grade, class_no, title, description, vote_type, target_role, user_id))

        vote_id = cursor.lastrowid

        for idx, opt in enumerate(options):
            text = sanitize_html(opt.get('text', ''), 500)
            if text:
                cursor.execute("""
                    INSERT INTO class_vote_option (vote_id, option_order, option_text)
                    VALUES (%s, %s, %s)
                """, (vote_id, idx + 1, text))

        conn.commit()
        return jsonify({'success': True, 'message': '투표가 생성되었습니다.', 'vote_id': vote_id})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 생성 오류: {e}")
        return jsonify({'success': False, 'message': '투표 생성 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 상세
# ============================================
@class_vote_bp.route('/api/class-vote/detail', methods=['GET'])
def vote_detail():
    conn = None
    cursor = None
    try:
        vote_id = sanitize_input(request.args.get('id'), 20)
        if not vote_id:
            return jsonify({'success': False, 'message': '투표 ID가 필요합니다.'})

        user_id = session.get('user_id')
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})

        # 선택지 + 각 선택지별 응답 수
        cursor.execute("""
            SELECT o.*,
                (SELECT COUNT(*) FROM class_vote_response WHERE option_id = o.id) AS response_count
            FROM class_vote_option o
            WHERE o.vote_id = %s ORDER BY o.option_order
        """, (vote_id,))
        options = []
        for o in cursor.fetchall():
            options.append({
                'id': o['id'],
                'option_order': o['option_order'],
                'option_text': o['option_text'],
                'response_count': o['response_count']
            })

        # 총 응답자 수
        cursor.execute("SELECT COUNT(DISTINCT respondent_id) AS cnt FROM class_vote_response WHERE vote_id = %s", (vote_id,))
        total_respondents = cursor.fetchone()['cnt']

        # 현재 사용자가 이미 투표했는지
        already_responded = False
        if user_id:
            cursor.execute("SELECT id FROM class_vote_response WHERE vote_id = %s AND respondent_id = %s LIMIT 1", (vote_id, user_id))
            already_responded = cursor.fetchone() is not None

        result = {
            'id': vote['id'],
            'title': vote['title'],
            'description': vote.get('description') or '',
            'vote_type': vote['vote_type'],
            'target_role': vote['target_role'],
            'status': vote['status'],
            'created_by': vote['created_by'],
            'created_at': vote['created_at'].strftime('%Y-%m-%d %H:%M') if vote.get('created_at') else '',
            'started_at': vote['started_at'].strftime('%Y-%m-%d %H:%M') if vote.get('started_at') else '',
            'closed_at': vote['closed_at'].strftime('%Y-%m-%d %H:%M') if vote.get('closed_at') else '',
            'options': options,
            'total_respondents': total_respondents,
            'already_responded': already_responded
        }

        return jsonify({'success': True, 'vote': result})

    except Exception as e:
        print(f"투표 상세 오류: {e}")
        return jsonify({'success': False, 'message': '투표 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 수정 (draft만)
# ============================================
@class_vote_bp.route('/api/class-vote/update', methods=['POST'])
def update_vote():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        vote_id = sanitize_input(data.get('vote_id'), 20)
        title = sanitize_html(data.get('title', ''), 200)
        description = sanitize_html(data.get('description', ''), 1000)
        vote_type = sanitize_input(data.get('vote_type', 'single'), 20)
        target_role = sanitize_input(data.get('target_role', 'student'), 20)
        options = data.get('options', [])

        if not vote_id or not title:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})
        if len(options) < 2:
            return jsonify({'success': False, 'message': '선택지는 최소 2개 이상 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})
        if vote['status'] != 'draft':
            return jsonify({'success': False, 'message': '임시저장 상태의 투표만 수정할 수 있습니다.'})

        cursor.execute("""
            UPDATE class_vote SET title=%s, description=%s, vote_type=%s, target_role=%s WHERE id=%s
        """, (title, description, vote_type, target_role, vote_id))

        # 선택지 재생성
        cursor.execute("DELETE FROM class_vote_option WHERE vote_id = %s", (vote_id,))
        for idx, opt in enumerate(options):
            text = sanitize_html(opt.get('text', ''), 500)
            if text:
                cursor.execute("INSERT INTO class_vote_option (vote_id, option_order, option_text) VALUES (%s, %s, %s)",
                               (vote_id, idx + 1, text))

        conn.commit()
        return jsonify({'success': True, 'message': '투표가 수정되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 수정 오류: {e}")
        return jsonify({'success': False, 'message': '투표 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 삭제 (draft/closed만)
# ============================================
@class_vote_bp.route('/api/class-vote/delete', methods=['POST'])
def delete_vote():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        vote_id = sanitize_input(data.get('vote_id'), 20)

        if not vote_id:
            return jsonify({'success': False, 'message': '투표 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})
        if vote['status'] == 'active':
            return jsonify({'success': False, 'message': '진행중인 투표는 삭제할 수 없습니다. 먼저 종료해주세요.'})

        cursor.execute("DELETE FROM class_vote WHERE id = %s", (vote_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '투표가 삭제되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 삭제 오류: {e}")
        return jsonify({'success': False, 'message': '투표 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 시작 (draft → active)
# ============================================
@class_vote_bp.route('/api/class-vote/start', methods=['POST'])
def start_vote():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        vote_id = sanitize_input(data.get('vote_id'), 20)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})
        if vote['status'] != 'draft':
            return jsonify({'success': False, 'message': '임시저장 상태의 투표만 시작할 수 있습니다.'})

        cursor.execute("UPDATE class_vote SET status='active', started_at=NOW() WHERE id=%s", (vote_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '투표가 시작되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 시작 오류: {e}")
        return jsonify({'success': False, 'message': '투표 시작 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 종료 (active → closed)
# ============================================
@class_vote_bp.route('/api/class-vote/close', methods=['POST'])
def close_vote():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        vote_id = sanitize_input(data.get('vote_id'), 20)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})
        if vote['status'] != 'active':
            return jsonify({'success': False, 'message': '진행중인 투표만 종료할 수 있습니다.'})

        cursor.execute("UPDATE class_vote SET status='closed', closed_at=NOW() WHERE id=%s", (vote_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '투표가 종료되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 종료 오류: {e}")
        return jsonify({'success': False, 'message': '투표 종료 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 투표 참여 (학생/학부모)
# ============================================
@class_vote_bp.route('/api/class-vote/respond', methods=['POST'])
def respond_vote():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        data = request.get_json()
        vote_id = sanitize_input(data.get('vote_id'), 20)
        selected_options = data.get('selected_options', [])

        if not vote_id or not selected_options:
            return jsonify({'success': False, 'message': '투표 항목을 선택해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 투표 정보 확인
        cursor.execute("SELECT * FROM class_vote WHERE id = %s", (vote_id,))
        vote = cursor.fetchone()
        if not vote:
            return jsonify({'success': False, 'message': '투표를 찾을 수 없습니다.'})
        if vote['status'] != 'active':
            return jsonify({'success': False, 'message': '진행중인 투표가 아닙니다.'})

        # 대상 역할 확인
        if vote['target_role'] == 'student' and user_role != 'student':
            return jsonify({'success': False, 'message': '학생만 참여할 수 있는 투표입니다.'})
        if vote['target_role'] == 'parent' and user_role != 'parent':
            return jsonify({'success': False, 'message': '학부모만 참여할 수 있는 투표입니다.'})
        if vote['target_role'] == 'both' and user_role not in ('student', 'parent'):
            return jsonify({'success': False, 'message': '참여 권한이 없습니다.'})

        # 중복 투표 확인
        cursor.execute("SELECT id FROM class_vote_response WHERE vote_id = %s AND respondent_id = %s LIMIT 1", (vote_id, user_id))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 투표에 참여하셨습니다.'})

        # 단일 선택 검증
        if vote['vote_type'] == 'single' and len(selected_options) > 1:
            return jsonify({'success': False, 'message': '하나의 항목만 선택해주세요.'})

        # 응답 저장
        for opt_id in selected_options:
            cursor.execute("""
                INSERT INTO class_vote_response (vote_id, option_id, respondent_id, respondent_role)
                VALUES (%s, %s, %s, %s)
            """, (vote_id, opt_id, user_id, user_role))

        conn.commit()
        return jsonify({'success': True, 'message': '투표가 완료되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"투표 참여 오류: {e}")
        return jsonify({'success': False, 'message': '투표 참여 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 내 학급 활성 투표 목록 (학생/학부모용)
# ============================================
@class_vote_bp.route('/api/class-vote/my-votes', methods=['GET'])
def my_votes():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        school_id = session.get('school_id')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 학생/학부모의 학급 정보 가져오기
        class_grade = None
        class_no = None

        if user_role == 'student':
            cursor.execute("SELECT class_grade, class_no FROM stu_all WHERE member_id = %s AND school_id = %s LIMIT 1",
                           (user_id, school_id))
            stu = cursor.fetchone()
            if stu:
                class_grade = stu['class_grade']
                class_no = stu['class_no']
        elif user_role == 'parent':
            cursor.execute("SELECT class_grade, class_no FROM fm_all WHERE member_id = %s AND school_id = %s LIMIT 1",
                           (user_id, school_id))
            fm = cursor.fetchone()
            if fm:
                class_grade = fm['class_grade']
                class_no = fm['class_no']

        if not class_grade or not class_no:
            return jsonify({'success': True, 'votes': []})

        # 대상 역할에 맞는 활성 투표 조회
        role_filter = user_role  # 'student' or 'parent'
        cursor.execute("""
            SELECT v.*,
                (SELECT COUNT(DISTINCT respondent_id) FROM class_vote_response WHERE vote_id = v.id) AS response_count
            FROM class_vote v
            WHERE v.school_id = %s AND v.class_grade = %s AND v.class_no = %s
              AND v.status = 'active'
              AND (v.target_role = %s OR v.target_role = 'both')
            ORDER BY v.started_at DESC
        """, (school_id, class_grade, class_no, role_filter))

        votes = []
        for r in cursor.fetchall():
            # 이미 투표했는지 확인
            cursor.execute("SELECT id FROM class_vote_response WHERE vote_id = %s AND respondent_id = %s LIMIT 1",
                           (r['id'], user_id))
            already = cursor.fetchone() is not None

            votes.append({
                'id': r['id'],
                'title': r['title'],
                'description': r.get('description') or '',
                'vote_type': r['vote_type'],
                'target_role': r['target_role'],
                'response_count': r['response_count'],
                'started_at': r['started_at'].strftime('%Y-%m-%d') if r.get('started_at') else '',
                'already_responded': already
            })

        return jsonify({'success': True, 'votes': votes})

    except Exception as e:
        print(f"내 투표 목록 오류: {e}")
        return jsonify({'success': False, 'message': '투표 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
