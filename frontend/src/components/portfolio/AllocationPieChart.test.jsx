import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import AllocationPieChart from './AllocationPieChart'

// jsdom은 레이아웃이 없어 ResponsiveContainer 크기가 0이 된다 — 고정 크기로 그리게 한다.
vi.mock('recharts', async () => {
  const actual = await vi.importActual('recharts')
  const { cloneElement } = await vi.importActual('react')
  return {
    ...actual,
    ResponsiveContainer: ({ children }) => cloneElement(children, { width: 600, height: 300 }),
  }
})

const pieLabels = (container) =>
  [...container.querySelectorAll('.recharts-pie text')].map((t) => t.textContent).filter((t) => /%$/.test(t))

const allocation = (a, b) => [
  { name: 'A', value: a, percent: (a / (a + b)) * 100 },
  { name: 'B', value: b, percent: (b / (a + b)) * 100 },
]

describe('포트폴리오 비중 파이차트', () => {
  it('비중 라벨을 애니메이션 없이 바로 그린다', () => {
    const { container } = render(<AllocationPieChart data={allocation(600, 400)} />)
    expect(pieLabels(container)).toEqual(['60.0%', '40.0%'])
  })

  it('실시간 시세로 데이터가 바뀌어도 라벨이 사라지지 않고 새 값으로 바뀐다', () => {
    const { container, rerender } = render(<AllocationPieChart data={allocation(600, 400)} />)
    rerender(<AllocationPieChart data={allocation(700, 300)} />)
    expect(pieLabels(container)).toEqual(['70.0%', '30.0%'])
  })

  it('비중 5% 미만 조각은 라벨을 생략한다', () => {
    const { container } = render(<AllocationPieChart data={allocation(970, 30)} />)
    expect(pieLabels(container)).toEqual(['97.0%'])
  })
})
