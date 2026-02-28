// homeroom-core.js — 전역변수, 초기화, 탭전환, 공용 유틸리티
let currentUser = null;
let homeroomInfo = null;
let studentList = [];

document.addEventListener('DOMContentLoaded', () => {
    const userStr = localStorage.getItem('schoolus_user');
    if (!userStr) {
        alert('로그인이 필요합니다.');
        window.location.href = '/';
        return;
    }
    currentUser = JSON.parse(userStr);
    
    document.getElementById('teacher-name').textContent = (currentUser.member_name || '사용자') + ' 선생님';
    document.getElementById('teacher-avatar').textContent = (currentUser.member_name || 'T').charAt(0);
    document.getElementById('teacher-info').textContent = currentUser.member_school || '-';
    
    checkHomeroomTeacher();
    setupDragDrop();
    setupRecordDragDrop();
});

function getSchoolParams() {
    const params = new URLSearchParams();
    if (currentUser.school_id) params.append('school_id', currentUser.school_id);
    if (currentUser.member_school) params.append('member_school', currentUser.member_school);
    return params;
}

async function checkHomeroomTeacher() {
    try {
        const params = getSchoolParams();
        params.append('member_id', currentUser.member_id);
        const response = await fetch(`/api/homeroom/check?${params.toString()}`);
        const data = await response.json();
        
        if (data.success && data.is_homeroom) {
            homeroomInfo = { class_grade: data.class_grade, class_no: data.class_no, teacher_name: data.teacher_name };
            document.getElementById('class-badge').textContent = `${data.class_grade}학년 ${data.class_no}반 담임`;
            document.getElementById('class-badge').classList.remove('hidden');
            document.getElementById('no-homeroom-view').classList.add('hidden');
            document.getElementById('homeroom-view').classList.remove('hidden');
            
            const yearSelect = document.getElementById('record-year');
            const currentYear = new Date().getFullYear();
            yearSelect.innerHTML = '';
            for (let y = currentYear; y >= currentYear - 2; y--) {
                yearSelect.innerHTML += `<option value="${y}">${y}년</option>`;
            }
            
            loadStudents();
            loadParents();
            loadNotices();
            loadSchedules();
            loadLogs();
            loadCommonActivities();
        } else {
            document.getElementById('no-homeroom-view').classList.remove('hidden');
            document.getElementById('homeroom-view').classList.add('hidden');
        }
    } catch (error) {
        console.error('담임 확인 오류:', error);
        document.getElementById('no-homeroom-view').classList.remove('hidden');
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('bg-white', 'border-2', 'border-slate-200');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.remove('bg-white', 'border-2', 'border-slate-200');
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
    document.getElementById(`panel-${tabName}`).classList.remove('hidden');
}


// ==================== 학생 선택 드롭다운 업데이트 ====================
function updateStudentSelects() {
    const selects = ['schedule-student', 'log-student', 'record-student'];
    const options = '<option value="">학생을 선택하세요</option>' + 
        studentList.map(s => `<option value="${s.member_id}" data-name="${s.member_name}" data-num="${s.class_num}">${s.class_num || '-'}번 ${s.member_name}</option>`).join('');
    selects.forEach(id => {
        const select = document.getElementById(id);
        if (select) select.innerHTML = options;
    });
}

// ==================== 공용 유틸리티 ====================
function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        pdf: {icon:'fas fa-file-pdf',color:'text-red-500',bg:'bg-red-100'},
        hwp: {icon:'fas fa-file-alt',color:'text-sky-500',bg:'bg-sky-100'},
        hwpx:{icon:'fas fa-file-alt',color:'text-sky-500',bg:'bg-sky-100'},
        doc: {icon:'fas fa-file-word',color:'text-blue-500',bg:'bg-blue-100'},
        docx:{icon:'fas fa-file-word',color:'text-blue-500',bg:'bg-blue-100'},
        xls: {icon:'fas fa-file-excel',color:'text-green-500',bg:'bg-green-100'},
        xlsx:{icon:'fas fa-file-excel',color:'text-green-500',bg:'bg-green-100'},
        ppt: {icon:'fas fa-file-powerpoint',color:'text-orange-500',bg:'bg-orange-100'},
        pptx:{icon:'fas fa-file-powerpoint',color:'text-orange-500',bg:'bg-orange-100'},
        jpg: {icon:'fas fa-file-image',color:'text-purple-500',bg:'bg-purple-100'},
        jpeg:{icon:'fas fa-file-image',color:'text-purple-500',bg:'bg-purple-100'},
        png: {icon:'fas fa-file-image',color:'text-purple-500',bg:'bg-purple-100'},
        gif: {icon:'fas fa-file-image',color:'text-purple-500',bg:'bg-purple-100'},
        zip: {icon:'fas fa-file-archive',color:'text-yellow-600',bg:'bg-yellow-100'},
    };
    return icons[ext] || {icon:'fas fa-file',color:'text-slate-500',bg:'bg-slate-100'};
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

function handleLogout() {
    if (confirm('로그아웃 하시겠습니까?')) {
        localStorage.removeItem('schoolus_user');
        window.location.href = '/';
    }
}


// ==================== 모바일 사이드바 ====================
function toggleMobileSidebar() {
    document.getElementById('sidebar').classList.toggle('mobile-open');
    document.getElementById('mobile-overlay').classList.toggle('active');
}
document.getElementById('mobile-overlay').onclick = function() {
    document.getElementById('sidebar').classList.remove('mobile-open');
    this.classList.remove('active');
};
