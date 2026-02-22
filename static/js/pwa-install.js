/**
 * SchoolUs PWA Install Manager v3
 * - 모바일 전용: 설치 배너 + 버튼
 * - PC에서는 설치 UI 미표시
 * - Service Worker는 모든 기기에서 등록
 */
(function() {
  'use strict';

  let deferredPrompt = null;
  let isStandalone = false;

  // ============================================
  // 모바일 감지
  // ============================================
  function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
      || (navigator.maxTouchPoints > 1 && window.innerWidth < 1024);
  }

  // ============================================
  // Standalone 감지
  // ============================================
  function checkStandalone() {
    isStandalone = window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone === true
      || document.referrer.includes('android-app://');
    return isStandalone;
  }

  // ============================================
  // Service Worker 등록 (모든 기기)
  // ============================================
  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;

    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then((reg) => {
        console.log('[PWA] SW registered, scope:', reg.scope);
        reg.addEventListener('updatefound', () => {
          const nw = reg.installing;
          nw.addEventListener('statechange', () => {
            if (nw.state === 'activated') console.log('[PWA] New SW activated');
          });
        });
      })
      .catch((err) => console.error('[PWA] SW registration failed:', err));
  }

  // ============================================
  // Nav / Hero 설치 버튼 표시 (모바일만)
  // ============================================
  function showInstallButtons() {
    if (checkStandalone() || !isMobile()) return;

    const navBtn = document.getElementById('nav-install-btn');
    const heroBtn = document.getElementById('hero-install-btn');
    if (navBtn) navBtn.classList.remove('hidden');
    if (heroBtn) heroBtn.classList.remove('hidden');
  }

  function hideInstallButtons() {
    const navBtn = document.getElementById('nav-install-btn');
    const heroBtn = document.getElementById('hero-install-btn');
    if (navBtn) navBtn.classList.add('hidden');
    if (heroBtn) heroBtn.classList.add('hidden');
  }

  // ============================================
  // 설치 실행
  // ============================================
  function triggerInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choice) => {
        console.log('[PWA] User choice:', choice.outcome);
        if (choice.outcome === 'accepted') {
          removeBanner();
          hideInstallButtons();
        }
        deferredPrompt = null;
      });
    } else {
      showInstallGuide();
    }
  }

  // ============================================
  // 상단 설치 배너 (모바일만, nav 바로 아래)
  // ============================================
  function createInstallBanner() {
    if (checkStandalone() || !isMobile()) return;
    if (document.getElementById('pwa-install-banner')) return;

    const dismissed = localStorage.getItem('pwa_banner_dismissed');
    if (dismissed && (Date.now() - parseInt(dismissed)) < 24 * 60 * 60 * 1000) return;

    const banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.innerHTML = `
      <div style="position:fixed;top:80px;left:0;right:0;z-index:49;padding:0 8px;pointer-events:none;">
        <div style="max-width:480px;margin:0 auto;background:linear-gradient(135deg,#1e3a5f,#1e293b);border-radius:14px;padding:12px 14px;display:flex;align-items:center;gap:10px;box-shadow:0 4px 20px rgba(0,0,0,0.3);pointer-events:auto;border:1px solid rgba(255,255,255,0.08);">
          <img src="/static/icons/icon-72x72.png" alt="" style="width:36px;height:36px;border-radius:8px;flex-shrink:0;">
          <div style="flex:1;min-width:0;">
            <div style="font-weight:700;font-size:13px;color:#f1f5f9;">SchoolUs 앱 설치</div>
            <div style="font-size:11px;color:#94a3b8;line-height:1.3;">홈 화면에 추가하면 더 빠르게!</div>
          </div>
          <button id="pwa-banner-install" style="background:linear-gradient(135deg,#3b82f6,#6366f1);color:white;border:none;padding:8px 14px;border-radius:10px;font-size:12px;font-weight:700;cursor:pointer;white-space:nowrap;">설치</button>
          <button id="pwa-banner-dismiss" style="background:none;color:#64748b;border:none;padding:4px;font-size:18px;cursor:pointer;line-height:1;">&times;</button>
        </div>
      </div>
    `;

    document.body.appendChild(banner);

    document.getElementById('pwa-banner-install').addEventListener('click', triggerInstall);
    document.getElementById('pwa-banner-dismiss').addEventListener('click', () => {
      localStorage.setItem('pwa_banner_dismissed', Date.now().toString());
      removeBanner();
    });

    // 슬라이드다운 애니메이션
    const inner = banner.querySelector('div > div');
    inner.style.transform = 'translateY(-120%)';
    inner.style.opacity = '0';
    inner.style.transition = 'transform 0.5s cubic-bezier(0.16,1,0.3,1), opacity 0.4s ease';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        inner.style.transform = 'translateY(0)';
        inner.style.opacity = '1';
      });
    });
  }

  function removeBanner() {
    const banner = document.getElementById('pwa-install-banner');
    if (banner) {
      const inner = banner.querySelector('div > div');
      inner.style.transform = 'translateY(-120%)';
      inner.style.opacity = '0';
      setTimeout(() => banner.remove(), 500);
    }
  }

  // ============================================
  // 설치 가이드 (iOS / Android 분기)
  // ============================================
  function showInstallGuide() {
    if (document.getElementById('pwa-install-guide')) return;

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const guide = document.createElement('div');
    guide.id = 'pwa-install-guide';

    const content = isIOS
      ? `<div style="font-size:40px;margin-bottom:12px;">&#128242;</div>
         <div style="font-weight:700;font-size:16px;color:#1e293b;margin-bottom:8px;">홈 화면에 추가하기</div>
         <div style="font-size:13px;color:#64748b;line-height:1.6;">
           Safari 하단의 <strong>공유 버튼</strong> <span style="font-size:18px;">&#11014;&#65039;</span> 을 누른 후<br>
           <strong>"홈 화면에 추가"</strong>를 선택하세요
         </div>`
      : `<div style="font-size:40px;margin-bottom:12px;">&#128242;</div>
         <div style="font-weight:700;font-size:16px;color:#1e293b;margin-bottom:8px;">앱 설치하기</div>
         <div style="font-size:13px;color:#64748b;line-height:1.6;">
           브라우저 메뉴 <strong>&#8942;</strong> 를 누른 후<br>
           <strong>"홈 화면에 추가"</strong> 또는 <strong>"앱 설치"</strong>를 선택하세요
         </div>`;

    guide.innerHTML = `
      <div style="position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;padding:20px;" onclick="this.parentElement.remove()">
        <div style="background:white;border-radius:20px;padding:24px;max-width:340px;width:100%;text-align:center;" onclick="event.stopPropagation()">
          ${content}
          <button style="margin-top:16px;background:#3b82f6;color:white;border:none;padding:10px 24px;border-radius:10px;font-size:14px;font-weight:600;cursor:pointer;" onclick="this.closest('#pwa-install-guide').remove()">확인</button>
        </div>
      </div>
    `;
    document.body.appendChild(guide);
  }

  // ============================================
  // 이벤트 리스너
  // ============================================

  // beforeinstallprompt (Android Chrome 등)
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    console.log('[PWA] beforeinstallprompt captured');
    if (isMobile()) {
      showInstallButtons();
      createInstallBanner();
    }
  });

  // 앱 설치 완료
  window.addEventListener('appinstalled', () => {
    console.log('[PWA] App installed');
    deferredPrompt = null;
    removeBanner();
    hideInstallButtons();
    localStorage.removeItem('pwa_banner_dismissed');
  });

  // ============================================
  // 초기화
  // ============================================
  function init() {
    checkStandalone();
    registerServiceWorker();

    // 모바일 + standalone 아닌 경우만 설치 UI
    if (!isStandalone && isMobile()) {
      setTimeout(() => {
        showInstallButtons();
        // iOS는 beforeinstallprompt 미지원이므로 직접 배너 표시
        if (!deferredPrompt && !document.getElementById('pwa-install-banner')) {
          const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
          if (isIOS) {
            createInstallBanner();
          }
        }
      }, 2000);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 전역 유틸리티
  window.SchoolUsPWA = {
    isStandalone: () => checkStandalone(),
    isMobile: isMobile,
    showInstallBanner: createInstallBanner,
    triggerInstall: triggerInstall
  };
})();
