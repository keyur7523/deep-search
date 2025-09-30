"use client";
import { useEffect, useRef, useState } from "react";
import { openRunEvents, ResearchMsg } from "@/lib/stream";

export function useRunMessages(apiBase: string, runId: string | null) {
  const [msgs, setMsgs] = useState<ResearchMsg[]>([]);
  const lastId = useRef<string | null>(null);
  const alive = useRef(true);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  useEffect(() => {
    setMsgs([]); lastId.current = null;
    if (!runId) return;

    const push = (m: ResearchMsg) => {
      lastId.current = m._id;
      setMsgs(prev => (prev.length && prev[prev.length-1]._id === m._id) ? prev : [...prev, m]);
    };

    // SSE primary
    const close = openRunEvents(apiBase, runId, push);

    // Polling safety net (in case SSE is throttled)
    const poll = async () => {
      try {
        const qs = lastId.current ? `?sinceId=${lastId.current}` : "";
        const r = await fetch(`${apiBase.replace(/\/+$/,"")}/runs/${runId}/messages${qs}`);
        if (r.ok) {
          const { items } = await r.json();
          for (const m of items) push(m);
        }
      } catch {}
    };
    const iv = window.setInterval(poll, 4000);

    return () => { close(); window.clearInterval(iv); };
  }, [apiBase, runId]);

  return msgs;
}
