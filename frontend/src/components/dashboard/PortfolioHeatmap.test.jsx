import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../../test/utils'
import PortfolioHeatmap from './PortfolioHeatmap'

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
