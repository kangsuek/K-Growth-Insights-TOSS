import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });

function toRealtimeWsUrl(base) {
  // base가 "/api"처럼 스킴 없는 상대 경로여도 현재 페이지 origin 기준으로 절대 URL을 만든다.
  const absolute = new URL(base, window.location.href);
  absolute.protocol = absolute.protocol === "https:" ? "wss:" : "ws:";
  absolute.pathname = `${absolute.pathname.replace(/\/$/, "")}/ws/realtime`;
  return absolute.toString();
}

export const realtimeWsUrl = toRealtimeWsUrl(baseURL);

export const getWatchlist = () => api.get("/api/watchlist").then((r) => r.data);

export const addToWatchlist = (symbol) =>
  api.post("/api/watchlist", { symbol }).then((r) => r.data);

export const removeFromWatchlist = (symbol) =>
  api.delete(`/api/watchlist/${symbol}`).then((r) => r.data);

export const getCandles = (symbol, limit = 120) =>
  api.get(`/api/watchlist/${symbol}/candles`, { params: { limit } }).then((r) => r.data);

export const getTradingFlow = (symbol, limit = 60) =>
  api.get(`/api/watchlist/${symbol}/trading-flow`, { params: { limit } }).then((r) => r.data);
