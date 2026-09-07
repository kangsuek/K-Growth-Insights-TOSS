import { api } from "./client";

export const getDataStats = () => api.get("/api/data/stats").then((r) => r.data);

export const resetData = () => api.delete("/api/data/reset").then((r) => r.data);
