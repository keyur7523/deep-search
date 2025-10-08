"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { subscribeToAgentEvents } from "@/lib/api";
import type { AgentEvent } from "@/lib/types";
import { Brain, Search, CheckCircle, FileText, AlertCircle } from "lucide-react";

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
  thinking: "bg-blue-500/10 text-blue-700 border-blue-200",
  action: "bg-green-500/10 text-green-700 border-green-200",
  result: "bg-purple-500/10 text-purple-700 border-purple-200",
  error: "bg-red-500/10 text-red-700 border-red-200",
} as const;

export function AgentEventViewer({ runId }: AgentEventViewerProps) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    setIsConnected(true);

    const unsubscribe = subscribeToAgentEvents(
      runId,
      (event) => {
        setEvents((prev) => [...prev, event]);
      },
      () => {
        setIsDone(true);
        setIsConnected(false);
      },
      (error) => {
        console.error("Event stream error:", error);
        setIsConnected(false);
      }
    );

    return () => {
      unsubscribe();
      setIsConnected(false);
    };
  }, [runId]);

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
          {events.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <p>Waiting for agent activity...</p>
            </div>
          ) : (
            <div className="space-y-3">
              {events.map((event, idx) => {
                const Icon = AGENT_ICONS[event.agent as keyof typeof AGENT_ICONS] || AlertCircle;
                const colorClass = KIND_COLORS[event.kind] || KIND_COLORS.thinking;

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
                          {event.kind}
                        </Badge>
                      </div>
                      <p className="text-sm break-words">{event.text}</p>
                      {event.meta && Object.keys(event.meta).length > 0 && (
                        <div className="mt-2 text-xs text-muted-foreground">
                          {Object.entries(event.meta).map(([key, value]) => (
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