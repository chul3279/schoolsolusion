// homeroom-counsel.js — 공지사항, 상담일정, 상담일지, 생활기록부, 공통활동, 파일업로드
async function loadNotices() {
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        const response = await fetch(`/api/homeroom/notice/list?${params.toString()}`);
        const data = await response.json();
        const container = document.getElementById('notice-list');
        if (data.success && data.notices?.length > 0) {
            container.innerHTML = data.notices.map(n => `
                <div class="p-4 hover:bg-slate-50 transition">
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <p class="font-bold text-slate-800">${n.title}</p>
                            <p class="text-sm text-slate-600 mt-1 whitespace-pre-wrap">${n.content}</p>
                            <p class="text-xs text-slate-400 mt-2">${n.created_at} · ${n.teacher_name}</p>
                        </div>
                        <div class="flex gap-1 flex-shrink-0">
                            <button onclick="openEditNotice(${n.id}, '${n.title.replace(/'/g,"\\'")}', \`${n.content.replace(/`/g,'\\`')}\`)" class="text-amber-400 hover:text-amber-600 p-2" title="수정"><i class="fas fa-pen"></i></button>
                            <button onclick="deleteNotice(${n.id})" class="text-red-400 hover:text-red-600 p-2" title="삭제"><i class="fas fa-trash"></i></button>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center py-12 text-slate-400">공지사항이 없습니다.</div>';
        }
    } catch (error) { console.error('공지 로드 오류:', error); }
}

let editingNoticeId = null;

function openNoticeModal() {
    editingNoticeId = null;
    document.getElementById('notice-title').value = '';
    document.getElementById('notice-content').value = '';
    document.getElementById('notice-modal-title').textContent = '학급 공지 등록';
    document.getElementById('notice-submit-btn').textContent = '등록하기';
    document.getElementById('notice-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function openEditNotice(id, title, content) {
    editingNoticeId = id;
    document.getElementById('notice-title').value = title;
    document.getElementById('notice-content').value = content;
    document.getElementById('notice-modal-title').textContent = '학급 공지 수정';
    document.getElementById('notice-submit-btn').textContent = '수정하기';
    document.getElementById('notice-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeNoticeModal() {
    editingNoticeId = null;
    document.getElementById('notice-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

async function submitNotice() {
    const title = document.getElementById('notice-title').value.trim();
    const content = document.getElementById('notice-content').value.trim();
    if (!title || !content) return alert('제목과 내용을 입력해주세요.');
    try {
        let url, body;
        if (editingNoticeId) {
            url = '/api/homeroom/notice/update';
            body = { id: editingNoticeId, title, content };
        } else {
            url = '/api/homeroom/notice/create';
            body = {
                school_id: currentUser.school_id, member_school: currentUser.member_school,
                class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no,
                teacher_id: currentUser.member_id, teacher_name: currentUser.member_name,
                title, content
            };
        }
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (data.success) { alert(data.message); closeNoticeModal(); loadNotices(); }
        else alert(data.message);
    } catch (error) { alert('처리 중 오류가 발생했습니다.'); }
}

async function deleteNotice(id) {
    if (!confirm('공지를 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/homeroom/notice/delete', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, teacher_id: currentUser.member_id })
        });
        const data = await response.json();
        if (data.success) loadNotices(); else alert(data.message);
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

// ==================== 상담 일정 ====================
async function loadSchedules() {
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        const response = await fetch(`/api/homeroom/counsel-schedule/list?${params.toString()}`);
        const data = await response.json();
        const container = document.getElementById('schedule-list');
        if (data.success && data.schedules?.length > 0) {
            container.innerHTML = data.schedules.map(s => `
                <div class="p-4 hover:bg-slate-50 transition">
                    <div class="flex justify-between items-center">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                                <span class="font-bold text-blue-600">${s.class_num || '-'}</span>
                            </div>
                            <div>
                                <p class="font-bold text-slate-800">${s.student_name}</p>
                                <p class="text-sm text-slate-500">${s.counsel_date} · ${s.counsel_type}</p>
                                ${s.memo ? `<p class="text-xs text-slate-400 mt-1">${s.memo}</p>` : ''}
                            </div>
                        </div>
                        <div class="flex items-center gap-2">
                            <button onclick="toggleScheduleStatus(${s.id}, '${s.status}')" class="px-2 py-1 ${s.status === 'scheduled' ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200' : 'bg-green-100 text-green-700 hover:bg-green-200'} rounded-full text-xs font-bold transition cursor-pointer" title="클릭하여 상태 변경">
                                ${s.status === 'scheduled' ? '예정' : '완료'} <i class="fas fa-exchange-alt ml-1 text-[10px]"></i>
                            </button>
                            <button onclick="deleteSchedule(${s.id})" class="text-red-400 hover:text-red-600 p-2"><i class="fas fa-trash"></i></button>
                        </div>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center py-12 text-slate-400">상담 일정이 없습니다.</div>';
        }
    } catch (error) { console.error('상담 일정 로드 오류:', error); }
}

function openScheduleModal() {
    document.getElementById('schedule-student').value = '';
    document.getElementById('schedule-date').value = '';
    document.getElementById('schedule-memo').value = '';
    document.getElementById('schedule-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeScheduleModal() {
    document.getElementById('schedule-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

async function submitSchedule() {
    const sel = document.getElementById('schedule-student');
    const studentId = sel.value;
    const studentName = sel.options[sel.selectedIndex]?.dataset?.name;
    const classNum = sel.options[sel.selectedIndex]?.dataset?.num;
    const counselDate = document.getElementById('schedule-date').value;
    const counselType = document.getElementById('schedule-type').value;
    const memo = document.getElementById('schedule-memo').value.trim();
    if (!studentId || !counselDate) return alert('학생과 상담 일시를 선택해주세요.');
    try {
        const response = await fetch('/api/homeroom/counsel-schedule/create', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: currentUser.school_id, member_school: currentUser.member_school,
                class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no,
                teacher_id: currentUser.member_id, teacher_name: currentUser.member_name,
                student_id: studentId, student_name: studentName, class_num: classNum,
                counsel_date: counselDate, counsel_type: counselType, memo
            })
        });
        const data = await response.json();
        if (data.success) { alert(data.message); closeScheduleModal(); loadSchedules(); }
        else alert(data.message);
    } catch (error) { alert('등록 중 오류가 발생했습니다.'); }
}

async function deleteSchedule(id) {
    if (!confirm('상담 일정을 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/homeroom/counsel-schedule/delete', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        const data = await response.json();
        if (data.success) loadSchedules(); else alert(data.message);
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

// ==================== 상담 일지 ====================
async function loadLogs() {
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        const response = await fetch(`/api/homeroom/counsel-log/list?${params.toString()}`);
        const data = await response.json();
        const container = document.getElementById('log-list');
        if (data.success && data.logs?.length > 0) {
            container.innerHTML = data.logs.map(l => `
                <div class="p-4 hover:bg-slate-50 transition">
                    <div class="flex justify-between items-start">
                        <div class="flex gap-4">
                            <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center flex-shrink-0">
                                <span class="font-bold text-purple-600">${l.class_num || '-'}</span>
                            </div>
                            <div>
                                <p class="font-bold text-slate-800">${l.student_name} <span class="text-xs font-normal text-slate-400">${l.counsel_date}</span></p>
                                <span class="inline-block px-2 py-0.5 bg-purple-100 text-purple-600 rounded-full text-xs font-bold mb-1">${l.counsel_type}</span>
                                <p class="text-sm text-slate-600 whitespace-pre-wrap">${l.content}</p>
                                ${l.result ? `<p class="text-xs text-slate-500 mt-1"><b>결과:</b> ${l.result}</p>` : ''}
                                ${l.next_plan ? `<p class="text-xs text-blue-500 mt-1"><b>향후 계획:</b> ${l.next_plan}</p>` : ''}
                            </div>
                        </div>
                        <button onclick="deleteLog(${l.id})" class="text-red-400 hover:text-red-600 p-2 flex-shrink-0"><i class="fas fa-trash"></i></button>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div class="text-center py-12 text-slate-400">상담 일지가 없습니다.</div>';
        }
    } catch (error) { console.error('상담 일지 로드 오류:', error); }
}

function openLogModal() {
    document.getElementById('log-student').value = '';
    document.getElementById('log-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('log-content').value = '';
    document.getElementById('log-result').value = '';
    document.getElementById('log-plan').value = '';
    document.getElementById('log-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeLogModal() {
    document.getElementById('log-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

async function submitLog() {
    const sel = document.getElementById('log-student');
    const studentId = sel.value;
    const studentName = sel.options[sel.selectedIndex]?.dataset?.name;
    const classNum = sel.options[sel.selectedIndex]?.dataset?.num;
    const counselDate = document.getElementById('log-date').value;
    const counselType = document.getElementById('log-type').value;
    const content = document.getElementById('log-content').value.trim();
    const result = document.getElementById('log-result').value.trim();
    const nextPlan = document.getElementById('log-plan').value.trim();
    if (!studentId || !counselDate || !content) return alert('학생, 일자, 상담 내용을 입력해주세요.');
    try {
        const response = await fetch('/api/homeroom/counsel-log/create', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: currentUser.school_id, member_school: currentUser.member_school,
                class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no,
                teacher_id: currentUser.member_id, teacher_name: currentUser.member_name,
                student_id: studentId, student_name: studentName, class_num: classNum,
                counsel_date: counselDate, counsel_type: counselType,
                content, result, next_plan: nextPlan
            })
        });
        const data = await response.json();
        if (data.success) { alert(data.message); closeLogModal(); loadLogs(); }
        else alert(data.message);
    } catch (error) { alert('등록 중 오류가 발생했습니다.'); }
}

async function deleteLog(id) {
    if (!confirm('상담 일지를 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/homeroom/counsel-log/delete', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        const data = await response.json();
        if (data.success) loadLogs(); else alert(data.message);
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

// ==================== 생활기록부 ====================
async function loadStudentRecord() {
    const studentId = document.getElementById('record-student').value;
    const recordYear = document.getElementById('record-year').value;
    const recordSemester = document.getElementById('record-semester').value;
    if (!studentId) { document.getElementById('record-form').classList.add('hidden'); document.getElementById('record-placeholder').classList.remove('hidden'); return; }
    document.getElementById('record-form').classList.remove('hidden');
    document.getElementById('record-placeholder').classList.add('hidden');
    document.getElementById('record-content').value = '';
    document.getElementById('record-file-list').innerHTML = '';
    try {
        const params = getSchoolParams();
        params.append('student_id', studentId);
        params.append('record_year', recordYear);
        params.append('record_semester', recordSemester);
        const response = await fetch(`/api/homeroom/student-record/get?${params.toString()}`);
        const data = await response.json();
        if (data.success && data.record) {
            document.getElementById('record-content').value = data.record.behavior_record || '';
        }
        loadRecordFiles();
    } catch (error) { console.error('기초자료 로드 오류:', error); }
}

async function saveStudentRecord() {
    const sel = document.getElementById('record-student');
    const studentId = sel.value;
    const studentName = sel.options[sel.selectedIndex]?.dataset?.name;
    const classNum = sel.options[sel.selectedIndex]?.dataset?.num;
    const recordYear = document.getElementById('record-year').value;
    const recordSemester = document.getElementById('record-semester').value;
    const content = document.getElementById('record-content').value.trim();
    if (!studentId) return alert('학생을 선택해주세요.');
    try {
        const response = await fetch('/api/homeroom/student-record/save', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: currentUser.school_id, member_school: currentUser.member_school,
                class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no,
                class_num: classNum, student_id: studentId, student_name: studentName,
                record_year: recordYear, record_semester: recordSemester, behavior_record: content
            })
        });
        const data = await response.json();
        alert(data.message);
    } catch (error) { alert('저장 중 오류가 발생했습니다.'); }
}

async function toggleScheduleStatus(id, currentStatus) {
    const newStatus = currentStatus === 'scheduled' ? 'completed' : 'scheduled';
    const statusText = newStatus === 'completed' ? '완료' : '예정';
    if (!confirm(`상담 일정을 "${statusText}" 상태로 변경하시겠습니까?`)) return;
    try {
        const response = await fetch('/api/homeroom/counsel-schedule/update-status', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, status: newStatus })
        });
        const data = await response.json();
        if (data.success) loadSchedules(); else alert(data.message);
    } catch (error) { alert('상태 변경 중 오류가 발생했습니다.'); }
}

// ==================== 학급 공통사항 ====================
async function loadCommonActivities() {
    const recordYear = document.getElementById('record-year')?.value;
    const recordSemester = document.getElementById('record-semester')?.value;
    const container = document.getElementById('common-activity-list');
    if (!container) return;

    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        if (recordYear) params.append('record_year', recordYear);
        if (recordSemester) params.append('record_semester', recordSemester);

        const response = await fetch('/api/homeroom/common-activity/list?' + params.toString());
        const data = await response.json();

        if (data.success && data.activities?.length > 0) {
            container.innerHTML = data.activities.map(a => {
                const typeColors = {
                    '수학여행': 'bg-blue-100 text-blue-700',
                    '체험학습': 'bg-green-100 text-green-700',
                    '봉사활동': 'bg-pink-100 text-pink-700',
                    '현장학습': 'bg-orange-100 text-orange-700',
                    '진로체험': 'bg-purple-100 text-purple-700',
                    '학교행사': 'bg-yellow-100 text-yellow-700',
                };
                const colorClass = typeColors[a.activity_type] || 'bg-slate-100 text-slate-700';
                return `
                    <div class="p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition">
                        <div class="flex justify-between items-start">
                            <div class="flex-1">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="px-2 py-0.5 ${colorClass} rounded-full text-xs font-bold">${a.activity_type}</span>
                                    <span class="text-xs text-slate-400">${a.activity_date || ''}</span>
                                </div>
                                <p class="font-bold text-slate-800">${a.title}</p>
                                ${a.content ? `<p class="text-sm text-slate-600 mt-1 whitespace-pre-wrap">${a.content}</p>` : ''}
                            </div>
                            <button onclick="deleteCommon(${a.id})" class="text-red-400 hover:text-red-600 p-2 flex-shrink-0"><i class="fas fa-trash"></i></button>
                        </div>
                    </div>`;
            }).join('');
        } else {
            container.innerHTML = '<div class="text-center py-8 text-slate-400">등록된 공통사항이 없습니다.</div>';
        }
    } catch (error) { console.error('공통사항 로드 오류:', error); }
}

function openCommonModal() {
    document.getElementById('common-type').value = '수학여행';
    document.getElementById('common-date').value = '';
    document.getElementById('common-title').value = '';
    document.getElementById('common-content').value = '';
    document.getElementById('common-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeCommonModal() {
    document.getElementById('common-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

async function submitCommon() {
    const activityType = document.getElementById('common-type').value;
    const activityDate = document.getElementById('common-date').value;
    const title = document.getElementById('common-title').value.trim();
    const commonContent = document.getElementById('common-content').value.trim();
    const recordYear = document.getElementById('record-year').value;
    const recordSemester = document.getElementById('record-semester').value;

    if (!title) return alert('제목을 입력해주세요.');

    try {
        const response = await fetch('/api/homeroom/common-activity/create', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: currentUser.school_id, member_school: currentUser.member_school,
                class_grade: homeroomInfo.class_grade, class_no: homeroomInfo.class_no,
                record_year: recordYear, record_semester: recordSemester,
                activity_type: activityType, activity_date: activityDate,
                title, content: commonContent,
                teacher_id: currentUser.member_id, teacher_name: currentUser.member_name
            })
        });
        const data = await response.json();
        if (data.success) { alert(data.message); closeCommonModal(); loadCommonActivities(); }
        else alert(data.message);
    } catch (error) { alert('등록 중 오류가 발생했습니다.'); }
}

async function deleteCommon(id) {
    if (!confirm('공통사항을 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/homeroom/common-activity/delete', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        const data = await response.json();
        if (data.success) loadCommonActivities(); else alert(data.message);
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

// ==================== 파일 업로드 관리 ====================
function setupRecordDragDrop() {
    const dropZone = document.getElementById('record-drop-zone');
    if (!dropZone) return;
    ['dragenter', 'dragover'].forEach(e => {
        dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.add('border-teal-400', 'bg-teal-50'); });
    });
    ['dragleave', 'drop'].forEach(e => {
        dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.remove('border-teal-400', 'bg-teal-50'); });
    });
    dropZone.addEventListener('drop', (ev) => {
        const files = ev.dataTransfer.files;
        if (files.length > 0) uploadRecordFiles(files);
    });
}

function handleRecordFiles(input) {
    if (input.files.length > 0) uploadRecordFiles(input.files);
}

async function uploadRecordFiles(files) {
    const studentId = document.getElementById('record-student').value;
    const recordYear = document.getElementById('record-year').value;
    const recordSemester = document.getElementById('record-semester').value;
    if (!studentId) return alert('학생을 먼저 선택해주세요.');
    const sel = document.getElementById('record-student');
    const studentName = sel.options[sel.selectedIndex]?.dataset?.name || '';
    const progress = document.getElementById('record-upload-progress');
    progress.classList.remove('hidden');
    let successCount = 0, failCount = 0;
    for (const file of files) {
        if (file.size > 10 * 1024 * 1024) { alert(file.name + ': 10MB 초과'); failCount++; continue; }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('school_id', currentUser.school_id || '');
        formData.append('member_school', currentUser.member_school || '');
        formData.append('student_id', studentId);
        formData.append('student_name', studentName);
        formData.append('record_year', recordYear);
        formData.append('record_semester', recordSemester);
        formData.append('uploaded_by', currentUser.member_id);
        formData.append('uploaded_name', currentUser.member_name);
        try {
            const response = await fetch('/api/homeroom/counsel-file/upload', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.success) successCount++; else { alert(data.message); failCount++; }
        } catch (error) { console.error('업로드 오류:', error); failCount++; }
    }
    progress.classList.add('hidden');
    document.getElementById('record-file-input').value = '';
    if (successCount > 0) loadRecordFiles();
    if (failCount > 0) alert('일부 파일 업로드 실패');
}

async function loadRecordFiles() {
    const studentId = document.getElementById('record-student').value;
    const recordYear = document.getElementById('record-year').value;
    const recordSemester = document.getElementById('record-semester').value;
    const container = document.getElementById('record-file-list');
    if (!studentId) { container.innerHTML = ''; return; }
    try {
        const params = getSchoolParams();
        params.append('student_id', studentId);
        params.append('record_year', recordYear);
        params.append('record_semester', recordSemester);
        const response = await fetch('/api/homeroom/counsel-file/list?' + params.toString());
        const data = await response.json();
        if (data.success && data.files?.length > 0) {
            container.innerHTML = data.files.map(f => {
                const icon = getFileIcon(f.original_name);
                const size = formatFileSize(f.file_size);
                return `<div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl hover:bg-slate-100 transition">
                    <div class="flex items-center gap-3 min-w-0 flex-1">
                        <div class="w-10 h-10 ${icon.bg} rounded-lg flex items-center justify-center flex-shrink-0">
                            <i class="${icon.icon} ${icon.color}"></i>
                        </div>
                        <div class="min-w-0 flex-1">
                            <p class="text-sm font-bold text-slate-700 truncate">${f.original_name}</p>
                            <p class="text-xs text-slate-400">${size} · ${f.created_at} · ${f.uploaded_name}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-1 flex-shrink-0 ml-2">
                        <a href="/api/homeroom/counsel-file/download/${f.id}" class="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition" title="다운로드"><i class="fas fa-download"></i></a>
                        <button onclick="deleteRecordFile(${f.id}, '${f.original_name}')" class="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition" title="삭제"><i class="fas fa-trash"></i></button>
                    </div>
                </div>`;
            }).join('');
        } else { container.innerHTML = ''; }
    } catch (error) { console.error('파일 목록 로드 오류:', error); }
}

async function deleteRecordFile(fileId, fileName) {
    if (!confirm(fileName + ' 파일을 삭제하시겠습니까?')) return;
    try {
        const response = await fetch('/api/homeroom/counsel-file/delete', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: fileId })
        });
        const data = await response.json();
        if (data.success) loadRecordFiles(); else alert(data.message);
    } catch (error) { alert('삭제 중 오류가 발생했습니다.'); }
}

