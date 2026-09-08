import { api } from "./client";

export const getCandles = (symbol, limit = 120) =>
  api.get(`/api/candles/${symbol}`, { params: { limit } }).then((r) => r.data);

export const syncCandles = (symbol, count = 120) =>
  api.post(`/api/candles/${symbol}/sync`, null, { params: { count } }).then((r) => r.data);
