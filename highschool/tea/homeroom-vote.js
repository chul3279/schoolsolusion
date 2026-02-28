// homeroom-vote.js — 학급투표 + switchTab 오버라이드 (반드시 마지막에 로드)
const origSwitchTab = switchTab;
switchTab = function(tabName) {
    origSwitchTab(tabName);
    if (tabName === 'attendance') {
        if (!document.getElementById('att-date').value) initAttendanceTab();
    }
    if (tabName === 'vote') {
        loadVotes();
    }
};

// ==================== 학급 투표 ====================
let voteList = [];
let currentVoteSubTab = 'list';

async function loadVotes() {
    if (!homeroomInfo) return;
    try {
        const res = await fetch(`/api/class-vote/list?class_grade=${homeroomInfo.class_grade}&class_no=${homeroomInfo.class_no}`);
        const data = await res.json();
        if (data.success) {
            voteList = data.votes || [];
            renderVoteList();
        }
    } catch(e) { console.error('투표 목록 오류:', e); }
}

function renderVoteList() {
    const container = document.getElementById('vote-list');
    if (voteList.length === 0) {
        container.innerHTML = '<div class="text-center py-12 text-slate-400"><i class="fas fa-vote-yea text-3xl mb-2 opacity-30"></i><p class="text-sm">투표가 없습니다. 새 투표를 만들어보세요.</p></div>';
        return;
    }
    container.innerHTML = voteList.map(v => {
        const badge = { draft: '<span class="px-2 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-bold">임시저장</span>',
            active: '<span class="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold animate-pulse">진행중</span>',
            closed: '<span class="px-2 py-1 bg-red-100 text-red-600 rounded-full text-xs font-bold">종료</span>' }[v.status] || '';
        const target = { student: '학생', parent: '학부모', both: '학생+학부모' }[v.target_role] || '';
        const typeLabel = v.vote_type === 'single' ? '단일선택' : '복수선택';
        let actionBtns = '';
        if (v.status === 'draft') {
            actionBtns = `<div class="flex gap-1 mt-2" onclick="event.stopPropagation()">
                <button onclick="startVote(${v.id})" class="px-3 py-1.5 bg-green-500 text-white rounded-lg text-xs font-bold hover:bg-green-600 transition"><i class="fas fa-play mr-1"></i>시작</button>
                <button onclick="editVote(${v.id})" class="px-3 py-1.5 bg-slate-400 text-white rounded-lg text-xs font-bold hover:bg-slate-500 transition"><i class="fas fa-edit mr-1"></i>수정</button>
                <button onclick="deleteVote(${v.id})" class="px-3 py-1.5 bg-red-400 text-white rounded-lg text-xs font-bold hover:bg-red-500 transition"><i class="fas fa-trash mr-1"></i>삭제</button>
            </div>`;
        } else if (v.status === 'active') {
            actionBtns = `<div class="flex gap-1 mt-2" onclick="event.stopPropagation()">
                <button onclick="viewVoteDetail(${v.id})" class="px-3 py-1.5 bg-violet-500 text-white rounded-lg text-xs font-bold hover:bg-violet-600 transition"><i class="fas fa-chart-bar mr-1"></i>결과</button>
                <button onclick="closeVoteAction(${v.id})" class="px-3 py-1.5 bg-red-500 text-white rounded-lg text-xs font-bold hover:bg-red-600 transition"><i class="fas fa-stop mr-1"></i>종료</button>
            </div>`;
        } else if (v.status === 'closed') {
            actionBtns = `<div class="flex gap-1 mt-2" onclick="event.stopPropagation()">
                <button onclick="viewVoteDetail(${v.id})" class="px-3 py-1.5 bg-violet-500 text-white rounded-lg text-xs font-bold hover:bg-violet-600 transition"><i class="fas fa-chart-bar mr-1"></i>결과</button>
                <button onclick="deleteVote(${v.id})" class="px-3 py-1.5 bg-red-400 text-white rounded-lg text-xs font-bold hover:bg-red-500 transition"><i class="fas fa-trash mr-1"></i>삭제</button>
            </div>`;
        }
        return `<div class="p-4 hover:bg-slate-50 cursor-pointer transition border-b border-slate-100" onclick="viewVoteDetail(${v.id})">
            <div class="flex items-center justify-between">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1 flex-wrap">${badge}<span class="text-xs text-slate-400">${target} | ${typeLabel}</span></div>
                    <h4 class="font-bold text-slate-800 truncate">${v.title}</h4>
                    <p class="text-xs text-slate-400 mt-1">${v.created_at} · 응답 ${v.response_count}명</p>
                    ${actionBtns}
                </div>
                <i class="fas fa-chevron-right text-slate-300 ml-3"></i>
            </div>
        </div>`;
    }).join('');
}

async function viewVoteDetail(voteId) {
    try {
        const res = await fetch(`/api/class-vote/detail?id=${voteId}`);
        const data = await res.json();
        if (!data.success) return alert(data.message);
        const v = data.vote;
        document.getElementById('vote-list-view').classList.add('hidden');
        document.getElementById('vote-detail-view').classList.remove('hidden');

        const target = { student: '학생', parent: '학부모', both: '학생+학부모' }[v.target_role] || '';
        const typeLabel = v.vote_type === 'single' ? '단일선택' : '복수선택';
        const badge = { draft: '<span class="px-2 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-bold">임시저장</span>',
            active: '<span class="px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-bold">진행중</span>',
            closed: '<span class="px-2 py-1 bg-red-100 text-red-600 rounded-full text-xs font-bold">종료</span>' }[v.status] || '';

        let actionBtns = '';
        if (v.status === 'draft') {
            actionBtns = `<button onclick="editVote(${v.id})" class="px-4 py-2 bg-slate-500 text-white rounded-lg text-sm font-bold hover:bg-slate-600 transition"><i class="fas fa-edit mr-1"></i>수정</button>
                <button onclick="startVote(${v.id})" class="px-4 py-2 bg-green-500 text-white rounded-lg text-sm font-bold hover:bg-green-600 transition"><i class="fas fa-play mr-1"></i>시작</button>
                <button onclick="deleteVote(${v.id})" class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600 transition"><i class="fas fa-trash mr-1"></i>삭제</button>`;
        } else if (v.status === 'active') {
            actionBtns = `<button onclick="closeVoteAction(${v.id})" class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600 transition"><i class="fas fa-stop mr-1"></i>종료</button>`;
        } else if (v.status === 'closed') {
            actionBtns = `<button onclick="deleteVote(${v.id})" class="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-bold hover:bg-red-600 transition"><i class="fas fa-trash mr-1"></i>삭제</button>`;
        }

        // 결과 바 차트
        const totalResp = v.total_respondents || 0;
        let optionsHtml = v.options.map(o => {
            const pct = totalResp > 0 ? Math.round(o.response_count / totalResp * 100) : 0;
            return `<div class="mb-3">
                <div class="flex justify-between items-center mb-1">
                    <span class="text-sm font-medium text-slate-700">${o.option_text}</span>
                    <span class="text-sm font-bold text-violet-600">${o.response_count}명 (${pct}%)</span>
                </div>
                <div class="w-full bg-slate-100 rounded-full h-6 overflow-hidden">
                    <div class="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-500 flex items-center justify-end pr-2" style="width: ${pct}%">
                        ${pct > 10 ? '<span class="text-xs text-white font-bold">' + pct + '%</span>' : ''}
                    </div>
                </div>
            </div>`;
        }).join('');

        const content = document.getElementById('vote-detail-content');
        content.innerHTML = `<div class="glass-card rounded-2xl shadow-lg overflow-hidden">
            <div class="bg-gradient-to-r from-violet-500 to-purple-600 p-5 text-white">
                <div class="flex items-center gap-2 mb-2">${badge}<span class="text-xs text-white/70">${target} | ${typeLabel}</span></div>
                <h3 class="font-bold text-xl">${v.title}</h3>
                ${v.description ? '<p class="text-sm text-white/80 mt-1">' + v.description + '</p>' : ''}
            </div>
            <div class="p-5">
                <div class="flex items-center justify-between mb-4">
                    <p class="text-sm text-slate-500">총 응답: <strong class="text-violet-600">${totalResp}명</strong></p>
                    <div class="flex gap-2">${actionBtns}</div>
                </div>
                ${optionsHtml}
            </div>
        </div>`;
    } catch(e) { console.error('투표 상세 오류:', e); }
}

function backToVoteList() {
    document.getElementById('vote-detail-view').classList.add('hidden');
    document.getElementById('vote-list-view').classList.remove('hidden');
}

function openVoteCreateModal(editData) {
    document.getElementById('vote-edit-id').value = editData ? editData.id : '';
    document.getElementById('vote-title').value = editData ? editData.title : '';
    document.getElementById('vote-description').value = editData ? editData.description : '';
    document.getElementById('vote-type').value = editData ? editData.vote_type : 'single';
    document.getElementById('vote-target').value = editData ? editData.target_role : 'student';
    document.getElementById('vote-modal-title').innerHTML = editData
        ? '<i class="fas fa-vote-yea mr-2"></i>투표 수정'
        : '<i class="fas fa-vote-yea mr-2"></i>투표 만들기';

    const list = document.getElementById('vote-options-list');
    list.innerHTML = '';
    if (editData && editData.options) {
        editData.options.forEach(o => addVoteOption(o.option_text));
    } else {
        addVoteOption(); addVoteOption();
    }
    document.getElementById('vote-modal').classList.remove('hidden');
}

function closeVoteModal() {
    document.getElementById('vote-modal').classList.add('hidden');
}

function addVoteOption(text) {
    const list = document.getElementById('vote-options-list');
    const idx = list.children.length + 1;
    const div = document.createElement('div');
    div.className = 'flex items-center gap-2';
    div.innerHTML = `<input type="text" value="${text || ''}" placeholder="선택지 ${idx}" class="flex-1 px-4 py-2.5 border-2 border-slate-200 rounded-xl focus:border-violet-500 outline-none text-sm vote-option-input">
        <button onclick="this.parentElement.remove()" class="w-9 h-9 bg-red-100 hover:bg-red-200 text-red-500 rounded-lg flex items-center justify-center transition"><i class="fas fa-times"></i></button>`;
    list.appendChild(div);
}

async function submitVote(startImmediately = false) {
    const editId = document.getElementById('vote-edit-id').value;
    const title = document.getElementById('vote-title').value.trim();
    const description = document.getElementById('vote-description').value.trim();
    const vote_type = document.getElementById('vote-type').value;
    const target_role = document.getElementById('vote-target').value;
    const optInputs = document.querySelectorAll('.vote-option-input');
    const options = [];
    optInputs.forEach(inp => { if (inp.value.trim()) options.push({ text: inp.value.trim() }); });

    if (!title) return alert('투표 제목을 입력해주세요.');
    if (options.length < 2) return alert('선택지는 최소 2개 이상 필요합니다.');

    if (startImmediately && !confirm('투표를 생성하고 바로 시작하시겠습니까?\n시작 후에는 수정할 수 없습니다.')) return;

    const body = { title, description, vote_type, target_role, options,
        class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no };
    const url = editId ? '/api/class-vote/update' : '/api/class-vote/create';
    if (editId) body.vote_id = editId;

    try {
        const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await res.json();
        if (data.success) {
            closeVoteModal();
            if (startImmediately) {
                const voteId = data.vote_id || (editId ? parseInt(editId) : null);
                if (voteId) {
                    await fetch('/api/class-vote/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ vote_id: voteId }) });
                }
            }
            loadVotes();
            backToVoteList();
        } else { alert(data.message); }
    } catch(e) { alert('저장 중 오류가 발생했습니다.'); }
}

async function editVote(voteId) {
    try {
        const res = await fetch(`/api/class-vote/detail?id=${voteId}`);
        const data = await res.json();
        if (data.success) openVoteCreateModal(data.vote);
    } catch(e) {}
}

async function startVote(voteId) {
    if (!confirm('투표를 시작하시겠습니까? 시작 후에는 수정할 수 없습니다.')) return;
    try {
        const res = await fetch('/api/class-vote/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ vote_id: voteId }) });
        const data = await res.json();
        if (data.success) { loadVotes(); viewVoteDetail(voteId); }
        else alert(data.message);
    } catch(e) { alert('오류가 발생했습니다.'); }
}

async function closeVoteAction(voteId) {
    if (!confirm('투표를 종료하시겠습니까?')) return;
    try {
        const res = await fetch('/api/class-vote/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ vote_id: voteId }) });
        const data = await res.json();
        if (data.success) { loadVotes(); viewVoteDetail(voteId); }
        else alert(data.message);
    } catch(e) { alert('오류가 발생했습니다.'); }
}

async function deleteVote(voteId) {
    if (!confirm('투표를 삭제하시겠습니까?')) return;
    try {
        const res = await fetch('/api/class-vote/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ vote_id: voteId }) });
        const data = await res.json();
        if (data.success) { loadVotes(); backToVoteList(); }
        else alert(data.message);
    } catch(e) { alert('오류가 발생했습니다.'); }
}

// 모바일 사이드바 토글
