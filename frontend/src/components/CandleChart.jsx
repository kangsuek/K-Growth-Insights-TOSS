import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS } from "../constants";
import { getCandles } from "../services/api";
import { formatPercent, formatPrice, getPriceChangeColor } from "../utils/format";

export default function CandleChart({ symbol, realtimeTrade }) {
  const { data: candles = [], isLoading } = useQuery({
    queryKey: ["candles", symbol],
    queryFn: () => getCandles(symbol),
    enabled: !!symbol,
  });

  if (!symbol) {
    return (
      <div className="card-bordered text-center py-16 text-gray-500 dark:text-gray-400">
        관심종목을 추가하거나 선택하세요.
      </div>
    );
  }

  const latest = candles.at(-1);
  const previous = candles.at(-2);
  const change = latest && previous ? latest.close_price - previous.close_price : null;
  const changePercent = change !== null && previous ? (change / previous.close_price) * 100 : null;

  // 실시간 체결가는 확정 종가(latest.close_price)와 별개의 값이라 섞어 계산하지 않는다.
  // 등락은 항상 전일 확정 종가 기준으로만 계산한다.
  const realtimeChange =
    realtimeTrade && previous ? realtimeTrade.price - previous.close_price : null;
  const realtimeChangePercent =
    realtimeChange !== null && previous ? (realtimeChange / previous.close_price) * 100 : null;

  return (
    <div className="card-bordered">
      <div className="flex items-baseline justify-between mb-1">
        <h2 className="text-lg font-semibold">{symbol} 일봉 종가</h2>
        {latest && (
          <div className={`text-right ${getPriceChangeColor(change)}`}>
            <span className="text-xl font-bold">{formatPrice(latest.close_price)}원</span>
            {change !== null && <span className="ml-2 text-sm">{formatPercent(changePercent)}</span>}
          </div>
        )}
      </div>

      {realtimeTrade && (
        <div className="flex items-center justify-end gap-1.5 mb-3 text-sm">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-success-500" />
          </span>
          <span className="text-gray-500 dark:text-gray-400">실시간(미확정)</span>
          <span className={getPriceChangeColor(realtimeChange)}>
            {formatPrice(realtimeTrade.price)}원
            {realtimeChangePercent !== null && ` (${formatPercent(realtimeChangePercent)})`}
          </span>
        </div>
      )}

      {isLoading ? (
        <p className="text-gray-500 dark:text-gray-400">차트를 불러오는 중...</p>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={candles}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.CHART_GRID} />
            <XAxis dataKey="trade_date" stroke={COLORS.CHART_AXIS} />
            <YAxis
              domain={["auto", "auto"]}
              stroke={COLORS.CHART_AXIS}
              tickFormatter={(v) => v.toLocaleString("ko-KR")}
            />
            <Tooltip formatter={(v) => v.toLocaleString("ko-KR")} />
            <Line type="monotone" dataKey="close_price" stroke={COLORS.CHART_PRIMARY} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
