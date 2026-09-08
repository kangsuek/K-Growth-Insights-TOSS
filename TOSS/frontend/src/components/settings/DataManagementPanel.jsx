import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getDataStats, resetData, syncCatalog } from "../../services/api";
import { useToast } from "../../contexts/ToastContext";
import { formatNumber } from "../../utils/format";

export default function DataManagementPanel() {
  const [confirmingReset, setConfirmingReset] = useState(false);
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: stats } = useQuery({ queryKey: ["data-stats"], queryFn: getDataStats });

  const syncCatalogMutation = useMutation({
    mutationFn: syncCatalog,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["data-stats"] });
      toast.success(`카탈로그 동기화 완료: 총 ${formatNumber(result.total_collected)}건`);
    },
    onError: () => toast.error("카탈로그 동기화에 실패했습니다."),
  });

  const resetMutation = useMutation({
    mutationFn: resetData,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["data-stats"] });
      queryClient.invalidateQueries({ queryKey: ["candles"] });
      queryClient.invalidateQueries({ queryKey: ["trading-flow"] });
      setConfirmingReset(false);
      toast.success(
        `초기화 완료: 캔들 ${formatNumber(result.deleted_price_rows)}건, 매매동향 ${formatNumber(result.deleted_trading_flow_rows)}건 삭제`
      );
    },
    onError: () => toast.error("데이터 초기화에 실패했습니다."),
  });

  return (
    <div className="card-bordered">
      <h3 className="font-semibold mb-3">데이터 관리</h3>

      {stats && (
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-sm">
          <div>
            <dt className="text-gray-500 dark:text-gray-400">관심종목</dt>
            <dd className="text-lg font-semibold">{formatNumber(stats.watchlist_count)}</dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">카탈로그 종목</dt>
            <dd className="text-lg font-semibold">{formatNumber(stats.catalog_count)}</dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">캔들 데이터</dt>
            <dd className="text-lg font-semibold">{formatNumber(stats.price_rows)}</dd>
          </div>
          <div>
            <dt className="text-gray-500 dark:text-gray-400">매매동향 데이터</dt>
            <dd className="text-lg font-semibold">{formatNumber(stats.trading_flow_rows)}</dd>
          </div>
        </dl>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        <button
          className="btn px-3 py-1.5 text-sm"
          onClick={() => syncCatalogMutation.mutate()}
          disabled={syncCatalogMutation.isPending}
        >
          {syncCatalogMutation.isPending ? "동기화 중..." : "카탈로그 재동기화"}
        </button>
      </div>

      <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <h4 className="text-sm font-semibold text-danger-600 dark:text-danger-400 mb-2">위험 작업</h4>
        {confirmingReset ? (
          <div className="flex items-center gap-2">
            <span className="text-sm text-danger-600 dark:text-danger-400">
              캔들·매매동향 수집 데이터를 전부 삭제합니다(관심종목·카탈로그는 유지). 계속할까요?
            </span>
            <button
              className="btn-danger px-2 py-1 text-xs shrink-0"
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
            >
              확인
            </button>
            <button className="btn px-2 py-1 text-xs shrink-0" onClick={() => setConfirmingReset(false)}>
              취소
            </button>
          </div>
        ) : (
          <button className="btn-danger px-3 py-1.5 text-sm" onClick={() => setConfirmingReset(true)}>
            수집 데이터 초기화
          </button>
        )}
      </div>
    </div>
  );
}
