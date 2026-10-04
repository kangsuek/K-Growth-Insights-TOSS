/**
 * 종목 비교 화면 공용 헬퍼.
 *
 * 비교 통계는 종목마다 '선택 기간 안의 자기 시세 전체'로 계산되므로, 최근 상장 종목은
 * 다른 종목보다 짧은 구간으로 계산된다. 그 사실을 화면에서 알리기 위해 계산 시작일이
 * 늦은 종목을 골라낸다.
 */

/**
 * 계산 시작일이 비교 종목 중 가장 이른 시작일보다 늦은 종목 → 그 시작일.
 * @param {Object|null} statistics - { ticker: { start_date, ... } }
 * @returns {Object} { ticker: 'YYYY-MM-DD' }
 */
export function getLateStartTickers(statistics) {
  if (!statistics) return {}
  const starts = Object.entries(statistics)
    .map(([ticker, s]) => [ticker, s?.start_date])
    .filter(([, d]) => d)
  if (starts.length === 0) return {}
  const earliest = starts.reduce((min, [, d]) => (d < min ? d : min), starts[0][1])
  return Object.fromEntries(starts.filter(([, d]) => d > earliest))
}
