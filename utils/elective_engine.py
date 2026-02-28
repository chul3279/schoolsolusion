"""
선택과목 교육반 배정 엔진 (동적 밴드 구조)
- 사용자 지정 band_group을 반영한 밴드 배정
- caller가 cursor/connection 관리
"""
import random
from collections import defaultdict

BAND_NAMES = list('ABCDEFGHIJKLMNOP')  # 최대 16밴드


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


def validate_band_balance(cursor, school_id, grade, band_count=4):
    """밴드그룹별 교육반 총수가 원반 수의 배수인지 검증.
    규칙: 선택군 내 교육반 총수 = 원반 수 × N (N=밴드 수, 자연수)
    예) 원반 10개, 선택군에 과목 8개 → 교육반 총수는 10, 20, 30, 40... 이어야 함"""
    errors = []

    # 원반 수 조회
    cursor.execute(
        """SELECT COUNT(DISTINCT class_no) as cnt FROM timetable_stu
           WHERE school_id=%s AND grade=%s AND class_no IS NOT NULL AND class_no != ''""",
        (school_id, grade))
    row = cursor.fetchone()
    home_classes = row['cnt'] if row else 0
    if home_classes == 0:
        return errors

    # 선택과목의 band_group 조회
    cursor.execute(
        """SELECT subject, band_group FROM timetable_data
           WHERE school_id=%s AND grade=%s AND subject_type='선택' AND band_group IS NOT NULL AND band_group != ''""",
        (school_id, grade))
    subject_band = {}
    for r in cursor.fetchall():
        subject_band[r['subject']] = r['band_group']

    if not subject_band:
        return errors

    # 과목별 교육반 수 조회 (timetable_tea 기준)
    elective_subjects = tuple(subject_band.keys())
    cursor.execute(
        """SELECT subject, COUNT(*) as group_cnt FROM timetable_tea
           WHERE school_id=%s AND grade=%s AND subject IN %s
           GROUP BY subject""",
        (school_id, grade, elective_subjects))
    subject_groups_cnt = {r['subject']: r['group_cnt'] for r in cursor.fetchall()}

    # band_group별 합산
    band_totals = defaultdict(lambda: {'total': 0, 'subjects': []})
    for sub, bg in subject_band.items():
        cnt = subject_groups_cnt.get(sub, 0)
        band_totals[bg]['total'] += cnt
        band_totals[bg]['subjects'].append({'subject': sub, 'groups': cnt})

    # 검증: 각 band_group의 교육반 총수가 원반 수의 배수인지
    for bg in sorted(band_totals.keys()):
        info = band_totals[bg]
        total = info['total']
        if total == 0:
            continue
        remainder = total % home_classes
        if remainder != 0:
            need = home_classes - remainder
            sub_detail = ', '.join(
                f"{s['subject']}({s['groups']}반)" for s in info['subjects'])
            # 가능한 교육반 수 예시
            lower = (total // home_classes) * home_classes
            upper = lower + home_classes
            errors.append({
                'band_group': bg,
                'total_groups': total,
                'home_classes': home_classes,
                'remainder': remainder,
                'need': need,
                'subjects': sub_detail,
                'message': (
                    f"선택군 {bg} 오류: 교육반 합계 {total}개는 "
                    f"학급 수({home_classes})의 배수가 아닙니다.\n"
                    f"  현재: {sub_detail}\n"
                    f"  교육반 합계는 {lower}개 또는 {upper}개로 조정하세요.\n"
                    f"  (교육반 수 = 선택과목 반 수의 합 = 학급 수 × 밴드 수)"
                )
            })

    return errors


def assign_groups_to_bands(groups, subject_groups, subject_band_map=None, home_classes=0):
    """교육반을 밴드에 분산 배정 (사용자 band_group 반영 + 교사 충돌 회피)

    subject_band_map: {과목명: band_group라벨} (timetable_data에서 사용자가 설정)
    home_classes: 원반(홈룸) 수
    """
    teacher_gids = defaultdict(list)
    for g in groups:
        teacher_gids[g['teacher_id']].append(g)

    # band_group 미설정이면 기존 4밴드 폴백
    if not subject_band_map or home_classes <= 0:
        all_groups = []
        for sub in sorted(subject_groups.keys()):
            all_groups.extend(subject_groups[sub])
        band_labels = BAND_NAMES[:4]
        for i, g in enumerate(all_groups):
            base = i % 4
            for attempt in range(4):
                candidate = band_labels[(base + attempt) % 4]
                conflict = any(
                    og['id'] != g['id'] and og.get('band') == candidate
                    for og in teacher_gids[g['teacher_id']]
                )
                if not conflict:
                    g['band'] = candidate
                    break
            else:
                g['band'] = band_labels[base]
        return

    # band_group별로 과목 분류
    bg_subjects = defaultdict(list)
    unassigned = []
    for sub in subject_groups:
        bg = subject_band_map.get(sub)
        if bg:
            bg_subjects[bg].append(sub)
        else:
            unassigned.append(sub)

    band_idx = 0  # 전역 밴드 라벨 인덱스 (A, B, C, ... 순차 사용)

    def _assign_to_bands(group_list, band_labels, num_bands):
        """그룹을 밴드에 분산 배정 (교사 충돌 최소화).
        제약이 많은 교사(그룹 수가 많은)를 먼저 배정하여 충돌 회피율을 높임."""
        # 교사 제약이 많은 그룹을 먼저 처리
        sorted_groups = sorted(group_list,
                               key=lambda g: -len(teacher_gids[g['teacher_id']]))
        for g in sorted_groups:
            base = group_list.index(g) % num_bands
            assigned = False
            for attempt in range(num_bands):
                candidate = band_labels[(base + attempt) % num_bands]
                conflict = any(
                    og['id'] != g['id'] and og.get('band') == candidate
                    for og in teacher_gids[g['teacher_id']]
                )
                if not conflict:
                    g['band'] = candidate
                    assigned = True
                    break
            if not assigned:
                # 충돌 최소화: 가장 충돌이 적은 밴드 선택
                conflict_counts = []
                for ci in range(num_bands):
                    cand = band_labels[(base + ci) % num_bands]
                    cnt = sum(1 for og in teacher_gids[g['teacher_id']]
                              if og['id'] != g['id'] and og.get('band') == cand)
                    conflict_counts.append((cnt, cand))
                conflict_counts.sort()
                g['band'] = conflict_counts[0][1]

    for bg in sorted(bg_subjects.keys()):
        subs = bg_subjects[bg]
        total = sum(len(subject_groups[s]) for s in subs)
        num_bands = max(1, total // home_classes)

        band_labels = BAND_NAMES[band_idx:band_idx + num_bands]
        band_idx += num_bands

        bg_groups = []
        for sub in sorted(subs):
            bg_groups.extend(subject_groups[sub])

        _assign_to_bands(bg_groups, band_labels, num_bands)

    # band_group 미지정 과목: 남은 밴드 라벨 사용
    if unassigned:
        un_groups = []
        for sub in sorted(unassigned):
            un_groups.extend(subject_groups[sub])
        num_fallback = max(1, len(un_groups) // max(home_classes, 1))
        if num_fallback < 1:
            num_fallback = 1
        fallback_labels = BAND_NAMES[band_idx:band_idx + num_fallback]
        _assign_to_bands(un_groups, fallback_labels, num_fallback)


def assign_students_to_groups(students, subject_groups, group_by_id, seed=None):
    """학생을 교육반에 배정 (밴드 분산 백트래킹)"""
    if seed is not None:
        random.seed(seed)

    if len(subject_groups) == 0:
        return {'success': 0, 'fail': 0, 'fail_students': []}

    def find_valid_assignment(stu):
        # 교육반이 존재하는 과목만 필터 (timetable_tea에 없는 과목은 건너뜀)
        subs = [s for s in stu['electives'] if s in subject_groups]
        if not subs:
            return subs, None
        stu_cnt = len(subs)
        options = []
        for sub in subs:
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

        return subs, backtrack(0, set(), [])

    random.shuffle(students)
    success = 0
    fail = 0
    fail_students = []

    for stu in students:
        subs, result = find_valid_assignment(stu)
        if result:
            for i, gid in enumerate(result):
                sub = subs[i]
                stu['group_map'][sub] = gid
                group_by_id[gid]['students'].append(stu['member_id'])
            success += 1
        else:
            fail += 1
            fail_students.append(stu)

    return {'success': success, 'fail': fail, 'fail_students': fail_students}


def _build_bands_config(groups, slot_count):
    """실제 배정된 밴드를 기반으로 슬롯 배분 (동적 밴드 수 지원)"""
    used_bands = sorted(set(g['band'] for g in groups if g.get('band')))
    if not used_bands:
        return {}
    band_count = len(used_bands)
    slots_per_band = slot_count // band_count
    remainder = slot_count % band_count
    bands = {}
    idx = 0
    for i, bn in enumerate(used_bands):
        size = slots_per_band + (1 if i < remainder else 0)
        bands[bn] = list(range(idx, idx + size))
        idx += size
    return bands


def assign_slots_to_groups(groups, group_by_id, slot_count):
    """각 그룹에 자기 밴드의 슬롯 배정"""
    bands = _build_bands_config(groups, slot_count)
    teacher_groups_map = defaultdict(list)
    for g in groups:
        teacher_groups_map[g['teacher_id']].append(g)

    for bn, band_slots in bands.items():
        if not band_slots:
            continue
        band_groups = [g for g in groups if g['band'] == bn]
        teacher_in_band = defaultdict(list)
        for g in band_groups:
            teacher_in_band[g['teacher_id']].append(g)

        for tid, tgs in teacher_in_band.items():
            hours = tgs[0].get('hours', 3) or 3
            if len(tgs) == 1:
                tgs[0]['slots'] = band_slots[:hours]
            else:
                for i, tg in enumerate(tgs):
                    h = tg.get('hours', 3) or 3
                    tg['slots'] = [band_slots[(i + j) % len(band_slots)] for j in range(h)]

        for g in band_groups:
            if not g['slots']:
                h = g.get('hours', 3) or 3
                g['slots'] = band_slots[:h]


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

    # 기존 선택 슬롯 삭제 (파라미터 바인딩으로 SQL 인젝션 방지)
    if slot_positions:
        conds = ' OR '.join(['(day_of_week=%s AND period=%s)'] * len(slot_positions))
        params = [school_id, grade]
        for d, p in slot_positions:
            params.extend([d, str(p)])
        cursor.execute(
            f"DELETE FROM timetable WHERE school_id=%s AND grade=%s AND ({conds})",
            tuple(params))

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

    # 밴드→시간대 매핑 저장 (학생 개인 시간표 조회용)
    cursor.execute("""CREATE TABLE IF NOT EXISTS timetable_band_slots (
        id INT AUTO_INCREMENT PRIMARY KEY,
        school_id VARCHAR(50), grade VARCHAR(10),
        band VARCHAR(5), day_of_week VARCHAR(5), period VARCHAR(5),
        INDEX idx_school_grade (school_id, grade)
    )""")
    cursor.execute("DELETE FROM timetable_band_slots WHERE school_id=%s AND grade=%s",
                   (school_id, grade))
    bands_config = _build_bands_config(groups, len(slot_positions))
    for band_name, slot_indices in bands_config.items():
        for si in slot_indices:
            if si < len(slot_positions):
                day, period = slot_positions[si]
                cursor.execute(
                    """INSERT INTO timetable_band_slots
                        (school_id, grade, band, day_of_week, period)
                        VALUES (%s,%s,%s,%s,%s)""",
                    (school_id, grade, band_name, day, str(period)))

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

    # Phase 0: 밴드 균형 검증 — 실패 시 즉시 중단
    band_errors = validate_band_balance(cursor, school_id, grade)
    if band_errors:
        return {
            'status': 'error',
            'error_type': 'band_balance',
            'message': '선택군 교육반 수가 학급 수의 배수가 아닙니다. 5단계(교사 수급)에서 교육반 수를 조정하세요.',
            'band_errors': [e['message'] for e in band_errors],
            'details': band_errors
        }

    # 사용자 band_group 설정 + 원반 수 조회
    cursor.execute(
        """SELECT subject, band_group FROM timetable_data
           WHERE school_id=%s AND grade=%s AND subject_type='선택'
           AND band_group IS NOT NULL AND band_group != ''""",
        (school_id, grade))
    subject_band_map = {r['subject']: r['band_group'] for r in cursor.fetchall()}

    cursor.execute(
        """SELECT COUNT(DISTINCT class_no) as cnt FROM timetable_stu
           WHERE school_id=%s AND grade=%s AND class_no IS NOT NULL AND class_no != ''""",
        (school_id, grade))
    hc_row = cursor.fetchone()
    home_classes = hc_row['cnt'] if hc_row else 0

    # Phase 1: 밴드 배정 (사용자 band_group 반영)
    assign_groups_to_bands(groups, subject_groups, subject_band_map, home_classes)

    # Phase 2: 학생 배정
    assign_result = assign_students_to_groups(students, subject_groups, group_by_id, seed=seed)

    # Phase 3: 슬롯 배정
    assign_slots_to_groups(groups, group_by_id, len(slot_positions))

    # Phase 4: 충돌 검증
    conflicts = validate_conflicts(students, group_by_id)

    # Phase 5: 저장 (학생 배정 실패/충돌 0일 때. 교사 충돌은 경고만)
    saved = False
    save_info = {}
    if (conflicts['student_conflicts'] == 0 and assign_result['fail'] == 0):
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
        'subject_band_map': subject_band_map,
        'band_warnings': [],  # 검증 통과 시 비어있음 (실패 시 조기반환)
        'fail_students': [
            {'class_no': s['class_no'], 'num': s['num'], 'name': s['name'],
             'electives': s['electives']}
            for s in assign_result['fail_students'][:10]
        ]
    }
