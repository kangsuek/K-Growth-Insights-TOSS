import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../test/mocks/server'
import { renderWithProviders } from '../../test/utils'
import ApiKeysPanel from './ApiKeysPanel'

const URL = 'http://localhost:8000/api/settings/api-keys'

describe('ApiKeysPanel 토스 키', () => {
  it('토스 섹션을 보여주고 새 키만 저장한다(마스킹된 Secret은 보내지 않음)', async () => {
    let saved = null
    server.use(
      http.get(URL, () => HttpResponse.json({
        keys: { TOSS_CLIENT_ID: 'tsck****', TOSS_CLIENT_SECRET: 'tssk****', NAVER_CLIENT_ID: '', NAVER_CLIENT_SECRET: '' },
        configured: { toss: true, naver: false },
      })),
      http.put(URL, async ({ request }) => {
        saved = await request.json()
        return HttpResponse.json({ keys: {}, configured: { toss: true, naver: false } })
      }),
    )
    renderWithProviders(<ApiKeysPanel />)

    expect(await screen.findByText('토스증권 Open API (실시간 시세)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /수정/ }))
    const idInput = screen.getByLabelText('토스 Client ID')
    await userEvent.clear(idInput)
    await userEvent.type(idInput, 'tsck_live_new')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(saved).toEqual({ TOSS_CLIENT_ID: 'tsck_live_new' }))
    expect(await screen.findByText(/토스 실시간 시세에 다시 연결합니다/)).toBeInTheDocument()
  })
})
