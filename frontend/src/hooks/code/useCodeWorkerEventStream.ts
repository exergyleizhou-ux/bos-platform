import { useEffect, useMemo, useRef, useState } from "react";

import { useAuthStore } from "@/store/authStore";
import type { CodeWorkerEvent } from "@/types/code";

function toWsBaseUrl(httpBaseUrl: string): string {
  if (httpBaseUrl.startsWith("https://")) {
    return httpBaseUrl.replace("https://", "wss://");
  }
  return httpBaseUrl.replace("http://", "ws://");
}

export function useCodeWorkerEventStream(workspaceId: number | null, afterId?: number) {
  const token = useAuthStore((state) => state.accessToken);
  const [events, setEvents] = useState<CodeWorkerEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [replayedCount, setReplayedCount] = useState(0);
  const [liveCount, setLiveCount] = useState(0);
  const initialAfterIdRef = useRef<number | undefined>(afterId);

  const socketUrl = useMemo(() => {
    if (!token || !workspaceId) return null;
    const configuredWsBase = import.meta.env.VITE_WS_BASE_URL;
    if (configuredWsBase) {
      return `${configuredWsBase}?token=${encodeURIComponent(token)}`;
    }

    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
    return `${toWsBaseUrl(apiBaseUrl)}/ws?token=${encodeURIComponent(token)}`;
  }, [token, workspaceId]);

  useEffect(() => {
    initialAfterIdRef.current = afterId;
  }, [afterId, workspaceId]);

  useEffect(() => {
    if (!socketUrl || !workspaceId) return;

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
          channel: `code:workspace:${workspaceId}:workers`,
          after_id: initialAfterIdRef.current,
        }),
      );
    });
    ws.addEventListener("close", () => setConnected(false));
    ws.addEventListener("message", (event) => {
      const parsed = JSON.parse(event.data) as { type?: string; channel?: string; event?: CodeWorkerEvent };
      if (
        (parsed.type === "code.worker.replayed" || parsed.type === "code.worker.event") &&
        parsed.channel === `code:workspace:${workspaceId}:workers` &&
        parsed.event
      ) {
        const incomingEvent = parsed.event;
        if (parsed.type === "code.worker.replayed") {
          setReplayedCount((current) => current + 1);
        } else {
          setLiveCount((current) => current + 1);
        }
        setEvents((current) => {
          if (current.some((item) => item.id === incomingEvent.id)) return current;
          return [...current, incomingEvent].sort((a, b) => a.id - b.id);
        });
      }
    });

    return () => {
      ws.close();
    };
  }, [socketUrl, workspaceId]);

  return { events, connected, replayedCount, liveCount };
}
