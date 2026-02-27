/**
 * SchoolUs 메신저 팝업 — 대시보드에서 인라인 채팅
 * tea.html, st.html, fm.html 공용
 */
(function(){
    let _roomId = null, _pollTimer = null, _lastMsgId = 0, _myId = '';
    let _currentRoomType = 'direct';
    let _selectedContacts = {};  // {member_id: {name, role, ...}}
    let _searchTimer = null;

    /* ── 초기화 ── */
    window.initMsgPopup = function(){
        _myId = sessionStorage.getItem('member_id') || '';
        document.body.insertAdjacentHTML('beforeend', `
<div id="msg-popup-overlay" class="hidden fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm flex items-center justify-center p-4" onclick="if(event.target===this)closeMsgPopup()">
  <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl flex flex-col overflow-hidden relative" style="height:min(80vh,700px)">
    <div class="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 text-white shrink-0">
      <div class="flex items-center gap-3">
        <button id="msg-back-btn" class="hidden w-8 h-8 rounded-lg bg-white/20 hover:bg-white/30 items-center justify-center transition" onclick="msgGoBack()"><i class="fas fa-arrow-left text-sm"></i></button>
        <h3 id="msg-popup-title" class="font-bold">메시지</h3>
      </div>
      <div class="flex items-center gap-1">
        <button id="msg-menu-btn" class="hidden w-8 h-8 rounded-lg bg-white/20 hover:bg-white/30 items-center justify-center transition" onclick="toggleRoomMenu(event)"><i class="fas fa-ellipsis-v text-sm"></i></button>
        <button onclick="closeMsgPopup()" class="w-8 h-8 rounded-lg bg-white/20 hover:bg-white/30 flex items-center justify-center transition"><i class="fas fa-times text-sm"></i></button>
      </div>
    </div>
    <div id="msg-room-dropdown" class="hidden absolute right-4 top-12 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-10 min-w-[160px]">
      <button onclick="leaveCurrentRoom()" class="w-full px-4 py-2.5 text-left text-sm text-red-500 hover:bg-red-50 flex items-center gap-2 transition"><i class="fas fa-sign-out-alt"></i> <span id="msg-leave-text">대화방 나가기</span></button>
    </div>

    <!-- 대화 목록 -->
    <div id="msg-list-view" class="flex-1 overflow-auto">
      <div class="p-3 border-b border-slate-100">
        <button onclick="showNewChat()" class="w-full flex items-center justify-center gap-2 py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-xl text-sm font-semibold transition"><i class="fas fa-plus"></i> 새 대화</button>
      </div>
      <div id="msg-popup-rooms" class="divide-y divide-slate-100"></div>
    </div>

    <!-- 새 대화 -->
    <div id="msg-new-view" class="hidden flex-1 flex flex-col overflow-hidden">
      <div class="flex border-b border-slate-200 shrink-0">
        <button id="msg-tab-person" onclick="switchNewTab('person')" class="flex-1 py-2.5 text-sm font-semibold text-blue-600 border-b-2 border-blue-500 transition">개인/그룹</button>
        <button id="msg-tab-group" onclick="switchNewTab('group')" class="flex-1 py-2.5 text-sm font-semibold text-slate-400 border-b-2 border-transparent hover:text-slate-600 transition">단체 대화</button>
      </div>
      <!-- 개인/그룹 탭 -->
      <div id="msg-person-panel" class="flex-1 flex flex-col overflow-hidden">
        <div class="p-3 border-b border-slate-100 space-y-2 shrink-0">
          <div class="flex gap-2">
            <select id="msg-role-filter" onchange="searchContacts()" class="px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:border-blue-400 outline-none">
              <option value="">전체</option>
              <option value="teacher">교사</option>
              <option value="student">학생</option>
              <option value="parent">학부모</option>
            </select>
            <input id="msg-contact-search" type="text" placeholder="이름 검색..." class="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none" oninput="onContactSearch()">
          </div>
          <div id="msg-selected-tags" class="flex flex-wrap gap-1.5 min-h-[28px]"></div>
        </div>
        <div id="msg-contact-list" class="flex-1 overflow-auto divide-y divide-slate-100"></div>
        <div class="p-3 border-t border-slate-200 shrink-0">
          <button id="msg-start-chat-btn" onclick="startNewChat()" disabled class="w-full py-2.5 bg-blue-500 hover:bg-blue-600 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl text-sm font-semibold transition">대화 시작</button>
        </div>
      </div>
      <!-- 단체 대화 탭 -->
      <div id="msg-group-panel" class="hidden flex-1 flex flex-col overflow-hidden">
        <div class="p-4 space-y-4 flex-1 overflow-auto">
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1.5">대화방 유형</label>
            <select id="msg-group-type" onchange="onGroupTypeChange()" class="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm bg-white focus:border-blue-400 outline-none">
              <option value="class">학급 단체방</option>
              <option value="grade">학년 단체방</option>
              <option value="school">학교 전체방</option>
            </select>
          </div>
          <div id="msg-group-grade-row">
            <label class="block text-xs font-bold text-slate-500 mb-1.5">학년</label>
            <select id="msg-group-grade" onchange="onGroupTypeChange()" class="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm bg-white focus:border-blue-400 outline-none">
              <option value="1">1학년</option>
              <option value="2">2학년</option>
              <option value="3">3학년</option>
            </select>
          </div>
          <div id="msg-group-class-row">
            <label class="block text-xs font-bold text-slate-500 mb-1.5">반</label>
            <select id="msg-group-class" class="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm bg-white focus:border-blue-400 outline-none">
              <option value="1">1반</option><option value="2">2반</option><option value="3">3반</option><option value="4">4반</option>
              <option value="5">5반</option><option value="6">6반</option><option value="7">7반</option><option value="8">8반</option>
              <option value="9">9반</option><option value="10">10반</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1.5">대상 역할</label>
            <div class="flex flex-wrap gap-2" id="msg-group-roles">
              <label class="flex items-center gap-1.5 text-sm"><input type="checkbox" value="teacher" class="rounded border-slate-300 text-blue-500 focus:ring-blue-400"> 교사</label>
              <label class="flex items-center gap-1.5 text-sm"><input type="checkbox" value="student" checked class="rounded border-slate-300 text-blue-500 focus:ring-blue-400"> 학생</label>
              <label class="flex items-center gap-1.5 text-sm"><input type="checkbox" value="parent" class="rounded border-slate-300 text-blue-500 focus:ring-blue-400"> 학부모</label>
            </div>
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-500 mb-1.5">대화방 이름 (선택)</label>
            <input id="msg-group-title" type="text" placeholder="자동 생성됨" class="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm focus:border-blue-400 outline-none">
          </div>
          <div>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" id="msg-group-announce" class="rounded border-slate-300 text-blue-500 focus:ring-blue-400">
              공지 전용 (관리자만 메시지 전송 가능)
            </label>
          </div>
        </div>
        <div class="p-3 border-t border-slate-200 shrink-0">
          <button id="msg-create-group-btn" onclick="createGroupRoom()" class="w-full py-2.5 bg-blue-500 hover:bg-blue-600 text-white rounded-xl text-sm font-semibold transition">단체 대화방 만들기</button>
        </div>
      </div>
    </div>

    <!-- 채팅 -->
    <div id="msg-chat-view" class="hidden flex-1 flex flex-col overflow-hidden">
      <div id="msg-chat-messages" class="flex-1 overflow-auto p-4 space-y-3 bg-slate-50"></div>
      <div class="p-3 border-t border-slate-200 bg-white flex items-center gap-2 shrink-0">
        <label class="w-9 h-9 shrink-0 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center cursor-pointer transition text-slate-500">
          <i class="fas fa-paperclip"></i>
          <input type="file" id="msg-file-input" class="hidden" onchange="handlePopupFile(this)">
        </label>
        <input id="msg-chat-input" type="text" placeholder="메시지 입력..." class="flex-1 px-3 py-2 rounded-lg border border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none text-sm" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendPopupMsg()}">
        <button onclick="sendPopupMsg()" class="w-9 h-9 shrink-0 rounded-lg bg-blue-500 hover:bg-blue-600 text-white flex items-center justify-center transition"><i class="fas fa-paper-plane text-sm"></i></button>
      </div>
    </div>
  </div>
</div>`);
    };

    /* ── 뷰 전환 헬퍼 ── */
    function _hideAll(){
        ['msg-list-view','msg-new-view','msg-chat-view'].forEach(id=>document.getElementById(id).classList.add('hidden'));
    }
    function _showBack(fn){
        const btn=document.getElementById('msg-back-btn');
        btn.style.display='flex'; btn.classList.remove('hidden');
        btn.onclick=fn;
    }
    function _hideBack(){
        const btn=document.getElementById('msg-back-btn');
        btn.classList.add('hidden'); btn.style.display='';
    }

    /* ── 팝업 열기/닫기 ── */
    window.openMsgPopup = function(){
        document.getElementById('msg-popup-overlay').classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        showMsgList();
    };
    window.closeMsgPopup = function(){
        document.getElementById('msg-popup-overlay').classList.add('hidden');
        document.body.style.overflow = '';
        _roomId = null; _stopPoll();
    };
    window.msgGoBack = function(){ showMsgList(); };

    /* ── 목록 보기 ── */
    window.showMsgList = function(){
        _hideAll();
        document.getElementById('msg-list-view').classList.remove('hidden');
        _hideBack();
        document.getElementById('msg-popup-title').textContent = '메시지';
        const menuBtn=document.getElementById('msg-menu-btn');
        if(menuBtn){menuBtn.classList.add('hidden');menuBtn.style.display='';}
        const dd=document.getElementById('msg-room-dropdown');
        if(dd) dd.classList.add('hidden');
        _roomId = null; _stopPoll();
        _loadRooms();
    };

    function _loadRooms(){
        fetch('/api/message/rooms').then(r=>r.json()).then(data=>{
            if(!data.success) return;
            const el = document.getElementById('msg-popup-rooms');
            const rooms = data.rooms || [];
            if(!rooms.length){
                el.innerHTML='<div class="text-center py-12 text-slate-300"><i class="fas fa-comments text-4xl mb-3"></i><p class="text-sm font-medium">메시지가 없습니다.</p><p class="text-xs mt-1">위의 "새 대화" 버튼으로 시작하세요.</p></div>';
                return;
            }
            let h='';
            rooms.forEach(r=>{
                const u=r.unread_count||0, lm=r.last_message||'';
                const pv=lm.length>30?lm.substring(0,30)+'...':lm;
                const tm=r.last_msg_time?_fmtTime(r.last_msg_time):'';
                const tt=_roomTitle(r);
                const bd=u>0?`<span class="w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold shrink-0">${u>99?'99+':u}</span>`:'';
                const rt=r.room_type||'direct';
                const leaveLabel=rt==='direct'?'대화방 삭제':'대화방 나가기';
                h+=`<div onclick="openMsgChat(${r.id})" class="group flex items-center gap-3 px-4 py-3 hover:bg-slate-50 cursor-pointer transition ${u>0?'bg-blue-50/50':''}">
                  <div class="w-10 h-10 shrink-0 rounded-full bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center text-white text-sm font-bold">${tt[0]}</div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-2"><p class="text-sm font-semibold text-slate-700 truncate">${tt}</p><span class="text-xs text-slate-400 shrink-0">${tm}</span></div>
                    <p class="text-xs ${u>0?'font-semibold text-slate-700':'text-slate-400'} truncate mt-0.5">${pv||'새 대화방'}</p>
                  </div>${bd}<button onclick="event.stopPropagation();leaveRoom(${r.id},'${rt}')" class="w-7 h-7 shrink-0 rounded-lg hover:bg-red-100 flex items-center justify-center text-slate-300 hover:text-red-500 transition opacity-0 group-hover:opacity-100 sm:opacity-0" style="touch-action:manipulation" title="${leaveLabel}"><i class="fas fa-times text-xs"></i></button></div>`;
            });
            el.innerHTML=h;
        }).catch(()=>{});
    }

    /* ── 새 대화 ── */
    window.showNewChat = function(){
        _hideAll();
        document.getElementById('msg-new-view').classList.remove('hidden');
        document.getElementById('msg-popup-title').textContent = '새 대화';
        _showBack(showMsgList);
        switchNewTab('person');
    };

    window.switchNewTab = function(tab){
        const pBtn=document.getElementById('msg-tab-person'), gBtn=document.getElementById('msg-tab-group');
        const pPanel=document.getElementById('msg-person-panel'), gPanel=document.getElementById('msg-group-panel');
        if(tab==='person'){
            pBtn.className='flex-1 py-2.5 text-sm font-semibold text-blue-600 border-b-2 border-blue-500 transition';
            gBtn.className='flex-1 py-2.5 text-sm font-semibold text-slate-400 border-b-2 border-transparent hover:text-slate-600 transition';
            pPanel.classList.remove('hidden'); gPanel.classList.add('hidden');
            _selectedContacts = {};
            _updateSelectedTags();
            document.getElementById('msg-contact-search').value = '';
            document.getElementById('msg-role-filter').value = '';
            searchContacts();
        } else {
            gBtn.className='flex-1 py-2.5 text-sm font-semibold text-blue-600 border-b-2 border-blue-500 transition';
            pBtn.className='flex-1 py-2.5 text-sm font-semibold text-slate-400 border-b-2 border-transparent hover:text-slate-600 transition';
            gPanel.classList.remove('hidden'); pPanel.classList.add('hidden');
            document.getElementById('msg-group-type').value='class';
            document.getElementById('msg-group-title').value='';
            document.getElementById('msg-group-announce').checked=false;
            onGroupTypeChange();
        }
    };

    window.onGroupTypeChange = function(){
        const type=document.getElementById('msg-group-type').value;
        document.getElementById('msg-group-grade-row').style.display = type==='school'?'none':'';
        document.getElementById('msg-group-class-row').style.display = type==='class'?'':'none';
    };

    window.createGroupRoom = function(){
        const type=document.getElementById('msg-group-type').value;
        const grade=document.getElementById('msg-group-grade').value;
        const classNo=document.getElementById('msg-group-class').value;
        const title=document.getElementById('msg-group-title').value.trim();
        const announce=document.getElementById('msg-group-announce').checked;
        const roleEls=document.querySelectorAll('#msg-group-roles input:checked');
        const roles=Array.from(roleEls).map(el=>el.value);
        if(!roles.length){ alert('대상 역할을 하나 이상 선택해주세요.'); return; }

        const btn=document.getElementById('msg-create-group-btn');
        btn.disabled=true; btn.textContent='생성 중...';

        const body={room_type:type, target_roles:roles, announcement_only:announce};
        if(title) body.room_title=title;
        if(type!=='school') body.class_grade=grade;
        if(type==='class') body.class_no=classNo;

        fetch('/api/message/room/create',{
            method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
        }).then(r=>r.json()).then(data=>{
            if(data.success){
                openMsgChat(data.room_id);
                if(typeof loadDashMessages==='function') loadDashMessages();
            } else {
                alert(data.message||'대화방 생성 실패');
            }
            btn.disabled=false; btn.textContent='단체 대화방 만들기';
        }).catch(()=>{
            alert('대화방 생성 중 오류');
            btn.disabled=false; btn.textContent='단체 대화방 만들기';
        });
    };

    window.searchContacts = function(){
        const role = document.getElementById('msg-role-filter').value;
        const search = document.getElementById('msg-contact-search').value.trim();
        let url = `/api/message/users?role=${encodeURIComponent(role)}&search=${encodeURIComponent(search)}`;
        fetch(url).then(r=>r.json()).then(data=>{
            if(!data.success) return;
            const el = document.getElementById('msg-contact-list');
            const users = data.users || [];
            if(!users.length){
                el.innerHTML='<div class="text-center py-12 text-slate-300"><p class="text-sm">검색 결과가 없습니다.</p></div>';
                return;
            }
            let h='';
            users.forEach(u=>{
                const sel = _selectedContacts[u.member_id] ? true : false;
                const roleLabel = {teacher:'교사',student:'학생',parent:'학부모'}[u.member_role]||u.member_role;
                const gradeInfo = u.class_grade ? `${u.class_grade}학년${u.class_no?` ${u.class_no}반`:''}` : '';
                const sub = [roleLabel, gradeInfo].filter(Boolean).join(' · ');
                h+=`<div onclick="toggleContact('${_esc(u.member_id)}','${_esc(u.member_name)}','${_esc(u.member_role)}')" class="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 cursor-pointer transition ${sel?'bg-blue-50':''}">
                  <div class="w-9 h-9 shrink-0 rounded-full ${sel?'bg-blue-500':'bg-gradient-to-br from-slate-300 to-slate-400'} flex items-center justify-center text-white text-sm font-bold transition">${sel?'<i class="fas fa-check text-xs"></i>':_esc(u.member_name[0])}</div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-semibold text-slate-700">${_esc(u.member_name)}</p>
                    <p class="text-xs text-slate-400">${sub}</p>
                  </div>
                </div>`;
            });
            el.innerHTML=h;
        }).catch(()=>{});
    };

    window.onContactSearch = function(){
        if(_searchTimer) clearTimeout(_searchTimer);
        _searchTimer = setTimeout(searchContacts, 300);
    };

    window.toggleContact = function(id, name, role){
        if(_selectedContacts[id]){
            delete _selectedContacts[id];
        } else {
            _selectedContacts[id] = {name, role};
        }
        _updateSelectedTags();
        searchContacts();  // re-render to update check marks
    };

    function _updateSelectedTags(){
        const el = document.getElementById('msg-selected-tags');
        const btn = document.getElementById('msg-start-chat-btn');
        const ids = Object.keys(_selectedContacts);
        if(!ids.length){
            el.innerHTML='<span class="text-xs text-slate-400">대화할 상대를 선택하세요</span>';
            btn.disabled = true;
            return;
        }
        let h='';
        ids.forEach(id=>{
            const c = _selectedContacts[id];
            h+=`<span class="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">${_esc(c.name)}<button onclick="event.stopPropagation();toggleContact('${_esc(id)}','${_esc(c.name)}','${_esc(c.role)}')" class="hover:text-blue-900"><i class="fas fa-times text-[10px]"></i></button></span>`;
        });
        el.innerHTML=h;
        btn.disabled = false;
        btn.textContent = ids.length === 1 ? '1:1 대화 시작' : `그룹 대화 시작 (${ids.length}명)`;
    }

    window.startNewChat = function(){
        const ids = Object.keys(_selectedContacts);
        if(!ids.length) return;
        const btn = document.getElementById('msg-start-chat-btn');
        btn.disabled = true; btn.textContent = '생성 중...';

        const roomType = ids.length === 1 ? 'direct' : 'group';
        fetch('/api/message/room/create',{
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({room_type:roomType, target_ids:ids})
        }).then(r=>r.json()).then(data=>{
            if(data.success){
                openMsgChat(data.room_id);
                if(typeof loadDashMessages==='function') loadDashMessages();
            } else {
                alert(data.message||'대화방 생성 실패');
                btn.disabled=false; btn.textContent='대화 시작';
            }
        }).catch(()=>{
            alert('대화방 생성 중 오류');
            btn.disabled=false; btn.textContent='대화 시작';
        });
    };

    /* ── 채팅 보기 ── */
    window.openMsgChat = function(roomId){
        const ov=document.getElementById('msg-popup-overlay');
        if(ov.classList.contains('hidden')){ov.classList.remove('hidden');document.body.style.overflow='hidden';}
        _roomId=roomId; _lastMsgId=0;
        _hideAll();
        document.getElementById('msg-chat-view').classList.remove('hidden');
        _showBack(showMsgList);
        document.getElementById('msg-popup-title').textContent='로딩...';
        document.getElementById('msg-chat-messages').innerHTML='<div class="text-center py-8 text-slate-300"><i class="fas fa-spinner fa-spin text-2xl"></i></div>';
        document.getElementById('msg-chat-input').value='';

        // 메뉴 버튼 표시
        const menuBtn=document.getElementById('msg-menu-btn');
        menuBtn.style.display='flex'; menuBtn.classList.remove('hidden');
        document.getElementById('msg-room-dropdown').classList.add('hidden');

        fetch(`/api/message/list?room_id=${roomId}`).then(r=>r.json()).then(data=>{
            if(!data.success) return;
            _currentRoomType=data.room?.room_type||'direct';
            document.getElementById('msg-leave-text').textContent=_currentRoomType==='direct'?'대화방 삭제':'대화방 나가기';
            let tt;
            if(data.room?.room_type&&['class','grade','school'].includes(data.room.room_type)&&data.room.room_title){tt=data.room.room_title;}
            else if(data.members){const o=data.members.filter(m=>m.member_id!==_myId); tt=o.length?o.map(m=>m.member_name).join(', '):'대화방';}
            else{tt=data.room?.room_title||'대화방';}
            document.getElementById('msg-popup-title').textContent=tt;
            _renderMsgs(data.messages||[]);
            fetch('/api/message/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room_id:roomId})}).catch(()=>{});
            _stopPoll();
            _pollTimer=setInterval(()=>_pollChat(roomId),5000);
        }).catch(()=>{});
    };

    function _renderMsgs(msgs){
        const c=document.getElementById('msg-chat-messages');
        if(!msgs.length){c.innerHTML='<div class="text-center py-16 text-slate-300"><i class="fas fa-comments text-3xl mb-2"></i><p class="text-sm">대화를 시작해보세요!</p></div>';return;}
        let h='',ld='';
        msgs.forEach(m=>{
            const md=m.created_at?m.created_at.split(' ')[0]:'';
            if(md&&md!==ld){ld=md;const tdy=new Date().toISOString().split('T')[0];const yst=new Date(Date.now()-86400000).toISOString().split('T')[0];let dl=md;if(md===tdy)dl='오늘';else if(md===yst)dl='어제';h+=`<div class="flex items-center gap-3 my-2"><div class="flex-1 border-t border-slate-200"></div><span class="text-xs text-slate-400 shrink-0">${dl}</span><div class="flex-1 border-t border-slate-200"></div></div>`;}
            h+=_msgBubble(m);
            if(m.id>_lastMsgId)_lastMsgId=m.id;
        });
        c.innerHTML=h;
        c.scrollTop=c.scrollHeight;
    }

    function _msgBubble(m){
        const t=m.created_at?m.created_at.split(' ')[1]?.substring(0,5):'';
        if(m.is_system) return `<div class="text-center"><span class="text-xs text-slate-400 bg-slate-100 rounded-full px-3 py-1">${_esc(m.content)}</span></div>`;
        const file=_fileHtml(m);
        const text=(m.content&&!m.content.startsWith('[파일]'))?m.content:'';
        if(m.is_mine){
            return `<div class="flex justify-end items-end gap-2"><span class="text-[10px] text-slate-400 shrink-0">${t}</span><div class="max-w-[70%]">${file}${text?`<div class="bg-blue-500 text-white rounded-2xl rounded-br-md px-4 py-2 text-sm break-words">${_esc(text)}</div>`:''}</div></div>`;
        } else {
            return `<div class="flex items-end gap-2"><div class="w-8 h-8 shrink-0 rounded-full bg-gradient-to-br from-slate-300 to-slate-400 flex items-center justify-center text-white text-xs font-bold self-start mt-1">${(m.sender_name||'?')[0]}</div><div class="max-w-[70%]"><p class="text-xs text-slate-500 font-medium mb-1">${_esc(m.sender_name||'')}</p>${file}${text?`<div class="bg-white border border-slate-200 rounded-2xl rounded-bl-md px-4 py-2 text-sm text-slate-700 break-words shadow-sm">${_esc(text)}</div>`:''}</div><span class="text-[10px] text-slate-400 shrink-0">${t}</span></div>`;
        }
    }

    function _fileHtml(m){
        if(!m.file_name) return '';
        const url=`/api/message/file/download?message_id=${m.id}`;
        if(m.message_type==='image') return `<img src="${url}" class="rounded-lg max-w-full max-h-48 cursor-pointer mb-1" onclick="window.open(this.src)" alt="${_esc(m.file_name)}">`;
        const cls=m.is_mine?'bg-blue-400/30 text-white hover:bg-blue-400/50':'bg-slate-100 text-slate-600 hover:bg-slate-200';
        return `<a href="${url}" target="_blank" class="flex items-center gap-2 ${cls} rounded-lg px-3 py-2 mb-1 transition text-xs"><i class="fas fa-file-download"></i>${_esc(m.file_name)}</a>`;
    }

    /* ── 폴링 ── */
    function _pollChat(roomId){
        if(_roomId!==roomId) return;
        fetch(`/api/message/poll?room_id=${roomId}&after_id=${_lastMsgId}`).then(r=>r.json()).then(data=>{
            if(!data.success||!data.messages||!data.messages.length) return;
            const c=document.getElementById('msg-chat-messages');
            const scroll=c.scrollHeight-c.scrollTop-c.clientHeight<100;
            data.messages.forEach(m=>{
                if(m.id<=_lastMsgId) return;
                _lastMsgId=m.id;
                c.insertAdjacentHTML('beforeend',_msgBubble(m));
            });
            if(scroll) c.scrollTop=c.scrollHeight;
            fetch('/api/message/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room_id:roomId})}).catch(()=>{});
        }).catch(()=>{});
    }
    function _stopPoll(){if(_pollTimer){clearInterval(_pollTimer);_pollTimer=null;}}

    /* ── 메시지 전송 ── */
    window.sendPopupMsg = function(){
        if(!_roomId) return;
        const inp=document.getElementById('msg-chat-input');
        const txt=inp.value.trim(); if(!txt) return; inp.value='';
        fetch('/api/message/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room_id:_roomId,content:txt})}).then(r=>r.json()).then(d=>{
            if(d.success){_pollChat(_roomId);if(typeof loadDashMessages==='function')loadDashMessages();}
        }).catch(()=>{});
    };

    /* ── 파일 첨부 ── */
    window.handlePopupFile = function(inp){
        if(!_roomId||!inp.files||!inp.files[0]) return;
        const fd=new FormData(); fd.append('room_id',_roomId); fd.append('file',inp.files[0]);
        fetch('/api/message/file/upload',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
            if(d.success){_pollChat(_roomId);if(typeof loadDashMessages==='function')loadDashMessages();}
            else alert(d.message||'파일 업로드 실패');
        }).catch(()=>alert('파일 업로드 중 오류'));
        inp.value='';
    };

    /* ── 대화방 나가기/삭제 ── */
    window.leaveRoom = function(roomId, roomType){
        const label = roomType==='direct' ? '삭제' : '나가기';
        if(!confirm('대화방을 '+label+'하시겠습니까?')) return;
        fetch('/api/message/room/leave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room_id:roomId})}).then(r=>r.json()).then(data=>{
            if(data.success){_loadRooms();if(typeof loadDashMessages==='function')loadDashMessages();}
            else alert(data.message||'처리 실패');
        }).catch(()=>alert('오류가 발생했습니다.'));
    };

    window.leaveCurrentRoom = function(){
        if(!_roomId) return;
        const label = _currentRoomType==='direct' ? '삭제' : '나가기';
        if(!confirm('대화방을 '+label+'하시겠습니까?')) return;
        const rid=_roomId;
        fetch('/api/message/room/leave',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room_id:rid})}).then(r=>r.json()).then(data=>{
            if(data.success){showMsgList();if(typeof loadDashMessages==='function')loadDashMessages();}
            else alert(data.message||'처리 실패');
        }).catch(()=>alert('오류가 발생했습니다.'));
    };

    window.toggleRoomMenu = function(e){
        if(e) e.stopPropagation();
        const dd=document.getElementById('msg-room-dropdown');
        dd.classList.toggle('hidden');
    };

    document.addEventListener('click',function(e){
        const dd=document.getElementById('msg-room-dropdown');
        const btn=document.getElementById('msg-menu-btn');
        if(dd&&btn&&!dd.contains(e.target)&&!btn.contains(e.target)){dd.classList.add('hidden');}
    });

    /* ── 유틸 ── */
    function _roomTitle(r){
        // class/grade/school 단체방은 고정 제목 사용
        if(r.room_title&&r.room_type&&['class','grade','school'].includes(r.room_type)) return r.room_title;
        // direct/group은 멤버에서 자신을 제외하고 동적 표시
        if(r.members){const o=r.members.filter(m=>m.member_id!==_myId); if(o.length) return o.map(m=>m.member_name).join(', ');}
        return r.room_title||'대화방';
    }
    function _fmtTime(t){if(!t)return '';const d=new Date(t.replace(' ','T'));const n=new Date();const df=n-d;if(df<60000)return '방금';if(df<3600000)return Math.floor(df/60000)+'분 전';if(df<86400000)return Math.floor(df/3600000)+'시간 전';if(df<604800000)return Math.floor(df/86400000)+'일 전';return(d.getMonth()+1)+'/'+d.getDate();}
    function _esc(s){if(!s)return '';return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
})();
