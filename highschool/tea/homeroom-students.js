// homeroom-students.js — 학생/학부모 명단 + 학생추가 모달
// ==================== 학생 명단 ====================
async function loadStudents() {
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        const response = await fetch(`/api/homeroom/students?${params.toString()}`);
        const data = await response.json();
        
        if (data.success) {
            studentList = data.students || [];
            document.getElementById('student-count').textContent = `총 ${studentList.length}명`;
            
            const tbody = document.getElementById('student-list');
            if (studentList.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center py-12 text-slate-400">등록된 학생이 없습니다. 학생을 추가해주세요.</td></tr>';
            } else {
                tbody.innerHTML = studentList.map(s => `
                    <tr class="hover:bg-slate-50 transition" id="stu-row-${s.id}">
                        <td class="px-4 py-3 font-bold text-slate-800">
                            <span class="stu-view">${s.class_num || '-'}</span>
                            <input type="text" value="${s.class_num || ''}" class="stu-edit hidden w-12 text-xs text-center border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 font-medium">
                            <span class="stu-view">${s.member_name}</span>
                            ${s.member_id ? '<button onclick="sendMessageTo(\'' + s.member_id + '\', \'' + s.member_name + '\')" class="stu-view ml-1 text-blue-400 hover:text-blue-600 transition no-print" title="메시지 보내기"><i class="fas fa-envelope text-xs"></i></button>' : ''}
                            <input type="text" value="${s.member_name || ''}" class="stu-edit hidden w-20 text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-sm text-slate-600">
                            <span class="stu-view">${s.member_birth || '-'}</span>
                            <input type="date" value="${s.member_birth || ''}" class="stu-edit hidden text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-sm text-slate-600">
                            <span class="stu-view">${s.member_tel || '-'}</span>
                            <input type="text" value="${s.member_tel || ''}" placeholder="010-0000-0000" class="stu-edit hidden w-28 text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-center">
                            <input type="text" value="${s.class_role || ''}" placeholder="-"
                                onblur="saveClassRole(${s.id}, this.value)"
                                onkeydown="if(event.key==='Enter'){this.blur();}"
                                class="w-20 text-xs text-center border border-slate-200 rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-1 focus:ring-green-400">
                        </td>
                        <td class="px-4 py-3 text-center">
                            <button onclick="quickCounsel('${s.member_id}', '${s.member_name}', ${s.class_num || 0})" class="px-3 py-1 bg-blue-100 text-blue-600 rounded-lg text-xs font-bold hover:bg-blue-200 transition">
                                <i class="fas fa-comments mr-1"></i>상담
                            </button>
                        </td>
                        <td class="px-4 py-3 text-center">
                            <button onclick="quickRecord('${s.member_id}', '${s.member_name}', ${s.class_num || 0})" class="px-3 py-1 bg-teal-100 text-teal-600 rounded-lg text-xs font-bold hover:bg-teal-200 transition">
                                <i class="fas fa-database mr-1"></i>기초자료
                            </button>
                        </td>
                        <td class="px-4 py-3 text-center whitespace-nowrap">
                            <button onclick="toggleStudentEdit(${s.id})" class="stu-view px-3 py-1 bg-amber-100 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-200 transition">
                                <i class="fas fa-pen mr-1"></i>수정
                            </button>
                            <button onclick="saveStudentEdit(${s.id})" class="stu-edit hidden px-3 py-1 bg-green-100 text-green-600 rounded-lg text-xs font-bold hover:bg-green-200 transition">
                                <i class="fas fa-check mr-1"></i>저장
                            </button>
                            <button onclick="cancelStudentEdit(${s.id})" class="stu-edit hidden px-3 py-1 bg-slate-100 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-200 transition">
                                <i class="fas fa-times"></i>
                            </button>
                            <button onclick="removeStudent(${s.id}, '${s.member_name}')" class="stu-view px-3 py-1 bg-red-100 text-red-600 rounded-lg text-xs font-bold hover:bg-red-200 transition ml-1">
                                <i class="fas fa-user-minus mr-1"></i>제거
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
            updateStudentSelects();
        }
    } catch (error) {
        console.error('학생 로드 오류:', error);
    }
}

function printStudentList() {
    if (!studentList || studentList.length === 0) {
        alert('출력할 학생 데이터가 없습니다.');
        return;
    }
    const schoolName = currentUser.member_school || '';
    const classInfo = homeroomInfo ? `${homeroomInfo.class_grade}학년 ${homeroomInfo.class_no}반` : '';
    const today = new Date().toLocaleDateString('ko-KR');

    let html = `<div class="print-header">
        <h2>${schoolName} ${classInfo} 학생 명단</h2>
        <p>출력일: ${today} | 총 ${studentList.length}명</p>
    </div>
    <table>
        <thead><tr>
            <th style="width:50px;text-align:center">번호</th>
            <th style="width:80px">이름</th>
            <th style="width:100px">생년월일</th>
            <th style="width:120px">연락처</th>
            <th style="width:80px;text-align:center">학급자치</th>
        </tr></thead><tbody>`;

    studentList.forEach(s => {
        html += `<tr>
            <td style="text-align:center">${s.class_num || '-'}</td>
            <td>${s.member_name || '-'}</td>
            <td>${s.member_birth || '-'}</td>
            <td>${s.member_tel || '-'}</td>
            <td style="text-align:center">${s.class_role || '-'}</td>
        </tr>`;
    });
    html += '</tbody></table>';

    const printArea = document.getElementById('print-area');
    printArea.innerHTML = html;
    printArea.style.display = 'block';
    window.print();
    printArea.style.display = 'none';
}

async function sendMessageTo(targetMemberId, targetName) {
    try {
        const res = await fetch('/api/messenger/conversations/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                member_id: currentUser.member_id,
                school_id: currentUser.school_id,
                user_role: 'teacher',
                member_name: currentUser.member_name,
                target_ids: [targetMemberId],
                conv_type: 'direct'
            })
        });
        const data = await res.json();
        if (data.success) {
            const level = (currentUser.school_level === '중학교') ? 'middleschool' : 'highschool';
            window.location.href = `/${level}/messenger.html?conv=${data.conversation_id}`;
        } else {
            alert(data.message || '대화방 생성에 실패했습니다.');
        }
    } catch (error) {
        console.error('메시지 보내기 오류:', error);
        alert('메시지 기능 연결 중 오류가 발생했습니다.');
    }
}

async function saveClassRole(id, role) {
    try {
        const response = await fetch('/api/homeroom/students/role', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, class_role: role })
        });
        const data = await response.json();
        if (data.success) {
            const s = studentList.find(st => st.id === id);
            if (s) s.class_role = role;
        }
    } catch (error) {
        console.error('학급자치 저장 오류:', error);
    }
}

function toggleStudentEdit(id) {
    const row = document.getElementById(`stu-row-${id}`);
    row.querySelectorAll('.stu-view').forEach(el => el.classList.add('hidden'));
    row.querySelectorAll('.stu-edit').forEach(el => el.classList.remove('hidden'));
}

function cancelStudentEdit(id) {
    const row = document.getElementById(`stu-row-${id}`);
    row.querySelectorAll('.stu-view').forEach(el => el.classList.remove('hidden'));
    row.querySelectorAll('.stu-edit').forEach(el => el.classList.add('hidden'));
    const s = studentList.find(st => st.id === id);
    if (s) {
        const inputs = row.querySelectorAll('.stu-edit');
        inputs[0].value = s.class_num || '';
        inputs[1].value = s.member_name || '';
        inputs[2].value = s.member_birth || '';
        inputs[3].value = s.member_tel || '';
    }
}

async function saveStudentEdit(id) {
    const row = document.getElementById(`stu-row-${id}`);
    const inputs = row.querySelectorAll('.stu-edit');
    const classNum = inputs[0].value.trim();
    const memberName = inputs[1].value.trim();
    const memberBirth = inputs[2].value.trim();
    const memberTel = inputs[3].value.trim();
    const s = studentList.find(st => st.id === id);
    const classRole = s ? s.class_role || '' : '';

    if (!memberName) { alert('이름은 필수입니다.'); return; }

    try {
        const response = await fetch('/api/homeroom/students/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, member_name: memberName, member_birth: memberBirth, member_tel: memberTel, class_num: classNum, class_role: classRole })
        });
        const data = await response.json();
        if (data.success) {
            const s = studentList.find(st => st.id === id);
            if (s) { s.class_num = classNum; s.member_name = memberName; s.member_birth = memberBirth; s.member_tel = memberTel; s.class_role = classRole; }
            loadStudents();
        } else {
            alert(data.message || '수정 실패');
        }
    } catch (error) {
        console.error('학생 정보 수정 오류:', error);
        alert('수정 중 오류가 발생했습니다.');
    }
}

function toggleParentEdit(id) {
    const row = document.getElementById(`par-row-${id}`);
    row.querySelectorAll('.par-view').forEach(el => el.classList.add('hidden'));
    row.querySelectorAll('.par-edit').forEach(el => el.classList.remove('hidden'));
}

function cancelParentEdit(id) {
    const row = document.getElementById(`par-row-${id}`);
    row.querySelectorAll('.par-view').forEach(el => el.classList.remove('hidden'));
    row.querySelectorAll('.par-edit').forEach(el => el.classList.add('hidden'));
    const p = parentList.find(pt => pt.id === id);
    if (p) {
        const inputs = row.querySelectorAll('.par-edit');
        inputs[0].value = p.member_name || '';
        inputs[1].value = p.member_tel || '';
        inputs[2].value = p.child_name || '';
        inputs[3].value = p.child_birth || '';
    }
}

async function saveParentEdit(id) {
    const row = document.getElementById(`par-row-${id}`);
    const inputs = row.querySelectorAll('.par-edit');
    const memberName = inputs[0].value.trim();
    const memberTel = inputs[1].value.trim();
    const childName = inputs[2].value.trim();
    const childBirth = inputs[3].value.trim();

    if (!memberName) { alert('이름은 필수입니다.'); return; }

    try {
        const response = await fetch('/api/homeroom/parents/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, member_name: memberName, member_tel: memberTel, child_name: childName, child_birth: childBirth })
        });
        const data = await response.json();
        if (data.success) {
            const p = parentList.find(pt => pt.id === id);
            if (p) { p.member_name = memberName; p.member_tel = memberTel; p.child_name = childName; p.child_birth = childBirth; }
            loadParents();
        } else {
            alert(data.message || '수정 실패');
        }
    } catch (error) {
        console.error('학부모 정보 수정 오류:', error);
        alert('수정 중 오류가 발생했습니다.');
    }
}

// ==================== 학부모 명단 ====================
let parentList = [];

async function loadParents() {
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        const response = await fetch(`/api/homeroom/parents?${params.toString()}`);
        const data = await response.json();

        if (data.success) {
            parentList = data.parents || [];
            document.getElementById('parent-count').textContent = `총 ${parentList.length}명`;

            const tbody = document.getElementById('parent-list');
            if (parentList.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-12 text-slate-400">등록된 학부모가 없습니다.</td></tr>';
            } else {
                tbody.innerHTML = parentList.map(p => `
                    <tr class="hover:bg-slate-50 transition" id="par-row-${p.id}">
                        <td class="px-4 py-3 font-bold text-slate-800">${p.class_num || '-'}</td>
                        <td class="px-4 py-3 font-medium">
                            <span class="par-view">${p.member_name}</span>
                            ${p.member_id ? '<button onclick="sendMessageTo(\'' + p.member_id + '\', \'' + p.member_name + '\')" class="par-view ml-1 text-blue-400 hover:text-blue-600 transition no-print" title="메시지 보내기"><i class="fas fa-envelope text-xs"></i></button>' : ''}
                            <input type="text" value="${p.member_name || ''}" class="par-edit hidden w-20 text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-sm text-slate-600">
                            <span class="par-view">${p.member_tel || '-'}</span>
                            <input type="text" value="${p.member_tel || ''}" placeholder="010-0000-0000" class="par-edit hidden w-28 text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-sm text-slate-600">
                            <span class="par-view">${p.child_name || '-'}</span>
                            <input type="text" value="${p.child_name || ''}" class="par-edit hidden w-20 text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-sm text-slate-600">
                            <span class="par-view">${p.child_birth || '-'}</span>
                            <input type="date" value="${p.child_birth || ''}" class="par-edit hidden text-xs border border-slate-300 rounded px-1 py-0.5">
                        </td>
                        <td class="px-4 py-3 text-center whitespace-nowrap">
                            <button onclick="toggleParentEdit(${p.id})" class="par-view px-3 py-1 bg-amber-100 text-amber-600 rounded-lg text-xs font-bold hover:bg-amber-200 transition">
                                <i class="fas fa-pen mr-1"></i>수정
                            </button>
                            <button onclick="saveParentEdit(${p.id})" class="par-edit hidden px-3 py-1 bg-green-100 text-green-600 rounded-lg text-xs font-bold hover:bg-green-200 transition">
                                <i class="fas fa-check mr-1"></i>저장
                            </button>
                            <button onclick="cancelParentEdit(${p.id})" class="par-edit hidden px-3 py-1 bg-slate-100 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-200 transition">
                                <i class="fas fa-times"></i>
                            </button>
                        </td>
                    </tr>
                `).join('');
            }
        }
    } catch (error) {
        console.error('학부모 로드 오류:', error);
    }
}

function printParentList() {
    if (!parentList || parentList.length === 0) {
        alert('출력할 학부모 데이터가 없습니다.');
        return;
    }
    const schoolName = currentUser.member_school || '';
    const classInfo = homeroomInfo ? `${homeroomInfo.class_grade}학년 ${homeroomInfo.class_no}반` : '';
    const today = new Date().toLocaleDateString('ko-KR');

    let html = `<div class="print-header">
        <h2>${schoolName} ${classInfo} 학부모 명단</h2>
        <p>출력일: ${today} | 총 ${parentList.length}명</p>
    </div>
    <table>
        <thead><tr>
            <th style="width:50px;text-align:center">번호</th>
            <th style="width:80px">학부모 이름</th>
            <th style="width:120px">연락처</th>
            <th style="width:80px">자녀 이름</th>
            <th style="width:100px">자녀 생년월일</th>
        </tr></thead><tbody>`;

    parentList.forEach(p => {
        html += `<tr>
            <td style="text-align:center">${p.class_num || '-'}</td>
            <td>${p.member_name || '-'}</td>
            <td>${p.member_tel || '-'}</td>
            <td>${p.child_name || '-'}</td>
            <td>${p.child_birth || '-'}</td>
        </tr>`;
    });
    html += '</tbody></table>';

    const printArea = document.getElementById('print-area');
    printArea.innerHTML = html;
    printArea.style.display = 'block';
    window.print();
    printArea.style.display = 'none';
}


// ==================== 학생 추가 (개별) ====================
function openAddStudentModal() {
    document.getElementById('add-name').value = '';
    document.getElementById('add-birth').value = '';
    document.getElementById('add-tel').value = '';
    document.getElementById('add-classnum').value = '';
    document.getElementById('search-student-keyword').value = '';
    document.getElementById('search-results').classList.add('hidden');
    document.getElementById('add-student-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeAddStudentModal() {
    document.getElementById('add-student-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

let searchTimer = null;
function debounceSearch() {
    clearTimeout(searchTimer);
    const keyword = document.getElementById('search-student-keyword').value.trim();
    if (keyword.length === 0) {
        document.getElementById('search-results').classList.add('hidden');
        return;
    }
    searchTimer = setTimeout(() => searchExistingStudents(), 300);
}

async function searchExistingStudents() {
    const keyword = document.getElementById('search-student-keyword').value.trim();
    if (!keyword) { document.getElementById('search-results').classList.add('hidden'); return; }
    
    try {
        const params = getSchoolParams();
        params.append('class_grade', homeroomInfo.class_grade);
        params.append('class_no', homeroomInfo.class_no);
        params.append('keyword', keyword);
        
        const response = await fetch(`/api/homeroom/students/search?${params.toString()}`);
        const data = await response.json();
        
        const container = document.getElementById('search-results');
        container.classList.remove('hidden');
        
        if (data.success && data.students?.length > 0) {
            container.innerHTML = data.students.map(s => `
                <div class="flex items-center justify-between p-3 bg-slate-50 rounded-xl mb-2 hover:bg-green-50 transition">
                    <div>
                        <span class="font-bold text-slate-800">${s.member_name}</span>
                        <span class="text-xs text-slate-500 ml-2">${s.member_birth || ''} ${s.member_tel || ''}</span>
                        ${s.class_grade ? `<span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full ml-1">${s.class_grade}-${s.class_no}</span>` : '<span class="text-xs bg-slate-200 text-slate-500 px-2 py-0.5 rounded-full ml-1">미배정</span>'}
                    </div>
                    <button onclick="assignExistingStudent(${s.id}, '${s.member_name}')" class="px-3 py-1 bg-green-500 text-white rounded-lg text-xs font-bold hover:bg-green-600 transition">
                        <i class="fas fa-plus mr-1"></i>배정
                    </button>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<p class="text-center py-4 text-slate-400 text-sm">검색 결과가 없습니다. 아래에서 직접 등록해주세요.</p>';
        }
    } catch (error) {
        console.error('학생 검색 오류:', error);
    }
}

async function assignExistingStudent(studentDbId, studentName) {
    const classNum = prompt(`${studentName} 학생의 번호를 입력하세요 (미정이면 빈칸):`, '');
    if (classNum === null) return;
    
    try {
        const response = await fetch('/api/homeroom/students/assign', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: studentDbId,
                class_grade: homeroomInfo.class_grade,
                class_no: homeroomInfo.class_no,
                class_num: classNum || null
            })
        });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            closeAddStudentModal();
            loadStudents();
        } else alert(data.message);
    } catch (error) {
        alert('배정 중 오류가 발생했습니다.');
    }
}

async function addStudentManual() {
    const memberName = document.getElementById('add-name').value.trim();
    const memberBirth = document.getElementById('add-birth').value.trim();
    const memberTel = document.getElementById('add-tel').value.trim();
    const classNum = document.getElementById('add-classnum').value.trim();
    
    if (!memberName) return alert('학생 이름은 필수입니다.');
    
    try {
        const response = await fetch('/api/homeroom/students/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: currentUser.school_id,
                member_school: currentUser.member_school,
                member_name: memberName,
                member_birth: memberBirth || null,
                member_tel: memberTel || null,
                class_grade: homeroomInfo.class_grade,
                class_no: homeroomInfo.class_no,
                class_num: classNum || null
            })
        });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            closeAddStudentModal();
            loadStudents();
        } else alert(data.message);
    } catch (error) {
        alert('학생 추가 중 오류가 발생했습니다.');
    }
}

// ==================== 학생 제거 ====================
async function removeStudent(studentDbId, studentName) {
    if (!confirm(`${studentName} 학생을 반에서 제거하시겠습니까?\n(학생 정보는 삭제되지 않고 반 배정만 해제됩니다)`)) return;
    try {
        const response = await fetch('/api/homeroom/students/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: studentDbId })
        });
        const data = await response.json();
        if (data.success) {
            alert(data.message);
            loadStudents();
        } else alert(data.message);
    } catch (error) {
        alert('제거 중 오류가 발생했습니다.');
    }
}

// ==================== 엑셀 업로드 ====================
function openUploadModal() {
    document.getElementById('upload-file').value = '';
    document.getElementById('upload-placeholder').classList.remove('hidden');
    document.getElementById('upload-selected').classList.add('hidden');
    document.getElementById('upload-btn').disabled = true;
    document.getElementById('upload-result').classList.add('hidden');
    document.getElementById('upload-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeUploadModal() {
    document.getElementById('upload-modal').classList.add('hidden');
    document.body.style.overflow = 'auto';
}

function handleFileSelect(input) {
    if (input.files.length > 0) {
        document.getElementById('upload-placeholder').classList.add('hidden');
        document.getElementById('upload-selected').classList.remove('hidden');
        document.getElementById('upload-filename').textContent = input.files[0].name;
        document.getElementById('upload-btn').disabled = false;
    }
}

function setupDragDrop() {
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone) return;
    ['dragenter', 'dragover'].forEach(e => {
        dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.add('border-green-400', 'bg-green-50'); });
    });
    ['dragleave', 'drop'].forEach(e => {
        dropZone.addEventListener(e, (ev) => { ev.preventDefault(); dropZone.classList.remove('border-green-400', 'bg-green-50'); });
    });
    dropZone.addEventListener('drop', (ev) => {
        const files = ev.dataTransfer.files;
        if (files.length > 0) {
            document.getElementById('upload-file').files = files;
            handleFileSelect(document.getElementById('upload-file'));
        }
    });
}

async function uploadExcel() {
    const fileInput = document.getElementById('upload-file');
    if (!fileInput.files.length) return alert('파일을 선택해주세요.');
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('school_id', currentUser.school_id || '');
    formData.append('member_school', currentUser.member_school || '');
    formData.append('class_grade', homeroomInfo.class_grade);
    formData.append('class_no', homeroomInfo.class_no);
    
    const btn = document.getElementById('upload-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>처리 중...';
    
    try {
        const response = await fetch('/api/homeroom/students/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        const resultDiv = document.getElementById('upload-result');
        resultDiv.classList.remove('hidden');
        
        if (data.success) {
            resultDiv.className = 'mt-4 p-4 rounded-xl text-sm bg-green-50 text-green-800 border border-green-200';
            resultDiv.innerHTML = `<i class="fas fa-check-circle mr-2"></i><b>${data.message}</b>`;
            if (data.errors?.length > 0) {
                resultDiv.innerHTML += '<br><span class="text-red-600 text-xs mt-1 block">오류: ' + data.errors.join(', ') + '</span>';
            }
            loadStudents();
        } else {
            resultDiv.className = 'mt-4 p-4 rounded-xl text-sm bg-red-50 text-red-800 border border-red-200';
            resultDiv.innerHTML = `<i class="fas fa-exclamation-circle mr-2"></i>${data.message}`;
        }
    } catch (error) {
        alert('업로드 중 오류가 발생했습니다.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-upload mr-2"></i>업로드 및 등록';
    }
}

// ==================== 바로가기 ====================
function quickCounsel(studentId, studentName, classNum) {
    switchTab('log');
    document.getElementById('log-student').value = studentId;
    openLogModal();
    document.getElementById('log-student').value = studentId;
}

function quickRecord(studentId, studentName, classNum) {
    switchTab('record');
    document.getElementById('record-student').value = studentId;
    document.getElementById('record-form').classList.remove('hidden');
    document.getElementById('record-placeholder').classList.add('hidden');
    loadStudentRecord();
}

