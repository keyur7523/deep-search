"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Brain, Search, CheckCircle, FileText, AlertCircle } from "lucide-react";
import { SkeletonAgentEvent } from "@/components/ui/skeletons";
import { useResearchStore } from "@/stores";
import { useAgentEventStream } from "@/hooks/useAgentEventStream";

interface AgentEventViewerProps {
  runId: string;
}

const AGENT_ICONS = {
  Strategy: Brain,
  Search: Search,
  Quality: CheckCircle,
  Synthesis: FileText,
} as const;

const KIND_COLORS = {
  search: "bg-blue-500/10 text-blue-700 border-blue-200",
  extract: "bg-emerald-500/10 text-emerald-700 border-emerald-200",
  analyze: "bg-purple-500/10 text-purple-700 border-purple-200",
  write: "bg-amber-500/10 text-amber-700 border-amber-200",
  info: "bg-slate-500/10 text-slate-700 border-slate-200",
  error: "bg-red-500/10 text-red-700 border-red-200",
} as const;

export function AgentEventViewer({ runId }: AgentEventViewerProps) {
  const events = useResearchStore((state) => state.agentEvents);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useAgentEventStream(runId);

  useEffect(() => {
    setIsConnected(true);

    const interval = window.setInterval(() => {
      if (events.length > 0) {
        setIsLoading(false);
        setIsDone(true);
        setIsConnected(false);
      }
    }, 500);

    return () => {
      window.clearInterval(interval);
      setIsConnected(false);
    };
  }, [runId, events.length]);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Agent Activity</CardTitle>
          <div className="flex items-center gap-2">
            {isConnected && !isDone && (
              <Badge variant="outline" className="gap-1">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                Live
              </Badge>
            )}
            {isDone && (
              <Badge variant="outline" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                Complete
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[400px] pr-4">
          <div role="status" aria-live="polite" className="sr-only">
            {events.length === 0 ? "No agent activity yet." : `Received ${events.length} agent events.`}
          </div>
          {isLoading ? (
            <div className="space-y-3">
              <SkeletonAgentEvent />
              <SkeletonAgentEvent />
              <SkeletonAgentEvent />
            </div>
          ) : events.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <p>Waiting for agent activity...</p>
            </div>
          ) : (
            <div className="space-y-3">
              {events.map((event, idx) => {
                const Icon = AGENT_ICONS[event.agent as keyof typeof AGENT_ICONS] || AlertCircle;
                const colorClass = KIND_COLORS[event.type as keyof typeof KIND_COLORS] || KIND_COLORS.info;

                return (
                  <div
                    key={idx}
                    className={`flex gap-3 p-3 rounded-lg border ${colorClass}`}
                  >
                    <Icon className="h-5 w-5 shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm">
                          {event.agent}
                        </span>
                        <Badge variant="secondary" className="text-xs">
                          {event.type}
                        </Badge>
                      </div>
                      <p className="text-sm break-words">{event.message}</p>
                      {event.data && Object.keys(event.data).length > 0 && (
                        <div className="mt-2 text-xs text-muted-foreground">
                          {Object.entries(event.data).map(([key, value]) => (
                            <span key={key} className="mr-3">
                              {key}: {String(value)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
