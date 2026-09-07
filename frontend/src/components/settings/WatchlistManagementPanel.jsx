import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  addToWatchlist,
  getCatalog,
  getWatchlist,
  removeFromWatchlist,
  reorderWatchlist,
} from "../../services/api";
import { useToast } from "../../contexts/ToastContext";

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function WatchlistManagementPanel() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query, 300);
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: stocks = [] } = useQuery({ queryKey: ["watchlist"], queryFn: getWatchlist });

  const { data: searchResults = [] } = useQuery({
    queryKey: ["catalog-search", debouncedQuery],
    queryFn: () => getCatalog({ q: debouncedQuery, pageSize: 10 }).then((r) => r.items),
    enabled: debouncedQuery.trim().length >= 2,
  });

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (stock) => {
      setQuery("");
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      queryClient.invalidateQueries({ queryKey: ["data-stats"] });
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
      queryClient.invalidateQueries({ queryKey: ["data-stats"] });
    },
  });

  const reorderMutation = useMutation({
    mutationFn: reorderWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const moveStock = (index, direction) => {
    const target = index + direction;
    if (target < 0 || target >= stocks.length) return;
    const nextOrder = stocks.map((s) => s.symbol);
    [nextOrder[index], nextOrder[target]] = [nextOrder[target], nextOrder[index]];
    reorderMutation.mutate(nextOrder);
  };

  return (
    <div className="card-bordered">
      <h3 className="font-semibold mb-3">관심종목 관리</h3>

      <div className="relative mb-4">
        <input
          className="input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="종목코드 또는 종목명 검색 (2자 이상)"
        />
        {searchResults.length > 0 && (
          <ul className="absolute z-10 mt-1 w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg max-h-64 overflow-auto">
            {searchResults.map((item) => (
              <li
                key={item.symbol}
                className="px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50"
                onClick={() => addMutation.mutate(item.symbol)}
              >
                <span className="font-medium">{item.name}</span>
                <span className="text-gray-500 dark:text-gray-400"> ({item.symbol}) · {item.market}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ul className="divide-y divide-gray-100 dark:divide-gray-700">
        {stocks.map((stock, index) => (
          <li key={stock.symbol} className="flex items-center justify-between gap-2 py-2 text-sm">
            <span>
              <span className="font-medium">{stock.name}</span>
              <span className="text-gray-500 dark:text-gray-400"> ({stock.symbol}) · {stock.market}</span>
            </span>
            <span className="flex items-center gap-1 shrink-0">
              <button
                className="btn px-2 py-1 text-xs"
                disabled={index === 0}
                onClick={() => moveStock(index, -1)}
              >
                ↑
              </button>
              <button
                className="btn px-2 py-1 text-xs"
                disabled={index === stocks.length - 1}
                onClick={() => moveStock(index, 1)}
              >
                ↓
              </button>
              <button
                className="btn-danger px-2 py-1 text-xs"
                onClick={() => removeMutation.mutate(stock.symbol)}
              >
                삭제
              </button>
            </span>
          </li>
        ))}
        {stocks.length === 0 && (
          <li className="py-4 text-sm text-gray-500 dark:text-gray-400">관심종목이 없습니다.</li>
        )}
      </ul>
    </div>
  );
}
