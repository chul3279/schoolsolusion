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
        member_school = sanitize_input(request.args.get('member_school'), 100)
        school_id = sanitize_input(request.args.get('school_id'), 50)

        if not member_name or (not member_school and not school_id):
            return jsonify({'success': False, 'message': '로그인 정보가 없습니다.'})

        day_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
        today = day_map.get(datetime.now().weekday(), '월')
        today_date = datetime.now().strftime('%Y-%m-%d')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        # 1) 원본 시간표 조회
        if school_id:
            cursor.execute("""
                SELECT period, subject, grade, class_no
                FROM timetable_tea
                WHERE member_name = %s AND school_id = %s AND day_of_week = %s
                ORDER BY period
            """, (member_name, school_id, today))
        else:
            cursor.execute("""
                SELECT period, subject, grade, class_no
                FROM timetable_tea
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

        # 1) 원본 시간표 조회 (timetable_tea 기준, FIND_IN_SET으로 학급 매칭)
        if school_id:
            cursor.execute("""
                SELECT period, subject, member_name, grade, class_no
                FROM timetable_tea
                WHERE school_id = %s AND grade = %s
                  AND FIND_IN_SET(%s, REPLACE(class_no, ' ', ''))
                  AND day_of_week = %s
                ORDER BY period
            """, (school_id, grade, class_no, today))
        else:
            cursor.execute("""
                SELECT period, subject, member_name, grade, class_no
                FROM timetable_tea
                WHERE member_school = %s AND grade = %s
                  AND FIND_IN_SET(%s, REPLACE(class_no, ' ', ''))
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
                SELECT id, school_id, member_school, grade, class_no, class_conut,
                       day_of_week, period, subject, member_name, hours, member_birth
                FROM timetable_tea
                WHERE school_id = %s
                ORDER BY member_name, grade, class_no
            """, (school_id,))
        else:
            cursor.execute("""
                SELECT id, school_id, member_school, grade, class_no, class_conut,
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
                (school_id, member_school, member_name, subject, grade, class_no, class_conut, 
                 hours, day_of_week, period, member_birth, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """, (school_id, member_school, member_name, subject, grade, class_no, class_conut,
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
        change_date = sanitize_input(request.args.get('change_date'), 20)

        if not member_name or (not school_id and not member_school):
            return jsonify({'success': False, 'message': '교사명과 학교 정보가 필요합니다.'})

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': '데이터베이스 연결 오류'})
        cursor = conn.cursor()

        if school_id:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable_tea
                WHERE school_id = %s AND member_name = %s
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (school_id, member_name))
        else:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable_tea
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

        # class_no가 "1, 2, 3"처럼 쉼표 구분 저장되므로 FIND_IN_SET 사용
        if school_id:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable_tea
                WHERE school_id = %s AND grade = %s
                  AND FIND_IN_SET(%s, REPLACE(class_no, ' ', ''))
                  AND day_of_week IN ('월','화','수','목','금')
                ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period
            """, (school_id, grade, class_no))
        else:
            cursor.execute("""
                SELECT day_of_week, period, subject, grade, class_no, member_name
                FROM timetable_tea
                WHERE member_school = %s AND grade = %s
                  AND FIND_IN_SET(%s, REPLACE(class_no, ' ', ''))
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
