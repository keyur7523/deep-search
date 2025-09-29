"use client"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { getStatusColor } from "@/lib/utils"
import { Progress } from "@/components/ui/progress"

export interface OutlineItemData {
  id: string
  index: number
  title: string
  brief: string
  status: "queued" | "searching" | "reflecting" | "drafting" | "done" | "needs review"
  progress?: number
}

interface OutlineItemProps {
  item: OutlineItemData
  onClick?: () => void
}

export function OutlineItem({ item, onClick }: OutlineItemProps) {
  return (
    <Card
      className="p-4 rounded-2xl border border-border bg-card hover:bg-accent/50 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-muted-foreground">#{item.index}</span>
              <h4 className="text-sm font-semibold text-foreground truncate">{item.title}</h4>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-2">{item.brief}</p>
          </div>
          <Badge className={`shrink-0 text-xs ${getStatusColor(item.status)}`}>{item.status}</Badge>
        </div>

        {item.progress !== undefined && item.progress > 0 && <Progress value={item.progress} className="h-1.5" />}
      </div>
    </Card>
  )
}
