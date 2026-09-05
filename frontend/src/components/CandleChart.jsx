import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getCandles } from "../services/api";

export default function CandleChart({ symbol }) {
  const { data: candles = [], isLoading } = useQuery({
    queryKey: ["candles", symbol],
    queryFn: () => getCandles(symbol),
    enabled: !!symbol,
  });

  if (!symbol) {
    return <p>관심종목을 추가하거나 선택하세요.</p>;
  }
  if (isLoading) {
    return <p>차트를 불러오는 중...</p>;
  }

  return (
    <div>
      <h2>{symbol} 일봉 종가</h2>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={candles}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="trade_date" />
          <YAxis domain={["auto", "auto"]} tickFormatter={(v) => v.toLocaleString("ko-KR")} />
          <Tooltip formatter={(v) => v.toLocaleString("ko-KR")} />
          <Line type="monotone" dataKey="close_price" stroke="#2563eb" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
