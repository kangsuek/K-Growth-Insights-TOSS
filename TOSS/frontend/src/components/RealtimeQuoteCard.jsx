import { formatPercent, formatPrice, getPriceChangeColor } from "../utils/format";

export default function RealtimeQuoteCard({ quote }) {
  if (!quote || quote.last == null) {
    return (
      <div className="card-bordered text-center py-8 text-gray-500 dark:text-gray-400">
        아직 실시간 시세가 없습니다. 장중에는 체결 발생 즉시 표시됩니다.
      </div>
    );
  }

  const change = quote.prev_close != null ? quote.last - quote.prev_close : null;
  const changePercent = change !== null && quote.prev_close ? (change / quote.prev_close) * 100 : null;

  return (
    <div className="card-bordered">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-success-500" />
        </span>
        <span className="text-sm text-gray-500 dark:text-gray-400">실시간 현재가(미확정)</span>
      </div>

      <div className={`mb-3 ${getPriceChangeColor(change)}`}>
        <span className="text-3xl font-bold">{formatPrice(quote.last)}원</span>
        {changePercent !== null && <span className="ml-2 text-lg">{formatPercent(changePercent)}</span>}
      </div>

      <dl className="grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-gray-500 dark:text-gray-400">시가</dt>
          <dd className="font-medium">{quote.open != null ? `${formatPrice(quote.open)}원` : "-"}</dd>
        </div>
        <div>
          <dt className="text-gray-500 dark:text-gray-400">고가</dt>
          <dd className="font-medium">{quote.high != null ? `${formatPrice(quote.high)}원` : "-"}</dd>
        </div>
        <div>
          <dt className="text-gray-500 dark:text-gray-400">저가</dt>
          <dd className="font-medium">{quote.low != null ? `${formatPrice(quote.low)}원` : "-"}</dd>
        </div>
      </dl>
    </div>
  );
}
