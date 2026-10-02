/**
 * 토스 실시간 시세(useRealtimeMarket의 quotes)를 배치(DB) 시세와 합치는 공용 헬퍼.
 *
 * 화면은 1초마다 갱신되는 실시간 현재가와, 스케줄러가 최대 10분 주기로 수집한 일봉을 함께 쓴다.
 * 둘을 그대로 나란히 두면 현재가는 움직이는데 차트의 오늘 봉·주간 수익률은 멈춰 있어
 * 서로 다른 값을 보여준다 — 오늘 봉과 현재가 기반 지표를 실시간 값으로 맞추는 계산을 여기 모은다.
 */

const kstParts = () => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Seoul',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).formatToParts(new Date())
  const get = (type) => parts.find((p) => p.type === type)?.value
  // 일부 런타임은 자정을 '24'로 표기한다 — intraday_prices.datetime 형식에 맞춰 '00'으로 보정.
  const hour = get('hour') === '24' ? '00' : get('hour')
  return { year: get('year'), month: get('month'), day: get('day'), hour, minute: get('minute') }
}

/**
 * 오늘 날짜(KST, YYYY-MM-DD). 클라이언트 로컬 타임존과 무관하게 Asia/Seoul 기준이다.
 */
export function todayKst() {
  const { year, month, day } = kstParts()
  return `${year}-${month}-${day}`
}

/**
 * 현재 KST 기준 "이번 분"을 intraday_prices.datetime과 동일한 포맷으로 반환한다
 * (타임존 오프셋 없는 YYYY-MM-DDTHH:MM:00, 초 단위 절삭).
 */
export function nowKstMinuteIso() {
  const { year, month, day, hour, minute } = kstParts()
  return `${year}-${month}-${day}T${hour}:${minute}:00`
}

/**
 * 오늘(KST) 체결로 갱신된 실시간 시세인지. 장 시작 전에는 quotes에 전일 체결값이 남아 있을 수
 * 있는데, 이를 오늘 봉으로 섞으면 안 되므로 updated_at 날짜로 거른다.
 */
export function isLiveToday(quote) {
  return quote?.last != null && typeof quote.updated_at === 'string'
    && quote.updated_at.slice(0, 10) === todayKst()
}

/**
 * 최신순(DESC) 일봉 배열의 오늘 봉을 실시간 시세로 합친 새 배열을 반환한다.
 *
 * - 맨 앞 행이 오늘이면 그 행을 교체한다: 시가는 실시간 시가 우선, 고가/저가는 기존 행과
 *   실시간 값 중 더 넓은 범위, 종가는 현재가, 등락률은 기준가(prev_close)로 재계산.
 *   거래량은 WS 체결이 누적 거래량을 주지 않아 기존(배치) 값을 유지한다.
 * - 맨 앞 행이 오늘이 아니면 allowAppend일 때만 오늘 봉을 새로 붙인다(거래량 null).
 *   과거 기간을 조회 중인 차트에 오늘 봉이 끼어들지 않도록 호출부가 결정한다.
 * - 오늘 체결 시세가 없으면 원본을 그대로 돌려준다.
 *
 * @param {Array} pricesDesc - [{date, open_price, high_price, low_price, close_price, volume, daily_change_pct}] 최신순
 * @param {Object} quote - {open, high, low, last, prev_close, updated_at}
 * @param {{allowAppend?: boolean}} options
 * @returns {Array}
 */
export function mergeLiveDailyCandle(pricesDesc, quote, { allowAppend = false } = {}) {
  if (!Array.isArray(pricesDesc) || !isLiveToday(quote)) return pricesDesc

  const today = todayKst()
  const last = quote.last
  const changePct = quote.prev_close ? ((last - quote.prev_close) / quote.prev_close) * 100 : null
  const head = pricesDesc[0]

  if (head?.date === today) {
    const highs = [head.high_price, quote.high, last].filter((v) => v != null)
    const lows = [head.low_price, quote.low, last].filter((v) => v != null)
    const merged = {
      ...head,
      open_price: quote.open ?? head.open_price ?? last,
      high_price: Math.max(...highs),
      low_price: Math.min(...lows),
      close_price: last,
      daily_change_pct: changePct ?? head.daily_change_pct,
    }
    return [merged, ...pricesDesc.slice(1)]
  }

  if (!allowAppend) return pricesDesc

  const open = quote.open ?? last
  return [
    {
      date: today,
      open_price: open,
      high_price: Math.max(quote.high ?? last, open, last),
      low_price: Math.min(quote.low ?? last, open, last),
      close_price: last,
      volume: null,
      daily_change_pct: changePct,
    },
    ...pricesDesc,
  ]
}

/**
 * DB 종가 기준 주간 수익률(%)을 실시간 현재가 기준으로 환산한다.
 *
 * 기준가(7일 전 종가)는 그대로 두고 현재가만 바꾼다: (1 + w) × (현재가 / DB 최신 종가) − 1.
 * DB 최신 행이 오늘이고 오늘 체결 시세가 있을 때만 환산한다 — 최신 행이 전일이면 그 주간
 * 수익률은 기준일 자체가 하루 밀려 있어 현재가만 바꾸면 기준이 섞인다.
 *
 * @param {number|null} weeklyReturn - DB 종가 기준 주간 수익률(%)
 * @param {Object} latestRow - DB 최신 일봉 행 {date, close_price}
 * @param {Object} quote - 실시간 시세
 * @returns {number|null}
 */
export function liveWeeklyReturn(weeklyReturn, latestRow, quote) {
  if (weeklyReturn == null || !latestRow?.close_price) return weeklyReturn
  if (latestRow.date !== todayKst() || !isLiveToday(quote)) return weeklyReturn
  return ((1 + weeklyReturn / 100) * (quote.last / latestRow.close_price) - 1) * 100
}
