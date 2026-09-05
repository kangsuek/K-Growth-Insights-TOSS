import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addToWatchlist, getWatchlist, removeFromWatchlist } from "../services/api";

export default function Watchlist({ selectedSymbol, onSelect }) {
  const [symbolInput, setSymbolInput] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const queryClient = useQueryClient();

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (stock) => {
      setSymbolInput("");
      setErrorMessage("");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      onSelect(stock.symbol);
    },
    onError: (error) => {
      setErrorMessage(error.response?.data?.detail || "종목 추가에 실패했습니다.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: (_data, removedSymbol) => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      if (removedSymbol === selectedSymbol) {
        onSelect(null);
      }
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (symbolInput.trim()) {
      addMutation.mutate(symbolInput.trim());
    }
  };

  return (
    <div>
      <h2>관심종목</h2>
      <form onSubmit={handleSubmit} style={{ marginBottom: "0.5rem" }}>
        <input
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="종목코드 (예: 005930)"
        />
        <button type="submit" disabled={addMutation.isPending}>
          추가
        </button>
      </form>
      {errorMessage && <p style={{ color: "red" }}>{errorMessage}</p>}

      {isLoading && <p>불러오는 중...</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {stocks.map((stock) => (
          <li
            key={stock.symbol}
            onClick={() => onSelect(stock.symbol)}
            style={{
              cursor: "pointer",
              padding: "0.25rem 0.5rem",
              background: stock.symbol === selectedSymbol ? "#eef" : "transparent",
            }}
          >
            <span>
              {stock.name} ({stock.symbol}) · {stock.market}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeMutation.mutate(stock.symbol);
              }}
              style={{ marginLeft: "0.5rem" }}
            >
              삭제
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
