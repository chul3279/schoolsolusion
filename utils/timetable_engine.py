"""
시간표 자동 생성 엔진
- 슬롯 분산 배치 + 다중 시도 (최선 결과 선택)
- 교사 연속수업 체크 (과목 무관, 최대 4연속)
- 파라미터화 (주당 시수, 일별 교시)
- 선택과목 분류를 DB band_group 기반으로 동적 처리
- caller가 cursor/connection 관리
"""
import random
import copy

DAYS = ['월', '화', '수', '목', '금']
DAY_IDX = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4}

DEFAULT_DMP = [7, 7, 7, 7, 7]   # 요일별 최대 교시
DEFAULT_WEEKLY_HOURS = 35        # 주당 수업 시수
MAX_TEACHER_CONSECUTIVE = 4      # 교사 연속수업 제한 (과목 무관)
MAX_SAME_SUBJECT_CONSECUTIVE = 2 # 같은 과목 연속 제한 (Pass 1)
N_ATTEMPTS = 10                  # 다중 시도 횟수


def load_teachers(cursor, school_id):
    cursor.execute("SELECT * FROM timetable_tea WHERE school_id=%s", (school_id,))
    result = []
    for t in cursor.fetchall():
        # class_conut(DB 오타) / class_count 모두 대응
        cc = t.get('class_count') or t.get('class_conut') or 0
        result.append({
            'member_id': t['member_id'] or '',
            'name': t['member_name'] or '',
            'subject': t['subject'] or '',
            'grade': t['grade'] or '',
            'classes': t['class_no'] or '',
            'class_count': int(cc),
            'unit_hours': int(t['hours'] or 4)
        })
    return result


def load_timetable_data(cursor, school_id):
    """timetable_data 로드. (st_map, sd_map, cd_map, bg_map) 반환.
    bg_map: {grade_subject: band_group} — 선택과목 분류용"""
    cursor.execute("SELECT * FROM timetable_data WHERE school_id=%s", (school_id,))
    rows = cursor.fetchall()
    st_map, sd_map, cd_map, bg_map = {}, {}, {}, {}
    for d in rows:
        key = f"{d['grade']}_{d['subject']}"
        st_map[key] = d.get('subject_type', '') or ''
        sd_map[key] = int(d.get('subject_demand', 0) or 0)
        cd_map[key] = int(d.get('class_demand', 0) or 0)
        bg = d.get('band_group', '') or ''
        if bg:
            bg_map[key] = bg
    return st_map, sd_map, cd_map, bg_map


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


def build_blocks(teachers, st_map, sd_map, cd_map, bg_map=None,
                 fixed_subs=None, weekly_hours=DEFAULT_WEEKLY_HOURS):
    """블록 구성. 선택과목은 bg_map(band_group)으로 동적 분류."""
    if fixed_subs is None:
        fixed_subs = []
    if bg_map is None:
        bg_map = {}

    regular_groups = {}
    elective_sections = {}  # grade -> {band_group_label -> [entries]}

    for t in teachers:
        if not t['grade'] or not t['subject']:
            continue
        key = f"{t['grade']}_{t['subject']}"
        stype = st_map.get(key, '')
        classes = [c.strip() for c in t['classes'].replace(',', ' ').split() if c.strip()]
        entry = {
            'teacher_id': t['member_id'], 'teacher_name': t['name'],
            'subject': t['subject'], 'classes': classes,
            'hours_per_class': t['unit_hours']
        }
        if stype == '선택':
            bg_label = bg_map.get(key, '기타선택')
            elective_sections.setdefault(t['grade'], {}).setdefault(bg_label, []).append(entry)
        else:
            if key not in regular_groups:
                regular_groups[key] = {'grade': t['grade'], 'subject': t['subject'], 'entries': []}
            regular_groups[key]['entries'].append(entry)

    blocks = []
    bid = 0

    # 고정교과 시수 맵: {grade_subject: total_fixed_periods}
    fixed_hours_map = {}
    for fs in fixed_subs:
        grades = ['1', '2', '3'] if fs['grade'] == 'all' else [fs['grade']]
        for g in grades:
            fk = f"{g}_{fs['subject']}"
            fixed_hours_map[fk] = fixed_hours_map.get(fk, 0) + fs['period_count']

    # 공통과목 블록: (교사, 반) 단위로 분리 — 교사 1명이 한 시간에 한 반만 수업
    for key, g in regular_groups.items():
        raw_hours = g['entries'][0]['hours_per_class'] if g['entries'] else 0
        fixed_h = fixed_hours_map.get(key, 0)
        net_hours = max(0, raw_hours - fixed_h)
        if net_hours <= 0:
            continue
        for entry in g['entries']:
            for cls in entry['classes']:
                bid += 1
                single_entry = {
                    'teacher_id': entry['teacher_id'],
                    'teacher_name': entry['teacher_name'],
                    'subject': entry['subject'],
                    'classes': [cls],
                    'hours_per_class': entry['hours_per_class']
                }
                blocks.append({
                    'id': f'blk_{bid}',
                    'name': f"{g['grade']}학년 {g['subject']}",
                    'grade': g['grade'], 'is_elective': False, 'linked_periods': 1,
                    'entries': [single_entry],
                    'hours_per_week': net_hours
                })

    # 선택과목 블록 — band_group별로 생성
    # 밴드시수 = (과목수 ÷ 학급수) × 과목별시수 (학급수 배수 원칙)
    for grade, bg_sections in elective_sections.items():
        cc = get_grade_count(grade, teachers)
        for bg_name, sections in sorted(bg_sections.items()):
            # 밴드 내 고유 과목 수 및 참여 학급 수
            unique_subjects = set(e['subject'] for e in sections)
            n_subj = len(unique_subjects)
            band_classes = set()
            for e in sections:
                for c in e['classes']:
                    band_classes.add(c)
            n_cls = len(band_classes) if band_classes else cc
            hours_per_subj = max((e['hours_per_class'] for e in sections), default=0)

            # 학급수 배수 검증
            if n_cls > 0 and n_subj % n_cls == 0:
                rotations = n_subj // n_cls
            else:
                # 배수 아님 → 보정 (가장 가까운 정수 로테이션)
                rotations = max(1, round(n_subj / n_cls))

            band_hours = rotations * hours_per_subj

            # 고정교과와 중복 차감
            fk = f"{grade}_{sections[0]['subject']}" if sections else ''
            fixed_h = fixed_hours_map.get(fk, 0)
            net_hours = max(0, band_hours - fixed_h)
            if net_hours <= 0:
                continue
            bid += 1
            blocks.append({
                'id': f'elec_{bg_name}_{bid}',
                'name': f"{grade}학년 {bg_name}",
                'grade': grade, 'is_elective': True, 'linked_periods': 1,
                'entries': sections,
                'hours_per_week': net_hours
            })

    return blocks


def _get_max_consecutive(block, day, start_p, linked, schedule, dmp, grade, class_cnt):
    """같은 과목 연속 시간 체크"""
    max_c = 0
    if block['is_elective']:
        affected = _elective_classes(block)
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


def _get_teacher_consecutive(entries, day, period, linked, busy, dmp):
    """교사 연속수업 체크 (과목 무관).
    한 교사가 쉬는시간 없이 연속 N교시 이상 수업하는지 확인."""
    max_c = 0
    for entry in entries:
        tk = _teacher_key(entry)
        tk_busy = busy.get(tk, set())
        consec = linked
        # 위로 확장
        p = period - 1
        while p >= 1 and f"{day}_{p}" in tk_busy:
            consec += 1
            p -= 1
        # 아래로 확장
        p = period + linked
        while p <= dmp[day] and f"{day}_{p}" in tk_busy:
            consec += 1
            p += 1
        max_c = max(max_c, consec)
    return max_c


def _elective_classes(block):
    """선택과목 블록의 실제 대상 반 목록 (편제표 기반)"""
    classes = set()
    for e in block['entries']:
        for c in e['classes']:
            classes.add(c)
    return sorted(classes, key=lambda x: int(x) if x.isdigit() else 0)


def _place_block(block, day, period, schedule, busy, grade, class_cnt):
    linked = block['linked_periods']
    for p in range(linked):
        ap = period + p
        cell = f"{day}_{ap}"
        lpos = None
        if linked > 1:
            lpos = 'top' if p == 0 else ('bottom' if p == linked - 1 else 'middle')
        if block['is_elective']:
            # 편제표에 실제 존재하는 반에만 배치
            for c in _elective_classes(block):
                ck = f"{grade}_{c}"
                if ck not in schedule:
                    schedule[ck] = {}
                entry = next((e for e in block['entries'] if c in e['classes']), None)
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


def _can_place(block, d, p, linked, schedule, busy, constraints, dmp,
               grade, cc, max_subj_consec, max_teacher_consec):
    """블록을 (d, p)에 배치할 수 있는지 5가지 조건 확인"""
    for lp in range(linked):
        cell = f"{d}_{p + lp}"
        # 1) 반 빈 칸 확인
        if block['is_elective']:
            # 편제표에 실제 존재하는 반만 체크
            for c in _elective_classes(block):
                if schedule.get(f"{grade}_{c}", {}).get(cell):
                    return False
        else:
            for e in block['entries']:
                for cls in e['classes']:
                    if schedule.get(f"{grade}_{cls}", {}).get(cell):
                        return False
        # 2) 교사 시간 중복 확인
        for e in block['entries']:
            if cell in busy.get(_teacher_key(e), set()):
                return False
        # 3) 교사 제약조건 확인
        for e in block['entries']:
            tk = _teacher_key(e)
            for con in constraints.get(tk, []):
                if con['day'] == DAYS[d] and (con['period'] is None or con['period'] == p + lp):
                    return False
    # 4) 같은 과목 연속 제한
    mc = _get_max_consecutive(block, d, p, linked, schedule, dmp, grade, cc)
    if mc > max_subj_consec:
        return False
    # 5) 교사 연속수업 제한 (과목 무관)
    tc = _get_teacher_consecutive(block['entries'], d, p, linked, busy, dmp)
    if tc > max_teacher_consec:
        return False
    return True


def _generate_slots(dmp, attempt):
    """시도(attempt)마다 다른 요일 순서로 슬롯 목록 생성.
    attempt=0: 기본 순서(월~금), attempt>0: 시도별 요일 셔플."""
    max_p = max(dmp)
    slots = []
    for p in range(1, max_p + 1):
        day_order = list(range(5))
        if attempt > 0:
            random.seed(attempt * 1000 + p)
            random.shuffle(day_order)
        for d in day_order:
            if p <= dmp[d]:
                slots.append((d, p))
    return slots


def run_auto_generate(blocks, fixed_subjects, constraints, teachers,
                      dmp=None, weekly_hours=DEFAULT_WEEKLY_HOURS,
                      n_attempts=N_ATTEMPTS):
    """시간표 자동 생성. 다중 시도 중 최선 결과 반환."""
    if dmp is None:
        dmp = list(DEFAULT_DMP)

    target_grades = sorted(set(b['grade'] for b in blocks))

    # ── 고정 교과 선배치 (모든 시도에서 공통) ──
    base_schedule = {}
    base_busy = {}
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
                base_schedule.setdefault(ck, {})
                for p_off in range(fs['period_count']):
                    cell = f"{di}_{fs['period_start'] + p_off}"
                    lpos = None
                    if fs['period_count'] > 1:
                        lpos = 'top' if p_off == 0 else (
                            'bottom' if p_off == fs['period_count'] - 1 else 'middle')
                    base_schedule[ck][cell] = {
                        'block_id': None, 'subject': fs['subject'], 'teacher': '(고정)',
                        'teacher_id': '', 'is_elective': False, 'is_fixed': True,
                        'linked_pos': lpos}
            fixed_count += 1

    # ── 블록 정렬: 선택과목 우선 → 교사 부하 높은 순(배치 어려운 것 우선) ──
    tblocks = [b for b in blocks if b['grade'] in target_grades]
    # 교사별 총 수업 부하 계산
    teacher_load = {}
    for b in tblocks:
        for e in b['entries']:
            tk = _teacher_key(e)
            teacher_load[tk] = teacher_load.get(tk, 0) + b['hours_per_week']
    # 블록의 교사 부하 = 해당 블록 교사의 총 수업시간 (높을수록 배치 어려움)
    def block_priority(b):
        load = max((teacher_load.get(_teacher_key(e), 0) for e in b['entries']), default=0)
        return (-int(b['is_elective']), -load, -b['hours_per_week'])
    tblocks.sort(key=block_priority)
    total_needed = sum(b['hours_per_week'] for b in tblocks)

    best = None  # (schedule, results, total_placed, total_needed, fixed_count, total_cw)

    # 블록 분리: 선택과목(고정순서) + 일반과목
    elective_blocks = [b for b in tblocks if b['is_elective']]
    regular_blocks = [b for b in tblocks if not b['is_elective']]

    def _count_available(block, slots, schedule, busy, constraints, dmp, teachers):
        """블록의 배치 가능 슬롯 수 (MCV용)"""
        grade = block['grade']
        cc = get_grade_count(grade, teachers)
        linked = block['linked_periods']
        count = 0
        for d, p in slots:
            if p + linked - 1 > dmp[d]:
                continue
            if _can_place(block, d, p, linked, schedule, busy, constraints,
                          dmp, grade, cc, MAX_SAME_SUBJECT_CONSECUTIVE,
                          MAX_TEACHER_CONSECUTIVE):
                count += 1
        return count

    def _place_one_block(block, slots, schedule, busy, constraints, dmp, teachers):
        """단일 블록 배치. (placed, cw) 반환."""
        placed = 0
        needed = block['hours_per_week']
        linked = block['linked_periods']
        grade = block['grade']
        cc = get_grade_count(grade, teachers)
        day_count = {}
        cw = 0

        if block['is_elective']:
            max_per_day = max(2, -(-needed // 5))
        else:
            max_per_day = 2

        for _pass in (1, 2):
            mcl_subj = MAX_SAME_SUBJECT_CONSECUTIVE if _pass == 1 else 3
            mcl_tea = MAX_TEACHER_CONSECUTIVE if _pass == 1 else MAX_TEACHER_CONSECUTIVE + 1
            for d, p in slots:
                if placed >= needed:
                    break
                if day_count.get(d, 0) >= max_per_day:
                    continue
                if p + linked - 1 > dmp[d]:
                    continue
                if _can_place(block, d, p, linked, schedule, busy, constraints,
                              dmp, grade, cc, mcl_subj, mcl_tea):
                    _place_block(block, d, p, schedule, busy, grade, cc)
                    placed += linked
                    day_count[d] = day_count.get(d, 0) + linked
                    if _pass == 2:
                        cw += linked
            if placed >= needed:
                break
        return placed, cw

    for attempt in range(n_attempts):
        schedule = copy.deepcopy(base_schedule)
        busy = {tk: set(s) for tk, s in base_busy.items()}

        results = []
        total_placed = 0
        total_cw = 0

        slots = _generate_slots(dmp, attempt)

        # 1단계: 선택과목 먼저 배치 (band 단위, 순서 고정)
        for block in elective_blocks:
            placed, cw = _place_one_block(block, slots, schedule, busy,
                                          constraints, dmp, teachers)
            total_placed += placed
            total_cw += cw
            results.append({
                'name': block['name'], 'is_elective': True,
                'needed': block['hours_per_week'], 'placed': placed,
                'ok': placed >= block['hours_per_week'], 'cw': cw
            })

        # 2단계: 일반과목 — MCV 휴리스틱 (가용 슬롯 적은 블록부터)
        remaining = list(regular_blocks)
        if attempt > 0:
            # attempt별 약간의 무작위성 추가 (tie-breaking용)
            random.seed(attempt * 7777)

        while remaining:
            # MCV: 각 블록의 가용 슬롯 수 계산
            if attempt == 0 or len(remaining) <= 3:
                # attempt 0 또는 블록 적을 때: 정확한 MCV
                avail = [(i, _count_available(b, slots, schedule, busy,
                          constraints, dmp, teachers))
                         for i, b in enumerate(remaining)]
                avail.sort(key=lambda x: x[1])  # 가용 슬롯 적은 것 우선
                pick_idx = avail[0][0]
            else:
                # attempt > 0: MCV 상위 5개 중 랜덤 선택 (다양성 확보)
                avail = [(i, _count_available(b, slots, schedule, busy,
                          constraints, dmp, teachers))
                         for i, b in enumerate(remaining)]
                avail.sort(key=lambda x: x[1])
                top_n = min(5, len(avail))
                pick_idx = avail[random.randint(0, top_n - 1)][0]

            block = remaining.pop(pick_idx)
            placed, cw = _place_one_block(block, slots, schedule, busy,
                                          constraints, dmp, teachers)
            total_placed += placed
            total_cw += cw
            results.append({
                'name': block['name'], 'is_elective': False,
                'needed': block['hours_per_week'], 'placed': placed,
                'ok': placed >= block['hours_per_week'], 'cw': cw
            })

        # 최선 결과 갱신
        if best is None or total_placed > best[2]:
            best = (schedule, results, total_placed, total_needed, fixed_count, total_cw)

        # 완벽 배치되면 더 시도하지 않음
        if total_placed >= total_needed:
            break

    return best


def _load_homeroom_map(cursor, school_id):
    """tea_all에서 담임교사 맵 로드. {grade_classno: {member_id, member_name}}"""
    cursor.execute(
        """SELECT member_id, member_name, class_grade, class_no
           FROM tea_all WHERE school_id=%s
           AND class_grade IS NOT NULL AND class_grade != ''
           AND class_no IS NOT NULL AND class_no != ''""",
        (school_id,))
    hmap = {}
    for r in cursor.fetchall():
        hk = f"{r['class_grade']}_{r['class_no']}"
        hmap[hk] = {'member_id': r['member_id'], 'member_name': r['member_name']}
    return hmap


def save_timetable(cursor, school_id, schedule):
    """schedule dict를 timetable 테이블에 저장. commit은 caller가.
    고정교과(창체 등)는 tea_all 담임교사를 자동 조회하여 반영."""
    day_names = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금'}
    cursor.execute("DELETE FROM timetable WHERE school_id=%s", (school_id,))
    cursor.execute("SELECT member_school FROM timetable_tea WHERE school_id=%s LIMIT 1", (school_id,))
    row = cursor.fetchone()
    ms = row['member_school'] if row else ''

    # 담임교사 맵 로드 (고정교과용)
    hmap = _load_homeroom_map(cursor, school_id)

    cnt = 0
    for ck, cells in schedule.items():
        g, c = ck.split('_')
        for cell_id, data in cells.items():
            di, period = cell_id.split('_')
            teacher_id = data.get('teacher_id', '')
            teacher_name = data.get('teacher', '')

            # 고정교과(창체 등)이면 담임교사 자동 배정
            if data.get('is_fixed') and teacher_name == '(고정)':
                hk = f"{g}_{c}"
                hr = hmap.get(hk)
                if hr:
                    teacher_id = hr['member_id']
                    teacher_name = hr['member_name']
                else:
                    teacher_name = '(담임)'

            cursor.execute(
                """INSERT INTO timetable (school_id, member_school, member_id, day_of_week,
                    grade, class_no, period, subject, member_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (school_id, ms, teacher_id, day_names[int(di)],
                 g, c, period, data['subject'], teacher_name))
            cnt += 1
    return cnt


def refresh_homeroom_timetable(cursor, school_id):
    """담임 배정 변경 시 timetable의 창체 등 고정교과 교사를 갱신.
    commit은 caller가."""
    hmap = _load_homeroom_map(cursor, school_id)
    updated = 0
    # 고정교과 목록 조회
    cursor.execute(
        "SELECT DISTINCT subject FROM timetable_fixed_subject WHERE school_id=%s",
        (school_id,))
    fixed_subjects = [r['subject'] for r in cursor.fetchall()]
    if not fixed_subjects:
        return 0

    for subj in fixed_subjects:
        cursor.execute(
            "SELECT id, grade, class_no FROM timetable WHERE school_id=%s AND subject=%s",
            (school_id, subj))
        rows = cursor.fetchall()
        for r in rows:
            hk = f"{r['grade']}_{r['class_no']}"
            hr = hmap.get(hk)
            if hr:
                cursor.execute(
                    "UPDATE timetable SET member_id=%s, member_name=%s WHERE id=%s",
                    (hr['member_id'], hr['member_name'], r['id']))
                updated += 1
            else:
                cursor.execute(
                    "UPDATE timetable SET member_id='', member_name='(담임)' WHERE id=%s",
                    (r['id'],))
    return updated
