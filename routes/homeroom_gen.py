from flask import Blueprint, request, jsonify
from utils.db import get_db_connection, sanitize_input, sanitize_html
from routes.subject_utils import check_and_deduct_point, AI_POINT_COST
import time
import re
import itertools
import requests as http_requests

homeroom_gen_bp = Blueprint('homeroom_gen', __name__)

# ============================================
# Gemini API 설정 (5키 로테이션)
# ============================================
from config.gemini_keys import GEMINI_API_KEYS
_gemini_key_cycle = itertools.cycle(GEMINI_API_KEYS)
GEMINI_MODEL = 'gemini-2.5-flash'
GEMINI_TEMPERATURE = 0.3


# ============================================
# 생기부 작성 데이터 조회 API
# ============================================
@homeroom_gen_bp.route('/api/homeroom/school-record-gen/get', methods=['GET'])
def get_school_record_gen():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        student_id = sanitize_input(request.args.get('student_id'), 50)
        record_year = sanitize_input(request.args.get('record_year'), 10)
        record_semester = sanitize_input(request.args.get('record_semester'), 5)

        if not school_id or not student_id or not record_year:
            return jsonify({'success': False, 'message': '필수 파라미터가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, curriculum_type, behavior, autonomous, career, volunteer,
                   behavior_byte_limit, autonomous_byte_limit, career_byte_limit, volunteer_byte_limit,
                   status, created_at, updated_at
            FROM school_record_generated
            WHERE school_id = %s AND student_id = %s AND record_year = %s AND record_semester = %s
        """, (school_id, student_id, record_year, record_semester))

        row = cursor.fetchone()

        if row:
            return jsonify({
                'success': True, 'exists': True,
                'record': {
                    'id': row['id'], 'curriculum_type': row['curriculum_type'],
                    'behavior': row['behavior'] or '', 'autonomous': row['autonomous'] or '',
                    'career': row['career'] or '', 'volunteer': row['volunteer'] or '',
                    'behavior_byte_limit': row['behavior_byte_limit'] or 1500,
                    'autonomous_byte_limit': row['autonomous_byte_limit'] or 1500,
                    'career_byte_limit': row['career_byte_limit'] or 2100,
                    'volunteer_byte_limit': row['volunteer_byte_limit'] or 500,
                    'status': row['status'],
                    'updated_at': row['updated_at'].strftime('%Y-%m-%d %H:%M') if row['updated_at'] else ''
                }
            })
        else:
            return jsonify({'success': True, 'exists': False})

    except Exception as e:
        print(f"생기부 조회 오류: {e}")
        return jsonify({'success': False, 'message': '생기부 데이터 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 생기부 작성 데이터 저장 API
# ============================================
@homeroom_gen_bp.route('/api/homeroom/school-record-gen/save', methods=['POST'])
def save_school_record_gen():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        student_id = sanitize_input(data.get('student_id'), 50)
        record_year = data.get('record_year')
        record_semester = data.get('record_semester', 1)
        curriculum_type = sanitize_input(data.get('curriculum_type', '2015'), 10)
        status = sanitize_input(data.get('status', 'draft'), 20)

        behavior = data.get('behavior', '')
        autonomous = data.get('autonomous', '')
        career = data.get('career', '')
        volunteer = data.get('volunteer', '')

        behavior_byte_limit = data.get('behavior_byte_limit', 1500)
        autonomous_byte_limit = data.get('autonomous_byte_limit', 1500)
        career_byte_limit = data.get('career_byte_limit', 2100)
        volunteer_byte_limit = data.get('volunteer_byte_limit', 500)

        if not school_id or not student_id or not record_year:
            return jsonify({'success': False, 'message': '필수 파라미터가 누락되었습니다.'})
        if status not in ('draft', 'complete'):
            return jsonify({'success': False, 'message': '유효하지 않은 상태값입니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO school_record_generated
                (school_id, student_id, record_year, record_semester, curriculum_type,
                 behavior, autonomous, career, volunteer,
                 behavior_byte_limit, autonomous_byte_limit, career_byte_limit, volunteer_byte_limit, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                curriculum_type = VALUES(curriculum_type),
                behavior = VALUES(behavior), autonomous = VALUES(autonomous),
                career = VALUES(career), volunteer = VALUES(volunteer),
                behavior_byte_limit = VALUES(behavior_byte_limit), autonomous_byte_limit = VALUES(autonomous_byte_limit),
                career_byte_limit = VALUES(career_byte_limit), volunteer_byte_limit = VALUES(volunteer_byte_limit),
                status = VALUES(status), updated_at = CURRENT_TIMESTAMP
        """, (school_id, student_id, record_year, record_semester, curriculum_type,
              behavior, autonomous, career, volunteer,
              behavior_byte_limit, autonomous_byte_limit, career_byte_limit, volunteer_byte_limit, status))

        conn.commit()
        status_text = '임시저장' if status == 'draft' else '작성완료'
        return jsonify({'success': True, 'message': f'{status_text}되었습니다.', 'status': status})

    except Exception as e:
        if conn: conn.rollback()
        print(f"생기부 저장 오류: {e}")
        return jsonify({'success': False, 'message': '생기부 저장 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 생기부 AI 생성 (Gemini API - 5키 순환)
# ============================================
def _calc_neis_bytes(text):
    total = 0
    for ch in text:
        total += 3 if ord(ch) > 127 else 1
    return total


def _bytes_to_chars(b):
    return max(50, int(b / 3))


def _byte_instruction(b):
    chars = max(50, int(b / 3))
    min_chars = int(chars * 0.85)
    return f"한글 기준 {min_chars}~{chars}자 작성. {min_chars}자 미만은 불합격. 구체적 사례와 에피소드를 충분히 서술하여 분량을 채울 것"


def _resummarize(original_text, max_bytes, tag_name):
    target_chars = max(30, int(max_bytes / 3) - 10)
    re_prompt = f"""아래는 학교생활기록부 '{tag_name}' 항목의 초안입니다.
현재 바이트 수가 제한({max_bytes}바이트)을 초과했습니다.
내용의 핵심을 모두 유지하면서 {target_chars}자 이내로 압축해주세요.

[필수 규칙]
- 문장 종결은 반드시 ~함, ~임, ~음 등 명사형 어미 사용
- 학생 실명 사용 금지
- 핵심 사실과 구체적 사례는 반드시 보존
- 불필요한 수식어와 중복 표현만 제거
- {target_chars}자를 절대 초과하지 마세요

[원문]
{original_text}

위 내용을 압축하여 작성해주세요. 태그 없이 본문만 출력하세요."""

    re_api_key = next(_gemini_key_cycle)
    re_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={re_api_key}"
    re_payload = {
        'contents': [{'parts': [{'text': re_prompt}]}],
        'generationConfig': {'temperature': GEMINI_TEMPERATURE, 'maxOutputTokens': 4096, 'thinkingConfig': {'thinkingBudget': 1024}},
        'safetySettings': [
            {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
            {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
        ]
    }

    try:
        re_response = http_requests.post(re_url, json=re_payload, timeout=60)
        if re_response.status_code == 200:
            re_result = re_response.json()

            # ===== Gemini 비용 측정 로깅 (재요약) =====
            _ru = re_result.get('usageMetadata', {})
            _rp = _ru.get('promptTokenCount', 0)
            _rc = _ru.get('candidatesTokenCount', 0)
            _rt = _ru.get('thoughtsTokenCount', 0)
            _rtot = _ru.get('totalTokenCount', 0)
            _ric = _rp * 0.30 / 1_000_000
            _roc = (_rc + _rt) * 2.50 / 1_000_000
            _rtu = _ric + _roc
            _rtk = _rtu * 1450
            with open('/tmp/gemini_cost.log', 'a') as _cf:
                _cf.write(f"[{__import__('datetime').datetime.now()}] [생기부-재요약] tag={tag_name} | "
                          f"input={_rp}tok(${_ric:.5f}) | "
                          f"output={_rc}tok+think={_rt}tok(${_roc:.5f}) | "
                          f"total={_rtot}tok | "
                          f"비용=${_rtu:.5f}({_rtk:.1f}원)\n")
            # ===== 비용 측정 로깅 끝 =====

            re_parts = re_result['candidates'][0]['content']['parts']
            re_text = ''.join(p.get('text', '') for p in re_parts if not p.get('thought', False)).strip()
            if _calc_neis_bytes(re_text) > max_bytes:
                sentences = re.split(r'(?<=\.)\s*', re_text)
                trimmed = ''
                for s in sentences:
                    candidate = (trimmed + ' ' + s).strip() if trimmed else s
                    if _calc_neis_bytes(candidate) > max_bytes:
                        break
                    trimmed = candidate
                return trimmed if trimmed else re_text[:target_chars]
            return re_text
        else:
            print(f"재요약 Gemini 오류 ({tag_name}): HTTP {re_response.status_code} - {re_response.text[:300]}")
    except Exception as e:
        print(f"재요약 요청 오류 ({tag_name}): {e}")

    return original_text


# ============================================
# 생기부 삭제 API
# ============================================
@homeroom_gen_bp.route('/api/homeroom/school-record-gen/delete', methods=['POST'])
def delete_school_record_gen():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        student_id = sanitize_input(data.get('student_id'), 50)
        record_year = sanitize_input(str(data.get('record_year', '')), 10)
        record_semester = sanitize_input(str(data.get('record_semester', '')), 5)

        if not school_id or not student_id or not record_year:
            return jsonify({'success': False, 'message': '필수 파라미터가 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM school_record_generated
            WHERE school_id = %s AND student_id = %s AND record_year = %s AND record_semester = %s
        """, (school_id, student_id, record_year, record_semester))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': '생기부 데이터가 삭제되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '삭제할 데이터가 없습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"생기부 삭제 오류: {e}")
        return jsonify({'success': False, 'message': '생기부 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


WRITING_RULES = """
[필수 작성 규칙 - 교육부 학교생활기록부 기재요령 준수]

1. 문체 규칙
   - 반드시 3인칭 시점으로 작성 (1인칭/2인칭 사용 금지)
   - 문장 종결은 명사형 어미 사용: ~함, ~임, ~음, ~됨, ~보임, ~있음, ~보여줌, ~증명함, ~갖춤, ~발휘함, ~돋보임, ~이끌어냄
   - 종결어미를 다양하게 활용하여 단조로운 반복을 피할 것
   - 절대 ~습니다, ~했다, ~이다 같은 종결어미 사용 금지
   - 한글 표기 원칙: DNA, RNA, SNS를 제외한 모든 영어는 반드시 한글로 변환하여 작성. 괄호 안에도 영어 병기 절대 금지
     예시) 크리스퍼 → O, CRISPR-Cas9 → X / 맥스웰 방정식 → O, Maxwell's equations → X / 파이썬 → O, Python → X

2. 학생 지칭 규칙
   - 학생 실명을 절대 사용하지 않음
   - '해당 학생은', '동 학생은', '이 학생은' 등의 지칭어도 사용 금지
   - 반드시 주어를 생략하고 바로 서술

3. 서술 구조 패턴 (핵심)
   - 반드시 다음 4단계 흐름으로 서술: 관심/계기 → 자기주도적 탐구 과정 → 구체적 결과물/성과 → 역량/태도 평가
   - 각 문장은 "구체적 행동 묘사 + 역량/태도 평가어"로 마무리
     예시) "오차 발생 원인을 pH 농도와 온도 변화 등 다각도로 분석하여 재실험을 수행하는 학업적 끈기를 보임"
   - 3~4문장이 시간/논리 순서로 자연스러운 서사 흐름을 유지할 것 (나열식 서술 금지)
   - 활동 나열이 아닌, 하나의 활동을 깊이 있게 서술한 뒤 다음 활동으로 이어갈 것

4. 문장 연결 및 수식어 규칙
   - 문장 간 자연스러운 연결 표현 활용: "~하고 ~하여", "특히", "이를 바탕으로", "~한 후", "~하는 등"
   - 심화 전환 표현 적극 활용: "단순히 ~에 그치지 않고", "~을 넘어" 등으로 표면적 활동에서 깊이 있는 행동으로의 전환을 드러낼 것
   - 활동의 지속성과 성실성을 보여주는 구체적 수치/빈도/기간 명시 (예: "주 1회 꾸준히", "1년간 장기 프로젝트")
   - 역량을 드러내는 부사 적극 사용: "주도적으로", "비판적으로", "다각도로", "꾸준히", "깊이", "체계적으로"
   - 역량을 드러내는 수식어 적극 사용: "뛰어난", "탁월한", "수준 높은", "높은 이해도", "부드러운 리더십"
   - 전문 용어나 활동명은 괄호로 보충하여 구체성 확보
     예시) "전염병 확산 모델(SIR 모델)에 미분 방정식을 적용하여"

5. 기재 금지 사항 (위반 시 생기부 기재 오류)
   - 학교명, 재단명, 학교축제명, 학교별칭 등 학교를 알 수 있는 내용 일체
   - 부모(친인척 포함)의 사회·경제적 지위 암시 내용
   - 사교육(학원, 과외 등) 관련 내용
   - 소논문(R&E, 연구보고서) 관련 내용
   - 교외 수상, 교외 인증시험 점수, 모의고사 성적 등
   - 특정 대학명 언급
   - 단순 사실을 과장하거나 부풀려서 기재
   - 사실과 다른 내용을 허위로 기재

6. 우수한 생기부 작성 원칙
   - 제공된 기초자료, 상담일지, 첨부파일, 공통활동에 없는 내용은 절대 창작하지 말고, 주어진 팩트를 기반으로만 서술
   - 추상적 표현 대신 구체적인 활동 사례와 행동 근거를 제시
   - 학생 개인만의 고유한 강점과 특성이 드러나도록 작성
   - 단순 활동 나열이 아닌, 활동 과정에서의 태도·역할·성장·변화를 서술
   - 인성 관련 핵심 가치·덕목의 변화를 구체적 근거와 함께 서술
   - 학업역량, 진로역량, 공동체역량 관점에서 학생을 평가
   - 장점 위주로 작성하되, 단점 기재 시 반드시 변화 가능성·개선 노력을 함께 기술
   - 학업적 끈기, 자기주도적 학습 능력, 갈등 조정 능력, 지적 호기심, 발전 가능성 등 핵심 역량이 드러나도록 서술

7. 글자 수 규칙 (최우선 준수사항)
   - 각 항목의 [글자 수]에 명시된 최소 글자 수 이상 반드시 작성
   - 지정된 최대 글자 수 초과는 금지
"""


@homeroom_gen_bp.route('/api/homeroom/generate-record', methods=['POST'])
def generate_school_record():
    try:
        data = request.get_json()
        member_id = sanitize_input(data.get('member_id'), 50)
        school_id = sanitize_input(data.get('school_id'), 50)
        student_id = sanitize_input(data.get('student_id'), 50)
        student_name = data.get('student_name', '')
        class_grade = data.get('class_grade', '')
        class_no = data.get('class_no', '')
        base_data = sanitize_html(data.get('base_data', ''))
        counsel_logs = data.get('counsel_logs', [])
        counsel_files = data.get('counsel_files', [])
        common_activities = data.get('common_activities', [])
        curriculum_type = data.get('curriculum_type', '2015')
        byte_limits = data.get('byte_limits', {})

        # 학년-교육과정 자동 보정 (3학년=2015, 1~2학년=2022)
        try:
            grade_num = int(class_grade) if class_grade else 0
            if grade_num >= 3 and curriculum_type == '2022':
                curriculum_type = '2015'
            elif 1 <= grade_num <= 2 and curriculum_type == '2015':
                curriculum_type = '2022'
        except (ValueError, TypeError):
            pass

        if not member_id:
            return jsonify({'success': False, 'message': '교사 정보가 누락되었습니다.'})

        # 포인트 차감 / 권한 확인
        success, msg, new_point = check_and_deduct_point(
            member_id, AI_POINT_COST, 'homeroom_record',
            school_id=school_id, student_id=student_id
        )
        if not success:
            return jsonify({'success': False, 'message': msg, 'point_error': True})

        counsel_text = ''
        if counsel_logs:
            counsel_text = '\n'.join([
                f"- [{log.get('date','')}] {log.get('type','')}: {log.get('content','')} (결과: {log.get('result','')})"
                for log in counsel_logs])

        common_text = ''
        if common_activities:
            common_text = '\n'.join([
                f"- [{act.get('date','')}] {act.get('type','')}: {act.get('title','')} - {act.get('content','')}"
                for act in common_activities])

        files_text = ''
        if counsel_files:
            files_text = '\n'.join([f"- {f.get('file_name','')} ({f.get('file_size','')})" for f in counsel_files])

        if curriculum_type == '2022':
            behavior_inst = _byte_instruction(byte_limits.get('행동특성및종합의견', 1500))
            autonomous_inst = _byte_instruction(byte_limits.get('자율자치활동', 1500))
            career_inst = _byte_instruction(byte_limits.get('진로활동', 2100))

            prompt = f"""당신은 대한민국 고등학교에서 20년 이상 근무한 베테랑 담임교사입니다.
학생부종합전형에서 높은 평가를 받는 생활기록부를 작성하는 전문가입니다.
아래 학생의 기초자료, 상담일지, 첨부파일, 학급 공통활동을 바탕으로 2022 개정교육과정에 맞는 생활기록부를 작성해주세요.

[적용 교육과정] 2022 개정교육과정 (고교학점제)
- 대상: 고등학교 1~2학년
- 창의적 체험활동: 자율·자치활동 / 동아리활동 / 진로활동 (3영역)
- 봉사활동은 독립 영역이 아니며, 행동특성 및 종합의견에 포함 가능

[학생 정보]
- 이름: {student_name} (작성 시 이름 및 지칭어 사용 금지, 주어 생략하고 바로 서술)
- 학년/반: {class_grade}학년 {class_no}반

[기초자료 - 담임교사 누가기록]
{base_data if base_data else '(등록된 기초자료 없음)'}

[상담일지]
{counsel_text if counsel_text else '(등록된 상담일지 없음)'}

[학급 공통활동]
{common_text if common_text else '(등록된 공통활동 없음)'}

[첨부파일]
{files_text if files_text else '(첨부된 파일 없음)'}
※ 파일명에서 활동 내용이나 상담 주제를 유추하여 참고하세요.

{WRITING_RULES}

아래 3가지 항목을 각각 작성해주세요. 반드시 해당 XML 태그로 감싸서 응답하세요.
태그 외의 설명이나 부연은 절대 작성하지 마세요.

<행동특성및종합의견>
[역할] 담임교사가 수시로 관찰한 누가기록을 바탕으로, 학생을 총체적으로 이해할 수 있는 추천서 성격의 종합의견 작성
[포함 요소] 성격·인성, 학습태도·학업역량(자기주도적 학습 능력, 학업적 끈기), 교우관계·공동체역량(갈등 조정 능력, 협력), 공통활동 참여 태도, 봉사활동, 성장과 변화
[서술 방법] 구체적 행동 사례를 근거로 역량을 평가하되, 마지막 문장은 반드시 "앞으로의 발전 가능성이 기대되는" 등 미래지향적 총평으로 마무리할 것
[글자 수] {behavior_inst}
</행동특성및종합의견>

<자율자치활동>
[역할] 자율·자치활동 특기사항 (담임교사 입력 항목)
[포함 요소] 학급임원 활동(재임기간), 자치회·학생회 활동, 학교행사 참여, 주제탐구 활동, 공통활동 반영
[서술 방법] 구체적 기획 과정(문제 인식 → 아이디어 도출 → 실행)과 실질적 변화/성과를 중심으로 서술. 리더십은 "타인을 배려하고 협력을 유도하는" 등 구체적 행동으로 표현할 것
[글자 수] {autonomous_inst}
</자율자치활동>

<진로활동>
[역할] 진로활동 특기사항 (담임교사 입력 항목)
[포함 요소] 진로탐색, 진로설계·실천, 진로체험, 진로상담 결과, 검사결과 활용, 자기주도적 탐색
[서술 방법] 탐구 깊이를 보여줄 것(특강/수업 참여 → 개인 심화 탐구 → 관련 자료 탐독 → 자기 견해 형성/에세이 작성). 진로에 대한 열정과 자기주도적 탐색 의지가 구체적 행동으로 드러나도록 서술
[글자 수] {career_inst}
</진로활동>
"""
            tag_list = ['행동특성및종합의견', '자율자치활동', '진로활동']

        else:
            behavior_inst = _byte_instruction(byte_limits.get('행동특성및종합의견', 1500))
            autonomous_inst = _byte_instruction(byte_limits.get('자율활동', 1500))
            career_inst = _byte_instruction(byte_limits.get('진로활동', 2100))
            volunteer_inst = _byte_instruction(byte_limits.get('봉사활동', 500))

            prompt = f"""당신은 대한민국 고등학교에서 20년 이상 근무한 베테랑 담임교사입니다.
학생부종합전형에서 높은 평가를 받는 생활기록부를 작성하는 전문가입니다.
아래 학생의 기초자료, 상담일지, 첨부파일, 학급 공통활동을 바탕으로 2015 개정교육과정에 맞는 생활기록부를 작성해주세요.

[적용 교육과정] 2015 개정교육과정
- 대상: 고등학교 3학년
- 창의적 체험활동: 자율활동 / 동아리활동 / 봉사활동 / 진로활동 (4영역)

[학생 정보]
- 이름: {student_name} (작성 시 이름 및 지칭어 사용 금지, 주어 생략하고 바로 서술)
- 학년/반: {class_grade}학년 {class_no}반

[기초자료 - 담임교사 누가기록]
{base_data if base_data else '(등록된 기초자료 없음)'}

[상담일지]
{counsel_text if counsel_text else '(등록된 상담일지 없음)'}

[학급 공통활동]
{common_text if common_text else '(등록된 공통활동 없음)'}

[첨부파일]
{files_text if files_text else '(첨부된 파일 없음)'}
※ 파일명에서 활동 내용이나 상담 주제를 유추하여 참고하세요.

{WRITING_RULES}

아래 4가지 항목을 모두 빠짐없이 작성해주세요. 반드시 해당 XML 태그로 감싸서 응답하세요.
태그 외의 설명이나 부연은 절대 작성하지 마세요.
[중요] 4개 항목 전부 작성 필수입니다. 봉사활동 포함 어떤 항목도 생략하지 마세요.
[중요] 2015 교육과정 태그명을 정확히 사용하세요: 자율활동 (자율자치활동 X)

<행동특성및종합의견>
[역할] 담임교사가 수시로 관찰한 누가기록을 바탕으로, 학생을 총체적으로 이해할 수 있는 추천서 성격의 종합의견 작성
[포함 요소] 성격·인성, 학습태도·학업역량(자기주도적 학습 능력, 학업적 끈기), 교우관계·공동체역량(갈등 조정 능력, 협력), 공통활동 참여 태도, 성장과 변화, 3학년 진로의지
[서술 방법] 구체적 행동 사례를 근거로 역량을 평가하되, 마지막 문장은 반드시 "앞으로의 발전 가능성이 기대되는" 등 미래지향적 총평으로 마무리할 것
[글자 수] {behavior_inst}
</행동특성및종합의견>

<자율활동>
[역할] 자율활동 특기사항 (담임교사 입력 항목)
[포함 요소] 학급임원 활동(재임기간), 자치·적응 활동, 창의주제 활동, 학교행사 참여, 공통활동 반영
[서술 방법] 구체적 기획 과정(문제 인식 → 아이디어 도출 → 실행)과 실질적 변화/성과를 중심으로 서술. 리더십은 "타인을 배려하고 협력을 유도하는" 등 구체적 행동으로 표현할 것
[글자 수] {autonomous_inst}
</자율활동>

<진로활동>
[역할] 진로활동 특기사항 (담임교사 입력 항목)
[포함 요소] 진로탐색, 진로설계·실천, 진로체험, 진로상담 결과, 검사결과 활용, 3학년 대입 준비 태도
[서술 방법] 탐구 깊이를 보여줄 것(특강/수업 참여 → 개인 심화 탐구 → 관련 자료 탐독 → 자기 견해 형성/에세이 작성). 진로에 대한 열정과 자기주도적 탐색 의지가 구체적 행동으로 드러나도록 서술
[글자 수] {career_inst}
</진로활동>

<봉사활동>
[역할] 봉사활동 참여 내역과 태도 서술 (독립 영역)
[포함 요소] 학교교육계획 봉사활동, 태도·역할·책임감, 인식 변화나 성장, 나눔과 배려 사례
[서술 방법] 단순 참여 나열이 아닌, 봉사 과정에서의 태도 변화와 인식 성장을 구체적 에피소드로 서술할 것. 봉사활동 관련 기초자료가 부족하더라도 학교교육계획에 따른 교내 봉사활동 참여를 기본으로 반드시 작성할 것
[글자 수] {volunteer_inst}
[중요] 이 영역은 반드시 작성해야 합니다. 비워두지 마세요.
</봉사활동>
"""
            tag_list = ['행동특성및종합의견', '자율활동', '진로활동', '봉사활동']

        # Gemini API 호출 (5키 순환 + 429 재시도)
        response = None
        max_retries = 5
        for attempt in range(max_retries):
            api_key = next(_gemini_key_cycle)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
            payload = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'temperature': GEMINI_TEMPERATURE, 'maxOutputTokens': 65536, 'thinkingConfig': {'thinkingBudget': 8192}},
                'safetySettings': [
                    {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'threshold': 'BLOCK_NONE'},
                    {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'threshold': 'BLOCK_NONE'}
                ]
            }
            response = http_requests.post(url, json=payload, timeout=120)
            if response.status_code == 429:
                print(f"Gemini 429 (키: ...{api_key[-6:]}), {attempt+1}/{max_retries} 재시도")
                time.sleep(5 * (attempt + 1))
                continue
            break

        if response.status_code != 200:
            print(f"Gemini API 오류: {response.status_code} - {response.text}")
            return jsonify({'success': False, 'message': f'AI 서비스 오류 ({response.status_code}). 잠시 후 다시 시도해주세요.', 'new_point': new_point})

        result = response.json()

        # ===== Gemini 비용 측정 로깅 =====
        _usage = result.get('usageMetadata', {})
        _prompt_tok = _usage.get('promptTokenCount', 0)
        _cand_tok = _usage.get('candidatesTokenCount', 0)
        _thoughts_tok = _usage.get('thoughtsTokenCount', 0)
        _total_tok = _usage.get('totalTokenCount', 0)
        _in_cost = _prompt_tok * 0.30 / 1_000_000
        _out_cost = (_cand_tok + _thoughts_tok) * 2.50 / 1_000_000
        _total_usd = _in_cost + _out_cost
        _total_krw = _total_usd * 1450
        with open('/tmp/gemini_cost.log', 'a') as _cf:
            _cf.write(f"[{__import__('datetime').datetime.now()}] [생기부] student={student_id} | "
                      f"input={_prompt_tok}tok(${_in_cost:.5f}) | "
                      f"output={_cand_tok}tok+think={_thoughts_tok}tok(${_out_cost:.5f}) | "
                      f"total={_total_tok}tok | "
                      f"비용=${_total_usd:.5f}({_total_krw:.1f}원)\n")
        # ===== 비용 측정 로깅 끝 =====

        ai_text = ''
        try:
            parts = result['candidates'][0]['content']['parts']
            for part in parts:
                if part.get('thought', False):
                    continue
                if 'text' in part:
                    ai_text += part['text']
            if not ai_text:
                for part in parts:
                    if 'text' in part:
                        ai_text += part['text']
        except (KeyError, IndexError):
            return jsonify({'success': False, 'message': 'AI 응답을 파싱할 수 없습니다.', 'new_point': new_point})

        print(f"[생기부 AI] 응답 길이: {len(ai_text)}자, 태그 포함여부: {[t for t in tag_list if f'<{t}>' in ai_text]}")

        def extract_tag(text, tag_name):
            pattern = f'<{tag_name}>(.*?)</{tag_name}>'
            match = re.search(pattern, text, re.DOTALL)
            return match.group(1).strip() if match else ''

        # 태그 별칭: Gemini가 2015/2022 태그를 혼용하는 경우 폴백
        TAG_ALIASES = {
            '자율활동': ['자율자치활동', '자율·자치활동'],
            '자율자치활동': ['자율활동', '자율·자치활동'],
        }

        parsed_result = {}
        has_any = False
        for tag in tag_list:
            content = extract_tag(ai_text, tag)
            if not content and tag in TAG_ALIASES:
                for alias in TAG_ALIASES[tag]:
                    content = extract_tag(ai_text, alias)
                    if content:
                        print(f"[생기부 AI] 태그 폴백: <{tag}> → <{alias}>")
                        break
            tag_byte_limit = byte_limits.get(tag, 1500)
            if content and _calc_neis_bytes(content) > tag_byte_limit:
                print(f"바이트 초과 감지 [{tag}]: {_calc_neis_bytes(content)}B > {tag_byte_limit}B → 재요약 요청")
                content = _resummarize(content, tag_byte_limit, tag)
            parsed_result[tag] = content
            if content:
                has_any = True

        if not has_any:
            parsed_result[tag_list[0]] = ai_text

        return jsonify({
            'success': True,
            'result': parsed_result,
            'new_point': new_point,
            'point_used': AI_POINT_COST
        })

    except http_requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'AI 서비스 응답 시간이 초과되었습니다. 다시 시도해주세요.'})
    except Exception as e:
        print(f"생기부 생성 오류: {e}")
        return jsonify({'success': False, 'message': '생기부 생성 중 오류가 발생했습니다.'})