// schooladmin-letter.js — 가정통신문 + 관리 탭
let currentConsentLetterId = null;

async function loadTeacherLetters() {
    const container = document.getElementById('letter-list-teacher');
    try {
        const params = getSchoolParams();
        const response = await fetch(`/api/letter/list?${params.toString()}`);
        const data = await response.json();

        if (data.success && data.letters?.length > 0) {
            container.innerHTML = data.letters.map(l => {
                let badges = '';
                if (l.require_consent) badges += '<span class="px-2 py-0.5 bg-rose-100 text-rose-600 rounded-full text-xs font-medium">동의필요</span> ';
                if (l.has_file) badges += '<span class="px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded-full text-xs"><i class="fas fa-paperclip"></i></span>';
                return `
                <div class="p-4 hover:bg-slate-50 transition">
                    <div class="flex items-start gap-3">
                        <span class="w-8 h-8 bg-rose-100 text-rose-600 rounded-lg flex items-center justify-center flex-shrink-0"><i class="fas fa-envelope text-sm"></i></span>
                        <div class="flex-1 min-w-0">
                            <p class="font-bold text-slate-800 truncate">${l.title}</p>
                            <p class="text-xs text-slate-500 mt-1">${l.created_at} ${badges}</p>
                        </div>
                        <div class="flex gap-1 flex-shrink-0">
                            ${l.require_consent ? `<button onclick="openConsentStatus(${l.id})" class="px-3 py-1.5 bg-purple-100 text-purple-600 rounded-lg text-xs font-medium hover:bg-purple-200 transition"><i class="fas fa-poll mr-1"></i>현황</button>` : ''}
                            <button onclick="deleteLetter(${l.id})" class="px-2 py-1.5 bg-red-50 text-red-400 rounded-lg text-xs hover:bg-red-100 transition"><i class="fas fa-trash"></i></button>
                        </div>
                    </div>
                </div>`;
            }).join('');
        } else {
            container.innerHTML = '<div class="text-center py-8 text-slate-300"><i class="fas fa-envelope-open text-2xl mb-2"></i><p class="text-xs">가정통신문이 없습니다.</p></div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="text-center py-8 text-slate-300"><p class="text-xs">목록을 불러올 수 없습니다.</p></div>';
    }
}

function openLetterCreateModal() {
    document.getElementById('letter-title').value = '';
    document.getElementById('letter-content').value = '';
    document.getElementById('letter-require-consent').checked = false;
    document.getElementById('letter-consent-deadline').classList.add('hidden');
    document.getElementById('letter-consent-deadline').value = '';
    document.getElementById('letter-file').value = '';
    document.getElementById('letter-create-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeLetterCreateModal() {
    document.getElementById('letter-create-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function toggleConsentDeadline() {
    const dl = document.getElementById('letter-consent-deadline');
    dl.classList.toggle('hidden', !document.getElementById('letter-require-consent').checked);
}

async function submitLetter() {
    const title = document.getElementById('letter-title').value.trim();
    const content = document.getElementById('letter-content').value.trim();
    if (!title || !content) { alert('제목과 내용을 입력해주세요.'); return; }

    const formData = new FormData();
    formData.append('school_id', currentUser.school_id);
    formData.append('title', title);
    formData.append('content', content);
    formData.append('require_consent', document.getElementById('letter-require-consent').checked ? '1' : '0');
    formData.append('consent_deadline', document.getElementById('letter-consent-deadline').value || '');

    const fileInput = document.getElementById('letter-file');
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }

    try {
        const response = await fetch('/api/letter/create', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            closeLetterCreateModal();
            loadTeacherLetters();
        } else {
            alert(data.message);
        }
    } catch (error) { alert('발송 중 오류가 발생했습니다.'); }
}

async function deleteLetter(id) {
    if (!confirm('이 가정통신문을 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/letter/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id})
        });
        const data = await response.json();
        if (data.success) { loadTeacherLetters(); } else { alert(data.message); }
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

async function openConsentStatus(letterId) {
    currentConsentLetterId = letterId;
    try {
        const response = await fetch(`/api/letter/consent-status?id=${letterId}`);
        const data = await response.json();
        if (!data.success) { alert(data.message); return; }

        const s = data.summary;
        document.getElementById('consent-summary').textContent = `동의 ${s.agreed} / 미동의 ${s.disagreed} / 미응답 ${s.no_reply} (총 ${s.total}명)`;

        const statusColors = {agreed:'emerald', disagreed:'red', no_reply:'slate'};
        const statusNames = {agreed:'동의', disagreed:'미동의', no_reply:'미응답'};

        document.getElementById('consent-list').innerHTML = data.consent_list.map(c => `
            <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                <div>
                    <span class="text-sm font-bold text-slate-800">${c.class_num || '-'}번 ${c.student_name}</span>
                    <span class="text-xs text-slate-500 ml-2">(${c.parent_name})</span>
                </div>
                <div class="flex items-center gap-2">
                    ${c.reply_memo ? `<span class="text-xs text-slate-400">${c.reply_memo}</span>` : ''}
                    <span class="px-2 py-0.5 bg-${statusColors[c.consent_status]}-100 text-${statusColors[c.consent_status]}-600 rounded-full text-xs font-medium">${statusNames[c.consent_status]}</span>
                </div>
            </div>
        `).join('');

        document.getElementById('consent-status-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    } catch (error) { alert('동의현황을 불러올 수 없습니다.'); }
}

function closeConsentModal() {
    document.getElementById('consent-status-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function exportConsentCSV() {
    if (currentConsentLetterId) {
        window.open(`/api/letter/export?id=${currentConsentLetterId}`, '_blank');
    }
}

// ==========================================
// 관리 탭
// ==========================================
function initAdminTab() {
    document.getElementById('admin-detail-area').classList.add('hidden');
}

const PERMISSION_ITEMS = [
    { key: 'admin',        icon: 'fa-cogs',              color: 'violet', label: '관리' },
    { key: 'meal',         icon: 'fa-utensils',          color: 'pink',   label: '급식 등록' },
    { key: 'afterschool',  icon: 'fa-book-reader',       color: 'emerald',label: '방과후 프로그램 관리' },
    { key: 'timetable',    icon: 'fa-edit',              color: 'cyan',   label: '시간표 작성 및 반편성' },
    { key: 'exchange',     icon: 'fa-exchange-alt',      color: 'blue',   label: '교환요청 목록' },
    { key: 'letter',       icon: 'fa-envelope-open-text',color: 'orange', label: '가정통신문 관리' },
    { key: 'exam',         icon: 'fa-file-alt',          color: 'red',    label: '시험시간표 및 감독' }
];

function openAdminSection(section) {
    const titles = {
        'school-info': '학교 정보',
        'teacher-manage': '교사 관리',
        'student-manage': '학생 관리',
        'parent-manage': '학부모 관리',
        'permission-manage': '권한 관리'
    };
    document.getElementById('admin-detail-title').textContent = titles[section] || section;
    document.getElementById('admin-detail-area').classList.remove('hidden');

    const content = document.getElementById('admin-detail-content');

    if (section === 'permission-manage') {
        renderPermissionManage(content);
        return;
    }
    content.innerHTML = '<div class="text-center py-12 text-slate-400"><i class="fas fa-tools text-4xl mb-3"></i><p class="font-medium">준비 중입니다</p></div>';
}

async function renderPermissionManage(container) {
    container.innerHTML = '<div class="text-center py-8"><i class="fas fa-spinner fa-spin text-2xl text-slate-300"></i></div>';

    let teachers = [];
    try {
        const res = await fetch('/api/afterschool/teachers');
        const data = await res.json();
        if (data.success) teachers = data.teachers || [];
    } catch(e) {}

    let html = `
        <div class="mb-5">
            <p class="text-sm text-slate-500"><i class="fas fa-info-circle mr-1 text-blue-400"></i>각 교사에게 행정 업무 권한을 부여합니다. 권한이 부여된 교사만 해당 기능에 접근할 수 있습니다.</p>
        </div>
        <div class="overflow-x-auto rounded-xl border border-slate-200">
            <table class="w-full text-sm">
                <thead>
                    <tr class="bg-gradient-to-r from-slate-50 to-slate-100">
                        <th class="text-left p-3 font-bold text-slate-700 sticky left-0 bg-slate-50 min-w-[120px] border-b border-slate-200">교사명</th>`;
    PERMISSION_ITEMS.forEach(p => {
        html += `<th class="text-center p-3 font-bold text-slate-700 min-w-[90px] border-b border-slate-200">
            <div class="flex flex-col items-center gap-1">
                <i class="fas ${p.icon} text-${p.color}-500 text-base"></i>
                <span class="text-xs leading-tight">${p.label}</span>
            </div>
        </th>`;
    });
    html += `</tr></thead><tbody>`;

    if (teachers.length === 0) {
        html += '<tr><td colspan="' + (PERMISSION_ITEMS.length + 1) + '" class="text-center py-8 text-slate-400">교사 목록을 불러올 수 없습니다.</td></tr>';
    } else {
        teachers.forEach((t, idx) => {
            const name = typeof t === 'string' ? t : (t.name || t.member_name || '');
            if (!name) return;
            const bg = idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50';
            html += '<tr class="' + bg + ' border-b border-slate-100 hover:bg-blue-50/40 transition">';
            html += '<td class="p-3 font-medium text-slate-800 sticky left-0 ' + bg + '">' + name + '</td>';
            PERMISSION_ITEMS.forEach(p => {
                html += '<td class="text-center p-3"><input type="checkbox" class="w-4 h-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer perm-check" data-teacher="' + name + '" data-perm="' + p.key + '"></td>';
            });
            html += '</tr>';
        });
    }

    html += '</tbody></table></div>';
    html += `<div class="flex justify-end mt-4">
        <button onclick="alert('준비 중입니다.')" class="px-5 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl font-bold text-sm shadow hover:opacity-90 transition">
            <i class="fas fa-save mr-1"></i>저장
        </button>
    </div>`;

    container.innerHTML = html;
}

function closeAdminDetail() {
    document.getElementById('admin-detail-area').classList.add('hidden');
}
