import { describe, it, expect } from 'vitest'
import { getLateStartTickers } from './comparison'

describe('getLateStartTickers', () => {
  it('가장 이른 시작일보다 늦게 시작한 종목만 고른다', () => {
    const statistics = {
      '005930': { start_date: '2026-04-06' },
      '000660': { start_date: '2026-04-06' },
      '0225V0': { start_date: '2026-08-04' },
    }
    expect(getLateStartTickers(statistics)).toEqual({ '0225V0': '2026-08-04' })
  })

  it('모두 같은 날 시작했거나 start_date가 없으면 빈 객체', () => {
    expect(getLateStartTickers({ a: { start_date: '2026-01-02' }, b: { start_date: '2026-01-02' } })).toEqual({})
    expect(getLateStartTickers({ a: { period_return: 1 } })).toEqual({})
    expect(getLateStartTickers(null)).toEqual({})
  })
})
