import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { API, wsUrl } from "@/lib/api";

// Live state channel with auto-reconnect, heartbeat and HTTP fallback polling.
export function useLiveChannel(channel) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("connecting");
  const statusRef = useRef("connecting");

  useEffect(() => {
    let ws;
    let retry;
    let closed = false;
    let attempt = 0;
    let lastSeen = Date.now();
    const mark = (s) => { statusRef.current = s; setStatus(s); };

    const connect = () => {
      clearTimeout(retry);
      mark(attempt ? "reconnecting" : "connecting");
      ws = new WebSocket(wsUrl(channel));
      ws.onopen = () => { attempt = 0; lastSeen = Date.now(); mark("live"); };
      ws.onmessage = (e) => {
        lastSeen = Date.now();
        const msg = JSON.parse(e.data);
        if (msg.type === "state") setData(msg.data);
      };
      ws.onerror = () => ws.close();
      ws.onclose = () => {
        if (closed) return;
        attempt += 1;
        mark(attempt > 6 ? "offline" : "reconnecting");
        retry = setTimeout(connect, Math.min(1000 * 2 ** (attempt - 1), 8000));
      };
    };

    const heartbeat = setInterval(() => {
      if (ws?.readyState !== WebSocket.OPEN) return;
      ws.send("ping");
      if (Date.now() - lastSeen > 30000) ws.close();
    }, 10000);

    const poll = setInterval(async () => {
      if (statusRef.current === "live") return;
      try {
        const { data: d } = await axios.get(`${API}/${channel}/display`);
        setData(d);
      } catch { /* backend still down */ }
    }, 5000);

    const reconnectNow = () => {
      if (ws?.readyState !== WebSocket.OPEN) { attempt = Math.max(attempt, 1); ws?.close(); connect(); }
    };
    window.addEventListener("online", reconnectNow);
    document.addEventListener("visibilitychange", reconnectNow);

    axios.get(`${API}/${channel}/display`).then((r) => setData((d) => d ?? r.data)).catch(() => {});
    connect();

    return () => {
      closed = true;
      clearTimeout(retry);
      clearInterval(heartbeat);
      clearInterval(poll);
      window.removeEventListener("online", reconnectNow);
      document.removeEventListener("visibilitychange", reconnectNow);
      ws?.close();
    };
  }, [channel]);

  return { data, status };
}
