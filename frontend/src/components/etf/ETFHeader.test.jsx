import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ETFHeader from './ETFHeader'

describe('ETFHeader', () => {
  it('ETF 정보를 올바르게 표시한다', () => {
    const etf = {
      name: 'KODEX 반도체',
      ticker: '069660',
      theme: '반도체',
    }

    render(<ETFHeader etf={etf} />)

    expect(screen.getByText('KODEX 반도체')).toBeInTheDocument()
    expect(screen.getByText('069660 · 반도체')).toBeInTheDocument()
  })

  it('ETF 정보가 없을 때 기본값을 표시한다', () => {
    render(<ETFHeader etf={null} />)

    expect(screen.getByText('ETF 상세')).toBeInTheDocument()
  })

  it('테마가 없을 때 "null"/"undefined" 문자열 없이 렌더링된다', () => {
    const etf = {
      name: 'KODEX 반도체',
      ticker: '069660',
    }

    render(<ETFHeader etf={etf} />)

    expect(screen.getByText('KODEX 반도체')).toBeInTheDocument()
    expect(screen.getByText('069660 ·')).toBeInTheDocument()
  })

  it('타입이 ETF면 ETF 뱃지를 표시한다', () => {
    const etf = {
      name: 'KODEX 반도체',
      ticker: '069660',
      theme: '반도체',
      type: 'ETF',
    }

    render(<ETFHeader etf={etf} />)

    expect(screen.getByText('ETF')).toBeInTheDocument()
  })

  it('타입이 STOCK이면 STOCK 뱃지를 표시한다', () => {
    const etf = {
      name: 'SK하이닉스',
      ticker: '000660',
      theme: '반도체',
      type: 'STOCK',
    }

    render(<ETFHeader etf={etf} />)

    expect(screen.getByText('STOCK')).toBeInTheDocument()
  })

  it('타입이 없을 때 뱃지를 렌더링하지 않는다', () => {
    const etf = {
      name: 'KODEX 반도체',
      ticker: '069660',
      theme: '반도체',
    }

    render(<ETFHeader etf={etf} />)

    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

