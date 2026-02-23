/**
 * SchoolUs 메신저 팝업 위젯
 * - 모든 대시보드 페이지(tea/st/fm)에 include하여 사용
 * - 헤더 아이콘 클릭 시 우측 슬라이드 패널로 열림
 * - 30초 폴링, 60초 뱃지 폴링 내장
 */
(function() {
    'use strict';

    let _user = null;
    let _convList = [];
    let _currentConvId = null;
    let _selectedContacts = [];
    let _allContacts = [];
    let _pollTimer = null;
    let _badgeTimer = null;
    let _roleFilter = '';
    let _panelOpen = false;

    // ── HTML 주입 ──
    function injectHTML() {
        // CSS
        const style = document.createElement('style');
        style.textContent = `
            #msg-panel-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.3); z-index:900; transition:opacity .2s; }
            #msg-panel-overlay.active { display:block; }
            #msg-slide-panel {
                position:fixed; top:0; right:-440px; width:420px; max-width:100vw; height:100vh;
                background:white; z-index:910; box-shadow:-4px 0 30px rgba(0,0,0,0.15);
                transition:right .3s cubic-bezier(.4,0,.2,1); display:flex; flex-direction:column;
            }
            #msg-slide-panel.open { right:0; }
            @media(max-width:480px){ #msg-slide-panel { width:100vw; right:-100vw; } }

            .mp-header { height:56px; background:linear-gradient(135deg,#3b82f6,#2563eb); color:white; display:flex; align-items:center; padding:0 16px; gap:12px; flex-shrink:0; }
            .mp-header h3 { font-size:16px; font-weight:800; flex:1; }
            .mp-header button { background:none; border:none; color:rgba(255,255,255,0.8); cursor:pointer; font-size:18px; padding:4px 8px; }
            .mp-header button:hover { color:white; }

            .mp-conv-list { flex:1; overflow-y:auto; }
            .mp-conv-item { display:flex; align-items:center; gap:12px; padding:12px 16px; cursor:pointer; border-bottom:1px solid #f1f5f9; transition:background .15s; }
            .mp-conv-item:hover { background:#f0f9ff; }
            .mp-conv-item.active { background:#eff6ff; border-left:3px solid #3b82f6; }
            .mp-conv-avatar { width:40px; height:40px; border-radius:50%; background:linear-gradient(135deg,#3b82f6,#6366f1); display:flex; align-items:center; justify-content:center; color:white; font-weight:700; font-size:14px; flex-shrink:0; }
            .mp-conv-info { flex:1; min-width:0; }
            .mp-conv-name { font-size:13px; font-weight:700; color:#1e293b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .mp-conv-preview { font-size:12px; color:#94a3b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; }
            .mp-conv-meta { display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex-shrink:0; }
            .mp-conv-time { font-size:11px; color:#94a3b8; }
            .mp-unread { min-width:18px; height:18px; background:#ef4444; color:white; font-size:10px; font-weight:700; border-radius:9px; display:flex; align-items:center; justify-content:center; padding:0 5px; }

            .mp-search-bar { padding:12px 16px; border-bottom:1px solid #f1f5f9; }
            .mp-search-bar input { width:100%; padding:8px 12px 8px 34px; background:#f1f5f9; border:none; border-radius:10px; font-size:13px; outline:none; }
            .mp-search-bar input:focus { box-shadow:0 0 0 2px rgba(59,130,246,0.3); }
            .mp-search-bar i { position:absolute; left:28px; top:50%; transform:translateY(-50%); color:#94a3b8; font-size:13px; }

            .mp-new-btn { position:absolute; bottom:16px; right:16px; width:48px; height:48px; background:linear-gradient(135deg,#3b82f6,#2563eb); color:white; border:none; border-radius:50%; font-size:20px; cursor:pointer; box-shadow:0 4px 15px rgba(59,130,246,0.4); transition:transform .2s; z-index:5; }
            .mp-new-btn:hover { transform:scale(1.1); }

            /* 메시지 뷰 */
            .mp-msg-header { height:52px; background:white; border-bottom:1px solid #e2e8f0; display:flex; align-items:center; padding:0 12px; gap:10px; flex-shrink:0; }
            .mp-msg-header .mp-back { background:none; border:none; cursor:pointer; color:#64748b; font-size:16px; padding:4px; }
            .mp-msg-header .mp-partner-name { font-weight:700; font-size:14px; color:#1e293b; flex:1; }
            .mp-msg-header .mp-partner-role { font-size:11px; color:#94a3b8; }
            .mp-msg-header .mp-leave-btn { background:#fef2f2; border:1px solid #fecaca; cursor:pointer; color:#ef4444; font-size:12px; font-weight:600; padding:5px 10px; border-radius:8px; display:flex; align-items:center; gap:4px; transition:all .15s; }
            .mp-msg-header .mp-leave-btn:hover { background:#fee2e2; border-color:#fca5a5; }

            .mp-msg-area { flex:1; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:8px; background:linear-gradient(180deg,#f8fafc,#fff); }
            .mp-date-sep { display:flex; align-items:center; gap:8px; color:#94a3b8; font-size:11px; margin:8px 0; }
            .mp-date-sep::before,.mp-date-sep::after { content:''; flex:1; height:1px; background:#e2e8f0; }

            .mp-bubble-row { display:flex; gap:8px; }
            .mp-bubble-row.mine { justify-content:flex-end; }
            .mp-bubble { max-width:75%; padding:10px 14px; font-size:13px; line-height:1.5; word-break:break-word; }
            .mp-bubble.mine { background:linear-gradient(135deg,#3b82f6,#2563eb); color:white; border-radius:16px 16px 4px 16px; }
            .mp-bubble.other { background:white; border:1px solid #e2e8f0; color:#1e293b; border-radius:16px 16px 16px 4px; }
            .mp-bubble .file-link { display:flex; align-items:center; gap:4px; margin-top:6px; font-size:11px; }
            .mp-bubble.mine .file-link { color:rgba(255,255,255,0.8); }
            .mp-bubble.mine .file-link a { color:rgba(255,255,255,0.9); text-decoration:underline; }
            .mp-bubble.other .file-link a { color:#3b82f6; text-decoration:underline; }
            .mp-bubble-time { font-size:10px; color:#94a3b8; align-self:flex-end; flex-shrink:0; }
            .mp-sender-avatar { width:28px; height:28px; border-radius:50%; background:linear-gradient(135deg,#94a3b8,#64748b); display:flex; align-items:center; justify-content:center; color:white; font-size:11px; font-weight:700; flex-shrink:0; }
            .mp-sender-name { font-size:11px; color:#64748b; font-weight:600; margin-bottom:2px; }
            .mp-del-btn { font-size:10px; color:#cbd5e1; cursor:pointer; border:none; background:none; margin-top:2px; }
            .mp-del-btn:hover { color:#ef4444; }

            .mp-input-area { border-top:1px solid #e2e8f0; padding:10px 12px; background:white; display:flex; align-items:flex-end; gap:8px; flex-shrink:0; }
            .mp-input-area textarea { flex:1; padding:8px 12px; background:#f1f5f9; border:none; border-radius:12px; font-size:13px; resize:none; outline:none; max-height:80px; font-family:inherit; }
            .mp-input-area textarea:focus { box-shadow:0 0 0 2px rgba(59,130,246,0.3); }
            .mp-input-area button { width:36px; height:36px; border:none; border-radius:50%; cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
            .mp-attach-btn { background:#f1f5f9; color:#64748b; font-size:14px; }
            .mp-attach-btn:hover { background:#e2e8f0; }
            .mp-send-btn { background:linear-gradient(135deg,#3b82f6,#2563eb); color:white; font-size:14px; box-shadow:0 2px 8px rgba(59,130,246,0.3); }
            .mp-file-preview { display:flex; align-items:center; gap:6px; padding:6px 10px; background:#eff6ff; border-radius:8px; font-size:12px; color:#3b82f6; margin-bottom:6px; }
            .mp-file-preview .mp-file-remove { cursor:pointer; color:#93c5fd; }
            .mp-file-preview .mp-file-remove:hover { color:#ef4444; }

            .mp-empty { display:flex; flex-direction:column; align-items:center; justify-content:center; flex:1; color:#94a3b8; text-align:center; padding:40px 20px; }
            .mp-empty i { font-size:40px; margin-bottom:12px; color:#cbd5e1; }
            .mp-empty p { font-size:13px; }

            /* 새 대화 모달 */
            #mp-new-modal { display:none; position:fixed; inset:0; z-index:920; background:rgba(0,0,0,0.5); align-items:center; justify-content:center; padding:16px; }
            #mp-new-modal.active { display:flex; }
            .mp-modal-box { background:white; border-radius:16px; width:100%; max-width:380px; max-height:75vh; display:flex; flex-direction:column; box-shadow:0 20px 60px rgba(0,0,0,0.2); }
            .mp-modal-header { padding:16px 20px; border-bottom:1px solid #f1f5f9; display:flex; align-items:center; justify-content:space-between; }
            .mp-modal-header h4 { font-size:16px; font-weight:800; color:#1e293b; }
            .mp-modal-header button { background:none; border:none; cursor:pointer; color:#94a3b8; font-size:18px; }
            .mp-modal-filters { display:flex; gap:6px; padding:12px 16px; border-bottom:1px solid #f1f5f9; flex-wrap:wrap; }
            .mp-filter-btn { padding:5px 12px; font-size:12px; font-weight:700; border-radius:8px; border:none; cursor:pointer; background:#f1f5f9; color:#64748b; transition:all .15s; }
            .mp-filter-btn.active { background:#3b82f6; color:white; }
            .mp-modal-search { padding:8px 16px; position:relative; }
            .mp-modal-search input { width:100%; padding:8px 12px 8px 32px; background:#f1f5f9; border:none; border-radius:10px; font-size:13px; outline:none; }
            .mp-modal-search i { position:absolute; left:28px; top:50%; transform:translateY(-50%); color:#94a3b8; font-size:12px; }
            .mp-contact-list { flex:1; overflow-y:auto; padding:4px 8px; min-height:0; max-height:300px; }
            .mp-contact-item { display:flex; align-items:center; gap:10px; padding:8px 10px; border-radius:10px; cursor:pointer; transition:background .15s; }
            .mp-contact-item:hover { background:#f8fafc; }
            .mp-contact-item.selected { background:#eff6ff; outline:1px solid #bfdbfe; }
            .mp-contact-avatar { width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:white; font-size:13px; font-weight:700; flex-shrink:0; }
            .mp-contact-info { flex:1; min-width:0; }
            .mp-contact-name { font-size:13px; font-weight:700; color:#1e293b; }
            .mp-contact-detail { font-size:11px; color:#94a3b8; }
            .mp-contact-check { width:18px; height:18px; border-radius:50%; border:2px solid #cbd5e1; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
            .mp-contact-check.checked { border-color:#3b82f6; background:#3b82f6; }
            .mp-modal-footer { padding:12px 16px; border-top:1px solid #f1f5f9; display:flex; align-items:center; justify-content:space-between; }
            .mp-modal-footer .mp-sel-names { font-size:12px; color:#3b82f6; font-weight:600; flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
            .mp-start-btn { padding:8px 20px; background:linear-gradient(135deg,#3b82f6,#2563eb); color:white; border:none; border-radius:10px; font-size:13px; font-weight:700; cursor:pointer; box-shadow:0 2px 8px rgba(59,130,246,0.3); }
            .mp-start-btn:hover { opacity:0.9; }
        `;
        document.head.appendChild(style);

        // Panel HTML
        const panelHTML = `
        <div id="msg-panel-overlay"></div>
        <div id="msg-slide-panel">
            <!-- 대화 목록 뷰 -->
            <div id="mp-list-view" style="display:flex;flex-direction:column;height:100%;">
                <div class="mp-header">
                    <i class="fas fa-comments"></i>
                    <h3>메신저</h3>
                    <button onclick="window._mpClose()" title="닫기"><i class="fas fa-times"></i></button>
                </div>
                <div class="mp-search-bar" style="position:relative;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="mp-conv-search" placeholder="대화 검색..." oninput="window._mpFilterConv()">
                </div>
                <div id="mp-conv-list" class="mp-conv-list" style="position:relative;">
                    <div class="mp-empty"><i class="fas fa-comments"></i><p>대화가 없습니다<br><small>새 대화를 시작해보세요</small></p></div>
                </div>
                <button class="mp-new-btn" onclick="window._mpOpenNew()" title="새 대화"><i class="fas fa-plus"></i></button>
            </div>

            <!-- 메시지 뷰 -->
            <div id="mp-msg-view" style="display:none;flex-direction:column;height:100%;">
                <div class="mp-msg-header">
                    <button class="mp-back" onclick="window._mpBackToList()"><i class="fas fa-arrow-left"></i></button>
                    <div class="mp-conv-avatar" id="mp-msg-avatar" style="width:32px;height:32px;font-size:12px;">?</div>
                    <div style="flex:1;min-width:0;">
                        <div class="mp-partner-name" id="mp-msg-name">-</div>
                        <div class="mp-partner-role" id="mp-msg-role"></div>
                    </div>
                    <button class="mp-leave-btn" onclick="window._mpLeave()" title="나가기"><i class="fas fa-sign-out-alt"></i> 나가기</button>
                </div>
                <div class="mp-msg-area" id="mp-msg-area"></div>
                <div id="mp-file-preview-bar" style="display:none;padding:4px 12px;">
                    <div class="mp-file-preview">
                        <i class="fas fa-file"></i>
                        <span id="mp-file-name" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
                        <span class="mp-file-remove" onclick="window._mpClearFile()"><i class="fas fa-times"></i></span>
                    </div>
                </div>
                <div class="mp-input-area">
                    <button class="mp-attach-btn" onclick="document.getElementById('mp-file-input').click()"><i class="fas fa-paperclip"></i></button>
                    <input type="file" id="mp-file-input" style="display:none" onchange="window._mpFileSelected(this)">
                    <textarea id="mp-msg-input" rows="1" placeholder="메시지 입력..." onkeydown="window._mpKeydown(event)" oninput="window._mpAutoResize()"></textarea>
                    <button class="mp-send-btn" onclick="window._mpSend()"><i class="fas fa-paper-plane"></i></button>
                </div>
            </div>
        </div>

        <!-- 새 대화 모달 -->
        <div id="mp-new-modal">
            <div class="mp-modal-box">
                <div class="mp-modal-header">
                    <h4>새 대화</h4>
                    <button onclick="window._mpCloseNew()"><i class="fas fa-times"></i></button>
                </div>
                <div id="mp-role-filters" class="mp-modal-filters"></div>
                <div class="mp-modal-search" style="position:relative;">
                    <i class="fas fa-search"></i>
                    <input type="text" id="mp-contact-search" placeholder="이름 검색..." oninput="window._mpSearchContacts()">
                </div>
                <div id="mp-contact-list" class="mp-contact-list">
                    <div class="mp-empty" style="padding:20px;"><p>로딩 중...</p></div>
                </div>
                <div class="mp-modal-footer" id="mp-modal-footer" style="display:none;">
                    <span class="mp-sel-names" id="mp-sel-names"></span>
                    <button class="mp-start-btn" onclick="window._mpStartConv()">대화 시작</button>
                </div>
            </div>
        </div>
        `;
        const div = document.createElement('div');
        div.innerHTML = panelHTML;
        document.body.appendChild(div);

        // 오버레이 클릭 시 닫기
        document.getElementById('msg-panel-overlay').addEventListener('click', () => window._mpClose());
    }

    // ── 패널 토글 ──
    window.toggleMessengerPanel = function() {
        if (_panelOpen) { window._mpClose(); }
        else { window._mpOpen(); }
    };

    window._mpOpen = function() {
        _panelOpen = true;
        document.getElementById('msg-panel-overlay').classList.add('active');
        document.getElementById('msg-slide-panel').classList.add('open');
        _loadConversations();
        // 30초 메시지 폴링 시작
        if (_pollTimer) clearInterval(_pollTimer);
        _pollTimer = setInterval(() => {
            if (document.visibilityState === 'visible' && _panelOpen) {
                if (_currentConvId) _loadMessages(_currentConvId, true);
                _loadConversations(true);
            }
        }, 30000);
    };

    window._mpClose = function() {
        _panelOpen = false;
        document.getElementById('msg-panel-overlay').classList.remove('active');
        document.getElementById('msg-slide-panel').classList.remove('open');
        if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
        // 목록 뷰로 리셋
        setTimeout(() => {
            document.getElementById('mp-list-view').style.display = 'flex';
            document.getElementById('mp-msg-view').style.display = 'none';
            _currentConvId = null;
        }, 300);
    };

    // ── 대화 목록 ──
    async function _loadConversations(silent) {
        if (!_user) return;
        try {
            const p = new URLSearchParams({ member_id: _user.member_id, school_id: _user.school_id || '' });
            const res = await fetch('/api/messenger/conversations?' + p);
            const data = await res.json();
            if (!data.success) return;
            _convList = data.conversations;
            _renderConvList(_convList);
        } catch(e) { if (!silent) console.error(e); }
    }

    function _renderConvList(list) {
        const el = document.getElementById('mp-conv-list');
        if (!list.length) {
            el.innerHTML = '<div class="mp-empty"><i class="fas fa-comments"></i><p>대화가 없습니다<br><small>새 대화를 시작해보세요</small></p></div>';
            return;
        }
        el.innerHTML = list.map(c => {
            const active = c.id === _currentConvId ? ' active' : '';
            const name = c.title || '(알 수 없음)';
            const avatar = name.charAt(0);
            const unread = c.unread_count > 0 ? `<div class="mp-unread">${c.unread_count > 99 ? '99+' : c.unread_count}</div>` : '';
            const time = c.last_msg_time ? _fmtTime(c.last_msg_time) : '';
            const preview = c.last_message ? _truncate(c.last_message, 25) : '대화를 시작하세요';
            return `<div class="mp-conv-item${active}" onclick="window._mpOpenConv(${c.id})">
                <div class="mp-conv-avatar">${_esc(avatar)}</div>
                <div class="mp-conv-info">
                    <div class="mp-conv-name">${_esc(name)}</div>
                    <div class="mp-conv-preview">${_esc(preview)}</div>
                </div>
                <div class="mp-conv-meta">
                    <div class="mp-conv-time">${time}</div>
                    ${unread}
                </div>
            </div>`;
        }).join('') + '<div style="height:60px"></div>';  // FAB 공간
    }

    window._mpFilterConv = function() {
        const kw = document.getElementById('mp-conv-search').value.trim().toLowerCase();
        if (!kw) { _renderConvList(_convList); return; }
        const f = _convList.filter(c =>
            (c.title || '').toLowerCase().includes(kw) ||
            (c.partners || []).some(p => p.name.toLowerCase().includes(kw))
        );
        _renderConvList(f);
    };

    // ── 대화 열기 ──
    window._mpOpenConv = async function(convId) {
        _currentConvId = convId;
        // 뷰 전환
        document.getElementById('mp-list-view').style.display = 'none';
        document.getElementById('mp-msg-view').style.display = 'flex';

        const conv = _convList.find(c => c.id === convId);
        if (conv) {
            const name = conv.title || '(알 수 없음)';
            document.getElementById('mp-msg-name').textContent = name;
            document.getElementById('mp-msg-avatar').textContent = name.charAt(0);
            document.getElementById('mp-msg-role').textContent = (conv.partners || []).map(p => _roleLabel(p.role)).join(', ');
        }
        await _loadMessages(convId);
    };

    window._mpBackToList = function() {
        _currentConvId = null;
        document.getElementById('mp-list-view').style.display = 'flex';
        document.getElementById('mp-msg-view').style.display = 'none';
        _loadConversations(true);
    };

    // ── 메시지 ──
    async function _loadMessages(convId, silent) {
        try {
            const p = new URLSearchParams({ member_id: _user.member_id, conversation_id: convId });
            const res = await fetch('/api/messenger/messages?' + p);
            const data = await res.json();
            if (!data.success) return;
            _renderMessages(data.messages);
        } catch(e) { if (!silent) console.error(e); }
    }

    function _renderMessages(msgs) {
        const area = document.getElementById('mp-msg-area');
        if (!msgs.length) {
            area.innerHTML = '<div class="mp-empty" style="padding:20px;"><i class="fas fa-paper-plane"></i><p>첫 메시지를 보내보세요!</p></div>';
            return;
        }
        let html = '';
        let lastDate = '';
        for (const m of msgs) {
            const d = m.created_at.split(' ')[0];
            if (d !== lastDate) { lastDate = d; html += `<div class="mp-date-sep">${_fmtDateLabel(d)}</div>`; }
            const time = m.created_at.split(' ')[1]?.substring(0,5) || '';
            const content = m.is_deleted ? '<em style="opacity:.6">삭제된 메시지</em>' : _esc(m.content);
            const fileHtml = m.has_file && !m.is_deleted ? `<div class="file-link"><i class="fas fa-file"></i> <a href="/api/messenger/file/download?member_id=${_user.member_id}&message_id=${m.id}" target="_blank">${_esc(m.file_name)}</a></div>` : '';

            if (m.is_mine) {
                html += `<div class="mp-bubble-row mine">
                    <div class="mp-bubble-time">${time}</div>
                    <div class="mp-bubble mine">${content}${fileHtml}</div>
                </div>`;
                if (!m.is_deleted) html += `<div style="display:flex;justify-content:flex-end;"><button class="mp-del-btn" onclick="window._mpDeleteMsg(${m.id})">삭제</button></div>`;
            } else {
                html += `<div class="mp-bubble-row">
                    <div class="mp-sender-avatar">${_esc((m.sender_name||'?').charAt(0))}</div>
                    <div>
                        <div class="mp-sender-name">${_esc(m.sender_name)}</div>
                        <div class="mp-bubble other">${content}${fileHtml}</div>
                    </div>
                    <div class="mp-bubble-time">${time}</div>
                </div>`;
            }
        }
        area.innerHTML = html;
        area.scrollTop = area.scrollHeight;
    }

    // ── 메시지 전송 ──
    window._mpSend = async function() {
        const input = document.getElementById('mp-msg-input');
        const content = input.value.trim();
        const fileInput = document.getElementById('mp-file-input');
        const file = fileInput.files[0];
        if (!content && !file) return;
        if (!_currentConvId) return;

        const fd = new FormData();
        fd.append('conversation_id', _currentConvId);
        fd.append('content', content);
        if (file) fd.append('file', file);

        try {
            const res = await fetch('/api/messenger/messages/send', { method: 'POST', body: fd });
            const data = await res.json();
            if (data.success) {
                input.value = ''; input.style.height = 'auto';
                window._mpClearFile();
                await _loadMessages(_currentConvId);
                _loadConversations(true);
            } else { alert(data.message || '전송 실패'); }
        } catch(e) { alert('전송 오류'); }
    };

    window._mpKeydown = function(e) {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window._mpSend(); }
    };
    window._mpAutoResize = function() {
        const el = document.getElementById('mp-msg-input');
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 80) + 'px';
    };

    // ── 파일 ──
    window._mpFileSelected = function(input) {
        const f = input.files[0]; if (!f) return;
        document.getElementById('mp-file-preview-bar').style.display = 'block';
        document.getElementById('mp-file-name').textContent = f.name;
    };
    window._mpClearFile = function() {
        document.getElementById('mp-file-input').value = '';
        document.getElementById('mp-file-preview-bar').style.display = 'none';
    };

    // ── 삭제 ──
    window._mpDeleteMsg = async function(msgId) {
        if (!confirm('메시지를 삭제하시겠습니까?')) return;
        try {
            const res = await fetch('/api/messenger/messages/delete', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ member_id: _user.member_id, message_id: msgId })
            });
            const data = await res.json();
            if (data.success) await _loadMessages(_currentConvId);
            else alert(data.message || '삭제 실패');
        } catch(e) { alert('삭제 오류'); }
    };

    // ── 나가기 ──
    window._mpLeave = async function() {
        if (!_currentConvId || !confirm('대화방을 나가시겠습니까?')) return;
        try {
            await fetch('/api/messenger/conversations/leave', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ member_id: _user.member_id, conversation_id: _currentConvId })
            });
            window._mpBackToList();
        } catch(e) {}
    };

    // ── 새 대화 모달 ──
    window._mpOpenNew = function() {
        _selectedContacts = [];
        document.getElementById('mp-new-modal').classList.add('active');
        _setupRoleFilters();
        _loadContacts();
    };
    window._mpCloseNew = function() {
        document.getElementById('mp-new-modal').classList.remove('active');
        _selectedContacts = [];
    };

    function _setupRoleFilters() {
        const role = _user.member_roll || _user.user_role || 'student';
        const el = document.getElementById('mp-role-filters');
        let html = '<button class="mp-filter-btn active" onclick="window._mpSetFilter(\'\',this)">전체</button>';
        if (role === 'teacher') {
            html += '<button class="mp-filter-btn" onclick="window._mpSetFilter(\'teacher\',this)">교사</button>';
            html += '<button class="mp-filter-btn" onclick="window._mpSetFilter(\'student\',this)">학생</button>';
            html += '<button class="mp-filter-btn" onclick="window._mpSetFilter(\'parent\',this)">학부모</button>';
        }
        el.innerHTML = html;
        _roleFilter = '';
    }

    window._mpSetFilter = function(role, btn) {
        _roleFilter = role;
        document.querySelectorAll('#mp-role-filters .mp-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _loadContacts();
    };

    async function _loadContacts() {
        const kw = document.getElementById('mp-contact-search')?.value.trim() || '';
        try {
            const p = new URLSearchParams({
                member_id: _user.member_id,
                school_id: _user.school_id || '',
                user_role: _user.member_roll || _user.user_role || 'student',
                role_filter: _roleFilter,
                keyword: kw
            });
            const res = await fetch('/api/messenger/contacts?' + p);
            const data = await res.json();
            if (!data.success) return;
            _allContacts = data.contacts;
            _renderContacts();
        } catch(e) { console.error(e); }
    }

    window._mpSearchContacts = function() { _loadContacts(); };

    function _renderContacts() {
        const el = document.getElementById('mp-contact-list');
        if (!_allContacts.length) {
            el.innerHTML = '<div class="mp-empty" style="padding:20px;"><p>검색 결과 없음</p></div>';
            return;
        }
        const roleColors = { teacher: 'background:linear-gradient(135deg,#22c55e,#16a34a)', student: 'background:linear-gradient(135deg,#3b82f6,#6366f1)', parent: 'background:linear-gradient(135deg,#a855f7,#ec4899)' };
        el.innerHTML = _allContacts.map(c => {
            const sel = _selectedContacts.some(s => s.member_id === c.member_id);
            return `<div class="mp-contact-item${sel ? ' selected' : ''}" onclick="window._mpToggleContact('${c.member_id}','${_escAttr(c.name)}','${c.role}')">
                <div class="mp-contact-avatar" style="${roleColors[c.role] || 'background:#94a3b8'}">${_esc(c.name.charAt(0))}</div>
                <div class="mp-contact-info">
                    <div class="mp-contact-name">${_esc(c.name)}</div>
                    <div class="mp-contact-detail">${_roleLabel(c.role)}${c.detail ? ' · ' + _esc(c.detail) : ''}</div>
                </div>
                <div class="mp-contact-check${sel ? ' checked' : ''}">${sel ? '<i class="fas fa-check" style="color:white;font-size:10px;"></i>' : ''}</div>
            </div>`;
        }).join('');
        _updateFooter();
    }

    window._mpToggleContact = function(id, name, role) {
        const idx = _selectedContacts.findIndex(s => s.member_id === id);
        if (idx >= 0) _selectedContacts.splice(idx, 1);
        else _selectedContacts.push({ member_id: id, name, role });
        _renderContacts();
    };

    function _updateFooter() {
        const footer = document.getElementById('mp-modal-footer');
        if (_selectedContacts.length === 0) { footer.style.display = 'none'; return; }
        footer.style.display = 'flex';
        document.getElementById('mp-sel-names').textContent = _selectedContacts.map(c => c.name).join(', ');
    }

    window._mpStartConv = async function() {
        if (!_selectedContacts.length) return;
        const type = _selectedContacts.length === 1 ? 'direct' : 'group';
        try {
            const res = await fetch('/api/messenger/conversations/create', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    member_id: _user.member_id,
                    school_id: _user.school_id || '',
                    user_role: _user.member_roll || _user.user_role || 'student',
                    target_ids: _selectedContacts.map(c => c.member_id),
                    conv_type: type
                })
            });
            const data = await res.json();
            if (data.success) {
                window._mpCloseNew();
                await _loadConversations();
                window._mpOpenConv(data.conversation_id);
            } else { alert(data.message || '생성 실패'); }
        } catch(e) { alert('생성 오류'); }
    };

    // ── 뱃지 폴링 (패널 닫혀있을 때도) ──
    async function _pollBadge() {
        if (!_user) return;
        try {
            const res = await fetch('/api/messenger/unread-count?member_id=' + _user.member_id);
            const data = await res.json();
            if (!data.success) return;
            const cnt = data.total_unread || 0;
            ['sidebar-msg-badge', 'header-msg-badge'].forEach(id => {
                const el = document.getElementById(id);
                if (!el) return;
                if (cnt > 0) { el.textContent = cnt > 99 ? '99+' : cnt; el.classList.remove('hidden'); }
                else { el.classList.add('hidden'); }
            });
        } catch(e) {}
    }

    // ── 유틸 ──
    function _esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function _escAttr(s) { return (s||'').replace(/'/g,"\\'").replace(/"/g,'\\"'); }
    function _truncate(s, n) { return s.length > n ? s.substring(0,n) + '...' : s; }
    function _roleLabel(r) { return {teacher:'교사',student:'학생',parent:'학부모'}[r]||r; }
    function _fmtTime(s) {
        if (!s) return '';
        const today = new Date().toISOString().split('T')[0];
        const d = s.split(' ')[0];
        if (d === today) return s.split(' ')[1]?.substring(0,5) || '';
        const y = new Date(); y.setDate(y.getDate()-1);
        if (d === y.toISOString().split('T')[0]) return '어제';
        return d.substring(5);
    }
    function _fmtDateLabel(d) {
        const today = new Date().toISOString().split('T')[0];
        if (d === today) return '오늘';
        const y = new Date(); y.setDate(y.getDate()-1);
        if (d === y.toISOString().split('T')[0]) return '어제';
        const p = d.split('-');
        return parseInt(p[1]) + '월 ' + parseInt(p[2]) + '일';
    }

    // ── 초기화 ──
    function init() {
        const userStr = localStorage.getItem('schoolus_user');
        if (!userStr) return;
        _user = JSON.parse(userStr);
        injectHTML();
        // 60초 뱃지 폴링
        _pollBadge();
        _badgeTimer = setInterval(_pollBadge, 60000);

        // URL에 ?msg_conv= 파라미터가 있으면 자동 오픈
        const params = new URLSearchParams(window.location.search);
        const convParam = params.get('msg_conv');
        if (convParam) {
            setTimeout(() => {
                window._mpOpen();
                setTimeout(() => window._mpOpenConv(parseInt(convParam)), 500);
            }, 800);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
