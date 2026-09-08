import { useEffect, useRef, useState } from 'react'
import { realtimeWsUrl } from '../services/api'

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 30000
// 체결은 불규칙하게 들어오므로, 화면 리렌더는 이 주기로만 최신값을 반영한다.
const DISPLAY_REFRESH_MS = 3000

/**
 * 백엔드 /ws/realtime에 연결해 종목별 실시간 시세(quotes)를 반환한다.
 * WS 수신 자체는 실시간이지만, 화면 표시는 3초 주기로만 갱신해 깜빡임을 줄인다.
 * 연결이 끊기면 지수 백오프로 재연결한다.
 */
export function useRealtimeMarket() {
  const [quotes, setQuotes] = useState({})
  const latestQuotesRef = useRef({})
  const backoffRef = useRef(INITIAL_BACKOFF_MS)

  useEffect(() => {
    let socket
    let reconnectTimer
    let cancelled = false

    const connect = () => {
      socket = new WebSocket(realtimeWsUrl)

      socket.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS
      }

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.type === 'snapshot') {
            latestQuotesRef.current = { ...latestQuotesRef.current, ...payload.data.quotes }
          } else if (payload.type === 'quote') {
            const quote = payload.data
            latestQuotesRef.current = { ...latestQuotesRef.current, [quote.symbol]: quote }
          }
        } catch {
          // 파싱 실패 프레임은 무시한다.
        }
      }

      socket.onclose = () => {
        if (cancelled) return
        reconnectTimer = setTimeout(connect, backoffRef.current)
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [])

  useEffect(() => {
    const interval = setInterval(() => {
      setQuotes(latestQuotesRef.current)
    }, DISPLAY_REFRESH_MS)
    return () => clearInterval(interval)
  }, [])

  return { quotes }
}
