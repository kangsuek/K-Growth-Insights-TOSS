import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../test/utils'
import PortfolioHeatmap, { buildSparkPath, sessionPrevClose } from './PortfolioHeatmap'

// jsdom은 레이아웃이 없어 컨테이너 너비가 0으로 측정된다 — 격자가 그려지도록 고정 너비를 준다.
vi.mock('../../hooks/useContainerWidth', () => ({
  useContainerWidth: () => ({ containerRef: { current: null }, width: 1200 }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const etfs = [
  { ticker: '005930', name: '삼성전자' },
  { ticker: '000660', name: 'SK하이닉스' },
]

const batchSummary = {
  '005930': { latest_price: { close_price: 70000, daily_change_pct: 1.23 }, weekly_return: 2.5 },
  '000660': { latest_price: { close_price: 180000, daily_change_pct: -0.8 }, weekly_return: -1.2 },
}

describe('전체 현황 히트맵', () => {
  beforeEach(() => {
    mockNavigate.mockClear()
  })

  it('종목마다 셀을 그리고 등락률을 표시한다', () => {
    renderWithProviders(<PortfolioHeatmap etfs={etfs} batchSummary={batchSummary} />)

    expect(screen.getByText('(2종목)')).toBeInTheDocument()
    expect(screen.getByTestId('heatmap-cell-005930')).toBeInTheDocument()
    expect(screen.getByTestId('heatmap-cell-000660')).toBeInTheDocument()
    expect(screen.getByText('+1.2%')).toBeInTheDocument()
    expect(screen.getByText('-0.8%')).toBeInTheDocument()
  })

  it('셀을 클릭하면 종목 상세로 이동한다', () => {
    renderWithProviders(<PortfolioHeatmap etfs={etfs} batchSummary={batchSummary} />)

    fireEvent.click(screen.getByTestId('heatmap-cell-000660'))
    expect(mockNavigate).toHaveBeenCalledWith('/etf/000660')
  })

  it('셀을 우클릭하면 컨텍스트 메뉴 콜백을 호출한다', () => {
    const onContextMenu = vi.fn()
    renderWithProviders(
      <PortfolioHeatmap etfs={etfs} batchSummary={batchSummary} onContextMenu={onContextMenu} />
    )

    fireEvent.contextMenu(screen.getByTestId('heatmap-cell-005930'), { clientX: 10, clientY: 20 })
    expect(onContextMenu).toHaveBeenCalledWith(10, 20, '005930', '삼성전자')
  })

  it('요약 데이터가 없으면 렌더링하지 않는다', () => {
    const { container } = renderWithProviders(<PortfolioHeatmap etfs={etfs} batchSummary={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})

describe('미니그래프 전일 종가 기준선', () => {
  const today = new Date().toLocaleDateString('en-CA') // YYYY-MM-DD(로컬) — 컴포넌트와 같은 기준
  const intraday = { '005930': { date: today, data: [{ price: 70500 }, { price: 71000 }, { price: 70800 }] } }

  it('실시간 시세의 전일 종가(prev_close)로 가로 점선을 그리고 툴팁에 표시한다', () => {
    const quotes = { '005930': { last: 70800, prev_close: 70000, updated_at: `${today}T10:00:00+09:00` } }
    renderWithProviders(
      <PortfolioHeatmap etfs={[etfs[0]]} batchSummary={batchSummary} quotes={quotes} intradayByTicker={intraday} />
    )
    const line = screen.getByTestId('heatmap-prev-close-line')
    // 전일 종가(70,000)가 분봉 최저가보다 낮아 스케일 맨 아래 = 차트 높이(48)에 온다
    expect(Number(line.getAttribute('y1'))).toBeCloseTo(48)
    expect(line.getAttribute('y1')).toBe(line.getAttribute('y2'))
    expect(screen.getByTestId('heatmap-cell-005930').textContent).toContain('전일 종가: 70,000원')
  })

  it('실시간 시세가 없으면 일봉 등락률로 역산한 기준가를 쓴다', () => {
    const summary = {
      '005930': {
        latest_price: { date: today, close_price: 70800, daily_change_pct: 1.143 },
        prices: [{ date: today, close_price: 70800, daily_change_pct: 1.143 }],
        weekly_return: 2.5,
      },
    }
    renderWithProviders(
      <PortfolioHeatmap etfs={[etfs[0]]} batchSummary={summary} intradayByTicker={intraday} />
    )
    expect(screen.getByTestId('heatmap-prev-close-line')).toBeInTheDocument()
    expect(screen.getByTestId('heatmap-cell-005930').textContent).toContain('전일 종가: 70,000원')
  })

  it('전일 종가를 구할 수 없으면 기준선을 그리지 않는다', () => {
    renderWithProviders(
      <PortfolioHeatmap etfs={[etfs[0]]} batchSummary={batchSummary} intradayByTicker={intraday} />
    )
    expect(screen.queryByTestId('heatmap-prev-close-line')).not.toBeInTheDocument()
  })
})

describe('buildSparkPath / sessionPrevClose', () => {
  it('기준선을 스케일에 포함해 위·아래 어디든 차트 안에 둔다', () => {
    const above = buildSparkPath([100, 101, 102], 100, 40, 110)
    expect(above.baseY).toBeCloseTo(0)   // 최고가보다 높으면 맨 위
    const inside = buildSparkPath([100, 110], 100, 40, 105)
    expect(inside.baseY).toBeCloseTo(20) // 중간
    expect(buildSparkPath([100, 110], 100, 40, null).baseY).toBeNull()
  })

  it('세션 날짜 행이 없으면 그 이전 최근 종가로 폴백한다', () => {
    const prices = [
      { date: '2026-10-02', close_price: 105, daily_change_pct: 5 },
      { date: '2026-10-01', close_price: 100, daily_change_pct: 0 },
    ]
    expect(sessionPrevClose(prices, '2026-10-02')).toBeCloseTo(100)
    expect(sessionPrevClose(prices.slice(1), '2026-10-02')).toBe(100)
    expect(sessionPrevClose([], '2026-10-02')).toBeNull()
    expect(sessionPrevClose(prices, null)).toBeNull()
  })
})
