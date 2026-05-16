import { useEffect, useMemo, useRef, useState } from "react";

import { useAuthStore } from "@/store/authStore";
import type { CodeEvent } from "@/types/code";

function toWsBaseUrl(httpBaseUrl: string): string {
  if (httpBaseUrl.startsWith("https://")) {
    return httpBaseUrl.replace("https://", "wss://");
  }
  return httpBaseUrl.replace("http://", "ws://");
}

export function useCodeSessionStream(sessionId: number | null, afterSeq?: number) {
  const token = useAuthStore((state) => state.accessToken);
  const [events, setEvents] = useState<CodeEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [replayedCount, setReplayedCount] = useState(0);
  const [liveCount, setLiveCount] = useState(0);
  const initialAfterSeqRef = useRef<number | undefined>(afterSeq);

  const socketUrl = useMemo(() => {
    if (!token || !sessionId) return null;
    const configuredWsBase = import.meta.env.VITE_WS_BASE_URL;
    if (configuredWsBase) {
      return `${configuredWsBase}?token=${encodeURIComponent(token)}`;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
    return `${toWsBaseUrl(apiBaseUrl)}/ws?token=${encodeURIComponent(token)}`;
  }, [sessionId, token]);

  useEffect(() => {
    initialAfterSeqRef.current = afterSeq;
  }, [afterSeq, sessionId]);

  useEffect(() => {
    if (!socketUrl || !sessionId) return;

    setEvents([]);
    setConnected(false);
    setReplayedCount(0);
    setLiveCount(0);

    const ws = new WebSocket(socketUrl);
    ws.addEventListener("open", () => {
      setConnected(true);
      ws.send(
        JSON.stringify({
          type: "subscribe",
          channel: `code:session:${sessionId}`,
          after_seq: initialAfterSeqRef.current,
        }),
      );
    });
    ws.addEventListener("close", () => setConnected(false));
    ws.addEventListener("message", (event) => {
      const parsed = JSON.parse(event.data) as { type?: string; channel?: string; event?: CodeEvent };
      if (
        (parsed.type === "code.session.replayed" || parsed.type === "code.session.event") &&
        parsed.channel === `code:session:${sessionId}` &&
        parsed.event
      ) {
        const incomingEvent = parsed.event;
        if (parsed.type === "code.session.replayed") {
          setReplayedCount((current) => current + 1);
        } else {
          setLiveCount((current) => current + 1);
        }
        setEvents((current) => {
          if (current.some((item) => item.id === incomingEvent.id)) return current;
          return [...current, incomingEvent].sort((a, b) => a.seq_no - b.seq_no);
        });
      }
    });

    return () => {
      ws.close();
    };
  }, [sessionId, socketUrl]);

  return { events, connected, replayedCount, liveCount };
}
