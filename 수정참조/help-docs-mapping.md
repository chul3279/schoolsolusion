# 사용설명서 파일 ↔ 페이지 매핑

## 규칙
- 기능 수정 시 해당 설명서도 반드시 동시 갱신
- 설명서 위치: `/var/www/web/html/사용설명서/`
- 공통 JS: `/static/js/help-modal.js`

## 매핑표

| data-doc 값 | 설명서 파일 | 적용 페이지 |
|---|---|---|
| teacher-dashboard | teacher-dashboard.html | highschool/tea.html, middleschool/tea.html |
| homeroom | homeroom.html | highschool/tea/homeroom.html, middleschool/tea/homeroom.html |
| subject | subject.html | highschool/tea/subject.html, middleschool/tea/subject.html |
| schooladmin | schooladmin.html | highschool/tea/schooladmin.html, middleschool/tea/schooladmin.html |
| timetable-workflow | timetable-workflow.html | highschool/tea/timetable_workflow.html |
| school-record | school-record.html | highschool/tea/school_record_maker.html, middleschool/tea/school_record_maker.html |
| student-dashboard | student-dashboard.html | highschool/st.html, middleschool/st.html |
| student-homeroom | student-homeroom.html | highschool/st_homeroom.html, middleschool/st_homeroom.html |
| student-activity | student-activity.html | highschool/st/lesson_activity.html, middleschool/st/lesson_activity.html |
| parent-dashboard | parent-dashboard.html | highschool/fm.html, middleschool/fm.html |
| parent-homeroom | parent-homeroom.html | highschool/fm_homeroom.html, middleschool/fm_homeroom.html |
| notice | notice.html | highschool/notice.html, middleschool/notice.html |
| messenger | messenger.html | highschool/messenger.html, middleschool/messenger.html |
| message | message.html | highschool/tea/message.html, st/message.html, fm/message.html × 2 |
| survey | survey.html | highschool/survey_respond.html, middleschool/survey_respond.html |
| mypage | mypage.html | highschool/mypage.html, middleschool/mypage.html |
| admission | admission.html | highschool/admission/admission.html, middleschool/admission/admission.html |
| login | login.html | index.html, register.html |
