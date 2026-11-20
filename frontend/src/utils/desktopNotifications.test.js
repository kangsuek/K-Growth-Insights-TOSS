import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { enable, disable, isEnabled, notifyAlertEvent } from './desktopNotifications'

describe('desktopNotifications', () => {
  let created

  beforeEach(() => {
    created = []
    // 생성자 호출을 기록하는 가짜 Notification(일반 클래스 — vi.fn을 new로 부르는 동작에 기대지 않음)
    class FakeNotification {
      constructor(title, options) { created.push({ title, ...options }) }
    }
    FakeNotification.permission = 'default'
    FakeNotification.requestPermission = vi.fn(async () => {
      FakeNotification.permission = 'granted'
      return 'granted'
    })
    vi.stubGlobal('Notification', FakeNotification)
    // Node 24 내장 localStorage(파일 미지정 시 저장 안 됨)가 jsdom 것을 가릴 수 있어 메모리 구현으로 고정한다.
    const store = new Map()
    vi.stubGlobal('localStorage', {
      getItem: (k) => (store.has(k) ? store.get(k) : null),
      setItem: (k, v) => store.set(k, String(v)),
      removeItem: (k) => store.delete(k),
      clear: () => store.clear(),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('켜기 전에는 알림을 보내지 않는다', () => {
    notifyAlertEvent({ id: 1, message: 'SK하이닉스 목표가 도달' })
    expect(created).toEqual([])
    expect(isEnabled()).toBe(false)
  })

  it('켜면 권한을 받고 알림 문구를 OS 알림으로 띄운다', async () => {
    expect(await enable()).toBe(true)
    expect(window.Notification.requestPermission).toHaveBeenCalled()
    notifyAlertEvent({ id: 7, message: 'SK하이닉스 목표가 도달: 1,200,000원' })
    expect(created).toEqual([
      { title: 'K-Growth Insights 알림', body: 'SK하이닉스 목표가 도달: 1,200,000원', tag: 'alert-7' },
    ])
  })

  it('권한이 거부되면 켜지지 않는다', async () => {
    window.Notification.requestPermission = vi.fn(async () => 'denied')
    expect(await enable()).toBe(false)
    expect(isEnabled()).toBe(false)
  })

  it('끄면 다시 보내지 않는다', async () => {
    await enable()
    disable()
    notifyAlertEvent({ id: 1, message: 'x' })
    expect(created).toEqual([])
  })
})
