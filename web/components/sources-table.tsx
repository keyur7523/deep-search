"use client"

import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { ExternalLink, ChevronDown } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useResearchStore } from "@/stores"

export interface Source {
  id: string
  title: string
  domain: string
  score: number
  round: number
  url: string
  snapshot: string
}

interface SourcesTableProps {
  sources?: Source[]
}

export function SourcesTable({ sources }: SourcesTableProps) {
  const storeSources = useResearchStore((state) => state.sources)
  const list = useMemo<Source[]>(() => {
    if (sources) return sources
    return storeSources.map((s, index) => ({
      id: s.id || `source-${index}`,
      title: s.title || "Untitled Source",
      domain: s.url ? new URL(s.url).hostname.replace("www.", "") : "unknown",
      score: s.score ?? 0,
      round: (s.sectionIdx ?? 1),
      url: s.url,
      snapshot: s.venue || s.authors || s.sectionTitle || "",
    }))
  }, [sources, storeSources])
  const [selectedRound, setSelectedRound] = useState<string>("all")
  const [selectedDomain, setSelectedDomain] = useState<string>("all")
  const [sortBy, setSortBy] = useState<"score" | "round">("score")

  const filteredSources = list
    .filter((s) => selectedRound === "all" || s.round === Number(selectedRound))
    .filter((s) => selectedDomain === "all" || s.domain === selectedDomain)
    .sort((a, b) => (sortBy === "score" ? b.score - a.score : a.round - b.round))

  const uniqueDomains = Array.from(new Set(list.map((s) => s.domain)))
  const uniqueRounds = Array.from(new Set(list.map((s) => s.round))).sort()

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Select value={selectedRound} onValueChange={setSelectedRound}>
          <SelectTrigger className="w-32 rounded-2xl">
            <SelectValue placeholder="Round" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Rounds</SelectItem>
            {uniqueRounds.map((round) => (
              <SelectItem key={round} value={String(round)}>
                Round {round}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={selectedDomain} onValueChange={setSelectedDomain}>
          <SelectTrigger className="w-40 rounded-2xl">
            <SelectValue placeholder="Domain" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Domains</SelectItem>
            {uniqueDomains.map((domain) => (
              <SelectItem key={domain} value={domain}>
                {domain}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          className="rounded-2xl bg-transparent"
          onClick={() => setSortBy(sortBy === "score" ? "round" : "score")}
        >
          Sort by {sortBy === "score" ? "Score" : "Round"}
          <ChevronDown className="w-4 h-4 ml-1" />
        </Button>
      </div>

      {/* Table */}
      <ScrollArea className="h-[calc(100vh-16rem)]">
        <div className="space-y-2">
          {filteredSources.map((source) => (
            <Sheet key={source.id}>
              <div className="flex items-center gap-4 p-4 rounded-2xl border border-border bg-card hover:bg-accent/50 transition-colors">
                <div className="flex-1 min-w-0 space-y-1">
                  <h4 className="text-sm font-medium text-foreground truncate">{source.title}</h4>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="secondary" className="text-xs">
                      {source.domain}
                    </Badge>
                    <span className="text-xs text-muted-foreground">Round {source.round}</span>
                    <span className="text-xs font-medium text-[#6d28d9]">Score: {source.score.toFixed(2)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <SheetTrigger asChild>
                    <Button size="sm" variant="outline" className="rounded-2xl bg-transparent">
                      Preview
                    </Button>
                  </SheetTrigger>
                  <Button size="sm" variant="ghost" asChild>
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </Button>
                </div>
              </div>

              <SheetContent side="right" className="w-full sm:max-w-2xl">
                <SheetHeader>
                  <SheetTitle className="text-balance">{source.title}</SheetTitle>
                  <SheetDescription className="flex items-center gap-2 flex-wrap">
                    <Badge variant="secondary">{source.domain}</Badge>
                    <span>Round {source.round}</span>
                    <span>Score: {source.score.toFixed(2)}</span>
                  </SheetDescription>
                </SheetHeader>
                <ScrollArea className="h-[calc(100vh-12rem)] mt-6">
                  <div className="prose prose-sm max-w-none">
                    <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                      {source.snapshot}
                    </p>
                  </div>
                </ScrollArea>
                <div className="mt-4">
                  <Button asChild className="w-full rounded-2xl">
                    <a href={source.url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="w-4 h-4 mr-2" />
                      Open Source
                    </a>
                  </Button>
                </div>
              </SheetContent>
            </Sheet>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
