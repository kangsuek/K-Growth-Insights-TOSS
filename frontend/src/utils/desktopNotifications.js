/**
 * 목표가·신호 알림을 OS(데스크톱) 알림으로 띄우는 헬퍼.
 *
 * 브라우저와 Electron 렌더러 모두 표준 Notification Web API를 쓴다. 알림은 사용자가 알림
 * 화면에서 직접 켠 경우에만 보낸다(권한 요청은 사용자 클릭에서만 가능하고, 원치 않는
 * 팝업을 막기 위함). 켜짐 여부는 이 기기의 localStorage에만 저장한다.
 */
const STORAGE_KEY = 'desktop_notifications'

export const isSupported = () => typeof window !== 'undefined' && 'Notification' in window

export function isEnabled() {
  if (!isSupported() || window.Notification.permission !== 'granted') return false
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'on'
  } catch {
    return false
  }
}

/** 권한을 요청하고 켠다. 켜졌으면 true. 반드시 사용자 클릭 핸들러에서 호출한다. */
export async function enable() {
  if (!isSupported()) return false
  const permission = window.Notification.permission === 'granted'
    ? 'granted'
    : await window.Notification.requestPermission()
  if (permission !== 'granted') return false
  try {
    window.localStorage.setItem(STORAGE_KEY, 'on')
  } catch {
    // 저장이 막혀도 이번 세션 알림은 권한만으로 동작하지 않으므로 false 처리
    return false
  }
  return true
}

export function disable() {
  try {
    window.localStorage.setItem(STORAGE_KEY, 'off')
  } catch {
    // 무시
  }
}

/** 알림 이벤트 하나를 OS 알림으로 띄운다(꺼져 있으면 아무것도 하지 않음). */
export function notifyAlertEvent(event) {
  if (!isEnabled() || !event?.message) return
  // eslint-disable-next-line no-new
  new window.Notification('K-Growth Insights 알림', { body: event.message, tag: `alert-${event.id}` })
}
