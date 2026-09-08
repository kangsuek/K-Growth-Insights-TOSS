import axios from "axios";

// K-Growth-Insights(V2)의 백엔드(:8000)와 겹치지 않게 분리.
const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8100";

export const api = axios.create({ baseURL });

function toRealtimeWsUrl(base) {
  // base가 "/api"처럼 스킴 없는 상대 경로여도 현재 페이지 origin 기준으로 절대 URL을 만든다.
  const absolute = new URL(base, window.location.href);
  absolute.protocol = absolute.protocol === "https:" ? "wss:" : "ws:";
  absolute.pathname = `${absolute.pathname.replace(/\/$/, "")}/ws/realtime`;
  return absolute.toString();
}

export const realtimeWsUrl = toRealtimeWsUrl(baseURL);
