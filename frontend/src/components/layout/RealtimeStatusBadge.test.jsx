import { describe, it, expect } from 'vitest'
import { describeRealtimeStatus } from './RealtimeStatusBadge'
import { isKrxRegularSession } from '../../utils/realtime'

// 2026-11-20(금) KST 시각을 UTC Date로 만든다.
const kst = (hhmm) => new Date(`2026-11-20T${hhmm}:00+09:00`)

describe('isKrxRegularSession', () => {
  it('평일 09:00~15:30만 정규장으로 본다', () => {
    expect(isKrxRegularSession(kst('08:59'))).toBe(false)
    expect(isKrxRegularSession(kst('09:00'))).toBe(true)
    expect(isKrxRegularSession(kst('15:30'))).toBe(true)
    expect(isKrxRegularSession(kst('15:31'))).toBe(false)
    expect(isKrxRegularSession(new Date('2026-11-21T10:00:00+09:00'))).toBe(false) // 토요일
  })
})

describe('describeRealtimeStatus', () => {
  const now = kst('10:00')

  it('장중 최근 체결이 있으면 실시간(초록)', () => {
    const r = describeRealtimeStatus({ status: 'connected', last_trade_at: '2026-11-20T09:59:30+09:00' }, now)
    expect(r).toMatchObject({ tone: 'ok', label: '실시간' })
  })

  it('장중인데 2분 넘게 체결이 없으면 체결 지연', () => {
    const r = describeRealtimeStatus({ status: 'connected', last_trade_at: '2026-11-20T09:55:00+09:00' }, now)
    expect(r).toMatchObject({ tone: 'warn', label: '체결 지연' })
  })

  it('장중 연결 끊김은 빨강, 장 외에는 회색', () => {
    expect(describeRealtimeStatus({ status: 'disconnected' }, now)).toMatchObject({ tone: 'error', label: '실시간 끊김' })
    expect(describeRealtimeStatus({ status: 'disconnected' }, kst('20:00'))).toMatchObject({ tone: 'idle', label: '장 외' })
  })

  it('키 없음·인증 실패는 시간과 무관하게 빨강이고 설정으로 안내한다', () => {
    expect(describeRealtimeStatus({ status: 'no_credentials' }, kst('20:00'))).toMatchObject({ tone: 'error', label: '토스 키 없음', fixable: true })
    expect(describeRealtimeStatus({ status: 'auth_failed', last_error: '403' }, now)).toMatchObject({ tone: 'error', label: '토스 인증 실패', fixable: true })
  })
})
