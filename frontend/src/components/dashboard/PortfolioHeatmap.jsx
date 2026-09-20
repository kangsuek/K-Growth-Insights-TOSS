import { useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Treemap, ResponsiveContainer } from 'recharts'
import { format } from 'date-fns'
import PropTypes from 'prop-types'

/**
 * 일간 변동률에 따른 셀 배경색
 * @param {number} changePct - 일간 변동률 (%)
 * @returns {string} hex color
 */
const getChangeColor = (changePct) => {
  if (changePct == null || isNaN(changePct)) return '#9ca3af'
  if (changePct >= 3) return '#15803d'
  if (changePct >= 1.5) return '#16a34a'
  if (changePct >= 0.5) return '#22c55e'
  if (changePct >= 0) return '#86efac'
  if (changePct >= -0.5) return '#fca5a5'
  if (changePct >= -1.5) return '#ef4444'
  if (changePct >= -3) return '#dc2626'
  return '#991b1b'
}

/**
 * 배경색 대비 텍스트 색상
 * @param {number} changePct - 일간 변동률 (%)
 * @returns {string} hex color
 */
const getTextColor = (changePct) => {
  if (changePct == null || isNaN(changePct)) return '#374151'
  if (Math.abs(changePct) < 0.5) return '#1f2937'
  return '#ffffff'
}

/**
 * 가격 포맷 (한국 원화)
 * @param {number} price
 * @returns {string}
 */
const formatPrice = (price) => {
  if (!price) return ''
  return price.toLocaleString('ko-KR')
}

// 스파크라인 path 길이를 제한하기 위한 최대 표시 포인트 수
const MAX_SPARK_POINTS = 40

/**
 * 가격 배열 → 스파크라인 SVG path(d) 문자열(라인 + 면적 채움 + 마지막 점 좌표).
 * 포인트가 많으면 균등 간격으로 다운샘플링한다.
 * @param {number[]} prices
 * @param {number} w - 사용 가능한 너비(px)
 * @param {number} h - 사용 가능한 높이(px)
 */
const buildSparkPath = (prices, w, h) => {
  if (!prices || prices.length < 2 || w <= 0 || h <= 0) return null
  let pts = prices
  if (pts.length > MAX_SPARK_POINTS) {
    const step = (pts.length - 1) / (MAX_SPARK_POINTS - 1)
    pts = Array.from({ length: MAX_SPARK_POINTS }, (_, i) => pts[Math.round(i * step)])
  }
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  const stepX = w / (pts.length - 1)
  const coords = pts.map((p, i) => [i * stepX, h - ((p - min) / range) * h])
  const linePath = coords
    .map(([px, py], i) => `${i === 0 ? 'M' : 'L'}${px.toFixed(1)},${py.toFixed(1)}`)
    .join(' ')
  const areaPath = `${linePath} L${w.toFixed(1)},${h.toFixed(1)} L0,${h.toFixed(1)} Z`
  const [dotX, dotY] = coords[coords.length - 1]
  return { linePath, areaPath, dotX, dotY }
}

/**
 * MACD/Signal 배열 → 히스토그램 막대 + 두 선 path(d). ETF 상세 'MACD (12, 26, 9)'
 * 카드(components/charts/MACDChart.jsx)와 같은 배색(히스토그램 양수 빨강/음수 파랑)을
 * 최종 픽셀 좌표로 직접 계산한다(스파크라인과 동일하게 <g transform>으로 배치).
 * @param {number[]} macdArr
 * @param {number[]} signalArr
 * @param {number} w - 사용 가능한 너비(px)
 * @param {number} h - 사용 가능한 높이(px)
 */
const buildMacdCombo = (macdArr, signalArr, w, h) => {
  if (!macdArr || macdArr.length < 2 || w <= 0 || h <= 0) return null
  const n = macdArr.length
  const histArr = macdArr.map((m, i) => m - signalArr[i])
  const all = [...macdArr, ...signalArr, 0]
  const min = Math.min(...all)
  const max = Math.max(...all)
  const range = max - min || 1
  const toY = (v) => h - ((v - min) / range) * h
  const stepX = w / (n - 1)
  const zeroY = toY(0)
  const barW = Math.min(6, stepX * 0.5)

  const toPath = (arr) => arr
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * stepX).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(' ')

  const bars = histArr.map((v, i) => ({
    x: i * stepX - barW / 2,
    y: toY(Math.max(v, 0)),
    w: barW,
    h: Math.abs(toY(v) - zeroY),
    color: v >= 0 ? '#ef4444' : '#3b82f6', // MACDChart.jsx COLORS.MACD_HIST_POS/NEG과 동일
  }))

  return { macdLinePath: toPath(macdArr), signalLinePath: toPath(signalArr), bars }
}

/**
 * Treemap 셀 커스텀 렌더러
 * 종목명, 일간·주간 변동률을 표시. 셀이 충분히 크면 이름 아래 일간·주간 등락률을
 * 한 줄로, 그 다음 줄에 분봉 스파크라인(+폭이 넉넉하면 MACD 미니차트)을 보여주고,
 * 작으면 기존 중앙정렬 텍스트를 보여준다.
 */
const HeatmapCell = (props) => {
  const { x, y, width, height, name, ticker, changePct, closePrice, weeklyReturn, sparkPrices, macdSeries, isFallbackDay, isInvested, depth, onContextMenu } = props

  // root 노드(depth 0)는 렌더링하지 않음
  if (depth !== 1) return null
  if (width < 2 || height < 2) return null

  const bgColor = getChangeColor(changePct)
  const textColor = getTextColor(changePct)

  // 텍스트 영역 내부 패딩 (상하 4px)
  const padY = 4
  const innerH = Math.max(height - 2, 0)
  const textAreaH = innerH - padY * 2

  // 셀 크기별 표시 레벨 (텍스트 영역 기준)
  const canShowName = width > 50 && textAreaH > 14
  const canShowPrice = width > 60 && textAreaH > 36
  const canShowChange = width > 40 && textAreaH > 14
  const canShowWeekly = width > 60 && textAreaH > 50

  // 셀 폭에 맞게 이름 자르기
  const maxChars = Math.floor(width / 9)
  const displayName = name && name.length > maxChars
    ? name.slice(0, maxChars - 1) + '..'
    : name

  const changeStr = changePct != null
    ? `${changePct >= 0 ? '+' : ''}${changePct.toFixed(1)}%`
    : ''

  const weeklyStr = weeklyReturn != null
    ? `주간 ${weeklyReturn >= 0 ? '+' : ''}${weeklyReturn.toFixed(1)}%`
    : ''

  // 표시할 줄 수에 따라 세로 간격 조정
  const lines = [canShowName, canShowPrice, canShowChange, canShowWeekly].filter(Boolean).length
  const lineHeight = 14
  // 텍스트 블록 중앙 정렬, 패딩 범위 내로 클램핑
  const centerY = y + 1 + padY + textAreaH / 2
  const blockH = (lines - 1) * lineHeight
  const rawStartY = centerY - blockH / 2
  const minStartY = y + 1 + padY + lineHeight / 2
  const maxStartY = y + height - 1 - padY - lineHeight / 2 - blockH
  const startY = Math.max(minStartY, Math.min(rawStartY, maxStartY))
  let currentLine = 0

  // 세로 스택형 레이아웃: 이름 → (일간%+주간% 한 줄) → (분봉 스파크라인 + MACD) 순.
  // 셀이 작으면 canShowSpark가 false가 되어 아래 기존 중앙정렬 텍스트로 자동 폴백한다.
  const padX = 8
  const nameRowH = 16
  const gapAfterName = 4
  const percentRowH = 16
  const gapAfterPercent = 4
  const detailTop = y + 1 + padY + nameRowH + gapAfterName   // 등락률 줄 시작
  const detailH = Math.max(textAreaH - nameRowH - gapAfterName, 0)
  const chartTop = detailTop + percentRowH + gapAfterPercent
  const chartRowH = Math.max(detailH - percentRowH - gapAfterPercent, 0)
  const contentX = x + 1 + padX
  const contentW = Math.max(width - 2 * padX, 0)

  // 예전엔 텍스트와 차트가 한 줄을 나눠 썼지만 이제 세로로 쌓이므로 폭은 덜 필요하고
  // (차트가 줄 전체를 씀) 높이는 더 필요하다(줄이 하나 늘었다).
  const canShowSpark = width >= 100 && innerH >= 80 && sparkPrices?.length >= 2
  const hasMacdData = macdSeries && macdSeries.length >= 2
  const canShowMacd = canShowSpark && width >= 170 && hasMacdData

  const chartGap = 8
  const chartH = Math.min(chartRowH, 48)
  const chartY = chartTop + (chartRowH - chartH) / 2
  const sparkW = canShowMacd ? Math.max(40, (contentW - chartGap) / 2) : Math.min(140, contentW)
  const macdW = sparkW
  const macdX = contentX + sparkW + chartGap
  const spark = buildSparkPath(sparkPrices, sparkW, chartH)
  const macd = canShowMacd
    ? buildMacdCombo(macdSeries.map((p) => p.macd), macdSeries.map((p) => p.signal), macdW, chartH)
    : null

  // clipPath ID: 셀마다 고유하게
  const clipId = `hm-clip-${Math.round(x)}-${Math.round(y)}`

  // 네이티브 툴팁 텍스트
  const tooltipText = [
    name,
    closePrice ? `종가: ${formatPrice(closePrice)}원` : '',
    `일간: ${changeStr}`,
    weeklyReturn != null ? `주간: ${weeklyStr}` : '',
    isFallbackDay ? '당일 거래 없음(최근 거래일 데이터)' : '',
  ].filter(Boolean).join('\n')

  return (
    <g
      style={{ cursor: 'pointer' }}
      onContextMenu={(e) => {
        e.preventDefault()
        onContextMenu?.(e.clientX, e.clientY, ticker, name)
      }}
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={x + 1} y={y + 1} width={Math.max(width - 2, 0)} height={innerH} rx={4} />
        </clipPath>
      </defs>
      <rect
        x={x + 1}
        y={y + 1}
        width={Math.max(width - 2, 0)}
        height={innerH}
        fill={bgColor}
        rx={4}
        stroke={isInvested ? '#00e5ff' : 'none'}
        strokeWidth={isInvested ? 3 : 0}
      />
      <title>{tooltipText}</title>
      <g clipPath={`url(#${clipId})`} style={{ pointerEvents: 'none' }}>
        {canShowSpark ? (
          <>
            <text
              x={contentX}
              y={y + 1 + padY + nameRowH / 2}
              textAnchor="start"
              dominantBaseline="central"
              fill={textColor}
              fontSize={12}
              fontWeight="600"
            >
              {displayName}
            </text>
            {isFallbackDay && (
              <text
                x={x + width - 1 - padX}
                y={y + 1 + padY + nameRowH / 2}
                textAnchor="end"
                dominantBaseline="central"
                fill={textColor}
                fontSize={9}
                fontWeight="700"
                opacity={0.85}
              >
                무거래
              </text>
            )}
            <text
              x={contentX}
              y={detailTop + percentRowH / 2}
              textAnchor="start"
              dominantBaseline="central"
              fill={textColor}
              fontSize={14}
              fontWeight="bold"
            >
              {changeStr}
            </text>
            {weeklyReturn != null && (
              <text
                x={contentX + 50}
                y={detailTop + percentRowH / 2}
                textAnchor="start"
                dominantBaseline="central"
                fill={textColor}
                fontSize={10}
                opacity={0.8}
              >
                {weeklyStr.replace('주간 ', '')}
              </text>
            )}
            <g transform={`translate(${contentX}, ${chartY})`}>
              <path d={spark.areaPath} fill={textColor} opacity={0.18} />
              <path
                d={spark.linePath}
                fill="none"
                stroke={textColor}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.95}
              />
              <circle cx={spark.dotX} cy={spark.dotY} r={2} fill={textColor} />
            </g>
            {canShowMacd && macd && (
              <g transform={`translate(${macdX}, ${chartY})`}>
                {macd.bars.map((bar, i) => (
                  <rect key={i} x={bar.x} y={bar.y} width={bar.w} height={bar.h} fill={bar.color} opacity={0.8} />
                ))}
                <path
                  d={macd.macdLinePath}
                  fill="none"
                  stroke="#2563eb"
                  strokeWidth={1.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d={macd.signalLinePath}
                  fill="none"
                  stroke={textColor}
                  strokeWidth={1.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </g>
            )}
          </>
        ) : (
          <>
            {canShowName && (
              <text
                x={x + width / 2}
                y={startY + lineHeight * currentLine++}
                textAnchor="middle"
                dominantBaseline="central"
                fill={textColor}
                fontSize={11}
                fontWeight="600"
              >
                {displayName}
              </text>
            )}
            {canShowPrice && closePrice && (
              <text
                x={x + width / 2}
                y={startY + lineHeight * currentLine++}
                textAnchor="middle"
                dominantBaseline="central"
                fill={textColor}
                fontSize={10}
                fontWeight="normal"
              >
                {formatPrice(closePrice)}원
              </text>
            )}
            {canShowChange && (
              <text
                x={x + width / 2}
                y={startY + lineHeight * currentLine++}
                textAnchor="middle"
                dominantBaseline="central"
                fill={textColor}
                fontSize={12}
                fontWeight="bold"
              >
                {changeStr}
              </text>
            )}
            {canShowWeekly && weeklyReturn != null && (
              <text
                x={x + width / 2}
                y={startY + lineHeight * currentLine++}
                textAnchor="middle"
                dominantBaseline="central"
                fill={textColor}
                fontSize={9}
                fontWeight="normal"
                opacity={0.85}
              >
                {weeklyStr}
              </text>
            )}
          </>
        )}
      </g>
    </g>
  )
}

/**
 * PortfolioHeatmap Component
 *
 * 대시보드 상단에 표시되는 포트폴리오 히트맵 (Treemap 스타일)
 * - 셀 크기: 모든 종목 동일 (투자 종목 구분은 테두리 색상으로 표시)
 * - 셀 색상: 일간 변동률 (녹색=상승, 적색=하락)
 * - 셀 내용: 종목명, 종가, 일간 변동률, 주간 수익률
 * - 셀 클릭: ETF 상세 페이지로 이동
 *
 * @param {Array} etfs - ETF 종목 배열
 * @param {Object} batchSummary - 배치 요약 데이터 {ticker: summary} (weekly_macd 포함)
 * @param {Function} onContextMenu - 셀 우클릭 콜백 (x, y, ticker, name)
 */
export default function PortfolioHeatmap({ etfs, batchSummary, quotes, intradayByTicker, onContextMenu }) {
  const navigate = useNavigate()

  const heatmapData = useMemo(() => {
    if (!etfs || etfs.length === 0 || !batchSummary) return []

    const items = []
    const todayStr = format(new Date(), 'yyyy-MM-dd')

    for (const etf of etfs) {
      const summary = batchSummary[etf.ticker]
      const latestPrice = summary?.latest_price || summary?.prices?.[0]
      const liveQuote = quotes?.[etf.ticker]
      const hasLiveQuote = liveQuote?.last != null

      // 토스 실시간 시세가 있으면 그 값으로 종가·등락률을 교체(3초 주기 갱신).
      const closePrice = hasLiveQuote ? liveQuote.last : (latestPrice?.close_price ?? null)
      const changePct = hasLiveQuote && liveQuote.prev_close
        ? ((liveQuote.last - liveQuote.prev_close) / liveQuote.prev_close) * 100
        : (latestPrice?.daily_change_pct ?? 0)
      const weeklyReturn = summary?.weekly_return ?? null

      // 스파크라인: 과거 분봉(배치, 자동갱신 주기)은 그대로 두고 마지막 점만
      // 토스 실시간 시세(quotes, 3초 주기)로 치환해 끝점만 실시간으로 움직이게 한다.
      const intraday = intradayByTicker?.[etf.ticker]
      const basePrices = (intraday?.data ?? []).map((d) => d.price)
      const sparkPrices = hasLiveQuote
        ? [...basePrices.slice(0, -1), liveQuote.last]
        : basePrices
      // 유동성이 낮아 당일 체결이 없는 종목은 백엔드가 직전 거래일 분봉으로
      // 폴백해서 돌려준다 — 스파크라인이 오늘 것처럼 보이지 않게 표시해둔다.
      const isFallbackDay = !!(intraday?.date && intraday.date !== todayStr)

      items.push({
        name: etf.name,
        ticker: etf.ticker,
        size: 1, // 모든 종목 동일 크기
        changePct: Number(changePct) || 0,
        closePrice,
        weeklyReturn: weeklyReturn != null ? Number(weeklyReturn) : null,
        sparkPrices,
        macdSeries: summary?.weekly_macd ?? null,
        isFallbackDay,
        isInvested: !!(etf.purchase_price && etf.quantity),
      })
    }

    return items
  }, [etfs, batchSummary, quotes, intradayByTicker])

  const handleClick = useCallback((node) => {
    if (node?.ticker) {
      navigate(`/etf/${node.ticker}`)
    }
  }, [navigate])

  if (heatmapData.length === 0) return null

  return (
    <div className="card p-4 mb-6">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
        </svg>
        전체 현황
        <span className="text-xs font-normal text-gray-500 dark:text-gray-400">
          ({heatmapData.length}종목)
        </span>
      </h3>
      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <Treemap
            data={heatmapData}
            dataKey="size"
            ratio={4 / 3}
            content={<HeatmapCell onContextMenu={onContextMenu} />}
            onClick={handleClick}
            isAnimationActive={false}
          />
        </ResponsiveContainer>
      </div>
    </div>
  )
}

PortfolioHeatmap.propTypes = {
  etfs: PropTypes.array.isRequired,
  batchSummary: PropTypes.object,
  quotes: PropTypes.object,  // {ticker: {last, prev_close, ...}} (토스 실시간 시세)
  intradayByTicker: PropTypes.object,  // {ticker: {date, data: [{datetime, price}], ...}} (분봉 배치, date로 당일 거래 유무 판단)
  onContextMenu: PropTypes.func,
}
