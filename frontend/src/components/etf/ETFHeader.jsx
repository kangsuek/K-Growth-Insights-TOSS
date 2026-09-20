import PropTypes from 'prop-types'

/**
 * ETFHeader 컴포넌트
 * ETF 상세 페이지의 헤더 영역 (종목명, 티커, 테마, STOCK/ETF 타입 뱃지)
 * 
 * @param {Object} etf - ETF 정보 객체
 */
export default function ETFHeader({ etf }) {
  return (
    <div className="sticky top-[68px] z-40 mb-4">
      {/* 배경 레이어 (전체 너비) */}
      <div className="absolute inset-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 shadow-sm -mx-4 sm:-mx-6 lg:-mx-8 transition-colors"></div>
      {/* 내용 레이어 (카드와 동일한 패딩) */}
      <div className="relative py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">{etf?.name || 'ETF 상세'}</h1>
            <p className="text-gray-600 dark:text-gray-400 flex items-center gap-2">
              <span>{etf?.ticker} · {etf?.theme}</span>
              {etf?.type && (
                <span
                  className={`badge ${etf.type === 'ETF' ? 'badge-primary' : 'badge-info'}`}
                  role="status"
                  aria-label={`상품 유형: ${etf.type}`}
                >
                  {etf.type}
                </span>
              )}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

ETFHeader.propTypes = {
  etf: PropTypes.shape({
    name: PropTypes.string,
    ticker: PropTypes.string,
    theme: PropTypes.string,
    type: PropTypes.string,
  }),
}

