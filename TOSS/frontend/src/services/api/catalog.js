import { api } from "./client";

export const getCatalog = ({ market, securityType, q, page, pageSize } = {}) =>
  api
    .get("/api/catalog", { params: { market, security_type: securityType, q, page, page_size: pageSize } })
    .then((r) => r.data);

export const syncCatalog = () => api.post("/api/catalog/sync").then((r) => r.data);
