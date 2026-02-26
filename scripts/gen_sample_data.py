#!/usr/bin/env python3
"""2026 편성표 기준 1학기 과목 + 샘플 학생 데이터 생성"""
import pymysql, random

SCHOOL_ID = '12015'
SCHOOL_NAME = '샘플고등학교'

# ============================================================
# 1학기 개설교과목 (편성표 기준)
# ============================================================
subjects_1sem = [
    # --- 1학년 1학기 (필수과목) ---
    ('1', '공통국어1',      4, '일반', '국어'),
    ('1', '공통수학1',      4, '일반', '수학'),
    ('1', '공통영어1',      4, '일반', '영어'),
    ('1', '한국사1',        3, '일반', '사회'),
    ('1', '통합사회1',      4, '일반', '사회'),
    ('1', '통합과학1',      4, '일반', '과학'),
    ('1', '과학탐구실험1',   1, '일반', '과학'),
    ('1', '체육1',          2, '일반', '체육'),
    # 1학년 학기교차 (1학기 음악 선택 → 2학기 미술, 또는 반대)
    ('1', '음악',           3, '학기교차', '예술'),
    ('1', '미술',           3, '학기교차', '예술'),

    # --- 2학년 1학기 (필수과목) ---
    ('2', '문학',           4, '일반', '국어'),
    ('2', '대수',           4, '일반', '수학'),
    ('2', '영어Ⅰ',         4, '일반', '영어'),
    ('2', '정보',           3, '일반', '정보'),
    ('2', '스포츠 생활1',    2, '일반', '체육'),
    # 2학년 1학기 선택 (택4)
    ('2', '사회와 문화',     3, '선택', '사회'),
    ('2', '세계시민과 지리',  3, '선택', '사회'),
    ('2', '세계사',          3, '선택', '사회'),
    ('2', '현대사회와 윤리',  3, '선택', '사회'),
    ('2', '물리학',          3, '선택', '과학'),
    ('2', '화학',            3, '선택', '과학'),
    ('2', '생명과학',        3, '선택', '과학'),
    ('2', '지구과학',        3, '선택', '과학'),

    # --- 3학년 1학기 (필수과목) ---
    ('3', '독서와 작문',     3, '일반', '국어'),
    ('3', '확률과 통계',     3, '일반', '수학'),
    ('3', '영어 독해와 작문', 3, '일반', '영어'),
    ('3', '스포츠 과학',     1, '일반', '체육'),
    # 3학년 학기교차
    ('3', '음악 연주와 창작', 2, '학기교차', '예술'),
    ('3', '미술 창작',       2, '학기교차', '예술'),
    # 3학년 1학기 택1 (6개 중 1)
    ('3', '문학과 영상',     3, '선택', '국어'),
    ('3', '주제 탐구 독서',  3, '선택', '국어'),
    ('3', '경제 수학',       3, '선택', '수학'),
    ('3', '미적분Ⅱ',        3, '선택', '수학'),
    ('3', '영어 발표와 토론', 3, '선택', '영어'),
    ('3', '심화 영어 독해와 작문', 3, '선택', '영어'),
    # 3학년 1학기 택4 (15개 중 4)
    ('3', '정치',            3, '선택', '사회'),
    ('3', '법과 사회',       3, '선택', '사회'),
    ('3', '도시의 미래 탐구', 3, '선택', '사회'),
    ('3', '인문학과 윤리',   3, '선택', '사회'),
    ('3', '음악 감상과 비평', 3, '선택', '예술'),
    ('3', '미술 감상과 비평', 3, '선택', '예술'),
    ('3', '전자기와 양자',   3, '선택', '과학'),
    ('3', '화학 반응의 세계', 3, '선택', '과학'),
    ('3', '생물의 유전',     3, '선택', '과학'),
    ('3', '행성우주과학',    3, '선택', '과학'),
    ('3', '프로그래밍',      3, '선택', '정보'),
    ('3', '생활과학 탐구',   3, '선택', '과학'),
    ('3', '한문',            3, '선택', '한문'),
    ('3', '중국어',          3, '선택', '제2외국어'),
    ('3', '일본어',          3, '선택', '제2외국어'),
    # 3학년 교양 택1 (3개 중 1)
    ('3', '진로와 직업',     2, '선택', '교양'),
    ('3', '논리와 사고',     2, '선택', '교양'),
    ('3', '과학창의연구',    2, '선택', '교양'),
]

# ============================================================
# 2학년/3학년 선택과목 그룹 (학생 배정용)
# ============================================================
G2_ELECTIVES = ['사회와 문화', '세계시민과 지리', '세계사', '현대사회와 윤리',
                '물리학', '화학', '생명과학', '지구과학']

G3_SEMESTER_CHOICE = ['음악 연주와 창작', '미술 창작']
G3_PICK1 = ['문학과 영상', '주제 탐구 독서', '경제 수학', '미적분Ⅱ',
            '영어 발표와 토론', '심화 영어 독해와 작문']
G3_PICK4 = ['정치', '법과 사회', '도시의 미래 탐구', '인문학과 윤리',
            '음악 감상과 비평', '미술 감상과 비평', '전자기와 양자',
            '화학 반응의 세계', '생물의 유전', '행성우주과학',
            '프로그래밍', '생활과학 탐구', '한문', '중국어', '일본어']
G3_LIBERAL = ['진로와 직업', '논리와 사고', '과학창의연구']

# ============================================================
# 한국 이름 생성
# ============================================================
LAST = ['김','이','박','최','정','강','조','윤','장','임','한','오','서','신',
        '권','황','안','송','류','전','홍','고','문','양','손','배','백','허','남','심']
FIRST = ['민준','서준','예준','도윤','시우','주원','하준','지호','지후','준서',
         '준우','현우','도현','건우','우진','선우','서연','서윤','지우','서현',
         '하은','하윤','민서','지유','윤서','채원','수아','지아','지윤','다은',
         '은서','예은','수빈','소율','지원','소윤','예린','하린','수연','채은',
         '승현','태현','민재','승우','유준','정우','재윤','시현','연우','지환']

def make_name():
    return random.choice(LAST) + random.choice(FIRST)

# ============================================================
# 학생 선택과목 배정
# ============================================================
def pick_subjects_g1():
    """1학년: 학기교차 1과목만 선택 (음악 or 미술)"""
    return [random.choice(['음악', '미술'])]

def pick_subjects_g2():
    """2학년: 택4 (8개 중 4개)"""
    return random.sample(G2_ELECTIVES, 4)

def pick_subjects_g3():
    """3학년: 학기교차(1) + 택1(1) + 택4(4) + 교양택1(1) = 7과목"""
    subs = []
    subs.append(random.choice(G3_SEMESTER_CHOICE))  # 학기교차
    subs.append(random.choice(G3_PICK1))             # 택1
    subs.extend(random.sample(G3_PICK4, 4))          # 택4
    subs.append(random.choice(G3_LIBERAL))            # 교양 택1
    return subs

# ============================================================
# DB 작업
# ============================================================
def main():
    conn = pymysql.connect(host='10.10.0.3', user='school_user', password='3279',
                           database='school_db', charset='utf8mb4',
                           cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()

    # 1) 기존 데이터 삭제
    cur.execute("DELETE FROM timetable_data WHERE school_id=%s", (SCHOOL_ID,))
    cur.execute("DELETE FROM timetable_stu WHERE school_id=%s", (SCHOOL_ID,))
    print(f"기존 데이터 삭제 완료")

    # 2) 1학기 과목 INSERT
    for grade, subj, hours, stype, dept in subjects_1sem:
        cur.execute("""
            INSERT INTO timetable_data
            (school_id, member_school, subject, course_year, grade,
             subject_demand, subject_type, subject_depart,
             stu_count, class_demand, tea_demand)
            VALUES (%s,%s,%s,'2022',%s,%s,%s,%s,0,0,0)
        """, (SCHOOL_ID, SCHOOL_NAME, subj, grade, hours, stype, dept))
    print(f"과목 {len(subjects_1sem)}개 INSERT 완료")

    # 3) 샘플 학생 생성 (학년별 10반 × 25명 = 250명)
    total = 0
    for grade in ['1', '2', '3']:
        for class_no in range(1, 11):
            for num in range(1, 26):
                name = make_name()
                if grade == '1':
                    subs = pick_subjects_g1()
                elif grade == '2':
                    subs = pick_subjects_g2()
                else:
                    subs = pick_subjects_g3()

                # subject1~subject12 채우기
                sub_vals = {}
                for i in range(1, 13):
                    sub_vals[f'subject{i}'] = subs[i-1] if i <= len(subs) else ''

                cur.execute("""
                    INSERT INTO timetable_stu
                    (school_id, member_school, member_name, grade, class_no, student_num,
                     subject1,subject2,subject3,subject4,subject5,subject6,
                     subject7,subject8,subject9,subject10,subject11,subject12)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (SCHOOL_ID, SCHOOL_NAME, name, grade, str(class_no), str(num),
                      sub_vals['subject1'], sub_vals['subject2'], sub_vals['subject3'],
                      sub_vals['subject4'], sub_vals['subject5'], sub_vals['subject6'],
                      sub_vals['subject7'], sub_vals['subject8'], sub_vals['subject9'],
                      sub_vals['subject10'], sub_vals['subject11'], sub_vals['subject12']))
                total += 1

    conn.commit()
    print(f"학생 {total}명 INSERT 완료")

    # 4) 검증
    cur.execute("SELECT COUNT(*) as c FROM timetable_data WHERE school_id=%s", (SCHOOL_ID,))
    print(f"과목 수: {cur.fetchone()['c']}")
    cur.execute("SELECT grade, COUNT(*) as c FROM timetable_stu WHERE school_id=%s GROUP BY grade", (SCHOOL_ID,))
    for r in cur.fetchall():
        print(f"  {r['grade']}학년: {r['c']}명")

    cur.close()
    conn.close()
    print("완료!")

if __name__ == '__main__':
    main()
