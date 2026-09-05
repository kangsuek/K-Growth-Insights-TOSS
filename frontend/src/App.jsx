import { useState } from "react";
import Watchlist from "./components/Watchlist";
import CandleChart from "./components/CandleChart";

export default function App() {
  const [selectedSymbol, setSelectedSymbol] = useState(null);

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>K-Growth Insights TOSS</h1>
      <div style={{ display: "flex", gap: "2rem" }}>
        <div style={{ minWidth: "280px" }}>
          <Watchlist selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
        </div>
        <div style={{ flex: 1 }}>
          <CandleChart symbol={selectedSymbol} />
        </div>
      </div>
    </div>
  );
}
