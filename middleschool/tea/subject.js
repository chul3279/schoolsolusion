// subject.js - 교과 및 동아리 관리 JS

let userInfo = {};
let clubStudentsList = [];
let currentPoint = 0;
let swSelectedStudent = null;
let cwSelectedStudent = null;
let _allSubjectOptions = [];

document.addEventListener('DOMContentLoaded', () => {
    const userStr = localStorage.getItem('schoolus_user');
    if (userStr) {
        userInfo = JSON.parse(userStr);
        document.getElementById('teacher-name').textContent = (userInfo.member_name || '사용자') + ' 선생님';
        document.getElementById('teacher-avatar').textContent = (userInfo.member_name || 'T').charAt(0);
        document.getElementById('teacher-info').textContent = userInfo.member_school || '-';
    }
    initYearSelects();
    initClassSelects();
    loadClubSelects();
    loadUserPoint();
    loadSubjectOptions().then(() => loadAssignments());
});

// ===== 포인트 =====
async function loadUserPoint() {
    if (!userInfo.member_id) return;
    try {
        const res = await fetch(`/api/teacher/info?member_id=${userInfo.member_id}&school_id=${userInfo.school_id}`);
        const data = await res.json();
        if (data.success && data.teacher) displayPoint(data.teacher.point);
    } catch (e) { console.error('포인트 로드 오류:', e); }
}

function displayPoint(point) {
    const el = document.getElementById('userPoint');
    if (!el) return;
    if (point === 'free' || point === 'Free') { el.textContent = 'Free'; currentPoint = 'free'; }
    else if (point === null || point === undefined || point === '') { el.textContent = '0'; currentPoint = 0; }
    else { const num = parseInt(point); currentPoint = isNaN(num) ? 0 : num; el.textContent = currentPoint.toLocaleString(); }
}

// ===== 과목 목록 로드 =====
async function loadSubjectOptions() {
    if (!userInfo.school_id) return;
    try {
        const res = await fetch(`/api/subject/options?school_id=${userInfo.school_id}`);
        const data = await res.json();
        if (data.success && data.subjects.length > 0) {
            ['hw-subject', 'sb-subject', 'sw-subject'].forEach(id => {
                const sel = document.getElementById(id);
                if (!sel) return;
                const val = sel.value;
                sel.innerHTML = '<option value="">과목 선택</option>';
                data.subjects.forEach(name => { const opt = document.createElement('option'); opt.value = name; opt.textContent = name; sel.appendChild(opt); });
                if (val) sel.value = val;
            });
            _allSubjectOptions = data.subjects.map(name => ({ value: name, text: name }));
        }
    } catch (e) { console.error('과목 목록 로드 오류:', e); }
}

function initYearSelects() {
    ['hw-year', 'sb-year', 'sw-year', 'cb-year', 'cw-year'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const opt = document.createElement('option'); opt.value = 2026; opt.textContent = '2026년'; opt.selected = true; sel.appendChild(opt);
    });
}

function initClassSelects() {
    // sw-class, sb-class: 기존 단일 select
    ['sw-class', 'sb-class'].forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        for (let i = 1; i <= 15; i++) { const opt = document.createElement('option'); opt.value = i; opt.textContent = i + '반'; sel.appendChild(opt); }
    });
    // hw-class: 체크박스 멀티 선택
    const optWrap = document.getElementById('hw-class-options');
    if (optWrap) {
        let html = '';
        for (let i = 1; i <= 15; i++) {
            html += '<label class="flex items-center px-4 py-2 hover:bg-blue-50 cursor-pointer text-sm">' +
                '<input type="checkbox" value="' + i + '" name="hw-class-cb" class="mr-2 w-4 h-4 accent-blue-500"> ' + i + '반</label>';
        }
        optWrap.innerHTML = html;
    }
    // hw-class 이벤트 바인딩 (인라인 onclick 대신 addEventListener 사용)
    var hwBtn = document.getElementById('hw-class-btn');
    var hwDD = document.getElementById('hw-class-dropdown');
    var hwDoneBtn = document.getElementById('hw-class-done-btn');
    if (hwBtn && hwDD) {
        // 버튼 클릭: 열기만 (닫기는 외부클릭 또는 선택완료 버튼으로만)
        hwBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (hwDD.classList.contains('hidden')) {
                hwDD.classList.remove('hidden');
                var arrow = document.getElementById('hw-class-arrow');
                if (arrow) arrow.style.transform = 'rotate(180deg)';
            }
        });
        // 드롭다운 내부 클릭: 이벤트 전파 완전 차단
        hwDD.addEventListener('click', function(e) { e.stopPropagation(); });
        hwDD.addEventListener('touchstart', function(e) { e.stopPropagation(); }, {passive: true});
        hwDD.addEventListener('touchend', function(e) { e.stopPropagation(); }, {passive: true});
        // 체크박스 변경 감지
        hwDD.addEventListener('change', function(e) {
            var target = e.target;
            if (target.id === 'hw-class-all') { toggleHwClassAll(); }
            else if (target.name === 'hw-class-cb') { onHwClassChange(); }
        });
        // 선택 완료 버튼
        if (hwDoneBtn) {
            hwDoneBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                hwDD.classList.add('hidden');
                var arrow = document.getElementById('hw-class-arrow');
                if (arrow) arrow.style.transform = '';
            });
        }
        // 외부 클릭 시 닫기
        document.addEventListener('click', function(e) {
            if (!hwDD.classList.contains('hidden') && !hwDD.contains(e.target) && !hwBtn.contains(e.target)) {
                hwDD.classList.add('hidden');
                var arrow = document.getElementById('hw-class-arrow');
                if (arrow) arrow.style.transform = '';
            }
        });
    }
}

// ===== 과제출제 반 멀티셀렉트 =====
function toggleHwClassAll() {
    const allChecked = document.getElementById('hw-class-all').checked;
    document.querySelectorAll('input[name="hw-class-cb"]').forEach(cb => cb.checked = allChecked);
    updateHwClassText();
}
function onHwClassChange() {
    const cbs = document.querySelectorAll('input[name="hw-class-cb"]');
    const allCb = document.getElementById('hw-class-all');
    allCb.checked = [...cbs].every(cb => cb.checked);
    updateHwClassText();
}
function updateHwClassText() {
    const selected = getSelectedHwClasses();
    const textEl = document.getElementById('hw-class-text');
    if (selected.length === 0) { textEl.textContent = '반 선택'; textEl.className = 'text-slate-500'; }
    else if (selected.length >= 15) { textEl.textContent = '전체 반'; textEl.className = 'text-blue-600 font-bold'; }
    else { textEl.textContent = selected.map(v => v + '반').join(', '); textEl.className = 'text-slate-800 font-medium'; }
}
function getSelectedHwClasses() {
    return [...document.querySelectorAll('input[name="hw-class-cb"]:checked')].map(cb => cb.value);
}
// ===== 탭 전환 =====
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => { btn.classList.remove('active'); btn.classList.add('bg-white', 'border-2', 'border-slate-200'); });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.remove('bg-white', 'border-2', 'border-slate-200');
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
    document.getElementById(`panel-${tabName}`).classList.add('active');
}

function calcNeisBytes(str) { if (!str) return 0; let bytes = 0; for (let i = 0; i < str.length; i++) bytes += str.charCodeAt(i) > 127 ? 3 : 1; return bytes; }
function updateSubjectWriteBytes() { document.getElementById('sw-byte-count').textContent = calcNeisBytes(document.getElementById('sw-content').value); }
function updateClubWriteBytes() { document.getElementById('cw-byte-count').textContent = calcNeisBytes(document.getElementById('cw-content').value); }

// ===== 과목 검색 필터 (공통) =====
function filterSubjectSearch(inputId, dropdownId, query) {
    if (!_allSubjectOptions.length) return;
    const dropdown = document.getElementById(dropdownId);
    const q = (query || '').trim();
    let filtered;
    if (!q) {
        // 빈 쿼리: 전체 과목 표시
        filtered = _allSubjectOptions;
    } else {
        filtered = _allSubjectOptions.filter(o => o.text.includes(q));
    }
    if (filtered.length === 0) {
        dropdown.innerHTML = '<div class="px-4 py-3 text-sm text-slate-400">일치하는 과목이 없습니다.</div>';
    } else {
        dropdown.innerHTML = filtered.map(o => {
            const display = q ? o.text.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), '<span class="text-blue-600 font-black">' + q + '</span>') : o.text;
            return `<div class="px-4 py-2.5 text-sm hover:bg-blue-50 cursor-pointer transition font-medium" onclick="selectSubjectFilter('${inputId}','${dropdownId}','${o.value}','${o.text}')">${display}</div>`;
        }).join('');
    }
    dropdown.classList.remove('hidden');
}

function showSubjectDropdown(inputId, dropdownId) {
    if (!_allSubjectOptions.length) return;
    const q = document.getElementById(inputId).value.trim();
    // 항상 드롭다운 표시 (빈 쿼리면 전체 목록)
    filterSubjectSearch(inputId, dropdownId, q);
}

function selectSubjectFilter(inputId, dropdownId, value, text) {
    const input = document.getElementById(inputId);
    input.value = text;
    input.dataset.selectedValue = value;
    document.getElementById(dropdownId).classList.add('hidden');
    // hidden select에 값 설정 + 콜백 트리거
    if (inputId === 'hw-subject-search') { document.getElementById('hw-subject').value = value; }
    else if (inputId === 'sb-subject-search') { document.getElementById('sb-subject').value = value; onSubjectBaseFilterChange(); }
    else if (inputId === 'sw-subject-search') { document.getElementById('sw-subject').value = value; onSubjectWriteFilterChange(); }
}

// 외부 클릭 시 드롭다운 닫기 + 자동 매칭
document.addEventListener('click', function(e) {
    ['hw-subject-dropdown', 'sb-subject-dropdown', 'sw-subject-dropdown'].forEach(id => {
        const dropdown = document.getElementById(id);
        if (!dropdown) return;
        const inputId = id.replace('-dropdown', '-search');
        const input = document.getElementById(inputId);
        if (input && dropdown && !input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.add('hidden');
            autoMatchSubject(inputId);
        }
    });
});

function autoMatchSubject(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const val = input.value.trim();
    if (!val || !_allSubjectOptions.length) return;
    const selectId = inputId.replace('-search', '');
    const sel = document.getElementById(selectId);
    // 1) 정확히 일치
    let match = _allSubjectOptions.find(o => o.text === val);
    // 2) 입력값으로 시작하는 과목 (예: "통합과학" → "통합과학1")
    if (!match) match = _allSubjectOptions.find(o => o.text.startsWith(val));
    // 3) 입력값을 포함하는 과목이 1개뿐이면 자동 선택
    if (!match) {
        const candidates = _allSubjectOptions.filter(o => o.text.includes(val));
        if (candidates.length === 1) match = candidates[0];
    }
    if (!match) return;
    input.value = match.text;
    if (sel && sel.value !== match.value) {
        sel.value = match.value;
        if (selectId === 'sb-subject') { if (typeof onSubjectBaseFilterChange === 'function') onSubjectBaseFilterChange(); }
        else if (selectId === 'sw-subject') { if (typeof onSubjectWriteFilterChange === 'function') onSubjectWriteFilterChange(); }
    }
}

// ===== 동아리 목록 로드 =====
async function loadClubSelects() {
    if (!userInfo.school_id) return;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    try {
        const res = await fetch(`/api/club/list?school_id=${userInfo.school_id}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success) {
            ['cb-club', 'cw-club'].forEach(id => {
                const sel = document.getElementById(id);
                if (!sel) return;
                const val = sel.value;
                sel.innerHTML = '<option value="">동아리 선택</option>';
                data.clubs.forEach(c => { const opt = document.createElement('option'); opt.value = c.club_name; opt.textContent = `${c.club_name} (${c.student_count}명)`; sel.appendChild(opt); });
                if (val) sel.value = val;
            });
        }
    } catch (e) { console.error('동아리 목록 로드 오류:', e); }
}

// ===== 동아리 등록 모달 =====
function openClubCreateModal() { document.getElementById('cc-create-name').value = ''; document.getElementById('cc-create-desc').value = ''; document.getElementById('club-create-modal').classList.remove('hidden'); }
function closeClubCreateModal() { document.getElementById('club-create-modal').classList.add('hidden'); }

async function submitClubCreate() {
    const clubName = document.getElementById('cc-create-name').value.trim();
    const desc = document.getElementById('cc-create-desc').value.trim();
    if (!clubName) return alert('동아리 이름을 입력해주세요.');
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    try {
        const res = await fetch('/api/club/create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school, club_name: clubName, teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, description: desc, record_year: String(year), record_semester: String(semester) }) });
        const data = await res.json();
        alert(data.message); if (data.success) { closeClubCreateModal(); loadClubSelects(); }
    } catch (e) { alert('등록 중 오류가 발생했습니다.'); }
}

// ===== 동아리 기초작업 =====
async function onClubBaseFilterChange() {
    const clubName = document.getElementById('cb-club')?.value;
    const studentArea = document.getElementById('cb-student-area');
    if (!clubName) {
        if (studentArea) studentArea.classList.add('hidden');
        return;
    }
    if (studentArea) studentArea.classList.remove('hidden');
    await loadClubStudentList();
    await loadClubCommonList();
}

async function loadClubStudentList() {
    const clubName = document.getElementById('cb-club')?.value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    if (!clubName) return;
    try {
        const res = await fetch(`/api/club/students?school_id=${userInfo.school_id}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        clubStudentsList = data.success ? data.students : [];
        const listEl = document.getElementById('cb-student-list');
        const selectEl = document.getElementById('cb-student');
        if (clubStudentsList.length > 0) {
            listEl.innerHTML = clubStudentsList.map(s => `<div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl cursor-pointer hover:bg-teal-50 border border-transparent transition" onclick="loadClubStudentBase('${s.student_id}','${s.student_name}','${s.class_grade}','${s.class_no}','${s.class_num}',this)"><div class="w-8 h-8 bg-gradient-to-br from-teal-400 to-emerald-500 rounded-full flex items-center justify-center text-white font-bold text-xs">${(s.student_name||'?').charAt(0)}</div><div class="flex-1"><p class="font-bold text-sm">${s.student_name}</p><p class="text-xs text-slate-500">${s.class_grade}학년 ${s.class_no}반 ${s.class_num}번</p></div></div>`).join('');
            if (selectEl) {
                selectEl.innerHTML = '<option value="">학생을 선택하세요</option>' + clubStudentsList.map(s => `<option value="${s.student_id}" data-name="${s.student_name}" data-grade="${s.class_grade}" data-class="${s.class_no}" data-num="${s.class_num}">${s.student_name} (${s.class_grade}-${s.class_no}-${s.class_num}번)</option>`).join('');
            }
        } else {
            listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">등록된 학생이 없습니다.</div>';
            if (selectEl) selectEl.innerHTML = '<option value="">학생을 선택하세요</option>';
        }
    } catch (e) {}
}

function openClubStudentAddModal() { document.getElementById('cs-add-grade').value = ''; document.getElementById('cs-add-class').value = ''; document.getElementById('cs-search-result').innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">학년/반을 선택하면 학생 목록이 표시됩니다.</div>'; document.getElementById('club-student-add-modal').classList.remove('hidden'); }
function closeClubStudentAddModal() { document.getElementById('club-student-add-modal').classList.add('hidden'); }

async function searchClubStudents() {
    const grade = document.getElementById('cs-add-grade').value;
    const classNo = document.getElementById('cs-add-class').value;
    if (!grade || !classNo) return;
    try {
        const res = await fetch(`/api/subject/students?school_id=${userInfo.school_id}&class_grade=${grade}&class_no=${classNo}`);
        const data = await res.json();
        const resultEl = document.getElementById('cs-search-result');
        if (data.success && data.students.length > 0) {
            resultEl.innerHTML = data.students.map(s => `<div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg"><span class="text-sm font-medium">${s.member_name} (${s.class_num}번)</span><button onclick="addStudentToClub('${s.member_id}','${s.member_name}','${s.class_grade}','${s.class_no}','${s.class_num}',this)" class="px-3 py-1 bg-teal-500 text-white text-xs rounded-lg hover:bg-teal-600">추가</button></div>`).join('');
        } else { resultEl.innerHTML = '<div class="text-center py-4 text-slate-400 text-sm">학생이 없습니다.</div>'; }
    } catch (e) {}
}

async function addStudentToClub(studentId, studentName, grade, classNo, classNum, btnEl) {
    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    try {
        const res = await fetch('/api/club/student/add', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school, teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, club_name: clubName, student_id: studentId, student_name: studentName, class_grade: grade, class_no: classNo, class_num: classNum, record_year: String(year), record_semester: String(semester) }) });
        const data = await res.json();
        if (data.success) { btnEl.textContent = '완료'; btnEl.disabled = true; btnEl.className = 'px-3 py-1 bg-slate-300 text-white text-xs rounded-lg'; loadClubStudentList(); loadClubSelects(); }
        else alert(data.message);
    } catch (e) { alert('추가 중 오류 발생'); }
}

async function loadClubStudentBase(studentId, studentName, grade, classNo, classNum, el) {
    // select에서 호출 시 (파라미터 없음)
    if (!studentId) {
        const selectEl = document.getElementById('cb-student');
        if (!selectEl || !selectEl.value) return;
        const opt = selectEl.options[selectEl.selectedIndex];
        studentId = selectEl.value;
        studentName = opt.dataset.name;
        grade = opt.dataset.grade;
        classNo = opt.dataset.class;
        classNum = opt.dataset.num;
    }
    // 카드 클릭 시 하이라이트
    if (el) { document.querySelectorAll('#cb-student-list > div').forEach(d => { d.classList.remove('bg-teal-50', 'border-teal-300'); d.classList.add('bg-slate-50', 'border-transparent'); }); el.classList.remove('bg-slate-50', 'border-transparent'); el.classList.add('bg-teal-50', 'border-teal-300'); }
    // select도 동기화
    const selectEl2 = document.getElementById('cb-student');
    if (selectEl2) selectEl2.value = studentId;

    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    document.getElementById('cb-form').classList.remove('hidden'); document.getElementById('cb-placeholder').classList.add('hidden');
    document.getElementById('cb-content').value = '';
    document.getElementById('cb-form').dataset.studentId = studentId; document.getElementById('cb-form').dataset.studentName = studentName; document.getElementById('cb-form').dataset.grade = grade; document.getElementById('cb-form').dataset.classNo = classNo; document.getElementById('cb-form').dataset.classNum = classNum;
    try {
        const res = await fetch(`/api/club/record/get?school_id=${userInfo.school_id}&student_id=${studentId}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.record && data.record.base_data) document.getElementById('cb-content').value = data.record.base_data;
    } catch (e) {}
    loadClubFileList(studentId);
}

async function saveClubBase() {
    const form = document.getElementById('cb-form');
    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    try {
        const res = await fetch('/api/club/base/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, student_id: form.dataset.studentId, student_name: form.dataset.studentName, club_name: clubName, class_grade: form.dataset.grade, class_no: form.dataset.classNo, class_num: form.dataset.classNum, record_year: year, record_semester: semester, base_data: document.getElementById('cb-content').value }) });
        const data = await res.json();
        alert(data.message);
    } catch (e) { alert('저장 중 오류 발생'); }
}

async function handleClubFiles(input) {
    const files = input.files;
    if (!files.length) return;
    const form = document.getElementById('cb-form');
    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    document.getElementById('cb-upload-progress').classList.remove('hidden');
    for (const file of files) {
        const fd = new FormData();
        fd.append('file', file); fd.append('school_id', userInfo.school_id); fd.append('member_school', userInfo.member_school || '');
        fd.append('teacher_id', userInfo.member_id); fd.append('teacher_name', userInfo.member_name || '');
        fd.append('student_id', form.dataset.studentId); fd.append('student_name', form.dataset.studentName || '');
        fd.append('club_name', clubName);
        fd.append('record_year', year); fd.append('record_semester', semester);
        try { await fetch('/api/club/file/upload', { method: 'POST', body: fd }); } catch (e) {}
    }
    document.getElementById('cb-upload-progress').classList.add('hidden');
    input.value = '';
    loadClubFileList(form.dataset.studentId);
}

async function loadClubFileList(studentId) {
    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    try {
        const res = await fetch(`/api/club/file/list?school_id=${userInfo.school_id}&student_id=${studentId}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        const listEl = document.getElementById('cb-file-list');
        if (data.success && data.files.length > 0) {
            listEl.innerHTML = data.files.map(f => `<div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg text-sm"><a href="/api/club/file/download/${f.id}" class="text-blue-600 hover:underline truncate flex-1">${f.file_name}</a><button onclick="deleteClubFile(${f.id},'${studentId}')" class="text-red-400 hover:text-red-600 ml-2"><i class="fas fa-trash-alt"></i></button></div>`).join('');
        } else { listEl.innerHTML = ''; }
    } catch (e) {}
}

async function deleteClubFile(fileId, studentId) {
    if (!confirm('파일을 삭제하시겠습니까?')) return;
    try { await fetch('/api/club/file/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: fileId }) }); loadClubFileList(studentId); } catch (e) {}
}

function openClubCommonModal() { document.getElementById('cc-modal-title').value = ''; document.getElementById('cc-modal-content').value = ''; document.getElementById('cc-modal-date').value = ''; document.getElementById('club-common-modal').classList.remove('hidden'); }
function closeClubCommonModal() { document.getElementById('club-common-modal').classList.add('hidden'); }

async function submitClubCommon() {
    const clubName = document.getElementById('cb-club').value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    const title = document.getElementById('cc-modal-title').value.trim();
    if (!title) return alert('제목을 입력해주세요.');
    try {
        const res = await fetch('/api/club/common/create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name || '', club_name: clubName, record_year: year, record_semester: semester, activity_type: document.getElementById('cc-modal-type').value, title: title, content: document.getElementById('cc-modal-content').value.trim(), activity_date: document.getElementById('cc-modal-date').value }) });
        const data = await res.json();
        alert(data.message); if (data.success) { closeClubCommonModal(); loadClubCommonList(); }
    } catch (e) { alert('등록 중 오류 발생'); }
}

async function loadClubCommonList() {
    const clubName = document.getElementById('cb-club')?.value;
    const year = document.getElementById('cb-year')?.value || '2026';
    const semester = document.getElementById('cb-semester')?.value || '1';
    if (!clubName) return;
    try {
        const res = await fetch(`/api/club/common/list?school_id=${userInfo.school_id}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        const listEl = document.getElementById('cb-common-list');
        if (data.success && data.activities.length > 0) {
            listEl.innerHTML = data.activities.map(a => `<div class="p-3 bg-slate-50 rounded-xl"><div class="flex justify-between items-start"><div><p class="font-bold text-sm">${a.title}</p><p class="text-xs text-slate-500 mt-1">${a.activity_date || ''} | ${a.activity_type}</p>${a.content ? `<p class="text-xs text-slate-600 mt-1">${a.content}</p>` : ''}</div><button onclick="deleteClubCommon(${a.id})" class="text-red-400 hover:text-red-600 text-xs"><i class="fas fa-trash-alt"></i></button></div></div>`).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400">등록된 공통사항이 없습니다.</div>'; }
    } catch (e) {}
}

async function deleteClubCommon(id) {
    if (!confirm('삭제하시겠습니까?')) return;
    try { const res = await fetch('/api/club/common/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }); const data = await res.json(); if (data.success) { loadClubCommonList(); } else { alert(data.message || '삭제 실패'); } } catch (e) { alert('삭제 중 오류 발생'); }
}

async function saveClubWrite(status) {
    if (!cwSelectedStudent) return alert('학생을 선택해주세요.');
    const clubName = document.getElementById('cw-club').value;
    const year = document.getElementById('cw-year')?.value || '2026';
    const semester = document.getElementById('cw-semester')?.value || '1';
    try {
        const res = await fetch('/api/club/write/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, student_id: cwSelectedStudent.member_id, student_name: cwSelectedStudent.member_name, club_name: clubName, class_grade: cwSelectedStudent.class_grade, class_no: cwSelectedStudent.class_no, class_num: cwSelectedStudent.class_num, record_year: year, record_semester: semester, content: document.getElementById('cw-content').value, status }) });
        const data = await res.json();
        alert(data.message); if (data.success) onClubWriteFilterChange();
    } catch (e) { alert('저장 중 오류 발생'); }
}

async function onClubWriteFilterChange() {
    const clubName = document.getElementById('cw-club')?.value;
    const year = document.getElementById('cw-year')?.value || '2026';
    const semester = document.getElementById('cw-semester')?.value || '1';
    const listEl = document.getElementById('cw-student-list');
    document.getElementById('cw-write-form').classList.add('hidden'); document.getElementById('cw-placeholder').classList.remove('hidden'); cwSelectedStudent = null;
    if (!clubName) { listEl.innerHTML = '<div class="text-center py-8 text-slate-400">동아리를 선택하세요.</div>'; return; }
    listEl.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin text-emerald-400"></i></div>';
    try {
        const res = await fetch(`/api/club/record/status-list?school_id=${userInfo.school_id}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.students.length > 0) {
            listEl.innerHTML = data.students.map(s => { const badge = s.status === 'complete' ? '<span class="w-2 h-2 bg-green-400 rounded-full"></span>' : s.status === 'draft' ? '<span class="w-2 h-2 bg-yellow-400 rounded-full"></span>' : '<span class="w-2 h-2 bg-slate-300 rounded-full"></span>';
                return `<div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl cursor-pointer hover:bg-emerald-50 hover:border-emerald-300 border border-transparent transition" onclick="selectClubWriteStudent('${s.member_id}','${s.member_name}','${s.class_grade}','${s.class_no}','${s.class_num}',this)">${badge}<div class="w-8 h-8 bg-gradient-to-br from-teal-400 to-emerald-500 rounded-full flex items-center justify-center text-white font-bold text-xs">${(s.member_name||'?').charAt(0)}</div><div class="flex-1 min-w-0"><p class="font-bold text-sm text-slate-800 truncate">${s.member_name}</p><p class="text-xs text-slate-500">${s.class_grade}학년 ${s.class_no}반 ${s.class_num}번</p></div></div>`; }).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">등록된 학생이 없습니다.</div>'; }
    } catch (e) { listEl.innerHTML = '<div class="text-center py-8 text-red-400 text-sm">조회 중 오류 발생</div>'; }
}

async function selectClubWriteStudent(studentId, studentName, grade, classNo, classNum, el) {
    document.querySelectorAll('#cw-student-list > div').forEach(d => { d.classList.remove('bg-emerald-50', 'border-emerald-300'); d.classList.add('bg-slate-50', 'border-transparent'); });
    el.classList.remove('bg-slate-50', 'border-transparent'); el.classList.add('bg-emerald-50', 'border-emerald-300');
    cwSelectedStudent = { member_id: studentId, member_name: studentName, class_grade: grade, class_no: classNo, class_num: classNum };
    document.getElementById('cw-student-avatar').textContent = (studentName||'?').charAt(0); document.getElementById('cw-student-name').textContent = studentName; document.getElementById('cw-student-info').textContent = `${grade}학년 ${classNo}반 ${classNum}번`;
    document.getElementById('cw-write-form').classList.remove('hidden'); document.getElementById('cw-placeholder').classList.add('hidden');
    document.getElementById('cw-content').value = ''; document.getElementById('cw-byte-count').textContent = '0';
    const clubName = document.getElementById('cw-club').value;
    const year = document.getElementById('cw-year').value; const semester = document.getElementById('cw-semester').value;
    let refHtml = '';
    // 1) 기초자료
    try {
        const res = await fetch(`/api/club/record/get?school_id=${userInfo.school_id}&student_id=${studentId}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.record) {
            if (data.record.content) { document.getElementById('cw-content').value = data.record.content; updateClubWriteBytes(); }
            if (data.record.base_data) refHtml += `<p class="mb-1"><strong>기초자료:</strong> ${data.record.base_data}</p>`;
        }
    } catch (e) {}
    // 2) 공통활동
    try {
        const cRes = await fetch(`/api/club/common/list?school_id=${userInfo.school_id}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const cData = await cRes.json();
        if (cData.success && cData.activities.length > 0) {
            refHtml += '<p class="mt-2 mb-1"><strong>공통활동:</strong></p>' + cData.activities.map(a => `<p class="text-xs text-slate-500 ml-2">• [${a.activity_date||''}] ${a.activity_type}: ${a.title}</p>`).join('');
        }
    } catch (e) {}
    // 3) 첨부파일 (버그수정: 파일 정보도 참고자료에 표시)
    try {
        const fRes = await fetch(`/api/club/file/list?school_id=${userInfo.school_id}&student_id=${studentId}&club_name=${encodeURIComponent(clubName)}&record_year=${year}&record_semester=${semester}`);
        const fData = await fRes.json();
        if (fData.success && fData.files.length > 0) {
            refHtml += '<p class="mt-2 mb-1"><strong>첨부파일:</strong></p>' + fData.files.map(f => `<p class="text-xs text-slate-500 ml-2">• ${f.file_name} (${f.uploaded_at})</p>`).join('');
        }
    } catch (e) {}
    document.getElementById('cw-ref-data').innerHTML = refHtml || '참고할 기초자료가 없습니다.';
}

// ===== 과세특 기초작업 =====
async function onSubjectBaseFilterChange() {
    const subjectName = document.getElementById('sb-subject').value;
    const grade = document.getElementById('sb-grade').value; const classNo = document.getElementById('sb-class').value;
    const studentSelect = document.getElementById('sb-student');
    document.getElementById('sb-form').classList.add('hidden'); document.getElementById('sb-placeholder').classList.remove('hidden');
    if (!subjectName || !grade || !classNo) { studentSelect.innerHTML = '<option value="">학생을 선택하세요</option>'; return; }
    try {
        const res = await fetch(`/api/subject/students?school_id=${userInfo.school_id}&class_grade=${grade}&class_no=${classNo}`);
        const data = await res.json();
        studentSelect.innerHTML = '<option value="">학생을 선택하세요</option>';
        if (data.success) data.students.forEach(s => { const opt = document.createElement('option'); opt.value = JSON.stringify(s); opt.textContent = `${s.class_num}번 ${s.member_name}`; studentSelect.appendChild(opt); });
    } catch (e) {}
    loadSubjectCommonList();
}

async function loadSubjectStudentBase() {
    const val = document.getElementById('sb-student').value;
    if (!val) { document.getElementById('sb-form').classList.add('hidden'); document.getElementById('sb-placeholder').classList.remove('hidden'); return; }
    const s = JSON.parse(val);
    const subjectName = document.getElementById('sb-subject').value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    document.getElementById('sb-form').classList.remove('hidden'); document.getElementById('sb-placeholder').classList.add('hidden');
    document.getElementById('sb-content').value = '';
    document.getElementById('sb-form').dataset.studentId = s.member_id; document.getElementById('sb-form').dataset.studentName = s.member_name;
    document.getElementById('sb-form').dataset.grade = s.class_grade; document.getElementById('sb-form').dataset.classNo = s.class_no; document.getElementById('sb-form').dataset.classNum = s.class_num;
    try {
        const res = await fetch(`/api/subject/record/get?school_id=${userInfo.school_id}&student_id=${s.member_id}&subject_name=${encodeURIComponent(subjectName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.record && data.record.base_data) document.getElementById('sb-content').value = data.record.base_data;
    } catch (e) {}
    loadSubjectFileList(s.member_id);
}

async function saveSubjectBase() {
    const form = document.getElementById('sb-form');
    const subjectName = document.getElementById('sb-subject').value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    try {
        const res = await fetch('/api/subject/base/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, student_id: form.dataset.studentId, student_name: form.dataset.studentName, subject_name: subjectName, class_grade: form.dataset.grade, class_no: form.dataset.classNo, class_num: form.dataset.classNum, record_year: year, record_semester: semester, base_data: document.getElementById('sb-content').value }) });
        const data = await res.json();
        alert(data.message);
    } catch (e) { alert('저장 중 오류 발생'); }
}

async function handleSubjectFiles(input) {
    const files = input.files;
    if (!files.length) return;
    const form = document.getElementById('sb-form');
    const subjectName = document.getElementById('sb-subject').value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    document.getElementById('sb-upload-progress').classList.remove('hidden');
    for (const file of files) {
        const fd = new FormData();
        fd.append('file', file); fd.append('school_id', userInfo.school_id); fd.append('member_school', userInfo.member_school || '');
        fd.append('teacher_id', userInfo.member_id); fd.append('teacher_name', userInfo.member_name || '');
        fd.append('student_id', form.dataset.studentId); fd.append('student_name', form.dataset.studentName || '');
        fd.append('subject_name', subjectName);
        fd.append('record_year', year); fd.append('record_semester', semester);
        try { await fetch('/api/subject/file/upload', { method: 'POST', body: fd }); } catch (e) {}
    }
    document.getElementById('sb-upload-progress').classList.add('hidden');
    input.value = '';
    loadSubjectFileList(form.dataset.studentId);
}

async function loadSubjectFileList(studentId) {
    const subjectName = document.getElementById('sb-subject').value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    try {
        const res = await fetch(`/api/subject/file/list?school_id=${userInfo.school_id}&student_id=${studentId}&subject_name=${encodeURIComponent(subjectName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        const listEl = document.getElementById('sb-file-list');
        if (data.success && data.files.length > 0) {
            listEl.innerHTML = data.files.map(f => `<div class="flex items-center justify-between p-2 bg-slate-50 rounded-lg text-sm"><a href="/api/subject/file/download/${f.id}" class="text-blue-600 hover:underline truncate flex-1">${f.file_name}</a><button onclick="deleteSubjectFile(${f.id},'${studentId}')" class="text-red-400 hover:text-red-600 ml-2"><i class="fas fa-trash-alt"></i></button></div>`).join('');
        } else { listEl.innerHTML = ''; }
    } catch (e) {}
}

async function deleteSubjectFile(fileId, studentId) {
    if (!confirm('파일을 삭제하시겠습니까?')) return;
    try { await fetch('/api/subject/file/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: fileId }) }); loadSubjectFileList(studentId); } catch (e) {}
}

function openSubjectCommonModal() { document.getElementById('sc-modal-title').value = ''; document.getElementById('sc-modal-content').value = ''; document.getElementById('sc-modal-date').value = ''; document.getElementById('subject-common-modal').classList.remove('hidden'); }
function closeSubjectCommonModal() { document.getElementById('subject-common-modal').classList.add('hidden'); }

async function submitSubjectCommon() {
    const subjectName = document.getElementById('sb-subject').value;
    const grade = document.getElementById('sb-grade').value; const classNo = document.getElementById('sb-class').value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    const title = document.getElementById('sc-modal-title').value.trim();
    if (!title) return alert('제목을 입력해주세요.');
    try {
        const res = await fetch('/api/subject/common/create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, subject_name: subjectName, class_grade: grade, class_no: classNo, record_year: year, record_semester: semester, activity_type: document.getElementById('sc-modal-type').value, title: title, content: document.getElementById('sc-modal-content').value.trim(), activity_date: document.getElementById('sc-modal-date').value }) });
        const data = await res.json();
        alert(data.message); if (data.success) { closeSubjectCommonModal(); loadSubjectCommonList(); }
    } catch (e) { alert('등록 중 오류 발생'); }
}

async function loadSubjectCommonList() {
    const subjectName = document.getElementById('sb-subject')?.value;
    const grade = document.getElementById('sb-grade')?.value;
    const classNo = document.getElementById('sb-class')?.value;
    const year = document.getElementById('sb-year')?.value || '2026';
    const semester = document.getElementById('sb-semester')?.value || '1';
    if (!subjectName) return;
    try {
        const res = await fetch(`/api/subject/common/list?school_id=${userInfo.school_id}&subject_name=${encodeURIComponent(subjectName)}&class_grade=${grade}&class_no=${classNo}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        const listEl = document.getElementById('sb-common-list');
        if (data.success && data.activities.length > 0) {
            listEl.innerHTML = data.activities.map(a => `<div class="p-3 bg-slate-50 rounded-xl"><div class="flex justify-between items-start"><div><p class="font-bold text-sm">${a.title}</p><p class="text-xs text-slate-500 mt-1">${a.activity_date || ''} | ${a.activity_type}</p>${a.content ? `<p class="text-xs text-slate-600 mt-1">${a.content}</p>` : ''}</div><button onclick="deleteSubjectCommon(${a.id})" class="text-red-400 hover:text-red-600 text-xs"><i class="fas fa-trash-alt"></i></button></div></div>`).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400">등록된 공통사항이 없습니다.</div>'; }
    } catch (e) {}
}

async function deleteSubjectCommon(id) {
    if (!confirm('삭제하시겠습니까?')) return;
    try { const res = await fetch('/api/subject/common/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }); const data = await res.json(); if (data.success) { loadSubjectCommonList(); } else { alert(data.message || '삭제 실패'); } } catch (e) { alert('삭제 중 오류 발생'); }
}

// ===== 과세특 작성 =====
async function saveSubjectWrite(status) {
    if (!swSelectedStudent) return alert('학생을 선택해주세요.');
    const subjectName = document.getElementById('sw-subject').value;
    const year = document.getElementById('sw-year')?.value || '2026';
    const semester = document.getElementById('sw-semester')?.value || '1';
    try {
        const res = await fetch('/api/subject/write/save', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ school_id: userInfo.school_id, member_school: userInfo.member_school || '', teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, student_id: swSelectedStudent.member_id, student_name: swSelectedStudent.member_name, subject_name: subjectName, class_grade: swSelectedStudent.class_grade, class_no: swSelectedStudent.class_no, class_num: swSelectedStudent.class_num, record_year: year, record_semester: semester, content: document.getElementById('sw-content').value, status }) });
        const data = await res.json();
        alert(data.message); if (data.success) onSubjectWriteFilterChange();
    } catch (e) { alert('저장 중 오류 발생'); }
}

// ===== 자유학기 옵션 토글 (중학교 1학년만) =====
function toggleFreeSemesterOption() {
    const grade = document.getElementById('sw-grade')?.value;
    const el = document.getElementById('sw-free-semester-wrap');
    if (el) el.classList.toggle('hidden', grade !== '1');
    if (grade !== '1') { const cb = document.getElementById('sw-free-semester'); if (cb) cb.checked = false; }
}

async function onSubjectWriteFilterChange() {
    toggleFreeSemesterOption();
    const subjectName = document.getElementById('sw-subject')?.value;
    const grade = document.getElementById('sw-grade')?.value; const classNo = document.getElementById('sw-class')?.value;
    const year = document.getElementById('sw-year')?.value; const semester = document.getElementById('sw-semester')?.value;
    const listEl = document.getElementById('sw-student-list');
    document.getElementById('sw-write-form').classList.add('hidden'); document.getElementById('sw-placeholder').classList.remove('hidden'); swSelectedStudent = null;
    if (!subjectName || !grade || !classNo) { listEl.innerHTML = '<div class="text-center py-8 text-slate-400">과목과 학급을 선택하세요.</div>'; return; }
    listEl.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin text-purple-400"></i></div>';
    try {
        const res = await fetch(`/api/subject/record/status-list?school_id=${userInfo.school_id}&subject_name=${encodeURIComponent(subjectName)}&class_grade=${grade}&class_no=${classNo}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.students.length > 0) {
            listEl.innerHTML = data.students.map(s => { const badge = s.status === 'complete' ? '<span class="w-2 h-2 bg-green-400 rounded-full"></span>' : s.status === 'draft' ? '<span class="w-2 h-2 bg-yellow-400 rounded-full"></span>' : '<span class="w-2 h-2 bg-slate-300 rounded-full"></span>';
                return `<div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl cursor-pointer hover:bg-purple-50 hover:border-purple-300 border border-transparent transition" onclick="selectSubjectWriteStudent('${s.member_id}','${s.member_name}','${s.class_grade}','${s.class_no}','${s.class_num}',this)">${badge}<div class="w-8 h-8 bg-gradient-to-br from-purple-400 to-indigo-500 rounded-full flex items-center justify-center text-white font-bold text-xs">${(s.member_name||'?').charAt(0)}</div><div class="flex-1 min-w-0"><p class="font-bold text-sm text-slate-800 truncate">${s.member_name}</p><p class="text-xs text-slate-500">${s.class_grade}학년 ${s.class_no}반 ${s.class_num}번</p></div></div>`; }).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">해당 학급에 학생이 없습니다.</div>'; }
    } catch (e) { listEl.innerHTML = '<div class="text-center py-8 text-red-400 text-sm">조회 중 오류 발생</div>'; }
}

async function selectSubjectWriteStudent(studentId, studentName, grade, classNo, classNum, el) {
    document.querySelectorAll('#sw-student-list > div').forEach(d => { d.classList.remove('bg-purple-50', 'border-purple-300'); d.classList.add('bg-slate-50', 'border-transparent'); });
    el.classList.remove('bg-slate-50', 'border-transparent'); el.classList.add('bg-purple-50', 'border-purple-300');
    swSelectedStudent = { member_id: studentId, member_name: studentName, class_grade: grade, class_no: classNo, class_num: classNum };
    document.getElementById('sw-student-avatar').textContent = (studentName||'?').charAt(0); document.getElementById('sw-student-name').textContent = studentName; document.getElementById('sw-student-info').textContent = `${grade}학년 ${classNo}반 ${classNum}번`;
    document.getElementById('sw-write-form').classList.remove('hidden'); document.getElementById('sw-placeholder').classList.add('hidden');
    document.getElementById('sw-content').value = ''; document.getElementById('sw-byte-count').textContent = '0';
    const subjectName = document.getElementById('sw-subject').value;
    const year = document.getElementById('sw-year').value; const semester = document.getElementById('sw-semester').value;
    let refHtml = '';
    // 1) 기초자료
    try {
        const res = await fetch(`/api/subject/record/get?school_id=${userInfo.school_id}&student_id=${studentId}&subject_name=${encodeURIComponent(subjectName)}&record_year=${year}&record_semester=${semester}`);
        const data = await res.json();
        if (data.success && data.record) {
            if (data.record.content) { document.getElementById('sw-content').value = data.record.content; updateSubjectWriteBytes(); }
            if (data.record.base_data) refHtml += `<p class="mb-1"><strong>기초자료:</strong> ${data.record.base_data}</p>`;
        }
    } catch (e) {}
    // 2) 공통활동
    try {
        const cRes = await fetch(`/api/subject/common/list?school_id=${userInfo.school_id}&subject_name=${encodeURIComponent(subjectName)}&class_grade=${grade}&class_no=${classNo}&record_year=${year}&record_semester=${semester}`);
        const cData = await cRes.json();
        if (cData.success && cData.activities.length > 0) {
            refHtml += '<p class="mt-2 mb-1"><strong>공통활동:</strong></p>' + cData.activities.map(a => `<p class="text-xs text-slate-500 ml-2">• [${a.activity_date||''}] ${a.activity_type}: ${a.title}</p>`).join('');
        }
    } catch (e) {}
    // 3) 제출 과제 (버그수정: 학생이 제출한 과제를 참고자료에 표시)
    try {
        const sRes = await fetch(`/api/subject/student-submissions?school_id=${userInfo.school_id}&student_id=${studentId}&subject_name=${encodeURIComponent(subjectName)}&record_year=${year}&record_semester=${semester}`);
        const sData = await sRes.json();
        if (sData.success && sData.submissions.length > 0) {
            refHtml += '<p class="mt-2 mb-1"><strong>제출 과제:</strong></p>' + sData.submissions.map(s => {
                let line = `• 과제: ${s.assignment_title}`;
                if (s.file_name) line += ` [${s.file_name}]`;
                if (s.comment) line += ` - ${s.comment}`;
                if (s.submitted_at) line += ` (${s.submitted_at})`;
                return `<p class="text-xs text-slate-500 ml-2">${line}</p>`;
            }).join('');
        }
    } catch (e) {}
    // 4) 첨부파일
    try {
        const fRes = await fetch(`/api/subject/file/list?school_id=${userInfo.school_id}&student_id=${studentId}&subject_name=${encodeURIComponent(subjectName)}&record_year=${year}&record_semester=${semester}`);
        const fData = await fRes.json();
        if (fData.success && fData.files.length > 0) {
            refHtml += '<p class="mt-2 mb-1"><strong>첨부파일:</strong></p>' + fData.files.map(f => `<p class="text-xs text-slate-500 ml-2">• ${f.file_name} (${f.uploaded_at})</p>`).join('');
        }
    } catch (e) {}
    document.getElementById('sw-ref-data').innerHTML = refHtml || '참고할 기초자료가 없습니다.';
}

// ===== AI 과세특 생성 (제출 과제 포함) =====
async function generateSubjectAI() {
    const subjectName = document.getElementById('sw-subject')?.value;
    const studentName = document.getElementById('sw-student-name')?.textContent;
    const baseRef = document.getElementById('sw-ref-data')?.innerText || '';
    const byteLimit = parseInt(document.getElementById('sw-byte-max')?.value) || 500;
    if (!subjectName || !studentName || studentName === '-') return alert('과목과 학생을 먼저 선택해주세요.');
    const grade = document.getElementById('sw-grade')?.value || '';
    const classNo = document.getElementById('sw-class')?.value || '';
    if (currentPoint !== 'free') { if (currentPoint < 300) return alert(`포인트가 부족합니다.\n\n현재 포인트: ${currentPoint.toLocaleString()}P\n필요 포인트: 300P`); if (!confirm(`${studentName} 학생의 '${subjectName}' 과세특을 AI로 생성합니다.\n\n300포인트가 차감됩니다.\n현재 포인트: ${currentPoint.toLocaleString()}P\n차감 후: ${(currentPoint - 300).toLocaleString()}P\n\n계속하시겠습니까?`)) return; }
    const btn = document.getElementById('btn-sw-generate'); const btnOriginal = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>AI 생성 중... (약 30초~1분)'; btn.className = 'w-full py-3 bg-slate-400 text-white font-bold rounded-xl cursor-wait transition';
    document.getElementById('sw-content').value = '⏳ AI가 생성 중입니다... 잠시만 기다려주세요.'; document.getElementById('sw-content').disabled = true;
    try {
        const res = await fetch('/api/subject/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ member_id: userInfo.member_id, school_id: userInfo.school_id, student_id: swSelectedStudent?.member_id, student_name: studentName, subject_name: subjectName, class_grade: grade, class_no: classNo, base_data: baseRef, common_activities: [], submission_data: '', byte_limit: byteLimit, school_level: 'middle', free_semester: document.getElementById('sw-free-semester')?.checked || false }) });
        const data = await res.json();
        if (data.success) { document.getElementById('sw-content').value = data.content; updateSubjectWriteBytes(); if (data.new_point !== undefined) displayPoint(data.new_point); const pointMsg = data.new_point === 'free' ? '(Free 사용자)' : `차감: -${data.point_used}P → 잔여: ${typeof data.new_point === 'number' ? data.new_point.toLocaleString() : data.new_point}P`; alert(`✅ AI 과세특 생성 완료!\n\n생성 바이트: ${data.bytes}B / ${byteLimit}B\n포인트 ${pointMsg}\n\n내용을 확인하고 필요시 수정 후 저장하세요.`); }
        else { document.getElementById('sw-content').value = ''; alert(data.point_error ? data.message : 'AI 생성 실패: ' + data.message); if (!data.point_error && data.new_point !== undefined) displayPoint(data.new_point); }
    } catch (e) { document.getElementById('sw-content').value = ''; alert('AI 생성 중 네트워크 오류가 발생했습니다.'); }
    finally { btn.disabled = false; btn.innerHTML = btnOriginal; btn.className = 'w-full py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white font-bold rounded-xl shadow-lg hover:shadow-xl transition'; document.getElementById('sw-content').disabled = false; }
}

// ===== AI 동아리 기록 생성 (파일 포함) =====
async function generateClubAI() {
    const clubName = document.getElementById('cw-club')?.value;
    const studentName = document.getElementById('cw-student-name')?.textContent;
    const baseRef = document.getElementById('cw-ref-data')?.innerText || '';
    const byteLimit = parseInt(document.getElementById('cw-byte-max')?.value) || 500;
    if (!clubName || !studentName || studentName === '-') return alert('동아리와 학생을 먼저 선택해주세요.');
    if (currentPoint !== 'free') { if (currentPoint < 300) return alert(`포인트가 부족합니다.\n\n현재 포인트: ${currentPoint.toLocaleString()}P\n필요 포인트: 300P`); if (!confirm(`${studentName} 학생의 '${clubName}' 동아리 기록을 AI로 생성합니다.\n\n300포인트가 차감됩니다.\n현재 포인트: ${currentPoint.toLocaleString()}P\n차감 후: ${(currentPoint - 300).toLocaleString()}P\n\n계속하시겠습니까?`)) return; }
    const btn = document.getElementById('btn-cw-generate'); const btnOriginal = btn.innerHTML;
    btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>AI 생성 중... (약 30초~1분)'; btn.className = 'w-full py-3 bg-slate-400 text-white font-bold rounded-xl cursor-wait transition';
    document.getElementById('cw-content').value = '⏳ AI가 생성 중입니다... 잠시만 기다려주세요.'; document.getElementById('cw-content').disabled = true;
    try {
        const res = await fetch('/api/club/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ member_id: userInfo.member_id, school_id: userInfo.school_id, student_id: cwSelectedStudent?.member_id, student_name: studentName, club_name: clubName, class_grade: cwSelectedStudent?.class_grade || '', class_no: cwSelectedStudent?.class_no || '', base_data: baseRef, common_activities: [], file_data: '', byte_limit: byteLimit, school_level: 'middle' }) });
        const data = await res.json();
        if (data.success) { document.getElementById('cw-content').value = data.content; updateClubWriteBytes(); if (data.new_point !== undefined) displayPoint(data.new_point); const pointMsg = data.new_point === 'free' ? '(Free 사용자)' : `차감: -${data.point_used}P → 잔여: ${typeof data.new_point === 'number' ? data.new_point.toLocaleString() : data.new_point}P`; alert(`✅ AI 동아리 기록 생성 완료!\n\n생성 바이트: ${data.bytes}B / ${byteLimit}B\n포인트 ${pointMsg}\n\n내용을 확인하고 필요시 수정 후 저장하세요.`); }
        else { document.getElementById('cw-content').value = ''; alert(data.point_error ? data.message : 'AI 생성 실패: ' + data.message); if (!data.point_error && data.new_point !== undefined) displayPoint(data.new_point); }
    } catch (e) { document.getElementById('cw-content').value = ''; alert('AI 생성 중 네트워크 오류가 발생했습니다.'); }
    finally { btn.disabled = false; btn.innerHTML = btnOriginal; btn.className = 'w-full py-3 bg-gradient-to-r from-teal-500 to-emerald-600 text-white font-bold rounded-xl shadow-lg hover:shadow-xl transition'; document.getElementById('cw-content').disabled = false; }
}

// ===== 과제 출제/관리 =====
async function createAssignment() {
    let subjectName = document.getElementById('hw-subject').value;
    // 검색 입력에서 자동 매칭 (드롭다운 클릭 안 한 경우 대비)
    if (!subjectName) {
        const searchVal = (document.getElementById('hw-subject-search').value || '').trim();
        if (searchVal && _allSubjectOptions.length) {
            let match = _allSubjectOptions.find(o => o.text === searchVal);
            if (!match) match = _allSubjectOptions.find(o => o.text.startsWith(searchVal));
            if (!match) { const c = _allSubjectOptions.filter(o => o.text.includes(searchVal)); if (c.length === 1) match = c[0]; }
            if (match) { subjectName = match.value; document.getElementById('hw-subject').value = match.value; document.getElementById('hw-subject-search').value = match.text; }
        }
    }
    const grade = document.getElementById('hw-grade').value;
    const selectedClasses = getSelectedHwClasses();
    const title = document.getElementById('hw-title').value.trim();
    if (!subjectName || !grade || selectedClasses.length === 0 || !title) return alert('과목, 학년, 반, 과제 제목을 모두 입력해주세요.');
    const desc = document.getElementById('hw-desc').value.trim();
    const dueDate = document.getElementById('hw-due').value;
    const year = document.getElementById('hw-year').value;
    const semester = document.getElementById('hw-semester').value;
    let successCount = 0;
    let failCount = 0;
    for (const classNo of selectedClasses) {
        try {
            const res = await fetch('/api/subject/assignment/create', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ school_id: userInfo.school_id, teacher_id: userInfo.member_id, teacher_name: userInfo.member_name, subject_name: subjectName, class_grade: grade, class_no: classNo, record_year: year, record_semester: semester, title: title, description: desc, due_date: dueDate }) });
            const data = await res.json();
            if (data.success) successCount++; else failCount++;
        } catch (e) { failCount++; }
    }
    if (successCount > 0) {
        alert(`"${title}" 과제가 ${successCount}개 반에 출제되었습니다.${failCount > 0 ? ` (실패: ${failCount}개 반)` : ''}`);
        document.getElementById('hw-title').value = ''; document.getElementById('hw-desc').value = ''; document.getElementById('hw-due').value = '';
        loadAssignments();
    } else { alert('과제 출제에 실패했습니다.'); }
}

async function loadAssignments() {
    const listEl = document.getElementById('hw-assignment-list');
    if (!userInfo.school_id) { listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">로그인 정보가 없습니다.</div>'; return; }
    try {
        // 해당 교사의 전체 과제를 항상 표시 (과목/학년/반 필터 없음)
        const url = `/api/subject/assignment/list?school_id=${userInfo.school_id}&record_year=${document.getElementById('hw-year').value}&record_semester=${document.getElementById('hw-semester').value}`;
        const res = await fetch(url);
        const data = await res.json();
        const assignments = data.success ? data.assignments : [];
        if (assignments.length > 0) {
            listEl.innerHTML = assignments.map(a => `<div class="p-4 bg-slate-50 rounded-xl"><div class="flex justify-between items-start"><div class="flex-1"><p class="font-bold text-sm">${a.title}</p><p class="text-xs text-slate-500 mt-1">${a.subject_name} | ${a.class_grade}학년 ${a.class_no}반${a.due_date ? ' | 마감: ' + a.due_date : ''}</p>${a.description ? `<p class="text-xs text-slate-600 mt-2">${a.description}</p>` : ''}<p class="text-xs text-blue-600 mt-2 cursor-pointer hover:underline" onclick="viewSubmissions(${a.id},'${a.title}')"><i class="fas fa-eye mr-1"></i>제출현황 (${a.submission_count}명)</p></div><button onclick="deleteAssignment(${a.id})" class="text-red-400 hover:text-red-600 text-sm ml-3"><i class="fas fa-trash-alt"></i></button></div></div>`).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">등록된 과제가 없습니다.</div>'; }
    } catch (e) { listEl.innerHTML = '<div class="text-center py-8 text-red-400 text-sm">조회 중 오류 발생</div>'; }
}

async function deleteAssignment(id) {
    if (!confirm('과제를 삭제하시겠습니까?')) return;
    try { const res = await fetch('/api/subject/assignment/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) }); const data = await res.json(); if (data.success) { loadAssignments(); } else { alert(data.message || '삭제 실패'); } } catch (e) { alert('삭제 중 오류 발생'); }
}

async function viewSubmissions(assignmentId, title) {
    document.getElementById('submission-modal-title').textContent = title;
    document.getElementById('submission-list').innerHTML = '<div class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin mr-2"></i>로딩 중...</div>';
    document.getElementById('submission-modal').classList.remove('hidden');
    try {
        const res = await fetch(`/api/subject/submission/list?assignment_id=${assignmentId}`);
        const data = await res.json();
        const listEl = document.getElementById('submission-list');
        if (data.success && data.submissions.length > 0) {
            listEl.innerHTML = data.submissions.map((s, i) => `<div class="flex items-center gap-3 p-3 bg-slate-50 rounded-xl"><div class="w-8 h-8 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-full flex items-center justify-center text-white font-bold text-xs">${i+1}</div><div class="flex-1 min-w-0"><p class="font-bold text-sm">${s.student_name}</p><p class="text-xs text-slate-500">${s.submitted_at}</p></div><a href="/api/subject/submission/download/${s.id}" class="text-blue-600 hover:underline text-xs"><i class="fas fa-download mr-1"></i>${s.file_name}</a></div>`).join('');
        } else { listEl.innerHTML = '<div class="text-center py-8 text-slate-400 text-sm">제출한 학생이 없습니다.</div>'; }
    } catch (e) { document.getElementById('submission-list').innerHTML = '<div class="text-center py-8 text-red-400 text-sm">조회 중 오류 발생</div>'; }
}

function handleLogout() { if (confirm('로그아웃 하시겠습니까?')) { localStorage.removeItem('schoolus_user'); window.location.href = '/'; } }