"""
SchoolUs 푸시 알림 API
- /api/push/vapid-key: VAPID 공개키 반환
- /api/push/subscribe: 구독 등록
- /api/push/unsubscribe: 구독 해제
- /api/push/send: 알림 발송 (교사/관리자 전용)
"""

from flask import Blueprint, request, jsonify, session
import json
import os
from pywebpush import webpush, WebPushException
from utils.db import get_db_connection, sanitize_html

push_bp = Blueprint('push', __name__)

# ============================================
# VAPID 설정 로드
# ============================================
_VAPID_CONFIG = None

def _load_vapid_config():
    global _VAPID_CONFIG
    if _VAPID_CONFIG is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vapid_keys.json')
        try:
            with open(config_path, 'r') as f:
                _VAPID_CONFIG = json.load(f)
        except Exception as e:
            print(f"[Push] VAPID config load error: {e}")
            _VAPID_CONFIG = {}
    return _VAPID_CONFIG


# ============================================
# VAPID 공개키 반환
# ============================================
@push_bp.route('/api/push/vapid-key', methods=['GET'])
def get_vapid_key():
    config = _load_vapid_config()
    public_key = config.get('public_key')
    if not public_key:
        return jsonify({'success': False, 'message': 'VAPID 키가 설정되지 않았습니다.'}), 500
    return jsonify({'success': True, 'public_key': public_key})


# ============================================
# 푸시 구독 등록
# ============================================
@push_bp.route('/api/push/subscribe', methods=['POST'])
def subscribe():
    member_id = session.get('user_id')
    if not member_id:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401

    data = request.get_json(silent=True)
    if not data or 'subscription' not in data:
        return jsonify({'success': False, 'message': '구독 정보가 없습니다.'}), 400

    sub = data['subscription']
    endpoint = sub.get('endpoint', '')
    keys = sub.get('keys', {})
    p256dh = keys.get('p256dh', '')
    auth = keys.get('auth', '')

    if not endpoint or not p256dh or not auth:
        return jsonify({'success': False, 'message': '구독 정보가 유효하지 않습니다.'}), 400

    school_id = session.get('school_id', '')
    user_role = session.get('user_role', '')

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 오류'}), 500

    try:
        cursor = conn.cursor()
        # UPSERT: endpoint 기준으로 중복 시 업데이트
        cursor.execute("""
            INSERT INTO push_subscriptions (member_id, school_id, user_role, endpoint, p256dh, auth)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                member_id = VALUES(member_id),
                school_id = VALUES(school_id),
                user_role = VALUES(user_role),
                p256dh = VALUES(p256dh),
                auth = VALUES(auth),
                updated_at = NOW()
        """, (member_id, school_id, user_role, endpoint, p256dh, auth))
        conn.commit()
        return jsonify({'success': True, 'message': '푸시 알림이 등록되었습니다.'})
    except Exception as e:
        print(f"[Push] Subscribe error: {e}")
        return jsonify({'success': False, 'message': '등록 중 오류가 발생했습니다.'}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# 푸시 구독 해제
# ============================================
@push_bp.route('/api/push/unsubscribe', methods=['POST'])
def unsubscribe():
    data = request.get_json(silent=True)
    endpoint = data.get('endpoint', '') if data else ''

    if not endpoint:
        return jsonify({'success': False, 'message': 'endpoint가 필요합니다.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 오류'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
        conn.commit()
        return jsonify({'success': True, 'message': '구독이 해제되었습니다.'})
    except Exception as e:
        print(f"[Push] Unsubscribe error: {e}")
        return jsonify({'success': False, 'message': '해제 중 오류가 발생했습니다.'}), 500
    finally:
        cursor.close()
        conn.close()


# ============================================
# 푸시 알림 발송 (교사/관리자 전용)
# ============================================
@push_bp.route('/api/push/send', methods=['POST'])
def send_push():
    # 교사만 발송 가능
    if session.get('user_role') != 'teacher':
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': '요청 데이터가 없습니다.'}), 400

    title = sanitize_html(data.get('title', 'SchoolUs 알림'), 200)
    body = sanitize_html(data.get('body', ''), 1000)
    url = data.get('url', '/')
    target_school = data.get('school_id') or session.get('school_id')
    target_role = data.get('target_role')  # 'student', 'parent', 'teacher', None=전체

    if not body:
        return jsonify({'success': False, 'message': '알림 내용을 입력해주세요.'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'DB 연결 오류'}), 500

    try:
        cursor = conn.cursor()

        # 대상 구독자 조회
        query = "SELECT endpoint, p256dh, auth FROM push_subscriptions WHERE school_id = %s"
        params = [target_school]
        if target_role:
            query += " AND user_role = %s"
            params.append(target_role)

        cursor.execute(query, params)
        subscriptions = cursor.fetchall()

        if not subscriptions:
            return jsonify({'success': True, 'message': '발송 대상이 없습니다.', 'sent': 0})

        config = _load_vapid_config()
        private_key_path = config.get('private_key_path', '')
        claims_email = config.get('claims_email', 'mailto:admin@schoolwithus.co.kr')

        payload = json.dumps({
            'title': title,
            'body': body,
            'icon': '/static/icons/icon-192x192.png',
            'url': url
        })

        sent = 0
        failed = 0
        expired_endpoints = []

        for sub in subscriptions:
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub['endpoint'],
                        'keys': {
                            'p256dh': sub['p256dh'],
                            'auth': sub['auth']
                        }
                    },
                    data=payload,
                    vapid_private_key=private_key_path,
                    vapid_claims={"sub": claims_email}
                )
                sent += 1
            except WebPushException as e:
                if e.response and e.response.status_code in (404, 410):
                    # 만료된 구독 → 삭제 예정
                    expired_endpoints.append(sub['endpoint'])
                else:
                    print(f"[Push] Send error: {e}")
                failed += 1
            except Exception as e:
                print(f"[Push] Send error: {e}")
                failed += 1

        # 만료된 구독 정리
        if expired_endpoints:
            format_str = ','.join(['%s'] * len(expired_endpoints))
            cursor.execute(f"DELETE FROM push_subscriptions WHERE endpoint IN ({format_str})", expired_endpoints)
            conn.commit()

        return jsonify({
            'success': True,
            'message': f'{sent}명에게 발송 완료',
            'sent': sent,
            'failed': failed,
            'expired': len(expired_endpoints)
        })
    except Exception as e:
        print(f"[Push] Send error: {e}")
        return jsonify({'success': False, 'message': '발송 중 오류가 발생했습니다.'}), 500
    finally:
        cursor.close()
        conn.close()
