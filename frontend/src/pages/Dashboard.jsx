import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addToWatchlist, getWatchlist, removeFromWatchlist } from "../services/api";
import { useToast } from "../contexts/ToastContext";
import { useRealtimeMarket } from "../hooks/useRealtimeMarket";
import StockCard from "../components/StockCard";

export default function Dashboard() {
  const [symbolInput, setSymbolInput] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();
  const { quotes } = useRealtimeMarket();

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (stock) => {
      setSymbolInput("");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      toast.success(`${stock.name}(${stock.symbol})을(를) 추가했습니다.`);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || "종목 추가에 실패했습니다.");
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
    },
  });

  const handleSubmit = (event) => {
    event.preventDefault();
    if (symbolInput.trim()) {
      addMutation.mutate(symbolInput.trim());
    }
  };

  return (
    <div className="animate-fadeIn">
      <div className="flex items-center justify-between mb-4 gap-4 flex-wrap">
        <h2 className="text-xl font-bold">대시보드</h2>
        <form onSubmit={handleSubmit} className="flex gap-2">
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
      </div>

      {isLoading && <p className="text-gray-500 dark:text-gray-400">불러오는 중...</p>}
      {!isLoading && stocks.length === 0 && (
        <div className="card-bordered text-center py-12 text-gray-500 dark:text-gray-400">
          관심종목이 없습니다. 종목코드를 추가해보세요.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
        {stocks.map((stock) => (
          <StockCard
            key={stock.symbol}
            stock={stock}
            quote={quotes[stock.symbol]}
            onDelete={removeMutation.mutate}
          />
        ))}
      </div>
    </div>
  );
}
