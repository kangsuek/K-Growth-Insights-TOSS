import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { realtimeApi } from '../../services/api'
import { isKrxRegularSession } from '../../utils/realtime'

// 장중에 이 시간 넘게 체결이 없으면 연결은 살아 있어도 시세가 멈춘 것으로 본다.
const STALE_TRADE_MS = 2 * 60 * 1000

const TONES = {
  ok: 'bg-green-500',
  idle: 'bg-gray-400',
  warn: 'bg-amber-500',
  error: 'bg-red-500',
}

const formatTime = (iso) => {
  if (!iso) return '없음'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false })
}

/**
 * 토스 실시간 연결 상태를 {tone, label, detail}로 요약한다.
 * 키 없음·인증 실패는 설정에서 고쳐야 하므로 장중이 아니어도 빨강으로 알린다.
 */
export function describeRealtimeStatus(data, now = new Date()) {
  const inSession = isKrxRegularSession(now)
  const lastTrade = data?.last_trade_at ? new Date(data.last_trade_at) : null
  const detail = `마지막 체결: ${formatTime(data?.last_trade_at)}${data?.last_error ? ` · ${data.last_error}` : ''}`

  if (!data) return { tone: 'idle', label: '실시간 확인 중', detail: '상태를 불러오는 중입니다' }
  if (data.status === 'no_credentials') {
    return { tone: 'error', label: '토스 키 없음', detail: '설정 → API 키에서 토스증권 키를 등록하세요', fixable: true }
  }
  if (data.status === 'auth_failed') {
    return { tone: 'error', label: '토스 인증 실패', detail: `토스증권 키를 확인하세요 · ${detail}`, fixable: true }
  }
  if (data.status !== 'connected') {
    return inSession
      ? { tone: 'error', label: '실시간 끊김', detail: `재연결 중입니다 · ${detail}` }
      : { tone: 'idle', label: '장 외', detail: `정규장(평일 09:00~15:30)이 아닙니다 · ${detail}` }
  }
  if (!inSession) return { tone: 'idle', label: '장 외', detail: `실시간 연결됨 · ${detail}` }
  if (!lastTrade || now - lastTrade > STALE_TRADE_MS) {
    return { tone: 'warn', label: '체결 지연', detail: `연결은 됐지만 최근 2분간 체결이 없습니다 · ${detail}` }
  }
  return { tone: 'ok', label: '실시간', detail }
}

/** 헤더의 토스 실시간 시세 상태 배지. 10초마다 백엔드 상태를 조회한다. */
export default function RealtimeStatusBadge() {
  const { data } = useQuery({
    queryKey: ['realtime-status'],
    queryFn: async () => (await realtimeApi.getStatus()).data,
    refetchInterval: 10000,
    retry: false,
  })
  const { tone, label, detail, fixable } = describeRealtimeStatus(data)
  const badge = (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700"
      title={detail}
      data-testid="realtime-status-badge"
    >
      <span className={`w-2 h-2 rounded-full ${TONES[tone]}`} aria-hidden="true" />
      {label}
    </span>
  )
  return fixable ? <Link to="/settings" aria-label={`${label} — 설정으로 이동`}>{badge}</Link> : badge
}
