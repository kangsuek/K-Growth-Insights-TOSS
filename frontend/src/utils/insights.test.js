import { describe, it, expect } from 'vitest'
import { calculateDailyVolatility } from './insights'

/** 최신순 가격 배열을 만든다(insights.js가 기대하는 형식). */
const priceRows = (closesDesc) => closesDesc.map((c) => ({ close_price: c }))

describe('calculateDailyVolatility', () => {
  it('표본표준편차(n-1)로 계산한다', () => {
    // 최신순 [99, 110, 100] → 일간 수익률: (99-110)/110 = -10%, (110-100)/100 = +10%
    // 평균 0, 표본표준편차 = sqrt((0.01+0.01)/1) = 0.1414... → 14.14%
    // 모표준편차였다면 sqrt(0.02/2) = 0.1 → 10.00%
    const vol = calculateDailyVolatility(priceRows([99, 110, 100]))

    expect(vol).toBeCloseTo(Math.sqrt(0.02) * 100, 6)
    expect(vol).toBeGreaterThan(10) // 모표준편차(10.00)와 확실히 구분된다
  })

  it('가격이 일정하면 변동성 0', () => {
    expect(calculateDailyVolatility(priceRows([100, 100, 100]))).toBe(0)
  })

  // n-1로 나누므로 표본 1개면 0으로 나누기가 된다(Infinity/NaN 방지).
  it('수익률 표본이 2개 미만이면 null', () => {
    expect(calculateDailyVolatility(priceRows([110, 100]))).toBeNull() // 수익률 1개
    expect(calculateDailyVolatility(priceRows([100]))).toBeNull()
    expect(calculateDailyVolatility([])).toBeNull()
    expect(calculateDailyVolatility(null)).toBeNull()
  })

  it('직전 종가가 0 이하인 구간은 건너뛴다', () => {
    // 0으로 나누는 구간을 제외하고 나머지로 계산한다
    const vol = calculateDailyVolatility(priceRows([99, 110, 100, 0]))
    expect(vol).toBeCloseTo(Math.sqrt(0.02) * 100, 6)
  })
})


describe('매매동향 금액 인사이트(주식 수 × 종가)', () => {
  it('순매수 주식 수에 그날 종가를 곱해 억원으로 말한다', async () => {
    const { generateTradingInsights } = await import('./insights')
    const flow = [
      { date: '2026-11-19', foreign_net: 50000, institutional_net: 10000, individual_net: -60000 },
      { date: '2026-11-18', foreign_net: 30000, institutional_net: 0, individual_net: -30000 },
      { date: '2026-11-17', foreign_net: 20000, institutional_net: 0, individual_net: -20000 },
    ]
    const prices = [
      { date: '2026-11-19', close_price: 100000 },
      { date: '2026-11-18', close_price: 100000 },
      { date: '2026-11-17', close_price: 100000 },
    ]
    // (60,000 + 30,000 + 20,000)주 × 100,000원 = 110억원
    const texts = generateTradingInsights(flow, prices).map((i) => i.text)
    expect(texts).toContain('최근 3일 외국인+기관 순매수 약 110억원')
  })

  it('종가를 모르면 주식 수를 금액으로 말하지 않는다', async () => {
    const { generateTradingInsights } = await import('./insights')
    const flow = [
      { date: '2026-11-19', foreign_net: 5000000000, institutional_net: 0 },
      { date: '2026-11-18', foreign_net: 0, institutional_net: 0 },
      { date: '2026-11-17', foreign_net: 0, institutional_net: 0 },
    ]
    const texts = generateTradingInsights(flow).map((i) => i.text)
    expect(texts.some((t) => t.includes('억원'))).toBe(false)
  })
})
