import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getWatchlist, removeFromWatchlist } from "../services/api";
import { useRealtimeMarket } from "../hooks/useRealtimeMarket";
import StockCard from "../components/StockCard";

export default function Dashboard() {
  const queryClient = useQueryClient();
  const { quotes } = useRealtimeMarket();

  const { data: stocks = [], isLoading } = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const removeMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watchlist"] });
      queryClient.invalidateQueries({ queryKey: ["data-stats"] });
    },
  });

  return (
    <div className="animate-fadeIn">
      <h2 className="text-xl font-bold mb-4">대시보드</h2>

      {isLoading && <p className="text-gray-500 dark:text-gray-400">불러오는 중...</p>}
      {!isLoading && stocks.length === 0 && (
        <div className="card-bordered text-center py-12 text-gray-500 dark:text-gray-400">
          관심종목이 없습니다.{" "}
          <Link to="/settings" className="link">
            설정
          </Link>
          에서 종목을 추가해보세요.
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
