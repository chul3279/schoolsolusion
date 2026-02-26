"""
선택과목 교육반 배정 엔진 (4밴드 구조)
- /tmp/rebuild_elective_v3.py에서 추출
- 하드코딩 제거, 모든 함수 파라미터화
- caller가 cursor/connection 관리
"""
import random
from collections import defaultdict

BAND_NAMES = ['A', 'B', 'C', 'D']


def detect_elective_subjects(cursor, school_id, grade):
    """timetable_data에서 선택과목 자동 탐지"""
    cursor.execute(
        "SELECT subject FROM timetable_data WHERE school_id=%s AND grade=%s AND subject_type='선택'",
        (school_id, grade))
    return {r['subject'] for r in cursor.fetchall()}


def load_elective_groups(cursor, school_id, grade, elective_subjects):
    """교육반(timetable_tea) 로드. (subject_groups, group_by_id, groups) 반환"""
    if not elective_subjects:
        return {}, {}, []
    cursor.execute(
        """SELECT member_id, member_name, subject, class_no, hours
           FROM timetable_tea WHERE school_id=%s AND grade=%s
           AND subject IN %s ORDER BY subject, CAST(class_no AS UNSIGNED)""",
        (school_id, grade, tuple(elective_subjects)))

    subject_groups = defaultdict(list)
    group_by_id = {}
    gid = 0
    for r in cursor.fetchall():
        gid += 1
        g = {'id': gid, 'subject': r['subject'], 'group_no': r['class_no'],
             'teacher_id': r['member_id'], 'teacher_name': r['member_name'],
             'hours': int(r['hours']), 'students': [], 'band': None, 'slots': []}
        subject_groups[g['subject']].append(g)
        group_by_id[gid] = g

    groups = list(group_by_id.values())
    return subject_groups, group_by_id, groups


def load_students(cursor, school_id, grade, elective_subjects):
    """학생+선택과목 로드"""
    cursor.execute(
        "SELECT * FROM timetable_stu WHERE school_id=%s AND grade=%s ORDER BY class_no, student_num",
        (school_id, grade))
    students = []
    for s in cursor.fetchall():
        elecs = [s.get(f'subject{i}') for i in range(1, 13)
                 if s.get(f'subject{i}') and s.get(f'subject{i}') in elective_subjects]
        students.append({
            'member_id': s['member_id'], 'name': s['member_name'],
            'class_no': s['class_no'], 'num': s['student_num'],
            'electives': elecs, 'group_map': {}
        })
    return students


def find_slot_positions(cursor, school_id, grade, elective_subjects):
    """시간표에서 선택과목 슬롯 위치 탐색"""
    if not elective_subjects:
        return []
    cursor.execute(
        """SELECT DISTINCT day_of_week, period FROM timetable
           WHERE school_id=%s AND grade=%s AND class_no='1'
           AND (subject IN %s OR subject='선택')
           ORDER BY FIELD(day_of_week,'월','화','수','목','금'), period""",
        (school_id, grade, tuple(elective_subjects)))
    return [(r['day_of_week'], int(r['period'])) for r in cursor.fetchall()]


def assign_groups_to_bands(groups, subject_groups, band_count=4):
    """교육반을 밴드에 분산 배정 (교사 충돌 회피)"""
    band_names = BAND_NAMES[:band_count]
    teacher_gids = defaultdict(list)
    for g in groups:
        teacher_gids[g['teacher_id']].append(g)

    for sub in sorted(subject_groups.keys()):
        gs = subject_groups[sub]
        for i, g in enumerate(gs):
            base_band = i % band_count
            assigned_band = base_band
            for attempt in range(band_count):
                candidate = band_names[(base_band + attempt) % band_count]
                conflict = False
                for other_g in teacher_gids[g['teacher_id']]:
                    if other_g['id'] != g['id'] and other_g.get('band') == candidate:
                        conflict = True
                        break
                if not conflict:
                    assigned_band = (base_band + attempt) % band_count
                    break
            g['band'] = band_names[assigned_band]


def assign_students_to_groups(students, subject_groups, group_by_id, seed=None):
    """학생을 교육반에 배정 (밴드 분산 백트래킹)"""
    if seed is not None:
        random.seed(seed)

    if len(subject_groups) == 0:
        return {'success': 0, 'fail': 0, 'fail_students': []}

    def find_valid_assignment(stu):
        subs = stu['electives']
        if not subs:
            return None
        stu_cnt = len(subs)
        options = []
        for sub in subs:
            if sub not in subject_groups:
                return None
            opts = [(g['band'], g['id']) for g in subject_groups[sub]]
            options.append(opts)

        def backtrack(idx, used_bands, assignment):
            if idx == stu_cnt:
                return assignment[:]
            opts = sorted(options[idx], key=lambda x: len(group_by_id[x[1]]['students']))
            for band, gid in opts:
                if band not in used_bands:
                    assignment.append(gid)
                    result = backtrack(idx + 1, used_bands | {band}, assignment)
                    if result:
                        return result
                    assignment.pop()
            return None

        return backtrack(0, set(), [])

    random.shuffle(students)
    success = 0
    fail = 0
    fail_students = []

    for stu in students:
        result = find_valid_assignment(stu)
        if result:
            for i, gid in enumerate(result):
                sub = stu['electives'][i]
                stu['group_map'][sub] = gid
                group_by_id[gid]['students'].append(stu['member_id'])
            success += 1
        else:
            fail += 1
            fail_students.append(stu)

    return {'success': success, 'fail': fail, 'fail_students': fail_students}


def _build_bands_config(slot_count):
    """슬롯 수에 따라 밴드 구성 자동 생성"""
    band_count = min(4, slot_count // 3) if slot_count >= 3 else 1
    slots_per_band = slot_count // band_count
    remainder = slot_count % band_count
    bands = {}
    idx = 0
    for i in range(band_count):
        size = slots_per_band + (1 if i < remainder else 0)
        bands[BAND_NAMES[i]] = list(range(idx, idx + size))
        idx += size
    return bands


def assign_slots_to_groups(groups, group_by_id, slot_count):
    """각 그룹에 자기 밴드의 슬롯 중 3개 배정"""
    bands = _build_bands_config(slot_count)
    teacher_groups_map = defaultdict(list)
    for g in groups:
        teacher_groups_map[g['teacher_id']].append(g)

    for bn in BAND_NAMES:
        if bn not in bands:
            continue
        band_slots = bands[bn]
        band_groups = [g for g in groups if g['band'] == bn]
        teacher_in_band = defaultdict(list)
        for g in band_groups:
            teacher_in_band[g['teacher_id']].append(g)

        for tid, tgs in teacher_in_band.items():
            if len(tgs) == 1:
                tgs[0]['slots'] = band_slots[:3]
            else:
                for i, tg in enumerate(tgs):
                    start = i
                    tg['slots'] = [band_slots[(start + j) % len(band_slots)] for j in range(3)]

        for g in band_groups:
            if not g['slots']:
                g['slots'] = band_slots[:3]


def validate_conflicts(students, group_by_id):
    """학생/교사 시간 충돌 검증"""
    teacher_groups_map = defaultdict(list)
    for g in group_by_id.values():
        teacher_groups_map[g['teacher_id']].append(g)

    stu_conflicts = 0
    for stu in students:
        if not stu['group_map']:
            continue
        used_slots = {}
        for sub, gid in stu['group_map'].items():
            g = group_by_id[gid]
            for si in g['slots']:
                if si in used_slots:
                    stu_conflicts += 1
                used_slots[si] = sub

    tea_conflicts = 0
    for tid, tgs in teacher_groups_map.items():
        slot_map = defaultdict(list)
        for g in tgs:
            for si in g['slots']:
                slot_map[si].append(g)
        for si, gs_in in slot_map.items():
            if len(gs_in) > 1:
                tea_conflicts += 1

    return {'student_conflicts': stu_conflicts, 'teacher_conflicts': tea_conflicts}


def save_results(cursor, school_id, grade, groups, students, slot_positions, group_by_id):
    """교육반 배정 결과 DB 저장. commit은 caller가."""
    cursor.execute("SELECT member_school FROM timetable_tea WHERE school_id=%s LIMIT 1", (school_id,))
    ms_row = cursor.fetchone()
    ms = ms_row['member_school'] if ms_row else ''

    # 기존 선택 슬롯 삭제
    if slot_positions:
        conds = [f"(day_of_week='{d}' AND period='{p}')" for d, p in slot_positions]
        cursor.execute(
            f"DELETE FROM timetable WHERE school_id=%s AND grade=%s AND ({' OR '.join(conds)})",
            (school_id, grade))

    # 새 시간표 삽입
    homerooms = sorted(set(s['class_no'] for s in students))
    insert_count = 0
    for si in range(len(slot_positions)):
        day, period = slot_positions[si]
        for hc in homerooms:
            hc_stus = [s for s in students if s['class_no'] == hc]
            sub_counts = defaultdict(lambda: {'count': 0, 'teacher': '', 'tid': ''})
            for stu in hc_stus:
                for sub, gid in stu['group_map'].items():
                    g = group_by_id[gid]
                    if si in g['slots']:
                        sub_counts[sub]['count'] += 1
                        sub_counts[sub]['teacher'] = g['teacher_name']
                        sub_counts[sub]['tid'] = g['teacher_id']
                        break

            if sub_counts:
                best = max(sub_counts.keys(), key=lambda s: sub_counts[s]['count'])
                subj = best
                teacher = sub_counts[best]['teacher']
                tid = sub_counts[best]['tid']
            else:
                subj, teacher, tid = '자습', '-', ''

            cursor.execute(
                """INSERT INTO timetable
                    (school_id, member_school, member_id, day_of_week,
                     grade, class_no, period, subject, member_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (school_id, ms, tid, day, grade, hc, str(period), subj, teacher))
            insert_count += 1

    # timetable_stu_group 저장
    cursor.execute("""CREATE TABLE IF NOT EXISTS timetable_stu_group (
        id INT AUTO_INCREMENT PRIMARY KEY,
        school_id VARCHAR(50), member_id VARCHAR(50), member_name VARCHAR(100),
        grade VARCHAR(10), homeroom_class VARCHAR(10), student_num VARCHAR(10),
        subject VARCHAR(100), group_no VARCHAR(10), band VARCHAR(5),
        teacher_name VARCHAR(100), teacher_id VARCHAR(50),
        created_at DATETIME DEFAULT NOW(),
        INDEX idx_school_grade (school_id, grade), INDEX idx_member (member_id)
    )""")
    cursor.execute("DELETE FROM timetable_stu_group WHERE school_id=%s AND grade=%s",
                   (school_id, grade))

    mapping_count = 0
    for stu in students:
        for sub, gid in stu['group_map'].items():
            g = group_by_id[gid]
            cursor.execute(
                """INSERT INTO timetable_stu_group
                    (school_id, member_id, member_name, grade, homeroom_class, student_num,
                     subject, group_no, band, teacher_name, teacher_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (school_id, stu['member_id'], stu['name'], grade, stu['class_no'],
                 stu['num'], sub, g['group_no'], g['band'], g['teacher_name'], g['teacher_id']))
            mapping_count += 1

    return {'timetable_inserted': insert_count, 'mappings_saved': mapping_count}


def run_elective_pipeline(cursor, school_id, grade, seed=42):
    """교육반 배정 전체 파이프라인. 단일 호출로 모든 단계 실행."""
    elective_subjects = detect_elective_subjects(cursor, school_id, grade)
    if not elective_subjects:
        return {'skipped': True, 'reason': f'{grade}학년 선택과목 없음'}

    subject_groups, group_by_id, groups = load_elective_groups(
        cursor, school_id, grade, elective_subjects)
    if not groups:
        return {'skipped': True, 'reason': f'{grade}학년 교육반 없음'}

    students = load_students(cursor, school_id, grade, elective_subjects)
    if not students:
        return {'skipped': True, 'reason': f'{grade}학년 학생 없음'}

    slot_positions = find_slot_positions(cursor, school_id, grade, elective_subjects)
    if not slot_positions:
        return {'skipped': True, 'reason': f'{grade}학년 선택과목 슬롯 없음'}

    # Phase 1: 밴드 배정
    assign_groups_to_bands(groups, subject_groups)

    # Phase 2: 학생 배정
    assign_result = assign_students_to_groups(students, subject_groups, group_by_id, seed=seed)

    # Phase 3: 슬롯 배정
    assign_slots_to_groups(groups, group_by_id, len(slot_positions))

    # Phase 4: 충돌 검증
    conflicts = validate_conflicts(students, group_by_id)

    # Phase 5: 저장 (충돌 0일 때만)
    saved = False
    save_info = {}
    if (conflicts['student_conflicts'] == 0 and
            conflicts['teacher_conflicts'] == 0 and
            assign_result['fail'] == 0):
        save_info = save_results(
            cursor, school_id, grade, groups, students, slot_positions, group_by_id)
        saved = True

    # 교육반별 학생수 통계
    group_stats = {}
    for sub in sorted(elective_subjects):
        gs = subject_groups[sub]
        group_stats[sub] = [{'group_no': g['group_no'], 'band': g['band'],
                             'teacher': g['teacher_name'], 'count': len(g['students'])}
                            for g in gs]

    return {
        'skipped': False,
        'total_students': len(students),
        'success': assign_result['success'],
        'fail': assign_result['fail'],
        'student_conflicts': conflicts['student_conflicts'],
        'teacher_conflicts': conflicts['teacher_conflicts'],
        'groups_count': len(groups),
        'slots_count': len(slot_positions),
        'saved': saved,
        'save_info': save_info,
        'group_stats': group_stats,
        'fail_students': [
            {'class_no': s['class_no'], 'num': s['num'], 'name': s['name'],
             'electives': s['electives']}
            for s in assign_result['fail_students'][:10]
        ]
    }
