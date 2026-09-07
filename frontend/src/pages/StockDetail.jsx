import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getWatchlist } from "../services/api";
import { useRealtimeMarket } from "../hooks/useRealtimeMarket";
import RealtimeQuoteCard from "../components/RealtimeQuoteCard";
import RealtimeTradeChart from "../components/RealtimeTradeChart";
import CandleChart from "../components/CandleChart";
import TradingFlowChart from "../components/TradingFlowChart";
import ComingSoon from "../components/common/ComingSoon";

export default function StockDetail() {
  const { symbol } = useParams();
  const { data: stocks = [] } = useQuery({ queryKey: ["watchlist"], queryFn: getWatchlist });
  const stock = stocks.find((s) => s.symbol === symbol);
  const { trades, quotes } = useRealtimeMarket();

  return (
    <div className="animate-fadeIn flex flex-col gap-6">
      <div>
        <Link to="/" className="link text-sm">
          ← 대시보드로
        </Link>
        <h2 className="text-2xl font-bold mt-1">
          {stock ? `${stock.name} (${stock.symbol})` : symbol}
        </h2>
        {stock && <p className="text-gray-500 dark:text-gray-400">{stock.market} · {stock.security_type}</p>}
      </div>

      <RealtimeQuoteCard quote={quotes[symbol]} />
      <CandleChart symbol={symbol} />
      <RealtimeTradeChart ticks={trades[symbol] || []} />
      <TradingFlowChart symbol={symbol} />

      <ComingSoon title="펀더멘털 / 뉴스 / 인사이트" />
    </div>
  );
}
