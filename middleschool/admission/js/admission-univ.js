    async function loadYears() {
        setStatus('학년도 목록을 불러오는 중...', true);
        const data = await apiCall('/api/admission/years');
        const sel = document.getElementById('sel-year');
        sel.innerHTML = '<option value="">학년도 선택</option>';

        if (!data || !data.years || data.years.length === 0) {
            document.getElementById('empty-state').classList.add('hidden');
            document.getElementById('no-data-state').classList.remove('hidden');
            setStatus('입시요강 데이터가 없습니다. 데이터서버 연결을 확인해주세요.');
            return;
        }

        data.years.forEach(year => {
            const opt = document.createElement('option');
            opt.value = year;
            opt.textContent = `${year}학년도`;
            sel.appendChild(opt);
        });
        setStatus(`${data.years.length}개 학년도 데이터가 준비되어 있습니다.`);
    }

    async function loadYearData(year) {
        setStatus(`${year}학년도 대학 목록을 불러오는 중...`, true);
        const data = await apiCall(`/api/admission/list/${year}`);
        if (!data || !data.success) {
            setStatus('데이터 로드에 실패했습니다.');
            return null;
        }
        yearData = data;
        setStatus(`${year}학년도: ${data.total}개 대학, ${data.regions.length}개 지역`);
        return data;
    }

    // ═══════════════════════════════════════════
    // 캐스케이딩 셀렉터 이벤트
    // ═══════════════════════════════════════════
    async function onYearChange() {
        const year = document.getElementById('sel-year').value;
        resetSelect('sel-region', '지역 선택');
        resetSelect('sel-univ', '지역을 먼저 선택');
        resetTypeButtons();
        hideResult();

        if (!year) {
            document.getElementById('sel-region').disabled = true;
            document.getElementById('sel-univ').disabled = true;
            return;
        }

        const data = await loadYearData(year);
        if (!data) return;

        const selRegion = document.getElementById('sel-region');
        selRegion.innerHTML = '<option value="">지역 선택</option>';
        selRegion.innerHTML += `<option value="전체">전체 (${data.total})</option>`;
        data.regions.forEach(region => {
            const count = data.universities.filter(u => u.region === region).length;
            const opt = document.createElement('option');
            opt.value = region;
            opt.textContent = `${region} (${count})`;
            selRegion.appendChild(opt);
        });
        selRegion.disabled = false;
    }

    function onRegionChange() {
        const region = document.getElementById('sel-region').value;
        resetSelect('sel-univ', '대학교 선택');
        resetTypeButtons();
        hideResult();

        if (!region || !yearData) {
            document.getElementById('sel-univ').disabled = true;
            return;
        }

        const filtered = region === '전체'
            ? yearData.universities
            : yearData.universities.filter(u => u.region === region);

        const selUniv = document.getElementById('sel-univ');
        selUniv.innerHTML = `<option value="">대학교 선택 (${filtered.length}개)</option>`;
        filtered.forEach(univ => {
            const opt = document.createElement('option');
            opt.value = univ.name;
            const types = Object.keys(univ.types).join('/');
            opt.textContent = `${univ.name} [${types}]`;
            selUniv.appendChild(opt);
        });
        selUniv.disabled = false;
    }

    function onUnivChange() {
        const univName = document.getElementById('sel-univ').value;
        resetTypeButtons();
        hideResult();
        if (!univName || !yearData) return;

        const univ = yearData.universities.find(u => u.name === univName);
        if (!univ) return;

        const types = Object.keys(univ.types);
        const btnSusi = document.getElementById('btn-susi');
        const btnJeongsi = document.getElementById('btn-jeongsi');

        if (types.includes('수시')) {
            btnSusi.disabled = false;
            btnSusi.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        if (types.includes('정시')) {
            btnJeongsi.disabled = false;
            btnJeongsi.classList.remove('opacity-50', 'cursor-not-allowed');
        }

        if (types.length === 1) {
            onTypeSelect(types[0]);
        }

        setStatus(`${univ.name} - ${types.join(', ')} 모집요강 확인 가능`);
    }

    async function onTypeSelect(type) {
        selectedType = type;

        document.getElementById('btn-susi').classList.remove('active');
        document.getElementById('btn-jeongsi').classList.remove('active');
        document.getElementById(type === '수시' ? 'btn-susi' : 'btn-jeongsi').classList.add('active');

        const year = document.getElementById('sel-year').value;
        const univName = document.getElementById('sel-univ').value;
        if (!year || !univName || !yearData) return;

        const univ = yearData.universities.find(u => u.name === univName);
        if (!univ || !univ.types[type]) return;

        const fileInfo = univ.types[type];
        const filename = fileInfo;
        const typeCode = type === '수시' ? 'susi' : 'jeongsi';

        document.getElementById('empty-state').classList.add('hidden');
        document.getElementById('no-data-state').classList.add('hidden');
        document.getElementById('result-area').classList.remove('hidden');

        document.getElementById('result-title').textContent = `${univName} ${year}학년도 ${type}모집요강`;
        document.getElementById('result-subtitle').textContent = `${univ.region} | ${filename}`;

        currentPdfUrl = `${API_BASE}/api/admission/pdf/${year}/${typeCode}/${encodeURIComponent(filename)}`;
        const pdfViewer = document.getElementById('pdf-viewer');
        const pdfLoading = document.getElementById('pdf-loading');

        pdfLoading.classList.remove('hidden');
        pdfViewer.src = currentPdfUrl;
        pdfViewer.onload = () => pdfLoading.classList.add('hidden');

        setStatus(`${univName} ${type}모집요강 로드 완료`);

        const summaryArea = document.getElementById('summary-area');
        summaryArea.classList.add('hidden');

        const summaryData = await apiCall(`/api/admission/summary/${year}/${typeCode}/${encodeURIComponent(univName)}`);
        if (summaryData && summaryData.summary) {
            const html = typeof marked !== 'undefined'
                ? marked.parse(summaryData.summary)
                : '<pre>' + summaryData.summary + '</pre>';
            document.getElementById('summary-content').innerHTML = html;
            summaryArea.classList.remove('hidden');
        }
    }

    // ═══════════════════════════════════════════
    // 교육과정 선택
    // ═══════════════════════════════════════════
    function onCurriculumSelect(curriculum) {
        currentCurriculum = curriculum;

        // 버튼 활성화 표시
        const btn2015 = document.getElementById('cur-2015');
        const btn2022 = document.getElementById('cur-2022');
        btn2015.classList.remove('active-2015', 'active-2022');
        btn2022.classList.remove('active-2015', 'active-2022');
        if (curriculum === '2015') {
            btn2015.classList.add('active-2015');
        } else {
            btn2022.classList.add('active-2022');
        }

        // 모의고사 폼 전환
        document.getElementById('mock-form-2015').style.display = curriculum === '2015' ? 'block' : 'none';
        document.getElementById('mock-form-2022').style.display = curriculum === '2022' ? 'block' : 'none';
        // 수능 폼 전환
        document.getElementById('csat-form-2015').style.display = curriculum === '2015' ? 'block' : 'none';
        document.getElementById('csat-form-2022').style.display = curriculum === '2022' ? 'block' : 'none';
        // 계열 토글: 2022(고1·2)는 불필요
        document.getElementById('mock-track-selector').style.display = curriculum === '2015' ? '' : 'none';
        document.getElementById('csat-track-selector').style.display = curriculum === '2015' ? '' : 'none';

        // 평가원 버튼: 2022에서는 숨김 (평가원 모의고사 없음)
        const kiceBtn = document.getElementById('mock-org-kice');
        if (curriculum === '2022') {
            kiceBtn.style.display = 'none';
            // 평가원 선택 상태였으면 초기화
            if (selectedMockOrg === 'kice') {
                selectedMockOrg = null;
                selectedMockExamType = null;
                ['local', 'kice', 'private'].forEach(o => document.getElementById(`mock-org-${o}`).classList.remove('active'));
                document.getElementById('mock-month-selector').style.display = 'none';
            }
        } else {
            kiceBtn.style.display = '';
        }

        // 주관기관 선택 상태이면 월 버튼 재렌더 (교육과정 변경에 따라 월 목록이 달라짐)
        if (selectedMockOrg && selectedMockOrg !== 'private') {
            renderMockMonthBtns();
        }

        // 2022 선택 시 계열 초기화
        if (curriculum === '2022') {
            selectedMockTrack = null;
            selectedCsatTrack = null;
        }
    }

    // ═══════════════════════════════════════════
    // 입시자료 등록 - 서브탭
    // ═══════════════════════════════════════════
    function switchSubTab(name) {
        document.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.sub-tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById('subtab-' + name).classList.add('active');
        document.getElementById('subcontent-' + name).classList.add('active');
    }

