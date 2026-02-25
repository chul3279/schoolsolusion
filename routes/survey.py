"""
SchoolUs 설문조사 API
- /api/survey/list: 설문 목록 (교사용)
- /api/survey/create: 설문 생성 (draft)
- /api/survey/detail: 설문 상세 + 문항
- /api/survey/update: 설문 수정 (draft만)
- /api/survey/delete: 설문 삭제 (draft만)
- /api/survey/start: 설문 개시 (draft → active)
- /api/survey/close: 설문 종료 (active → closed)
- /api/survey/respond: 학생/학부모 응답 제출
- /api/survey/my-surveys: 내 대상 설문 목록 (학생/학부모용)
- /api/survey/stats: 설문 통계
"""

from flask import Blueprint, request, jsonify, session
from utils.db import get_db_connection, sanitize_input, sanitize_html
import json

survey_bp = Blueprint('survey', __name__)


# ============================================
# 설문 목록 (교사용)
# ============================================
@survey_bp.route('/api/survey/list', methods=['GET'])
def list_surveys():
    conn = None
    cursor = None
    try:
        school_id = session.get('school_id') or sanitize_input(request.args.get('school_id'), 50)
        status_filter = sanitize_input(request.args.get('status'), 20)

        if not school_id:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        query = """
            SELECT s.*,
                   (SELECT COUNT(*) FROM survey_response sr WHERE sr.survey_id = s.id) AS response_count,
                   (SELECT COUNT(*) FROM survey_question sq WHERE sq.survey_id = s.id) AS question_count
            FROM survey s
            WHERE s.school_id = %s
        """
        params = [school_id]

        if status_filter:
            query += " AND s.status = %s"
            params.append(status_filter)

        query += " ORDER BY s.created_at DESC"
        cursor.execute(query, params)
        surveys = cursor.fetchall()

        result = []
        for s in surveys:
            result.append({
                'id': s['id'],
                'title': s['title'],
                'description': s.get('description') or '',
                'target_role': s['target_role'],
                'target_grades': s['target_grades'],
                'status': s['status'],
                'created_by': s['created_by'],
                'response_count': int(s['response_count'] or 0),
                'question_count': int(s['question_count'] or 0),
                'started_at': s['started_at'].strftime('%Y-%m-%d %H:%M') if s.get('started_at') else '',
                'closed_at': s['closed_at'].strftime('%Y-%m-%d %H:%M') if s.get('closed_at') else '',
                'created_at': s['created_at'].strftime('%Y-%m-%d %H:%M') if s.get('created_at') else ''
            })

        return jsonify({'success': True, 'surveys': result})

    except Exception as e:
        print(f"설문 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': '설문 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 생성 (draft)
# ============================================
@survey_bp.route('/api/survey/create', methods=['POST'])
def create_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = session.get('school_id') or sanitize_input(data.get('school_id'), 50)
        title = sanitize_html(data.get('title', ''), 200)
        description = sanitize_html(data.get('description', ''), 2000)
        target_role = sanitize_input(data.get('target_role', 'student'), 20)
        target_grades = sanitize_input(data.get('target_grades', 'all'), 50)
        questions = data.get('questions', [])
        created_by = session.get('user_id')

        if not school_id or not title:
            return jsonify({'success': False, 'message': '제목을 입력해주세요.'})

        if target_role not in ('student', 'parent', 'both'):
            return jsonify({'success': False, 'message': '대상을 선택해주세요.'})

        if not questions:
            return jsonify({'success': False, 'message': '최소 1개 이상의 문항을 추가해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()
        conn.begin()

        cursor.execute("""
            INSERT INTO survey (school_id, title, description, target_role, target_grades, status, created_by)
            VALUES (%s, %s, %s, %s, %s, 'draft', %s)
        """, (school_id, title, description, target_role, target_grades, created_by))
        survey_id = cursor.lastrowid

        for i, q in enumerate(questions):
            q_text = sanitize_html(q.get('question_text') or q.get('question') or q.get('text') or '', 1000)
            q_type = sanitize_input(q.get('question_type') or q.get('type') or 'single', 20)
            q_required = 1 if q.get('required', True) else 0
            q_options = q.get('options')

            # 타입 매핑 (choice→single 등)
            type_map = {'choice': 'single', 'radio': 'single', 'checkbox': 'multiple', 'select': 'single', 'textarea': 'text', 'star': 'rating', 'scale': 'rating'}
            q_type = type_map.get(q_type, q_type)
            if q_type not in ('single', 'multiple', 'text', 'rating'):
                q_type = 'single'

            cursor.execute("""
                INSERT INTO survey_question (survey_id, question_order, question_text, question_type, options, required)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (survey_id, i + 1, q_text, q_type,
                  json.dumps(q_options, ensure_ascii=False) if q_options else None, q_required))

        conn.commit()
        return jsonify({'success': True, 'message': '설문이 생성되었습니다.', 'survey_id': survey_id})

    except Exception as e:
        print(f"설문 생성 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '설문 생성 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 상세 + 문항 조회
# ============================================
@survey_bp.route('/api/survey/detail', methods=['GET'])
def get_survey_detail():
    conn = None
    cursor = None
    try:
        survey_id = sanitize_input(request.args.get('id'), 20)
        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})

        cursor.execute("SELECT * FROM survey_question WHERE survey_id = %s ORDER BY question_order", (survey_id,))
        questions = []
        for q in cursor.fetchall():
            opts = q['options']
            if isinstance(opts, str):
                opts = json.loads(opts)
            questions.append({
                'id': q['id'],
                'question_order': q['question_order'],
                'question_text': q['question_text'],
                'question_type': q['question_type'],
                'options': opts,
                'required': bool(q['required'])
            })

        return jsonify({
            'success': True,
            'survey': {
                'id': s['id'],
                'title': s['title'],
                'description': s.get('description') or '',
                'target_role': s['target_role'],
                'target_grades': s['target_grades'],
                'status': s['status'],
                'created_by': s['created_by'],
                'started_at': s['started_at'].strftime('%Y-%m-%d %H:%M') if s.get('started_at') else '',
                'closed_at': s['closed_at'].strftime('%Y-%m-%d %H:%M') if s.get('closed_at') else '',
                'created_at': s['created_at'].strftime('%Y-%m-%d %H:%M') if s.get('created_at') else ''
            },
            'questions': questions
        })

    except Exception as e:
        print(f"설문 상세 조회 오류: {e}")
        return jsonify({'success': False, 'message': '설문 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 수정 (draft만)
# ============================================
@survey_bp.route('/api/survey/update', methods=['POST'])
def update_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        survey_id = sanitize_input(data.get('id'), 20)
        title = sanitize_html(data.get('title', ''), 200)
        description = sanitize_html(data.get('description', ''), 2000)
        target_role = sanitize_input(data.get('target_role', 'student'), 20)
        target_grades = sanitize_input(data.get('target_grades', 'all'), 50)
        questions = data.get('questions', [])

        if not survey_id or not title:
            return jsonify({'success': False, 'message': '필수 항목을 입력해주세요.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status, created_by FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})
        if s['status'] != 'draft':
            return jsonify({'success': False, 'message': '임시저장 상태의 설문만 수정할 수 있습니다.'})

        conn.begin()

        cursor.execute("""
            UPDATE survey SET title=%s, description=%s, target_role=%s, target_grades=%s
            WHERE id=%s
        """, (title, description, target_role, target_grades, survey_id))

        # 기존 문항 삭제 후 재생성
        cursor.execute("DELETE FROM survey_question WHERE survey_id = %s", (survey_id,))

        for i, q in enumerate(questions):
            q_text = sanitize_html(q.get('question_text') or q.get('question') or q.get('text') or '', 1000)
            q_type = sanitize_input(q.get('question_type') or q.get('type') or 'single', 20)
            q_required = 1 if q.get('required', True) else 0
            q_options = q.get('options')

            type_map = {'choice': 'single', 'radio': 'single', 'checkbox': 'multiple', 'select': 'single', 'textarea': 'text', 'star': 'rating', 'scale': 'rating'}
            q_type = type_map.get(q_type, q_type)
            if q_type not in ('single', 'multiple', 'text', 'rating'):
                q_type = 'single'

            cursor.execute("""
                INSERT INTO survey_question (survey_id, question_order, question_text, question_type, options, required)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (survey_id, i + 1, q_text, q_type,
                  json.dumps(q_options, ensure_ascii=False) if q_options else None, q_required))

        conn.commit()
        return jsonify({'success': True, 'message': '설문이 수정되었습니다.'})

    except Exception as e:
        print(f"설문 수정 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '설문 수정 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 삭제 (draft만)
# ============================================
@survey_bp.route('/api/survey/delete', methods=['POST'])
def delete_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        survey_id = sanitize_input(data.get('id'), 20)

        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})
        if s['status'] == 'active':
            return jsonify({'success': False, 'message': '진행 중인 설문은 삭제할 수 없습니다. 먼저 종료해주세요.'})

        cursor.execute("DELETE FROM survey WHERE id = %s", (survey_id,))

        return jsonify({'success': True, 'message': '설문이 삭제되었습니다.'})

    except Exception as e:
        print(f"설문 삭제 오류: {e}")
        return jsonify({'success': False, 'message': '설문 삭제 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 개시 (draft → active)
# ============================================
@survey_bp.route('/api/survey/start', methods=['POST'])
def start_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        survey_id = sanitize_input(data.get('id'), 20)

        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})
        if s['status'] != 'draft':
            return jsonify({'success': False, 'message': '임시저장 상태의 설문만 개시할 수 있습니다.'})

        cursor.execute("UPDATE survey SET status='active', started_at=NOW() WHERE id=%s", (survey_id,))

        return jsonify({'success': True, 'message': '설문이 개시되었습니다.'})

    except Exception as e:
        print(f"설문 개시 오류: {e}")
        return jsonify({'success': False, 'message': '설문 개시 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 종료 (active → closed)
# ============================================
@survey_bp.route('/api/survey/close', methods=['POST'])
def close_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        survey_id = sanitize_input(data.get('id'), 20)

        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT status FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})
        if s['status'] != 'active':
            return jsonify({'success': False, 'message': '진행 중인 설문만 종료할 수 있습니다.'})

        cursor.execute("UPDATE survey SET status='closed', closed_at=NOW() WHERE id=%s", (survey_id,))

        return jsonify({'success': True, 'message': '설문이 종료되었습니다.'})

    except Exception as e:
        print(f"설문 종료 오류: {e}")
        return jsonify({'success': False, 'message': '설문 종료 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생/학부모 응답 제출
# ============================================
@survey_bp.route('/api/survey/respond', methods=['POST'])
def respond_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        survey_id = sanitize_input(data.get('survey_id'), 20)
        answers = data.get('answers', [])
        user_id = session.get('user_id')
        user_role = session.get('user_role')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})
        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 설문 검증
        cursor.execute("SELECT * FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})
        if s['status'] != 'active':
            return jsonify({'success': False, 'message': '현재 응답 가능한 설문이 아닙니다.'})

        # 대상 검증
        if s['target_role'] == 'student' and user_role != 'student':
            return jsonify({'success': False, 'message': '학생만 응답할 수 있는 설문입니다.'})
        if s['target_role'] == 'parent' and user_role != 'parent':
            return jsonify({'success': False, 'message': '학부모만 응답할 수 있는 설문입니다.'})
        if s['target_role'] == 'both' and user_role not in ('student', 'parent'):
            return jsonify({'success': False, 'message': '학생 또는 학부모만 응답할 수 있습니다.'})

        # 학년 검증
        if s['target_grades'] != 'all':
            allowed_grades = [g.strip() for g in s['target_grades'].split(',')]
            user_grade = session.get('class_grade', '')
            if user_grade not in allowed_grades:
                return jsonify({'success': False, 'message': '대상 학년이 아닙니다.'})

        # 중복 응답 확인
        cursor.execute("SELECT id FROM survey_response WHERE survey_id=%s AND respondent_id=%s", (survey_id, user_id))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '이미 응답한 설문입니다.'})

        # 설문의 문항 목록을 미리 조회 (question_id 검증용)
        cursor.execute("SELECT id, question_order FROM survey_question WHERE survey_id = %s", (survey_id,))
        q_rows = cursor.fetchall()
        valid_qids = {str(q['id']) for q in q_rows}
        order_to_id = {str(q['question_order']): str(q['id']) for q in q_rows}

        conn.begin()

        cursor.execute("""
            INSERT INTO survey_response (survey_id, respondent_id, respondent_role)
            VALUES (%s, %s, %s)
        """, (survey_id, user_id, user_role))
        response_id = cursor.lastrowid

        saved_count = 0
        for ans in answers:
            question_id = sanitize_input(str(ans.get('question_id', '')), 20)
            answer_value = sanitize_html(str(ans.get('answer_value', '') or ''), 2000)
            if not question_id:
                continue
            # question_id가 유효한 DB ID가 아니면 question_order로 매핑 시도
            if question_id not in valid_qids:
                mapped = order_to_id.get(question_id, question_id)
                if mapped != question_id:
                    question_id = mapped
                else:
                    # 순서 기반 매핑도 실패 → 인덱스로 시도 (1-based)
                    idx_based = order_to_id.get(str(answers.index(ans) + 1))
                    if idx_based:
                        question_id = idx_based
            if question_id in valid_qids:
                cursor.execute("""
                    INSERT INTO survey_answer (response_id, question_id, answer_value)
                    VALUES (%s, %s, %s)
                """, (response_id, question_id, answer_value))
                saved_count += 1
            else:
                print(f"[survey] 응답 저장 건너뜀: question_id={question_id}, valid={valid_qids}, order_map={order_to_id}")

        if saved_count == 0 and len(answers) > 0:
            print(f"[survey] 경고: {len(answers)}개 답변 중 0개 저장됨! survey_id={survey_id}, response_id={response_id}")

        conn.commit()
        return jsonify({'success': True, 'message': '응답이 제출되었습니다.'})

    except Exception as e:
        print(f"설문 응답 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': '응답 제출 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 내 대상 설문 목록 (학생/학부모용)
# ============================================
@survey_bp.route('/api/survey/my-surveys', methods=['GET'])
def my_surveys():
    conn = None
    cursor = None
    try:
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        school_id = session.get('school_id')
        user_grade = session.get('class_grade', '')

        if not user_id:
            return jsonify({'success': False, 'message': '로그인이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s.*,
                   (SELECT COUNT(*) FROM survey_question sq WHERE sq.survey_id = s.id) AS question_count,
                   (SELECT id FROM survey_response sr WHERE sr.survey_id = s.id AND sr.respondent_id = %s) AS my_response_id
            FROM survey s
            WHERE s.school_id = %s AND s.status = 'active'
              AND (s.target_role = %s OR s.target_role = 'both')
            ORDER BY s.started_at DESC
        """, (user_id, school_id, user_role))

        surveys = []
        for s in cursor.fetchall():
            # 학년 필터
            if s['target_grades'] != 'all':
                allowed = [g.strip() for g in s['target_grades'].split(',')]
                if user_grade not in allowed:
                    continue

            surveys.append({
                'id': s['id'],
                'title': s['title'],
                'description': s.get('description') or '',
                'question_count': int(s['question_count'] or 0),
                'already_responded': s['my_response_id'] is not None,
                'started_at': s['started_at'].strftime('%Y-%m-%d') if s.get('started_at') else ''
            })

        return jsonify({'success': True, 'surveys': surveys})

    except Exception as e:
        print(f"내 설문 목록 오류: {e}")
        return jsonify({'success': False, 'message': '설문 목록 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 설문 통계
# ============================================
@survey_bp.route('/api/survey/stats', methods=['GET'])
@survey_bp.route('/api/survey/results', methods=['GET'])
def survey_stats():
    conn = None
    cursor = None
    try:
        survey_id = sanitize_input(request.args.get('id'), 20)
        if not survey_id:
            return jsonify({'success': False, 'message': '설문 ID가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 설문 기본 정보
        cursor.execute("SELECT * FROM survey WHERE id = %s", (survey_id,))
        s = cursor.fetchone()
        if not s:
            return jsonify({'success': False, 'message': '설문을 찾을 수 없습니다.'})

        # 총 응답 수
        cursor.execute("SELECT COUNT(*) AS cnt FROM survey_response WHERE survey_id = %s", (survey_id,))
        total_responses = int(cursor.fetchone()['cnt'] or 0)

        # 대상 수 계산
        school_id = s['school_id']
        target_count = 0
        if s['target_role'] in ('student', 'both'):
            grade_filter = ""
            grade_params = [school_id]
            if s['target_grades'] != 'all':
                grades = [g.strip() for g in s['target_grades'].split(',')]
                placeholders = ','.join(['%s'] * len(grades))
                grade_filter = f" AND class_grade IN ({placeholders})"
                grade_params.extend(grades)
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM stu_all WHERE school_id = %s{grade_filter}", grade_params)
            target_count += int(cursor.fetchone()['cnt'] or 0)

        if s['target_role'] in ('parent', 'both'):
            grade_filter = ""
            grade_params = [school_id]
            if s['target_grades'] != 'all':
                grades = [g.strip() for g in s['target_grades'].split(',')]
                placeholders = ','.join(['%s'] * len(grades))
                grade_filter = f" AND class_grade IN ({placeholders})"
                grade_params.extend(grades)
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM fm_all WHERE school_id = %s{grade_filter}", grade_params)
            target_count += int(cursor.fetchone()['cnt'] or 0)

        # 문항별 통계
        cursor.execute("SELECT * FROM survey_question WHERE survey_id = %s ORDER BY question_order", (survey_id,))
        questions = cursor.fetchall()

        question_stats = []
        for q in questions:
            opts = q['options']
            if isinstance(opts, str):
                opts = json.loads(opts)

            # 해당 문항의 모든 응답 (survey_id 필터 포함)
            cursor.execute("""
                SELECT sa.answer_value FROM survey_answer sa
                JOIN survey_response sr ON sa.response_id = sr.id AND sr.survey_id = %s
                WHERE sa.question_id = %s
            """, (survey_id, q['id'],))
            raw_answers = [r['answer_value'] or '' for r in cursor.fetchall()]

            stat = {
                'question_id': q['id'],
                'question_order': q['question_order'],
                'question_text': q['question_text'],
                'question_type': q['question_type'],
                'options': opts,
                'required': bool(q['required']),
                'answer_count': len(raw_answers)
            }

            if q['question_type'] in ('single', 'multiple') and opts:
                option_list = opts if isinstance(opts, list) else []
                counts = [0] * len(option_list)
                for ans in raw_answers:
                    if q['question_type'] == 'single':
                        try:
                            idx = int(ans)
                            if 0 <= idx < len(option_list):
                                counts[idx] += 1
                        except (ValueError, TypeError):
                            pass
                    else:  # multiple
                        for part in ans.split(','):
                            try:
                                idx = int(part.strip())
                                if 0 <= idx < len(option_list):
                                    counts[idx] += 1
                            except (ValueError, TypeError):
                                pass
                stat['option_counts'] = counts

            elif q['question_type'] == 'rating':
                values = []
                for ans in raw_answers:
                    try:
                        values.append(int(ans))
                    except (ValueError, TypeError):
                        pass
                stat['average'] = round(sum(values) / len(values), 2) if values else 0
                # 분포
                max_val = (opts or {}).get('max', 5) if isinstance(opts, dict) else 5
                distribution = [0] * max_val
                for v in values:
                    if 1 <= v <= max_val:
                        distribution[v - 1] += 1
                stat['distribution'] = distribution

            elif q['question_type'] == 'text':
                stat['text_answers'] = raw_answers[:200]  # 최대 200개

            question_stats.append(stat)

        return jsonify({
            'success': True,
            'survey': {
                'id': s['id'],
                'title': s['title'],
                'description': s.get('description') or '',
                'target_role': s['target_role'],
                'target_grades': s['target_grades'],
                'status': s['status'],
                'started_at': s['started_at'].strftime('%Y-%m-%d %H:%M') if s.get('started_at') else '',
                'closed_at': s['closed_at'].strftime('%Y-%m-%d %H:%M') if s.get('closed_at') else ''
            },
            'total_responses': total_responses,
            'target_count': target_count,
            'question_stats': question_stats
        })

    except Exception as e:
        print(f"설문 통계 오류: {e}")
        return jsonify({'success': False, 'message': '통계 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
