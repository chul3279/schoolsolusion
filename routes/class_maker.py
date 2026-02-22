from flask import Blueprint, request, jsonify, session
import json
import random
from utils.db import get_db_connection, sanitize_input

class_maker_bp = Blueprint('class_maker', __name__)


# ============================================
# Step 1: 개설과목 + 학생 데이터 통합 조회
# ============================================
@class_maker_bp.route('/api/class-maker/load-data', methods=['GET'])
def load_class_maker_data():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        grade = sanitize_input(request.args.get('grade'), 10)

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 1) 개설과목 (timetable_data)
        q_subjects = """
            SELECT subject, grade, subject_demand, subject_depart, stu_count,
                   class_demand, tea_demand, tea_1person
            FROM timetable_data WHERE school_id = %s
        """
        params = [school_id]
        if grade:
            q_subjects += " AND grade = %s"
            params.append(grade)
        q_subjects += " ORDER BY subject_depart, subject"
        cursor.execute(q_subjects, params)
        subjects = cursor.fetchall()

        # 2) 학생 선택과목 (timetable_stu)
        q_stu = """
            SELECT ts.member_id, ts.member_name, ts.grade, ts.class_no, ts.student_num,
                   ts.subject1, ts.subject2, ts.subject3, ts.subject4, ts.subject5, ts.subject6,
                   ts.subject7, ts.subject8, ts.subject9, ts.subject10, ts.subject11, ts.subject12,
                   sa.point
            FROM timetable_stu ts
            LEFT JOIN stu_all sa ON ts.member_id = sa.member_id AND ts.school_id = sa.school_id
            WHERE ts.school_id = %s
        """
        stu_params = [school_id]
        if grade:
            q_stu += " AND ts.grade = %s"
            stu_params.append(grade)
        q_stu += " ORDER BY ts.grade, ts.class_no, ts.student_num"
        cursor.execute(q_stu, stu_params)
        students = cursor.fetchall()

        # point를 직렬화 가능하게 변환
        for s in students:
            if s.get('point') is not None:
                try:
                    s['point'] = float(s['point'])
                except (ValueError, TypeError):
                    s['point'] = 0

        # 3) 학년별 학생수 요약
        cursor.execute("""
            SELECT grade, COUNT(*) as cnt
            FROM timetable_stu WHERE school_id = %s
            GROUP BY grade ORDER BY grade
        """, (school_id,))
        grade_summary = cursor.fetchall()

        # 4) 학년별 설정 (class_maker_config)
        cursor.execute("SELECT * FROM class_maker_config WHERE school_id = %s", (school_id,))
        configs = cursor.fetchall()

        return jsonify({
            'success': True,
            'subjects': subjects,
            'students': students,
            'grade_summary': grade_summary,
            'configs': configs
        })

    except Exception as e:
        print(f"class-maker load-data 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# Step 2: 학년별 설정 저장 (학급수, 정원)
# ============================================
@class_maker_bp.route('/api/class-maker/config/save', methods=['POST'])
def save_class_maker_config():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        configs = data.get('configs', [])

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        for cfg in configs:
            grade = sanitize_input(cfg.get('grade'), 10)
            num_classes = int(cfg.get('num_classes', 10))
            min_per = int(cfg.get('min_per_class', 20))
            max_per = int(cfg.get('max_per_class', 35))

            cursor.execute("""
                INSERT INTO class_maker_config (school_id, grade, num_classes, min_per_class, max_per_class)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    num_classes = VALUES(num_classes),
                    min_per_class = VALUES(min_per_class),
                    max_per_class = VALUES(max_per_class),
                    updated_at = NOW()
            """, (school_id, grade, num_classes, min_per, max_per))

        conn.commit()
        return jsonify({'success': True, 'message': '설정이 저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"class-maker config save 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# Step 3: 제약조건 CRUD
# ============================================
@class_maker_bp.route('/api/class-maker/constraints', methods=['GET'])
def get_constraints():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        grade = sanitize_input(request.args.get('grade'), 10)

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        q = "SELECT * FROM class_maker_constraints WHERE school_id = %s"
        params = [school_id]
        if grade:
            q += " AND grade = %s"
            params.append(grade)
        q += " ORDER BY grade, constraint_type, id"
        cursor.execute(q, params)
        rows = cursor.fetchall()

        # JSON 필드 파싱
        for r in rows:
            if isinstance(r.get('student_ids'), str):
                try:
                    r['student_ids'] = json.loads(r['student_ids'])
                except:
                    r['student_ids'] = []
            if isinstance(r.get('student_names'), str):
                try:
                    r['student_names'] = json.loads(r['student_names'])
                except:
                    r['student_names'] = []

        return jsonify({'success': True, 'constraints': rows, 'count': len(rows)})

    except Exception as e:
        print(f"constraints 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@class_maker_bp.route('/api/class-maker/constraints/save', methods=['POST'])
def save_constraint():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        grade = sanitize_input(data.get('grade'), 10)
        constraint_type = sanitize_input(data.get('constraint_type'), 20)
        student_ids = data.get('student_ids', [])
        student_names = data.get('student_names', [])
        target_class = sanitize_input(data.get('target_class'), 10)
        memo = sanitize_input(data.get('memo'), 500)
        constraint_id = data.get('id')

        if not school_id or not grade or not constraint_type:
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})
        if constraint_type not in ('separate', 'together', 'fixed_class', 'special'):
            return jsonify({'success': False, 'message': '유효하지 않은 제약조건 유형입니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        ids_json = json.dumps(student_ids, ensure_ascii=False)
        names_json = json.dumps(student_names, ensure_ascii=False)

        if constraint_id:
            cursor.execute("""
                UPDATE class_maker_constraints
                SET grade=%s, constraint_type=%s, student_ids=%s, student_names=%s,
                    target_class=%s, memo=%s, updated_at=NOW()
                WHERE id=%s AND school_id=%s
            """, (grade, constraint_type, ids_json, names_json,
                  target_class, memo, constraint_id, school_id))
        else:
            cursor.execute("""
                INSERT INTO class_maker_constraints
                (school_id, grade, constraint_type, student_ids, student_names, target_class, memo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (school_id, grade, constraint_type, ids_json, names_json, target_class, memo))

        conn.commit()
        return jsonify({'success': True, 'message': '제약조건이 저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"constraint save 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@class_maker_bp.route('/api/class-maker/constraints/delete', methods=['POST'])
def delete_constraint():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        constraint_id = data.get('id')
        school_id = sanitize_input(data.get('school_id'), 50)

        if not constraint_id or not school_id:
            return jsonify({'success': False, 'message': 'id와 school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("DELETE FROM class_maker_constraints WHERE id = %s AND school_id = %s",
                        (constraint_id, school_id))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': '삭제되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '해당 데이터를 찾을 수 없습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"constraint delete 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# Step 4: 자동 반편성 알고리즘
# ============================================
@class_maker_bp.route('/api/class-maker/auto-assign', methods=['POST'])
def auto_assign():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        grade = sanitize_input(data.get('grade'), 10)

        if not school_id or not grade:
            return jsonify({'success': False, 'message': 'school_id와 grade가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 1) 설정 조회
        cursor.execute("SELECT * FROM class_maker_config WHERE school_id=%s AND grade=%s",
                        (school_id, grade))
        config = cursor.fetchone()
        num_classes = config['num_classes'] if config else 10

        # 2) 학생 조회 (+ 성적)
        cursor.execute("""
            SELECT ts.member_id, ts.member_name, ts.grade, ts.class_no, ts.student_num,
                   ts.subject1, ts.subject2, ts.subject3, ts.subject4, ts.subject5, ts.subject6,
                   ts.subject7, ts.subject8, ts.subject9, ts.subject10, ts.subject11, ts.subject12,
                   COALESCE(sa.point, 0) as score
            FROM timetable_stu ts
            LEFT JOIN stu_all sa ON ts.member_id = sa.member_id AND ts.school_id = sa.school_id
            WHERE ts.school_id = %s AND ts.grade = %s
            ORDER BY ts.student_num
        """, (school_id, grade))
        students = cursor.fetchall()

        if not students:
            return jsonify({'success': False, 'message': f'{grade}학년 학생 데이터가 없습니다.'})

        # score를 float으로
        for s in students:
            try:
                s['score'] = float(s['score'])
            except (ValueError, TypeError):
                s['score'] = 0.0

        # 3) 제약조건 조회
        cursor.execute("SELECT * FROM class_maker_constraints WHERE school_id=%s AND grade=%s",
                        (school_id, grade))
        constraints = cursor.fetchall()
        for c in constraints:
            if isinstance(c.get('student_ids'), str):
                try:
                    c['student_ids'] = json.loads(c['student_ids'])
                except:
                    c['student_ids'] = []

        # 4) 반편성 알고리즘 실행
        result = _run_assignment(students, num_classes, constraints)

        # 5) 결과 DB 저장 (기존 삭제 후 INSERT)
        cursor.execute("DELETE FROM class_maker_result WHERE school_id=%s AND grade=%s",
                        (school_id, grade))

        for r in result:
            cursor.execute("""
                INSERT INTO class_maker_result
                (school_id, grade, member_id, member_name, original_class, assigned_class, score, assignment_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (school_id, grade, r['member_id'], r['member_name'],
                  r['original_class'], r['assigned_class'], r['score'], r['type']))

        conn.commit()

        # 6) 반별 통계 계산
        class_stats = _calc_class_stats(result, num_classes)

        return jsonify({
            'success': True,
            'message': f'{grade}학년 {len(result)}명 → {num_classes}개 반 배치 완료',
            'result': result,
            'class_stats': class_stats,
            'num_classes': num_classes
        })

    except Exception as e:
        if conn: conn.rollback()
        print(f"auto-assign 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def _run_assignment(students, num_classes, constraints):
    """Snake-draft 기반 반편성 알고리즘"""
    # 고정반 학생 분리
    fixed = {}  # member_id -> class_no
    separate_groups = []  # [[id1, id2], ...]
    together_groups = []  # [[id1, id2], ...]

    for c in constraints:
        ids = c.get('student_ids', [])
        if c['constraint_type'] == 'fixed_class' and c.get('target_class'):
            for sid in ids:
                fixed[sid] = str(c['target_class'])
        elif c['constraint_type'] == 'separate':
            separate_groups.append(set(ids))
        elif c['constraint_type'] == 'together':
            together_groups.append(set(ids))

    # 반 초기화
    classes = {str(i): [] for i in range(1, num_classes + 1)}

    # 1단계: 고정반 학생 배치
    remaining = []
    for s in students:
        mid = s['member_id'] or ''
        if mid in fixed:
            s_result = {
                'member_id': mid,
                'member_name': s['member_name'],
                'original_class': s.get('class_no', ''),
                'assigned_class': fixed[mid],
                'score': s['score'],
                'type': 'fixed'
            }
            classes[fixed[mid]].append(s_result)
        else:
            remaining.append(s)

    # 2단계: 합반(together) 그룹 처리 — 그룹을 같은 반에 배치
    together_placed = set()
    for group in together_groups:
        group_students = [s for s in remaining if (s['member_id'] or '') in group]
        if not group_students:
            continue
        # 가장 인원 적은 반에 배치
        min_class = min(classes.keys(), key=lambda k: len(classes[k]))
        for s in group_students:
            mid = s['member_id'] or ''
            s_result = {
                'member_id': mid,
                'member_name': s['member_name'],
                'original_class': s.get('class_no', ''),
                'assigned_class': min_class,
                'score': s['score'],
                'type': 'auto'
            }
            classes[min_class].append(s_result)
            together_placed.add(mid)

    # 남은 학생 (고정/합반 제외)
    remaining = [s for s in remaining if (s['member_id'] or '') not in together_placed]

    # 3단계: 성적순 정렬 → Snake Draft
    remaining.sort(key=lambda x: x['score'], reverse=True)
    class_keys = [str(i) for i in range(1, num_classes + 1)]

    direction = 1
    idx = 0
    for s in remaining:
        mid = s['member_id'] or ''
        assigned = False

        # 분리 제약 확인: 이미 배치된 같은 그룹 학생이 있는 반은 건너뜀
        forbidden_classes = set()
        for sep_group in separate_groups:
            if mid in sep_group:
                for cls_key, cls_list in classes.items():
                    for placed in cls_list:
                        if placed['member_id'] in sep_group and placed['member_id'] != mid:
                            forbidden_classes.add(cls_key)

        # Snake draft 순서로 배치 시도
        attempts = 0
        while attempts < num_classes:
            target = class_keys[idx]
            if target not in forbidden_classes:
                s_result = {
                    'member_id': mid,
                    'member_name': s['member_name'],
                    'original_class': s.get('class_no', ''),
                    'assigned_class': target,
                    'score': s['score'],
                    'type': 'auto'
                }
                classes[target].append(s_result)
                assigned = True
                # 다음 인덱스로
                idx += direction
                if idx >= num_classes:
                    idx = num_classes - 1
                    direction = -1
                elif idx < 0:
                    idx = 0
                    direction = 1
                break

            # forbidden이면 다음 반 시도
            idx += direction
            if idx >= num_classes:
                idx = num_classes - 1
                direction = -1
            elif idx < 0:
                idx = 0
                direction = 1
            attempts += 1

        # 모든 반이 forbidden이면 인원 적은 반에 강제 배치
        if not assigned:
            min_class = min(class_keys, key=lambda k: len(classes[k]))
            classes[min_class].append({
                'member_id': mid,
                'member_name': s['member_name'],
                'original_class': s.get('class_no', ''),
                'assigned_class': min_class,
                'score': s['score'],
                'type': 'auto'
            })

    # 모든 반의 결과를 1차원 리스트로
    all_results = []
    for cls_list in classes.values():
        all_results.extend(cls_list)

    return all_results


def _calc_class_stats(result, num_classes):
    """반별 통계 계산"""
    stats = {}
    for i in range(1, num_classes + 1):
        key = str(i)
        members = [r for r in result if str(r['assigned_class']) == key]
        scores = [m['score'] for m in members if m['score'] > 0]
        stats[key] = {
            'count': len(members),
            'avg_score': round(sum(scores) / len(scores), 1) if scores else 0,
            'min_score': round(min(scores), 1) if scores else 0,
            'max_score': round(max(scores), 1) if scores else 0
        }
    return stats


# ============================================
# 반편성 결과 조회
# ============================================
@class_maker_bp.route('/api/class-maker/result', methods=['GET'])
def get_result():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        grade = sanitize_input(request.args.get('grade'), 10)

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        q = "SELECT * FROM class_maker_result WHERE school_id = %s"
        params = [school_id]
        if grade:
            q += " AND grade = %s"
            params.append(grade)
        q += " ORDER BY assigned_class, member_name"
        cursor.execute(q, params)
        rows = cursor.fetchall()

        # score를 float으로
        for r in rows:
            if r.get('score') is not None:
                r['score'] = float(r['score'])

        # 반별 통계
        if rows:
            max_class = max(int(r['assigned_class']) for r in rows if r['assigned_class'])
            class_stats = _calc_class_stats(rows, max_class)
        else:
            class_stats = {}

        return jsonify({
            'success': True,
            'result': rows,
            'class_stats': class_stats,
            'count': len(rows)
        })

    except Exception as e:
        print(f"class-maker result 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학생 수동 이동
# ============================================
@class_maker_bp.route('/api/class-maker/move', methods=['POST'])
def move_student():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_id = sanitize_input(data.get('member_id'), 50)
        grade = sanitize_input(data.get('grade'), 10)
        new_class = sanitize_input(data.get('new_class'), 10)

        if not all([school_id, member_id, grade, new_class]):
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE class_maker_result
            SET assigned_class = %s, assignment_type = 'manual', updated_at = NOW()
            WHERE school_id = %s AND member_id = %s AND grade = %s
        """, (new_class, school_id, member_id, grade))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': f'{new_class}반으로 이동 완료'})
        else:
            return jsonify({'success': False, 'message': '해당 학생을 찾을 수 없습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"class-maker move 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 반편성 결과 확정 → timetable_stu 반영
# ============================================
@class_maker_bp.route('/api/class-maker/confirm', methods=['POST'])
def confirm_result():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        grade = sanitize_input(data.get('grade'), 10)

        if not school_id or not grade:
            return jsonify({'success': False, 'message': 'school_id와 grade가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 결과 조회
        cursor.execute("""
            SELECT member_id, assigned_class
            FROM class_maker_result
            WHERE school_id = %s AND grade = %s
        """, (school_id, grade))
        results = cursor.fetchall()

        if not results:
            return jsonify({'success': False, 'message': '확정할 반편성 결과가 없습니다.'})

        # timetable_stu의 class_no 업데이트
        updated = 0
        for r in results:
            if r['member_id'] and r['assigned_class']:
                cursor.execute("""
                    UPDATE timetable_stu
                    SET class_no = %s, updated_at = NOW()
                    WHERE school_id = %s AND member_id = %s AND grade = %s
                """, (r['assigned_class'], school_id, r['member_id'], grade))
                updated += cursor.rowcount

        conn.commit()

        return jsonify({
            'success': True,
            'message': f'{grade}학년 반편성 확정 완료 ({updated}명 반 업데이트)',
            'updated': updated
        })

    except Exception as e:
        if conn: conn.rollback()
        print(f"class-maker confirm 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
