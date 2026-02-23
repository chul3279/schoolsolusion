# admission.html 개발 계획

> 최종 수정: 2026-02-18
> 현재 파일: `admission.html` 2,187줄 / 142KB

---

## 현황 정리

### 완료된 기능

| 영역 | 내용 |
|------|------|
| **대학 정보** | 연도별 PDF 목록 조회, 뷰어, 요약 |
| **입시자료 > 생기부** | 파일 선택 UI, 업로드 API 연결 (`/api/admission/record/upload`) |
| **입시자료 > 모의고사 입력** | 2015/2022 교육과정 분리 폼, 주관기관(교육청/평가원/사설) + 월 선택, 저장 API 연결 |
| **입시자료 > 수능 입력** | 2015/2022 분리 폼, 저장 API 연결 |
| **DB** | `admission_student_record`, `admission_mock_exam`, `admission_csat_score` 테이블 (v2) |
| **API (admission.py)** | 13개: record·mock·csat 각 save/list/delete + share request/approve/reject/pending |

### 미연결 API (백엔드 구현 완료, 프론트 미연결)

- `GET /api/admission/record/list` → `#record-history` 렌더링 없음
- `GET /api/admission/mock/list` → `#mock-history` 렌더링 없음
- `GET /api/admission/csat/list` → `#csat-history` 렌더링 없음
- `POST /api/admission/record/delete` / `mock/delete` / `csat/delete`
- `POST /api/admission/share/request` / `approve` / `reject`
- `GET /api/admission/share/pending`

### 껍데기만 있는 탭

- **수시지원 가능대학** (`#content-early`) — 안내 문구만
- **정시지원 가능대학** (`#content-regular`) — 안내 문구만
- **생기부 분석** (`#content-analysis`) — 안내 문구만

---

## 개발 계획

### Phase 1 — 데이터 이력 표시 (즉시 작업 가능)

> 저장만 되고 보이지 않는 상태. 사용성 완성을 위한 필수 작업.

#### 1-1. 생기부 업로드 이력 (`#record-history`)

- 페이지 로드 및 업로드 성공 시 `/api/admission/record/list` 호출
- 카드 형태로 렌더링:
  - 파일명, 업로드일시, 업로더(교사명), 파일크기
  - `share_status` 배지: `private(비공개)` / `requested(공유요청중)` / `approved(공유됨)`
  - 삭제 버튼 (본인 업로드만)
  - 학생/학부모: "교사에게 공유 요청" 버튼 (status=private일 때)
  - 교사: 공유 요청 들어온 항목에 "승인/거절" 버튼

#### 1-2. 모의고사 성적 이력 (`#mock-history`)

- 저장 성공 시 및 탭 진입 시 `/api/admission/mock/list` 호출
- 테이블 형태:
  - 학년도, 시험 (exam_type 라벨 변환: `local_3` → `교육청 3월` 등), 계열, 주요 과목 등급
  - `share_status` 배지 + 공유 요청/승인 버튼
  - 삭제 버튼

**exam_type → 표시명 매핑:**
```
local_3  → 교육청 3월    local_5  → 교육청 5월
local_6  → 교육청 6월    local_7  → 교육청 7월
local_9  → 교육청 9월    local_10 → 교육청 10월
kice_6   → 평가원 6월    kice_9   → 평가원 9월
private  → [exam_name 그대로 표시]
```

#### 1-3. 수능 성적 이력 (`#csat-history`)

- 구조 동일, `/api/admission/csat/list` 호출
- 학년도, 계열, 국/수/영/탐 등급 요약

---

### Phase 2 — 공유/승인 시스템 UI

> API는 완성. 역할별 UI 분기 필요.

#### 2-1. 학생/학부모 — 공유 요청

- 이력 카드에 `share_status === 'private'`이면 **"담임에게 공유 요청"** 버튼 표시 (학생·학부모 모두)
- 클릭 시 `POST /api/admission/share/request` → 버튼 비활성화 + 배지 변경

#### 2-2. 교사 — 공유 승인 패널

- 별도 섹션 또는 모달: "공유 승인 대기 목록"
- `GET /api/admission/share/pending` 로 로드
- 항목별 **승인 / 거절** 버튼
- 승인 후 해당 학생 데이터가 교사 view에서 조회 가능

#### 2-3. 교사 — 본인 입력 데이터 공유

- 교사가 직접 입력한 데이터도 `share_status='private'` → 학생에게 공유 가능하도록 버튼 제공

---

### Phase 3 — 교사용 학생 선택 API 연결

> 현재 TODO 주석으로 처리된 부분

#### 3-1. 반 목록 조회

- `onMydataGradeChange()` 내 TODO: 학년 선택 시 `/api/homeroom/classes?grade=X` 호출
- 현재는 1~12반 하드코딩

#### 3-2. 학생 목록 조회

- `onMydataClassChange()` 내: `/api/homeroom/students` 연결은 있으나 파라미터 확인 필요
- 학생 선택 후 기존 데이터 자동 로드 (mock/csat/record 이력 표시)

---

### Phase 4 — 분석 기능 (포인트 차감)

> 현재 탭이 안내 문구만 있는 상태

#### 4-1. 정시지원 가능대학 (`#content-regular`)

- 입력된 수능/모의고사 성적 기반
- 포인트 차감 확인 → API 호출 → 대학 목록 표시
- **전제조건**: 수능 또는 모의고사 데이터 1건 이상 존재

#### 4-2. 수시지원 가능대학 (`#content-early`)

- 내신 성적 + 생기부 기반
- **전제조건**: 생기부 업로드 1건 이상 존재

#### 4-3. 생기부 분석 (`#content-analysis`)

- Claude AI API 연동
- 업로드된 생기부 PDF → 텍스트 추출 → 분석 → 전략 제안
- **전제조건**: 생기부 업로드 필수

---

### Phase 5 — 파일 분리 (리팩토링)

> 기능 완성 후 진행. 현재는 불필요.

```
highschool/admission/
  admission.html        ← HTML + CSS (레이아웃)
  js/
    admission-core.js   ← 공통 유틸, apiCall, 초기화
    admission-record.js ← 생기부 탭
    admission-mock.js   ← 모의고사 탭
    admission-csat.js   ← 수능 탭
    admission-share.js  ← 공유/승인
    admission-analysis.js ← 분석 탭
```

---

## 작업 순서 권장

```
Phase 1-2 (이력 표시 + 공유 UI) → Phase 3 (학생 선택 API) → Phase 4 (분석) → Phase 5 (분리)
```

Phase 1이 가장 사용성에 직접적인 영향. 저장하고 확인이 안 되면 기능을 믿기 어려움.

---

## 참고: DB exam_type ENUM 값

| 코드 | 표시 | 교육과정 |
|------|------|------|
| `local_3` | 교육청 3월 | 2015·2022 |
| `local_5` | 교육청 5월 | 2015 |
| `local_6` | 교육청 6월 | 2022 |
| `local_7` | 교육청 7월 | 2015 |
| `local_9` | 교육청 9월 | 2022 |
| `local_10` | 교육청 10월 | 2015·2022 |
| `kice_6` | 평가원 6월 | 2015 |
| `kice_9` | 평가원 9월 | 2015 |
| `private` | exam_name 사용 | 2015·2022 |
