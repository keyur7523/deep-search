"use client"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Copy } from "lucide-react"
import { formatDate } from "@/lib/utils"

export interface Note {
  id: string
  timestamp: Date
  content: string
  type: "reflection" | "search" | "system"
}

interface NotesLogProps {
  notes: Note[]
}

export function NotesLog({ notes }: NotesLogProps) {
  const handleCopy = (content: string) => {
    navigator.clipboard.writeText(content)
    console.log("[v0] Copied note to clipboard")
  }

  return (
    <ScrollArea className="h-[calc(100vh-12rem)]">
      <div className="space-y-4">
        {notes.map((note) => (
          <div key={note.id} className="p-4 rounded-2xl border border-border bg-card space-y-2">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium capitalize">{note.type}</span>
                <span>•</span>
                <span>{formatDate(note.timestamp)}</span>
              </div>
              <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleCopy(note.content)}>
                <Copy className="w-3.5 h-3.5" />
              </Button>
            </div>
            <pre className="text-sm font-mono text-foreground whitespace-pre-wrap leading-relaxed">{note.content}</pre>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}
