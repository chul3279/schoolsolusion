    // ═══════════════════════════════════════════
    // 설정
    // ═══════════════════════════════════════════
    const API_BASE = '';

    // ═══════════════════════════════════════════
    // 사이드바 메뉴 설정
    // ═══════════════════════════════════════════
    const menuConfig = {
        teacher: {
            title: '선생님',
            menus: [
                { href: '/highschool/tea.html', icon: 'fas fa-desktop', color: 'text-blue-400', label: '대시보드' },
                { href: '/highschool/tea/homeroom.html', icon: 'fas fa-chalkboard-user', color: 'text-green-400', label: '담임업무' },
                { href: '/highschool/tea/subject.html', icon: 'fas fa-book-open', color: 'text-purple-400', label: '교과업무' },
                { href: '/highschool/admission/admission.html', icon: 'fas fa-graduation-cap', color: 'text-pink-400', label: '입시상담', active: true },
                { href: '/highschool/tea/schooladmin.html', icon: 'fas fa-cog', color: 'text-yellow-400', label: '행정업무' }
            ]
        },
        student: {
            title: '학생',
            menus: [
                { href: '/highschool/st.html', icon: 'fas fa-desktop', color: 'text-blue-400', label: '대시보드' },
                { href: '/highschool/st_homeroom.html', icon: 'fas fa-users', color: 'text-green-400', label: '학급활동' },
                { href: '/highschool/admission/admission.html', icon: 'fas fa-graduation-cap', color: 'text-pink-400', label: '입시상담', active: true }
            ]
        },
        parent: {
            title: '학부모님',
            menus: [
                { href: '/highschool/fm.html', icon: 'fas fa-desktop', color: 'text-blue-400', label: '대시보드' },
                { href: '/highschool/fm_homeroom.html', icon: 'fas fa-users', color: 'text-green-400', label: '학급정보' },
                { href: '/highschool/admission/admission.html', icon: 'fas fa-graduation-cap', color: 'text-pink-400', label: '입시상담', active: true }
            ]
        }
    };

    // ═══════════════════════════════════════════
    // 상태 변수
    // ═══════════════════════════════════════════
    let yearData = null;
    let selectedType = null;
    let currentPdfUrl = null;
    let selectedRecordFile = null;
    let currentUser = null;
    let selectedMockOrg = null;      // 'local' | 'kice' | 'private'
    let selectedMockExamType = null; // 'local_3' | 'kice_6' | 'private' 등
    let selectedMockTrack = null;
    let selectedCsatTrack = null;
    let currentCurriculum = null; // '2015' 또는 '2022'

    // ═══════════════════════════════════════════
    // 초기화
    // ═══════════════════════════════════════════
    document.addEventListener('DOMContentLoaded', () => {
        const userStr = localStorage.getItem('schoolus_user');
        if (!userStr) {
            alert('로그인이 필요합니다.');
            window.location.href = '/';
            return;
        }
        currentUser = JSON.parse(userStr);
        const role = currentUser.member_roll || 'student';
        const config = menuConfig[role] || menuConfig.student;

        document.getElementById('user-name').textContent = (currentUser.member_name || '사용자') + ' ' + config.title;
        document.getElementById('user-avatar').textContent = (currentUser.member_name || 'U').charAt(0);
        document.getElementById('user-info').textContent = currentUser.member_school || '-';
        renderSidebarMenu(config.menus);

        // 교사인 경우 학생 선택 셀렉터 표시
        if (role === 'teacher') {
            document.getElementById('mydata-student-selector').classList.remove('hidden');
        }

        // 학생/학부모인 경우 학년으로 교육과정 자동 설정 + 이력 로드
        if (role !== 'teacher') {
            const grade = parseInt(currentUser.class_grade) || 0;
            const autoCurriculum = grade >= 3 ? '2015' : '2022';
            onCurriculumSelect(autoCurriculum);
            refreshHistory(null);
            refreshAnalysisPrereq(null);
        }

        // 교사인 경우 승인 대기 목록 로드
        if (role === 'teacher') {
            loadPendingApprovals();
        }

        loadYears();
    });

    // ═══════════════════════════════════════════
    // API 호출
    // ═══════════════════════════════════════════
    async function apiCall(endpoint, options = {}) {
        try {
            const res = await fetch(`${API_BASE}${endpoint}`, options);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`API 오류 [${endpoint}]:`, err);
            return null;
        }
    }

