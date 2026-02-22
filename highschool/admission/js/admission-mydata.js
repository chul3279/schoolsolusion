    // ─── 교사용 학생 셀렉터 ───
    function onMydataGradeChange() {
        const grade = document.getElementById('mydata-grade').value;
        const selClass = document.getElementById('mydata-class');
        const selStudent = document.getElementById('mydata-student');
        selClass.innerHTML = '<option value="">반 선택</option>';
        selStudent.innerHTML = '<option value="">반을 먼저 선택</option>';
        selClass.disabled = !grade;
        selStudent.disabled = true;
        document.getElementById('mydata-student-info').textContent = '학생을 선택하세요';

        // 교사용: 학년에 따라 교육과정 자동 전환 + 반 목록 API 조회
        if (grade) {
            const autoCurriculum = parseInt(grade) >= 3 ? '2015' : '2022';
            onCurriculumSelect(autoCurriculum);
            loadClassList(grade).then(() => { selClass.disabled = false; });
        }
    }

    async function onMydataClassChange() {
        const grade = document.getElementById('mydata-grade').value;
        const cls = document.getElementById('mydata-class').value;
        const selStudent = document.getElementById('mydata-student');
        selStudent.innerHTML = '<option value="">학생 선택</option>';
        selStudent.disabled = !cls;
        document.getElementById('mydata-student-info').textContent = '학생을 선택하세요';

        if (grade && cls) {
            const data = await apiCall(`/api/homeroom/students?school_id=${encodeURIComponent(currentUser.school_id || '')}&class_grade=${grade}&class_no=${cls}`);
            if (data && data.students) {
                data.students.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.member_id;
                    opt.textContent = `${s.class_num}번 ${s.member_name}`;
                    selStudent.appendChild(opt);
                });
                selStudent.disabled = false;
            }
        }
    }

    function onMydataStudentChange() {
        const studentId = document.getElementById('mydata-student').value;
        const info = document.getElementById('mydata-student-info');
        if (studentId) {
            const sel = document.getElementById('mydata-student');
            info.innerHTML = `<span class="text-teal-600 font-bold"><i class="fas fa-check-circle mr-1"></i>${sel.options[sel.selectedIndex].text} 선택됨</span>`;
            loadStudentAdmissionData(studentId);
        } else {
            info.textContent = '학생을 선택하세요';
        }
    }

    async function loadStudentAdmissionData(studentId) {
        refreshHistory(studentId);
        loadPendingApprovals();
        refreshAnalysisPrereq(studentId);
    }

    // ─── 생기부 업로드 ───
    function handleRecordDrop(e) {
        e.preventDefault();
        e.target.closest('.upload-zone').classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) processRecordFile(files[0]);
    }

    function handleRecordFile(input) {
        if (input.files.length > 0) processRecordFile(input.files[0]);
    }

    function processRecordFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            alert('PDF 파일만 업로드 가능합니다.');
            return;
        }
        if (file.size > 20 * 1024 * 1024) {
            alert('파일 크기는 20MB를 초과할 수 없습니다.');
            return;
        }
        selectedRecordFile = file;
        document.getElementById('record-file-name').textContent = file.name;
        document.getElementById('record-file-size').textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
        document.getElementById('record-upload-placeholder').classList.add('hidden');
        document.getElementById('record-upload-selected').classList.remove('hidden');
        document.getElementById('record-upload-zone').classList.add('has-file');
        document.getElementById('btn-upload-record').disabled = false;
    }

    function clearRecordFile() {
        selectedRecordFile = null;
        document.getElementById('record-file-input').value = '';
        document.getElementById('record-upload-placeholder').classList.remove('hidden');
        document.getElementById('record-upload-selected').classList.add('hidden');
        document.getElementById('record-upload-zone').classList.remove('has-file');
        document.getElementById('btn-upload-record').disabled = true;
    }

    async function uploadRecord() {
        if (!selectedRecordFile) return;

        const btn = document.getElementById('btn-upload-record');
        btn.disabled = true;
        btn.innerHTML = '<span class="loading-spinner" style="width:16px;height:16px;border-width:2px;margin-right:8px;display:inline-block;vertical-align:middle;border-top-color:white;border-color:rgba(255,255,255,0.3);border-top-color:white;"></span>업로드 중...';

        const formData = new FormData();
        formData.append('file', selectedRecordFile);
        formData.append('school_id', currentUser.school_id || '');

        // 교사인 경우 선택된 학생, 학생인 경우 본인
        const role = currentUser.member_roll || 'student';
        if (role === 'teacher') {
            const studentId = document.getElementById('mydata-student').value;
            if (!studentId) {
                alert('학생을 먼저 선택해주세요.');
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-upload mr-2"></i>생기부 업로드';
                return;
            }
            formData.append('student_id', studentId);
        } else {
            formData.append('student_id', currentUser.user_id || '');
        }

        try {
            const res = await fetch(`${API_BASE}/api/admission/record/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                alert('생기부가 성공적으로 업로드되었습니다.');
                clearRecordFile();
                loadRecordHistory(document.getElementById('mydata-student')?.value || null);
            } else {
                alert(data.message || '업로드에 실패했습니다.');
            }
        } catch (err) {
            console.error('업로드 오류:', err);
            alert('서버 연결 오류가 발생했습니다.');
        }

        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-upload mr-2"></i>생기부 업로드';
    }

    // ─── 모의고사 성적 ───

    // 교육과정별 주관기관·월 매핑
    const MOCK_MONTHS = {
        '2015': { local: [3, 5, 7, 10], kice: [6, 9] },
        '2022': { local: [3, 6, 9, 10] }
    };

    function selectMockOrg(org) {
        selectedMockOrg = org;
        selectedMockExamType = null;
        ['local', 'kice', 'private'].forEach(o => {
            document.getElementById(`mock-org-${o}`).classList.toggle('active', o === org);
        });
        const monthSel = document.getElementById('mock-month-selector');
        const privateSel = document.getElementById('mock-private-selector');
        if (org === 'private') {
            monthSel.style.display = 'none';
            privateSel.style.display = '';
        } else {
            monthSel.style.display = '';
            privateSel.style.display = 'none';
            renderMockMonthBtns();
        }
    }

    function renderMockMonthBtns() {
        if (!selectedMockOrg || selectedMockOrg === 'private') return;
        const cur = currentCurriculum || '2015';
        const months = (MOCK_MONTHS[cur] || {})[selectedMockOrg] || [];
        const prefix = selectedMockOrg === 'kice' ? 'kice' : 'local';
        const container = document.getElementById('mock-month-btns');
        container.innerHTML = months.map(m =>
            `<button onclick="selectMockExamType('${prefix}_${m}')" id="mock-et-${prefix}_${m}" class="type-toggle px-5 py-2.5 bg-white border-2 border-slate-200 rounded-lg text-sm font-bold text-slate-400">${m}월</button>`
        ).join('');
        selectedMockExamType = null;
    }

    function selectMockExamType(type) {
        selectedMockExamType = type;
        document.querySelectorAll('#mock-month-btns .type-toggle').forEach(btn => btn.classList.remove('active'));
        const btn = document.getElementById(`mock-et-${type}`);
        if (btn) btn.classList.add('active');
    }

    function selectMockTrack(track) {
        selectedMockTrack = track;
        document.getElementById('mock-mun').classList.toggle('active', track === '문과');
        document.getElementById('mock-li').classList.toggle('active', track === '이과');
    }

    function clearMockForm() {
        selectedMockOrg = null;
        selectedMockExamType = null;
        selectedMockTrack = null;
        ['local', 'kice', 'private'].forEach(o => document.getElementById(`mock-org-${o}`).classList.remove('active'));
        document.getElementById('mock-month-selector').style.display = 'none';
        document.getElementById('mock-private-selector').style.display = 'none';
        document.getElementById('mock-month-btns').innerHTML = '';
        document.getElementById('mock-private-name').value = '';
        document.getElementById('mock-private-month').value = '';
        document.getElementById('mock-mun').classList.remove('active');
        document.getElementById('mock-li').classList.remove('active');
        document.querySelectorAll('#mock-form-2015 .score-table input[type="number"]').forEach(inp => inp.value = '');
        document.querySelectorAll('#mock-form-2015 .score-table select').forEach(sel => sel.selectedIndex = 0);
    }

    async function saveMockScore() {
        let examType = selectedMockExamType;
        let examName = null;
        if (selectedMockOrg === 'private') {
            const name = document.getElementById('mock-private-name').value.trim();
            const month = document.getElementById('mock-private-month').value;
            if (!name) { alert('시험명을 입력해주세요.'); return; }
            if (!month) { alert('시험 월을 선택해주세요.'); return; }
            examType = 'private';
            examName = `${name} (${month}월)`;
        } else {
            if (!selectedMockOrg) { alert('주관기관을 선택해주세요.'); return; }
            if (!examType) { alert('시험 월을 선택해주세요.'); return; }
        }
        if (!selectedMockTrack) { alert('계열을 선택해주세요.'); return; }

        const role = currentUser.member_roll || 'student';
        let studentId = currentUser.user_id;
        if (role === 'teacher') {
            studentId = document.getElementById('mydata-student').value;
            if (!studentId) { alert('학생을 먼저 선택해주세요.'); return; }
        }

        const payload = {
            curriculum: '2015',
            school_id: currentUser.school_id || '',
            student_id: studentId,
            exam_year: document.getElementById('mock-year').value,
            exam_type: examType,
            exam_name: examName,
            track: selectedMockTrack,
            korean: {
                choice: document.getElementById('mock-kor-choice').value,
                raw: document.getElementById('mock-kor-raw').value || null,
                standard: document.getElementById('mock-kor-std').value || null,
                percentile: document.getElementById('mock-kor-pct').value || null,
                grade: document.getElementById('mock-kor-grade').value || null
            },
            math: {
                choice: document.getElementById('mock-math-choice').value,
                raw: document.getElementById('mock-math-raw').value || null,
                standard: document.getElementById('mock-math-std').value || null,
                percentile: document.getElementById('mock-math-pct').value || null,
                grade: document.getElementById('mock-math-grade').value || null
            },
            english: {
                raw: document.getElementById('mock-eng-raw').value || null,
                grade: document.getElementById('mock-eng-grade').value || null
            },
            history: {
                raw: document.getElementById('mock-hist-raw').value || null,
                grade: document.getElementById('mock-hist-grade').value || null
            },
            tamgu1: {
                choice: document.getElementById('mock-tam1-choice').value,
                raw: document.getElementById('mock-tam1-raw').value || null,
                standard: document.getElementById('mock-tam1-std').value || null,
                percentile: document.getElementById('mock-tam1-pct').value || null,
                grade: document.getElementById('mock-tam1-grade').value || null
            },
            tamgu2: {
                choice: document.getElementById('mock-tam2-choice').value,
                raw: document.getElementById('mock-tam2-raw').value || null,
                standard: document.getElementById('mock-tam2-std').value || null,
                percentile: document.getElementById('mock-tam2-pct').value || null,
                grade: document.getElementById('mock-tam2-grade').value || null
            },
            lang2: {
                choice: document.getElementById('mock-lang2-choice').value,
                raw: document.getElementById('mock-lang2-raw').value || null,
                standard: document.getElementById('mock-lang2-std').value || null,
                percentile: document.getElementById('mock-lang2-pct').value || null,
                grade: document.getElementById('mock-lang2-grade').value || null
            }
        };

        const data = await apiCall('/api/admission/mock/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (data && data.success) {
            alert('모의고사 성적이 저장되었습니다.');
            refreshHistory(document.getElementById('mydata-student')?.value || null);
        } else {
            alert((data && data.message) || '저장에 실패했습니다.');
        }
    }

    // ─── 2022 교육과정 모의고사 ───
    function clearMockForm22() {
        selectedMockOrg = null;
        selectedMockExamType = null;
        ['local', 'kice', 'private'].forEach(o => document.getElementById(`mock-org-${o}`).classList.remove('active'));
        document.getElementById('mock-month-selector').style.display = 'none';
        document.getElementById('mock-private-selector').style.display = 'none';
        document.getElementById('mock-month-btns').innerHTML = '';
        document.getElementById('mock-private-name').value = '';
        document.getElementById('mock-private-month').value = '';
        document.querySelectorAll('#mock-form-2022 input[type="number"]').forEach(inp => inp.value = '');
        document.querySelectorAll('#mock-form-2022 select').forEach(sel => sel.selectedIndex = 0);
    }

    async function saveMockScore22() {
        let examType = selectedMockExamType;
        let examName = null;
        if (selectedMockOrg === 'private') {
            const name = document.getElementById('mock-private-name').value.trim();
            const month = document.getElementById('mock-private-month').value;
            if (!name) { alert('시험명을 입력해주세요.'); return; }
            if (!month) { alert('시험 월을 선택해주세요.'); return; }
            examType = 'private';
            examName = `${name} (${month}월)`;
        } else {
            if (!selectedMockOrg) { alert('주관기관을 선택해주세요.'); return; }
            if (!examType) { alert('시험 월을 선택해주세요.'); return; }
        }

        const role = currentUser.member_roll || 'student';
        let studentId = currentUser.user_id;
        if (role === 'teacher') {
            studentId = document.getElementById('mydata-student').value;
            if (!studentId) { alert('학생을 먼저 선택해주세요.'); return; }
        }

        const payload = {
            curriculum: '2022',
            school_id: currentUser.school_id || '',
            student_id: studentId,
            exam_year: document.getElementById('mock-year').value,
            exam_type: examType,
            exam_name: examName,
            track: null,
            korean: {
                choice: null,
                raw: document.getElementById('mock22-kor-raw').value || null,
                standard: document.getElementById('mock22-kor-std').value || null,
                percentile: document.getElementById('mock22-kor-pct').value || null,
                grade: document.getElementById('mock22-kor-grade').value || null
            },
            math: {
                choice: null,
                raw: document.getElementById('mock22-math-raw').value || null,
                standard: document.getElementById('mock22-math-std').value || null,
                percentile: document.getElementById('mock22-math-pct').value || null,
                grade: document.getElementById('mock22-math-grade').value || null
            },
            english: {
                raw: document.getElementById('mock22-eng-raw').value || null,
                grade: document.getElementById('mock22-eng-grade').value || null
            },
            history: {
                raw: document.getElementById('mock22-hist-raw').value || null,
                grade: document.getElementById('mock22-hist-grade').value || null
            },
            tamgu1: {
                choice: '통합사회',
                raw: document.getElementById('mock22-tam1-raw').value || null,
                standard: document.getElementById('mock22-tam1-std').value || null,
                percentile: document.getElementById('mock22-tam1-pct').value || null,
                grade: document.getElementById('mock22-tam1-grade').value || null
            },
            tamgu2: {
                choice: '통합과학',
                raw: document.getElementById('mock22-tam2-raw').value || null,
                standard: document.getElementById('mock22-tam2-std').value || null,
                percentile: document.getElementById('mock22-tam2-pct').value || null,
                grade: document.getElementById('mock22-tam2-grade').value || null
            },
            lang2: {
                choice: document.getElementById('mock22-lang2-choice').value,
                raw: document.getElementById('mock22-lang2-raw').value || null,
                standard: document.getElementById('mock22-lang2-std').value || null,
                percentile: document.getElementById('mock22-lang2-pct').value || null,
                grade: document.getElementById('mock22-lang2-grade').value || null
            }
        };

        const data = await apiCall('/api/admission/mock/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (data && data.success) {
            alert('모의고사 성적이 저장되었습니다.');
        } else {
            alert((data && data.message) || '저장에 실패했습니다.');
        }
    }

    // ─── 수능점수 ───
    function selectCsatTrack(track) {
        selectedCsatTrack = track;
        document.getElementById('csat-mun').classList.toggle('active', track === '문과');
        document.getElementById('csat-li').classList.toggle('active', track === '이과');
    }

    function clearCsatForm() {
        selectedCsatTrack = null;
        document.getElementById('csat-mun').classList.remove('active');
        document.getElementById('csat-li').classList.remove('active');

        const inputs = document.querySelectorAll('#subcontent-csat .score-table input[type="number"]');
        inputs.forEach(inp => inp.value = '');
        const selects = document.querySelectorAll('#subcontent-csat .score-table select');
        selects.forEach(sel => sel.selectedIndex = 0);
    }

    async function saveCsatScore() {
        if (!selectedCsatTrack) { alert('계열을 선택해주세요.'); return; }

        const role = currentUser.member_roll || 'student';
        let studentId = currentUser.user_id;
        if (role === 'teacher') {
            studentId = document.getElementById('mydata-student').value;
            if (!studentId) { alert('학생을 먼저 선택해주세요.'); return; }
        }

        const payload = {
            curriculum: '2015',
            school_id: currentUser.school_id || '',
            student_id: studentId,
            exam_year: document.getElementById('csat-year').value,
            track: selectedCsatTrack,
            korean: {
                choice: document.getElementById('csat-kor-choice').value,
                standard: document.getElementById('csat-kor-std').value || null,
                percentile: document.getElementById('csat-kor-pct').value || null,
                grade: document.getElementById('csat-kor-grade').value || null
            },
            math: {
                choice: document.getElementById('csat-math-choice').value,
                standard: document.getElementById('csat-math-std').value || null,
                percentile: document.getElementById('csat-math-pct').value || null,
                grade: document.getElementById('csat-math-grade').value || null
            },
            english: {
                grade: document.getElementById('csat-eng-grade').value || null
            },
            history: {
                grade: document.getElementById('csat-hist-grade').value || null
            },
            tamgu1: {
                choice: document.getElementById('csat-tam1-choice').value,
                standard: document.getElementById('csat-tam1-std').value || null,
                percentile: document.getElementById('csat-tam1-pct').value || null,
                grade: document.getElementById('csat-tam1-grade').value || null
            },
            tamgu2: {
                choice: document.getElementById('csat-tam2-choice').value,
                standard: document.getElementById('csat-tam2-std').value || null,
                percentile: document.getElementById('csat-tam2-pct').value || null,
                grade: document.getElementById('csat-tam2-grade').value || null
            },
            lang2: {
                choice: document.getElementById('csat-lang2-choice').value,
                standard: document.getElementById('csat-lang2-std').value || null,
                percentile: document.getElementById('csat-lang2-pct').value || null,
                grade: document.getElementById('csat-lang2-grade').value || null
            }
        };

        const data = await apiCall('/api/admission/csat/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (data && data.success) {
            alert('수능 성적이 저장되었습니다.');
            refreshHistory(document.getElementById('mydata-student')?.value || null);
        } else {
            alert((data && data.message) || '저장에 실패했습니다.');
        }
    }

    // ─── 2022 교육과정 수능 ───
    function clearCsatForm22() {
        document.querySelectorAll('#csat-form-2022 input[type="number"]').forEach(inp => inp.value = '');
        document.querySelectorAll('#csat-form-2022 select').forEach(sel => sel.selectedIndex = 0);
    }

    async function saveCsatScore22() {
        const role = currentUser.member_roll || 'student';
        let studentId = currentUser.user_id;
        if (role === 'teacher') {
            studentId = document.getElementById('mydata-student').value;
            if (!studentId) { alert('학생을 먼저 선택해주세요.'); return; }
        }

        const payload = {
            curriculum: '2022',
            school_id: currentUser.school_id || '',
            student_id: studentId,
            exam_year: document.getElementById('csat-year').value,
            track: null,
            korean: {
                choice: null,
                standard: document.getElementById('csat22-kor-std').value || null,
                percentile: document.getElementById('csat22-kor-pct').value || null,
                grade: document.getElementById('csat22-kor-grade').value || null
            },
            math: {
                choice: null,
                standard: document.getElementById('csat22-math-std').value || null,
                percentile: document.getElementById('csat22-math-pct').value || null,
                grade: document.getElementById('csat22-math-grade').value || null
            },
            english: {
                grade: document.getElementById('csat22-eng-grade').value || null
            },
            history: {
                grade: document.getElementById('csat22-hist-grade').value || null
            },
            tamgu1: {
                choice: '통합사회',
                standard: document.getElementById('csat22-tam1-std').value || null,
                percentile: document.getElementById('csat22-tam1-pct').value || null,
                grade: document.getElementById('csat22-tam1-grade').value || null
            },
            tamgu2: {
                choice: '통합과학',
                standard: document.getElementById('csat22-tam2-std').value || null,
                percentile: document.getElementById('csat22-tam2-pct').value || null,
                grade: document.getElementById('csat22-tam2-grade').value || null
            },
            lang2: {
                choice: document.getElementById('csat22-lang2-choice').value,
                standard: document.getElementById('csat22-lang2-std').value || null,
                percentile: document.getElementById('csat22-lang2-pct').value || null,
                grade: document.getElementById('csat22-lang2-grade').value || null
            }
        };

        const data = await apiCall('/api/admission/csat/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (data && data.success) {
            alert('수능 성적이 저장되었습니다.');
        } else {
            alert((data && data.message) || '저장에 실패했습니다.');
        }
    }

    // ═══════════════════════════════════════════
    // 유틸리티
    // ═══════════════════════════════════════════
    function resetSelect(id, placeholder) {
        const sel = document.getElementById(id);
        sel.innerHTML = `<option value="">${placeholder}</option>`;
        sel.disabled = true;
    }

    function resetTypeButtons() {
        selectedType = null;
        ['btn-susi', 'btn-jeongsi'].forEach(id => {
            const btn = document.getElementById(id);
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
            btn.classList.remove('active');
        });
    }

    function hideResult() {
        document.getElementById('result-area').classList.add('hidden');
        document.getElementById('empty-state').classList.remove('hidden');
        document.getElementById('summary-area').classList.add('hidden');
        document.getElementById('pdf-viewer').src = 'about:blank';
        currentPdfUrl = null;
    }

    function setStatus(text, loading = false) {
        document.getElementById('status-text').textContent = text;
        document.getElementById('loading-indicator').classList.toggle('hidden', !loading);
    }

    function toggleSummary() {
        const el = document.getElementById('summary-content');
        const icon = document.getElementById('summary-toggle-icon');
        const hidden = el.style.display === 'none';
        el.style.display = hidden ? 'block' : 'none';
        icon.style.transform = hidden ? 'rotate(0deg)' : 'rotate(-90deg)';
    }

    function openPdfNewTab() { if (currentPdfUrl) window.open(currentPdfUrl, '_blank'); }
    function downloadPdf() {
        if (!currentPdfUrl) return;
        const a = document.createElement('a');
        a.href = currentPdfUrl;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // ═══════════════════════════════════════════
    // 공통 (탭, 사이드바, 로그아웃)
    // ═══════════════════════════════════════════
    function switchTab(name) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById('tab-' + name).classList.add('active');
        document.getElementById('content-' + name).classList.add('active');
        if (name === 'department') initDeptTab();
    }

    function renderSidebarMenu(menus) {
        const container = document.getElementById('sidebar-menu');
        let html = '<ul class="space-y-1 px-3 mb-4">';
        const dash = menus.find(m => m.label === '대시보드');
        if (dash) {
            html += `<li><a href="${dash.href}" class="nav-item flex items-center px-4 py-3 rounded-xl hover:text-white font-medium"><i class="${dash.icon} w-6 mr-3 ${dash.color}"></i>${dash.label}</a></li>`;
        }
        html += '</ul><ul class="space-y-1 px-3">';
        menus.filter(m => m.label !== '대시보드').forEach(m => {
            const cls = m.active ? 'active text-white' : 'hover:text-white';
            html += `<li><a href="${m.href}" class="nav-item ${cls} flex items-center px-4 py-3 rounded-xl font-medium"><i class="${m.icon} w-6 mr-3 ${m.color}"></i>${m.label}</a></li>`;
        });
        html += '</ul>';
        container.innerHTML = html;
    }

    function handleLogout() {
        if (confirm('로그아웃 하시겠습니까?')) {
            localStorage.removeItem('schoolus_user');
            window.location.href = '/';
        }
    }

    // ═══════════════════════════════════════════════════════
