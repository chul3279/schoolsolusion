from flask import Flask, session, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import secrets
import time
import traceback
from utils.db import get_db_connection

# ============================================
# Flask 앱 생성
# ============================================
app = Flask(__name__)

# ============================================
# Secret Key 관리 (재부팅 후에도 세션 유지)
# ============================================
def get_or_create_secret_key():
    """secret_key를 파일에 저장하여 재부팅 후에도 유지"""
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.secret_key')

    env_key = os.environ.get('FLASK_SECRET_KEY')
    if env_key:
        return env_key

    if os.path.exists(key_file):
        try:
            with open(key_file, 'r') as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception as e:
            print(f"Secret key 파일 읽기 오류: {e}")

    key = secrets.token_hex(32)
    try:
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
        print(f"새 secret_key 생성 완료: {key_file}")
    except Exception as e:
        print(f"Secret key 파일 저장 오류: {e}")

    return key

app.secret_key = get_or_create_secret_key()

# ============================================
# [보안] 세션 쿠키 보안 플래그
# ============================================
app.config['SESSION_COOKIE_SECURE'] = True       # HTTPS에서만 쿠키 전송
app.config['SESSION_COOKIE_HTTPONLY'] = True      # JS에서 쿠키 접근 차단
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'    # 외부 사이트 POST 요청 시 쿠키 미전송 (CSRF 방어)

CORS(app, origins=['https://www.schoolwithus.co.kr', 'https://schoolwithus.co.kr', 'https://schoolwithus.kr', 'https://www.schoolwithus.kr'])


# ============================================
# 보안 미들웨어 (취약점 1~6번 통합 해결)
# ============================================
# 긴급 비활성화: SCHOOLUS_SECURITY=false 환경변수 설정 후 재시작
SECURITY_ENABLED = os.environ.get('SCHOOLUS_SECURITY', 'true').lower() != 'false'

if SECURITY_ENABLED:
    print("[SECURITY] 보안 미들웨어 활성화됨")
else:
    print("[SECURITY] 보안 미들웨어 비활성화됨 (SCHOOLUS_SECURITY=false)")

# ── 인증 없이 접근 가능한 API ──
# 로그인/가입/결제콜백 등 비인증 필수 경로
AUTH_WHITELIST = {
    '/api/signup',              # 회원가입
    '/api/schools',             # 학교목록 (가입 시 사용)
    '/api/push/vapid-key',      # PWA 푸시 VAPID 공개키 (인증 불필요)
    '/api/find-id',             # 아이디 찾기 (비인증)
    '/api/find-password',       # 비밀번호 찾기 (비인증)
    '/api/academies',           # 학원 목록 (강사 가입 시 사용)
}

AUTH_WHITELIST_PREFIXES = (
    '/api/payment/',            # 결제 웹훅/콜백 (외부 PG사 호출)
)

# ── 교사 전용 API (학생/학부모 접근 차단) ──
_TEACHER_ONLY_APIS = {
    # 홈룸
    '/api/homeroom/counsel-schedule/create',
    '/api/homeroom/counsel-schedule/update',
    '/api/homeroom/counsel-schedule/delete',
    '/api/homeroom/counsel-log/create',
    '/api/homeroom/counsel-log/update',
    '/api/homeroom/counsel-log/delete',
    '/api/homeroom/notice/create',
    '/api/homeroom/notice/update',
    '/api/homeroom/notice/delete',
    '/api/homeroom/common-activity/create',
    '/api/homeroom/common-activity/delete',
    '/api/homeroom/student-record/save',
    '/api/homeroom/generate-record',
    # 교과
    '/api/subject/common/create',
    '/api/subject/common/delete',
    '/api/subject/base/save',
    '/api/subject/write/save',
    '/api/subject/generate',
    '/api/subject/file/upload',
    '/api/subject/file/delete',
    '/api/subject/assignment/create',
    '/api/subject/assignment/delete',
    # 동아리
    '/api/club/create',
    '/api/club/delete',
    '/api/club/student/add',
    '/api/club/base/save',
    '/api/club/write/save',
    '/api/club/common/create',
    '/api/club/common/delete',
    '/api/club/generate',
    '/api/club/file/upload',
    '/api/club/file/delete',
    '/api/club/authorize',
    '/api/club/unauthorize',
    # 시간표 관리
    '/api/timetable/class/save-manual',
    '/api/timetable/teacher/save-manual',
    '/api/timetable/change/save',
    '/api/timetable/change/delete',
    '/api/timetable-tea/save',
    '/api/timetable-data/save',
    '/api/timetable-stu/save',
    '/api/timetable-survey/save',
    '/api/timetable-data/update-stu-count',
    # 학급편성, 입시
    '/api/class-maker/save',
    '/api/class-maker/delete',
}

# ── 원장 전용 API (강사/학생/학부모 접근 차단) ──
_DIRECTOR_ONLY_APIS = {
    '/api/academy/create',
    '/api/academy/update',
    '/api/academy/instructor/approve',
    '/api/academy/class/create',
    '/api/academy/class/update',
    '/api/academy/class/delete',
    '/api/academy/student/register',
}

# ── 브루트포스 방어 설정 (DB 기반) ──
_BRUTE_MAX_ATTEMPTS = 5         # login_id당 최대 실패 횟수
_BRUTE_WINDOW_SEC = 600         # 10분 잠금


def _get_client_ip():
    """프록시(nginx/envoy) 뒤 실제 클라이언트 IP 추출"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.headers.get('X-Real-IP', request.remote_addr)


def _extract_school_id():
    """요청에서 school_id 추출 (GET → JSON → Form 순서)"""
    try:
        sid = request.args.get('school_id')
        if sid:
            return str(sid).strip()

        if request.is_json:
            data = request.get_json(silent=True)
            if data and data.get('school_id'):
                return str(data['school_id']).strip()

        sid = request.form.get('school_id')
        if sid:
            return str(sid).strip()
    except Exception:
        pass
    return None




@app.before_request
def security_middleware():
    """
    전역 보안 미들웨어
    - /api/* 경로: 세션 인증 + school_id 검증
    - /login_process: 브루트포스 방어 (IP당 10회/5분)
    - 오류 발생 시 요청 차단 안 함 (fail-open, 서비스 우선)
    """
    if not SECURITY_ENABLED:
        return None

    try:
        path = request.path
        method = request.method

        # OPTIONS (CORS preflight) 무조건 통과
        if method == 'OPTIONS':
            return None

        # ── 브루트포스 방어: /login_process (DB 기반, 계정별 잠금) ──
        if path == '/login_process' and method == 'POST':
            try:
                data = request.get_json(silent=True)
                login_id = (data.get('login_id', '') if data else '').strip()
                if login_id:
                    bf_conn = get_db_connection()
                    if bf_conn:
                        try:
                            bf_cursor = bf_conn.cursor()
                            bf_cursor.execute(
                                "SELECT COUNT(*) as cnt FROM login_attempts "
                                "WHERE login_id = %s AND attempted_at > DATE_SUB(NOW(), INTERVAL %s SECOND)",
                                (login_id, _BRUTE_WINDOW_SEC)
                            )
                            row = bf_cursor.fetchone()
                            if row and row['cnt'] >= _BRUTE_MAX_ATTEMPTS:
                                ip = _get_client_ip()
                                print(f"[SECURITY] 브루트포스 차단: login_id={login_id}, IP={ip}, 실패={row['cnt']}회")
                                return jsonify({
                                    'success': False,
                                    'message': '로그인 시도 횟수를 초과했습니다. 10분 후 다시 시도해주세요.'
                                }), 429
                        finally:
                            if bf_cursor: bf_cursor.close()
                            bf_conn.close()
            except Exception as e:
                print(f"[SECURITY] 브루트포스 체크 오류 (요청 허용): {e}")
            return None

        # ── /api/ 경로가 아니면 통과 (HTML, 정적파일, /login_process 등) ──
        if not path.startswith('/api/'):
            return None

        # ── 화이트리스트 체크 (회원가입, 학교목록, 결제 등) ──
        if path in AUTH_WHITELIST:
            return None
        for prefix in AUTH_WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return None

        # ── [취약점 1~4] 세션 인증 체크 ──
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '로그인이 필요합니다.'
            }), 401

        # ── [취약점 5] school_id 횡적 권한 상승 방지 ──
        req_school = _extract_school_id()
        sess_school = session.get('school_id')
        if req_school and sess_school and req_school != str(sess_school):
            print(f"[SECURITY] 타학교 접근 차단: user={session.get('user_id')}, "
                  f"session={sess_school}, request={req_school}, path={path}")
            return jsonify({
                'success': False,
                'message': '권한이 없습니다.'
            }), 403

        # ── [취약점 6] 역할 기반 접근 제어 (교사 전용 API) ──
        if path in _TEACHER_ONLY_APIS:
            if session.get('user_role') != 'teacher':
                print(f"[SECURITY] 비교사 접근 차단: user={session.get('user_id')}, "
                      f"role={session.get('user_role')}, path={path}")
                return jsonify({
                    'success': False,
                    'message': '교사만 사용할 수 있습니다.'
                }), 403

        # ── 역할 기반 접근 제어 (원장 전용 API) ──
        if path in _DIRECTOR_ONLY_APIS:
            if session.get('user_role') != 'director':
                print(f"[SECURITY] 비원장 접근 차단: user={session.get('user_id')}, "
                      f"role={session.get('user_role')}, path={path}")
                return jsonify({
                    'success': False,
                    'message': '원장만 사용할 수 있습니다.'
                }), 403

        # ── 학교/학원 교차 접근 차단 ──
        user_role = session.get('user_role', '')
        _SCHOOL_API_PREFIXES = ('/api/homeroom/', '/api/subject/', '/api/club/',
                                '/api/timetable', '/api/class-maker/',
                                '/api/counsel/', '/api/schedule/')
        _ACADEMY_API_PREFIX = '/api/academy/'

        if any(path.startswith(p) for p in _SCHOOL_API_PREFIXES):
            if user_role not in ('teacher', 'student', 'parent'):
                print(f"[SECURITY] 비학교역할 학교API 차단: user={session.get('user_id')}, "
                      f"role={user_role}, path={path}")
                return jsonify({
                    'success': False,
                    'message': '권한이 없습니다.'
                }), 403

        if path.startswith(_ACADEMY_API_PREFIX):
            if user_role not in ('director', 'instructor'):
                print(f"[SECURITY] 비학원역할 학원API 차단: user={session.get('user_id')}, "
                      f"role={user_role}, path={path}")
                return jsonify({
                    'success': False,
                    'message': '권한이 없습니다.'
                }), 403

        # ── [취약점 7] IDOR 방어: 학생/학부모는 본인 데이터만 조회 ──
        user_role = session.get('user_role')
        if user_role in ('student', 'parent'):
            req_student_id = request.args.get('student_id')
            if not req_student_id and request.is_json:
                json_data = request.get_json(silent=True)
                if json_data:
                    req_student_id = json_data.get('student_id')

            if req_student_id:
                sess_user_id = session.get('user_id')
                if user_role == 'student' and req_student_id != sess_user_id:
                    print(f"[SECURITY] IDOR 차단(학생): user={sess_user_id}, "
                          f"target={req_student_id}, path={path}")
                    return jsonify({
                        'success': False,
                        'message': '본인 정보만 조회할 수 있습니다.'
                    }), 403
                elif user_role == 'parent':
                    # 학부모: 세션에 저장된 자녀 ID 목록과 대조
                    allowed_children = session.get('children_ids', [])
                    if req_student_id not in allowed_children and req_student_id != sess_user_id:
                        print(f"[SECURITY] IDOR 차단(학부모): user={sess_user_id}, "
                              f"target={req_student_id}, allowed={allowed_children}, path={path}")
                        return jsonify({
                            'success': False,
                            'message': '본인 자녀 정보만 조회할 수 있습니다.'
                        }), 403

        return None

    except Exception as e:
        # ★ 핵심 안전장치: 미들웨어 오류 시 요청을 차단하지 않음
        print(f"[SECURITY] 미들웨어 오류 (요청 허용됨): {e}")
        traceback.print_exc()
        return None


@app.after_request
def security_after_request(response):
    """로그인 브루트포스 관리 (보안 헤더는 nginx에서 일괄 처리)"""
    if not SECURITY_ENABLED:
        return response
    try:
        if request.path == '/login_process' and request.method == 'POST':
            login_data = request.get_json(silent=True)
            login_id = (login_data.get('login_id', '') if login_data else '').strip()
            if not login_id:
                return response

            resp_data = response.get_json(silent=True)
            is_success = (response.status_code == 200 and resp_data and resp_data.get('success'))

            bf_conn = get_db_connection()
            if bf_conn:
                try:
                    bf_cursor = bf_conn.cursor()
                    if is_success:
                        # 로그인 성공 → 실패 기록 초기화
                        bf_cursor.execute("DELETE FROM login_attempts WHERE login_id = %s", (login_id,))
                    else:
                        # 로그인 실패 → 기록 추가
                        ip = _get_client_ip()
                        bf_cursor.execute(
                            "INSERT INTO login_attempts (login_id, ip_address, attempted_at) VALUES (%s, %s, NOW())",
                            (login_id, ip)
                        )
                        # 10분 지난 오래된 기록 정리
                        bf_cursor.execute(
                            "DELETE FROM login_attempts WHERE attempted_at < DATE_SUB(NOW(), INTERVAL %s SECOND)",
                            (_BRUTE_WINDOW_SEC * 2,)
                        )
                    bf_conn.commit()
                finally:
                    if bf_cursor: bf_cursor.close()
                    bf_conn.close()
    except Exception as e:
        print(f"[SECURITY] after_request 브루트포스 오류: {e}")
    return response


# ============================================
# Blueprint 등록
# ============================================
from routes.auth import auth_bp
from routes.teacher import teacher_bp
from routes.student import student_bp
from routes.parent import parent_bp
from routes.payment import payment_bp
from routes.notice import notice_bp
from routes.schedule import schedule_bp
from routes.meal import meal_bp
from routes.timetable import timetable_bp
from routes.homeroom import homeroom_bp
from routes.homeroom_record import homeroom_record_bp
from routes.homeroom_gen import homeroom_gen_bp
from routes.support import support_bp
from routes.admission import admission_bp
from routes.subject import subject_bp
from routes.club import club_bp
from routes.assignment import assignment_bp
from routes.class_maker import class_maker_bp
from routes.push import push_bp
from routes.academy import academy_bp

app.register_blueprint(auth_bp)
app.register_blueprint(teacher_bp)
app.register_blueprint(student_bp)
app.register_blueprint(parent_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(notice_bp)
app.register_blueprint(schedule_bp)
app.register_blueprint(meal_bp)
app.register_blueprint(timetable_bp)
app.register_blueprint(homeroom_bp)
app.register_blueprint(homeroom_record_bp)
app.register_blueprint(homeroom_gen_bp)
app.register_blueprint(support_bp)
app.register_blueprint(admission_bp)
app.register_blueprint(subject_bp)
app.register_blueprint(club_bp)
app.register_blueprint(assignment_bp)
app.register_blueprint(class_maker_bp)
app.register_blueprint(push_bp)
app.register_blueprint(academy_bp)


# ============================================
# 학원 페이지 접근 제어 (nginx에서 프록시)
# ============================================
@app.route('/academy/director.html')
def serve_director_page():
    if session.get('user_role') != 'director':
        return '접근 권한이 없습니다.', 403
    return send_from_directory(os.path.join(app.root_path, 'academy'), 'director.html')

@app.route('/academy/instructor.html')
def serve_instructor_page():
    if session.get('user_role') not in ('director', 'instructor'):
        return '접근 권한이 없습니다.', 403
    return send_from_directory(os.path.join(app.root_path, 'academy'), 'instructor.html')


# ============================================
# 서버 실행
# ============================================
if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)