/**
 * SchoolUs Push Notification Manager
 * - VAPID 기반 웹 푸시 구독/해지
 * - 서버에 구독 정보 등록
 */
(function() {
  'use strict';

  const PUSH_API_BASE = '/api/push';

  // ============================================
  // VAPID 공개키 가져오기
  // ============================================
  async function getVapidPublicKey() {
    try {
      const res = await fetch(PUSH_API_BASE + '/vapid-key');
      const data = await res.json();
      if (data.success && data.public_key) {
        return data.public_key;
      }
    } catch (e) {
      console.error('[Push] Failed to get VAPID key:', e);
    }
    return null;
  }

  // Base64 URL → Uint8Array
  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i++) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  // ============================================
  // 푸시 구독
  // ============================================
  async function subscribePush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      console.log('[Push] Push not supported');
      return { success: false, message: '이 브라우저는 푸시 알림을 지원하지 않습니다.' };
    }

    try {
      // 알림 권한 요청
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        return { success: false, message: '알림 권한이 거부되었습니다.' };
      }

      // VAPID 공개키 가져오기
      const vapidKey = await getVapidPublicKey();
      if (!vapidKey) {
        return { success: false, message: 'VAPID 키를 가져올 수 없습니다.' };
      }

      // Service Worker 준비
      const registration = await navigator.serviceWorker.ready;

      // 기존 구독 확인
      let subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        console.log('[Push] Already subscribed');
        // 서버에 재등록 (기기 변경 등)
        await sendSubscriptionToServer(subscription);
        return { success: true, message: '푸시 알림이 이미 활성화되어 있습니다.' };
      }

      // 새 구독
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey)
      });

      // 서버에 등록
      await sendSubscriptionToServer(subscription);
      console.log('[Push] Subscribed successfully');
      return { success: true, message: '푸시 알림이 활성화되었습니다.' };
    } catch (e) {
      console.error('[Push] Subscribe error:', e);
      return { success: false, message: '푸시 알림 등록 중 오류가 발생했습니다.' };
    }
  }

  // ============================================
  // 푸시 구독 해지
  // ============================================
  async function unsubscribePush() {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();

      if (subscription) {
        // 서버에서 제거
        await fetch(PUSH_API_BASE + '/unsubscribe', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: subscription.endpoint })
        });

        await subscription.unsubscribe();
        console.log('[Push] Unsubscribed');
        return { success: true, message: '푸시 알림이 해제되었습니다.' };
      }
      return { success: true, message: '활성화된 구독이 없습니다.' };
    } catch (e) {
      console.error('[Push] Unsubscribe error:', e);
      return { success: false, message: '푸시 알림 해제 중 오류가 발생했습니다.' };
    }
  }

  // ============================================
  // 서버에 구독 정보 전송
  // ============================================
  async function sendSubscriptionToServer(subscription) {
    try {
      const res = await fetch(PUSH_API_BASE + '/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subscription: subscription.toJSON()
        })
      });
      const data = await res.json();
      return data.success;
    } catch (e) {
      console.error('[Push] Server registration error:', e);
      return false;
    }
  }

  // ============================================
  // 구독 상태 확인
  // ============================================
  async function isPushSubscribed() {
    try {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      return !!subscription;
    } catch (e) {
      return false;
    }
  }

  // 전역 노출
  window.SchoolUsPush = {
    subscribe: subscribePush,
    unsubscribe: unsubscribePush,
    isSubscribed: isPushSubscribed
  };
})();
