    // Phase 1+2: 이력 표시 & 공유/승인 시스템
    // ═══════════════════════════════════════════════════════

    const EXAM_TYPE_LABELS = {
        local_3: '교육청 3월', local_5: '교육청 5월', local_6: '교육청 6월',
        local_7: '교육청 7월', local_9: '교육청 9월', local_10: '교육청 10월',
        kice_6: '평가원 6월', kice_9: '평가원 9월'
    };
    function examTypeLabel(type, name) { return EXAM_TYPE_LABELS[type] || name || type; }

    function getShareBadge(status) {
        if (status === 'approved') return '<span class="badge-approved"><i class="fas fa-check-circle mr-1"></i>공유됨</span>';
        if (status === 'requested') return '<span class="badge-requested"><i class="fas fa-hourglass-half mr-1"></i>요청중</span>';
        return '<span class="badge-private"><i class="fas fa-lock mr-1"></i>비공개</span>';
    }

    function getShareActions(tableKey, item, role, userId) {
        const s = item.share_status;
        if (role === 'teacher') {
            if (s === 'requested' && item.input_by === userId)
                return `<button onclick="approveShare('${tableKey}',${item.id})" class="btn-xs btn-approve">승인</button>
                        <button onclick="rejectShare('${tableKey}',${item.id})" class="btn-xs btn-reject">거절</button>`;
            if (s === 'private' && item.input_by === userId)
                return `<button onclick="publishShare('${tableKey}',${item.id})" class="btn-xs btn-share-out">학생공유</button>`;
            return '';
        } else {
            if (s === 'private' && item.input_by !== userId)
                return `<button onclick="requestShare('${tableKey}',${item.id})" class="btn-xs btn-share-out">담임에게 공유 요청</button>`;
            return '';
        }
    }

    // ─── 생기부 이력 ───
    async function loadRecordHistory(studentId) {
        const role = currentUser.member_roll || 'student';
        const sid = studentId || (role !== 'teacher' ? currentUser.user_id : null);
        const params = sid ? `?student_id=${encodeURIComponent(sid)}` : '';
        const data = await apiCall(`/api/admission/record/list${params}`);
        renderRecordHistory(data?.records || []);
    }

    function renderRecordHistory(records) {
        const container = document.getElementById('record-history');
        if (!records.length) {
            container.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">업로드된 생기부가 없습니다.</p>';
            return;
        }
        const role = currentUser.member_roll || 'student';
        const userId = currentUser.user_id;
        container.innerHTML = records.map(r => {
            const canDelete = r.input_by === userId;
            const shareActions = getShareActions('record', r, role, userId);
            const dt = r.created_at ? new Date(r.created_at).toLocaleDateString('ko-KR') : '-';
            const size = r.file_size ? `${(r.file_size/1024/1024).toFixed(2)} MB` : '-';
            return `
            <div class="history-card" id="record-card-${r.id}">
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 bg-rose-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <i class="fas fa-file-pdf text-rose-500"></i>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex flex-wrap items-center gap-2 mb-1">
                            <span class="font-bold text-sm text-slate-700 truncate">${r.original_filename || '생기부.pdf'}</span>
                            ${getShareBadge(r.share_status)}
                            ${r.input_by_role === 'teacher' ? '<span class="badge-teacher">교사입력</span>' : ''}
                        </div>
                        <p class="text-xs text-slate-400">${dt} · ${size}${r.memo ? ' · ' + r.memo : ''}</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        ${shareActions}
                        ${canDelete ? `<button onclick="deleteRecord(${r.id})" class="btn-xs btn-danger-xs"><i class="fas fa-trash"></i></button>` : ''}
                    </div>
                </div>
            </div>`;
        }).join('');
    }

    async function deleteRecord(id) {
        if (!confirm('생기부를 삭제하시겠습니까?')) return;
        const data = await apiCall('/api/admission/record/delete', {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({id})
        });
        if (data?.success) document.getElementById(`record-card-${id}`)?.remove();
        else alert(data?.message || '삭제 실패');
    }

    // ─── 모의고사 이력 ───
    async function loadMockHistory(studentId) {
        const role = currentUser.member_roll || 'student';
        const sid = studentId || (role !== 'teacher' ? currentUser.user_id : null);
        const params = sid ? `?student_id=${encodeURIComponent(sid)}` : '';
        const data = await apiCall(`/api/admission/mock/list${params}`);
        renderMockHistory(data?.exams || []);
    }

    function renderMockHistory(exams) {
        const container = document.getElementById('mock-history');
        if (!exams.length) {
            container.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">저장된 모의고사 성적이 없습니다.</p>';
            return;
        }
        const role = currentUser.member_roll || 'student';
        const userId = currentUser.user_id;
        container.innerHTML = exams.map(e => {
            const label = examTypeLabel(e.exam_type, e.exam_name);
            const track = e.track ? ` · ${e.track}` : '';
            const grades = [
                e.kor_grade ? `국어 ${e.kor_grade}등급` : null,
                e.math_grade ? `수학 ${e.math_grade}등급` : null,
                e.eng_grade ? `영어 ${e.eng_grade}등급` : null
            ].filter(Boolean).join(' / ');
            const canDelete = e.input_by === userId;
            const shareActions = getShareActions('mock', e, role, userId);
            const dt = e.updated_at ? new Date(e.updated_at).toLocaleDateString('ko-KR') : '-';
            return `
            <div class="history-card" id="mock-card-${e.id}">
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <i class="fas fa-clipboard-list text-indigo-500"></i>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex flex-wrap items-center gap-2 mb-1">
                            <span class="font-bold text-sm text-slate-700">${e.exam_year}학년도 ${label}${track}</span>
                            ${getShareBadge(e.share_status)}
                            ${e.input_by_role === 'teacher' ? '<span class="badge-teacher">교사입력</span>' : ''}
                        </div>
                        <p class="text-xs text-slate-500">${grades || '성적 없음'}</p>
                        <p class="text-xs text-slate-400">${dt}</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        ${shareActions}
                        ${canDelete ? `<button onclick="deleteMock(${e.id})" class="btn-xs btn-danger-xs"><i class="fas fa-trash"></i></button>` : ''}
                    </div>
                </div>
            </div>`;
        }).join('');
    }

    async function deleteMock(id) {
        if (!confirm('모의고사 성적을 삭제하시겠습니까?')) return;
        const data = await apiCall('/api/admission/mock/delete', {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({id})
        });
        if (data?.success) document.getElementById(`mock-card-${id}`)?.remove();
        else alert(data?.message || '삭제 실패');
    }

    // ─── 수능 이력 ───
    async function loadCsatHistory(studentId) {
        const role = currentUser.member_roll || 'student';
        const sid = studentId || (role !== 'teacher' ? currentUser.user_id : null);
        const params = sid ? `?student_id=${encodeURIComponent(sid)}` : '';
        const data = await apiCall(`/api/admission/csat/list${params}`);
        renderCsatHistory(data?.scores || []);
    }

    function renderCsatHistory(scores) {
        const container = document.getElementById('csat-history');
        if (!scores.length) {
            container.innerHTML = '<p class="text-sm text-slate-400 text-center py-8">저장된 수능 성적이 없습니다.</p>';
            return;
        }
        const role = currentUser.member_roll || 'student';
        const userId = currentUser.user_id;
        container.innerHTML = scores.map(s => {
            const track = s.track ? ` · ${s.track}` : '';
            const grades = [
                s.kor_grade ? `국어 ${s.kor_grade}등급` : null,
                s.math_grade ? `수학 ${s.math_grade}등급` : null,
                s.eng_grade ? `영어 ${s.eng_grade}등급` : null
            ].filter(Boolean).join(' / ');
            const canDelete = s.input_by === userId;
            const shareActions = getShareActions('csat', s, role, userId);
            const dt = s.updated_at ? new Date(s.updated_at).toLocaleDateString('ko-KR') : '-';
            return `
            <div class="history-card" id="csat-card-${s.id}">
                <div class="flex items-start gap-3">
                    <div class="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <i class="fas fa-pen-fancy text-amber-500"></i>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex flex-wrap items-center gap-2 mb-1">
                            <span class="font-bold text-sm text-slate-700">${s.exam_year}학년도 수능${track}</span>
                            ${getShareBadge(s.share_status)}
                            ${s.input_by_role === 'teacher' ? '<span class="badge-teacher">교사입력</span>' : ''}
                        </div>
                        <p class="text-xs text-slate-500">${grades || '성적 없음'}</p>
                        <p class="text-xs text-slate-400">${dt}</p>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        ${shareActions}
                        ${canDelete ? `<button onclick="deleteCsat(${s.id})" class="btn-xs btn-danger-xs"><i class="fas fa-trash"></i></button>` : ''}
                    </div>
                </div>
            </div>`;
        }).join('');
    }

    async function deleteCsat(id) {
        if (!confirm('수능 성적을 삭제하시겠습니까?')) return;
        const data = await apiCall('/api/admission/csat/delete', {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({id})
        });
        if (data?.success) document.getElementById(`csat-card-${id}`)?.remove();
        else alert(data?.message || '삭제 실패');
    }

    // ─── 이력 전체 새로고침 ───
    function refreshHistory(studentId) {
        const sid = studentId || document.getElementById('mydata-student')?.value || null;
        loadRecordHistory(sid);
        loadMockHistory(sid);
        loadCsatHistory(sid);
    }

    // ─── 공유 요청 (학생·학부모) ───
    async function requestShare(tableKey, id) {
        const data = await apiCall('/api/admission/share/request', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({table: tableKey, id})
        });
        if (data?.success) { alert('담임 선생님께 공유 요청이 전송되었습니다.'); refreshHistory(); }
        else alert(data?.message || '요청 실패');
    }

    // ─── 공유 승인/거절 (교사) ───
    async function approveShare(tableKey, id) {
        const data = await apiCall('/api/admission/share/approve', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({table: tableKey, id})
        });
        if (data?.success) { refreshHistory(); loadPendingApprovals(); }
        else alert(data?.message || '승인 실패');
    }

    async function rejectShare(tableKey, id) {
        const data = await apiCall('/api/admission/share/reject', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({table: tableKey, id})
        });
        if (data?.success) { refreshHistory(); loadPendingApprovals(); }
        else alert(data?.message || '거절 실패');
    }

    // ─── 교사 → 학생 직접 공유 ───
    async function publishShare(tableKey, id) {
        const data = await apiCall('/api/admission/share/publish', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({table: tableKey, id})
        });
        if (data?.success) { alert('학생에게 공유되었습니다.'); refreshHistory(); }
        else alert(data?.message || '공유 실패');
    }

    // ─── 교사: 승인 대기 목록 ───
    async function loadPendingApprovals() {
        const role = currentUser.member_roll || 'student';
        if (role !== 'teacher') return;
        const data = await apiCall('/api/admission/share/pending');
        renderPendingApprovals(data?.pending || []);
    }

    function renderPendingApprovals(items) {
        const panel = document.getElementById('pending-approvals-panel');
        const list  = document.getElementById('pending-approvals-list');
        if (!panel || !list) return;
        if (!items.length) { panel.classList.add('hidden'); return; }
        panel.classList.remove('hidden');
        const labelMap = { record: '생기부', mock: '모의고사', csat: '수능' };
        list.innerHTML = items.map(item => {
            const label = item.label || labelMap[item.table] || item.table;
            const dt = item.share_requested_at ? new Date(item.share_requested_at).toLocaleDateString('ko-KR') : '-';
            return `
            <div class="flex items-center justify-between py-2 border-b border-amber-100 last:border-0">
                <div>
                    <span class="font-bold text-sm text-amber-900">${label}</span>
                    <span class="text-xs text-amber-600 ml-2">학생 ID: ${item.student_id} · ${dt}</span>
                </div>
                <div class="flex gap-2">
                    <button onclick="approveShare('${item.table}',${item.id})" class="btn-xs btn-approve">승인</button>
                    <button onclick="rejectShare('${item.table}',${item.id})" class="btn-xs btn-reject">거절</button>
                </div>
            </div>`;
        }).join('');
    }

    // ═══════════════════════════════════════════════════════
    // Phase 3: 교사 학생 선택 — 반 목록 API 연결
    // ═══════════════════════════════════════════════════════

    async function loadClassList(grade) {
        const data = await apiCall(`/api/admission/classes?grade=${grade}&school_id=${encodeURIComponent(currentUser.school_id || '')}`);
        const selClass = document.getElementById('mydata-class');
        selClass.innerHTML = '<option value="">반 선택</option>';
        const classes = data?.classes || [];
        if (classes.length) {
            classes.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c; opt.textContent = `${c}반`;
                selClass.appendChild(opt);
            });
        } else {
            for (let i = 1; i <= 18; i++) {
                const opt = document.createElement('option');
                opt.value = i; opt.textContent = `${i}반`;
                selClass.appendChild(opt);
            }
        }
    }

    // ═══════════════════════════════════════════════════════
    // Phase 4: 분석 탭
    // ═══════════════════════════════════════════════════════

    async function refreshAnalysisPrereq(studentId) {
        const role = currentUser.member_roll || 'student';
        const sid = studentId || (role !== 'teacher' ? currentUser.user_id : null);
        const params = sid ? `?student_id=${encodeURIComponent(sid)}` : '';

        const [recData, mockData, csatData] = await Promise.all([
            apiCall(`/api/admission/record/list${params}`),
            apiCall(`/api/admission/mock/list${params}`),
            apiCall(`/api/admission/csat/list${params}`)
        ]);

        const records = recData?.records || [];
        const exams   = mockData?.exams   || [];
        const scores  = csatData?.scores  || [];

        const earlyOk   = records.length > 0;
        const regularOk = exams.length > 0 || scores.length > 0;

        document.getElementById('early-prereq').innerHTML = earlyOk
            ? `<p class="text-sm text-green-700 bg-green-50 rounded-lg px-4 py-2"><i class="fas fa-check-circle mr-2"></i>생기부 ${records.length}건 등록됨 · 분석 가능</p>`
            : `<p class="text-sm text-amber-700 bg-amber-50 rounded-lg px-4 py-2"><i class="fas fa-exclamation-triangle mr-2"></i>생기부를 먼저 업로드하세요.</p>`;
        document.getElementById('btn-analyze-early').disabled = !earlyOk;

        document.getElementById('regular-prereq').innerHTML = regularOk
            ? `<p class="text-sm text-green-700 bg-green-50 rounded-lg px-4 py-2"><i class="fas fa-check-circle mr-2"></i>모의고사 ${exams.length}건, 수능 ${scores.length}건 · 분석 가능</p>`
            : `<p class="text-sm text-amber-700 bg-amber-50 rounded-lg px-4 py-2"><i class="fas fa-exclamation-triangle mr-2"></i>모의고사 또는 수능 성적을 먼저 입력하세요.</p>`;
        document.getElementById('btn-analyze-regular').disabled = !regularOk;

        const sel = document.getElementById('analysis-record-select');
        sel.innerHTML = '<option value="">분석할 생기부를 선택하세요</option>';
        records.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.id;
            opt.textContent = `${r.original_filename || '생기부.pdf'} (${r.created_at ? new Date(r.created_at).toLocaleDateString('ko-KR') : '-'})`;
            sel.appendChild(opt);
        });
        document.getElementById('analysis-prereq').innerHTML = records.length
            ? `<p class="text-sm text-green-700 bg-green-50 rounded-lg px-4 py-2"><i class="fas fa-check-circle mr-2"></i>생기부 ${records.length}건 등록됨</p>`
            : `<p class="text-sm text-amber-700 bg-amber-50 rounded-lg px-4 py-2"><i class="fas fa-exclamation-triangle mr-2"></i>생기부를 먼저 업로드하세요.</p>`;
        sel.onchange = () => { document.getElementById('btn-analyze-analysis').disabled = !sel.value; };
        document.getElementById('btn-analyze-analysis').disabled = true;
    }

    async function startAnalysis(type) {
        const POINTS = { early: 3000, regular: 3000, analysis: 10000 };
        const NAMES  = { early: '수시지원 가능대학', regular: '정시지원 가능대학', analysis: 'AI 생기부 종합 분석' };
        const ICONS  = { early: '수시 가능대학 분석 시작', regular: '정시 가능대학 분석 시작', analysis: 'AI 분석 시작' };
        if (!confirm(`${NAMES[type]} 분석을 시작합니다.\n포인트 ${POINTS[type].toLocaleString()}점이 차감됩니다.\n계속하시겠습니까?`)) return;

        const btn = document.getElementById(`btn-analyze-${type}`);
        const spinHtml = '<span style="display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,0.4);border-top-color:white;border-radius:50%;animation:spin 0.8s linear infinite;vertical-align:middle;margin-right:8px;"></span>';
        btn.disabled = true;
        btn.innerHTML = spinHtml + '분석 요청 중...';

        const resultEl = document.getElementById(`${type}-result`);
        resultEl.classList.add('hidden');

        const role = currentUser.member_roll || 'student';
        const studentId = role === 'teacher' ? document.getElementById('mydata-student')?.value : currentUser.user_id;
        const body = { student_id: studentId, school_id: currentUser.school_id || '' };
        if (type === 'analysis') body.record_id = document.getElementById('analysis-record-select').value;

        // ① 분석 시작 요청 → job_id 수신
        const startData = await apiCall(`/api/admission/analyze/${type}`, {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)
        });

        if (!startData?.success) {
            alert(startData?.message || '분석 시작에 실패했습니다.');
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-${type === 'analysis' ? 'robot' : 'search'} mr-2"></i>${ICONS[type]}`;
            return;
        }

        // ② job_id가 없으면 구버전 동기 응답 (result 바로 있음)
        if (!startData.job_id) {
            resultEl.innerHTML = `<div class="analysis-result">${startData.result || '분석 결과가 없습니다.'}</div>`;
            resultEl.classList.remove('hidden');
            btn.disabled = false;
            btn.innerHTML = `<i class="fas fa-${type === 'analysis' ? 'robot' : 'search'} mr-2"></i>${ICONS[type]}`;
            return;
        }

        // ③ 폴링 (최대 120초, 2초 간격)
        const jobId = startData.job_id;
        btn.innerHTML = spinHtml + '분석 중...';
        let elapsed = 0;
        const poll = async () => {
            if (elapsed >= 120) {
                alert('분석 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.');
                btn.disabled = false;
                btn.innerHTML = `<i class="fas fa-${type === 'analysis' ? 'robot' : 'search'} mr-2"></i>${ICONS[type]}`;
                return;
            }
            const statusData = await apiCall(`/api/admission/analyze/status/${jobId}`);
            if (statusData?.status === 'pending') {
                elapsed += 2;
                setTimeout(poll, 2000);
            } else if (statusData?.status === 'done') {
                resultEl.innerHTML = `<div class="analysis-result">${statusData.result || '분석 결과가 없습니다.'}</div>`;
                resultEl.classList.remove('hidden');
                btn.disabled = false;
                btn.innerHTML = `<i class="fas fa-${type === 'analysis' ? 'robot' : 'search'} mr-2"></i>${ICONS[type]}`;
            } else {
                alert(statusData?.message || '분석에 실패했습니다.');
                btn.disabled = false;
                btn.innerHTML = `<i class="fas fa-${type === 'analysis' ? 'robot' : 'search'} mr-2"></i>${ICONS[type]}`;
            }
        };
        setTimeout(poll, 2000);
    }

