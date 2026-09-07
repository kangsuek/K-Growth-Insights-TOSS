import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS } from "../constants";
import { getCandles } from "../services/api";
import { formatPercent, formatPrice, getPriceChangeColor } from "../utils/format";

export default function CandleChart({ symbol }) {
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

  return (
    <div className="card-bordered">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">{symbol} 일봉 종가</h2>
        {latest && (
          <div className={`text-right ${getPriceChangeColor(change)}`}>
            <span className="text-xl font-bold">{formatPrice(latest.close_price)}원</span>
            {change !== null && <span className="ml-2 text-sm">{formatPercent(changePercent)}</span>}
          </div>
        )}
      </div>

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
