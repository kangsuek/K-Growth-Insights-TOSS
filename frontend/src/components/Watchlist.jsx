import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useToast } from "../contexts/ToastContext";
import { addToWatchlist, getWatchlist, removeFromWatchlist } from "../services/api";

export default function Watchlist({ selectedSymbol, onSelect }) {
  const [symbolInput, setSymbolInput] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (stock) => {
      setSymbolInput("");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      onSelect(stock.symbol);
      toast.success(`${stock.name}(${stock.symbol})을(를) 추가했습니다.`);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || "종목 추가에 실패했습니다.");
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
    <div className="card-bordered">
      <h2 className="text-lg font-semibold mb-3">관심종목</h2>
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          className="input"
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          placeholder="종목코드 (예: 005930)"
        />
        <button type="submit" className="btn-primary shrink-0" disabled={addMutation.isPending}>
          추가
        </button>
      </form>

      {isLoading && <p className="text-gray-500 dark:text-gray-400">불러오는 중...</p>}
      {!isLoading && stocks.length === 0 && (
        <p className="text-gray-500 dark:text-gray-400">관심종목이 없습니다. 종목코드를 추가해보세요.</p>
      )}

      <ul className="divide-y divide-gray-100 dark:divide-gray-700">
        {stocks.map((stock) => (
          <li
            key={stock.symbol}
            onClick={() => onSelect(stock.symbol)}
            className={`flex items-center justify-between gap-2 px-2 py-2.5 rounded-lg cursor-pointer transition-colors ${
              stock.symbol === selectedSymbol
                ? "bg-primary-50 dark:bg-primary-900/30"
                : "hover:bg-gray-50 dark:hover:bg-gray-700/50"
            }`}
          >
            <span className="text-sm">
              <span className="font-medium">{stock.name}</span>
              <span className="text-gray-500 dark:text-gray-400"> ({stock.symbol}) · {stock.market}</span>
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeMutation.mutate(stock.symbol);
              }}
              className="btn-danger px-2 py-1 text-xs"
            >
              삭제
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
