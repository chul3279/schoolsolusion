# 디버깅 가이드

## 1. 로그 위치

```
Gunicorn 접근 로그: /var/log/gunicorn/access.log
Gunicorn 에러 로그: /var/log/gunicorn/error.log
nginx 접근 로그:    /var/log/nginx/access.log
nginx 에러 로그:    /var/log/nginx/error.log
systemd 로그:       journalctl -u schoolus -f
```

### 실시간 로그 확인
```bash
# Gunicorn 에러 실시간
tail -f /var/log/gunicorn/error.log

# nginx 에러 실시간
tail -f /var/log/nginx/error.log

# systemd 서비스 로그
journalctl -u schoolus -f --no-pager

# 특정 API 에러만 필터
grep "오류" /var/log/gunicorn/error.log | tail -20
```

## 2. 서비스 재시작

```bash
# 재시작 (NOPASSWD 설정 완료)
sudo systemctl restart schoolus

# 상태 확인
sudo systemctl status schoolus --no-pager -l

# nginx 재시작 (설정 변경 시)
sudo systemctl reload nginx
```

## 3. 자주 발생하는 문제와 해결

### 3.1 모바일에서 JS/CSS 수정 반영 안 됨
- **원인**: 브라우저 캐시 (nginx 7일 캐시)
- **해결**: 캐시 버스팅 쿼리스트링 추가
```html
<!-- 변경 전 -->
<script src="/tea/subject.js?v=20260221a"></script>
<!-- 변경 후 (날짜 업데이트) -->
<script src="/tea/subject.js?v=20260226a"></script>
```
- **주의**: subject.js는 현재 `?v=20260221a`로 로드 — 수정 시 버전 업데이트 필수

### 3.2 세션 만료 / 401 에러
- **원인**: 세션 키 불일치 또는 서버 재시작
- **확인**: `session.get('user_role')` 사용 여부 확인
- **주의**: 과거 `session['member_roll']` 잔재 → `session['user_role']`로 통일됨

### 3.3 DB 연결 실패
- **확인**: `mysql -h 10.10.0.3 -u school_user -p3279 school_db -e "SELECT 1;"`
- **원인1**: DB 서버 다운 → DB 서버 상태 확인
- **원인2**: 커넥션 풀 소진 → Gunicorn 재시작
- **위치**: utils/db.py (PersistentDB 커넥션 풀)

### 3.4 SFTP 연결 실패 (파일 업로드/다운로드)
- **확인**: `sftp manager@10.10.0.4` (pw: 3279)
- **원인**: 연결 타임아웃 (10분) 후 재연결 실패
- **위치**: routes/subject_utils.py (전역 SFTP 클라이언트)
- **해결**: Gunicorn 재시작으로 SFTP 재연결

### 3.5 Gemini AI 생기부 생성 실패
- **확인**: config/gemini_keys.py 키 유효성
- **원인1**: API 키 만료/할당량 초과
- **원인2**: 프롬프트 너무 길어서 타임아웃
- **위치**: routes/subject_utils.py (다중 키 로드 분산)

### 3.6 시간표 교육반 배정 실패
- **원인1**: 밴드 균형 오류 (교육반 합계 ≠ 원반수 × N)
  → Step 5에서 교육반 수 조정
- **원인2**: 학생 백트래킹 실패 (같은 밴드에 2과목)
  → band_group 설정 확인, 교육반 수 확인
- **위치**: utils/elective_engine.py

### 3.7 토스 결제 실패
- **확인**: routes/payment.py의 API 키
- **원인**: 테스트/실환경 키 불일치
- **위치**: routes/payment.py (민감파일)

### 3.8 nginx 502 Bad Gateway
- **원인**: Gunicorn 프로세스 다운
- **확인**: `sudo systemctl status schoolus`
- **해결**: `sudo systemctl restart schoolus`
- **원인2**: 소켓 파일 없음 → RuntimeDirectory 확인

### 3.9 정적 파일 404
- **원인**: nginx try_files 순서 문제
- **확인**: 파일이 /var/www/web/html/ 에 실제 존재하는지
- **참고**: 한글 경로(사용설명서/)는 URL 인코딩 필요

## 4. DB 직접 조회 명령어

```bash
# 기본 접속
mysql -h 10.10.0.3 -u school_user -p3279 school_db

# 특정 학교 교사 조회
mysql -h 10.10.0.3 -u school_user -p3279 school_db -e "
  SELECT member_id, member_name, class_grade, class_no, department
  FROM tea_all WHERE school_id='학교ID';"

# 특정 학교 학생 수
mysql -h 10.10.0.3 -u school_user -p3279 school_db -e "
  SELECT class_grade, class_no, COUNT(*) as cnt
  FROM stu_all WHERE school_id='학교ID'
  GROUP BY class_grade, class_no;"

# 시간표 데이터 확인
mysql -h 10.10.0.3 -u school_user -p3279 school_db -e "
  SELECT grade, class_no, day_of_week, period, subject, member_name
  FROM timetable WHERE school_id='학교ID' AND grade='2'
  ORDER BY class_no, FIELD(day_of_week,'월','화','수','목','금'), period;"

# 선택과목 교육반 배정 결과
mysql -h 10.10.0.3 -u school_user -p3279 school_db -e "
  SELECT subject, group_no, band, COUNT(*) as students
  FROM timetable_stu_group WHERE school_id='학교ID' AND grade='2'
  GROUP BY subject, group_no, band
  ORDER BY band, subject, group_no;"
```

## 5. 수정 후 체크리스트

### Python 파일 수정 시
- [ ] 문법 에러 없는지 확인: `python3 -c "import py_compile; py_compile.compile('파일경로')"`
- [ ] `sudo systemctl restart schoolus` 실행
- [ ] `sudo systemctl status schoolus` 정상 확인
- [ ] 에러 로그 확인: `tail -5 /var/log/gunicorn/error.log`
- [ ] 민감파일이면 데이터서버 백업 갱신

### HTML/JS 파일 수정 시
- [ ] 캐시 버스팅 쿼리스트링 업데이트 (해당 시)
- [ ] 모바일 크롬 강력 새로고침 테스트
- [ ] highschool + middleschool 양쪽 수정했는지 확인
- [ ] 사용설명서 갱신 필요한지 확인 (help-docs-mapping.md 참조)

### DB 스키마 변경 시
- [ ] ALTER TABLE은 서비스 중단 없이 가능한지 확인
- [ ] 관련 Python 코드의 컬럼명 일치 확인
- [ ] 인덱스 필요 여부 확인

## 6. 성능 문제 진단

```bash
# Gunicorn 워커 상태
ps aux | grep gunicorn | wc -l

# 메모리 사용량
free -h

# 디스크 사용량
df -h /var/www/web/html

# MySQL 느린 쿼리 (DB 서버에서)
mysql -h 10.10.0.3 -u school_user -p3279 -e "SHOW PROCESSLIST;"

# nginx 동시 접속 수
ss -s | head -5
```

## 7. 민감파일 수정 시 백업 절차

```bash
# 대상 파일 6개 (수정 후 반드시 실행)
sshpass -p 3279 scp routes/payment.py manager@10.10.0.4:/home/manager/민감파일/
sshpass -p 3279 scp utils/email_util.py manager@10.10.0.4:/home/manager/민감파일/
sshpass -p 3279 scp utils/db.py manager@10.10.0.4:/home/manager/민감파일/
sshpass -p 3279 scp routes/subject_utils.py manager@10.10.0.4:/home/manager/민감파일/
sshpass -p 3279 scp routes/homeroom_record.py manager@10.10.0.4:/home/manager/민감파일/
sshpass -p 3279 scp routes/admission.py manager@10.10.0.4:/home/manager/민감파일/
```
