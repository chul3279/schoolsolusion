# SchoolUS 프로젝트 메모리

## 서버 정보
- 웹서버: /var/www/web/html (Flask + nginx)
- DB서버: 10.10.0.3 / user: school_user / pw: 3279 / db: school_db
- 데이터서버: 10.10.0.4 / pw: 3279 (SFTP 파일 저장소)
- 도메인: schoolwithus.co.kr, schoolwithus.kr

## DB 핵심 테이블 구조
- member: 로그인 계정 (member_id PK, member_sn=비밀번호, member_roll=역할, member_email)
- tea_all: 교사 정보 (member_id, school_id, class_grade, class_no, department)
- stu_all: 학생 정보 (member_id, school_id, class_grade, class_no, class_num, point)
- fm_all: 학부모 정보 (member_id, school_id, child_name, child_birth)
- schoolinfo: 학교 목록 (약 10,549개)

## 세션 키 규칙 (중요!)
- 로그인 시 설정: session['user_role'] = 'teacher'|'student'|'parent'
- 권한 체크 시: session.get('user_role') 사용
- 주의: 과거 코드에 session['member_roll'] 잔재 있을 수 있음 → user_role로 통일 완료

## 로그인 흐름
- nginx: try_files $uri $uri/ @flask (정적파일 우선, 없으면 Flask)
- 로그인 후 프론트에서 직접 /highschool/tea.html 등으로 이동 (Flask render_template 미사용)

## 완료된 수정
- session['member_roll'] → session['user_role'] 통일 (homeroom, subject, club, assignment)
- subject.js 모바일 반 멀티셀렉트 드롭다운 닫힘 버그 (캐시 버스팅으로 해결)

## 디버깅 인사이트
- 정적 JS/CSS 수정 후 모바일에서 반영 안 될 때 → 캐시 버스팅 쿼리스트링 필수 (예: script.js?v=날짜)
- subject.js는 현재 `?v=20260221a`로 로드됨 — 수정 시 버전 업데이트 필요

## 사용자 워크플로우 설정
- 단순 조회/검색(파일 읽기, grep, wc 등)은 확인 없이 바로 실행
- 파일 수정/생성/삭제만 기본 확인 동작 유지
- 하나의 작업(task)에 대한 동의는 한 번으로 전체 처리 — 중간에 재확인하지 않음

## 민감파일 백업 (중요!)
- 키값 포함 파일은 .gitignore에 등록되어 GitHub에 올라가지 않음
- 민감파일 백업 위치: 데이터서버(10.10.0.4) `/home/manager/민감파일/`
- 대상 파일 6개:
  - routes/payment.py (토스 페이먼츠 키)
  - utils/email_util.py (Gmail SMTP 인증)
  - utils/db.py (DB 접속 정보)
  - routes/subject_utils.py (SFTP 접속 정보 + Gemini API)
  - routes/homeroom_record.py (데이터서버 접속 정보)
  - routes/admission.py (데이터서버 접속 정보)
- 이 파일들 수정 시 데이터서버 백업도 함께 갱신할 것

## GitHub 백업
- 저장소: https://github.com/chul3279/schoolsolusion (private)
- 자동 백업: 6시간마다 cron (/home/manager/git-backup.sh)
- git-filter-repo로 히스토리 정리 완료 (2026-02-25) — 이전 키값 흔적 제거됨

## 사용설명서 시스템
- 위치: `/var/www/web/html/사용설명서/` (18개 HTML 파일)
- 공통 JS: `/static/js/help-modal.js` (플로팅 ? 버튼 + 모달)
- 각 페이지 `</body>` 직전에 `<script src="/static/js/help-modal.js" data-doc="파일명"></script>` 삽입 (39개 페이지)
- **기능 수정 시 해당 설명서 파일도 반드시 동시 갱신**
- 파일명↔페이지 매핑: memory/help-docs-mapping.md 참조

## 서비스 관리
- schoolus.service: Gunicorn 24워커, manager 유저, 소켓=/run/flask_app/flask_app.sock
- 재시작 명령: sudo systemctl restart schoolus
- sudo 패스워드: 3279 (echo '3279' | sudo -S ...)
- NOPASSWD 설정 완료 (/etc/sudoers.d/manager-schoolus) → 이후 sudo 패스워드 불필요
