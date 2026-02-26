"""
시간표 파이프라인 API
- 시간표 서버사이드 생성 (Step 7)
- 교육반 배정 (Step 8)
"""
from flask import Blueprint, request, jsonify
from utils.db import get_db_connection, sanitize_input

timetable_pipeline_bp = Blueprint('timetable_pipeline', __name__)


@timetable_pipeline_bp.route('/api/pipeline/check', methods=['POST'])
def check_prerequisites():
    """각 학년별 파이프라인 사전 조건 확인"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id 필요'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        grades_info = {}
        for grade in ['1', '2', '3']:
            info = {'grade': grade, 'ready': True, 'missing': []}

            # 학생 데이터
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM timetable_stu WHERE school_id=%s AND grade=%s",
                (school_id, grade))
            stu_count = cursor.fetchone()['cnt']
            info['students'] = stu_count
            if stu_count == 0:
                info['ready'] = False
                info['missing'].append('학생 데이터')

            # 반편성 확정 여부
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM timetable_stu
                   WHERE school_id=%s AND grade=%s AND class_no IS NOT NULL AND class_no != ''""",
                (school_id, grade))
            assigned = cursor.fetchone()['cnt']
            info['assigned'] = assigned
            if stu_count > 0 and assigned < stu_count:
                info['ready'] = False
                info['missing'].append(f'반편성 ({assigned}/{stu_count}명)')

            # 반 수
            cursor.execute(
                """SELECT COUNT(DISTINCT class_no) as cnt FROM timetable_stu
                   WHERE school_id=%s AND grade=%s AND class_no IS NOT NULL AND class_no != ''""",
                (school_id, grade))
            info['classes'] = cursor.fetchone()['cnt']

            # 교사 편성
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM timetable_tea WHERE school_id=%s AND grade=%s",
                (school_id, grade))
            tea_count = cursor.fetchone()['cnt']
            info['teachers'] = tea_count
            if tea_count == 0:
                info['ready'] = False
                info['missing'].append('교사 편성')

            # 선택과목 존재 여부
            cursor.execute(
                """SELECT COUNT(*) as cnt FROM timetable_data
                   WHERE school_id=%s AND grade=%s AND subject_type='선택'""",
                (school_id, grade))
            info['has_electives'] = cursor.fetchone()['cnt'] > 0

            # 밴드그룹별 교육반 균형 검증
            if info['has_electives']:
                from utils.elective_engine import validate_band_balance
                band_warnings = validate_band_balance(cursor, school_id, grade)
                info['band_warnings'] = [w['message'] for w in band_warnings]
            else:
                info['band_warnings'] = []

            grades_info[grade] = info

        return jsonify({'success': True, 'grades': grades_info})

    except Exception as e:
        print(f"pipeline check 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@timetable_pipeline_bp.route('/api/pipeline/generate', methods=['POST'])
def generate_timetable():
    """시간표 서버사이드 자동 생성"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id 필요'})

        from utils.timetable_engine import (
            load_teachers, load_timetable_data, load_constraints,
            load_fixed_subjects, build_blocks, run_auto_generate, save_timetable
        )

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        teachers = load_teachers(cursor, school_id)
        st_map, sd_map, cd_map = load_timetable_data(cursor, school_id)
        constraints = load_constraints(cursor, school_id)
        fixed_subjects = load_fixed_subjects(cursor, school_id)
        blocks = build_blocks(teachers, st_map, sd_map, cd_map, fixed_subjects)

        if not blocks:
            return jsonify({'success': False, 'message': '생성할 블록이 없습니다. 교사 편성을 확인하세요.'})

        schedule, results, total_placed, total_needed, fixed_count, total_cw = \
            run_auto_generate(blocks, fixed_subjects, constraints, teachers)

        cnt = save_timetable(cursor, school_id, schedule)
        conn.commit()

        pct = round(total_placed / total_needed * 100) if total_needed else 0

        return jsonify({
            'success': True,
            'total_placed': total_placed,
            'total_needed': total_needed,
            'percentage': pct,
            'fixed_count': fixed_count,
            'consecutive_warnings': total_cw,
            'saved_count': cnt,
            'details': results
        })

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"pipeline generate 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@timetable_pipeline_bp.route('/api/pipeline/assign-electives', methods=['POST'])
def assign_electives():
    """선택과목 교육반 배정 (4밴드)"""
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        grade = sanitize_input(data.get('grade'), 10)
        seed = data.get('seed', 42)

        if not school_id or not grade:
            return jsonify({'success': False, 'message': 'school_id와 grade 필요'})

        from utils.elective_engine import run_elective_pipeline

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'DB 연결 오류'})
        cursor = conn.cursor()

        result = run_elective_pipeline(cursor, school_id, grade, seed=seed)

        # 밴드 균형 오류 등 엔진에서 에러 반환 시
        if result.get('status') == 'error':
            conn.rollback()
            return jsonify({'success': False, **result})

        if result.get('saved'):
            conn.commit()
        elif not result.get('skipped'):
            conn.rollback()

        return jsonify({'success': True, **result})

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"pipeline assign-electives 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
