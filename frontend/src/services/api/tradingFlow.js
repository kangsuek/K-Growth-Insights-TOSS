import { api } from "./client";

export const getTradingFlow = (symbol, limit = 60) =>
  api.get(`/api/trading-flow/${symbol}`, { params: { limit } }).then((r) => r.data);

export const syncTradingFlow = (symbol, count = 60) =>
  api.post(`/api/trading-flow/${symbol}/sync`, null, { params: { count } }).then((r) => r.data);
