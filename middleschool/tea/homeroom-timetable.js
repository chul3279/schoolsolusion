// homeroom-timetable.js — 출결관리
// ==================== 출결 관리 ====================
let attSheetData = [];

function initAttendanceTab() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('att-date').value = today;
    const thisMonth = today.substring(0, 7);
    document.getElementById('att-month').value = thisMonth;
    loadAttendanceSheet();
    loadMonthlyOverview();
}

async function loadAttendanceSheet() {
    const container = document.getElementById('att-sheet');
    const attDate = document.getElementById('att-date').value;
    if (!attDate) return;

    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        params.append('date', attDate);

        const response = await fetch(`/api/attendance/sheet?${params.toString()}`);
        const data = await response.json();

        if (data.success && data.students?.length > 0) {
            attSheetData = data.students;
            renderAttSheet();
        } else {
            container.innerHTML = '<p class="text-center text-sm text-slate-400 py-8">해당 반에 학생이 없습니다.</p>';
        }
    } catch (error) {
        container.innerHTML = '<p class="text-center text-sm text-slate-400 py-8">출석부를 불러올 수 없습니다.</p>';
    }
}

function renderAttSheet() {
    const container = document.getElementById('att-sheet');
    const statuses = [
        {val:'present', label:'출석', color:'emerald'},
        {val:'absent', label:'결석', color:'red'},
        {val:'late', label:'지각', color:'amber'},
        {val:'early_leave', label:'조퇴', color:'blue'},
        {val:'sick', label:'병결', color:'slate'}
    ];

    container.innerHTML = attSheetData.map((s, idx) => `
        <div class="flex items-center gap-2 p-2 rounded-xl bg-slate-50 flex-wrap" data-idx="${idx}">
            <span class="w-8 text-center text-xs font-bold text-slate-500">${s.class_num || idx+1}</span>
            <span class="w-20 text-sm font-medium text-slate-800 truncate">${s.member_name}</span>
            <div class="flex gap-1 flex-1 flex-wrap">
                ${statuses.map(st => {
                    const isActive = (s.status || '') === st.val;
                    return `<button onclick="setAttStatus(${idx},'${st.val}')" class="att-btn-${idx} px-2 py-1 rounded-lg text-xs font-medium transition ${isActive ? `bg-${st.color}-500 text-white` : `bg-white text-slate-500 border border-slate-200 hover:bg-${st.color}-50`}" data-status="${st.val}">${st.label}</button>`;
                }).join('')}
            </div>
            <input type="text" value="${s.memo || ''}" placeholder="메모" class="att-memo w-24 px-2 py-1 text-xs border border-slate-200 rounded-lg" data-idx="${idx}">
        </div>
    `).join('');
}

function setAttStatus(idx, status) {
    attSheetData[idx].status = status;
    const statuses = {present:'emerald', absent:'red', late:'amber', early_leave:'blue', sick:'slate'};
    document.querySelectorAll(`.att-btn-${idx}`).forEach(btn => {
        const st = btn.dataset.status;
        const c = statuses[st];
        if (st === status) {
            btn.className = `att-btn-${idx} px-2 py-1 rounded-lg text-xs font-medium transition bg-${c}-500 text-white`;
        } else {
            btn.className = `att-btn-${idx} px-2 py-1 rounded-lg text-xs font-medium transition bg-white text-slate-500 border border-slate-200 hover:bg-${c}-50`;
        }
    });
}

function markAllPresent() {
    attSheetData.forEach((s, idx) => setAttStatus(idx, 'present'));
}

async function saveAttendance() {
    const attDate = document.getElementById('att-date').value;
    if (!attDate) { alert('날짜를 선택해주세요.'); return; }

    // 메모 수집
    document.querySelectorAll('.att-memo').forEach(el => {
        const idx = parseInt(el.dataset.idx);
        if (!isNaN(idx)) attSheetData[idx].memo = el.value;
    });

    const records = attSheetData.filter(s => s.status).map(s => ({
        student_id: s.member_id,
        status: s.status,
        memo: s.memo || ''
    }));

    if (records.length === 0) { alert('출결 상태를 선택해주세요.'); return; }

    try {
        const response = await fetch('/api/attendance/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                school_id: currentUser.school_id,
                class_grade: homeroomInfo.class_grade,
                class_no: homeroomInfo.class_no,
                date: attDate,
                records
            })
        });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadMonthlyOverview();
        } else {
            alert(data.message);
        }
    } catch (error) { alert('저장 중 오류가 발생했습니다.'); }
}

async function loadMonthlyOverview() {
    const month = document.getElementById('att-month').value;
    if (!month) return;

    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        params.append('month', month);

        const response = await fetch(`/api/attendance/monthly?${params.toString()}`);
        const data = await response.json();

        const container = document.getElementById('att-monthly');
        if (data.success && data.daily?.length > 0) {
            // 캘린더 히트맵
            const year = parseInt(month.split('-')[0]);
            const mon = parseInt(month.split('-')[1]);
            const firstDay = new Date(year, mon - 1, 1).getDay();
            const daysInMonth = new Date(year, mon, 0).getDate();
            const dayMap = {};
            data.daily.forEach(d => { dayMap[d.date] = d; });

            const headers = ['일','월','화','수','목','금','토'];
            let html = headers.map(h => `<div class="font-bold text-slate-500 py-1">${h}</div>`).join('');

            for (let i = 0; i < firstDay; i++) html += '<div></div>';

            for (let d = 1; d <= daysInMonth; d++) {
                const dateStr = `${year}-${String(mon).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
                const info = dayMap[dateStr];
                let bgClass = 'bg-slate-100';
                let tooltip = '';
                if (info) {
                    if (info.rate >= 95) bgClass = 'bg-emerald-200';
                    else if (info.rate >= 80) bgClass = 'bg-amber-200';
                    else bgClass = 'bg-red-200';
                    tooltip = `${info.rate}% (${info.present}/${info.total})`;
                }
                html += `<div class="p-1 ${bgClass} rounded text-slate-700" title="${tooltip}">${d}</div>`;
            }
            container.innerHTML = html;

            // 통계 요약
            let totalPresent = 0, totalAbsent = 0, totalLate = 0, totalAll = 0;
            data.daily.forEach(d => { totalPresent += d.present; totalAbsent += d.absent; totalLate += d.late; totalAll += d.total; });
            const overallRate = totalAll > 0 ? (totalPresent / totalAll * 100).toFixed(1) : 0;
            document.getElementById('att-stats-summary').innerHTML = `
                <div class="flex gap-4 text-sm">
                    <span class="text-emerald-600 font-bold">출석 ${totalPresent}</span>
                    <span class="text-red-500 font-bold">결석 ${totalAbsent}</span>
                    <span class="text-amber-500 font-bold">지각 ${totalLate}</span>
                    <span class="text-slate-600">출석률 ${overallRate}%</span>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="text-center text-sm text-slate-400 py-4 col-span-7">이번 달 출결 데이터가 없습니다.</p>';
            document.getElementById('att-stats-summary').innerHTML = '';
        }
    } catch (error) { console.error('월간 출결 오류:', error); }
}


