import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getTradingFlow } from "../services/api";
import { formatPercent, formatPrice, getPriceChangeColor } from "../utils/format";

function NetFlowBadge({ label, value }) {
  if (value === null || value === undefined) return null;
  const sign = value > 0 ? "+" : "";
  return (
    <span className={`text-xs ${getPriceChangeColor(value)}`}>
      {label} {sign}
      {value.toLocaleString("ko-KR")}
    </span>
  );
}

export default function StockCard({ stock, quote, onDelete }) {
  const { data: flows = [] } = useQuery({
    queryKey: ["trading-flow", stock.symbol],
    queryFn: () => getTradingFlow(stock.symbol, 1),
  });
  const latestFlow = flows.at(-1);

  const last = quote?.last;
  const change = last != null && quote?.prev_close != null ? last - quote.prev_close : null;
  const changePercent = change !== null && quote.prev_close ? (change / quote.prev_close) * 100 : null;

  return (
    <article className="card-interactive animate-fadeIn">
      <Link to={`/stocks/${stock.symbol}`} className="block">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="font-semibold">{stock.name}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {stock.symbol} · {stock.market}
            </p>
          </div>
          <span className="badge bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
            {stock.security_type}
          </span>
        </div>

        <div className={`mb-2 ${getPriceChangeColor(change)}`}>
          <span className="text-xl font-bold">{last != null ? `${formatPrice(last)}원` : "-"}</span>
          {changePercent !== null && <span className="ml-2 text-sm">{formatPercent(changePercent)}</span>}
        </div>

        <dl className="grid grid-cols-3 gap-1 text-xs text-gray-500 dark:text-gray-400 mb-2">
          <div>
            <dt>시가</dt>
            <dd className="text-gray-800 dark:text-gray-200">{quote?.open != null ? formatPrice(quote.open) : "-"}</dd>
          </div>
          <div>
            <dt>고가</dt>
            <dd className="text-gray-800 dark:text-gray-200">{quote?.high != null ? formatPrice(quote.high) : "-"}</dd>
          </div>
          <div>
            <dt>저가</dt>
            <dd className="text-gray-800 dark:text-gray-200">{quote?.low != null ? formatPrice(quote.low) : "-"}</dd>
          </div>
        </dl>

        {latestFlow && (
          <div className="flex gap-2 flex-wrap">
            <NetFlowBadge label="개인" value={latestFlow.individual_net} />
            <NetFlowBadge label="외국인" value={latestFlow.foreigner_net} />
            <NetFlowBadge label="기관" value={latestFlow.institution_net} />
          </div>
        )}
      </Link>

      <button
        onClick={() => onDelete(stock.symbol)}
        className="btn-danger mt-3 px-2 py-1 text-xs"
      >
        삭제
      </button>
    </article>
  );
}
