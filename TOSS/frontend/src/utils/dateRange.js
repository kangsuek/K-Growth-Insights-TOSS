// "기본 조회 기간" 설정값을 캔들/매매동향 조회 limit(영업일 수 근사)으로 변환한다.
const RANGE_TO_TRADING_DAYS = {
  "1M": 22,
  "3M": 66,
  "6M": 132,
};

export function dateRangeToLimit(range) {
  return RANGE_TO_TRADING_DAYS[range] || RANGE_TO_TRADING_DAYS["3M"];
}
