# 페이지 ↔ API 매핑표

> 각 프론트엔드 페이지가 호출하는 API 목록. 수정 시 영향범위 파악용.
> middleschool/ 은 highschool/ 과 동일 구조.

## 교사 페이지

### tea.html (교사 대시보드)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/teacher/info` | teacher.py | 교사 정보 |
| `/api/meal/today` | meal.py | 급식 |
| `/api/timetable/teacher` | timetable.py | 당일 시간표 |
| `/api/timetable/class` | timetable.py | 반 시간표 |
| `/api/notice/list` | notice.py | 공지 목록 |
| `/api/notice/create` | notice.py | 공지 작성 |
| `/api/message/rooms` | message.py | 메시지방 |
| `/api/homeroom/counsel-schedule/list` | homeroom.py | 상담 일정 |
| `/api/schedule/*` | schedule.py | 개인 일정 CRUD |
| `/api/notifications/check` | notice.py | 알림 |
| `/api/member/verify-password` | auth.py | 비번 확인 |
| `/api/member/info` | auth.py | 회원 정보 |
| `/api/teacher/update-class-info` | auth.py | 담임반 수정 |

### tea/homeroom.html (담임 관리)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/homeroom/check` | homeroom.py | 담임 확인 |
| `/api/homeroom/students` | homeroom.py | 학생 목록 |
| `/api/homeroom/students/search` | homeroom.py | 학생 검색 |
| `/api/homeroom/students/assign` | homeroom.py | 학생 배정 |
| `/api/homeroom/students/add` | homeroom.py | 학생 추가 |
| `/api/homeroom/students/remove` | homeroom.py | 학생 제거 |
| `/api/homeroom/students/upload` | homeroom.py | 엑셀 업로드 |
| `/api/homeroom/students/template` | homeroom.py | 엑셀 양식 |
| `/api/homeroom/notice/*` | homeroom.py | 담임 공지 CRUD |
| `/api/homeroom/counsel-schedule/*` | homeroom.py | 상담 일정 CRUD |
| `/api/homeroom/counsel-log/*` | homeroom.py | 상담 기록 CRUD |
| `/api/homeroom/counsel-file/*` | homeroom.py | 상담 파일 |
| `/api/homeroom/student-record/*` | homeroom.py | 학생 기록 |
| `/api/homeroom/common-activity/*` | homeroom.py | 공통활동 |
| `/api/timetable/class/week` | timetable.py | 주간 시간표 |
| `/api/timetable/class/save-manual` | timetable.py | 시간표 수동 저장 |
| `/api/attendance/*` | attendance.py | 출결 |
| `/api/homeroom/generate-record` | homeroom_gen.py | AI 기록 생성 |
| `/api/homeroom/school-record-gen/*` | homeroom_record.py | 생기부 |

### tea/subject.html + subject.js (교과/동아리)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/teacher/info` | teacher.py | 교사 정보 |
| `/api/subject/options` | subject.py | 과목 옵션 |
| `/api/subject/students` | subject.py | 과목 학생 |
| `/api/subject/record/*` | subject.py | 교과 기록 |
| `/api/subject/base/save` | subject.py | 기본정보 저장 |
| `/api/subject/write/save` | subject.py | 내용 저장 |
| `/api/subject/file/*` | subject.py | 파일 CRUD |
| `/api/subject/common/*` | subject.py | 공통항목 CRUD |
| `/api/subject/generate` | subject.py | AI 생기부 |
| `/api/subject/assignment/*` | assignment.py | 과제 CRUD |
| `/api/subject/submission/*` | assignment.py | 제출물 |
| `/api/subject/student-submissions` | subject.py | 학생 제출물 |
| `/api/club/*` | club.py | 동아리 전체 CRUD |
| `/api/timetable/teacher/week` | timetable.py | 주간 시간표 |
| `/api/timetable/teacher/save-manual` | timetable.py | 시간표 수동 |

### tea/schooladmin.html (학교관리)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/teacher/info` | teacher.py | 교사 정보 |
| `/api/notice/create` | notice.py | 공지 작성 |
| `/api/meal/*` | meal.py | 급식 관리 |
| `/api/survey/*` | survey.py | 설문 전체 CRUD |
| `/api/afterschool/*` | afterschool.py | 방과후 전체 CRUD |
| `/api/letter/*` | letter.py | 가정통신문 CRUD |

### tea/timetable_workflow.html (시간표 워크플로우)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/teacher/info` | teacher.py | 교사 정보 |
| `/api/cours-subject/*` | timetable.py | 기초DB |
| `/api/timetable-data/*` | timetable.py | 과목 설정 |
| `/api/timetable-survey/*` | timetable.py | 설문 기간 |
| `/api/timetable-stu/*` | timetable.py | 학생 데이터 |
| `/api/timetable-tea/*` | timetable.py | 교사 편성 |
| `/api/timetable-constraint/*` | timetable.py | 제약 조건 |
| `/api/timetable-fixed-subject/*` | timetable.py | 고정 교과 |
| `/api/class-maker/*` | class_maker.py | 반편성 |
| `/api/pipeline/generate` | timetable_pipeline.py | 시간표 생성 |
| `/api/pipeline/check` | timetable_pipeline.py | 사전 점검 |
| `/api/pipeline/assign-electives` | timetable_pipeline.py | 교육반 배정 |
| `/api/timetable/schedule/*` | timetable.py | 시간표 스케줄 |

### tea/school_record_maker.html (생기부)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/teacher/info` | teacher.py | 교사 정보 |
| `/api/homeroom/check` | homeroom.py | 담임 확인 |
| `/api/homeroom/students` | homeroom.py | 학생 목록 |
| `/api/homeroom/student-record/*` | homeroom.py | 학생 기록 |
| `/api/homeroom/counsel-*` | homeroom.py | 상담 기록/파일 |
| `/api/homeroom/common-activity/*` | homeroom.py | 공통활동 |
| `/api/homeroom/generate-record` | homeroom_gen.py | AI 생성 |
| `/api/homeroom/school-record-gen/*` | homeroom_record.py | 생기부 |

### tea/message.html (교사 메시지)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/message/rooms` | message.py | 대화방 목록 |
| `/api/message/list` | message.py | 메시지 목록 |
| `/api/message/send` | message.py | 메시지 전송 |
| `/api/message/poll` | message.py | 실시간 폴링 |
| `/api/message/read` | message.py | 읽음 처리 |
| `/api/message/users` | message.py | 사용자 목록 |
| `/api/message/users/groups` | message.py | 그룹 목록 |
| `/api/message/users/by-group` | message.py | 그룹별 사용자 |
| `/api/message/room/*` | message.py | 대화방 CRUD |
| `/api/message/file/*` | message.py | 파일 전송 |

---

## 학생 페이지

### st.html (학생 대시보드)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/student/info` | student.py | 학생 정보 |
| `/api/meal/today` | meal.py | 급식 |
| `/api/timetable/student` | timetable.py | 개인 시간표 |
| `/api/timetable/class` | timetable.py | 반 시간표 |
| `/api/notice/list` | notice.py | 공지 |
| `/api/schedule/*` | schedule.py | 일정 CRUD |
| `/api/notifications/check` | notice.py | 알림 |
| `/api/message/rooms` | message.py | 메시지방 |

### st_homeroom.html (학생 담임)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/student/info` | student.py | 학생 정보 |
| `/api/homeroom/teacher` | homeroom.py | 담임 정보 |
| `/api/homeroom/counsel-schedule/list` | homeroom.py | 상담 일정 |
| `/api/attendance/my` | attendance.py | 내 출결 |
| `/api/homeroom/notice/list` | homeroom.py | 담임 공지 |
| `/api/letter/*` | letter.py | 가정통신문 |

### st/lesson_activity.html (수업활동)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/student/my-subjects` | assignment.py | 내 과목 |
| `/api/student/my-assignments` | assignment.py | 내 과제 |
| `/api/subject/submission/upload` | assignment.py | 제출 업로드 |
| `/api/student/my-clubs` | assignment.py | 내 동아리 |
| `/api/student/club-file/*` | assignment.py | 동아리 파일 |

### st/message.html (학생 메시지)
- tea/message.html과 동일 API (역할 제한: 교사에게만 메시지 가능)

---

## 학부모 페이지

### fm.html (학부모 대시보드)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/parent/info` | parent.py | 학부모 정보 |
| `/api/meal/today` | meal.py | 급식 |
| `/api/timetable/class` | timetable.py | 반 시간표 |
| `/api/notice/list` | notice.py | 공지 |
| `/api/schedule/*` | schedule.py | 일정 |
| `/api/homeroom/teacher` | homeroom.py | 담임 정보 |
| `/api/homeroom/counsel-schedule/*` | homeroom.py | 상담 신청 |
| `/api/message/rooms` | message.py | 메시지방 |

### fm_homeroom.html (학부모 담임)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/parent/info` | parent.py | 학부모 정보 |
| `/api/homeroom/teacher` | homeroom.py | 담임 정보 |
| `/api/homeroom/notice/list` | homeroom.py | 담임 공지 |
| `/api/student/my-assignments` | assignment.py | 자녀 과제 |
| `/api/attendance/child` | attendance.py | 자녀 출결 |
| `/api/letter/*` | letter.py | 가정통신문 |

### fm/message.html (학부모 메시지)
- tea/message.html과 동일 API (역할 제한)

---

## 공통 페이지

### index.html (로그인)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/public/stats` | app.py | 통계 |
| `/login_process` | auth.py | 로그인 |
| `/api/find-id` | auth.py | ID 찾기 |
| `/api/find-password` | auth.py | PW 찾기 |
| `/api/select-role` | auth.py | 역할 선택 |
| `/api/select-child` | auth.py | 자녀 선택 |

### notice.html (공지사항)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/notice/*` | notice.py | 공지 CRUD |

### messenger.html + messenger-widget.js
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/messenger/conversations` | messenger.py | 대화방 |
| `/api/messenger/messages` | messenger.py | 메시지 |
| `/api/messenger/messages/send` | messenger.py | 전송 |
| `/api/messenger/messages/delete` | messenger.py | 삭제 |
| `/api/messenger/contacts` | messenger.py | 연락처 |
| `/api/messenger/conversations/create` | messenger.py | 대화방 생성 |
| `/api/messenger/conversations/leave` | messenger.py | 나가기 |
| `/api/messenger/unread-count` | messenger.py | 미읽음 수 |
| `/api/messenger/file/download` | messenger.py | 파일 |

### survey_respond.html (설문 응답)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/survey/my-surveys` | survey.py | 내 설문 |
| `/api/survey/detail` | survey.py | 설문 상세 |
| `/api/survey/respond` | survey.py | 응답 제출 |

### mypage.html (마이페이지)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/schools` | auth.py | 학교 목록 |
| `/api/member/verify-password` | auth.py | 비번 확인 |
| `/api/member/info` | auth.py | 회원 정보 |
| `/api/member/update` | auth.py | 정보 수정 |
| `/api/member/change-password` | auth.py | 비번 변경 |

### admission/admission.html (입시관리)
| API | 라우트 파일 | 용도 |
|-----|-----------|------|
| `/api/admission/years` | admission.py | 연도 목록 |
| `/api/admission/list/{year}` | admission.py | 대학 목록 |
| `/api/admission/pdf/...` | admission.py | PDF |
| `/api/admission/summary/...` | admission.py | 요약 |
| `/api/admission/record/*` | admission.py | 기록 CRUD |
| `/api/admission/mock/*` | admission.py | 모의고사 |
| `/api/admission/csat/*` | admission.py | 수능 |
| `/api/admission/share/*` | admission.py | 공유 |
| `/api/admission/analyze/*` | admission.py | AI 분석 |
| `/api/admission/classes` | admission.py | 반 목록 |
| `/api/dept/*` | admission.py | 학과 검색 |
| `/api/homeroom/students` | homeroom.py | 학생 목록 |
