"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sparkles } from "lucide-react"

interface TopicFormProps {
  onSubmit: (data: { topic: string; maxParagraphs: number; roundsPerParagraph: number; searchProvider?: string }) => void
}

export function TopicForm({ onSubmit }: TopicFormProps) {
  const [topic, setTopic] = useState("")
  const [maxParagraphs, setMaxParagraphs] = useState(5)
  const [roundsPerParagraph, setRoundsPerParagraph] = useState(3)
  const [searchProvider, setSearchProvider] = useState("hybrid")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (topic.trim()) {
      onSubmit({ topic, maxParagraphs, roundsPerParagraph, searchProvider })
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="topic" className="text-sm font-medium text-foreground">
          Research Topic
        </Label>
        <Textarea
          id="topic"
          placeholder="Enter your research topic or question..."
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          className="min-h-24 resize-none rounded-2xl"
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label htmlFor="maxParagraphs" className="text-sm font-medium text-foreground">
            Max Paragraphs
          </Label>
          <Input
            id="maxParagraphs"
            type="number"
            min={1}
            max={20}
            value={maxParagraphs}
            onChange={(e) => setMaxParagraphs(Number(e.target.value))}
            className="rounded-2xl"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="roundsPerParagraph" className="text-sm font-medium text-foreground">
            Rounds/Para
          </Label>
          <Input
            id="roundsPerParagraph"
            type="number"
            min={1}
            max={10}
            value={roundsPerParagraph}
            onChange={(e) => setRoundsPerParagraph(Number(e.target.value))}
            className="rounded-2xl"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="searchProvider" className="text-sm font-medium text-foreground">
            Search Type
          </Label>
          <Select value={searchProvider} onValueChange={setSearchProvider}>
            <SelectTrigger className="rounded-2xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hybrid">🎓 Academic + Web</SelectItem>
              <SelectItem value="scholar">📚 Academic Only</SelectItem>
              <SelectItem value="serpapi">🌐 Web Only</SelectItem>
              <SelectItem value="brave">🔍 Brave Search</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <Button
        type="submit"
        className="w-full bg-[#6d28d9] hover:bg-[#7c3aed] text-white rounded-2xl h-11"
        disabled={!topic.trim()}
      >
        <Sparkles className="w-4 h-4 mr-2" />
        Create Research
      </Button>
    </form>
  )
}
