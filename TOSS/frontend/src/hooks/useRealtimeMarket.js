import { useEffect, useRef, useState } from "react";
import { realtimeWsUrl } from "../services/api";

const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;
const TRADE_HISTORY_MAXLEN = 200;

/**
 * 백엔드 /ws/realtime에 연결해 symbol별 체결 이력(trades)과 실시간 시세(quotes)를 반환한다.
 * 연결이 끊기면 지수 백오프로 재연결한다.
 */
export function useRealtimeMarket() {
  const [trades, setTrades] = useState({});
  const [quotes, setQuotes] = useState({});
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
            setTrades((prev) => ({ ...prev, ...payload.data.trades }));
            setQuotes((prev) => ({ ...prev, ...payload.data.quotes }));
          } else if (payload.type === "trade") {
            const trade = payload.data;
            setTrades((prev) => {
              const history = [...(prev[trade.symbol] || []), trade].slice(-TRADE_HISTORY_MAXLEN);
              return { ...prev, [trade.symbol]: history };
            });
          } else if (payload.type === "quote") {
            const quote = payload.data;
            setQuotes((prev) => ({ ...prev, [quote.symbol]: quote }));
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

  return { trades, quotes };
}
