import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { COLORS } from "../constants";

function formatTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleTimeString("ko-KR", { hour12: false });
}

export default function RealtimeTradeChart({ ticks = [] }) {
  return (
    <div className="card-bordered">
      <h2 className="text-lg font-semibold mb-3">실시간 체결 추이</h2>
      {ticks.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400 py-8 text-center">
          아직 수신된 체결이 없습니다. 장중에는 체결이 발생하는 즉시 표시됩니다.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={ticks}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.CHART_GRID} />
            <XAxis dataKey="timestamp" stroke={COLORS.CHART_AXIS} tickFormatter={formatTime} minTickGap={40} />
            <YAxis
              domain={["auto", "auto"]}
              stroke={COLORS.CHART_AXIS}
              tickFormatter={(v) => v.toLocaleString("ko-KR")}
            />
            <Tooltip labelFormatter={formatTime} formatter={(v) => v.toLocaleString("ko-KR")} />
            <Line type="monotone" dataKey="price" stroke={COLORS.CHART_PRIMARY} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
