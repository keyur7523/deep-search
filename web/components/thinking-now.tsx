"use client";
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { openLiveStream, type LiveMsg } from "@/lib/live";

export default function ThinkingNow({ apiBase, runId }:{ apiBase:string; runId:string | null }) {
  const [m, setM] = useState<LiveMsg | null>(null);
  const hideTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!runId) { setM(null); return; }
    const close = openLiveStream(apiBase, runId, (msg) => {
      setM(msg);
      if (hideTimer.current) window.clearTimeout(hideTimer.current);
      // Auto-hide after 1.6s unless updated by next message
      hideTimer.current = window.setTimeout(() => setM(null), 1600);
    });
    return () => { if (hideTimer.current) window.clearTimeout(hideTimer.current); close(); };
  }, [apiBase, runId]);

  if (!m) return null;

  return (
    <div
      className="fixed top-4 right-4 z-[9999] flex items-center rounded-2xl border border-border bg-white/90 backdrop-blur px-3 py-2 shadow-sm text-sm"
      role="status"
      aria-live="polite"
    >
      {m.kind !== "done" ? (
        <Skeleton className="mr-2 h-4 w-4 rounded-full" aria-hidden="true" />
      ) : null}
      <span className="mr-2 uppercase tracking-wide text-xs text-primary">{m.kind}</span>
      <span className="text-foreground">{m.msg}</span>
      <span className="sr-only">Live research update</span>
    </div>
  );
}
