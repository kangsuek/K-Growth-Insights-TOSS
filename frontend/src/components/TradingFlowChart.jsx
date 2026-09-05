import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLORS } from "../constants";
import { getTradingFlow } from "../services/api";
import { formatVolume } from "../utils/format";

export default function TradingFlowChart({ symbol }) {
  const { data: flows = [], isLoading } = useQuery({
    queryKey: ["trading-flow", symbol],
    queryFn: () => getTradingFlow(symbol),
    enabled: !!symbol,
  });

  if (!symbol) return null;

  return (
    <div className="card-bordered">
      <h2 className="text-lg font-semibold mb-3">투자자별 매매동향(순매수)</h2>
      {isLoading ? (
        <p className="text-gray-500 dark:text-gray-400">불러오는 중...</p>
      ) : flows.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400">아직 수집된 매매동향이 없습니다.</p>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={flows}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.CHART_GRID} />
            <XAxis dataKey="trade_date" stroke={COLORS.CHART_AXIS} />
            <YAxis stroke={COLORS.CHART_AXIS} tickFormatter={formatVolume} />
            <Tooltip formatter={(v) => v.toLocaleString("ko-KR")} />
            <Legend />
            <Bar dataKey="individual_net" name="개인" fill={COLORS.CHART_PRIMARY} />
            <Bar dataKey="foreigner_net" name="외국인" fill={COLORS.CHART_SECONDARY} />
            <Bar dataKey="institution_net" name="기관" fill={COLORS.CHART_TERTIARY} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
