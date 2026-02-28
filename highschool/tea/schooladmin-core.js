// schooladmin-core.js — 전역변수, 초기화, 탭전환, 공지/급식 모달, 사이드바
let currentUser = null;
let surveyQuestionIndex = 0;

document.addEventListener('DOMContentLoaded', () => {
    initUserInfo();
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (tab) switchTab(tab);
});

// ==========================================
// 탭 전환
// ==========================================
function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('bg-white', 'border-2', 'border-slate-200');
    });
    const activeBtn = document.getElementById('tab-' + tabName);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.classList.remove('bg-white', 'border-2', 'border-slate-200');
    }
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    const panel = document.getElementById('panel-' + tabName);
    if (panel) panel.classList.add('active');

    if (tabName === 'survey') loadSurveys();
    if (tabName === 'afterschool') loadPrograms();
    if (tabName === 'letter') loadTeacherLetters();
    if (tabName === 'exam') {}
    if (tabName === 'admin') initAdminTab();
}

// ==========================================
// 사용자 초기화 (기존 유지)
// ==========================================
function initUserInfo() {
    const userStr = localStorage.getItem('schoolus_user');
    if (!userStr) { alert('로그인이 필요합니다.'); window.location.href = '/'; return; }
    currentUser = JSON.parse(userStr);
    const schoolBadge = document.getElementById('userSchoolBadge');
    if (currentUser.member_school) { schoolBadge.textContent = currentUser.member_school; }
    else { schoolBadge.textContent = '학교 미설정'; schoolBadge.className = 'bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold'; }
    const userName = document.getElementById('userName');
    const userAvatar = document.getElementById('userAvatar');
    const welcomeMessage = document.getElementById('welcomeMessage');
    if (currentUser.member_name) {
        if (userName) userName.textContent = currentUser.member_name + ' 선생님';
        if (userAvatar) userAvatar.textContent = currentUser.member_name.charAt(0);
        if (welcomeMessage) welcomeMessage.textContent = `${currentUser.member_name} 선생님, 안녕하세요!`;
    }
    loadUserPoint();
}
async function loadUserPoint() {
    try {
        const r = await fetch(`/api/teacher/info?member_id=${encodeURIComponent(currentUser.member_id)}`);
        const d = await r.json();
        if (d.success && d.teacher) displayPoint(d.teacher.point);
    } catch(e) { console.error('포인트 로드 오류:', e); }
}
function displayPoint(point) {
    const el = document.getElementById('userPoint');
    if (!el) return;
    if (point === 'free' || point === 'Free') el.textContent = 'Free';
    else if (point === null || point === undefined || point === '') el.textContent = '0';
    else { const num = parseInt(point); el.textContent = isNaN(num) ? '0' : num.toLocaleString(); }
}
function getSchoolParams() {
    const params = new URLSearchParams();
    if (currentUser.school_id) params.append('school_id', currentUser.school_id);
    if (currentUser.member_school) params.append('member_school', currentUser.member_school);
    return params;
}

// ==========================================
// 공지사항 모달 (기존 유지)
// ==========================================
function openNoticeModal() {
    document.getElementById('notice-title').value = '';
    document.getElementById('notice-message').value = '';
    document.getElementById('notice-correct-no').value = '';
    document.getElementById('notice-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closeNoticeModal() { document.getElementById('notice-modal').classList.add('hidden'); document.body.style.overflow = 'auto'; }
async function submitNotice() {
    const title = document.getElementById('notice-title').value.trim();
    const message = document.getElementById('notice-message').value.trim();
    const correct_no = document.getElementById('notice-correct-no').value.trim();
    if (!title || !message) return alert('제목과 내용을 모두 입력해주세요.');
    if (!correct_no || correct_no.length < 4) return alert('비밀번호를 4자리 이상 입력해주세요.');
    try {
        const r = await fetch('/api/notice/create', { method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ member_name: currentUser.member_name, member_school: currentUser.member_school, school_id: currentUser.school_id, title, message, correct_no })
        });
        const d = await r.json();
        alert(d.message); if (d.success) closeNoticeModal();
    } catch(e) { alert('공지사항 등록 중 오류가 발생했습니다.'); }
}

// ==========================================
// 월간 급식 모달 (기존 유지)
// ==========================================
function openMealModal() {
    const yearSelect = document.getElementById('meal-year');
    const cy = new Date().getFullYear(); yearSelect.innerHTML = '';
    for (let y = cy-1; y <= cy+1; y++) { const o = document.createElement('option'); o.value = y; o.textContent = y+'년'; if(y===cy) o.selected=true; yearSelect.appendChild(o); }
    document.getElementById('meal-month').value = new Date().getMonth()+1;
    generateMealGrid(); loadMealData();
    document.getElementById('meal-modal').classList.remove('hidden'); document.body.style.overflow = 'hidden';
}
function closeMealModal() { document.getElementById('meal-modal').classList.add('hidden'); document.body.style.overflow = 'auto'; }
function generateMealGrid() {
    const year = parseInt(document.getElementById('meal-year').value), month = parseInt(document.getElementById('meal-month').value);
    const dim = new Date(year, month, 0).getDate(), grid = document.getElementById('meal-grid'); grid.innerHTML = '';
    for (let d=1; d<=dim; d++) {
        const dt = new Date(year, month-1, d), dw = ['일','월','화','수','목','금','토'][dt.getDay()], isWe = dt.getDay()===0||dt.getDay()===6;
        const c = document.createElement('div');
        c.className = `p-3 rounded-xl border-2 ${isWe?'border-slate-100 bg-slate-50':'border-slate-200 bg-white'}`;
        c.innerHTML = `<div class="flex items-center justify-between mb-2"><span class="font-bold text-slate-800">${d}일</span><span class="text-xs px-2 py-0.5 rounded-full ${dt.getDay()===0?'bg-red-100 text-red-600':dt.getDay()===6?'bg-blue-100 text-blue-600':'bg-slate-100 text-slate-600'}">${dw}</span></div><textarea id="meal-day-${d}" rows="3" placeholder="${isWe?'주말':'메뉴 입력'}" class="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:border-pink-400 outline-none resize-none meal-input ${isWe?'bg-slate-100':''}"></textarea>`;
        grid.appendChild(c);
    }
}
async function loadMealData() {
    const year=document.getElementById('meal-year').value, month=document.getElementById('meal-month').value, st=document.getElementById('meal-status');
    generateMealGrid(); st.innerHTML='<i class="fas fa-spinner fa-spin mr-1"></i>불러오는 중...';
    try {
        const p=getSchoolParams(); p.append('year',year); p.append('month',month);
        const r=await fetch(`/api/meal/month?${p.toString()}`), d=await r.json();
        if(d.success&&d.meals){const mc=Object.keys(d.meals).length; for(const[day,mi] of Object.entries(d.meals)){const ta=document.getElementById(`meal-day-${day}`); if(ta)ta.value=mi.menu||'';} st.innerHTML=mc>0?`<i class="fas fa-check-circle text-green-500 mr-1"></i>${mc}일분 로드됨`:'<i class="fas fa-info-circle text-slate-400 mr-1"></i>데이터 없음';}
        else st.innerHTML='<i class="fas fa-info-circle text-slate-400 mr-1"></i>데이터 없음';
    } catch(e){st.innerHTML='<i class="fas fa-exclamation-circle text-red-500 mr-1"></i>로드 실패';}
}
async function saveMealData() {
    const year=document.getElementById('meal-year').value, month=document.getElementById('meal-month').value;
    const dim=new Date(parseInt(year),parseInt(month),0).getDate(), meals={}; let fc=0;
    for(let d=1;d<=dim;d++){const ta=document.getElementById(`meal-day-${d}`); if(ta&&ta.value.trim()){meals[d]=ta.value.trim();fc++;}}
    if(fc===0&&!confirm('입력된 메뉴가 없습니다. 기존 데이터를 삭제하시겠습니까?')) return;
    try {
        const r=await fetch('/api/meal/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({school_id:currentUser.school_id,member_school:currentUser.member_school,year,month,meals})});
        const d=await r.json(); alert(d.message); if(d.success)document.getElementById('meal-status').innerHTML='<i class="fas fa-check-circle text-green-500 mr-1"></i>저장 완료';
    } catch(e){alert('저장 중 오류가 발생했습니다.');}
}

// ==========================================
// 모바일 사이드바
// ==========================================
function toggleMobileSidebar() {
    document.getElementById('sidebar').classList.toggle('mobile-open');
    document.getElementById('mobile-overlay').classList.toggle('active');
}
function closeMobileSidebar() {
    document.getElementById('sidebar').classList.remove('mobile-open');
    document.getElementById('mobile-overlay').classList.remove('active');
}
document.getElementById('mobile-overlay').onclick = closeMobileSidebar;
