import { useEffect, useRef, useState } from "react";
import { realtimeWsUrl } from "../services/api";

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

/**
 * 백엔드 /ws/realtime에 연결해 symbol별 최신 체결가를 반환한다.
 * 연결이 끊기면 지수 백오프로 재연결한다.
 */
export function useRealtimeTrades() {
  const [trades, setTrades] = useState({});
  const backoffRef = useRef(INITIAL_BACKOFF_MS);

  useEffect(() => {
    let socket;
    let reconnectTimer;
    let cancelled = false;

    const connect = () => {
      socket = new WebSocket(realtimeWsUrl);

      socket.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS;
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "snapshot") {
            setTrades((prev) => {
              const next = { ...prev };
              for (const trade of payload.data) next[trade.symbol] = trade;
              return next;
            });
          } else if (payload.type === "trade") {
            setTrades((prev) => ({ ...prev, [payload.data.symbol]: payload.data }));
          }
        } catch {
          // 파싱 실패 프레임은 무시한다.
        }
      };

      socket.onclose = () => {
        if (cancelled) return;
        reconnectTimer = setTimeout(connect, backoffRef.current);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return trades;
}
