/**
 * SchoolUs 사용설명서 모달 시스템
 *
 * 사용법: 각 페이지 </body> 직전에 추가
 * <script src="/static/js/help-modal.js" data-doc="homeroom"></script>
 *
 * data-doc 값이 /사용설명서/{value}.html 파일과 매핑됩니다.
 */
(function () {
    // 현재 script 태그에서 data-doc 추출
    var scripts = document.getElementsByTagName('script');
    var currentScript = scripts[scripts.length - 1];
    var docName = currentScript.getAttribute('data-doc');
    if (!docName) return;

    var DOC_URL = '/사용설명서/' + docName + '.html';
    var modalEl = null;
    var contentEl = null;
    var loaded = false;

    // 플로팅 도움말 버튼 생성
    var fab = document.createElement('button');
    fab.id = 'help-fab';
    fab.innerHTML = '<i class="fas fa-question"></i>';
    fab.title = '사용설명서';
    fab.style.cssText = [
        'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9999',
        'width:48px', 'height:48px', 'border-radius:50%', 'border:none',
        'background:linear-gradient(135deg,#3b82f6,#6366f1)', 'color:#fff',
        'font-size:18px', 'cursor:pointer', 'box-shadow:0 4px 16px rgba(99,102,241,.4)',
        'display:flex', 'align-items:center', 'justify-content:center',
        'transition:transform .2s,box-shadow .2s'
    ].join(';');
    fab.onmouseenter = function () { fab.style.transform = 'scale(1.1)'; fab.style.boxShadow = '0 6px 24px rgba(99,102,241,.5)'; };
    fab.onmouseleave = function () { fab.style.transform = 'scale(1)'; fab.style.boxShadow = '0 4px 16px rgba(99,102,241,.4)'; };
    fab.onclick = openHelpModal;
    document.body.appendChild(fab);

    function createModal() {
        modalEl = document.createElement('div');
        modalEl.id = 'help-modal-overlay';
        modalEl.style.cssText = [
            'position:fixed', 'inset:0', 'z-index:10000',
            'background:rgba(0,0,0,.5)', 'backdrop-filter:blur(4px)',
            'display:flex', 'align-items:center', 'justify-content:center',
            'padding:16px', 'opacity:0', 'transition:opacity .2s'
        ].join(';');
        modalEl.onclick = function (e) { if (e.target === modalEl) closeHelpModal(); };

        var card = document.createElement('div');
        card.style.cssText = [
            'background:#fff', 'border-radius:16px', 'box-shadow:0 24px 64px rgba(0,0,0,.2)',
            'width:100%', 'max-width:720px', 'max-height:85vh',
            'display:flex', 'flex-direction:column', 'overflow:hidden',
            'transform:translateY(16px)', 'transition:transform .2s'
        ].join(';');

        // 헤더
        var header = document.createElement('div');
        header.style.cssText = [
            'background:linear-gradient(135deg,#3b82f6,#6366f1)',
            'padding:20px 24px', 'display:flex', 'align-items:center',
            'justify-content:space-between', 'flex-shrink:0'
        ].join(';');
        header.innerHTML = '<div style="display:flex;align-items:center;gap:12px;color:#fff">' +
            '<i class="fas fa-book-open" style="font-size:20px;opacity:.9"></i>' +
            '<div><div style="font-weight:800;font-size:16px">사용설명서</div>' +
            '<div style="font-size:12px;opacity:.8">이 페이지의 기능과 사용법을 안내합니다</div></div></div>';

        var closeBtn = document.createElement('button');
        closeBtn.innerHTML = '<i class="fas fa-times"></i>';
        closeBtn.style.cssText = [
            'background:rgba(255,255,255,.2)', 'border:none', 'color:#fff',
            'width:32px', 'height:32px', 'border-radius:8px', 'cursor:pointer',
            'font-size:14px', 'display:flex', 'align-items:center', 'justify-content:center',
            'transition:background .15s'
        ].join(';');
        closeBtn.onmouseenter = function () { closeBtn.style.background = 'rgba(255,255,255,.3)'; };
        closeBtn.onmouseleave = function () { closeBtn.style.background = 'rgba(255,255,255,.2)'; };
        closeBtn.onclick = closeHelpModal;
        header.appendChild(closeBtn);
        card.appendChild(header);

        // 콘텐츠 영역
        contentEl = document.createElement('div');
        contentEl.id = 'help-modal-content';
        contentEl.style.cssText = [
            'padding:24px', 'overflow-y:auto', 'flex:1',
            'font-size:14px', 'line-height:1.8', 'color:#334155'
        ].join(';');
        contentEl.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8"><i class="fas fa-spinner fa-spin" style="font-size:24px"></i><div style="margin-top:12px;font-size:13px">설명서 불러오는 중...</div></div>';
        card.appendChild(contentEl);

        modalEl.appendChild(card);
        document.body.appendChild(modalEl);

        // 스타일 주입 (설명서 콘텐츠용)
        if (!document.getElementById('help-doc-styles')) {
            var style = document.createElement('style');
            style.id = 'help-doc-styles';
            style.textContent = [
                '#help-modal-content h2{font-size:20px;font-weight:800;color:#1e293b;margin:0 0 8px;padding-bottom:12px;border-bottom:2px solid #e2e8f0}',
                '#help-modal-content h3{font-size:15px;font-weight:700;color:#3b82f6;margin:20px 0 8px;padding-left:12px;border-left:3px solid #3b82f6}',
                '#help-modal-content h4{font-size:14px;font-weight:700;color:#475569;margin:14px 0 6px}',
                '#help-modal-content p{margin:6px 0;font-size:13px}',
                '#help-modal-content ul{margin:6px 0 6px 8px;padding:0;list-style:none}',
                '#help-modal-content ul li{padding:4px 0 4px 20px;font-size:13px;position:relative}',
                '#help-modal-content ul li::before{content:"\\f00c";font-family:"Font Awesome 6 Free";font-weight:900;font-size:10px;color:#3b82f6;position:absolute;left:0;top:6px}',
                '#help-modal-content .doc-tip{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:12px 16px;margin:10px 0;font-size:12px;color:#1e40af}',
                '#help-modal-content .doc-tip::before{content:"\\f0eb";font-family:"Font Awesome 6 Free";font-weight:900;margin-right:8px;color:#3b82f6}',
                '#help-modal-content .doc-warn{background:#fef3c7;border:1px solid #fde68a;border-radius:10px;padding:12px 16px;margin:10px 0;font-size:12px;color:#92400e}',
                '#help-modal-content .doc-warn::before{content:"\\f071";font-family:"Font Awesome 6 Free";font-weight:900;margin-right:8px;color:#f59e0b}',
                '#help-modal-content .doc-steps{counter-reset:step;margin:8px 0}',
                '#help-modal-content .doc-steps li{counter-increment:step;padding-left:32px}',
                '#help-modal-content .doc-steps li::before{content:counter(step);font-family:inherit;background:#3b82f6;color:#fff;width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;position:absolute;left:0;top:4px}',
                '#help-modal-content table{width:100%;border-collapse:collapse;margin:10px 0;font-size:12px}',
                '#help-modal-content th{background:#f1f5f9;padding:8px 12px;text-align:left;font-weight:700;border:1px solid #e2e8f0;color:#475569}',
                '#help-modal-content td{padding:8px 12px;border:1px solid #e2e8f0}',
                '#help-modal-content strong,#help-modal-content b{color:#1e293b}',
                '#help-modal-content hr{border:none;border-top:1px solid #e2e8f0;margin:16px 0}',
                '@media(max-width:640px){#help-fab{bottom:16px;right:16px;width:44px;height:44px;font-size:16px}}'
            ].join('\n');
            document.head.appendChild(style);
        }

        return { card: card };
    }

    function openHelpModal() {
        if (!modalEl) {
            var m = createModal();
            // 트리거 애니메이션
            requestAnimationFrame(function () {
                modalEl.style.opacity = '1';
                m.card.style.transform = 'translateY(0)';
            });
        } else {
            modalEl.style.display = 'flex';
            requestAnimationFrame(function () { modalEl.style.opacity = '1'; });
        }
        document.body.style.overflow = 'hidden';

        // 콘텐츠 로드
        if (!loaded) {
            fetch(DOC_URL)
                .then(function (r) {
                    if (!r.ok) throw new Error(r.status);
                    return r.text();
                })
                .then(function (html) {
                    contentEl.innerHTML = html;
                    loaded = true;
                })
                .catch(function () {
                    contentEl.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8">' +
                        '<i class="fas fa-file-circle-exclamation" style="font-size:32px;margin-bottom:12px;display:block"></i>' +
                        '<div style="font-size:14px;font-weight:600;color:#64748b">설명서를 불러올 수 없습니다</div>' +
                        '<div style="font-size:12px;margin-top:4px">파일: ' + DOC_URL + '</div></div>';
                });
        }

        // ESC 닫기
        document.addEventListener('keydown', escHandler);
    }

    function closeHelpModal() {
        if (!modalEl) return;
        modalEl.style.opacity = '0';
        document.body.style.overflow = '';
        document.removeEventListener('keydown', escHandler);
        setTimeout(function () { if (modalEl) modalEl.style.display = 'none'; }, 200);
    }

    function escHandler(e) {
        if (e.key === 'Escape') closeHelpModal();
    }
})();
