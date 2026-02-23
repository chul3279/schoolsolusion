"""
SchoolUs 내부 메신저 API
- /api/messenger/conversations          : 대화방 목록
- /api/messenger/conversations/create    : 대화방 생성
- /api/messenger/messages                : 메시지 목록
- /api/messenger/messages/send           : 메시지 전송
- /api/messenger/messages/delete         : 메시지 삭제
- /api/messenger/read                    : 읽음 처리
- /api/messenger/unread-count            : 안 읽은 메시지 수
- /api/messenger/contacts                : 연락처 목록
- /api/messenger/conversations/leave     : 대화방 나가기
- /api/messenger/file/download           : 첨부파일 다운로드
"""

from flask import Blueprint, request, jsonify, session, send_file
from utils.db import get_db_connection, sanitize_input, sanitize_html
from routes.subject_utils import sftp_upload_file, sftp_download_file, allowed_file
from utils.push_helper import send_push_to_user
import os
import tempfile
import traceback

messenger_bp = Blueprint('messenger', __name__)


def _check_member_in_conversation(cursor, conversation_id, member_id):
    """대화방 참여자 여부 확인"""
    cursor.execute("""
        SELECT id FROM conversation_members
        WHERE conversation_id = %s AND member_id = %s AND is_active = 1
    """, (conversation_id, member_id))
    return cursor.fetchone() is not None


# ============================================
# 대화방 목록
# ============================================
@messenger_bp.route('/api/messenger/conversations', methods=['GET'])
def get_conversations():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)

        if not all([member_id, school_id]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        page = int(request.args.get('page', 1))
        limit = 30
        offset = (page - 1) * limit

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.id, c.conv_type, c.title, c.updated_at,
                   (SELECT content FROM messages
                    WHERE conversation_id = c.id AND is_deleted = 0
                    ORDER BY created_at DESC LIMIT 1) AS last_message,
                   (SELECT created_at FROM messages
                    WHERE conversation_id = c.id AND is_deleted = 0
                    ORDER BY created_at DESC LIMIT 1) AS last_msg_time,
                   (SELECT m2.member_name FROM messages msg
                    JOIN member m2 ON msg.sender_id = m2.member_id
                    WHERE msg.conversation_id = c.id AND msg.is_deleted = 0
                    ORDER BY msg.created_at DESC LIMIT 1) AS last_sender_name,
                   (SELECT COUNT(*) FROM messages msg2
                    WHERE msg2.conversation_id = c.id
                      AND msg2.created_at > COALESCE(cm.last_read_at, '1970-01-01')
                      AND msg2.sender_id != %s
                      AND msg2.is_deleted = 0) AS unread_count
            FROM conversations c
            JOIN conversation_members cm ON cm.conversation_id = c.id
                 AND cm.member_id = %s AND cm.is_active = 1
            WHERE c.school_id = %s
            ORDER BY c.updated_at DESC
            LIMIT %s OFFSET %s
        """, (member_id, member_id, school_id, limit, offset))

        conversations = []
        for r in cursor.fetchall():
            # 대화 상대방 이름 조회
            cursor.execute("""
                SELECT cm2.member_id, m.member_name, cm2.member_role
                FROM conversation_members cm2
                JOIN member m ON cm2.member_id = m.member_id
                WHERE cm2.conversation_id = %s AND cm2.is_active = 1 AND cm2.member_id != %s
                LIMIT 5
            """, (r['id'], member_id))
            partners = [{'id': p['member_id'], 'name': p['member_name'], 'role': p['member_role']} for p in cursor.fetchall()]

            conversations.append({
                'id': r['id'],
                'conv_type': r['conv_type'],
                'title': r['title'] or (', '.join(p['name'] for p in partners) if partners else '(알 수 없음)'),
                'partners': partners,
                'last_message': r['last_message'] or '',
                'last_msg_time': r['last_msg_time'].strftime('%Y-%m-%d %H:%M') if r['last_msg_time'] else '',
                'last_sender_name': r['last_sender_name'] or '',
                'unread_count': r['unread_count'] or 0,
                'updated_at': r['updated_at'].strftime('%Y-%m-%d %H:%M') if r['updated_at'] else ''
            })

        return jsonify({'success': True, 'conversations': conversations})
    except Exception as e:
        print(f"[Messenger] get_conversations error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '대화 목록 로드 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 대화방 생성
# ============================================
@messenger_bp.route('/api/messenger/conversations/create', methods=['POST'])
def create_conversation():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        creator_id = session.get('user_id') or sanitize_input(data.get('member_id'), 50)
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        creator_role = session.get('user_role') or sanitize_input(data.get('user_role'), 20)
        target_ids = data.get('target_ids', [])  # list of member_id strings
        conv_type = sanitize_input(data.get('conv_type', 'direct'), 10)
        title = sanitize_html(data.get('title', ''))

        if not all([creator_id, school_id, creator_role]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        if not target_ids or not isinstance(target_ids, list):
            return jsonify({'success': False, 'message': '대화 상대를 선택해주세요.'})

        # 1:1 대화는 기존 대화 재사용
        if conv_type == 'direct' and len(target_ids) == 1:
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': 'DB 연결 오류'})
            cursor = conn.cursor()

            cursor.execute("""
                SELECT cm1.conversation_id
                FROM conversation_members cm1
                JOIN conversation_members cm2 ON cm1.conversation_id = cm2.conversation_id
                JOIN conversations c ON c.id = cm1.conversation_id
                WHERE cm1.member_id = %s AND cm1.is_active = 1
                  AND cm2.member_id = %s AND cm2.is_active = 1
                  AND c.conv_type = 'direct' AND c.school_id = %s
                LIMIT 1
            """, (creator_id, target_ids[0], school_id))
            existing = cursor.fetchone()
            if existing:
                return jsonify({'success': True, 'conversation_id': existing['conversation_id'], 'reused': True})

        if not conn:
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': 'DB 연결 오류'})
            cursor = conn.cursor()

        # 권한 검증: 대상이 같은 학교인지 확인
        format_str = ','.join(['%s'] * len(target_ids))
        cursor.execute(f"""
            SELECT member_id FROM member WHERE member_id IN ({format_str}) AND school_id = %s
        """, target_ids + [school_id])
        valid_ids = {row['member_id'] for row in cursor.fetchall()}
        invalid = [tid for tid in target_ids if tid not in valid_ids]
        if invalid:
            return jsonify({'success': False, 'message': '같은 학교 소속이 아닌 사용자가 포함되어 있습니다.'})

        # 학생 권한 검증: 교사에게만 메시지 가능
        if creator_role == 'student':
            cursor.execute(f"""
                SELECT member_id FROM tea_all WHERE member_id IN ({format_str}) AND school_id = %s
            """, target_ids + [school_id])
            teacher_ids = {row['member_id'] for row in cursor.fetchall()}
            if not all(tid in teacher_ids for tid in target_ids):
                return jsonify({'success': False, 'message': '학생은 교사에게만 메시지를 보낼 수 있습니다.'})

        # 학부모 권한 검증: 자녀의 교사에게만
        if creator_role == 'parent':
            cursor.execute("""
                SELECT ta.member_id
                FROM tea_all ta
                JOIN fm_all fa ON fa.school_id = ta.school_id
                    AND (ta.class_grade = fa.class_grade AND ta.class_no = fa.class_no)
                WHERE fa.member_id = %s AND fa.school_id = %s
            """, (creator_id, school_id))
            allowed_teachers = {row['member_id'] for row in cursor.fetchall()}
            if not all(tid in allowed_teachers for tid in target_ids):
                return jsonify({'success': False, 'message': '학부모는 자녀의 교사에게만 메시지를 보낼 수 있습니다.'})

        # 대화방 생성
        cursor.execute("""
            INSERT INTO conversations (school_id, conv_type, title, created_by)
            VALUES (%s, %s, %s, %s)
        """, (school_id, conv_type, title or None, creator_id))
        conv_id = cursor.lastrowid

        # 생성자 추가
        cursor.execute("""
            INSERT INTO conversation_members (conversation_id, member_id, member_role, last_read_at)
            VALUES (%s, %s, %s, NOW())
        """, (conv_id, creator_id, creator_role))

        # 대상 추가
        for tid in target_ids:
            # 대상의 역할 조회
            cursor.execute("SELECT member_roll FROM member WHERE member_id = %s", (tid,))
            t_row = cursor.fetchone()
            t_role = t_row['member_roll'] if t_row else 'student'
            cursor.execute("""
                INSERT INTO conversation_members (conversation_id, member_id, member_role)
                VALUES (%s, %s, %s)
            """, (conv_id, tid, t_role))

        conn.commit()
        return jsonify({'success': True, 'conversation_id': conv_id, 'reused': False})
    except Exception as e:
        if conn: conn.rollback()
        print(f"[Messenger] create_conversation error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '대화방 생성 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 메시지 목록
# ============================================
@messenger_bp.route('/api/messenger/messages', methods=['GET'])
def get_messages():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)
        conv_id = int(request.args.get('conversation_id', 0))
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        if not member_id or not conv_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        if not _check_member_in_conversation(cursor, conv_id, member_id):
            return jsonify({'success': False, 'message': '대화 참여 권한이 없습니다.'})

        cursor.execute("""
            SELECT msg.id, msg.sender_id, msg.content, msg.file_path, msg.file_name,
                   msg.created_at, msg.is_deleted,
                   m.member_name AS sender_name
            FROM messages msg
            JOIN member m ON msg.sender_id = m.member_id
            WHERE msg.conversation_id = %s
            ORDER BY msg.created_at ASC
            LIMIT %s OFFSET %s
        """, (conv_id, limit, offset))

        messages = []
        for r in cursor.fetchall():
            messages.append({
                'id': r['id'],
                'sender_id': r['sender_id'],
                'sender_name': r['sender_name'],
                'content': '삭제된 메시지입니다.' if r['is_deleted'] else r['content'],
                'file_name': r['file_name'] if not r['is_deleted'] else None,
                'has_file': bool(r['file_path']) and not r['is_deleted'],
                'created_at': r['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'is_deleted': bool(r['is_deleted']),
                'is_mine': r['sender_id'] == member_id
            })

        # 읽음 처리 자동 수행
        cursor.execute("""
            UPDATE conversation_members SET last_read_at = NOW()
            WHERE conversation_id = %s AND member_id = %s
        """, (conv_id, member_id))
        conn.commit()

        return jsonify({'success': True, 'messages': messages})
    except Exception as e:
        print(f"[Messenger] get_messages error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '메시지 로드 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 메시지 전송
# ============================================
@messenger_bp.route('/api/messenger/messages/send', methods=['POST'])
def send_message():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id')
        member_name = session.get('user_name', '')
        content = request.form.get('content', '').strip()
        conv_id = int(request.form.get('conversation_id', 0))

        if not member_id or not conv_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        if not content and 'file' not in request.files:
            return jsonify({'success': False, 'message': '메시지 내용을 입력해주세요.'})

        content = sanitize_html(content) if content else ''

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        if not _check_member_in_conversation(cursor, conv_id, member_id):
            return jsonify({'success': False, 'message': '대화 참여 권한이 없습니다.'})

        # 파일 첨부 처리
        file_path = None
        file_name = None
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            if not allowed_file(uploaded_file.filename):
                return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})

            file_name = uploaded_file.filename
            # school_id 조회
            cursor.execute("SELECT school_id FROM conversations WHERE id = %s", (conv_id,))
            conv_row = cursor.fetchone()
            s_id = conv_row['school_id'] if conv_row else 'unknown'

            import time
            ts = int(time.time())
            remote_path = f'/schoolus/messenger/{s_id}/{conv_id}/{ts}_{file_name}'
            local_tmp = os.path.join(tempfile.gettempdir(), f'msg_{ts}_{file_name}')
            uploaded_file.save(local_tmp)
            try:
                sftp_upload_file(local_tmp, remote_path)
                file_path = remote_path
            finally:
                if os.path.exists(local_tmp):
                    os.remove(local_tmp)

        # 메시지 저장
        cursor.execute("""
            INSERT INTO messages (conversation_id, sender_id, content, file_path, file_name)
            VALUES (%s, %s, %s, %s, %s)
        """, (conv_id, member_id, content, file_path, file_name))
        msg_id = cursor.lastrowid

        # 대화방 updated_at 갱신
        cursor.execute("UPDATE conversations SET updated_at = NOW() WHERE id = %s", (conv_id,))

        # 발신자 읽음 처리
        cursor.execute("""
            UPDATE conversation_members SET last_read_at = NOW()
            WHERE conversation_id = %s AND member_id = %s
        """, (conv_id, member_id))

        conn.commit()

        # 상대방 푸시 알림
        cursor.execute("""
            SELECT member_id FROM conversation_members
            WHERE conversation_id = %s AND member_id != %s AND is_active = 1
        """, (conv_id, member_id))
        for row in cursor.fetchall():
            try:
                preview = content[:30] + '...' if len(content) > 30 else content
                if not preview and file_name:
                    preview = f'파일: {file_name}'
                send_push_to_user(
                    row['member_id'],
                    f'{member_name}님의 메시지',
                    preview or '새 메시지가 도착했습니다.',
                    f'/highschool/messenger.html?conv={conv_id}'
                )
            except Exception:
                pass

        return jsonify({'success': True, 'message_id': msg_id})
    except Exception as e:
        if conn: conn.rollback()
        print(f"[Messenger] send_message error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '메시지 전송 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 메시지 삭제
# ============================================
@messenger_bp.route('/api/messenger/messages/delete', methods=['POST'])
def delete_message():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = session.get('user_id') or sanitize_input(data.get('member_id'), 50)
        msg_id = int(data.get('message_id', 0))

        if not member_id or not msg_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT sender_id FROM messages WHERE id = %s", (msg_id,))
        row = cursor.fetchone()
        if not row or row['sender_id'] != member_id:
            return jsonify({'success': False, 'message': '본인이 보낸 메시지만 삭제할 수 있습니다.'})

        cursor.execute("UPDATE messages SET is_deleted = 1 WHERE id = %s", (msg_id,))
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        if conn: conn.rollback()
        print(f"[Messenger] delete_message error: {e}")
        return jsonify({'success': False, 'message': '메시지 삭제 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 읽음 처리
# ============================================
@messenger_bp.route('/api/messenger/read', methods=['POST'])
def mark_read():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = session.get('user_id') or sanitize_input(data.get('member_id'), 50)
        conv_id = int(data.get('conversation_id', 0))

        if not member_id or not conv_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE conversation_members SET last_read_at = NOW()
            WHERE conversation_id = %s AND member_id = %s AND is_active = 1
        """, (conv_id, member_id))
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        if conn: conn.rollback()
        print(f"[Messenger] mark_read error: {e}")
        return jsonify({'success': False, 'message': '읽음 처리 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 안 읽은 메시지 수
# ============================================
@messenger_bp.route('/api/messenger/unread-count', methods=['GET'])
def unread_count():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)

        if not member_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS total_unread FROM messages msg
            JOIN conversation_members cm ON cm.conversation_id = msg.conversation_id
                AND cm.member_id = %s AND cm.is_active = 1
            WHERE msg.created_at > COALESCE(cm.last_read_at, '1970-01-01')
              AND msg.sender_id != %s AND msg.is_deleted = 0
        """, (member_id, member_id))
        row = cursor.fetchone()

        return jsonify({'success': True, 'total_unread': row['total_unread'] if row else 0})
    except Exception as e:
        print(f"[Messenger] unread_count error: {e}")
        return jsonify({'success': False, 'message': '조회 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 연락처 목록
# ============================================
@messenger_bp.route('/api/messenger/contacts', methods=['GET'])
def get_contacts():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        user_role = session.get('user_role') or sanitize_input(request.args.get('user_role'), 20)
        keyword = sanitize_input(request.args.get('keyword'), 50)
        role_filter = sanitize_input(request.args.get('role_filter'), 20)

        if not all([member_id, school_id, user_role]):
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        contacts = []

        if user_role == 'teacher':
            # 교사: 같은 학교 모든 사용자 (본인 제외)
            if not role_filter or role_filter == 'teacher':
                q = """SELECT m.member_id, m.member_name, 'teacher' AS role,
                              ta.class_grade, ta.class_no, ta.department
                       FROM tea_all ta JOIN member m ON ta.member_id = m.member_id
                       WHERE ta.school_id = %s AND ta.member_id != %s"""
                params = [school_id, member_id]
                if keyword:
                    q += " AND m.member_name LIKE %s"
                    params.append(f'%{keyword}%')
                q += " ORDER BY m.member_name"
                cursor.execute(q, params)
                for r in cursor.fetchall():
                    contacts.append({
                        'member_id': r['member_id'], 'name': r['member_name'],
                        'role': 'teacher', 'detail': f"{r['department'] or ''} {r['class_grade'] or ''}-{r['class_no'] or ''}".strip()
                    })

            if not role_filter or role_filter == 'student':
                q = """SELECT m.member_id, m.member_name, 'student' AS role,
                              sa.class_grade, sa.class_no, sa.class_num
                       FROM stu_all sa JOIN member m ON sa.member_id = m.member_id
                       WHERE sa.school_id = %s"""
                params = [school_id]
                if keyword:
                    q += " AND m.member_name LIKE %s"
                    params.append(f'%{keyword}%')
                q += " ORDER BY sa.class_grade, sa.class_no, sa.class_num"
                cursor.execute(q, params)
                for r in cursor.fetchall():
                    contacts.append({
                        'member_id': r['member_id'], 'name': r['member_name'],
                        'role': 'student', 'detail': f"{r['class_grade']}학년 {r['class_no']}반 {r['class_num']}번"
                    })

            if not role_filter or role_filter == 'parent':
                q = """SELECT m.member_id, m.member_name, 'parent' AS role,
                              fa.child_name, fa.class_grade, fa.class_no
                       FROM fm_all fa JOIN member m ON fa.member_id = m.member_id
                       WHERE fa.school_id = %s"""
                params = [school_id]
                if keyword:
                    q += " AND (m.member_name LIKE %s OR fa.child_name LIKE %s)"
                    params.extend([f'%{keyword}%', f'%{keyword}%'])
                q += " ORDER BY fa.class_grade, fa.class_no"
                cursor.execute(q, params)
                for r in cursor.fetchall():
                    contacts.append({
                        'member_id': r['member_id'], 'name': r['member_name'],
                        'role': 'parent', 'detail': f"{r['child_name']} 학부모 ({r['class_grade']}-{r['class_no']})"
                    })

        elif user_role == 'student':
            # 학생: 같은 학교 교사만
            q = """SELECT m.member_id, m.member_name, 'teacher' AS role,
                          ta.class_grade, ta.class_no, ta.department
                   FROM tea_all ta JOIN member m ON ta.member_id = m.member_id
                   WHERE ta.school_id = %s"""
            params = [school_id]
            if keyword:
                q += " AND m.member_name LIKE %s"
                params.append(f'%{keyword}%')
            q += " ORDER BY m.member_name"
            cursor.execute(q, params)
            for r in cursor.fetchall():
                contacts.append({
                    'member_id': r['member_id'], 'name': r['member_name'],
                    'role': 'teacher', 'detail': f"{r['department'] or ''} {r['class_grade'] or ''}-{r['class_no'] or ''}".strip()
                })

        elif user_role == 'parent':
            # 학부모: 자녀의 교사만
            q = """SELECT DISTINCT m.member_id, m.member_name, 'teacher' AS role,
                          ta.class_grade, ta.class_no, ta.department
                   FROM tea_all ta
                   JOIN member m ON ta.member_id = m.member_id
                   JOIN fm_all fa ON fa.school_id = ta.school_id
                       AND ta.class_grade = fa.class_grade AND ta.class_no = fa.class_no
                   WHERE fa.member_id = %s AND fa.school_id = %s"""
            params = [member_id, school_id]
            if keyword:
                q += " AND m.member_name LIKE %s"
                params.append(f'%{keyword}%')
            q += " ORDER BY m.member_name"
            cursor.execute(q, params)
            for r in cursor.fetchall():
                contacts.append({
                    'member_id': r['member_id'], 'name': r['member_name'],
                    'role': 'teacher', 'detail': f"{r['department'] or ''} {r['class_grade'] or ''}-{r['class_no'] or ''}".strip()
                })

        return jsonify({'success': True, 'contacts': contacts})
    except Exception as e:
        print(f"[Messenger] get_contacts error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': '연락처 로드 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 대화방 나가기
# ============================================
@messenger_bp.route('/api/messenger/conversations/leave', methods=['POST'])
def leave_conversation():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        member_id = session.get('user_id') or sanitize_input(data.get('member_id'), 50)
        conv_id = int(data.get('conversation_id', 0))

        if not member_id or not conv_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE conversation_members SET is_active = 0
            WHERE conversation_id = %s AND member_id = %s
        """, (conv_id, member_id))
        conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        if conn: conn.rollback()
        print(f"[Messenger] leave_conversation error: {e}")
        return jsonify({'success': False, 'message': '대화방 나가기 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 첨부파일 다운로드
# ============================================
@messenger_bp.route('/api/messenger/file/download', methods=['GET'])
def download_file():
    conn = None
    cursor = None
    try:
        member_id = session.get('user_id') or sanitize_input(request.args.get('member_id'), 50)
        msg_id = int(request.args.get('message_id', 0))

        if not member_id or not msg_id:
            return jsonify({'success': False, 'message': '필수 정보가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT msg.file_path, msg.file_name, msg.conversation_id
            FROM messages msg
            WHERE msg.id = %s AND msg.is_deleted = 0 AND msg.file_path IS NOT NULL
        """, (msg_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'})

        if not _check_member_in_conversation(cursor, row['conversation_id'], member_id):
            return jsonify({'success': False, 'message': '권한이 없습니다.'})

        local_tmp = os.path.join(tempfile.gettempdir(), f'dl_{msg_id}_{row["file_name"]}')
        sftp_download_file(row['file_path'], local_tmp)

        return send_file(local_tmp, as_attachment=True, download_name=row['file_name'])
    except Exception as e:
        print(f"[Messenger] download_file error: {e}")
        return jsonify({'success': False, 'message': '파일 다운로드 오류'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
