export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString("ko-KR");
}

export function formatPrice(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString("ko-KR", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatVolume(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

export function formatBillionWon(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value / 1e8).toFixed(1)}억`;
}

export function formatNetBuying(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  const label = value >= 0 ? "순매수" : "순매도";
  return `${label} ${formatBillionWon(Math.abs(value))}`;
}

export function getPriceChangeColor(value) {
  if (value === null || value === undefined || value === 0 || Number.isNaN(value)) {
    return "text-gray-500 dark:text-gray-400";
  }
  return value > 0 ? "text-red-600 dark:text-red-400" : "text-blue-600 dark:text-blue-400";
}

export function getPriceChangeColorHex(value) {
  if (value === null || value === undefined || value === 0 || Number.isNaN(value)) {
    return "#6b7280";
  }
  return value > 0 ? "#dc2626" : "#2563eb";
}

export function getNetBuyingColor(value) {
  return getPriceChangeColorHex(value);
}
