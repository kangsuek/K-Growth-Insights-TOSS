import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });

export const getWatchlist = () => api.get("/api/watchlist").then((r) => r.data);

export const addToWatchlist = (symbol) =>
  api.post("/api/watchlist", { symbol }).then((r) => r.data);

export const removeFromWatchlist = (symbol) =>
  api.delete(`/api/watchlist/${symbol}`).then((r) => r.data);

export const getCandles = (symbol, limit = 120) =>
  api.get(`/api/watchlist/${symbol}/candles`, { params: { limit } }).then((r) => r.data);

export const getTradingFlow = (symbol, limit = 60) =>
  api.get(`/api/watchlist/${symbol}/trading-flow`, { params: { limit } }).then((r) => r.data);
