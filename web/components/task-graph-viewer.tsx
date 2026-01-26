"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getTaskGraph } from "@/lib/api";
import type { AgentGraph, AgentGraphNode } from "@/lib/types";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface TaskGraphViewerProps {
  runId: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const STATUS_COLORS = {
  pending: "bg-gray-500",
  running: "bg-blue-500",
  done: "bg-green-500",
  failed: "bg-red-500",
} as const;

const TASK_TYPE_COLORS = {
  STRATEGY: "bg-purple-100 border-purple-300 text-purple-800",
  SEARCH: "bg-blue-100 border-blue-300 text-blue-800",
  QUALITY_CHECK: "bg-green-100 border-green-300 text-green-800",
  SYNTHESIS: "bg-orange-100 border-orange-300 text-orange-800",
} as const;

export function TaskGraphViewer({
  runId,
  autoRefresh = true,
  refreshInterval = 2000,
}: TaskGraphViewerProps) {
  const [graph, setGraph] = useState<AgentGraph | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchGraph = async () => {
    try {
      const data = await getTaskGraph(runId);
      setGraph(data);
    } catch (error) {
      console.error("Failed to fetch task graph:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();

    if (autoRefresh) {
      const interval = setInterval(fetchGraph, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [runId, autoRefresh, refreshInterval]);

  const getNodesByType = (type: string) => {
    return graph?.nodes.filter((n) => n.type === type) || [];
  };

  const getStatusCounts = () => {
    const counts = { pending: 0, running: 0, done: 0, failed: 0 };
    graph?.nodes.forEach((node) => {
      counts[node.status as keyof typeof counts]++;
    });
    return counts;
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-8 w-20" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Status badges skeleton */}
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-5 w-20 rounded-full" />
              ))}
            </div>
            {/* Task groups skeleton */}
            {[1, 2].map((group) => (
              <div key={group} className="space-y-2">
                <Skeleton className="h-4 w-20" />
                <div className="grid grid-cols-3 gap-2">
                  {[1, 2, 3].map((task) => (
                    <Skeleton key={task} className="h-10 rounded" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  const statusCounts = getStatusCounts();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Task Graph</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchGraph}
            className="gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {!graph || graph.nodes.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            No tasks yet
          </div>
        ) : (
          <div className="space-y-4">
            {/* Status Summary */}
            <div className="flex gap-2 flex-wrap">
              {Object.entries(statusCounts).map(([status, count]) => (
                <Badge
                  key={status}
                  variant="secondary"
                  className="gap-1"
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      STATUS_COLORS[status as keyof typeof STATUS_COLORS]
                    }`}
                  />
                  {status}: {count}
                </Badge>
              ))}
              <Badge variant="outline">Total: {graph.nodes.length}</Badge>
            </div>

            {/* Tasks by Type */}
            <div className="space-y-3">
              {["STRATEGY", "SEARCH", "QUALITY_CHECK", "SYNTHESIS"].map(
                (type) => {
                  const nodes = getNodesByType(type);
                  if (nodes.length === 0) return null;

                  return (
                    <div key={type}>
                      <h4 className="text-sm font-medium mb-2">{type}</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {nodes.map((node) => (
                          <div
                            key={node.id}
                            className={`p-2 rounded border text-xs ${
                              TASK_TYPE_COLORS[
                                type as keyof typeof TASK_TYPE_COLORS
                              ]
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium truncate">
                                Task {node.id.slice(-4)}
                              </span>
                              <span
                                className={`h-2 w-2 rounded-full ${
                                  STATUS_COLORS[
                                    node.status as keyof typeof STATUS_COLORS
                                  ]
                                }`}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}