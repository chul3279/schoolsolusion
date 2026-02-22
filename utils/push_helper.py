"""
SchoolUs 푸시 알림 헬퍼
- 학급 단위 푸시 발송 유틸리티
- routes/push.py의 send 로직을 재사용 가능하게 분리
"""

import json
import os
from pywebpush import webpush, WebPushException
from utils.db import get_db_connection

_VAPID_CONFIG = None

def _load_vapid_config():
    global _VAPID_CONFIG
    if _VAPID_CONFIG is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vapid_keys.json')
        try:
            with open(config_path, 'r') as f:
                _VAPID_CONFIG = json.load(f)
        except Exception as e:
            print(f"[PushHelper] VAPID config load error: {e}")
            _VAPID_CONFIG = {}
    return _VAPID_CONFIG


def send_push_to_class(school_id, class_grade, class_no, title, body, url='/', target_roles=None):
    """
    학급 단위 푸시 알림 발송.

    Args:
        school_id: 학교 ID
        class_grade: 학년
        class_no: 반
        title: 알림 제목
        body: 알림 내용
        url: 클릭 시 이동할 URL
        target_roles: list of roles ['student', 'parent', 'teacher'] or None=전체

    Returns:
        dict: {'sent': int, 'failed': int, 'expired': int}
    """
    result = {'sent': 0, 'failed': 0, 'expired': 0}

    conn = get_db_connection()
    if not conn:
        return result

    try:
        cursor = conn.cursor()
        subscriptions = []

        roles = target_roles or ['student', 'parent', 'teacher']

        if 'student' in roles:
            # 해당 학급 학생의 구독 조회
            cursor.execute("""
                SELECT ps.endpoint, ps.p256dh, ps.auth
                FROM push_subscriptions ps
                JOIN stu_all sa ON ps.member_id = sa.member_id AND ps.school_id = sa.school_id
                WHERE ps.school_id = %s AND ps.user_role = 'student'
                  AND sa.class_grade = %s AND sa.class_no = %s
            """, (school_id, class_grade, class_no))
            subscriptions.extend(cursor.fetchall())

        if 'parent' in roles:
            # 해당 학급 학생의 학부모 구독 조회
            cursor.execute("""
                SELECT ps.endpoint, ps.p256dh, ps.auth
                FROM push_subscriptions ps
                JOIN fm_all fa ON ps.member_id = fa.member_id AND ps.school_id = fa.school_id
                WHERE ps.school_id = %s AND ps.user_role = 'parent'
                  AND fa.class_grade = %s AND fa.class_no = %s
            """, (school_id, class_grade, class_no))
            subscriptions.extend(cursor.fetchall())

        if 'teacher' in roles:
            # 해당 학급 담임 구독 조회
            cursor.execute("""
                SELECT ps.endpoint, ps.p256dh, ps.auth
                FROM push_subscriptions ps
                JOIN tea_all ta ON ps.member_id = ta.member_id AND ps.school_id = ta.school_id
                WHERE ps.school_id = %s AND ps.user_role = 'teacher'
                  AND ta.class_grade = %s AND ta.class_no = %s
            """, (school_id, class_grade, class_no))
            subscriptions.extend(cursor.fetchall())

        if not subscriptions:
            return result

        config = _load_vapid_config()
        private_key_path = config.get('private_key_path', '')
        claims_email = config.get('claims_email', 'mailto:admin@schoolwithus.co.kr')

        payload = json.dumps({
            'title': title,
            'body': body,
            'icon': '/static/icons/icon-192x192.png',
            'url': url
        })

        expired_endpoints = []

        # 중복 endpoint 제거
        seen = set()
        unique_subs = []
        for sub in subscriptions:
            if sub['endpoint'] not in seen:
                seen.add(sub['endpoint'])
                unique_subs.append(sub)

        for sub in unique_subs:
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub['endpoint'],
                        'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth']}
                    },
                    data=payload,
                    vapid_private_key=private_key_path,
                    vapid_claims={"sub": claims_email}
                )
                result['sent'] += 1
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    expired_endpoints.append(sub['endpoint'])
                else:
                    print(f"[PushHelper] Send error: {e}")
                result['failed'] += 1
            except Exception as e:
                print(f"[PushHelper] Send error: {e}")
                result['failed'] += 1

        # 만료된 구독 정리
        if expired_endpoints:
            format_str = ','.join(['%s'] * len(expired_endpoints))
            cursor.execute(f"DELETE FROM push_subscriptions WHERE endpoint IN ({format_str})", expired_endpoints)
            conn.commit()
            result['expired'] = len(expired_endpoints)

        return result
    except Exception as e:
        print(f"[PushHelper] Error: {e}")
        return result
    finally:
        cursor.close()
        conn.close()


def send_push_to_student(school_id, student_id, title, body, url='/'):
    """
    특정 학생 + 학부모에게 푸시 발송 (상담 일정 등 개인 알림용).
    """
    result = {'sent': 0, 'failed': 0, 'expired': 0}

    conn = get_db_connection()
    if not conn:
        return result

    try:
        cursor = conn.cursor()

        # 학생 본인 구독
        cursor.execute("""
            SELECT endpoint, p256dh, auth FROM push_subscriptions
            WHERE school_id = %s AND member_id = %s
        """, (school_id, student_id))
        subscriptions = list(cursor.fetchall())

        # 학부모 구독 (fm_all에서 자녀 매칭)
        cursor.execute("""
            SELECT ps.endpoint, ps.p256dh, ps.auth
            FROM push_subscriptions ps
            JOIN fm_all fa ON ps.member_id = fa.member_id AND ps.school_id = fa.school_id
            JOIN stu_all sa ON fa.school_id = sa.school_id
                AND fa.child_name = sa.member_name AND fa.class_grade = sa.class_grade
                AND fa.class_no = sa.class_no
            WHERE sa.member_id = %s AND ps.school_id = %s AND ps.user_role = 'parent'
        """, (student_id, school_id))
        subscriptions.extend(cursor.fetchall())

        if not subscriptions:
            return result

        config = _load_vapid_config()
        private_key_path = config.get('private_key_path', '')
        claims_email = config.get('claims_email', 'mailto:admin@schoolwithus.co.kr')

        payload = json.dumps({
            'title': title,
            'body': body,
            'icon': '/static/icons/icon-192x192.png',
            'url': url
        })

        expired_endpoints = []
        seen = set()

        for sub in subscriptions:
            if sub['endpoint'] in seen:
                continue
            seen.add(sub['endpoint'])
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub['endpoint'],
                        'keys': {'p256dh': sub['p256dh'], 'auth': sub['auth']}
                    },
                    data=payload,
                    vapid_private_key=private_key_path,
                    vapid_claims={"sub": claims_email}
                )
                result['sent'] += 1
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    expired_endpoints.append(sub['endpoint'])
                else:
                    print(f"[PushHelper] Send error: {e}")
                result['failed'] += 1
            except Exception as e:
                print(f"[PushHelper] Send error: {e}")
                result['failed'] += 1

        if expired_endpoints:
            format_str = ','.join(['%s'] * len(expired_endpoints))
            cursor.execute(f"DELETE FROM push_subscriptions WHERE endpoint IN ({format_str})", expired_endpoints)
            conn.commit()
            result['expired'] = len(expired_endpoints)

        return result
    except Exception as e:
        print(f"[PushHelper] Error: {e}")
        return result
    finally:
        cursor.close()
        conn.close()
