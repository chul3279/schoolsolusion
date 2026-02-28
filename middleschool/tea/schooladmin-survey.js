// schooladmin-survey.js — 설문조사 탭 전체
async function loadSurveys() {
    try {
        const r = await fetch(`/api/survey/list?school_id=${currentUser.school_id}`);
        const d = await r.json();
        if (!d.success) return;

        const body = document.getElementById('survey-list-body');
        const empty = document.getElementById('survey-empty');

        if (!d.surveys || d.surveys.length === 0) {
            body.innerHTML = ''; empty.classList.remove('hidden'); return;
        }
        empty.classList.add('hidden');

        const roleMap = {student:'학생', parent:'학부모', both:'학생+학부모'};
        const statusMap = {draft:'임시저장', active:'진행중', closed:'종료'};

        body.innerHTML = d.surveys.map(s => `
            <tr class="hover:bg-slate-50">
                <td class="px-4 py-3 font-medium text-slate-800">${s.title}</td>
                <td class="px-4 py-3 text-center text-sm">${roleMap[s.target_role]||s.target_role} ${s.target_grades==='all'?'전체':s.target_grades+'학년'}</td>
                <td class="px-4 py-3 text-center"><span class="status-badge status-${s.status}">${statusMap[s.status]||s.status}</span></td>
                <td class="px-4 py-3 text-center text-sm">${s.question_count}문항</td>
                <td class="px-4 py-3 text-center text-sm font-bold">${s.response_count}명</td>
                <td class="px-4 py-3 text-center text-sm text-slate-500">${s.created_at}</td>
                <td class="px-4 py-3 text-center">
                    <div class="flex gap-1 justify-center flex-wrap">
                        ${s.status==='draft'?`<button onclick="editSurvey(${s.id})" class="px-2 py-1 bg-indigo-100 text-indigo-700 rounded text-xs font-bold hover:bg-indigo-200">수정</button><button onclick="startSurvey(${s.id})" class="px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-bold hover:bg-green-200">개시</button><button onclick="deleteSurvey(${s.id})" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold hover:bg-red-200">삭제</button>`:''}
                        ${s.status==='active'?`<button onclick="closeSurvey(${s.id})" class="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-bold hover:bg-orange-200">종료</button>`:''}
                        ${s.status!=='draft'?`<button onclick="loadSurveyStats(${s.id})" class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold hover:bg-blue-200">통계</button>`:''}
                        ${s.status==='closed'?`<button onclick="deleteSurvey(${s.id})" class="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold hover:bg-red-200">삭제</button>`:''}
                    </div>
                </td>
            </tr>
        `).join('');
    } catch(e) { console.error('설문 목록 오류:', e); }
}

function openSurveyEditor(id) {
    document.getElementById('survey-list-view').classList.add('hidden');
    document.getElementById('survey-stats-view').classList.add('hidden');
    document.getElementById('survey-editor-view').classList.remove('hidden');
    document.getElementById('sv-edit-id').value = id || '';
    document.getElementById('survey-editor-title').textContent = id ? '설문 수정' : '새 설문 만들기';
    if (!id) {
        document.getElementById('sv-title').value = '';
        document.getElementById('sv-description').value = '';
        document.getElementById('sv-target-role').value = 'student';
        document.getElementById('sv-target-grades').value = 'all';
        document.getElementById('sv-questions-container').innerHTML = '';
        surveyQuestionIndex = 0;
        addQuestion(); // 기본 1문항
    }
}

async function editSurvey(id) {
    openSurveyEditor(id);
    try {
        const r = await fetch(`/api/survey/detail?id=${id}`);
        const d = await r.json();
        if (!d.success) return alert(d.message);
        document.getElementById('sv-title').value = d.survey.title;
        document.getElementById('sv-description').value = d.survey.description;
        document.getElementById('sv-target-role').value = d.survey.target_role;
        document.getElementById('sv-target-grades').value = d.survey.target_grades;
        document.getElementById('sv-questions-container').innerHTML = '';
        surveyQuestionIndex = 0;
        d.questions.forEach(q => addQuestion(q));
    } catch(e) { alert('설문 불러오기 오류'); }
}

function closeSurveyEditor() {
    document.getElementById('survey-editor-view').classList.add('hidden');
    document.getElementById('survey-list-view').classList.remove('hidden');
    loadSurveys();
}

function addQuestion(data) {
    const idx = surveyQuestionIndex++;
    const container = document.getElementById('sv-questions-container');
    const div = document.createElement('div');
    div.className = 'q-card';
    div.id = `q-card-${idx}`;

    const qText = data ? data.question_text : '';
    const qType = data ? data.question_type : 'single';
    const qRequired = data ? data.required : true;
    let optionsStr = '';
    if (data && data.options) {
        if (Array.isArray(data.options)) optionsStr = data.options.join('\n');
        else if (data.options.max) optionsStr = data.options.max;
    }

    div.innerHTML = `
        <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-bold text-indigo-600">문항 ${idx+1}</span>
            <button onclick="removeQuestion(${idx})" class="text-red-400 hover:text-red-600 text-sm"><i class="fas fa-trash"></i></button>
        </div>
        <input type="text" class="w-full px-3 py-2 border border-slate-200 rounded-lg mb-3 font-medium q-text" placeholder="질문을 입력하세요" value="${qText}">
        <div class="flex gap-3 items-center mb-3">
            <select class="px-3 py-2 border border-slate-200 rounded-lg text-sm font-medium q-type" onchange="onQTypeChange(${idx})">
                <option value="single" ${qType==='single'?'selected':''}>단일 선택</option>
                <option value="multiple" ${qType==='multiple'?'selected':''}>복수 선택</option>
                <option value="text" ${qType==='text'?'selected':''}>주관식</option>
                <option value="rating" ${qType==='rating'?'selected':''}>척도(1~5)</option>
            </select>
            <label class="flex items-center gap-1 text-sm text-slate-500">
                <input type="checkbox" class="q-required" ${qRequired?'checked':''}> 필수
            </label>
        </div>
        <div class="q-options-area" id="q-opts-${idx}">
            ${(qType==='single'||qType==='multiple') ? `<textarea class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none q-options" rows="4" placeholder="보기를 한 줄에 하나씩 입력하세요\n예:\n매우 만족\n만족\n보통\n불만">${optionsStr}</textarea>` : ''}
            ${qType==='rating' ? `<p class="text-sm text-slate-400">1~5점 척도로 자동 생성됩니다.</p>` : ''}
            ${qType==='text' ? `<p class="text-sm text-slate-400">자유 서술형 응답입니다.</p>` : ''}
        </div>
    `;
    container.appendChild(div);
}

function removeQuestion(idx) {
    const el = document.getElementById(`q-card-${idx}`);
    if (el) el.remove();
}

function onQTypeChange(idx) {
    const card = document.getElementById(`q-card-${idx}`);
    const type = card.querySelector('.q-type').value;
    const area = document.getElementById(`q-opts-${idx}`);
    if (type === 'single' || type === 'multiple') {
        area.innerHTML = `<textarea class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none q-options" rows="4" placeholder="보기를 한 줄에 하나씩 입력"></textarea>`;
    } else if (type === 'rating') {
        area.innerHTML = `<p class="text-sm text-slate-400">1~5점 척도로 자동 생성됩니다.</p>`;
    } else {
        area.innerHTML = `<p class="text-sm text-slate-400">자유 서술형 응답입니다.</p>`;
    }
}

function collectQuestions() {
    const cards = document.querySelectorAll('.q-card');
    const questions = [];
    cards.forEach(card => {
        const text = card.querySelector('.q-text').value.trim();
        const type = card.querySelector('.q-type').value;
        const required = card.querySelector('.q-required').checked;
        if (!text) return;
        let options = null;
        if (type === 'single' || type === 'multiple') {
            const textarea = card.querySelector('.q-options');
            if (textarea) options = textarea.value.split('\n').map(s=>s.trim()).filter(s=>s);
        } else if (type === 'rating') {
            options = {min: 1, max: 5};
        }
        questions.push({ question_text: text, question_type: type, required, options });
    });
    return questions;
}

async function saveSurvey(andStart) {
    const title = document.getElementById('sv-title').value.trim();
    if (!title) return alert('제목을 입력해주세요.');
    const questions = collectQuestions();
    if (questions.length === 0) return alert('최소 1개 이상의 문항을 추가해주세요.');

    const payload = {
        school_id: currentUser.school_id,
        title,
        description: document.getElementById('sv-description').value.trim(),
        target_role: document.getElementById('sv-target-role').value,
        target_grades: document.getElementById('sv-target-grades').value,
        questions
    };

    const editId = document.getElementById('sv-edit-id').value;
    const url = editId ? '/api/survey/update' : '/api/survey/create';
    if (editId) payload.id = editId;

    try {
        const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
        const d = await r.json();
        if (!d.success) return alert(d.message);

        if (andStart) {
            const sid = editId || d.survey_id;
            await fetch('/api/survey/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id: sid})});
            alert('설문이 개시되었습니다.');
        } else {
            alert(d.message);
        }
        closeSurveyEditor();
    } catch(e) { alert('저장 중 오류가 발생했습니다.'); }
}

function saveSurveyAndStart() { saveSurvey(true); }

async function startSurvey(id) {
    if (!confirm('설문을 개시하시겠습니까? 개시 후에는 수정할 수 없습니다.')) return;
    try {
        const r = await fetch('/api/survey/start', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
        const d = await r.json(); alert(d.message); loadSurveys();
    } catch(e) { alert('개시 중 오류'); }
}

async function closeSurvey(id) {
    if (!confirm('설문을 종료하시겠습니까?')) return;
    try {
        const r = await fetch('/api/survey/close', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
        const d = await r.json(); alert(d.message); loadSurveys();
    } catch(e) { alert('종료 중 오류'); }
}

async function deleteSurvey(id) {
    if (!confirm('설문을 삭제하시겠습니까?')) return;
    try {
        const r = await fetch('/api/survey/delete', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})});
        const d = await r.json(); alert(d.message); loadSurveys();
    } catch(e) { alert('삭제 중 오류'); }
}

// ==========================================
// 설문 통계
// ==========================================
async function loadSurveyStats(id) {
    try {
        const r = await fetch(`/api/survey/stats?id=${id}`);
        const d = await r.json();
        if (!d.success) return alert(d.message);

        document.getElementById('survey-list-view').classList.add('hidden');
        document.getElementById('survey-editor-view').classList.add('hidden');
        document.getElementById('survey-stats-view').classList.remove('hidden');
        document.getElementById('stats-title').textContent = d.survey.title + ' - 통계';

        const rate = d.target_count > 0 ? Math.round(d.total_responses / d.target_count * 100) : 0;
        let html = `
            <div class="glass-card rounded-2xl p-6 mb-6 shadow-sm print-area">
                <div class="flex flex-wrap gap-6 items-center">
                    <div><span class="text-3xl font-black text-indigo-600">${d.total_responses}</span><span class="text-sm text-slate-500 ml-1">명 응답</span></div>
                    <div><span class="text-3xl font-black text-slate-400">${d.target_count}</span><span class="text-sm text-slate-500 ml-1">명 대상</span></div>
                    <div class="flex items-center gap-2">
                        <div class="w-32 h-3 bg-slate-200 rounded-full overflow-hidden"><div class="h-full bg-indigo-500 rounded-full" style="width:${rate}%"></div></div>
                        <span class="text-sm font-bold text-indigo-600">${rate}%</span>
                    </div>
                </div>
            </div>
        `;

        d.question_stats.forEach((q, qi) => {
            html += `<div class="glass-card rounded-2xl p-6 mb-4 shadow-sm print-area">`;
            html += `<h4 class="font-bold text-slate-800 mb-4">Q${q.question_order}. ${q.question_text} <span class="text-sm text-slate-400 font-normal">(${q.answer_count}명 응답)</span></h4>`;

            if ((q.question_type === 'single' || q.question_type === 'multiple') && q.options && q.option_counts) {
                const maxCount = Math.max(...q.option_counts, 1);
                q.options.forEach((opt, oi) => {
                    const cnt = q.option_counts[oi] || 0;
                    const pct = q.answer_count > 0 ? Math.round(cnt / q.answer_count * 100) : 0;
                    html += `<div class="flex items-center gap-3 mb-2">
                        <span class="text-sm w-28 truncate text-slate-600">${opt}</span>
                        <div class="flex-1 bg-slate-100 rounded h-6 overflow-hidden"><div class="bar-chart-bar" style="width:${maxCount>0?cnt/maxCount*100:0}%"></div></div>
                        <span class="text-sm font-bold w-16 text-right">${cnt}명 (${pct}%)</span>
                    </div>`;
                });
            } else if (q.question_type === 'rating') {
                html += `<div class="text-center mb-4"><span class="text-4xl font-black text-amber-500">${q.average}</span><span class="text-lg text-slate-400"> / 5</span></div>`;
                if (q.distribution) {
                    const maxD = Math.max(...q.distribution, 1);
                    for (let i = 0; i < q.distribution.length; i++) {
                        const cnt = q.distribution[i];
                        html += `<div class="flex items-center gap-3 mb-1">
                            <span class="text-sm w-12 text-slate-600">${i+1}점</span>
                            <div class="flex-1 bg-slate-100 rounded h-5 overflow-hidden"><div class="h-full rounded bg-amber-400" style="width:${maxD>0?cnt/maxD*100:0}%"></div></div>
                            <span class="text-sm font-bold w-12 text-right">${cnt}명</span>
                        </div>`;
                    }
                }
            } else if (q.question_type === 'text' && q.text_answers) {
                html += `<div class="max-h-48 overflow-y-auto border border-slate-200 rounded-lg p-3">`;
                q.text_answers.forEach(a => {
                    if (a) html += `<p class="text-sm text-slate-700 py-1 border-b border-slate-100 last:border-0">${a}</p>`;
                });
                html += `</div>`;
            }
            html += `</div>`;
        });

        document.getElementById('stats-content').innerHTML = html;
    } catch(e) { alert('통계 조회 오류'); console.error(e); }
}

function closeSurveyStats() {
    document.getElementById('survey-stats-view').classList.add('hidden');
    document.getElementById('survey-list-view').classList.remove('hidden');
}

function printSurveyStats() {
    document.getElementById('panel-survey').classList.add('print-target');
    setTimeout(() => { window.print(); document.getElementById('panel-survey').classList.remove('print-target'); }, 200);
}
