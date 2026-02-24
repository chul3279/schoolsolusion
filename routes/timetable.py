from flask import Blueprint, request, jsonify, session
from datetime import datetime
from utils.db import get_db_connection, sanitize_input

timetable_bp = Blueprint('timetable', __name__)

# ============================================
# cours_subject DB 불러오기 API (기초DB)
# ============================================
@timetable_bp.route('/api/cours-subject/list', methods=['GET'])
def get_cours_subject_list():
    conn = None
    cursor = None
    try:
        school_level = sanitize_input(request.args.get('school_level'), 20)
        course_year = sanitize_input(request.args.get('course_year'), 20)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()

        query = "SELECT id, course_year, domain, subject, school_level FROM cours_subject WHERE 1=1"
        params = []
        if school_level:
            query += " AND school_level = %s"
            params.append(school_level)
        if course_year:
            query += " AND course_year = %s"
            params.append(course_year)
        query += " ORDER BY domain, subject"
        cursor.execute(query, params)
        subjects = cursor.fetchall()

        return jsonify({
            'success': True,
            'subjects': subjects,
            'count': len(subjects)
        })

    except Exception as e:
        print(f"cours_subject 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'기초DB 불러오기 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 과목 조사 기간 조회/저장 API
# ============================================
@timetable_bp.route('/api/timetable-survey/get', methods=['GET'])
def get_timetable_survey():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM timetable_survey WHERE school_id = %s", (school_id,))
        row = cursor.fetchone()

        if row:
            return jsonify({
                'success': True,
                'survey': {
                    'survey_start': row['survey_start'].strftime('%Y-%m-%d') if row['survey_start'] else '',
                    'survey_end': row['survey_end'].strftime('%Y-%m-%d') if row['survey_end'] else '',
                    'survey_status': row['survey_status'] or 'inactive'
                }
            })
        else:
            return jsonify({'success': True, 'survey': None})

    except Exception as e:
        print(f"survey 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@timetable_bp.route('/api/timetable-survey/save', methods=['POST'])
def save_timetable_survey():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        survey_start = sanitize_input(data.get('survey_start'), 10)
        survey_end = sanitize_input(data.get('survey_end'), 10)
        survey_status = sanitize_input(data.get('survey_status'), 20) or 'active'

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})

        cursor = conn.cursor()
        cursor.execute("SELECT id FROM timetable_survey WHERE school_id = %s", (school_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""UPDATE timetable_survey
                SET member_school=%s, survey_start=%s, survey_end=%s, survey_status=%s
                WHERE school_id=%s""",
                (member_school, survey_start or None, survey_end or None, survey_status, school_id))
        else:
            cursor.execute("""INSERT INTO timetable_survey
                (school_id, member_school, survey_start, survey_end, survey_status)
                VALUES (%s, %s, %s, %s, %s)""",
                (school_id, member_school, survey_start or None, survey_end or None, survey_status))

        conn.commit()
        return jsonify({'success': True, 'message': '과목 조사 기간이 저장되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"survey 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# cours_subject DB 저장하기 API (기초DB)
# ============================================
@timetable_bp.route('/api/cours-subject/save', methods=['POST'])
def save_cours_subject():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        subjects = data.get('subjects', [])
        
        if not subjects:
            return jsonify({'success': False, 'message': '저장할 데이터가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        
        for subj in subjects:
            course_year = sanitize_input(subj.get('course_year'), 20)
            domain = sanitize_input(subj.get('domain'), 100)
            subject = sanitize_input(subj.get('subject'), 100)
            school_level = sanitize_input(subj.get('school_level'), 20)
            
            if not subject:
                continue
            
            cursor.execute("""
                SELECT id FROM cours_subject 
                WHERE subject = %s AND (course_year = %s OR (course_year IS NULL AND %s IS NULL))
            """, (subject, course_year, course_year))
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE cours_subject 
                    SET domain = %s, school_level = %s, updated_at = NOW()
                    WHERE id = %s
                """, (domain, school_level, existing['id']))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO cours_subject (course_year, domain, subject, school_level, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (course_year, domain, subject, school_level))
                inserted += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'기초DB 저장 완료 (추가: {inserted}, 업데이트: {updated})'
        })
        
    except Exception as e:
        print(f"cours_subject 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'기초DB 저장 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_data DB 불러오기 API (결과DB)
# ============================================
@timetable_bp.route('/api/timetable-data/list', methods=['GET'])
def get_timetable_data_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            query = """
                SELECT id, school_id, member_school, subject, course_year, grade, 
                       subject_demand, subject_type, subject_depart,
                       stu_count, class_demand, tea_demand, tea_1person,
                       subject_type_tea_conclution
                FROM timetable_data
                WHERE school_id = %s
                ORDER BY subject_depart, grade, subject
            """
            cursor.execute(query, (school_id,))
        else:
            query = """
                SELECT id, school_id, member_school, subject, course_year, grade, 
                       subject_demand, subject_type, subject_depart,
                       stu_count, class_demand, tea_demand, tea_1person,
                       subject_type_tea_conclution
                FROM timetable_data
                WHERE member_school = %s
                ORDER BY subject_depart, grade, subject
            """
            cursor.execute(query, (member_school,))
        
        data = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'school_id': school_id,
            'member_school': member_school
        })
        
    except Exception as e:
        print(f"timetable_data 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'결과DB 불러오기 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_data DB 저장하기 API (결과DB)
# ============================================
@timetable_bp.route('/api/timetable-data/save', methods=['POST'])
def save_timetable_data():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        timetable_data = data.get('data', [])
        
        if not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not timetable_data:
            return jsonify({'success': False, 'message': '저장할 데이터가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        
        for item in timetable_data:
            subject = sanitize_input(item.get('subject'), 100)
            course_year = sanitize_input(item.get('course_year'), 20)
            grade = item.get('grade')
            subject_demand = item.get('subject_demand')
            subject_type = sanitize_input(item.get('subject_type'), 100)
            subject_depart = sanitize_input(item.get('subject_depart'), 100)
            stu_count = item.get('stu_count')
            class_demand = item.get('class_demand')
            tea_demand = item.get('tea_demand')
            tea_1person = item.get('tea_1person')
            tea_conclution = item.get('subject_type_tea_conclution')
            
            if not subject:
                continue
            
            if school_id:
                cursor.execute("""
                    SELECT id FROM timetable_data 
                    WHERE school_id = %s AND subject = %s AND grade = %s
                """, (school_id, subject, grade))
            else:
                cursor.execute("""
                    SELECT id FROM timetable_data 
                    WHERE member_school = %s AND subject = %s AND grade = %s
                """, (member_school, subject, grade))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE timetable_data 
                    SET course_year = %s, subject_demand = %s, subject_type = %s, 
                        subject_depart = %s, stu_count = %s, class_demand = %s,
                        tea_demand = %s, tea_1person = %s, subject_type_tea_conclution = %s,
                        school_id = %s, member_school = %s, updated_at = NOW()
                    WHERE id = %s
                """, (course_year, subject_demand, subject_type, subject_depart, 
                      stu_count, class_demand, tea_demand, tea_1person, tea_conclution,
                      school_id, member_school, existing['id']))
                updated += 1
            else:
                cursor.execute("""
                    INSERT INTO timetable_data 
                    (school_id, member_school, subject, course_year, grade, subject_demand, 
                     subject_type, subject_depart, stu_count, class_demand, tea_demand, tea_1person,
                     subject_type_tea_conclution, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """, (school_id, member_school, subject, course_year, grade, subject_demand, 
                      subject_type, subject_depart, stu_count, class_demand, tea_demand, tea_1person,
                      tea_conclution))
                inserted += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'결과DB 저장 완료 (추가: {inserted}, 업데이트: {updated})',
            'school_id': school_id,
            'member_school': member_school
        })
        
    except Exception as e:
        print(f"timetable_data 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'결과DB 저장 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 교사 시간표 조회 API (당일 + 변경사항 오버레이)
# ============================================
@timetable_bp.route('/api/timetable/teacher', methods=['GET'])
def get_teacher_timetable():
    conn = None
    cursor = None
    try:
        member_name = sanitize_input(request.args.get('member_name'), 50)
        query_member_id = sanitize_input(request.args.get('member_id'), 100)
        member_school = sanitize_input(request.args.get('member_school'), 100)
        school_id = sanitize_input(request.args.get('school_id'), 50)

        if (not member_name and not query_member_id) or (not member_school and not school_id):
            return jsonify({'success': False, 'message': '세션이 만료되었습니다. 다시 로그인해주세요.'})

        day_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        today = day_map.get(datetime.now().weekday(), '월')
        today_date = datetime.now().strftime('%Y-%m-%d')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 1) 원본 시간표 조회 — member_id 우선, 없으면 member_name 폴백
        if query_member_id:
            id_col = "school_id" if school_id else "member_school"
            id_val = school_id or member_school
            cursor.execute(f"""
                SELECT period, subject, grade, class_no
                FROM timetable
                WHERE member_id = %s AND {id_col} = %s AND day_of_week = %s
                ORDER BY period
            """, (query_member_id, id_val, today))
        elif school_id:
            cursor.execute("""
                SELECT period, subject, grade, class_no
                FROM timetable
                WHERE member_name = %s AND school_id = %s AND day_of_week = %s
                ORDER BY period
            """, (member_name, school_id, today))
        else:
            cursor.execute("""
                SELECT period, subject, grade, class_no
                FROM timetable
                WHERE member_name = %s AND member_school = %s AND day_of_week = %s
                ORDER BY period
            """, (member_name, member_school, today))
        timetable = cursor.fetchall()

        # 2) 오늘자 변경사항 조회 (이 교사가 원래 담당이던 수업)
        change_where = "school_id = %s" if school_id else "member_school = %s"
        change_param = school_id or member_school
        cursor.execute(f"""
            SELECT period, day_of_week, new_teacher, new_subject,
                   original_subject, original_grade, original_class_no, change_reason
            FROM timetable_changes
            WHERE {change_where} AND change_date = %s AND day_of_week = %s
              AND original_teacher = %s
        """, (change_param, today_date, today, member_name))
        my_changes = cursor.fetchall()

        # 3) 오늘자 변경사항 중 이 교사가 보강으로 투입된 수업
        cursor.execute(f"""
            SELECT period, day_of_week, original_teacher, original_subject,
                   new_subject, original_grade, original_class_no, change_reason
            FROM timetable_changes
            WHERE {change_where} AND change_date = %s AND day_of_week = %s
              AND new_teacher = %s
        """, (change_param, today_date, today, member_name))
        cover_changes = cursor.fetchall()

        # 4) 변경사항 오버레이 적용
        change_map = {}
        for c in my_changes:
            change_map[int(c['period'])] = {
                'type': 'cancelled',
                'reason': c.get('change_reason', ''),
                'new_teacher': c.get('new_teacher', ''),
                'new_subject': c.get('new_subject', '')
            }

        cover_map = {}
        for c in cover_changes:
            cover_map[int(c['period'])] = {
                'original_teacher': c.get('original_teacher', ''),
                'subject': c.get('new_subject') or c.get('original_subject', ''),
                'grade': c.get('original_grade', ''),
                'class_no': c.get('original_class_no', ''),
                'reason': c.get('change_reason', '')
            }

        result = []
        for item in timetable:
            p = int(item['period'])
            entry = dict(item)
            if p in change_map:
                ch = change_map[p]
                entry['changed'] = True
                entry['change_type'] = 'cancelled'
                entry['change_reason'] = ch['reason']
                entry['new_teacher'] = ch['new_teacher']
                entry['original_subject'] = entry['subject']
                entry['subject'] = ch['new_subject'] or '자습'
            result.append(entry)

        # 보강 투입 수업 추가 (원래 내 시간표에 없던 교시)
        existing_periods = {int(r['period']) for r in result}
        for p, cv in cover_map.items():
            if p not in existing_periods:
                result.append({
                    'period': p,
                    'subject': cv['subject'],
                    'grade': cv['grade'],
                    'class_no': cv['class_no'],
                    'changed': True,
                    'change_type': 'cover',
                    'change_reason': cv['reason'],
                    'original_teacher': cv['original_teacher']
                })

        result.sort(key=lambda x: int(x['period']))

        return jsonify({'success': True, 'today': today, 'timetable': result})

    except Exception as e:
        print(f"교사 시간표 조회 오류: {e}")
        return jsonify({'success': False, 'message': '시간표 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# 학급 시간표 조회 API (당일 + 변경사항 오버레이)
# ============================================
@timetable_bp.route('/api/timetable/class', methods=['GET'])
def get_class_timetable():
    conn = None
    cursor = None
    try:
        member_school = sanitize_input(request.args.get('member_school'), 100)
        school_id = sanitize_input(request.args.get('school_id'), 50)
        grade = sanitize_input(request.args.get('grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)

        if (not member_school and not school_id) or not grade or not class_no:
            return jsonify({'success': False, 'message': '학급 정보가 없습니다.'})

        day_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        today = day_map.get(datetime.now().weekday(), '월')
        today_date = datetime.now().strftime('%Y-%m-%d')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 1) 원본 시간표 조회 (timetable 테이블 사용, class_no 단일값)
        if school_id:
            cursor.execute("""
                SELECT period, subject, member_name, grade, class_no
                FROM timetable
                WHERE school_id = %s AND grade = %s AND class_no = %s
                  AND day_of_week = %s
                ORDER BY period
            """, (school_id, grade, class_no, today))
        else:
            cursor.execute("""
                SELECT period, subject, member_name, grade, class_no
                FROM timetable
                WHERE member_school = %s AND grade = %s AND class_no = %s
                  AND day_of_week = %s
                ORDER BY period
            """, (member_school, grade, class_no, today))
        timetable = cursor.fetchall()

        # 2) 오늘자 해당 학급 변경사항 조회
        change_where = "school_id = %s" if school_id else "member_school = %s"
        change_param = school_id or member_school
        cursor.execute(f"""
            SELECT period, original_teacher, original_subject,
                   new_teacher, new_subject, change_reason
            FROM timetable_changes
            WHERE {change_where} AND change_date = %s AND day_of_week = %s
              AND original_grade = %s AND original_class_no = %s
        """, (change_param, today_date, today, grade, class_no))
        changes = cursor.fetchall()

        # 3) 변경사항 오버레이
        change_map = {int(c['period']): c for c in changes}

        result = []
        for item in timetable:
            p = int(item['period'])
            entry = dict(item)
            if p in change_map:
                ch = change_map[p]
                entry['changed'] = True
                entry['change_reason'] = ch.get('change_reason', '')
                entry['original_teacher'] = ch.get('original_teacher', '')
                entry['original_subject'] = entry['subject']
                entry['subject'] = ch.get('new_subject') or '자습'
                entry['member_name'] = ch.get('new_teacher') or '자습'
            result.append(entry)

        result.sort(key=lambda x: int(x['period']))

        return jsonify({'success': True, 'today': today, 'timetable': result})

    except Exception as e:
        print(f"학급 시간표 조회 오류: {e}")
        return jsonify({'success': False, 'message': '시간표 조회 중 오류가 발생했습니다.'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_stu DB 불러오기 API (학생 데이터)
# ============================================
@timetable_bp.route('/api/timetable-stu/list', methods=['GET'])
def get_timetable_stu_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            query = """
                SELECT id, member_id, school_id, member_name, member_birth, member_school,
                       grade, class_no, student_num,
                       subject1, subject2, subject3, subject4, subject5, subject6,
                       subject7, subject8, subject9, subject10, subject11, subject12
                FROM timetable_stu
                WHERE school_id = %s
                ORDER BY grade, class_no, student_num
            """
            cursor.execute(query, (school_id,))
        else:
            query = """
                SELECT id, member_id, school_id, member_name, member_birth, member_school,
                       grade, class_no, student_num,
                       subject1, subject2, subject3, subject4, subject5, subject6,
                       subject7, subject8, subject9, subject10, subject11, subject12
                FROM timetable_stu
                WHERE member_school = %s
                ORDER BY grade, class_no, student_num
            """
            cursor.execute(query, (member_school,))
        
        data = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data),
            'school_id': school_id,
            'member_school': member_school
        })
        
    except Exception as e:
        print(f"timetable_stu 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'학생DB 불러오기 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_stu DB 저장하기 API (학생 데이터)
# ============================================
@timetable_bp.route('/api/timetable-stu/save', methods=['POST'])
def save_timetable_stu():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        stu_data = data.get('data', [])
        
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})
        
        if not stu_data:
            return jsonify({'success': False, 'message': '저장할 학생 데이터가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM timetable_stu WHERE school_id = %s", (school_id,))
        
        inserted = 0
        
        for item in stu_data:
            member_id = sanitize_input(item.get('member_id'), 50) or None
            member_name = sanitize_input(item.get('member_name'), 100) or None
            
            if not member_name:
                continue
            
            member_birth_raw = sanitize_input(item.get('member_birth'), 20)
            if member_birth_raw and member_birth_raw.strip() and member_birth_raw.strip().lower() not in ('', 'null', 'undefined', 'none'):
                member_birth = member_birth_raw.strip()
            else:
                member_birth = None
            
            grade = sanitize_input(item.get('grade'), 10) or None
            class_no = sanitize_input(item.get('class_no'), 10) or None
            student_num = sanitize_input(item.get('student_num'), 10) or None
            
            subjects = []
            for i in range(1, 13):
                subj = sanitize_input(item.get(f'subject{i}'), 100)
                subjects.append(subj if subj and subj.strip() else None)
            
            cursor.execute("""
                INSERT INTO timetable_stu 
                (member_id, school_id, member_school, member_name, member_birth, grade, class_no, student_num,
                 subject1, subject2, subject3, subject4, subject5, subject6,
                 subject7, subject8, subject9, subject10, subject11, subject12, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (member_id, school_id, member_school, member_name, member_birth, grade, class_no, student_num,
                  subjects[0], subjects[1], subjects[2], subjects[3], subjects[4], subjects[5],
                  subjects[6], subjects[7], subjects[8], subjects[9], subjects[10], subjects[11]))
            inserted += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'학생DB 저장 완료 ({inserted}명)',
            'inserted': inserted,
            'school_id': school_id,
            'member_school': member_school
        })
        
    except Exception as e:
        print(f"timetable_stu 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'학생DB 저장 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_data stu_count 업데이트 API
# ============================================
@timetable_bp.route('/api/timetable-data/update-stu-count', methods=['POST'])
def update_timetable_data_stu_count():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        count_data = data.get('data', [])
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not count_data:
            return jsonify({'success': False, 'message': '저장할 수강인원 데이터가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        updated = 0
        not_found = 0
        
        for item in count_data:
            subject = sanitize_input(item.get('subject'), 100)
            stu_count = item.get('stu_count', 0)
            
            if not subject:
                continue
            
            if school_id:
                cursor.execute("""
                    UPDATE timetable_data 
                    SET stu_count = %s, updated_at = NOW()
                    WHERE school_id = %s AND subject = %s
                """, (stu_count, school_id, subject))
            else:
                cursor.execute("""
                    UPDATE timetable_data 
                    SET stu_count = %s, updated_at = NOW()
                    WHERE member_school = %s AND subject = %s
                """, (stu_count, member_school, subject))
            
            if cursor.rowcount > 0:
                updated += 1
            else:
                not_found += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'수강인원 저장 완료 (업데이트: {updated}개, 미등록 과목: {not_found}개)',
            'updated': updated,
            'not_found': not_found,
            'school_id': school_id,
            'member_school': member_school
        })
        
    except Exception as e:
        print(f"stu_count 업데이트 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'수강인원 저장 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_tea 불러오기 API
# ============================================
@timetable_bp.route('/api/timetable-tea/list', methods=['GET'])
def get_timetable_tea_list():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            cursor.execute("""
                SELECT id, school_id, member_id, member_school, grade, class_no, class_conut,
                       day_of_week, period, subject, member_name, hours, member_birth
                FROM timetable_tea
                WHERE school_id = %s
                ORDER BY member_name, grade, class_no
            """, (school_id,))
        else:
            cursor.execute("""
                SELECT id, school_id, member_id, member_school, grade, class_no, class_conut,
                       day_of_week, period, subject, member_name, hours, member_birth
                FROM timetable_tea
                WHERE member_school = %s
                ORDER BY member_name, grade, class_no
            """, (member_school,))
        
        data = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data)
        })
        
    except Exception as e:
        print(f"timetable_tea 조회 오류: {e}")
        return jsonify({'success': False, 'message': f'이전 작업 불러오기 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ============================================
# timetable_tea 저장 API
# ============================================
@timetable_bp.route('/api/timetable-tea/save', methods=['POST'])
def save_timetable_tea():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        tea_data = data.get('data', [])
        
        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        
        if not tea_data:
            return jsonify({'success': False, 'message': '저장할 데이터가 없습니다.'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        
        cursor = conn.cursor()
        
        if school_id:
            cursor.execute("DELETE FROM timetable_tea WHERE school_id = %s", (school_id,))
        else:
            cursor.execute("DELETE FROM timetable_tea WHERE member_school = %s", (member_school,))
        
        inserted = 0
        
        for item in tea_data:
            item_member_id = sanitize_input(item.get('member_id'), 100)
            member_name = sanitize_input(item.get('member_name'), 100)
            subject = sanitize_input(item.get('subject'), 100)
            grade = sanitize_input(item.get('grade'), 10)
            class_no = sanitize_input(item.get('class_no'), 10)
            class_conut = item.get('class_conut') or item.get('class_count')
            hours = item.get('hours')
            day_of_week = sanitize_input(item.get('day_of_week'), 10)
            period = item.get('period')
            member_birth = sanitize_input(item.get('member_birth'), 20)

            if not member_name:
                continue

            cursor.execute("""
                INSERT INTO timetable_tea
                (school_id, member_id, member_school, member_name, subject, grade, class_no, class_conut,
                 hours, day_of_week, period, member_birth, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (school_id, item_member_id, member_school, member_name, subject, grade, class_no, class_conut,
                  hours, day_of_week, period, member_birth))
            inserted += 1
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'timetable_tea 저장 완료 ({inserted}건)',
            'inserted': inserted
        })
        
    except Exception as e:
        print(f"timetable_tea 저장 오류: {e}")
        if conn: conn.rollback()
        return jsonify({'success': False, 'message': f'저장 오류: {str(e)}'})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 교사별 주간 시간표 조회 API
# ============================================
@timetable_bp.route('/api/timetable/teacher/week', methods=['GET'])
def get_teacher_week_timetable():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        member_name = sanitize_input(request.args.get('member_name'), 50)
        query_member_id = sanitize_input(request.args.get('member_id'), 100)
        change_date = sanitize_input(request.args.get('change_date'), 20)

        if (not member_name and not query_member_id) or (not school_id and not member_school):
            return jsonify({'success': False, 'message': '교사명과 학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # timetable 테이블에서 실제 시간표 조회 (timetable_tea는 배정 데이터만 있음)
        if query_member_id:
            id_col = "school_id" if school_id else "member_school"
            id_val = school_id or member_school
            cursor.execute(f"""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable
                WHERE {id_col} = %s AND member_id = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (id_val, query_member_id))
        elif school_id:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable
                WHERE school_id = %s AND member_name = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (school_id, member_name))
        else:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable
                WHERE member_school = %s AND member_name = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (member_school, member_name))

        timetable = cursor.fetchall()

        # 해당 날짜 변경사항 조회
        changes = []
        if change_date:
            where = "school_id = %s" if school_id else "member_school = %s"
            param = school_id or member_school
            cursor.execute(f"""
                SELECT * FROM timetable_changes
                WHERE {where} AND change_date = %s AND original_teacher = %s
                ORDER BY period
            """, (param, change_date, member_name))
            changes = cursor.fetchall()

        return jsonify({
            'success': True,
            'timetable': timetable,
            'changes': changes,
            'count': len(timetable)
        })

    except Exception as e:
        print(f"교사 주간 시간표 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학급별 주간 시간표 조회 API
# ============================================
@timetable_bp.route('/api/timetable/class/week', methods=['GET'])
def get_class_week_timetable():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)
        grade = sanitize_input(request.args.get('grade'), 10)
        class_no = sanitize_input(request.args.get('class_no'), 10)
        change_date = sanitize_input(request.args.get('change_date'), 20)

        if not grade or not class_no or (not school_id and not member_school):
            return jsonify({'success': False, 'message': '학년, 반, 학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # timetable 테이블에서 실제 시간표 조회 (class_no는 단일값으로 저장됨)
        if school_id:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable
                WHERE school_id = %s AND grade = %s AND class_no = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (school_id, grade, class_no))
        else:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable
                WHERE member_school = %s AND grade = %s AND class_no = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (member_school, grade, class_no))

        timetable = cursor.fetchall()

        # 해당 날짜 변경사항 조회
        changes = []
        if change_date:
            where = "school_id = %s" if school_id else "member_school = %s"
            param = school_id or member_school
            cursor.execute(f"""
                SELECT * FROM timetable_changes
                WHERE {where} AND change_date = %s
                  AND original_grade = %s AND original_class_no = %s
                ORDER BY period
            """, (param, change_date, grade, class_no))
            changes = cursor.fetchall()

        return jsonify({
            'success': True,
            'timetable': timetable,
            'changes': changes,
            'count': len(timetable)
        })

    except Exception as e:
        print(f"학급 주간 시간표 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학교 전체 시간표 조회 API (출력용)
# ============================================
@timetable_bp.route('/api/timetable/school/all', methods=['GET'])
def get_school_all_timetable():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT day_of_week, period, subject, grade, class_no, member_name, member_id
            FROM timetable
            WHERE school_id = %s AND day_of_week IN ('월','화','수','목','금')
            ORDER BY grade, class_no, FIELD(day_of_week,'월','화','수','목','금'), period
        """, (school_id,))
        timetable = cursor.fetchall()

        # 교사 목록 (부서 포함)
        cursor.execute("""
            SELECT member_id, member_name, department
            FROM tea_all WHERE school_id = %s
        """, (school_id,))
        teachers = cursor.fetchall()

        return jsonify({
            'success': True,
            'timetable': timetable,
            'teachers': teachers,
            'count': len(timetable)
        })

    except Exception as e:
        print(f"학교 전체 시간표 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 교사별 제약조건 조회 API
# ============================================
@timetable_bp.route('/api/timetable-constraint/list', methods=['GET'])
def get_timetable_constraints():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, member_id, member_name, constraint_type, day_of_week, period, reason
            FROM timetable_constraint
            WHERE school_id = %s
            ORDER BY member_name, day_of_week, period
        """, (school_id,))
        data = cursor.fetchall()

        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print(f"제약조건 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 교사별 제약조건 저장 API
# ============================================
@timetable_bp.route('/api/timetable-constraint/save', methods=['POST'])
def save_timetable_constraints():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        constraints = data.get('constraints', [])

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 기존 제약 전체 삭제
        cursor.execute("DELETE FROM timetable_constraint WHERE school_id = %s", (school_id,))

        # 새로 INSERT
        if constraints:
            insert_sql = """
                INSERT INTO timetable_constraint
                (school_id, member_id, member_name, constraint_type, day_of_week, period, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            rows = []
            for c in constraints:
                rows.append((
                    school_id,
                    sanitize_input(c.get('member_id'), 100),
                    sanitize_input(c.get('member_name'), 100),
                    c.get('constraint_type', 'period_off'),
                    sanitize_input(c.get('day_of_week'), 10),
                    c.get('period') if c.get('period') is not None else None,
                    sanitize_input(c.get('reason', ''), 200)
                ))
            cursor.executemany(insert_sql, rows)

        conn.commit()
        return jsonify({'success': True, 'message': f'{len(constraints)}건 저장 완료'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"제약조건 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 시간표 변경 저장 API
# ============================================
@timetable_bp.route('/api/timetable/change/save', methods=['POST'])
def save_timetable_change():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        change_date = sanitize_input(data.get('change_date'), 20)
        day_of_week = sanitize_input(data.get('day_of_week'), 10)
        period = data.get('period')
        original_teacher = sanitize_input(data.get('original_teacher'), 100)
        original_subject = sanitize_input(data.get('original_subject'), 100)
        original_grade = sanitize_input(data.get('original_grade'), 10)
        original_class_no = sanitize_input(data.get('original_class_no'), 10)
        new_teacher = sanitize_input(data.get('new_teacher'), 100)
        new_subject = sanitize_input(data.get('new_subject'), 100)
        change_reason = sanitize_input(data.get('change_reason'), 200)
        changed_by = sanitize_input(data.get('changed_by'), 100)

        if not school_id or not change_date or not day_of_week or period is None:
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO timetable_changes
            (school_id, member_school, change_date, day_of_week, period,
             original_teacher, original_subject, original_grade, original_class_no,
             new_teacher, new_subject, change_reason, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, member_school, change_date, day_of_week, period,
              original_teacher, original_subject, original_grade, original_class_no,
              new_teacher, new_subject, change_reason, changed_by))

        conn.commit()
        return jsonify({'success': True, 'message': '변경사항이 저장되었습니다.', 'id': cursor.lastrowid})

    except Exception as e:
        if conn: conn.rollback()
        print(f"시간표 변경 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 시간표 변경이력 조회 API
# ============================================
@timetable_bp.route('/api/timetable/changes', methods=['GET'])
def get_timetable_changes():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        change_date = sanitize_input(request.args.get('change_date'), 20)

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        q = "SELECT * FROM timetable_changes WHERE school_id = %s"
        params = [school_id]
        if change_date:
            q += " AND change_date = %s"
            params.append(change_date)
        q += " ORDER BY change_date DESC, period"

        cursor.execute(q, params)
        rows = cursor.fetchall()

        # datetime/date 직렬화
        for r in rows:
            if r.get('change_date'):
                r['change_date'] = str(r['change_date'])
            if r.get('created_at'):
                r['created_at'] = str(r['created_at'])
            if r.get('updated_at'):
                r['updated_at'] = str(r['updated_at'])

        return jsonify({'success': True, 'changes': rows, 'count': len(rows)})

    except Exception as e:
        print(f"시간표 변경이력 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 시간표 변경 취소(삭제) API
# ============================================
@timetable_bp.route('/api/timetable/change/delete', methods=['POST'])
def delete_timetable_change():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        change_id = data.get('id')
        school_id = sanitize_input(data.get('school_id'), 50)

        if not change_id or not school_id:
            return jsonify({'success': False, 'message': 'id와 school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("DELETE FROM timetable_changes WHERE id = %s AND school_id = %s",
                        (change_id, school_id))
        conn.commit()

        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': '변경이 취소되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '해당 변경 내역을 찾을 수 없습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"시간표 변경 삭제 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 학급 시간표 수동 저장 API (담임용)
# ============================================
@timetable_bp.route('/api/timetable/class/save-manual', methods=['POST'])
def save_class_timetable_manual():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        grade = sanitize_input(str(data.get('grade', '')), 10)
        class_no = sanitize_input(str(data.get('class_no', '')), 10)
        timetable = data.get('timetable', [])

        if not school_id or not grade or not class_no:
            return jsonify({'success': False, 'message': 'school_id, grade, class_no가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 해당 학급의 기존 단일 class_no 레코드 삭제
        cursor.execute(
            "DELETE FROM timetable_tea WHERE school_id = %s AND grade = %s AND class_no = %s",
            (school_id, grade, class_no)
        )

        # 새 레코드 삽입
        VALID_DAYS = {'월','화','수','목','금'}
        inserted = 0
        for item in timetable:
            day = sanitize_input(item.get('day_of_week', ''), 10)
            subject = sanitize_input(item.get('subject', ''), 50)
            member_name = sanitize_input(item.get('member_name', ''), 20)

            if not day or day not in VALID_DAYS or not subject:
                continue
            try:
                period = int(item.get('period', 0))
            except (ValueError, TypeError):
                continue
            if period < 1 or period > 10:
                continue

            cursor.execute("""
                INSERT INTO timetable_tea
                (school_id, member_school, member_name, subject, grade, class_no, class_conut, hours, day_of_week, period)
                VALUES (%s, %s, %s, %s, %s, %s, 1, 0, %s, %s)
            """, (school_id, member_school, member_name, subject, grade, class_no, day, period))
            inserted += 1

        conn.commit()
        return jsonify({'success': True, 'message': f'학급 시간표가 저장되었습니다. ({inserted}건)', 'count': inserted})

    except Exception as e:
        if conn: conn.rollback()
        print(f"학급 시간표 수동 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 교사 시간표 수동 저장 API (교과업무용)
# ============================================
# ============================================
# 시간표 스케줄 저장 API (timetablemaker용)
# ============================================
@timetable_bp.route('/api/timetable/schedule/save', methods=['POST'])
def save_timetable_schedule():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        entries = data.get('data', [])

        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})
        if not entries:
            return jsonify({'success': False, 'message': '저장할 시간표 데이터가 없습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 기존 데이터 삭제
        if school_id:
            cursor.execute("DELETE FROM timetable WHERE school_id = %s", (school_id,))
        else:
            cursor.execute("DELETE FROM timetable WHERE member_school = %s", (member_school,))

        inserted = 0
        for item in entries:
            grade = sanitize_input(str(item.get('grade', '')), 10)
            class_no = sanitize_input(str(item.get('class_no', '')), 10)
            day_of_week = sanitize_input(item.get('day_of_week', ''), 10)
            period = item.get('period')
            subject = sanitize_input(item.get('subject', ''), 100)
            member_name = sanitize_input(item.get('member_name', ''), 100)
            item_member_id = sanitize_input(item.get('member_id', ''), 100)

            if not grade or not class_no or not day_of_week or not period or not subject:
                continue

            cursor.execute("""
                INSERT INTO timetable
                (school_id, member_id, member_school, grade, class_no, day_of_week, period, subject, member_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (school_id, item_member_id, member_school, grade, class_no, day_of_week, period, subject, member_name))
            inserted += 1

        conn.commit()
        return jsonify({'success': True, 'message': f'시간표 저장 완료 ({inserted}건)', 'count': inserted})

    except Exception as e:
        if conn: conn.rollback()
        print(f"시간표 스케줄 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 시간표 스케줄 불러오기 API (timetablemaker용)
# ============================================
@timetable_bp.route('/api/timetable/schedule/load', methods=['GET'])
def load_timetable_schedule():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_school = sanitize_input(request.args.get('member_school'), 200)

        if not school_id and not member_school:
            return jsonify({'success': False, 'message': '학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        if school_id:
            cursor.execute("""
                SELECT grade, class_no, day_of_week, period, subject, member_name, member_id
                FROM timetable WHERE school_id = %s
                ORDER BY grade, class_no, FIELD(day_of_week,'월','화','수','목','금'), period
            """, (school_id,))
        else:
            cursor.execute("""
                SELECT grade, class_no, day_of_week, period, subject, member_name, member_id
                FROM timetable WHERE member_school = %s
                ORDER BY grade, class_no, FIELD(day_of_week,'월','화','수','목','금'), period
            """, (member_school,))

        data = cursor.fetchall()
        return jsonify({'success': True, 'data': data, 'count': len(data)})

    except Exception as e:
        print(f"시간표 스케줄 불러오기 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@timetable_bp.route('/api/timetable/teacher/save-manual', methods=['POST'])
def save_teacher_timetable_manual():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 100)
        member_name = sanitize_input(data.get('member_name'), 50)
        timetable = data.get('timetable', [])

        if not school_id or not member_name:
            return jsonify({'success': False, 'message': 'school_id, member_name이 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 해당 교사의 기존 레코드 삭제
        cursor.execute(
            "DELETE FROM timetable_tea WHERE school_id = %s AND member_name = %s",
            (school_id, member_name)
        )

        # 새 레코드 삽입
        VALID_DAYS = {'월','화','수','목','금'}
        inserted = 0
        for item in timetable:
            day = sanitize_input(item.get('day_of_week', ''), 10)
            subject = sanitize_input(item.get('subject', ''), 50)
            grade = sanitize_input(str(item.get('grade', '')), 5)
            class_no = sanitize_input(str(item.get('class_no', '')), 5)

            if not day or day not in VALID_DAYS or not subject:
                continue
            try:
                period = int(item.get('period', 0))
            except (ValueError, TypeError):
                continue
            if period < 1 or period > 10:
                continue

            cursor.execute("""
                INSERT INTO timetable_tea
                (school_id, member_school, member_name, subject, grade, class_no, class_conut, hours, day_of_week, period)
                VALUES (%s, %s, %s, %s, %s, %s, 1, 0, %s, %s)
            """, (school_id, member_school, member_name, subject, grade, class_no, day, period))
            inserted += 1

        conn.commit()
        return jsonify({'success': True, 'message': f'교사 시간표가 저장되었습니다. ({inserted}건)', 'count': inserted})

    except Exception as e:
        if conn: conn.rollback()
        print(f"교사 시간표 수동 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수업 교환 요청 생성 API
# ============================================
@timetable_bp.route('/api/timetable/exchange/create', methods=['POST'])
def create_timetable_exchange():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        member_school = sanitize_input(data.get('member_school'), 200)
        exchange_date = sanitize_input(data.get('exchange_date'), 20)

        requester_id = sanitize_input(data.get('requester_id'), 100)
        requester_name = sanitize_input(data.get('requester_name'), 100)
        requester_day = sanitize_input(data.get('requester_day'), 10)
        requester_period = data.get('requester_period')
        requester_subject = sanitize_input(data.get('requester_subject'), 100)
        requester_grade = sanitize_input(data.get('requester_grade'), 10)
        requester_class_no = sanitize_input(data.get('requester_class_no'), 10)

        target_id = sanitize_input(data.get('target_id'), 100)
        target_name = sanitize_input(data.get('target_name'), 100)
        target_day = sanitize_input(data.get('target_day'), 10)
        target_period = data.get('target_period')
        target_subject = sanitize_input(data.get('target_subject'), 100)
        target_grade = sanitize_input(data.get('target_grade'), 10)
        target_class_no = sanitize_input(data.get('target_class_no'), 10)

        reason = sanitize_input(data.get('reason', ''), 200)

        if not school_id or not exchange_date or not requester_id or not target_id:
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})
        if not requester_day or requester_period is None or not target_day or target_period is None:
            return jsonify({'success': False, 'message': '교환 교시 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 중복 검사: 같은 날짜+교시에 이미 pending 요청 있는지
        cursor.execute("""
            SELECT id FROM timetable_exchange
            WHERE school_id = %s AND exchange_date = %s AND status = 'pending'
              AND ((requester_id = %s AND requester_day = %s AND requester_period = %s)
                OR (target_id = %s AND target_day = %s AND target_period = %s)
                OR (requester_id = %s AND requester_day = %s AND requester_period = %s)
                OR (target_id = %s AND target_day = %s AND target_period = %s))
        """, (school_id, exchange_date,
              requester_id, requester_day, requester_period,
              requester_id, requester_day, requester_period,
              target_id, target_day, target_period,
              target_id, target_day, target_period))
        if cursor.fetchone():
            return jsonify({'success': False, 'message': '해당 교시에 이미 대기 중인 교환 요청이 있습니다.'})

        cursor.execute("""
            INSERT INTO timetable_exchange
            (school_id, member_school, exchange_date,
             requester_id, requester_name, requester_day, requester_period,
             requester_subject, requester_grade, requester_class_no,
             target_id, target_name, target_day, target_period,
             target_subject, target_grade, target_class_no,
             reason, status)
            VALUES (%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,'pending')
        """, (school_id, member_school, exchange_date,
              requester_id, requester_name, requester_day, requester_period,
              requester_subject, requester_grade, requester_class_no,
              target_id, target_name, target_day, target_period,
              target_subject, target_grade, target_class_no,
              reason))

        conn.commit()
        return jsonify({'success': True, 'message': '교환 요청이 등록되었습니다.', 'id': cursor.lastrowid})

    except Exception as e:
        if conn: conn.rollback()
        print(f"교환 요청 생성 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수업 교환 요청 목록 조회 API
# ============================================
@timetable_bp.route('/api/timetable/exchange/list', methods=['GET'])
def list_timetable_exchange():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        member_id = sanitize_input(request.args.get('member_id'), 100)
        status_filter = sanitize_input(request.args.get('status'), 20)
        exchange_date = sanitize_input(request.args.get('exchange_date'), 20)

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        q = "SELECT * FROM timetable_exchange WHERE school_id = %s"
        params = [school_id]

        if member_id:
            q += " AND (requester_id = %s OR target_id = %s)"
            params.extend([member_id, member_id])
        if status_filter and status_filter != 'all':
            q += " AND status = %s"
            params.append(status_filter)
        if exchange_date:
            q += " AND exchange_date = %s"
            params.append(exchange_date)

        q += " ORDER BY created_at DESC"
        cursor.execute(q, params)
        rows = cursor.fetchall()

        for r in rows:
            if r.get('exchange_date'):
                r['exchange_date'] = str(r['exchange_date'])
            if r.get('created_at'):
                r['created_at'] = str(r['created_at'])
            if r.get('updated_at'):
                r['updated_at'] = str(r['updated_at'])

        return jsonify({'success': True, 'data': rows, 'count': len(rows)})

    except Exception as e:
        print(f"교환 요청 목록 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수업 교환 요청 응답 (승인/거절) API
# ============================================
@timetable_bp.route('/api/timetable/exchange/respond', methods=['POST'])
def respond_timetable_exchange():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        exchange_id = data.get('exchange_id')
        school_id = sanitize_input(data.get('school_id'), 50)
        action = sanitize_input(data.get('action'), 20)
        reject_reason = sanitize_input(data.get('reject_reason', ''), 200)

        if not exchange_id or not school_id or action not in ('approve', 'reject'):
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM timetable_exchange WHERE id = %s AND school_id = %s",
                        (exchange_id, school_id))
        ex = cursor.fetchone()
        if not ex:
            return jsonify({'success': False, 'message': '교환 요청을 찾을 수 없습니다.'})
        if ex['status'] != 'pending':
            return jsonify({'success': False, 'message': '이미 처리된 요청입니다.'})

        if action == 'reject':
            cursor.execute("""UPDATE timetable_exchange SET status='rejected', reject_reason=%s
                            WHERE id=%s""", (reject_reason, exchange_id))
            conn.commit()
            return jsonify({'success': True, 'message': '교환 요청이 거절되었습니다.'})

        # approve: timetable_changes에 2개 레코드 생성
        # 레코드1: 요청자 슬롯 → 대상자가 가르침
        cursor.execute("""
            INSERT INTO timetable_changes
            (school_id, member_school, change_date, day_of_week, period,
             original_teacher, original_subject, original_grade, original_class_no,
             new_teacher, new_subject, change_reason, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, ex['member_school'], ex['exchange_date'],
              ex['requester_day'], ex['requester_period'],
              ex['requester_name'], ex['requester_subject'],
              ex['requester_grade'], ex['requester_class_no'],
              ex['target_name'], ex['requester_subject'],
              '교환수업', ex['target_name']))
        change_id_1 = cursor.lastrowid

        # 레코드2: 대상자 슬롯 → 요청자가 가르침
        cursor.execute("""
            INSERT INTO timetable_changes
            (school_id, member_school, change_date, day_of_week, period,
             original_teacher, original_subject, original_grade, original_class_no,
             new_teacher, new_subject, change_reason, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (school_id, ex['member_school'], ex['exchange_date'],
              ex['target_day'], ex['target_period'],
              ex['target_name'], ex['target_subject'],
              ex['target_grade'], ex['target_class_no'],
              ex['requester_name'], ex['target_subject'],
              '교환수업', ex['target_name']))
        change_id_2 = cursor.lastrowid

        cursor.execute("""UPDATE timetable_exchange
            SET status='approved', change_id_1=%s, change_id_2=%s
            WHERE id=%s""", (change_id_1, change_id_2, exchange_id))

        conn.commit()
        return jsonify({'success': True, 'message': '교환 요청이 승인되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"교환 요청 응답 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 수업 교환 요청 취소 API
# ============================================
@timetable_bp.route('/api/timetable/exchange/cancel', methods=['POST'])
def cancel_timetable_exchange():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        exchange_id = data.get('exchange_id')
        school_id = sanitize_input(data.get('school_id'), 50)

        if not exchange_id or not school_id:
            return jsonify({'success': False, 'message': '필수 항목이 누락되었습니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM timetable_exchange WHERE id = %s AND school_id = %s",
                        (exchange_id, school_id))
        ex = cursor.fetchone()
        if not ex:
            return jsonify({'success': False, 'message': '교환 요청을 찾을 수 없습니다.'})
        if ex['status'] not in ('pending', 'approved'):
            return jsonify({'success': False, 'message': '취소할 수 없는 상태입니다.'})

        # approved 상태면 timetable_changes 레코드도 삭제
        if ex['status'] == 'approved':
            if ex.get('change_id_1'):
                cursor.execute("DELETE FROM timetable_changes WHERE id = %s AND school_id = %s",
                                (ex['change_id_1'], school_id))
            if ex.get('change_id_2'):
                cursor.execute("DELETE FROM timetable_changes WHERE id = %s AND school_id = %s",
                                (ex['change_id_2'], school_id))

        cursor.execute("UPDATE timetable_exchange SET status='cancelled' WHERE id=%s", (exchange_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '교환 요청이 취소되었습니다.'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"교환 요청 취소 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 특정교과 편성 조회 API
# ============================================
@timetable_bp.route('/api/timetable-fixed-subject/list', methods=['GET'])
def get_fixed_subjects():
    conn = None
    cursor = None
    try:
        school_id = sanitize_input(request.args.get('school_id'), 50)
        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, grade, day_of_week, period_start, period_count, subject
            FROM timetable_fixed_subject
            WHERE school_id = %s
            ORDER BY grade, FIELD(day_of_week,'월','화','수','목','금'), period_start
        """, (school_id,))
        data = cursor.fetchall()

        return jsonify({'success': True, 'data': data})

    except Exception as e:
        print(f"특정교과 편성 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# ============================================
# 특정교과 편성 저장 API
# ============================================
@timetable_bp.route('/api/timetable-fixed-subject/save', methods=['POST'])
def save_fixed_subjects():
    conn = None
    cursor = None
    try:
        data = request.get_json()
        school_id = sanitize_input(data.get('school_id'), 50)
        items = data.get('items', [])

        if not school_id:
            return jsonify({'success': False, 'message': 'school_id가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        cursor.execute("DELETE FROM timetable_fixed_subject WHERE school_id = %s", (school_id,))

        if items:
            sql = """INSERT INTO timetable_fixed_subject
                (school_id, grade, day_of_week, period_start, period_count, subject)
                VALUES (%s, %s, %s, %s, %s, %s)"""
            rows = []
            for it in items:
                rows.append((
                    school_id,
                    sanitize_input(it.get('grade', ''), 10),
                    sanitize_input(it.get('day_of_week', ''), 10),
                    it.get('period_start', 1),
                    it.get('period_count', 1),
                    sanitize_input(it.get('subject', ''), 100)
                ))
            cursor.executemany(sql, rows)

        conn.commit()
        return jsonify({'success': True, 'message': f'{len(items)}건 저장 완료'})

    except Exception as e:
        if conn: conn.rollback()
        print(f"특정교과 편성 저장 오류: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
