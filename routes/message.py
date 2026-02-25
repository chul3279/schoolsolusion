"""
SchoolUs 메시지 기능 — 독립형 Blueprint
- message_rooms, message_room_members, messages, message_users 4개 테이블만 사용
- 외부 테이블(tea_all, stu_all, fm_all 등) JOIN 없음 → 서버 분리 대비
"""

from flask import Blueprint, request, jsonify, session, make_response
import json, os, io, time, tempfile, re
from datetime import datetime
from urllib.parse import quote

from utils.db import get_db_connection, sanitize_input, sanitize_html

message_bp = Blueprint('message', __name__)

# ============================================
# 파일 첨부 설정
# ============================================
ALLOWED_IMAGE_EXT = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_FILE_EXT = {'pdf', 'doc', 'docx', 'hwp', 'hwpx', 'xlsx', 'xls', 'ppt', 'pptx', 'txt', 'zip'}
ALLOWED_ALL_EXT = ALLOWED_IMAGE_EXT | ALLOWED_FILE_EXT
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _secure_filename_korean(filename):
    """한글 보존하면서 위험 문자만 제거"""
    filename = filename.replace('/', '').replace('\\', '')
    filename = re.sub(r'[<>:"|?*]', '', filename)
    filename = filename.strip('. ')
    return filename or 'unnamed'


@message_bp.before_app_request
def _auto_sync_message_user():
    """로그인된 사용자가 /api/message/ 요청 시 message_users 자동 동기화 (세션당 1회)."""
    if not request.path.startswith('/api/message/'):
        return None
    if session.get('_msg_synced'):
        return None
    uid = session.get('user_id')
    sid = session.get('school_id')
    uname = session.get('user_name')
    urole = session.get('user_role')
    if not uid or not sid or not uname or not urole:
        return None
    role_map = {'teacher': 'teacher', 'student': 'student', 'parent': 'parent'}
    db_role = role_map.get(urole)
    if not db_role:
        return None
    sync_message_user(
        member_id=uid, school_id=str(sid), member_name=uname, member_role=db_role,
        class_grade=session.get('class_grade'), class_no=session.get('class_no'),
        parent_of=session.get('selected_child_id'),
        parent_of_name=session.get('selected_child_name'),
    )
    session['_msg_synced'] = True
    return None


# ============================================
# message_users 동기화 (로그인 시 호출)
# ============================================

def sync_message_user(member_id, school_id, member_name, member_role,
                      class_grade=None, class_no=None, class_num=None,
                      parent_of=None, parent_of_name=None):
    """로그인 시 message_users 캐시 테이블에 사용자 정보 upsert."""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM message_users
            WHERE school_id = %s AND member_id = %s
        """, (school_id, member_id))
        row = cursor.fetchone()
        if row:
            cursor.execute("""
                UPDATE message_users
                SET member_name=%s, member_role=%s,
                    class_grade=%s, class_no=%s, class_num=%s,
                    parent_of=%s, parent_of_name=%s, updated_at=NOW()
                WHERE school_id=%s AND member_id=%s
            """, (member_name, member_role, class_grade, class_no, class_num,
                  parent_of, parent_of_name, school_id, member_id))
        else:
            cursor.execute("""
                INSERT INTO message_users
                (school_id, member_id, member_name, member_role,
                 class_grade, class_no, class_num, parent_of, parent_of_name)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (school_id, member_id, member_name, member_role,
                  class_grade, class_no, class_num, parent_of, parent_of_name))
        conn.commit()
    except Exception as e:
        print(f"[Message] sync_message_user error: {e}")
    finally:
        cursor.close()
        conn.close()


# ============================================
# 헬퍼 함수
# ============================================

def _get_session_info():
    """세션에서 사용자 정보 추출. (member_id, school_id, user_role) 또는 None"""
    uid = session.get('user_id')
    sid = session.get('school_id')
    role = session.get('user_role')
    if not uid or not sid:
        return None
    return uid, str(sid), role


def _get_my_name(cursor, member_id, school_id):
    """message_users에서 이름 조회"""
    cursor.execute(
        "SELECT member_name FROM message_users WHERE member_id=%s AND school_id=%s",
        (member_id, school_id))
    row = cursor.fetchone()
    return row['member_name'] if row else member_id


def _is_room_member(cursor, room_id, member_id):
    """해당 방의 활성 멤버인지 확인"""
    cursor.execute("""
        SELECT id, is_admin FROM message_room_members
        WHERE room_id=%s AND member_id=%s AND is_active=1
    """, (room_id, member_id))
    return cursor.fetchone()


def _system_message(cursor, room_id, content):
    """시스템 메시지 삽입"""
    cursor.execute("""
        INSERT INTO messages (room_id, sender_id, sender_name, sender_role, content, is_system)
        VALUES (%s, 'system', '시스템', 'teacher', %s, 1)
    """, (room_id, content))


# ============================================
# API 1: 사용자 목록 (대화 가능한 사람)
# ============================================
@message_bp.route('/api/message/users', methods=['GET'])
def get_users():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        search = request.args.get('search', '').strip()
        keyword = request.args.get('keyword', '').strip()  # search 별칭
        search = search or keyword  # 둘 중 하나라도 있으면 사용
        role_filter = request.args.get('role', '')  # teacher / student / parent / ''
        class_grade = request.args.get('class_grade', '').strip()
        class_no = request.args.get('class_no', '').strip()

        sql = """
            SELECT member_id, member_name, member_role,
                   class_grade, class_no, class_num, parent_of_name
            FROM message_users
            WHERE school_id = %s AND member_id != %s
        """
        params = [school_id, member_id]

        # 역할별 대화 상대 제한
        if role == 'student':
            # 학생: 교사 + 같은 학교 학생만 (학부모 제외)
            sql += " AND member_role IN ('teacher','student')"
        elif role == 'parent':
            # 학부모: 교사만
            sql += " AND member_role = 'teacher'"

        if role_filter:
            sql += " AND member_role = %s"
            params.append(role_filter)

        if class_grade:
            sql += " AND class_grade = %s"
            params.append(class_grade)

        if class_no:
            sql += " AND class_no = %s"
            params.append(class_no)

        if search:
            sql += " AND member_name LIKE %s"
            params.append(f'%{search}%')

        sql += " ORDER BY member_role ASC, member_name ASC LIMIT 200"

        cursor.execute(sql, params)
        users = cursor.fetchall()

        return jsonify({'success': True, 'users': users})
    except Exception as e:
        print(f"[Message] get_users error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 1-B: 단체 선택용 그룹 목록
# ============================================
@message_bp.route('/api/message/users/groups', methods=['GET'])
def get_user_groups():
    """학년/반별 사용자 그룹 목록 반환 (교사용 단체 선택)"""
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 학년/반 별 학생 수
        cursor.execute("""
            SELECT class_grade, class_no, COUNT(*) AS cnt
            FROM message_users
            WHERE school_id=%s AND member_role='student'
              AND class_grade IS NOT NULL AND class_grade != ''
            GROUP BY class_grade, class_no
            ORDER BY class_grade ASC, CAST(class_no AS UNSIGNED) ASC
        """, (school_id,))
        class_groups = cursor.fetchall()

        # 학년별 집계
        grade_map = {}
        for g in class_groups:
            gr = g['class_grade']
            if gr not in grade_map:
                grade_map[gr] = {'grade': gr, 'total_students': 0, 'classes': []}
            grade_map[gr]['total_students'] += g['cnt']
            grade_map[gr]['classes'].append({
                'class_no': g['class_no'],
                'student_count': g['cnt']
            })

        # 학년/반 별 학부모 수
        cursor.execute("""
            SELECT class_grade, class_no, COUNT(*) AS cnt
            FROM message_users
            WHERE school_id=%s AND member_role='parent'
              AND class_grade IS NOT NULL AND class_grade != ''
            GROUP BY class_grade, class_no
            ORDER BY class_grade ASC, CAST(class_no AS UNSIGNED) ASC
        """, (school_id,))
        parent_groups = cursor.fetchall()
        parent_map = {}
        for p in parent_groups:
            key = f"{p['class_grade']}_{p['class_no']}"
            parent_map[key] = p['cnt']

        # 교사 수
        cursor.execute("""
            SELECT COUNT(*) AS cnt FROM message_users
            WHERE school_id=%s AND member_role='teacher'
        """, (school_id,))
        teacher_count = cursor.fetchone()['cnt']

        grades = sorted(grade_map.values(), key=lambda x: x['grade'])

        return jsonify({
            'success': True,
            'grades': grades,
            'parent_map': parent_map,
            'teacher_count': teacher_count
        })
    except Exception as e:
        print(f"[Message] get_user_groups error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 1-C: 단체 선택 — 그룹 멤버 ID 일괄 조회
# ============================================
@message_bp.route('/api/message/users/by-group', methods=['GET'])
def get_users_by_group():
    """학년/반/역할 기준으로 사용자 목록 반환"""
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    group_role = request.args.get('role', '')  # teacher / student / parent
    grade = request.args.get('grade', '')
    class_no = request.args.get('class_no', '')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        sql = """
            SELECT member_id, member_name, member_role, class_grade, class_no
            FROM message_users
            WHERE school_id=%s AND member_id != %s
        """
        params = [school_id, member_id]

        if group_role:
            sql += " AND member_role=%s"
            params.append(group_role)
        if grade:
            sql += " AND class_grade=%s"
            params.append(grade)
        if class_no:
            sql += " AND class_no=%s"
            params.append(class_no)

        sql += " ORDER BY member_name ASC LIMIT 500"
        cursor.execute(sql, params)
        users = cursor.fetchall()

        return jsonify({'success': True, 'users': users})
    except Exception as e:
        print(f"[Message] get_users_by_group error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 2: 내 대화방 목록
# ============================================
@message_bp.route('/api/message/rooms', methods=['GET'])
def get_rooms():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        page = max(1, int(request.args.get('page', 1)))
        limit = min(50, int(request.args.get('limit', 30)))
        offset = (page - 1) * limit

        cursor.execute("""
            SELECT r.id, r.room_type, r.room_title, r.announcement_only,
                   r.created_at, r.is_active,
                   rm.is_admin, rm.last_read_at,
                   (SELECT COUNT(*) FROM messages m
                    WHERE m.room_id = r.id AND m.is_deleted = 0
                      AND m.created_at > COALESCE(rm.last_read_at, rm.joined_at, r.created_at)
                      AND m.sender_id != %s) AS unread_count,
                   (SELECT m2.content FROM messages m2
                    WHERE m2.room_id = r.id AND m2.is_deleted = 0
                    ORDER BY m2.created_at DESC LIMIT 1) AS last_message,
                   (SELECT m3.sender_name FROM messages m3
                    WHERE m3.room_id = r.id AND m3.is_deleted = 0
                    ORDER BY m3.created_at DESC LIMIT 1) AS last_sender,
                   (SELECT m4.created_at FROM messages m4
                    WHERE m4.room_id = r.id AND m4.is_deleted = 0
                    ORDER BY m4.created_at DESC LIMIT 1) AS last_msg_time
            FROM message_rooms r
            JOIN message_room_members rm ON rm.room_id = r.id
            WHERE rm.member_id = %s AND rm.is_active = 1
              AND r.school_id = %s AND r.is_active = 1
            ORDER BY COALESCE(
                (SELECT m5.created_at FROM messages m5
                 WHERE m5.room_id = r.id AND m5.is_deleted = 0
                 ORDER BY m5.created_at DESC LIMIT 1),
                r.created_at
            ) DESC
            LIMIT %s OFFSET %s
        """, (member_id, member_id, school_id, limit, offset))
        rooms = cursor.fetchall()

        # 각 방의 멤버 목록 첨부 (이름 표시용)
        for room in rooms:
            cursor.execute("""
                SELECT member_id, member_name, member_role, is_admin
                FROM message_room_members
                WHERE room_id = %s AND is_active = 1
            """, (room['id'],))
            room['members'] = cursor.fetchall()
            # datetime → str
            for key in ('created_at', 'last_read_at', 'last_msg_time'):
                if room.get(key):
                    room[key] = str(room[key])

        return jsonify({'success': True, 'rooms': rooms})
    except Exception as e:
        print(f"[Message] get_rooms error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 3: 대화방 생성
# ============================================
@message_bp.route('/api/message/room/create', methods=['POST'])
def create_room():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    raw_room_type = data.get('room_type', 'direct')
    if raw_room_type == 'individual':
        raw_room_type = 'direct'
    room_type = sanitize_input(raw_room_type, 20)
    if room_type not in ('direct', 'class', 'grade', 'school', 'group'):
        return jsonify({'success': False, 'message': '유효하지 않은 방 타입입니다.'})
    room_title = sanitize_input(data.get('room_title', ''), 100)
    target_ids = data.get('target_ids', [])  # list of member_id
    announcement_only = 1 if data.get('announcement_only') else 0
    class_grade = data.get('class_grade', '')
    class_no = data.get('class_no', '')
    target_roles = data.get('target_roles', [])  # class/grade/school 용

    # class/grade/school 타입은 교사만 생성 가능
    if room_type in ('class', 'grade', 'school') and role != 'teacher':
        return jsonify({'success': False, 'message': '교사만 단체 대화방을 만들 수 있습니다.'})

    # direct/group은 target_ids 필수
    if room_type in ('direct', 'group') and not target_ids:
        return jsonify({'success': False, 'message': '대화 상대를 선택해주세요.'})

    # class/grade/school은 조건 검증
    if room_type == 'class' and (not class_grade or not class_no):
        return jsonify({'success': False, 'message': '학년과 반을 지정해주세요.'})
    if room_type == 'grade' and not class_grade:
        return jsonify({'success': False, 'message': '학년을 지정해주세요.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # class/grade/school 타입: 자동으로 대상 멤버 조회
        if room_type in ('class', 'grade', 'school') and not target_ids:
            auto_sql = """
                SELECT member_id FROM message_users
                WHERE school_id = %s AND member_id != %s
            """
            auto_params = [school_id, member_id]

            if target_roles:
                role_fmt = ','.join(['%s'] * len(target_roles))
                auto_sql += f" AND member_role IN ({role_fmt})"
                auto_params.extend(target_roles)

            if room_type == 'class':
                auto_sql += " AND class_grade = %s AND class_no = %s"
                auto_params.extend([class_grade, class_no])
            elif room_type == 'grade':
                auto_sql += " AND class_grade = %s"
                auto_params.append(class_grade)
            # school: 학교 전체 (추가 필터 없음)

            cursor.execute(auto_sql, auto_params)
            target_ids = [r['member_id'] for r in cursor.fetchall()]

            if not target_ids:
                return jsonify({'success': False, 'message': '해당 조건에 맞는 사용자가 없습니다.'})

            # 자동 타이틀 생성
            if not room_title:
                if room_type == 'class':
                    room_title = f'{class_grade}학년 {class_no}반 단체방'
                elif room_type == 'grade':
                    room_title = f'{class_grade}학년 단체방'
                elif room_type == 'school':
                    room_title = '학교 전체 단체방'

        # 대화 상대가 같은 학교인지 확인
        fmt = ','.join(['%s'] * len(target_ids))
        cursor.execute(f"""
            SELECT member_id, member_name, member_role, class_grade, class_no
            FROM message_users
            WHERE school_id = %s AND member_id IN ({fmt})
        """, [school_id] + target_ids)
        valid_users = {r['member_id']: r for r in cursor.fetchall()}
        invalid = [t for t in target_ids if t not in valid_users]
        if invalid:
            return jsonify({'success': False, 'message': '같은 학교 소속이 아닌 사용자가 포함되어 있습니다.'})

        # 역할 제한 강화 (direct/group만 적용, class/grade/school은 교사 전용이므로 스킵)
        if room_type in ('direct', 'group'):
            if role == 'student':
                for tid in target_ids:
                    t_role = valid_users[tid]['member_role']
                    if t_role == 'parent':
                        return jsonify({'success': False, 'message': '학생은 학부모에게 메시지를 보낼 수 없습니다.'})
            elif role == 'parent':
                for tid in target_ids:
                    t_role = valid_users[tid]['member_role']
                    if t_role != 'teacher':
                        return jsonify({'success': False, 'message': '학부모는 교사에게만 메시지를 보낼 수 있습니다.'})

        # 1:1 대화 중복 방지
        if room_type == 'direct' and len(target_ids) == 1:
            cursor.execute("""
                SELECT rm1.room_id
                FROM message_room_members rm1
                JOIN message_room_members rm2 ON rm1.room_id = rm2.room_id
                JOIN message_rooms r ON r.id = rm1.room_id
                WHERE rm1.member_id = %s AND rm1.is_active = 1
                  AND rm2.member_id = %s AND rm2.is_active = 1
                  AND r.room_type = 'direct' AND r.school_id = %s AND r.is_active = 1
                LIMIT 1
            """, (member_id, target_ids[0], school_id))
            existing = cursor.fetchone()
            if existing:
                return jsonify({'success': True, 'room_id': existing['room_id'], 'reused': True})

        # 내 정보 조회
        my_name = _get_my_name(cursor, member_id, school_id)
        cursor.execute(
            "SELECT class_grade, class_no FROM message_users WHERE member_id=%s AND school_id=%s",
            (member_id, school_id))
        my_info = cursor.fetchone() or {}

        # 방 생성
        target_roles_str = ','.join(target_roles) if target_roles else None
        cursor.execute("""
            INSERT INTO message_rooms
            (school_id, room_type, room_title, class_grade, class_no,
             target_roles, announcement_only, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, room_type, room_title or None,
              class_grade or None, class_no or None,
              target_roles_str, announcement_only, member_id))
        room_id = cursor.lastrowid

        # 생성자 멤버 추가 (admin)
        my_role_enum = role if role in ('teacher', 'student', 'parent') else 'teacher'
        cursor.execute("""
            INSERT INTO message_room_members
            (room_id, member_id, member_name, member_role, class_grade, class_no, is_admin)
            VALUES (%s,%s,%s,%s,%s,%s,1)
        """, (room_id, member_id, my_name, my_role_enum,
              my_info.get('class_grade'), my_info.get('class_no')))

        # 대화 상대 멤버 추가
        for tid in target_ids:
            u = valid_users[tid]
            cursor.execute("""
                INSERT INTO message_room_members
                (room_id, member_id, member_name, member_role, class_grade, class_no, is_admin)
                VALUES (%s,%s,%s,%s,%s,%s,0)
            """, (room_id, tid, u['member_name'], u['member_role'],
                  u.get('class_grade'), u.get('class_no')))

        # 시스템 메시지
        if room_type != 'direct':
            _system_message(cursor, room_id, f'{my_name}님이 대화방을 만들었습니다.')

        conn.commit()
        return jsonify({'success': True, 'room_id': room_id})
    except Exception as e:
        conn.rollback()
        print(f"[Message] create_room error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 4: 메시지 목록 (대화 내용)
# ============================================
@message_bp.route('/api/message/list', methods=['GET'])
def get_messages():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    room_id = request.args.get('room_id')
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 멤버 확인
        mem = _is_room_member(cursor, room_id, member_id)
        if not mem:
            return jsonify({'success': False, 'message': '대화방 접근 권한이 없습니다.'}), 403

        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, int(request.args.get('limit', 50)))
        offset = (page - 1) * limit

        # before_id: 무한스크롤 — 이 ID보다 작은(이전) 메시지
        before_id = request.args.get('before_id')

        if before_id:
            cursor.execute("""
                SELECT id, room_id, sender_id, sender_name, sender_role,
                       content, message_type, file_name, is_system, is_deleted, created_at
                FROM messages
                WHERE room_id = %s AND id < %s AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT %s
            """, (room_id, before_id, limit))
        else:
            cursor.execute("""
                SELECT id, room_id, sender_id, sender_name, sender_role,
                       content, message_type, file_name, is_system, is_deleted, created_at
                FROM messages
                WHERE room_id = %s AND is_deleted = 0
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (room_id, limit, offset))

        msgs = cursor.fetchall()
        for m in msgs:
            m['is_mine'] = (m['sender_id'] == member_id)
            if m.get('created_at'):
                m['created_at'] = str(m['created_at'])
            if m.get('is_deleted'):
                m['content'] = '삭제된 메시지입니다.'
                m['file_name'] = None

        # 방 정보
        cursor.execute("""
            SELECT id, room_type, room_title, announcement_only, created_by
            FROM message_rooms WHERE id = %s
        """, (room_id,))
        room_info = cursor.fetchone()

        # 멤버 목록
        cursor.execute("""
            SELECT member_id, member_name, member_role, is_admin
            FROM message_room_members
            WHERE room_id = %s AND is_active = 1
        """, (room_id,))
        members = cursor.fetchall()

        return jsonify({
            'success': True,
            'messages': list(reversed(msgs)),  # 시간순 정렬
            'room': room_info,
            'members': members
        })
    except Exception as e:
        print(f"[Message] get_messages error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 5: 메시지 전송
# ============================================
@message_bp.route('/api/message/send', methods=['POST'])
def send_message():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    # multipart (파일첨부) 또는 JSON
    if request.content_type and 'multipart' in request.content_type:
        room_id = request.form.get('room_id')
        content = request.form.get('content', '').strip()
        uploaded_file = request.files.get('file')
    else:
        data = request.get_json(silent=True) or {}
        room_id = data.get('room_id')
        content = data.get('content', '').strip()
        uploaded_file = None

    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})
    if not content and not uploaded_file:
        return jsonify({'success': False, 'message': '메시지를 입력해주세요.'})

    content = sanitize_html(content, 5000) if content else ''

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 멤버/방 확인
        mem = _is_room_member(cursor, room_id, member_id)
        if not mem:
            return jsonify({'success': False, 'message': '대화방 접근 권한이 없습니다.'}), 403

        # 공지방/단체방 쓰기 권한 체크
        cursor.execute("SELECT announcement_only, room_type FROM message_rooms WHERE id=%s", (room_id,))
        room = cursor.fetchone()
        if room and room['announcement_only'] and not mem['is_admin']:
            return jsonify({'success': False, 'message': '공지 전용 대화방에서는 관리자만 메시지를 보낼 수 있습니다.'})
        # [보안] school/grade 타입 대화방은 교사(admin)만 전송 가능
        if room and room['room_type'] in ('school', 'grade') and role != 'teacher' and not mem['is_admin']:
            return jsonify({'success': False, 'message': '학교/학년 대화방에서는 교사만 메시지를 보낼 수 있습니다.'}), 403

        my_name = _get_my_name(cursor, member_id, school_id)
        my_role_enum = role if role in ('teacher', 'student', 'parent') else 'teacher'

        # 파일 처리
        file_path = None
        file_name = None
        message_type = 'text'

        if uploaded_file and uploaded_file.filename:
            from routes.subject_utils import sftp_upload_file
            safe_fname = _secure_filename_korean(uploaded_file.filename)
            ext = safe_fname.rsplit('.', 1)[1].lower() if '.' in safe_fname else ''

            # 학생은 이미지만 허용
            if role == 'student':
                if ext not in ALLOWED_IMAGE_EXT:
                    return jsonify({'success': False, 'message': '학생은 이미지 파일만 첨부할 수 있습니다.'})
            else:
                if ext not in ALLOWED_ALL_EXT:
                    return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})

            file_data = uploaded_file.read()
            if len(file_data) == 0:
                return jsonify({'success': False, 'message': '빈 파일은 업로드할 수 없습니다.'})
            if len(file_data) > MAX_FILE_SIZE:
                return jsonify({'success': False, 'message': f'파일 크기가 {MAX_FILE_SIZE // (1024*1024)}MB를 초과합니다.'})

            ts = int(time.time())
            remote_path = f'/data/messages/{school_id}/{room_id}/{ts}_{safe_fname}'

            upload_ok = sftp_upload_file(io.BytesIO(file_data), remote_path)
            if not upload_ok:
                return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

            file_path = remote_path
            file_name = safe_fname
            message_type = 'image' if ext in ALLOWED_IMAGE_EXT else 'file'

        # 메시지 INSERT
        cursor.execute("""
            INSERT INTO messages
            (room_id, sender_id, sender_name, sender_role, content,
             message_type, file_path, file_name)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (room_id, member_id, my_name, my_role_enum,
              content, message_type, file_path, file_name))
        msg_id = cursor.lastrowid

        # 내 last_read_at 갱신
        cursor.execute("""
            UPDATE message_room_members SET last_read_at = NOW()
            WHERE room_id=%s AND member_id=%s
        """, (room_id, member_id))

        conn.commit()

        # 푸시 알림 (비동기적, 실패해도 메시지 전송은 성공)
        try:
            from utils.push_helper import send_push_to_user
            cursor2 = conn.cursor()
            cursor2.execute("""
                SELECT member_id FROM message_room_members
                WHERE room_id=%s AND member_id != %s AND is_active=1
            """, (room_id, member_id))
            recipients = cursor2.fetchall()
            cursor2.close()

            preview = content[:30] + '...' if len(content) > 30 else content
            if not preview and file_name:
                preview = f'파일: {file_name}'
            for r in recipients:
                try:
                    send_push_to_user(
                        r['member_id'],
                        f'{my_name}님의 메시지',
                        preview or '새 메시지가 도착했습니다.',
                        f'/highschool/tea/message.html?room={room_id}'
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # 생성된 메시지의 시간 조회
        cursor.execute("SELECT created_at FROM messages WHERE id=%s", (msg_id,))
        created_row = cursor.fetchone()

        return jsonify({
            'success': True,
            'message_id': msg_id,
            'sender_name': my_name,
            'created_at': str(created_row['created_at']) if created_row else '',
        })
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[Message] send_message error: {e}")
        return jsonify({'success': False, 'message': '메시지 전송 중 오류가 발생했습니다.'}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# API 6: 읽음 처리
# ============================================
@message_bp.route('/api/message/read', methods=['POST'])
def mark_read():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE message_room_members
            SET last_read_at = NOW()
            WHERE room_id=%s AND member_id=%s AND is_active=1
        """, (room_id, member_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"[Message] mark_read error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 7: 메시지 삭제 (본인만)
# ============================================
@message_bp.route('/api/message/delete', methods=['POST'])
def delete_message():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    message_id = data.get('message_id')
    if not message_id:
        return jsonify({'success': False, 'message': 'message_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE messages SET is_deleted=1
            WHERE id=%s AND sender_id=%s
        """, (message_id, member_id))
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': '삭제 권한이 없거나 메시지를 찾을 수 없습니다.'})
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        print(f"[Message] delete_message error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 8: 안 읽은 메시지 수
# ============================================
@message_bp.route('/api/message/unread', methods=['GET'])
def unread_count():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS total_unread
            FROM messages msg
            JOIN message_room_members rm ON rm.room_id = msg.room_id
                AND rm.member_id = %s AND rm.is_active = 1
            JOIN message_rooms r ON r.id = msg.room_id AND r.is_active = 1
            WHERE msg.created_at > COALESCE(rm.last_read_at, rm.joined_at, r.created_at)
              AND msg.sender_id != %s
              AND msg.is_deleted = 0
              AND msg.is_system = 0
        """, (member_id, member_id))
        row = cursor.fetchone()
        return jsonify({'success': True, 'total_unread': row['total_unread'] if row else 0})
    except Exception as e:
        print(f"[Message] unread_count error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 9: 대화방 나가기
# ============================================
@message_bp.route('/api/message/room/leave', methods=['POST'])
def leave_room():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 방 타입 확인
        cursor.execute("SELECT room_type FROM message_rooms WHERE id=%s", (room_id,))
        room = cursor.fetchone()
        if not room:
            return jsonify({'success': False, 'message': '대화방을 찾을 수 없습니다.'})

        # direct는 나가기 불가 (삭제와 동일)
        if room['room_type'] == 'direct':
            # direct 방은 양쪽 다 비활성화
            cursor.execute("""
                UPDATE message_room_members SET is_active=0
                WHERE room_id=%s AND member_id=%s
            """, (room_id, member_id))
        else:
            my_name = _get_my_name(cursor, member_id, school_id)
            cursor.execute("""
                UPDATE message_room_members SET is_active=0
                WHERE room_id=%s AND member_id=%s
            """, (room_id, member_id))
            _system_message(cursor, room_id, f'{my_name}님이 대화방을 나갔습니다.')

            # 남은 활성 멤버 확인
            cursor.execute("""
                SELECT COUNT(*) AS cnt FROM message_room_members
                WHERE room_id=%s AND is_active=1
            """, (room_id,))
            remaining = cursor.fetchone()
            if remaining and remaining['cnt'] == 0:
                cursor.execute("UPDATE message_rooms SET is_active=0 WHERE id=%s", (room_id,))

        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"[Message] leave_room error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 10: 멤버 초대 (그룹방만, admin만)
# ============================================
@message_bp.route('/api/message/room/invite', methods=['POST'])
def invite_members():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    room_id = data.get('room_id')
    target_ids = data.get('target_ids', [])

    if not room_id or not target_ids:
        return jsonify({'success': False, 'message': 'room_id와 target_ids가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # admin 확인
        mem = _is_room_member(cursor, room_id, member_id)
        if not mem or not mem['is_admin']:
            return jsonify({'success': False, 'message': '관리자만 초대할 수 있습니다.'}), 403

        # 방 타입 확인
        cursor.execute("SELECT room_type, school_id FROM message_rooms WHERE id=%s", (room_id,))
        room = cursor.fetchone()
        if not room or room['room_type'] == 'direct':
            return jsonify({'success': False, 'message': '1:1 대화방에는 초대할 수 없습니다.'})

        # 대상 사용자 확인
        fmt = ','.join(['%s'] * len(target_ids))
        cursor.execute(f"""
            SELECT member_id, member_name, member_role, class_grade, class_no
            FROM message_users WHERE school_id=%s AND member_id IN ({fmt})
        """, [school_id] + target_ids)
        valid_users = {r['member_id']: r for r in cursor.fetchall()}

        my_name = _get_my_name(cursor, member_id, school_id)
        invited = []
        for tid in target_ids:
            if tid not in valid_users:
                continue
            u = valid_users[tid]
            # 이미 멤버인지 확인
            cursor.execute("""
                SELECT id, is_active FROM message_room_members
                WHERE room_id=%s AND member_id=%s
            """, (room_id, tid))
            existing = cursor.fetchone()
            if existing:
                if not existing['is_active']:
                    cursor.execute("""
                        UPDATE message_room_members SET is_active=1, joined_at=NOW()
                        WHERE id=%s
                    """, (existing['id'],))
                    invited.append(u['member_name'])
            else:
                cursor.execute("""
                    INSERT INTO message_room_members
                    (room_id, member_id, member_name, member_role, class_grade, class_no, is_admin)
                    VALUES (%s,%s,%s,%s,%s,%s,0)
                """, (room_id, tid, u['member_name'], u['member_role'],
                      u.get('class_grade'), u.get('class_no')))
                invited.append(u['member_name'])

        if invited:
            names = ', '.join(invited)
            _system_message(cursor, room_id, f'{my_name}님이 {names}님을 초대했습니다.')

        conn.commit()
        return jsonify({'success': True, 'invited_count': len(invited)})
    except Exception as e:
        conn.rollback()
        print(f"[Message] invite_members error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 11: 방 설정 변경 (admin만)
# ============================================
@message_bp.route('/api/message/room/setting', methods=['POST'])
def room_setting():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    data = request.get_json(silent=True) or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        mem = _is_room_member(cursor, room_id, member_id)
        if not mem or not mem['is_admin']:
            return jsonify({'success': False, 'message': '관리자만 설정을 변경할 수 있습니다.'}), 403

        updates = []
        params = []

        if 'room_title' in data:
            updates.append("room_title = %s")
            params.append(sanitize_input(data['room_title'], 100))
        if 'announcement_only' in data:
            updates.append("announcement_only = %s")
            params.append(1 if data['announcement_only'] else 0)

        if updates:
            params.append(room_id)
            cursor.execute(f"UPDATE message_rooms SET {', '.join(updates)} WHERE id=%s", params)
            conn.commit()

        return jsonify({'success': True})
    except Exception as e:
        print(f"[Message] room_setting error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 12: 파일 다운로드
# ============================================
@message_bp.route('/api/message/file/download', methods=['GET'])
def download_file():
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    message_id = request.args.get('message_id')
    if not message_id:
        return jsonify({'success': False, 'message': 'message_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 메시지 조회
        cursor.execute("""
            SELECT m.file_path, m.file_name, m.room_id
            FROM messages m WHERE m.id=%s AND m.is_deleted=0
        """, (message_id,))
        msg = cursor.fetchone()
        if not msg or not msg['file_path']:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'}), 404

        # 방 멤버 확인
        if not _is_room_member(cursor, msg['room_id'], member_id):
            return jsonify({'success': False, 'message': '접근 권한이 없습니다.'}), 403

        from routes.subject_utils import sftp_download_file
        file_data = sftp_download_file(msg['file_path'])
        if not file_data:
            return jsonify({'success': False, 'message': '파일을 찾을 수 없습니다.'}), 404

        response = make_response(file_data)
        fname = msg['file_name'] or 'download'
        ext = fname.rsplit('.', 1)[1].lower() if '.' in fname else ''
        # MIME 타입 설정
        mime_map = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp', 'pdf': 'application/pdf',
            'doc': 'application/msword', 'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'hwp': 'application/x-hwp', 'hwpx': 'application/x-hwpx',
            'xls': 'application/vnd.ms-excel', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'ppt': 'application/vnd.ms-powerpoint', 'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'txt': 'text/plain', 'zip': 'application/zip',
        }
        response.headers['Content-Type'] = mime_map.get(ext, 'application/octet-stream')
        # RFC 5987 한글 파일명 지원
        encoded_fname = quote(fname)
        response.headers['Content-Disposition'] = f"attachment; filename=\"{encoded_fname}\"; filename*=UTF-8''{encoded_fname}"
        return response
    except Exception as e:
        print(f"[Message] download_file error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 12-B: 독립 파일 업로드 (파일만 전송)
# ============================================
@message_bp.route('/api/message/file/upload', methods=['POST'])
def upload_file():
    """파일 첨부 전용 API — 파일을 업로드하고 메시지를 생성"""
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    room_id = request.form.get('room_id')
    uploaded_file = request.files.get('file')
    content = request.form.get('content', '').strip()

    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'success': False, 'message': '파일을 선택해주세요.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()

        # 멤버/방 확인
        mem = _is_room_member(cursor, room_id, member_id)
        if not mem:
            return jsonify({'success': False, 'message': '대화방 접근 권한이 없습니다.'}), 403

        # 공지방 체크
        cursor.execute("SELECT announcement_only FROM message_rooms WHERE id=%s", (room_id,))
        room = cursor.fetchone()
        if room and room['announcement_only'] and not mem['is_admin']:
            return jsonify({'success': False, 'message': '공지 전용 대화방에서는 관리자만 파일을 보낼 수 있습니다.'})

        safe_fname = _secure_filename_korean(uploaded_file.filename)
        ext = safe_fname.rsplit('.', 1)[1].lower() if '.' in safe_fname else ''

        # 확장자 검증 (학생은 이미지만)
        if role == 'student':
            if ext not in ALLOWED_IMAGE_EXT:
                return jsonify({'success': False, 'message': '학생은 이미지 파일만 첨부할 수 있습니다.'})
        else:
            if ext not in ALLOWED_ALL_EXT:
                return jsonify({'success': False, 'message': '허용되지 않는 파일 형식입니다.'})

        # 파일 크기 검증
        file_data = uploaded_file.read()
        file_size = len(file_data)
        if file_size == 0:
            return jsonify({'success': False, 'message': '빈 파일은 업로드할 수 없습니다.'})
        if file_size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'message': f'파일 크기가 {MAX_FILE_SIZE // (1024*1024)}MB를 초과합니다.'})

        # SFTP 업로드
        from routes.subject_utils import sftp_upload_file
        ts = int(time.time())
        remote_path = f'/data/messages/{school_id}/{room_id}/{ts}_{safe_fname}'

        upload_ok = sftp_upload_file(io.BytesIO(file_data), remote_path)
        if not upload_ok:
            return jsonify({'success': False, 'message': '파일 업로드에 실패했습니다.'})

        # 메시지 생성
        my_name = _get_my_name(cursor, member_id, school_id)
        my_role_enum = role if role in ('teacher', 'student', 'parent') else 'teacher'
        message_type = 'image' if ext in ALLOWED_IMAGE_EXT else 'file'
        content = sanitize_html(content, 5000) if content else f'[파일] {safe_fname}'

        cursor.execute("""
            INSERT INTO messages
            (room_id, sender_id, sender_name, sender_role, content,
             message_type, file_path, file_name)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (room_id, member_id, my_name, my_role_enum,
              content, message_type, remote_path, safe_fname))
        msg_id = cursor.lastrowid

        # 내 last_read_at 갱신
        cursor.execute("""
            UPDATE message_room_members SET last_read_at = NOW()
            WHERE room_id=%s AND member_id=%s
        """, (room_id, member_id))

        conn.commit()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 푸시 알림
        try:
            from utils.push_helper import send_push_to_user
            cursor2 = conn.cursor()
            cursor2.execute("""
                SELECT member_id FROM message_room_members
                WHERE room_id=%s AND member_id != %s AND is_active=1
            """, (room_id, member_id))
            recipients = cursor2.fetchall()
            cursor2.close()

            push_body = f'{safe_fname}'
            for r in recipients:
                try:
                    send_push_to_user(r['member_id'], my_name, push_body, '/highschool/messenger.html')
                except:
                    pass
        except:
            pass

        return jsonify({
            'success': True,
            'message_id': msg_id,
            'file_name': safe_fname,
            'file_size': file_size,
            'message_type': message_type,
            'created_at': now_str
        })
    except Exception as e:
        print(f"[Message] upload_file error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# API 13: 새 메시지 폴링 (효율적)
# ============================================
@message_bp.route('/api/message/poll', methods=['GET'])
def poll_messages():
    """현재 보고 있는 방의 새 메시지만 가져오기 (after_id 기준)"""
    info = _get_session_info()
    if not info:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
    member_id, school_id, role = info

    room_id = request.args.get('room_id')
    after_id = request.args.get('after_id', 0)
    if not room_id:
        return jsonify({'success': False, 'message': 'room_id가 필요합니다.'})

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 실패'}), 500
    try:
        cursor = conn.cursor()
        if not _is_room_member(cursor, room_id, member_id):
            return jsonify({'success': False, 'message': '접근 권한이 없습니다.'}), 403

        cursor.execute("""
            SELECT id, room_id, sender_id, sender_name, sender_role,
                   content, message_type, file_name, is_system, is_deleted, created_at
            FROM messages
            WHERE room_id = %s AND id > %s AND is_deleted = 0
            ORDER BY created_at ASC
            LIMIT 100
        """, (room_id, after_id))
        msgs = cursor.fetchall()
        for m in msgs:
            m['is_mine'] = (m['sender_id'] == member_id)
            if m.get('created_at'):
                m['created_at'] = str(m['created_at'])

        return jsonify({'success': True, 'messages': msgs})
    except Exception as e:
        print(f"[Message] poll_messages error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
