# 파일 의존성 맵 (수정 시 영향 범위)

> 특정 파일 수정 시 함께 확인/수정해야 하는 파일 목록

## 라우트 파일 → 영향받는 프론트엔드

```
routes/auth.py
  → index.html (로그인)
  → register.html (회원가입)
  → highschool/mypage.html, middleschool/mypage.html
  → templates/signup.html
  → 모든 페이지 (세션 키 변경 시)

routes/teacher.py
  → highschool/tea.html, middleschool/tea.html
  → 교사 전용 페이지 전체 (/api/teacher/info 의존)

routes/student.py
  → highschool/st.html, middleschool/st.html

routes/parent.py
  → highschool/fm.html, middleschool/fm.html

routes/homeroom.py
  → highschool/tea/homeroom.html, middleschool/tea/homeroom.html
  → highschool/tea/school_record_maker.html
  → highschool/st_homeroom.html, middleschool/st_homeroom.html
  → highschool/fm_homeroom.html, middleschool/fm_homeroom.html
  → highschool/fm.html (상담 일정)
  → highschool/admission/admission.html (/api/homeroom/students)

routes/subject.py
  → highschool/tea/subject.html + subject.js
  → middleschool/tea/subject.html + subject.js

routes/club.py
  → highschool/tea/subject.html + subject.js (동아리 탭)
  → middleschool/tea/subject.html + subject.js

routes/assignment.py
  → highschool/tea/subject.html + subject.js (과제 탭)
  → highschool/st/lesson_activity.html
  → highschool/fm_homeroom.html (자녀 과제)
  → middleschool 동일 구조

routes/timetable.py
  → highschool/tea/timetable_workflow.html
  → highschool/tea/timetablemaker.html
  → highschool/tea/timetablechange.html
  → highschool/tea/timetableprint.html
  → highschool/tea.html (당일 시간표)
  → highschool/st.html (학생 시간표)
  → highschool/fm.html (반 시간표)
  → highschool/tea/homeroom.html (주간 시간표)
  → highschool/tea/subject.html (주간 시간표)
  → middleschool 동일 구조

routes/timetable_pipeline.py
  → highschool/tea/timetable_workflow.html (Step 7, 8)
  → utils/elective_engine.py (교육반 배정)
  → utils/timetable_engine.py (자동 생성)

routes/notice.py
  → highschool/notice.html, middleschool/notice.html
  → highschool/tea.html, st.html, fm.html (공지 위젯)

routes/message.py
  → highschool/tea/message.html
  → highschool/st/message.html
  → highschool/fm/message.html
  → middleschool 동일 구조

routes/messenger.py
  → highschool/messenger.html, middleschool/messenger.html
  → static/js/messenger-widget.js (플로팅 위젯)

routes/survey.py
  → highschool/tea/schooladmin.html (설문 관리)
  → highschool/survey_respond.html (설문 응답)
  → middleschool 동일 구조

routes/attendance.py
  → highschool/tea/homeroom.html (출결 관리)
  → highschool/st_homeroom.html (내 출결)
  → highschool/fm_homeroom.html (자녀 출결)

routes/letter.py
  → highschool/tea/schooladmin.html (가정통신문 관리)
  → highschool/st_homeroom.html (학생 조회)
  → highschool/fm_homeroom.html (학부모 조회)

routes/afterschool.py
  → highschool/tea/schooladmin.html (방과후 관리)

routes/admission.py ★민감파일
  → highschool/admission/admission.html
  → highschool/admission/js/admission-*.js (5개)

routes/payment.py ★민감파일
  → templates/charge.html
  → highschool/tea.html (포인트 충전)

routes/homeroom_record.py ★민감파일
  → highschool/tea/school_record_maker.html
  → highschool/tea/homeroom.html

routes/subject_utils.py ★민감파일
  → routes/subject.py (AI 생기부)
  → routes/club.py (AI 생기부)
  → routes/admission.py (AI 분석)
```

## 유틸리티 → 의존하는 라우트

```
utils/db.py ★민감파일
  → 모든 routes/*.py (DB 연결)
  → 수정 시 전체 서비스에 영향

utils/email_util.py ★민감파일
  → routes/auth.py (비밀번호 찾기 이메일)

utils/elective_engine.py
  → routes/timetable_pipeline.py (교육반 배정)
  → highschool/tea/timetable_workflow.html

utils/timetable_engine.py
  → routes/timetable_pipeline.py (시간표 자동 생성)
  → highschool/tea/timetable_workflow.html

utils/push_helper.py
  → routes/push.py (푸시 알림)
```

## 프론트엔드 → 공유 JS

```
static/js/help-modal.js
  → 39개 HTML 페이지 (사용설명서 모달)
  → 사용설명서/ 폴더 18개 파일

static/js/messenger-widget.js
  → highschool/tea.html, st.html, fm.html
  → middleschool/tea.html, st.html, fm.html
  → (메인 대시보드에 플로팅 메신저)

static/js/pwa-install.js
  → 전체 페이지 (PWA 설치 프롬프트)

static/js/pwa-push.js
  → 전체 페이지 (푸시 알림 구독)

highschool/tea/subject.js (66.5KB)
  → highschool/tea/subject.html 에서만 로드
  → 교과+동아리+과제 전체 로직 포함
  → 수정 시 캐시 버스팅 필수 (?v= 업데이트)

highschool/tea/homeroom-*.js (5개 모듈, 총 92KB)
  → homeroom-core.js: 전역변수, init, switchTab, 유틸
  → homeroom-students.js: 학생/학부모 탭, 학생추가 모달
  → homeroom-counsel.js: 공지, 상담, 기록, 공통활동, 파일업로드
  → homeroom-timetable.js: 시간표, 출결
  → homeroom-vote.js: 투표 + switchTab 오버라이드 (반드시 마지막 로드!)
  → highschool/tea/homeroom.html 에서만 로드
  → 수정 시 캐시 버스팅 필수 (?v= 업데이트)
  → middleschool/tea/ 에 동일 파일 존재 (양쪽 동기화 필요)

highschool/tea/schooladmin-*.js (4개 모듈, 총 72KB)
  → schooladmin-core.js: 전역변수, init, switchTab, 공지/급식 모달
  → schooladmin-survey.js: 설문 탭 전체
  → schooladmin-afterschool.js: 방과후 탭 전체
  → schooladmin-letter.js: 가정통신문 + 관리 탭
  → highschool/tea/schooladmin.html 에서만 로드
  → 수정 시 캐시 버스팅 필수 (?v= 업데이트)
  → middleschool/tea/ 에 동일 파일 존재 (양쪽 동기화 필요)

highschool/admission/js/*.js (5개 모듈)
  → highschool/admission/admission.html 에서만 로드
```

## highschool ↔ middleschool 동기화 필요 파일

```
수정 시 반드시 양쪽 수정:
  highschool/tea.html          ↔ middleschool/tea.html
  highschool/st.html           ↔ middleschool/st.html
  highschool/fm.html           ↔ middleschool/fm.html
  highschool/tea/homeroom.html ↔ middleschool/tea/homeroom.html
  highschool/tea/homeroom-*.js ↔ middleschool/tea/homeroom-*.js (5개)
  highschool/tea/subject.html  ↔ middleschool/tea/subject.html
  highschool/tea/subject.js    ↔ middleschool/tea/subject.js
  highschool/tea/schooladmin.html ↔ middleschool/tea/schooladmin.html
  highschool/tea/schooladmin-*.js ↔ middleschool/tea/schooladmin-*.js (4개)
  highschool/tea/message.html  ↔ middleschool/tea/message.html
  ... (나머지 동일 구조 파일들)

  ※ 예외: timetable_workflow.html은 highschool에만 존재
```

## app.py 수정 시 영향

```
app.py 주요 섹션:
  라인 70-81:   AUTH_WHITELIST (화이트리스트 API)
  라인 84-164:  _TEACHER_ONLY_APIS (교사 전용 API 목록)
  라인 201-325: @before_request (미들웨어)
  라인 327-367: @after_request (로그인 기록)
  라인 401-451: Blueprint 등록

  새 API 추가 시:
  → 교사 전용이면 _TEACHER_ONLY_APIS에 추가
  → 비인증이면 AUTH_WHITELIST에 추가
  → 새 블루프린트면 import + register_blueprint 추가
```

## nginx 설정 수정 시

```
/etc/nginx/sites-enabled/flask_app
  → SSL 인증서 경로
  → Rate limit 설정
  → 캐싱 규칙
  → 보안 헤더

수정 후: sudo nginx -t && sudo systemctl reload nginx
```
