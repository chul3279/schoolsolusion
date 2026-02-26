# SchoolUs 사이트 로직 시각화

## 1. 전체 요청 흐름

```
클라이언트 (브라우저/PWA)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  nginx (HTTPS, www 정규화)                       │
│  ├─ Rate Limit: 로그인 5/분, 가입 3/분, AI 10/분  │
│  ├─ 보안헤더: HSTS, CSP, X-Frame, XSS-Protection │
│  └─ SSL: Let's Encrypt                          │
├─────────────────────────────────────────────────┤
│  정적파일 (try_files $uri $uri/ @flask)          │
│  ├─ CSS/JS/이미지/폰트 → 7일 캐시                │
│  ├─ HTML → no-cache                             │
│  ├─ sw.js → no-cache, no-store                  │
│  └─ .pem, vapid_keys.json → deny all            │
├─────────────────────────────────────────────────┤
│  동적 요청 → @flask (unix socket)                │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Gunicorn (24 워커, sync, timeout 180s)          │
│  소켓: /run/flask_app/flask_app.sock             │
└──────────────────┬──────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────┐
│  Flask app.py                                    │
│                                                  │
│  @before_request 미들웨어 체인:                    │
│  ┌───────────────────────────────────┐           │
│  │ 1. 브루트포스 체크 (IP당 5회/10분) │           │
│  │         ▼                         │           │
│  │ 2. 세션 인증 (user_id 확인)        │           │
│  │         ▼                         │           │
│  │ 3. school_id 횡적이동 방지         │           │
│  │         ▼                         │           │
│  │ 4. RBAC 역할 검증 (84개 교사전용)  │           │
│  │         ▼                         │           │
│  │ 5. IDOR 방어 (본인/자녀만 조회)    │           │
│  └───────────────────────────────────┘           │
│         ▼                                        │
│  Blueprint 라우팅 (25개)                          │
└──────────────────┬──────────────────────────────┘
                   ▼
         ┌─────────┼─────────┐
         ▼         ▼         ▼
    ┌────────┐ ┌────────┐ ┌────────────┐
    │ MySQL  │ │ SFTP   │ │ 외부 API    │
    │10.10.0.3│ │10.10.0.4│ │Gemini/토스  │
    └────────┘ └────────┘ └────────────┘
```

## 2. 로그인 흐름

```
index.html (로그인 폼)
    │
    ▼
POST /login_process
    │
    ├─ 실패 → login_attempts 기록 → 5회 초과시 429
    │
    ▼ 성공
member 테이블 조회 → member_roll 파싱
    │
    ├─ 단일역할 "teacher"
    │   └─ tea_all 조회 → 세션 설정 → /highschool/tea.html
    │
    ├─ 단일역할 "student"
    │   └─ stu_all 조회 → 세션 설정 → /highschool/st.html
    │
    ├─ 단일역할 "parent"
    │   ├─ 자녀 1명 → 자동선택 → /highschool/fm.html
    │   └─ 자녀 2명+ → /select-child 페이지
    │
    └─ 복수역할 "teacher,parent"
        └─ /select-role 페이지
            ├─ 교사 선택 → tea_all 세션
            └─ 학부모 선택 → fm_all 세션

세션 키:
┌──────────────────────────────────────┐
│ user_id       = member_id            │
│ user_name     = member_name          │
│ user_role     = teacher|student|parent│
│ user_school   = member_school        │
│ school_id     = school_id            │
│ class_grade   = 학년 (교사/학생)      │
│ class_no      = 반 (교사/학생)        │
│ department    = 교과 (교사)           │
│ children_ids  = [자녀ID] (학부모)     │
│ selected_child = 선택자녀ID (학부모)   │
└──────────────────────────────────────┘
```

## 3. 역할별 페이지 구조

```
┌─────────────────────────────────────────────────────────────┐
│                    공개 페이지                                │
│  index.html (로그인) │ register.html │ terms │ privacy      │
│  support.html        │ refund_policy.html                   │
└──────────────────────┬──────────────────────────────────────┘
                       │ 로그인 후
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│   교사        ││   학생        ││   학부모      │
│  tea.html    ││  st.html     ││  fm.html     │
├──────────────┤├──────────────┤├──────────────┤
│ tea/         ││ st_homeroom  ││ fm_homeroom  │
│ ├ homeroom   ││ st/          ││ fm/          │
│ ├ subject    ││ ├ lesson_    ││ └ message    │
│ ├ message    ││ │ activity   │├──────────────┤
│ ├ schooladmin││ └ message    ││ 공통 페이지   │
│ ├ school_    │├──────────────┤│ notice       │
│ │ record_    ││              ││ messenger    │
│ │ maker      ││              ││ survey       │
│ ├ timetable_ ││              ││ mypage       │
│ │ workflow   ││              ││ admission    │
│ ├ timetable  ││              │└──────────────┘
│ │ maker      ││              │
│ ├ timetable  ││              │
│ │ change     ││              │
│ ├ timetable  ││              │
│ │ print      ││              │
│ ├ class_maker││              │
│ └ classtime_ ││              │
│   maker_base ││              │
└──────────────┘└──────────────┘

※ highschool/ 과 middleschool/ 동일 구조 (총 2벌)
```

## 4. API 엔드포인트 분포 (274개)

```
시간표 timetable.py     ████████████████████████████████ 32
입시   admission.py     ██████████████████████████ 26
홈룸   homeroom.py      ███████████████████ 19
동아리 club.py          ███████████████████ 19
메시지 message.py       █████████████████ 17
교과   subject.py       ████████████████ 16
인증   auth.py          ███████████████ 15
방과후 afterschool.py   ███████████████ 15
과제   assignment.py    ██████████████ 14
설문   survey.py        ███████████ 11
기록   homeroom_record  ███████████ 11
출결   attendance.py    ██████████ 10
메신저 messenger.py     ██████████ 10
반구성 class_maker.py   █████████ 9
공문   letter.py        ████████ 8
공지   notice.py        ███████ 7
교사   teacher.py       ██████ 6
결제   payment.py       █████ 5
일정   schedule.py      ████ 4
기록생성 homeroom_gen   ████ 4
푸시   push.py          ████ 4
파이프라인 timetable_p  ███ 3
급식   meal.py          ███ 3
학생   student.py       ██ 2
학부모 parent.py        ██ 2
고객   support.py       ██ 2
```

## 5. DB 테이블 관계도

```
schoolinfo (10,549개)
    │ school_id (PK)
    │
    ├───────────────────┐
    │                   │
    ▼                   ▼
┌─────────┐    ┌──────────────────────────────────┐
│ member   │    │  역할별 상세 테이블                │
│──────────│    │                                   │
│ member_id├───►│  tea_all (교사)                    │
│ member_sn│    │  ├ member_id, school_id            │
│ member_  │    │  ├ class_grade, class_no           │
│  name    │    │  └ department                      │
│ member_  │    │                                   │
│  roll    ├───►│  stu_all (학생)                    │
│ member_  │    │  ├ member_id, school_id            │
│  email   │    │  ├ class_grade, class_no, class_num│
│ school_id│    │  └ point                           │
└─────────┘    │                                   │
    │          │  fm_all (학부모)                    │
    └─────────►│  ├ member_id, school_id            │
               │  ├ child_name, child_birth         │
               │  └ class_grade, class_no, class_num│
               └──────────────────────────────────┘

담임↔학생 관계:
  tea_all.school_id + class_grade + class_no
    = stu_all.school_id + class_grade + class_no

학부모↔자녀 관계:
  fm_all.child_name + child_birth + school_id
    → stu_all 매칭
```

## 6. 외부 서비스 연동

```
┌──────────────────────────────────────────────┐
│                  Flask 서버                    │
│                                               │
│  ┌─────────────┐  ┌──────────────────────┐   │
│  │ subject.py   │  │ admission.py          │   │
│  │ club.py      │──│ (AI 분석)             │   │
│  │ (AI 생기부)  │  └──────────┬───────────┘   │
│  └──────┬──────┘             │               │
│         └────────┬───────────┘               │
│                  ▼                            │
│         Google Gemini API                     │
│         (config/gemini_keys.py)               │
│                                               │
│  ┌──────────────┐     ┌─────────────────┐    │
│  │ payment.py    │────►│ 토스 페이먼츠    │    │
│  │ (결제 처리)   │◄────│ (PG/웹훅)       │    │
│  └──────────────┘     └─────────────────┘    │
│                                               │
│  ┌──────────────┐     ┌─────────────────┐    │
│  │ email_util.py │────►│ Gmail SMTP      │    │
│  │ (이메일 발송) │     │ (587/TLS)       │    │
│  └──────────────┘     └─────────────────┘    │
│                                               │
│  ┌──────────────┐     ┌─────────────────┐    │
│  │ subject_utils │────►│ 데이터서버       │    │
│  │ homeroom_     │     │ 10.10.0.4       │    │
│  │ record.py     │     │ (SFTP 파일저장) │    │
│  │ admission.py  │     └─────────────────┘    │
│  └──────────────┘                             │
│                                               │
│  ┌──────────────┐     ┌─────────────────┐    │
│  │ db.py         │────►│ DB서버          │    │
│  │ (커넥션풀)    │     │ 10.10.0.3       │    │
│  └──────────────┘     │ MySQL school_db  │    │
│                        └─────────────────┘    │
└──────────────────────────────────────────────┘
```

## 7. 보안 체계

```
┌─────────── 외부 (nginx) ──────────────────────┐
│                                                │
│  [Rate Limit]  로그인 5/분, 가입 3/분, AI 10/분 │
│  [SSL/TLS]     Let's Encrypt + HSTS 1년        │
│  [헤더]        CSP, X-Frame, XSS-Protection    │
│  [차단]        .pem, .json 직접접근 deny        │
│                                                │
└──────────────────┬─────────────────────────────┘
                   ▼
┌─────────── 내부 (Flask) ──────────────────────┐
│                                                │
│  [브루트포스] login_attempts 테이블, IP+ID 추적  │
│       │                                        │
│       ▼                                        │
│  [인증] 세션 user_id 필수 (화이트리스트 7개 제외) │
│       │                                        │
│       ▼                                        │
│  [학교격리] 요청 school_id == 세션 school_id     │
│       │                                        │
│       ▼                                        │
│  [RBAC] 교사전용 API 84개 → user_role 검증      │
│       │                                        │
│       ▼                                        │
│  [IDOR] 학생=본인만, 학부모=자녀만 데이터 접근    │
│                                                │
└────────────────────────────────────────────────┘

화이트리스트 (인증 불필요):
  /api/signup, /api/schools, /api/push/vapid-key
  /api/find-id, /api/find-password, /api/public/stats
  /api/payment/* (웹훅)
```

## 8. PWA 흐름

```
┌──── 설치 ─────────────────────────────┐
│                                        │
│  manifest.json → beforeinstallprompt   │
│  → pwa-install.js → 설치 프롬프트      │
│  → standalone 모드 실행                │
│                                        │
└────────────────────────────────────────┘

┌──── 서비스워커 (sw.js) ───────────────┐
│                                        │
│  Install: 프리캐시 (index, 아이콘, manifest)│
│       ▼                                │
│  Activate: 구버전 캐시 삭제             │
│       ▼                                │
│  Fetch 전략:                           │
│  ├─ 정적파일 → Cache-first (7일)       │
│  ├─ API 요청 → Network-first          │
│  └─ POST    → Network only            │
│                                        │
└────────────────────────────────────────┘

┌──── 푸시 알림 ────────────────────────┐
│                                        │
│  pwa-push.js                           │
│  ├─ GET /api/push/vapid-key            │
│  ├─ pushManager.subscribe()            │
│  └─ POST /api/push/subscribe           │
│       ▼                                │
│  교사: POST /api/push/send             │
│       ▼                                │
│  web-push → FCM/APNS → 기기 알림       │
│                                        │
└────────────────────────────────────────┘
```

## 9. 사용설명서 시스템

```
각 HTML 페이지 (39개)
  └─ <script src="/static/js/help-modal.js" data-doc="파일명">
         │
         ▼
    help-modal.js
    ├─ 우하단 ? 플로팅 버튼 생성
    ├─ 클릭 → fetch('/사용설명서/{data-doc}.html')
    ├─ 모달 표시 (캐시, ESC/배경 클릭 닫기)
    └─ 18개 설명서 파일 매핑
         │
         ▼
    /사용설명서/ (18개 HTML)
    ├─ teacher-dashboard, homeroom, subject
    ├─ schooladmin, timetable-workflow, school-record
    ├─ student-dashboard, student-homeroom, student-activity
    ├─ parent-dashboard, parent-homeroom
    ├─ notice, messenger, message, survey
    └─ mypage, admission, login
```

## 10. 서버 인프라

```
┌─────────────────────────────────────────┐
│  웹서버 (현재 서버)                       │
│  /var/www/web/html                       │
│  ├─ nginx (리버스 프록시 + 정적파일)      │
│  ├─ Gunicorn (24워커, unix 소켓)         │
│  ├─ Flask (Python 3)                     │
│  └─ cron: 6시간마다 Git 백업              │
├─────────────────────────────────────────┤
│  도메인: www.schoolwithus.co.kr          │
│  부도메인: schoolwithus.kr → 리다이렉트    │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼                     ▼
┌──────────┐       ┌──────────┐
│ DB서버    │       │ 데이터서버 │
│ 10.10.0.3│       │ 10.10.0.4│
│ MySQL    │       │ SFTP     │
│ school_db│       │ 파일저장  │
│          │       │ 민감파일  │
│          │       │  백업    │
└──────────┘       └──────────┘

GitHub 백업: chul3279/schoolsolusion (private)
  └─ 6시간마다 자동 push (민감파일 .gitignore 제외)
```
