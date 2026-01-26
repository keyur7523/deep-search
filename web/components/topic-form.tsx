"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Sparkles } from "lucide-react"
import type { AgentMode } from "@/lib/types"

interface TopicFormProps {
  onSubmit: (data: { 
    topic: string
    maxParagraphs: number
    roundsPerParagraph: number
    searchProvider?: string
    mode?: AgentMode
    deepMode?: boolean
    minCitations?: number
  }) => void
}

export function TopicForm({ onSubmit }: TopicFormProps) {
  const [topic, setTopic] = useState("")
  const [maxParagraphs, setMaxParagraphs] = useState(5)
  const [roundsPerParagraph, setRoundsPerParagraph] = useState(3)
  const [searchProvider, setSearchProvider] = useState("hybrid")
  const [mode, setMode] = useState<AgentMode>("auto")
  const [deepMode, setDeepMode] = useState(false)
  const [minCitations, setMinCitations] = useState(10)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (topic.trim()) {
      onSubmit({ 
        topic, 
        maxParagraphs, 
        roundsPerParagraph, 
        searchProvider,
        mode,
        deepMode,
        minCitations
      })
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
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

      {/* Research Mode Selection */}
      <div className="space-y-3 p-4 border rounded-2xl">
        <Label className="text-sm font-medium">Research Mode</Label>
        <RadioGroup value={mode} onValueChange={(value) => setMode(value as AgentMode)}>
          <div className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="auto" id="auto" className="mt-0.5" />
            <div className="flex-1">
              <Label htmlFor="auto" className="font-medium cursor-pointer">
                Auto (Recommended)
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                System decides based on topic complexity
              </p>
            </div>
          </div>
          
          <div className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="simple" id="simple" className="mt-0.5" />
            <div className="flex-1">
              <Label htmlFor="simple" className="font-medium cursor-pointer">
                Simple
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Fast, linear research pipeline
              </p>
            </div>
          </div>
          
          <div className="flex items-start space-x-3 p-3 rounded-lg border hover:bg-accent/50 transition-colors">
            <RadioGroupItem value="agentic" id="agentic" className="mt-0.5" />
            <div className="flex-1">
              <Label htmlFor="agentic" className="font-medium cursor-pointer">
                Agentic (Multi-Agent)
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Deep, iterative research with quality gates
              </p>
            </div>
          </div>
        </RadioGroup>
      </div>

      <div className="grid grid-cols-2 gap-4">
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
          <Label htmlFor="minCitations" className="text-sm font-medium text-foreground">
            Min Citations
          </Label>
          <Input
            id="minCitations"
            type="number"
            min={1}
            max={50}
            value={minCitations}
            onChange={(e) => setMinCitations(Number(e.target.value))}
            className="rounded-2xl"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="searchProvider" className="text-sm font-medium text-foreground">
            Search Type
          </Label>
          <Select value={searchProvider} onValueChange={setSearchProvider}>
            <SelectTrigger className="rounded-2xl">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hybrid">Academic + Web</SelectItem>
              <SelectItem value="academic">Academic Only</SelectItem>
              <SelectItem value="web">Web Only</SelectItem>
              <SelectItem value="semantic_scholar">Semantic Scholar</SelectItem>
              <SelectItem value="arxiv">arXiv</SelectItem>
            </SelectContent>
          </Select>
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
      </div>

      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          id="deepMode"
          checked={deepMode}
          onChange={(e) => setDeepMode(e.target.checked)}
          className="rounded"
        />
        <Label htmlFor="deepMode" className="text-sm cursor-pointer">
          Deep Research Mode (more thorough, slower)
        </Label>
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