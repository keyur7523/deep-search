"use client"

import { Progress } from "@/components/ui/progress"

interface ProgressStripProps {
  overall: number
  items?: Array<{ id: string; progress: number }>
}

export function ProgressStrip({ overall, items = [] }: ProgressStripProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Overall Progress</span>
        <span className="font-semibold text-foreground">{Math.round(overall)}%</span>
      </div>
      <Progress value={overall} className="h-2" />

      {items.length > 0 && (
        <div className="flex gap-1">
          {items.map((item) => (
            <div key={item.id} className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
              <div className="h-full bg-[#6d28d9] transition-all" style={{ width: `${item.progress}%` }} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
