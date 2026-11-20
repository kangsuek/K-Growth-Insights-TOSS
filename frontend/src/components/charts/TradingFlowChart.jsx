import { useMemo, memo } from 'react'
import PropTypes from 'prop-types'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { format } from 'date-fns'
import { getNetBuyingColor } from '../../utils/format'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useWindowSize } from '../../hooks/useWindowSize'
import { sampleData, validateChartData } from '../../utils/chartUtils'
import { COLORS, MAX_CHART_POINTS } from '../../constants'

/**
 * 순매수 주식 수 포맷팅. 네이버 매매동향(individualPureBuyQuant 등)은 금액이 아니라
 * 순매수 '주식 수'라 주 단위로 표기한다(예: 1,814,000 → '181.4만주').
 * @param {number} value - 순매수 주식 수
 * @returns {string}
 */
export const formatShares = (value) => {
  if (value === null || value === undefined || isNaN(value)) return '-'
  const absValue = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  const fmt = (v) => v.toLocaleString('ko-KR', { minimumFractionDigits: 0, maximumFractionDigits: 1 })
  if (absValue >= 100000000) return `${sign}${fmt(absValue / 100000000)}억주`
  if (absValue >= 10000) return `${sign}${fmt(absValue / 10000)}만주`
  return `${sign}${absValue.toLocaleString('ko-KR')}주`
}

const formatNetBuying = (value) => {
  if (value === null || value === undefined || isNaN(value)) return '-'
  const label = value > 0 ? '순매수' : value < 0 ? '순매도' : '보합'
  return `${label} ${value > 0 ? '+' : ''}${formatShares(value)}`
}

/**
 * 0을 포함하는 대칭 Y축 눈금. 1·2·5×10ⁿ 간격으로 잡아 0선이 '0'으로 표시되게 한다.
 * 막대는 stackOffset="sign"으로 쌓이므로 일자별 양수 합·음수 합의 최댓값을 범위로 쓴다.
 * @param {Array} chartData - [{individual_net, institutional_net, foreign_net}]
 * @returns {{domain: number[], ticks: number[]}}
 */
export const buildSymmetricTicks = (chartData) => {
  const keys = ['individual_net', 'institutional_net', 'foreign_net']
  const extent = Math.max(0, ...chartData.map((d) => {
    const vals = keys.map((k) => d[k] || 0)
    const pos = vals.filter((v) => v > 0).reduce((a, b) => a + b, 0)
    const neg = vals.filter((v) => v < 0).reduce((a, b) => a + b, 0)
    return Math.max(pos, -neg)
  }))
  if (extent === 0) return { domain: [-1, 1], ticks: [0] }
  const rough = extent / 2
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((v) => v >= rough)
  const top = Math.ceil(extent / step) * step
  const ticks = []
  for (let v = -top; v <= top + step / 2; v += step) ticks.push(Math.round(v))
  return { domain: [-top, top], ticks }
}

/**
 * CustomTooltip 컴포넌트
 * 투자자별 매매 동향 차트의 툴팁을 커스터마이징
 */
const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) {
    return null
  }

  const data = payload[0].payload

  return (
    <div className="bg-white dark:bg-gray-800 p-3 border border-gray-300 dark:border-gray-700 rounded-lg shadow-lg transition-colors">
      <p className="text-sm font-semibold mb-2 text-gray-900 dark:text-gray-100">
        {data.date ? format(new Date(data.date), 'yyyy년 MM월 dd일') : '-'}
      </p>
      <div className="space-y-1 text-xs">
        <div className="flex justify-between gap-4">
          <span className="text-gray-600 dark:text-gray-400">개인:</span>
          <span
            className="font-semibold"
            style={{ color: getNetBuyingColor(data.individual_net) }}
          >
            {formatNetBuying(data.individual_net)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-600 dark:text-gray-400">기관:</span>
          <span
            className="font-semibold"
            style={{ color: getNetBuyingColor(data.institutional_net) }}
          >
            {formatNetBuying(data.institutional_net)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-600 dark:text-gray-400">외국인:</span>
          <span
            className="font-semibold"
            style={{ color: getNetBuyingColor(data.foreign_net) }}
          >
            {formatNetBuying(data.foreign_net)}
          </span>
        </div>
      </div>
    </div>
  )
}

/**
 * 데이터 전처리 함수
 * API 응답을 차트 데이터로 변환
 * @param {Array} data - API 응답 데이터
 * @returns {Array} - 차트용 데이터
 */
export const formatTradingFlowData = (data) => {
  if (!data || data.length === 0) return []

  // 데이터 검증
  const validation = validateChartData(data, ['date', 'individual_net', 'institutional_net', 'foreign_net'])
  if (!validation.isValid) {
    return []
  }

  const formattedData = data
    .filter((item) => {
      // 주말 데이터 제외 (토요일=6, 일요일=0)
      const dayOfWeek = new Date(item.date).getDay()
      return dayOfWeek !== 0 && dayOfWeek !== 6
    })
    .map((item) => ({
      date: item.date,
      // 순매수 주식 수(네이버 매매동향 값)를 그대로 쓴다.
      individual_net: item.individual_net,
      institutional_net: item.institutional_net,
      foreign_net: item.foreign_net,
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date)) // 날짜 오름차순 정렬

  // 대용량 데이터 샘플링 (MAX_CHART_POINTS개 이상일 경우)
  return sampleData(formattedData, MAX_CHART_POINTS)
}

/**
 * TradingFlowChart 컴포넌트
 * 개인/기관/외국인 투자자별 순매수 데이터를 StackedBarChart로 시각화
 *
 * @param {Array} data - 매매 동향 데이터 배열
 * @param {string} ticker - 종목 코드
 * @param {number} height - 차트 높이 (기본값: null, null이면 반응형)
 * @param {string} dateRange - 조회 기간 ('7d', '1m', '3m', 'custom')
 * @param {React.RefObject} scrollRef - 스크롤 컨테이너 ref (차트 동기화용)
 * @param {Function} onScroll - 스크롤 이벤트 핸들러 (차트 동기화용)
 */
const TradingFlowChart = memo(function TradingFlowChart({ data = [], ticker, height = null, dateRange = '7d', scrollRef, onScroll }) {
  // 컨테이너 너비 측정
  const { containerRef, width: containerWidth } = useContainerWidth()

  // 반응형 차트 높이
  const { chartHeight: responsiveHeight } = useWindowSize()
  const finalHeight = height || responsiveHeight

  // 데이터 전처리 및 메모이제이션
  const chartData = useMemo(() => formatTradingFlowData(data), [data])

  // Y축 범위·눈금: 0을 가운데 둔 대칭 눈금(쌓인 막대 높이 기준)
  const { domain: yDomain, ticks: yTicks } = useMemo(() => buildSymmetricTicks(chartData), [chartData])

  // X축 틱 포맷팅
  const formatXAxis = (tickItem) => {
    try {
      return format(new Date(tickItem), 'MM/dd')
    } catch {
      return tickItem
    }
  }

  // Y축 틱 포맷팅 (주 단위)
  const formatYAxis = (value) => (value === 0 ? '0' : formatShares(value))

  const is7Days = dateRange === '7d' && chartData.length <= 7
  const dataCount = chartData.length

  // 동적 막대 두께 및 차트 너비 계산
  const { barSize, chartPixelWidth, barCategoryGap, shouldShowScroll } = useMemo(() => {
    const minBarSpacing = 30
    
    if (is7Days) {
      const width = containerWidth > 0 ? containerWidth : (typeof window !== 'undefined' ? window.innerWidth - 200 : 800)
      const margin = 80
      const availableWidth = width - margin
      const calculatedBarSize = Math.max(15, Math.floor((availableWidth / dataCount) * 0.6))
      const calculatedGap = Math.max(2, Math.floor((availableWidth / dataCount) * 0.15))
      return {
        barSize: calculatedBarSize,
        chartPixelWidth: width,
        barCategoryGap: `${calculatedGap}px`,
        shouldShowScroll: false
      }
    } else {
      return {
        barSize: undefined, // Recharts 기본값 사용
        chartPixelWidth: Math.max(800, dataCount * minBarSpacing),
        barCategoryGap: dataCount > 30 ? "1%" : dataCount > 15 ? "2%" : "5%",
        shouldShowScroll: true
      }
    }
  }, [is7Days, containerWidth, dataCount])
  
  // 데이터 없음 상태 처리
  if (!chartData || chartData.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-gray-50 dark:bg-gray-800 rounded-lg transition-colors"
        style={{ height: `${finalHeight}px` }}
        role="img"
        aria-label="투자자별 매매 동향 차트 - 데이터 없음"
      >
        <p className="text-gray-500 dark:text-gray-400">표시할 매매 동향 데이터가 없습니다.</p>
      </div>
    )
  }

  return (
    <div
      ref={(node) => {
        containerRef.current = node
        if (scrollRef) {
          scrollRef.current = node
        }
      }}
      className={`w-full ${shouldShowScroll ? 'overflow-x-auto' : ''}`}
      onScroll={onScroll}
      role="img"
      aria-label={`${ticker} 투자자별 매매 동향 차트`}
    >
      <div style={{ width: `${chartPixelWidth}px`, minWidth: '100%' }}>
        <ResponsiveContainer width="100%" height={finalHeight}>
          <BarChart
            data={chartData}
            margin={{ top: 10, right: 15, left: 15, bottom: chartData.length > 15 ? 60 : 0 }}
            stackOffset="sign"
            barCategoryGap={barCategoryGap}
            barGap={0}
          >
          <CartesianGrid strokeDasharray="3 3" stroke={COLORS.CHART_GRID} />
          <XAxis
            dataKey="date"
            tickFormatter={formatXAxis}
            tick={{ fontSize: 12 }}
            stroke={COLORS.CHART_AXIS}
            interval={0}
            angle={chartData.length > 15 ? -45 : 0}
            textAnchor={chartData.length > 15 ? "end" : "middle"}
            height={chartData.length > 15 ? 60 : 30}
          />
          <YAxis
            tickFormatter={formatYAxis}
            tick={{ fontSize: 12 }}
            stroke={COLORS.CHART_AXIS}
            domain={yDomain}
            ticks={yTicks}
            width={72}
          />
          <Tooltip 
            content={<CustomTooltip />}
            wrapperStyle={{ outline: 'none' }}
            contentStyle={{ 
              backgroundColor: 'transparent', 
              border: 'none', 
              padding: 0,
              boxShadow: 'none'
            }}
          />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="square"
          />

          {/* 기준선 (y=0) */}
          <ReferenceLine y={0} stroke={COLORS.CHART_AXIS} strokeWidth={1} />

          {/* 투자자별 Bar */}
          <Bar
            dataKey="individual_net"
            fill={COLORS.CHART_PRIMARY}
            name="개인"
            stackId="stack"
            barSize={barSize}
          />
          <Bar
            dataKey="institutional_net"
            fill={COLORS.CHART_SECONDARY}
            name="기관"
            stackId="stack"
            barSize={barSize}
          />
          <Bar
            dataKey="foreign_net"
            fill={COLORS.CHART_TERTIARY}
            name="외국인"
            stackId="stack"
            barSize={barSize}
          />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
})

TradingFlowChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      individual_net: PropTypes.number.isRequired,
      institutional_net: PropTypes.number.isRequired,
      foreign_net: PropTypes.number.isRequired,
    })
  ),
  ticker: PropTypes.string.isRequired,
  height: PropTypes.number,
  dateRange: PropTypes.oneOf(['7d', '1m', '3m', '6m', 'ytd', '1y', 'custom']),
  scrollRef: PropTypes.object,
  onScroll: PropTypes.func,
}

export default TradingFlowChart