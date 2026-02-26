"""
시간표 자동 생성 엔진
- /tmp/generate_timetable.py에서 추출
- 하드코딩 제거, 모든 함수 파라미터화
- caller가 cursor/connection 관리
"""

DAYS = ['월', '화', '수', '목', '금']
DAY_IDX = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4}


def load_teachers(cursor, school_id):
    cursor.execute("SELECT * FROM timetable_tea WHERE school_id=%s", (school_id,))
    return [{'member_id': t['member_id'] or '', 'name': t['member_name'] or '',
             'subject': t['subject'] or '', 'grade': t['grade'] or '',
             'classes': t['class_no'] or '', 'class_count': int(t['class_conut'] or 0),
             'unit_hours': int(t['hours'] or 4)} for t in cursor.fetchall()]


def load_timetable_data(cursor, school_id):
    cursor.execute("SELECT * FROM timetable_data WHERE school_id=%s", (school_id,))
    rows = cursor.fetchall()
    st_map, sd_map, cd_map = {}, {}, {}
    for d in rows:
        key = f"{d['grade']}_{d['subject']}"
        st_map[key] = d.get('subject_type', '') or ''
        sd_map[key] = int(d.get('subject_demand', 0) or 0)
        cd_map[key] = int(d.get('class_demand', 0) or 0)
    return st_map, sd_map, cd_map


def load_constraints(cursor, school_id):
    cursor.execute("SELECT * FROM timetable_constraint WHERE school_id=%s", (school_id,))
    rows = cursor.fetchall()
    constraints = {}
    for c in rows:
        tk = c['member_id'] or c['member_name']
        if tk not in constraints:
            constraints[tk] = []
        constraints[tk].append({
            'day': c['day_of_week'],
            'period': int(c['period']) if c['period'] else None,
            'type': c['constraint_type']
        })
    return constraints


def load_fixed_subjects(cursor, school_id):
    cursor.execute("SELECT * FROM timetable_fixed_subject WHERE school_id=%s", (school_id,))
    return [{'grade': f['grade'], 'day': f['day_of_week'],
             'period_start': int(f['period_start']),
             'period_count': int(f['period_count'] or 1),
             'subject': f['subject']} for f in cursor.fetchall()]


def get_grade_count(grade, teachers):
    max_class = 0
    for t in teachers:
        if t['grade'] != grade:
            continue
        for c in t['classes'].replace(',', ' ').split():
            try:
                max_class = max(max_class, int(c.strip()))
            except ValueError:
                pass
    return max_class if max_class > 0 else 10


def _teacher_key(entry):
    return entry['teacher_id'] or entry['teacher_name']


def build_blocks(teachers, st_map, sd_map, cd_map, fixed_subs=None):
    if fixed_subs is None:
        fixed_subs = []
    science = {'물리학', '화학', '생명과학', '지구과학'}
    social = {'세계사', '사회와 문화', '세계시민과 지리', '현대사회와 윤리'}
    regular_groups, elective_sections = {}, {}

    for t in teachers:
        if not t['grade'] or not t['subject']:
            continue
        key = f"{t['grade']}_{t['subject']}"
        stype = st_map.get(key, '')
        classes = [c.strip() for c in t['classes'].replace(',', ' ').split() if c.strip()]
        entry = {'teacher_id': t['member_id'], 'teacher_name': t['name'],
                 'subject': t['subject'], 'classes': classes,
                 'hours_per_class': t['unit_hours']}
        if stype == '선택':
            elective_sections.setdefault(t['grade'], []).append(entry)
        else:
            if key not in regular_groups:
                regular_groups[key] = {'grade': t['grade'], 'subject': t['subject'], 'entries': []}
            regular_groups[key]['entries'].append(entry)

    blocks = []
    bid = 0
    for key, g in regular_groups.items():
        bid += 1
        blocks.append({'id': f'blk_{bid}', 'name': f"{g['grade']}학년 {g['subject']}",
                       'grade': g['grade'], 'is_elective': False, 'linked_periods': 1,
                       'entries': g['entries'],
                       'hours_per_week': g['entries'][0]['hours_per_class'] if g['entries'] else 0})

    for grade, sections in elective_sections.items():
        sci = [e for e in sections if e['subject'] in science]
        soc = [e for e in sections if e['subject'] in social]
        oth = [e for e in sections if e['subject'] not in science and e['subject'] not in social]
        regular_hours = 0
        for key, demand in sd_map.items():
            if not key.startswith(f"{grade}_"):
                continue
            cd = cd_map.get(key, 0)
            cnt = get_grade_count(grade, teachers)
            if cd >= cnt:
                regular_hours += demand
        fixed_hours = sum(fs['period_count'] for fs in fixed_subs
                         if fs['grade'] == grade or fs['grade'] == 'all')
        elective_hours = max(0, 35 - regular_hours - fixed_hours)
        if sci:
            bid += 1
            blocks.append({'id': f'elec_sci_{bid}', 'name': f"{grade}학년 과학탐구",
                           'grade': grade, 'is_elective': True, 'linked_periods': 1,
                           'entries': sci, 'hours_per_week': elective_hours // 2})
        if soc:
            bid += 1
            blocks.append({'id': f'elec_soc_{bid}', 'name': f"{grade}학년 사회탐구",
                           'grade': grade, 'is_elective': True, 'linked_periods': 1,
                           'entries': soc, 'hours_per_week': elective_hours - elective_hours // 2})
        if oth:
            bid += 1
            blocks.append({'id': f'elec_other_{bid}', 'name': f"{grade}학년 기타선택",
                           'grade': grade, 'is_elective': True, 'linked_periods': 1,
                           'entries': oth, 'hours_per_week': elective_hours})
    return blocks


def _get_max_consecutive(block, day, start_p, linked, schedule, dmp, grade, class_cnt):
    max_c = 0
    if block['is_elective']:
        affected = [str(i) for i in range(1, class_cnt + 1)]
    else:
        affected = list(set(cls for e in block['entries'] for cls in e['classes']))
    for cls in affected:
        ck = f"{grade}_{cls}"
        sched = schedule.get(ck, {})
        entry = next((e for e in block['entries'] if cls in e['classes']), None)
        subj = entry['subject'] if entry else block['entries'][0]['subject'] if block['entries'] else ''
        lo, hi = start_p, start_p + linked - 1
        p = start_p - 1
        while p >= 1 and sched.get(f"{day}_{p}", {}).get('subject') == subj:
            lo = p
            p -= 1
        p = start_p + linked
        while p <= dmp[day] and sched.get(f"{day}_{p}", {}).get('subject') == subj:
            hi = p
            p += 1
        max_c = max(max_c, hi - lo + 1)
    return max_c


def _place_block(block, day, period, schedule, busy, grade, class_cnt):
    linked = block['linked_periods']
    for p in range(linked):
        ap = period + p
        cell = f"{day}_{ap}"
        lpos = None
        if linked > 1:
            lpos = 'top' if p == 0 else ('bottom' if p == linked - 1 else 'middle')
        if block['is_elective']:
            for c in range(1, class_cnt + 1):
                ck = f"{grade}_{c}"
                if ck not in schedule:
                    schedule[ck] = {}
                entry = next((e for e in block['entries'] if str(c) in e['classes']), None)
                schedule[ck][cell] = {
                    'block_id': block['id'],
                    'subject': entry['subject'] if entry else '선택',
                    'teacher': entry['teacher_name'] if entry else '-',
                    'teacher_id': entry['teacher_id'] if entry else '',
                    'is_elective': True, 'linked_pos': lpos}
        else:
            for entry in block['entries']:
                for cls in entry['classes']:
                    ck = f"{grade}_{cls}"
                    if ck not in schedule:
                        schedule[ck] = {}
                    schedule[ck][cell] = {
                        'block_id': block['id'], 'subject': entry['subject'],
                        'teacher': entry['teacher_name'], 'teacher_id': entry['teacher_id'],
                        'is_elective': False, 'linked_pos': lpos}
        for entry in block['entries']:
            tk = _teacher_key(entry)
            busy.setdefault(tk, set()).add(cell)


def run_auto_generate(blocks, fixed_subjects, constraints, teachers):
    """시간표 자동 생성. schedule dict + 통계 반환."""
    dmp = [7, 7, 7, 7, 7]
    target_grades = sorted(set(b['grade'] for b in blocks))
    schedule = {}
    busy = {}

    # 1. 고정 교과 선배치
    fixed_count = 0
    for fs in fixed_subjects:
        grades = ['1', '2', '3'] if fs['grade'] == 'all' else [fs['grade']]
        di = DAY_IDX.get(fs['day'])
        if di is None:
            continue
        for g in grades:
            if g not in target_grades:
                continue
            cc = get_grade_count(g, teachers)
            for c in range(1, cc + 1):
                ck = f"{g}_{c}"
                schedule.setdefault(ck, {})
                for p in range(fs['period_count']):
                    cell = f"{di}_{fs['period_start'] + p}"
                    lpos = None
                    if fs['period_count'] > 1:
                        lpos = 'top' if p == 0 else ('bottom' if p == fs['period_count'] - 1 else 'middle')
                    schedule[ck][cell] = {
                        'block_id': None, 'subject': fs['subject'], 'teacher': '(고정)',
                        'teacher_id': '', 'is_elective': False, 'is_fixed': True, 'linked_pos': lpos}
            fixed_count += 1

    # 2. 블록 정렬 (선택과목 우선 → 시수 많은 순)
    tblocks = [b for b in blocks if b['grade'] in target_grades]
    tblocks.sort(key=lambda b: (-int(b['is_elective']), -b['hours_per_week']))

    results = []
    total_placed = total_needed = total_cw = 0

    for block in tblocks:
        placed = 0
        needed = block['hours_per_week']
        total_needed += needed
        linked = block['linked_periods']
        grade = block['grade']
        cc = get_grade_count(grade, teachers)

        max_p = max(dmp)
        shuffled = [(d, p) for p in range(1, max_p + 1) for d in range(5) if p <= dmp[d]]
        day_count = {}
        cw = 0

        for _pass in (1, 2):
            mcl = 2 if _pass == 1 else 3
            for d, p in shuffled:
                if placed >= needed:
                    break
                if day_count.get(d, 0) >= 2:
                    continue
                if p + linked - 1 > dmp[d]:
                    continue

                ok = True
                for lp in range(linked):
                    cell = f"{d}_{p + lp}"
                    if block['is_elective']:
                        for c in range(1, cc + 1):
                            if schedule.get(f"{grade}_{c}", {}).get(cell):
                                ok = False
                                break
                    else:
                        for e in block['entries']:
                            for cls in e['classes']:
                                if schedule.get(f"{grade}_{cls}", {}).get(cell):
                                    ok = False
                                    break
                            if not ok:
                                break
                    if not ok:
                        break
                    for e in block['entries']:
                        if cell in busy.get(_teacher_key(e), set()):
                            ok = False
                            break
                    if not ok:
                        break
                    for e in block['entries']:
                        tk = _teacher_key(e)
                        for con in constraints.get(tk, []):
                            if con['day'] == DAYS[d] and (con['period'] is None or con['period'] == p + lp):
                                ok = False
                                break
                        if not ok:
                            break
                    if not ok:
                        break

                if ok:
                    mc = _get_max_consecutive(block, d, p, linked, schedule, dmp, grade, cc)
                    if mc > mcl:
                        ok = False

                if ok:
                    _place_block(block, d, p, schedule, busy, grade, cc)
                    placed += linked
                    day_count[d] = day_count.get(d, 0) + linked
                    if _pass == 2:
                        cw += linked
            if placed >= needed:
                break

        total_placed += placed
        total_cw += cw
        results.append({'name': block['name'], 'is_elective': block['is_elective'],
                        'needed': needed, 'placed': placed, 'ok': placed >= needed, 'cw': cw})

    return schedule, results, total_placed, total_needed, fixed_count, total_cw


def save_timetable(cursor, school_id, schedule):
    """schedule dict를 timetable 테이블에 저장. commit은 caller가."""
    day_names = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금'}
    cursor.execute("DELETE FROM timetable WHERE school_id=%s", (school_id,))
    cursor.execute("SELECT member_school FROM timetable_tea WHERE school_id=%s LIMIT 1", (school_id,))
    row = cursor.fetchone()
    ms = row['member_school'] if row else ''
    cnt = 0
    for ck, cells in schedule.items():
        g, c = ck.split('_')
        for cell_id, data in cells.items():
            di, period = cell_id.split('_')
            cursor.execute(
                """INSERT INTO timetable (school_id, member_school, member_id, day_of_week,
                    grade, class_no, period, subject, member_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (school_id, ms, data.get('teacher_id', ''), day_names[int(di)],
                 g, c, period, data['subject'], data['teacher']))
            cnt += 1
    return cnt
