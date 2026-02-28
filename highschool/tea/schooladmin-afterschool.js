// schooladmin-afterschool.js — 방과후학교 탭 전체
let currentAsSubTab = 'register';
let manageStatusFilter = '';
let allManagePrograms = [];

function switchAsSubTab(tab) {
    currentAsSubTab = tab;
    // 버튼 스타일
    document.querySelectorAll('.as-sub-btn').forEach(b => {
        b.className = 'as-sub-btn px-5 py-2.5 rounded-xl font-bold text-sm border-2 transition bg-white text-slate-600 border-slate-200 hover:border-emerald-300';
    });
    const activeBtn = document.getElementById(`as-sub-${tab}`);
    if (activeBtn) activeBtn.className = 'as-sub-btn px-5 py-2.5 rounded-xl font-bold text-sm border-2 transition bg-emerald-500 text-white border-emerald-500';
    // 패널 전환
    document.getElementById('as-panel-register').classList.toggle('hidden', tab !== 'register');
    document.getElementById('as-panel-manage').classList.toggle('hidden', tab !== 'manage');
    document.getElementById('as-detail-view').classList.add('hidden');
    document.getElementById('as-attendance-view').classList.add('hidden');
    document.getElementById('as-sub-tabs').classList.remove('hidden');
    if (tab === 'register') loadPrograms();
    else loadManagePrograms();
}

async function loadManagePrograms() {
    try {
        const r = await fetch(`/api/afterschool/list?school_id=${currentUser.school_id}`);
        const d = await r.json();
        if (!d.success) return;
        allManagePrograms = d.programs || [];
        renderManageTable();
    } catch(e) { console.error('관리 목록 오류:', e); }
}

function filterManagePrograms(status) {
    manageStatusFilter = status;
    document.querySelectorAll('.as-filter-btn').forEach(b => {
        b.className = b.dataset.status === status
            ? 'as-filter-btn px-3 py-1.5 rounded-lg text-xs font-bold border bg-indigo-500 text-white border-indigo-500'
            : 'as-filter-btn px-3 py-1.5 rounded-lg text-xs font-bold border bg-white text-slate-600 border-slate-200 hover:bg-slate-100';
    });
    renderManageTable();
}

function renderManageTable() {
    const filtered = manageStatusFilter ? allManagePrograms.filter(p => p.status === manageStatusFilter) : allManagePrograms;
    const body = document.getElementById('as-manage-body');
    const empty = document.getElementById('as-manage-empty');

    if (filtered.length === 0) {
        body.innerHTML = ''; empty.classList.remove('hidden'); return;
    }
    empty.classList.add('hidden');

    const statusMap = {recruiting:'모집중', confirmed:'확정', ongoing:'진행중', completed:'완료'};
    const statusColor = {recruiting:'bg-blue-100 text-blue-700', confirmed:'bg-emerald-100 text-emerald-700', ongoing:'bg-amber-100 text-amber-700', completed:'bg-slate-100 text-slate-500'};

    body.innerHTML = filtered.map(p => {
        let actions = `<button onclick="openAsDetail(${p.id})" class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold hover:bg-blue-200">상세</button>`;
        if (p.status === 'recruiting') {
            actions += `<button onclick="openAsDetail(${p.id})" class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold hover:bg-emerald-200">승인관리</button>`;
        }
        if (p.status === 'confirmed') {
            actions += `<button onclick="startProgram(${p.id})" class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold hover:bg-blue-200">시작</button>`;
        }
        if (['confirmed','ongoing'].includes(p.status)) {
            actions += `<button onclick="openAsAttendance(${p.id})" class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-bold hover:bg-green-200">출결</button>`;
        }
        if (p.status === 'ongoing') {
            actions += `<button onclick="completeProgram(${p.id})" class="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-bold hover:bg-orange-200">완료</button>`;
        }
        return `<tr class="hover:bg-slate-50">
            <td class="px-4 py-3 font-medium text-slate-800">${p.program_name}</td>
            <td class="px-4 py-3 text-center text-sm">${p.instructor_name||'-'}</td>
            <td class="px-4 py-3 text-center text-sm">${p.start_date}~${p.end_date}</td>
            <td class="px-4 py-3 text-center"><span class="px-2 py-0.5 rounded-full text-xs font-bold ${statusColor[p.status]||''}">${statusMap[p.status]||p.status}</span></td>
            <td class="px-4 py-3 text-center text-sm font-bold">${p.enrolled_count}/${p.max_students}</td>
            <td class="px-4 py-3 text-center"><div class="flex gap-1 justify-center flex-wrap">${actions}</div></td>
        </tr>`;
    }).join('');
}

async function loadPrograms() {
    try {
        const r = await fetch(`/api/afterschool/list?school_id=${currentUser.school_id}`);
        const d = await r.json();
        if (!d.success) return;

        const body = document.getElementById('as-list-body');
        const empty = document.getElementById('as-empty');

        if (!d.programs || d.programs.length === 0) {
            body.innerHTML = ''; empty.classList.remove('hidden'); return;
        }
        empty.classList.add('hidden');

        const statusMap = {recruiting:'모집중', confirmed:'확정', ongoing:'진행중', completed:'완료'};

        body.innerHTML = d.programs.map(p => `
            <tr class="hover:bg-slate-50">
                <td class="px-4 py-3 font-medium text-slate-800">${p.program_name}</td>
                <td class="px-4 py-3 text-center text-sm">${p.instructor_name||'-'}</td>
                <td class="px-4 py-3 text-center text-sm">${p.day_of_week||''} ${p.time_slot||''}<br><span class="text-xs text-slate-400">${p.start_date}~${p.end_date}</span></td>
                <td class="px-4 py-3 text-center"><span class="status-badge status-${p.status}">${statusMap[p.status]||p.status}</span></td>
                <td class="px-4 py-3 text-center text-sm font-bold">${p.enrolled_count}/${p.max_students}</td>
                <td class="px-4 py-3 text-center">
                    <div class="flex gap-1 justify-center flex-wrap">
                        <button onclick="openAsDetail(${p.id})" class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold hover:bg-blue-200">상세</button>
                        ${p.status==='recruiting'?`<button onclick="openProgramEditor(${p.id})" class="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-bold hover:bg-indigo-200">수정</button><button onclick="deleteProgram(${p.id})" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold hover:bg-red-200">삭제</button>`:''}
                        ${['confirmed','ongoing'].includes(p.status)?`<button onclick="openAsAttendance(${p.id})" class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-bold hover:bg-green-200">출결</button>`:''}
                        ${p.status==='ongoing'?`<button onclick="completeProgram(${p.id})" class="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-bold hover:bg-orange-200">완료</button>`:''}
                    </div>
                </td>
            </tr>
        `).join('');
    } catch(e) { console.error('방과후 목록 오류:', e); }
}

function openProgramEditor(id) {
    document.getElementById('as-edit-id').value = id || '';
    document.getElementById('as-editor-modal-title').textContent = id ? '프로그램 수정' : '프로그램 등록';
    // 교사 목록 로드
    loadTeacherList();
    if (!id) {
        ['as-name','as-desc','as-instructor','as-dow','as-time'].forEach(x => document.getElementById(x).value = '');
        document.getElementById('as-grades').value = 'all';
        document.getElementById('as-max').value = 30;
        document.getElementById('as-sessions').value = 10;
        document.getElementById('as-start').value = '';
        document.getElementById('as-end').value = '';
    } else {
        // 기존 데이터 로드
        fetch(`/api/afterschool/detail?id=${id}`).then(r=>r.json()).then(d => {
            if (!d.success) return;
            const p = d.program;
            document.getElementById('as-name').value = p.program_name;
            document.getElementById('as-desc').value = p.description;
            document.getElementById('as-instructor').value = p.instructor_name;
            document.getElementById('as-grades').value = p.target_grades;
            document.getElementById('as-max').value = p.max_students;
            document.getElementById('as-sessions').value = p.total_sessions;
            document.getElementById('as-dow').value = p.day_of_week;
            document.getElementById('as-time').value = p.time_slot;
            document.getElementById('as-start').value = p.start_date;
            document.getElementById('as-end').value = p.end_date;
        });
    }
    document.getElementById('as-editor-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeProgramEditor() { document.getElementById('as-editor-modal').classList.add('hidden'); document.body.style.overflow = 'auto'; }

async function loadTeacherList() {
    try {
        const r = await fetch('/api/afterschool/teachers');
        const d = await r.json();
        if (!d.success) return;
        const dl = document.getElementById('as-teacher-list');
        dl.innerHTML = d.teachers.map(t => `<option value="${t}">`).join('');
    } catch(e) { console.error('교사 목록 로드 오류:', e); }
}

async function saveProgram() {
    const name = document.getElementById('as-name').value.trim();
    const startDate = document.getElementById('as-start').value;
    const endDate = document.getElementById('as-end').value;
    if (!name || !startDate || !endDate) return alert('프로그램명, 시작일, 종료일을 입력해주세요.');

    const payload = {
        school_id: currentUser.school_id,
        program_name: name,
        description: document.getElementById('as-desc').value.trim(),
        instructor_name: document.getElementById('as-instructor').value.trim(),
        target_grades: document.getElementById('as-grades').value,
        max_students: parseInt(document.getElementById('as-max').value) || 30,
        total_sessions: parseInt(document.getElementById('as-sessions').value) || 10,
        day_of_week: document.getElementById('as-dow').value.trim(),
        time_slot: document.getElementById('as-time').value.trim(),
        start_date: startDate,
        end_date: endDate
    };

    const editId = document.getElementById('as-edit-id').value;
    const url = editId ? '/api/afterschool/update' : '/api/afterschool/create';
    if (editId) payload.id = editId;

    try {
        const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        const d = await r.json(); alert(d.message);
        if (d.success) { closeProgramEditor(); loadPrograms(); }
    } catch(e) { alert('저장 중 오류'); }
}

async function deleteProgram(id) {
    if (!confirm('프로그램을 삭제하시겠습니까?')) return;
    try {
        const r = await fetch('/api/afterschool/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
        const d = await r.json(); alert(d.message); loadPrograms();
    } catch(e) { alert('삭제 중 오류'); }
}

// 프로그램 상세 (수강생 관리)
let currentProgramId = null;
async function openAsDetail(id) {
    currentProgramId = id;
    document.getElementById('as-sub-tabs').classList.add('hidden');
    document.getElementById('as-panel-register').classList.add('hidden');
    document.getElementById('as-panel-manage').classList.add('hidden');
    document.getElementById('as-detail-view').classList.remove('hidden');
    try {
        const r = await fetch(`/api/afterschool/detail?id=${id}`);
        const d = await r.json();
        if (!d.success) return alert(d.message);
        const p = d.program;
        const statusMap = {recruiting:'모집중', confirmed:'확정', ongoing:'진행중', completed:'완료'};
        const canManage = ['recruiting','confirmed'].includes(p.status);
        const activeEnrolls = d.enrollments.filter(e => ['applied','approved'].includes(e.status));

        let html = `
            <div class="glass-card rounded-2xl p-6 mb-6 shadow-sm">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><span class="text-slate-400">프로그램</span><p class="font-bold">${p.program_name}</p></div>
                    <div><span class="text-slate-400">강사</span><p class="font-bold">${p.instructor_name||'-'}</p></div>
                    <div><span class="text-slate-400">일정</span><p class="font-bold">${p.day_of_week||''} ${p.time_slot||''}</p></div>
                    <div><span class="text-slate-400">상태</span><p><span class="status-badge status-${p.status}">${statusMap[p.status]}</span></p></div>
                    <div><span class="text-slate-400">기간</span><p class="font-bold">${p.start_date} ~ ${p.end_date}</p></div>
                    <div><span class="text-slate-400">정원</span><p class="font-bold">${activeEnrolls.length}/${p.max_students}명</p></div>
                    <div><span class="text-slate-400">회차</span><p class="font-bold">${p.total_sessions}회</p></div>
                    <div><span class="text-slate-400">대상</span><p class="font-bold">${p.target_grades==='all'?'전체':p.target_grades+'학년'}</p></div>
                </div>
            </div>
        `;

        // 수강생 테이블
        html += `<div class="glass-card rounded-2xl overflow-hidden shadow-sm">
            <div class="bg-slate-50 border-b px-6 py-4 flex items-center justify-between flex-wrap gap-2">
                <h4 class="font-bold text-slate-700"><i class="fas fa-users mr-2"></i>수강생 목록 (${d.enrollments.length}명)</h4>
                <div class="flex gap-2 flex-wrap">
                    ${canManage?`<button onclick="openEnrollModal(${id})" class="px-4 py-2 bg-blue-500 text-white rounded-lg font-bold text-sm hover:bg-blue-600 transition"><i class="fas fa-user-plus mr-1"></i>학생 등록</button>`:''}
                    ${p.status==='recruiting'?`<button onclick="approveAllEnrollments(${id})" class="px-4 py-2 bg-emerald-500 text-white rounded-lg font-bold text-sm hover:bg-emerald-600 transition"><i class="fas fa-check-double mr-1"></i>전체 승인 후 확정</button>`:''}
                    ${p.status==='confirmed'?`<button onclick="startProgram(${id})" class="px-4 py-2 bg-blue-500 text-white rounded-lg font-bold text-sm hover:bg-blue-600 transition"><i class="fas fa-play mr-1"></i>프로그램 시작</button>`:''}
                </div>
            </div>
            <div class="overflow-x-auto"><table class="w-full">
                <thead class="bg-slate-50 border-b">
                    <tr>
                        <th class="px-4 py-3 text-left text-xs font-bold text-slate-500">이름</th>
                        <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">학년반번</th>
                        <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">신청일</th>
                        <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">상태</th>
                        ${canManage?'<th class="px-4 py-3 text-center text-xs font-bold text-slate-500">관리</th>':''}
                    </tr>
                </thead>
                <tbody class="divide-y divide-slate-100">`;

        const enrollStatusMap = {applied:'신청', approved:'승인', rejected:'거절', withdrawn:'취소'};
        const statusColorMap = {applied:'bg-yellow-100 text-yellow-700', approved:'bg-emerald-100 text-emerald-700', rejected:'bg-red-100 text-red-700', withdrawn:'bg-slate-100 text-slate-500'};
        d.enrollments.forEach(e => {
            let actionBtns = '';
            if (canManage) {
                if (e.status === 'applied') {
                    actionBtns = `<button onclick="updateEnrollment(${e.id},'approved')" class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold hover:bg-emerald-200">승인</button>
                        <button onclick="updateEnrollment(${e.id},'rejected')" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold hover:bg-red-200">거절</button>`;
                } else if (e.status === 'approved') {
                    actionBtns = `<button onclick="cancelEnrollment(${e.id},'${e.student_id}',${id})" class="px-2 py-1 bg-slate-100 text-slate-600 rounded text-xs font-bold hover:bg-slate-200">취소</button>`;
                } else if (e.status === 'rejected') {
                    actionBtns = `<button onclick="updateEnrollment(${e.id},'approved')" class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold hover:bg-emerald-200">승인</button>`;
                }
            }
            html += `<tr class="${e.status==='withdrawn'||e.status==='rejected'?'opacity-50':''}">
                <td class="px-4 py-3 font-medium">${e.student_name}</td>
                <td class="px-4 py-3 text-center text-sm">${e.class_grade}-${e.class_no}-${e.class_num}</td>
                <td class="px-4 py-3 text-center text-sm text-slate-500">${e.applied_at}</td>
                <td class="px-4 py-3 text-center"><span class="px-2 py-0.5 rounded-full text-xs font-bold ${statusColorMap[e.status]||''}">${enrollStatusMap[e.status]||e.status}</span></td>
                ${canManage?`<td class="px-4 py-3 text-center"><div class="flex gap-1 justify-center">${actionBtns}</div></td>`:''}
            </tr>`;
        });
        if (d.enrollments.length === 0) {
            html += `<tr><td colspan="${canManage?5:4}" class="px-4 py-8 text-center text-slate-400">수강생이 없습니다</td></tr>`;
        }
        html += `</tbody></table></div></div>`;

        document.getElementById('as-detail-title').textContent = p.program_name;
        document.getElementById('as-detail-content').innerHTML = html;
    } catch(e) { alert('상세 조회 오류'); }
}

function closeAsDetail() {
    document.getElementById('as-detail-view').classList.add('hidden');
    document.getElementById('as-sub-tabs').classList.remove('hidden');
    if (currentAsSubTab === 'manage') {
        document.getElementById('as-panel-manage').classList.remove('hidden');
        loadManagePrograms();
    } else {
        document.getElementById('as-list-view').classList.remove('hidden');
        loadPrograms();
    }
}

// 개별 수강 승인/거절
async function updateEnrollment(enrollmentId, status) {
    const text = status === 'approved' ? '승인' : '거절';
    if (!confirm(`이 학생을 ${text}하시겠습니까?`)) return;
    try {
        const r = await fetch('/api/afterschool/enrollment/update', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({enrollment_id: enrollmentId, status})});
        const d = await r.json(); alert(d.message);
        if (d.success) openAsDetail(currentProgramId);
    } catch(e) { alert('처리 중 오류'); }
}

// 교사가 수강 취소
async function cancelEnrollment(enrollmentId, studentId, programId) {
    if (!confirm('이 학생의 수강을 취소하시겠습니까?')) return;
    try {
        const r = await fetch('/api/afterschool/cancel', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({enrollment_id: enrollmentId, student_id: studentId, program_id: programId})});
        const d = await r.json(); alert(d.message);
        if (d.success) openAsDetail(currentProgramId);
    } catch(e) { alert('취소 중 오류'); }
}

// 학생 등록 모달
function openEnrollModal(programId) {
    currentProgramId = programId;
    document.getElementById('enroll-search-input').value = '';
    document.getElementById('enroll-grade-filter').value = '';
    document.getElementById('enroll-search-results').innerHTML = '<div class="p-6 text-center text-slate-400 text-sm">이름 또는 학년으로 검색하세요</div>';
    document.getElementById('as-enroll-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeEnrollModal() {
    document.getElementById('as-enroll-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

async function searchStudentsForEnroll() {
    const keyword = document.getElementById('enroll-search-input').value.trim();
    const grade = document.getElementById('enroll-grade-filter').value;
    if (!keyword && !grade) return alert('이름 또는 학년을 입력해주세요.');
    try {
        const params = new URLSearchParams();
        if (keyword) params.set('q', keyword);
        if (grade) params.set('grade', grade);
        const r = await fetch(`/api/afterschool/search-students?${params}`);
        const d = await r.json();
        if (!d.success) return alert(d.message);
        const box = document.getElementById('enroll-search-results');
        if (!d.students || d.students.length === 0) {
            box.innerHTML = '<div class="p-6 text-center text-slate-400 text-sm">검색 결과가 없습니다</div>';
            return;
        }
        box.innerHTML = d.students.map(s => `
            <div class="flex items-center justify-between px-4 py-3 hover:bg-blue-50 border-b border-slate-100 last:border-0 cursor-pointer" onclick="enrollStudent('${s.member_id}')">
                <div>
                    <span class="font-bold text-sm text-slate-800">${s.member_name}</span>
                    <span class="text-xs text-slate-400 ml-2">${s.class_grade}-${s.class_no}-${s.class_num}</span>
                </div>
                <button class="px-3 py-1 bg-blue-500 text-white rounded-lg text-xs font-bold hover:bg-blue-600"><i class="fas fa-plus mr-1"></i>등록</button>
            </div>
        `).join('');
    } catch(e) { alert('검색 중 오류'); }
}

async function enrollStudent(studentId) {
    try {
        const r = await fetch('/api/afterschool/enroll', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({program_id: currentProgramId, student_id: studentId, auto_approve: true})});
        const d = await r.json(); alert(d.message);
        if (d.success) { closeEnrollModal(); openAsDetail(currentProgramId); }
    } catch(e) { alert('등록 중 오류'); }
}

async function approveAllEnrollments(programId) {
    if (!confirm('모든 신청자를 승인하고 수강을 확정하시겠습니까?')) return;
    try {
        const dr = await fetch(`/api/afterschool/detail?id=${programId}`);
        const dd = await dr.json();
        const enrollments = dd.enrollments.filter(e => e.status === 'applied').map(e => ({enrollment_id: e.id, status: 'approved'}));
        const r = await fetch('/api/afterschool/confirm', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({program_id: programId, enrollments})});
        const d = await r.json(); alert(d.message);
        openAsDetail(programId);
    } catch(e) { alert('승인 중 오류'); }
}

async function startProgram(id) {
    if (!confirm('프로그램을 시작하시겠습니까?')) return;
    try {
        const r = await fetch('/api/afterschool/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
        const d = await r.json(); alert(d.message); openAsDetail(id);
    } catch(e) { alert('시작 중 오류'); }
}

async function completeProgram(id) {
    const createSurvey = confirm('프로그램을 완료 처리하시겠습니까?\n\n[확인]을 누르면 만족도 설문이 자동 생성됩니다.');
    try {
        const r = await fetch('/api/afterschool/complete', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({id, create_survey: createSurvey})});
        const d = await r.json(); alert(d.message); loadPrograms();
    } catch(e) { alert('완료 처리 중 오류'); }
}

// 출결 관리
let currentAttProgramId = null;
let currentSessionNo = 1;

async function openAsAttendance(programId) {
    currentAttProgramId = programId;
    currentSessionNo = 1;
    document.getElementById('as-sub-tabs').classList.add('hidden');
    document.getElementById('as-panel-register').classList.add('hidden');
    document.getElementById('as-panel-manage').classList.add('hidden');
    document.getElementById('as-attendance-view').classList.remove('hidden');

    const dr = await fetch(`/api/afterschool/detail?id=${programId}`);
    const dd = await dr.json();
    if (!dd.success) return;
    const p = dd.program;
    document.getElementById('as-att-title').textContent = p.program_name + ' - 출결 관리';

    // 회차 선택 + 출결 테이블
    let html = `<div class="glass-card rounded-2xl p-6 mb-4 shadow-sm">
        <div class="flex items-center gap-4 flex-wrap mb-4">
            <label class="text-sm font-bold text-slate-600">회차 선택:</label>
            <div class="flex gap-1 flex-wrap" id="session-btns">`;
    for (let i = 1; i <= p.total_sessions; i++) {
        html += `<button onclick="loadSessionAtt(${i})" class="px-3 py-1.5 rounded-lg text-sm font-bold border ${i===1?'bg-indigo-500 text-white border-indigo-500':'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'}" id="sess-btn-${i}">${i}회</button>`;
    }
    html += `</div></div>
        <div class="flex items-center gap-4 mb-4">
            <label class="text-sm font-bold text-slate-500">날짜:</label>
            <input type="date" id="att-session-date" class="px-3 py-2 border border-slate-200 rounded-lg text-sm font-medium">
            <label class="text-sm font-bold text-slate-500">주제:</label>
            <input type="text" id="att-session-topic" placeholder="수업 주제" class="flex-1 px-3 py-2 border border-slate-200 rounded-lg text-sm font-medium">
        </div>
    </div>`;

    html += `<div class="glass-card rounded-2xl overflow-hidden shadow-sm mb-4">
        <div class="overflow-x-auto"><table class="w-full">
            <thead class="bg-slate-50 border-b">
                <tr>
                    <th class="px-4 py-3 text-left text-xs font-bold text-slate-500">이름</th>
                    <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">학년반번</th>
                    <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">출석</th>
                    <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">결석</th>
                    <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">지각</th>
                    <th class="px-4 py-3 text-center text-xs font-bold text-slate-500">사유</th>
                    <th class="px-4 py-3 text-left text-xs font-bold text-slate-500">메모</th>
                </tr>
            </thead>
            <tbody id="att-body" class="divide-y divide-slate-100"></tbody>
        </table></div>
    </div>`;

    html += `<button onclick="saveAttendance()" class="w-full py-3 bg-gradient-to-r from-emerald-500 to-green-600 text-white rounded-xl font-bold shadow hover:opacity-90 transition no-print">
        <i class="fas fa-save mr-2"></i>출결 저장
    </button>`;

    // 인쇄 영역 (전체 출석부)
    html += `<div id="att-print-area" class="hidden print-area"></div>`;

    document.getElementById('as-att-content').innerHTML = html;
    loadSessionAtt(1);
}

function closeAsAttendance() {
    document.getElementById('as-attendance-view').classList.add('hidden');
    document.getElementById('as-sub-tabs').classList.remove('hidden');
    if (currentAsSubTab === 'manage') {
        document.getElementById('as-panel-manage').classList.remove('hidden');
        loadManagePrograms();
    } else {
        document.getElementById('as-list-view').classList.remove('hidden');
        loadPrograms();
    }
}

async function loadSessionAtt(sessionNo) {
    currentSessionNo = sessionNo;
    // 버튼 스타일 업데이트
    document.querySelectorAll('#session-btns button').forEach(b => {
        b.className = 'px-3 py-1.5 rounded-lg text-sm font-bold border bg-white text-slate-600 border-slate-200 hover:bg-slate-100';
    });
    const activeBtn = document.getElementById(`sess-btn-${sessionNo}`);
    if (activeBtn) activeBtn.className = 'px-3 py-1.5 rounded-lg text-sm font-bold border bg-indigo-500 text-white border-indigo-500';

    try {
        const r = await fetch(`/api/afterschool/attendance/sheet?program_id=${currentAttProgramId}&session_no=${sessionNo}`);
        const d = await r.json();
        if (!d.success) return;

        document.getElementById('att-session-date').value = d.session_info.session_date || '';
        document.getElementById('att-session-topic').value = d.session_info.topic || '';

        const body = document.getElementById('att-body');
        body.innerHTML = d.students.map(s => {
            const st = s.status || 'present';
            return `<tr data-eid="${s.enrollment_id}">
                <td class="px-4 py-2 font-medium text-sm">${s.student_name}</td>
                <td class="px-4 py-2 text-center text-sm">${s.class_grade}-${s.class_no}-${s.class_num}</td>
                <td class="px-4 py-2 text-center"><input type="radio" name="att-${s.enrollment_id}" value="present" ${st==='present'?'checked':''}></td>
                <td class="px-4 py-2 text-center"><input type="radio" name="att-${s.enrollment_id}" value="absent" ${st==='absent'?'checked':''}></td>
                <td class="px-4 py-2 text-center"><input type="radio" name="att-${s.enrollment_id}" value="late" ${st==='late'?'checked':''}></td>
                <td class="px-4 py-2 text-center"><input type="radio" name="att-${s.enrollment_id}" value="excused" ${st==='excused'?'checked':''}></td>
                <td class="px-4 py-2"><input type="text" class="att-memo w-full px-2 py-1 border border-slate-200 rounded text-sm" value="${s.memo||''}"></td>
            </tr>`;
        }).join('');
    } catch(e) { console.error('출결 로드 오류:', e); }
}

async function saveAttendance() {
    const sessionDate = document.getElementById('att-session-date').value;
    if (!sessionDate) return alert('날짜를 선택해주세요.');

    const topic = document.getElementById('att-session-topic').value.trim();
    // 회차 정보 저장
    await fetch('/api/afterschool/session/save', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({program_id: currentAttProgramId, session_no: currentSessionNo, session_date: sessionDate, topic})});

    const rows = document.querySelectorAll('#att-body tr');
    const records = [];
    rows.forEach(row => {
        const eid = row.dataset.eid;
        const checked = row.querySelector(`input[name="att-${eid}"]:checked`);
        const memo = row.querySelector('.att-memo').value;
        records.push({enrollment_id: eid, status: checked ? checked.value : 'present', memo});
    });

    try {
        const r = await fetch('/api/afterschool/attendance/save', {method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({program_id: currentAttProgramId, session_no: currentSessionNo, session_date: sessionDate, records})});
        const d = await r.json(); alert(d.message);
    } catch(e) { alert('저장 중 오류'); }
}

async function printAttendanceFull() {
    try {
        const r = await fetch(`/api/afterschool/attendance/full?program_id=${currentAttProgramId}`);
        const d = await r.json();
        if (!d.success) return alert(d.message);

        const p = d.program;
        const symbolMap = {present:'O', absent:'X', late:'△', excused:'-', '':''};

        let html = `<div style="padding:20px;">
            <h2 style="text-align:center;font-size:20px;font-weight:bold;margin-bottom:5px;">${p.program_name} 출석부</h2>
            <p style="text-align:center;font-size:13px;color:#666;margin-bottom:15px;">강사: ${p.instructor_name||'-'} | ${p.day_of_week||''} ${p.time_slot||''} | ${p.start_date} ~ ${p.end_date}</p>
            <table style="width:100%;border-collapse:collapse;font-size:12px;">
                <thead><tr style="background:#f0f0f0;">
                    <th style="border:1px solid #999;padding:6px;">이름</th>
                    <th style="border:1px solid #999;padding:6px;">학년반번</th>`;
        d.sessions.forEach(s => {
            html += `<th style="border:1px solid #999;padding:4px;font-size:11px;">${s.session_no}회<br><span style="font-weight:normal;font-size:10px;">${s.session_date?s.session_date.substring(5):''}</span></th>`;
        });
        html += `</tr></thead><tbody>`;
        d.matrix.forEach(row => {
            html += `<tr><td style="border:1px solid #ccc;padding:4px;">${row.student_name}</td><td style="border:1px solid #ccc;padding:4px;text-align:center;">${row.class_info}</td>`;
            row.attendance.forEach(a => {
                html += `<td style="border:1px solid #ccc;padding:4px;text-align:center;">${symbolMap[a]||''}</td>`;
            });
            html += `</tr>`;
        });
        html += `</tbody></table>
            <p style="margin-top:10px;font-size:11px;color:#999;">O: 출석 | X: 결석 | △: 지각 | -: 사유</p>
        </div>`;

        const printArea = document.getElementById('att-print-area');
        printArea.innerHTML = html;
        printArea.classList.remove('hidden');
        document.getElementById('panel-afterschool').classList.add('print-target');
        setTimeout(() => {
            window.print();
            printArea.classList.add('hidden');
            document.getElementById('panel-afterschool').classList.remove('print-target');
        }, 200);
    } catch(e) { alert('출석부 조회 오류'); }
}
