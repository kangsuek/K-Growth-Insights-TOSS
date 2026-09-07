import { api } from "./client";

export const getRealtimeQuotes = () => api.get("/api/realtime/quotes").then((r) => r.data);

export const getRealtimeQuote = (symbol) =>
  api.get(`/api/realtime/quotes/${symbol}`).then((r) => r.data);

export const getRealtimeTrades = (symbol, limit = 200) =>
  api.get(`/api/realtime/trades/${symbol}`, { params: { limit } }).then((r) => r.data);
