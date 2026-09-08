import { useCallback, useEffect, useRef, useState } from "react";
import type { Snapshot } from "../shared/protocol";

export async function api<T>(
  url: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${url}`, {
    method,
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "操作失败，请重试");
  return result;
}

export function useProject() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    try {
      const data = await api<Snapshot>("/project");
      if (sequence.current === request) {
        setSnapshot(data);
        setError("");
      }
    } catch (error) {
      if (sequence.current === request) setError((error as Error).message);
    }
  }, []);
  useEffect(() => {
    void refresh();
    const stream = new EventSource("/api/events");
    stream.addEventListener("ready", () => {
      setConnected(true);
      void refresh();
    });
    stream.addEventListener("change", () => {
      void refresh();
    });
    stream.onerror = () => setConnected(false);
    return () => {
      stream.close();
      sequence.current++;
    };
  }, [refresh]);
  return { snapshot, error, connected, refresh };
}
