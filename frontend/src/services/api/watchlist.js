import { api } from "./client";

export const getWatchlist = () => api.get("/api/watchlist").then((r) => r.data);

export const addToWatchlist = (symbol) =>
  api.post("/api/watchlist", { symbol }).then((r) => r.data);

export const removeFromWatchlist = (symbol) =>
  api.delete(`/api/watchlist/${symbol}`).then((r) => r.data);

export const reorderWatchlist = (symbols) =>
  api.post("/api/watchlist/reorder", symbols).then((r) => r.data);
