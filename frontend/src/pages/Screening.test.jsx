import { describe, it, expect, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../test/mocks/server'
import { renderWithProviders } from '../test/utils'
import Screening from './Screening'

const BASE = 'http://localhost:8000/api/scanner'

describe('종목 발굴 진입 시 수집', () => {
  let collectCalls

  beforeEach(() => {
    collectCalls = 0
    server.use(
      http.get(BASE, () => HttpResponse.json({ items: [], total: 0, page: 1, page_size: 50 })),
      http.get(`${BASE}/themes`, () => HttpResponse.json([])),
      http.get(`${BASE}/collect-progress`, () => HttpResponse.json({ status: 'idle' })),
      http.post(`${BASE}/collect-data`, () => {
        collectCalls += 1
        return HttpResponse.json({ status: 'started' })
      }),
    )
  })

  it('지표가 오래됐어도 자동으로 수집하지 않고 배너로 권한다', async () => {
    server.use(
      http.get(`${BASE}/freshness`, () =>
        HttpResponse.json({ fresh: false, last_updated: '2026-11-18T07:33:01+09:00', missing: 0 })),
    )
    renderWithProviders(<Screening />)

    expect(await screen.findByTestId('scanner-stale-banner')).toBeInTheDocument()
    expect(collectCalls).toBe(0)

    await userEvent.click(screen.getByRole('button', { name: '지금 수집' }))
    await waitFor(() => expect(collectCalls).toBe(1))
  })

  it('지표가 최신이면 배너를 띄우지 않는다', async () => {
    server.use(
      http.get(`${BASE}/freshness`, () =>
        HttpResponse.json({ fresh: true, last_updated: '2026-11-20T09:53:39+09:00', missing: 0 })),
    )
    renderWithProviders(<Screening />)

    await waitFor(() => expect(screen.getByText('종목 발굴')).toBeInTheDocument())
    expect(screen.queryByTestId('scanner-stale-banner')).not.toBeInTheDocument()
    expect(collectCalls).toBe(0)
  })
})
