import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  todayKst,
  nowKstMinuteIso,
  isLiveToday,
  mergeLiveDailyCandle,
  liveWeeklyReturn,
} from './realtime'

// 2026-10-02 10:30:15 KST (= 01:30:15 UTC)
const NOW = new Date('2026-10-02T01:30:15Z')

const liveQuote = (overrides = {}) => ({
  symbol: '000660',
  open: 1800,
  high: 1850,
  low: 1790,
  last: 1840,
  prev_close: 1784,
  updated_at: '2026-10-02T10:30:14.100+09:00',
  ...overrides,
})

const todayRow = {
  date: '2026-10-02', open_price: 1795, high_price: 1830, low_price: 1785,
  close_price: 1820, volume: 1000, daily_change_pct: 2.02,
}
const prevRow = {
  date: '2026-09-30', open_price: 1780, high_price: 1800, low_price: 1770,
  close_price: 1784, volume: 900, daily_change_pct: 1.08,
}

describe('realtime 헬퍼', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('KST 기준 오늘 날짜와 이번 분을 만든다', () => {
    expect(todayKst()).toBe('2026-10-02')
    expect(nowKstMinuteIso()).toBe('2026-10-02T10:30:00')
  })

  it('오늘 체결로 갱신된 시세만 실시간으로 본다', () => {
    expect(isLiveToday(liveQuote())).toBe(true)
    expect(isLiveToday(liveQuote({ updated_at: '2026-09-30T15:30:00+09:00' }))).toBe(false)
    expect(isLiveToday(liveQuote({ updated_at: null }))).toBe(false)
    expect(isLiveToday(liveQuote({ last: null }))).toBe(false)
    expect(isLiveToday(undefined)).toBe(false)
  })

  describe('mergeLiveDailyCandle', () => {
    it('오늘 행이 있으면 실시간 값으로 교체한다(고가/저가는 더 넓은 범위, 거래량 유지)', () => {
      const merged = mergeLiveDailyCandle([todayRow, prevRow], liveQuote())
      expect(merged).toHaveLength(2)
      expect(merged[0]).toMatchObject({
        date: '2026-10-02',
        open_price: 1800,
        high_price: 1850,
        low_price: 1785,
        close_price: 1840,
        volume: 1000,
      })
      expect(merged[0].daily_change_pct).toBeCloseTo(((1840 - 1784) / 1784) * 100)
      expect(merged[1]).toBe(prevRow)
    })

    it('오늘 행이 없으면 allowAppend일 때만 오늘 봉을 붙인다', () => {
      expect(mergeLiveDailyCandle([prevRow], liveQuote())).toEqual([prevRow])

      const appended = mergeLiveDailyCandle([prevRow], liveQuote(), { allowAppend: true })
      expect(appended).toHaveLength(2)
      expect(appended[0]).toMatchObject({
        date: '2026-10-02', open_price: 1800, high_price: 1850, low_price: 1790,
        close_price: 1840, volume: null,
      })
      expect(appended[1]).toBe(prevRow)
    })

    it('전일 체결 시세는 섞지 않는다', () => {
      const rows = [prevRow]
      const stale = liveQuote({ updated_at: '2026-09-30T15:30:00+09:00' })
      expect(mergeLiveDailyCandle(rows, stale, { allowAppend: true })).toBe(rows)
    })

    it('시가·고가·저가·기준가가 없어도 현재가로 봉을 만든다', () => {
      const bare = liveQuote({ open: null, high: null, low: null, prev_close: null })
      const [row] = mergeLiveDailyCandle([], bare, { allowAppend: true })
      expect(row).toMatchObject({
        open_price: 1840, high_price: 1840, low_price: 1840, close_price: 1840, daily_change_pct: null,
      })
      const [replaced] = mergeLiveDailyCandle([todayRow], bare)
      expect(replaced.daily_change_pct).toBe(todayRow.daily_change_pct)
      expect(replaced.open_price).toBe(todayRow.open_price)
    })

    it('배열이 아니면 그대로 돌려준다', () => {
      expect(mergeLiveDailyCandle(undefined, liveQuote())).toBeUndefined()
      expect(mergeLiveDailyCandle(null, liveQuote())).toBeNull()
    })
  })

  describe('liveWeeklyReturn', () => {
    it('DB 최신 행이 오늘이면 현재가 기준으로 환산한다', () => {
      // DB 종가 1820 기준 +10% → 기준가 1654.5..., 현재가 1840이면 (1.1 × 1840/1820 − 1)
      const expected = (1.1 * (1840 / 1820) - 1) * 100
      expect(liveWeeklyReturn(10, todayRow, liveQuote())).toBeCloseTo(expected)
    })

    it('DB 최신 행이 전일이거나 오늘 시세가 없으면 원래 값을 쓴다', () => {
      expect(liveWeeklyReturn(10, prevRow, liveQuote())).toBe(10)
      expect(liveWeeklyReturn(10, todayRow, liveQuote({ updated_at: '2026-09-30T15:30:00+09:00' }))).toBe(10)
      expect(liveWeeklyReturn(10, todayRow, undefined)).toBe(10)
    })

    it('값이 없으면 그대로 둔다', () => {
      expect(liveWeeklyReturn(null, todayRow, liveQuote())).toBeNull()
      expect(liveWeeklyReturn(10, null, liveQuote())).toBe(10)
      expect(liveWeeklyReturn(10, { ...todayRow, close_price: null }, liveQuote())).toBe(10)
    })
  })
})
