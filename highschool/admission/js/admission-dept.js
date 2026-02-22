    // ═══════════════════════════════════════════════════════
    // 학과별 입시요강 탭 (admission_data 연동)
    // ═══════════════════════════════════════════════════════

    let deptFilters = { years: [], regions: [], dept_types: [], adm_codes: [], uni_names: [] };
    let deptCurrentPage = 1;
    let deptTotalItems = 0;
    let deptSearching = false;
    let deptInitSearchDone = false;   // 최초 검색 여부 (필터 선택 전 자동 검색 방지)

    // ── 탭 진입 시 초기화
    async function initDeptTab() {
        if (deptFilters.years.length > 0) return;  // 이미 로드됨
        const data = await apiCall('/api/dept/filters');
        if (!data || !data.success) return;
        deptFilters = data;
        renderDeptFilters(data);
    }

    function renderDeptFilters(data) {
        // 대학
        const uniSel = document.getElementById('dept-filter-uni');
        if (uniSel) {
            uniSel.innerHTML = '<option value="">대학 전체</option>';
            data.uni_names.forEach(v => uniSel.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`));
        }
        // 학과군
        const dtSel = document.getElementById('dept-filter-depttype');
        if (dtSel) {
            dtSel.innerHTML = '<option value="">학과군 전체</option>';
            data.dept_types.forEach(v => dtSel.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`));
        }
        // 학년도
        const yearSel = document.getElementById('dept-filter-year');
        if (yearSel) {
            yearSel.innerHTML = '<option value="">학년도 전체</option>';
            data.years.forEach(v => yearSel.insertAdjacentHTML('beforeend', `<option value="${v}">${v}학년도</option>`));
        }
        // 지역
        const regionSel = document.getElementById('dept-filter-region');
        if (regionSel) {
            regionSel.innerHTML = '<option value="">지역 전체</option>';
            data.regions.forEach(v => regionSel.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`));
        }
        // 전형코드
        const codeSel = document.getElementById('dept-filter-admcode');
        if (codeSel) {
            codeSel.innerHTML = '<option value="">전형 전체</option>';
            data.adm_codes.forEach(v => codeSel.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`));
        }
        // 카테고리 트리 버튼 렌더링
        renderCategoryTree(data.categories || []);
    }

    function renderCategoryTree(categories) {
        const container = document.getElementById('dept-category-tree');
        if (!container) return;

        const LARGE_COLORS = {
            'U01':'bg-orange-100 text-orange-700 border-orange-200',
            'U02':'bg-blue-100 text-blue-700 border-blue-200',
            'U03':'bg-green-100 text-green-700 border-green-200',
            'U04':'bg-indigo-100 text-indigo-700 border-indigo-200',
            'U05':'bg-teal-100 text-teal-700 border-teal-200',
            'U06':'bg-red-100 text-red-700 border-red-200',
            'U07':'bg-pink-100 text-pink-700 border-pink-200',
        };

        let html = '<div class="flex flex-wrap gap-1.5 mb-3">';
        html += '<button onclick="selectCatFilter(\'\')" id="cat-btn-all" class="cat-btn px-3 py-1.5 rounded-lg text-xs font-bold border transition bg-slate-700 text-white border-slate-700">전체</button>';
        categories.forEach(L => {
            const cls = LARGE_COLORS[L.cat_id] || 'bg-slate-100 text-slate-600 border-slate-200';
            html += `<button onclick="selectCatFilter('${L.cat_id}', this)" id="cat-btn-${L.cat_id}"
                class="cat-btn px-3 py-1.5 rounded-lg text-xs font-bold border transition ${cls} hover:opacity-80"
                data-level="1" data-children='${JSON.stringify(L.children.map(c=>({cat_id:c.cat_id,cat_name:c.cat_name,children:c.children})))}'
                >${L.cat_name}</button>`;
        });
        html += '</div>';
        // 중분류 영역 (동적)
        html += '<div id="dept-mid-category" class="hidden flex-wrap gap-1.5 mb-2"></div>';
        container.innerHTML = html;
    }

    let activeLargeCat = '';
    function selectCatFilter(catId, btn) {
        // 대분류 버튼 활성화
        document.querySelectorAll('.cat-btn').forEach(b => {
            b.classList.remove('bg-slate-700', 'text-white', 'border-slate-700', '!bg-indigo-600', '!text-white');
        });
        const midArea = document.getElementById('dept-mid-category');

        if (!catId) {
            // 전체
            activeLargeCat = '';
            document.getElementById('cat-btn-all').classList.add('bg-slate-700', 'text-white', 'border-slate-700');
            midArea.classList.add('hidden');
            midArea.innerHTML = '';
            document.getElementById('dept-cat-hidden').value = '';
            return;
        }

        activeLargeCat = catId;
        if (btn) btn.classList.add('bg-slate-700', 'text-white', 'border-slate-700');
        document.getElementById('dept-cat-hidden').value = catId;

        // 중분류 표시
        let children = [];
        try { children = JSON.parse(btn?.dataset.children || '[]'); } catch(e) {}

        if (children.length > 0) {
            midArea.classList.remove('hidden');
            midArea.style.display = 'flex';
            let mhtml = `<button onclick="selectMidCat('${catId}', null)" class="mid-btn px-2.5 py-1 rounded-lg text-xs font-medium border bg-slate-100 text-slate-600 border-slate-200 hover:bg-slate-200 transition">전체</button>`;
            children.forEach(M => {
                mhtml += `<button onclick="selectMidCat('${M.cat_id}', this)"
                    class="mid-btn px-2.5 py-1 rounded-lg text-xs font-medium border bg-white text-slate-600 border-slate-200 hover:bg-slate-100 transition"
                    data-children='${JSON.stringify(M.children)}'>${M.cat_name}</button>`;
            });
            midArea.innerHTML = mhtml;
        } else {
            midArea.classList.add('hidden');
            midArea.innerHTML = '';
        }
    }

    function selectMidCat(midId, btn) {
        document.querySelectorAll('.mid-btn').forEach(b => b.classList.remove('bg-slate-700', 'text-white', '!font-bold'));
        if (btn) btn.classList.add('bg-slate-700', 'text-white');
        document.getElementById('dept-cat-hidden').value = midId || activeLargeCat;
    }

    // ── 필터가 하나라도 선택되었는지 확인
    function hasDeptFilter() {
        const year     = document.getElementById('dept-filter-year')?.value;
        const admType  = document.getElementById('dept-filter-admtype')?.value;
        const region   = document.getElementById('dept-filter-region')?.value;
        const admCode  = document.getElementById('dept-filter-admcode')?.value;
        const deptType = document.getElementById('dept-filter-depttype')?.value;
        const uniName  = document.getElementById('dept-filter-uni')?.value;
        const catId    = document.getElementById('dept-cat-hidden')?.value;
        const q        = document.getElementById('dept-filter-q')?.value?.trim();
        return !!(year || admType || region || admCode || deptType || uniName || catId || q);
    }

    // ── 검색 실행
    async function searchDepts(page) {
        if (deptSearching) return;

        // 필터가 하나도 선택되지 않았으면 검색하지 않음
        if (!hasDeptFilter()) {
            document.getElementById('dept-result-area').innerHTML = `
                <div class="text-center py-16">
                    <div class="w-20 h-20 bg-gradient-to-br from-purple-100 to-purple-200 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-200/50">
                        <i class="fas fa-book text-3xl text-purple-500"></i>
                    </div>
                    <p class="text-slate-600 font-medium">필터를 선택하고 검색 버튼을 눌러주세요.</p>
                    <p class="text-slate-400 text-sm mt-1">대학·학과군·학년도·지역·계열·전형 등으로 원하는 학과를 찾을 수 있습니다.</p>
                </div>`;
            document.getElementById('dept-pagination').innerHTML = '';
            document.getElementById('dept-result-count').textContent = '';
            return;
        }

        deptSearching = true;
        deptCurrentPage = page || 1;

        const params = new URLSearchParams();
        const year     = document.getElementById('dept-filter-year')?.value;
        const admType  = document.getElementById('dept-filter-admtype')?.value;
        const region   = document.getElementById('dept-filter-region')?.value;
        const admCode  = document.getElementById('dept-filter-admcode')?.value;
        const deptType = document.getElementById('dept-filter-depttype')?.value;
        const uniName  = document.getElementById('dept-filter-uni')?.value;
        const catId    = document.getElementById('dept-cat-hidden')?.value;
        const q        = document.getElementById('dept-filter-q')?.value?.trim();

        if (year)     params.set('year', year);
        if (admType)  params.set('adm_type', admType);
        if (region)   params.set('region', region);
        if (admCode)  params.set('adm_code', admCode);
        if (deptType) params.set('dept_type', deptType);
        if (uniName)  params.set('uni_name', uniName);
        if (catId)    params.set('cat_id', catId);
        if (q)        params.set('q', q);
        params.set('page', deptCurrentPage);

        document.getElementById('dept-result-area').innerHTML =
            '<div class="text-center py-12 text-slate-400"><i class="fas fa-spinner fa-spin text-2xl mb-3"></i><div>검색 중...</div></div>';
        document.getElementById('dept-pagination').innerHTML = '';

        const data = await apiCall(`/api/dept/search?${params.toString()}`);
        deptSearching = false;

        if (!data || !data.success) {
            document.getElementById('dept-result-area').innerHTML =
                '<div class="text-center py-12 text-slate-400">검색에 실패했습니다.</div>';
            return;
        }
        deptTotalItems = data.total;
        deptInitSearchDone = true;
        renderDeptList(data.items, data.total);
        renderDeptPagination(data.total, data.page, data.per_page, params);
    }

    // ── 행 리스트 렌더링
    function renderDeptList(items, total) {
        const area = document.getElementById('dept-result-area');
        const countEl = document.getElementById('dept-result-count');
        if (countEl) countEl.textContent = `총 ${total.toLocaleString()}건`;

        if (!items || items.length === 0) {
            area.innerHTML = `
                <div class="text-center py-16">
                    <div class="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="fas fa-search text-3xl text-slate-400"></i>
                    </div>
                    <p class="text-slate-500 font-medium">검색 결과가 없습니다.</p>
                    <p class="text-slate-400 text-sm mt-1">필터를 조정하거나 다른 검색어를 입력해보세요.</p>
                </div>`;
            return;
        }

        const ADM_CODE_COLOR = {
            '학종일반': 'bg-blue-100 text-blue-700',
            '학종지균': 'bg-indigo-100 text-indigo-700',
            '학종기균': 'bg-violet-100 text-violet-700',
            '교과일반': 'bg-green-100 text-green-700',
            '교과지균': 'bg-teal-100 text-teal-700',
            '논술':     'bg-orange-100 text-orange-700',
            '실기':     'bg-pink-100 text-pink-700',
            '정시일반': 'bg-red-100 text-red-700',
        };

        // 테이블 헤더
        let html = `
        <div class="border border-slate-200 rounded-xl overflow-hidden">
            <div class="grid grid-cols-12 gap-0 bg-gradient-to-r from-slate-50 to-purple-50/30 text-xs font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <div class="col-span-3 px-4 py-3">대학</div>
                <div class="col-span-3 px-4 py-3">학과</div>
                <div class="col-span-2 px-4 py-3 text-center">전형</div>
                <div class="col-span-1 px-4 py-3 text-center">모집</div>
                <div class="col-span-1 px-4 py-3 text-center">70%컷</div>
                <div class="col-span-2 px-4 py-3 text-center">계열</div>
            </div>`;

        html += items.map(item => {
            const codeBadge = item.adm_code
                ? `<span class="inline-block px-1.5 py-0.5 rounded text-xs font-bold ${ADM_CODE_COLOR[item.adm_code] || 'bg-slate-100 text-slate-600'}">${item.adm_code}</span>`
                : '';
            const typeBadge = `<span class="inline-block px-1.5 py-0.5 rounded text-xs font-bold ${item.adm_type === '수시' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}">${item.adm_type || '-'}</span>`;
            const cut = item.cut_70 != null && item.cut_70 !== '' ? `<span class="text-rose-600 font-bold">${item.cut_70}</span>` : '<span class="text-slate-400">-</span>';
            const cnt = item.recruit_cnt != null && item.recruit_cnt > 0 ? `${item.recruit_cnt}명` : '<span class="text-slate-400">-</span>';
            const campus = item.campus_name ? `(${item.campus_name})` : '';

            return `
            <div class="dept-row-wrap">
                <div class="dept-row grid grid-cols-12 gap-0 items-center border-b border-slate-100 hover:bg-purple-50/40 transition-colors cursor-pointer text-sm"
                     onclick="toggleDeptDetail(${item.dept_id}, this)">
                    <div class="col-span-3 px-4 py-3">
                        <p class="font-medium text-slate-700 truncate">${item.uni_name || '-'}</p>
                        <p class="text-xs text-slate-400 truncate">${item.region || ''} ${campus}</p>
                    </div>
                    <div class="col-span-3 px-4 py-3">
                        <p class="font-bold text-slate-800 truncate">${item.dept_name || '-'}</p>
                    </div>
                    <div class="col-span-2 px-4 py-3 text-center">
                        <div class="flex items-center justify-center gap-1 flex-wrap">${typeBadge}${codeBadge}</div>
                    </div>
                    <div class="col-span-1 px-4 py-3 text-center font-medium text-slate-700">${cnt}</div>
                    <div class="col-span-1 px-4 py-3 text-center">${cut}</div>
                    <div class="col-span-2 px-4 py-3 text-center text-slate-500 text-xs">${item.dept_type || '-'}</div>
                </div>
                <div class="dept-detail-inline hidden" id="dept-inline-${item.dept_id}"></div>
            </div>`;
        }).join('');

        html += '</div>';
        area.innerHTML = html;
    }

    // ── 페이지네이션
    function renderDeptPagination(total, page, perPage, params) {
        const totalPages = Math.ceil(total / perPage);
        if (totalPages <= 1) return;
        const pg = document.getElementById('dept-pagination');
        if (!pg) return;

        let html = '<div class="flex items-center gap-1">';
        const mkBtn = (p, label, disabled, active) =>
            `<button onclick="searchDepts(${p})" class="px-3 py-1.5 rounded-lg text-sm font-medium transition
             ${active ? 'bg-pink-500 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-pink-50'}
             ${disabled ? 'opacity-40 cursor-not-allowed pointer-events-none' : ''}" ${disabled ? 'disabled' : ''}>${label}</button>`;

        html += mkBtn(page - 1, '‹', page <= 1, false);
        const start = Math.max(1, page - 2), end = Math.min(totalPages, page + 2);
        if (start > 1) { html += mkBtn(1, '1', false, false); if (start > 2) html += '<span class="px-1 text-slate-400">…</span>'; }
        for (let p = start; p <= end; p++) html += mkBtn(p, p, false, p === page);
        if (end < totalPages) { if (end < totalPages - 1) html += '<span class="px-1 text-slate-400">…</span>'; html += mkBtn(totalPages, totalPages, false, false); }
        html += mkBtn(page + 1, '›', page >= totalPages, false);
        html += '</div>';
        pg.innerHTML = html;
    }

    // ── 인라인 상세보기 토글
    let deptDetailOpenId = null;

    async function toggleDeptDetail(deptId, rowEl) {
        const inlineEl = document.getElementById(`dept-inline-${deptId}`);
        if (!inlineEl) return;

        // 이미 열려 있으면 닫기
        if (!inlineEl.classList.contains('hidden')) {
            inlineEl.classList.add('hidden');
            inlineEl.innerHTML = '';
            rowEl.classList.remove('bg-purple-50');
            deptDetailOpenId = null;
            return;
        }

        // 다른 열린 상세 닫기
        if (deptDetailOpenId && deptDetailOpenId !== deptId) {
            const prevEl = document.getElementById(`dept-inline-${deptDetailOpenId}`);
            if (prevEl) { prevEl.classList.add('hidden'); prevEl.innerHTML = ''; }
            document.querySelectorAll('.dept-row.bg-purple-50').forEach(r => r.classList.remove('bg-purple-50'));
        }

        deptDetailOpenId = deptId;
        rowEl.classList.add('bg-purple-50');
        inlineEl.classList.remove('hidden');
        inlineEl.innerHTML = '<div class="text-center py-8 text-slate-400"><i class="fas fa-spinner fa-spin text-xl"></i> 불러오는 중...</div>';

        const data = await apiCall(`/api/dept/${deptId}`);
        if (!data || !data.success) {
            inlineEl.innerHTML = '<div class="text-center py-4 text-red-500 text-sm">데이터를 불러오지 못했습니다.</div>';
            return;
        }
        renderDeptDetailInline(data.item, inlineEl);
    }

    function renderDeptDetailInline(item, container) {
        const ADM_CODE_COLOR = {
            '학종일반':'bg-blue-100 text-blue-700','학종지균':'bg-indigo-100 text-indigo-700',
            '학종기균':'bg-violet-100 text-violet-700','교과일반':'bg-green-100 text-green-700',
            '교과지균':'bg-teal-100 text-teal-700','논술':'bg-orange-100 text-orange-700',
            '실기':'bg-pink-100 text-pink-700','정시일반':'bg-red-100 text-red-700',
        };
        const typeBadge = `<span class="px-2 py-1 rounded text-xs font-bold ${item.adm_type === '수시' ? 'bg-pink-100 text-pink-700' : 'bg-blue-100 text-blue-700'}">${item.adm_type || '-'}</span>`;
        const codeBadge = item.adm_code
            ? `<span class="px-2 py-1 rounded text-xs font-bold ${ADM_CODE_COLOR[item.adm_code] || 'bg-slate-100 text-slate-600'}">${item.adm_code}</span>` : '';

        let recruitTable = '';
        if (item.recruit_detail) {
            try {
                const detail = typeof item.recruit_detail === 'string'
                    ? JSON.parse(item.recruit_detail) : item.recruit_detail;
                if (detail && Object.keys(detail).length > 0) {
                    const rows = Object.entries(detail).map(([k, v]) =>
                        `<tr><td class="py-1 pr-4 text-slate-600 text-sm">${k}</td><td class="py-1 font-semibold text-sm">${v}명</td></tr>`
                    ).join('');
                    recruitTable = `<table class="mt-2">${rows}</table>`;
                }
            } catch(e) {}
        }

        const recruitDisplay = item.recruit_cnt != null && item.recruit_cnt > 0
            ? item.recruit_cnt + '명' : '-';

        let admInfoHtml = '';
        if (item.adm_info) {
            try {
                const info = typeof item.adm_info === 'string' ? JSON.parse(item.adm_info) : item.adm_info;
                admInfoHtml = renderAdmInfo(info);
            } catch(e) {
                admInfoHtml = `<pre class="text-xs text-slate-600 whitespace-pre-wrap">${item.adm_info}</pre>`;
            }
        }

        container.innerHTML = `
            <div class="bg-gradient-to-r from-purple-50/50 to-slate-50 border-t-2 border-purple-200 p-5 animate-fadeIn">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            ${typeBadge}${codeBadge}
                            <span class="text-sm text-slate-500">${item.year || ''}학년도 · ${item.region || ''}</span>
                        </div>
                        <h3 class="text-lg font-bold text-slate-800">${item.dept_name || '-'}</h3>
                        <p class="text-slate-600 text-sm">${item.uni_name || '-'}${item.campus_name ? ' ' + item.campus_name : ''}</p>
                        <p class="text-slate-500 text-xs">${item.adm_name || ''}</p>
                    </div>
                    <button onclick="this.closest('.dept-row-wrap').querySelector('.dept-detail-inline').classList.add('hidden');this.closest('.dept-row-wrap').querySelector('.dept-detail-inline').innerHTML='';this.closest('.dept-row-wrap').querySelector('.dept-row').classList.remove('bg-purple-50');"
                            class="w-8 h-8 flex items-center justify-center rounded-full bg-white border border-slate-200 hover:bg-slate-100 text-slate-500 transition flex-shrink-0">
                        <i class="fas fa-times text-sm"></i>
                    </button>
                </div>

                <div class="grid grid-cols-3 gap-3 mb-4">
                    <div class="bg-white rounded-xl p-3 text-center border border-slate-100">
                        <p class="text-xs text-slate-500 mb-1">모집인원</p>
                        <p class="text-lg font-bold text-slate-800">${recruitDisplay}</p>
                        ${recruitTable}
                    </div>
                    <div class="bg-white rounded-xl p-3 text-center border border-slate-100">
                        <p class="text-xs text-slate-500 mb-1">70%컷 내신</p>
                        <p class="text-lg font-bold ${item.cut_70 != null && item.cut_70 !== '' ? 'text-rose-600' : 'text-slate-400'}">${item.cut_70 != null && item.cut_70 !== '' ? item.cut_70 + '등급' : '-'}</p>
                    </div>
                    <div class="bg-white rounded-xl p-3 text-center border border-slate-100">
                        <p class="text-xs text-slate-500 mb-1">계열</p>
                        <p class="text-base font-bold text-slate-700">${item.dept_type || '-'}</p>
                    </div>
                </div>

                ${item.selection_summary ? `
                <div class="bg-blue-50 rounded-xl p-4 mb-3">
                    <p class="text-xs font-bold text-blue-600 mb-1"><i class="fas fa-list-ol mr-1"></i>선발방법</p>
                    <p class="text-sm text-slate-700">${item.selection_summary}</p>
                </div>` : ''}

                ${item.min_criteria ? `
                <div class="bg-amber-50 rounded-xl p-4 mb-3">
                    <p class="text-xs font-bold text-amber-600 mb-1"><i class="fas fa-clipboard-check mr-1"></i>수능최저학력기준</p>
                    <p class="text-sm text-slate-700 whitespace-pre-line">${item.min_criteria}</p>
                </div>` : ''}

                ${admInfoHtml}

                ${item.url ? `
                <div class="mt-3">
                    <a href="${item.url}" target="_blank" rel="noopener"
                       class="inline-flex items-center gap-2 px-4 py-2 bg-purple-500 text-white rounded-lg text-sm font-medium hover:bg-purple-600 transition">
                        <i class="fas fa-external-link-alt"></i>입학 홈페이지 바로가기
                    </a>
                </div>` : ''}
            </div>`;
    }

    // 기존 모달 호환 (모달 사용하지 않지만 호출 방지)
    function showDeptDetail(deptId) { /* deprecated - use toggleDeptDetail */ }

    function renderAdmInfo(info) {
        if (!info || typeof info !== 'object') return '';
        const sections = Object.entries(info).map(([key, val]) => {
            let content = '';
            if (typeof val === 'string' || typeof val === 'number') {
                content = `<p class="text-sm text-slate-700">${val}</p>`;
            } else if (Array.isArray(val)) {
                content = val.map(v => `<li class="text-sm text-slate-700">${typeof v === 'object' ? JSON.stringify(v) : v}</li>`).join('');
                content = `<ul class="list-disc list-inside space-y-0.5">${content}</ul>`;
            } else if (typeof val === 'object') {
                content = Object.entries(val).map(([k2, v2]) =>
                    `<div class="flex gap-2 text-sm"><span class="text-slate-500 flex-shrink-0">${k2}:</span><span class="text-slate-700">${v2}</span></div>`
                ).join('');
            }
            return `<div class="mb-3">
                <p class="text-xs font-bold text-slate-500 uppercase tracking-wide mb-1">${key}</p>
                ${content}
            </div>`;
        }).join('');
        return sections ? `<div class="bg-white border border-slate-200 rounded-xl p-4 mt-4"><p class="text-xs font-bold text-slate-600 mb-3"><i class="fas fa-info-circle mr-1"></i>상세 입시 정보</p>${sections}</div>` : '';
    }

    function closeDeptDetail() {
        document.getElementById('dept-detail-modal').classList.add('hidden');
    }

    // 엔터키 검색
    function deptSearchOnEnter(e) {
        if (e.key === 'Enter') searchDepts(1);
    }

    // 필터 초기화
    function resetDeptFilters() {
        ['dept-filter-uni','dept-filter-depttype','dept-filter-year','dept-filter-admtype',
         'dept-filter-region','dept-filter-admcode'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.value = '';
        });
        const qEl = document.getElementById('dept-filter-q');
        if (qEl) qEl.value = '';
        const catHidden = document.getElementById('dept-cat-hidden');
        if (catHidden) catHidden.value = '';
        // 카테고리 버튼 초기화
        document.querySelectorAll('.cat-btn').forEach(b => {
            b.classList.remove('bg-slate-700', 'text-white', 'border-slate-700');
        });
        const allBtn = document.getElementById('cat-btn-all');
        if (allBtn) allBtn.classList.add('bg-slate-700', 'text-white', 'border-slate-700');
        const midArea = document.getElementById('dept-mid-category');
        if (midArea) { midArea.classList.add('hidden'); midArea.innerHTML = ''; }
        activeLargeCat = '';
        // 결과 초기화
        document.getElementById('dept-result-area').innerHTML = `
            <div class="text-center py-16">
                <div class="w-20 h-20 bg-gradient-to-br from-purple-100 to-purple-200 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-purple-200/50">
                    <i class="fas fa-book text-3xl text-purple-500"></i>
                </div>
                <p class="text-slate-600 font-medium">필터를 선택하고 검색 버튼을 눌러주세요.</p>
                <p class="text-slate-400 text-sm mt-1">대학·학과군·학년도·지역·계열·전형 등으로 원하는 학과를 찾을 수 있습니다.</p>
            </div>`;
        document.getElementById('dept-pagination').innerHTML = '';
        document.getElementById('dept-result-count').textContent = '';
    }
