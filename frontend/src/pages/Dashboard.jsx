import { useState } from "react";
import Watchlist from "../components/Watchlist";
import CandleChart from "../components/CandleChart";
import TradingFlowChart from "../components/TradingFlowChart";

export default function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  return (
    <div className="animate-fadeIn grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
      <Watchlist selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
      <div className="flex flex-col gap-6">
        <CandleChart symbol={selectedSymbol} />
        <TradingFlowChart symbol={selectedSymbol} />
      </div>
    </div>
  );
}
