"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ExternalLink, BookOpen, Globe, Calendar, Users, Award, FileText } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useResearchStore } from "@/stores"

interface Source {
  _id: string
  url: string
  title: string
  type: "academic" | "web"
  authors?: string
  year?: string
  venue?: string
  citations?: number
  score: number
  textLength: number
  sectionTitle?: string
  sectionIdx?: number
}

interface SourcesData {
  sources: Source[]
  total: number
  academic: number
  web: number
}

export function SourcesList({ runId }: { runId: string }) {
  const [data, setData] = useState<SourcesData | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<"all" | "academic" | "web">("all")
  const setSources = useResearchStore((state) => state.setSources)

  useEffect(() => {
    fetchSources()
  }, [runId])

  const fetchSources = async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/runs/${runId}/sources`)
      if (response.ok) {
        const sourcesData = await response.json()
        setData(sourcesData)
        setSources(
          sourcesData.sources.map((source: Source) => ({
            id: source._id,
            url: source.url,
            title: source.title,
            type: source.type,
            authors: source.authors,
            year: source.year,
            venue: source.venue,
            citations: source.citations,
            score: source.score,
            textLength: source.textLength,
            sectionTitle: source.sectionTitle,
            sectionIdx: source.sectionIdx,
          }))
        )
      }
    } catch (error) {
      console.error("Failed to fetch sources:", error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 min-h-[360px]">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (!data || data.sources.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-muted-foreground">
          <BookOpen className="mx-auto h-12 w-12 mb-4 opacity-50" />
          <p>No sources found for this research run.</p>
        </CardContent>
      </Card>
    )
  }

  const filteredSources = filter === "all" 
    ? data.sources 
    : data.sources.filter(s => s.type === filter)

  // Group sources by section
  const sourcesBySection = filteredSources.reduce((acc, source) => {
    const section = source.sectionTitle || "General"
    if (!acc[section]) acc[section] = []
    acc[section].push(source)
    return acc
  }, {} as Record<string, Source[]>)

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Total Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{data.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Academic Papers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-blue-600">{data.academic}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {((data.academic / data.total) * 100).toFixed(0)}% of total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Web Sources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-600">{data.web}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {((data.web / data.total) * 100).toFixed(0)}% of total
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs */}
      <Tabs value={filter} onValueChange={(v) => setFilter(v as any)} className="w-full">
        <TabsList>
          <TabsTrigger value="all">
            All ({data.total})
          </TabsTrigger>
          <TabsTrigger value="academic">
            Academic ({data.academic})
          </TabsTrigger>
          <TabsTrigger value="web">
            Web ({data.web})
          </TabsTrigger>
        </TabsList>

        <TabsContent value={filter} className="space-y-6 mt-6">
          {/* Sources grouped by section */}
          {Object.entries(sourcesBySection)
            .sort(([, a], [, b]) => {
              const aIdx = a[0]?.sectionIdx || 0
              const bIdx = b[0]?.sectionIdx || 0
              return aIdx - bIdx
            })
            .map(([sectionTitle, sources]) => (
              <div key={sectionTitle} className="space-y-3">
                <h3 className="text-lg font-semibold text-foreground/90">
                  {sources[0]?.sectionIdx ? `Section ${sources[0].sectionIdx}: ` : ""}
                  {sectionTitle}
                </h3>
                <div className="space-y-3">
                  {sources.map((source) => (
                    <SourceCard key={source._id} source={source} />
                  ))}
                </div>
              </div>
            ))}
        </TabsContent>
      </Tabs>
    </div>
  )
}

function SourceCard({ source }: { source: Source }) {
  const domain = new URL(source.url).hostname.replace("www.", "")

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-base font-semibold line-clamp-2">
              {source.title || "Untitled Source"}
            </CardTitle>
            <CardDescription className="mt-1 flex items-center gap-2 flex-wrap">
              <Badge variant={source.type === "academic" ? "default" : "secondary"} className="text-xs">
                {source.type === "academic" ? (
                  <>
                    <BookOpen className="w-3 h-3 mr-1" />
                    Academic
                  </>
                ) : (
                  <>
                    <Globe className="w-3 h-3 mr-1" />
                    Web
                  </>
                )}
              </Badge>
              <span className="text-xs text-muted-foreground">{domain}</span>
            </CardDescription>
          </div>
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
            title="Open source"
          >
            <ExternalLink className="w-5 h-5" />
          </a>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {/* Academic metadata */}
        {source.type === "academic" && (
          <div className="space-y-1 text-sm">
            {source.authors && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Users className="w-4 h-4 shrink-0" />
                <span className="line-clamp-1">{source.authors}</span>
              </div>
            )}
            {source.venue && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <FileText className="w-4 h-4 shrink-0" />
                <span className="line-clamp-1">{source.venue}</span>
              </div>
            )}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              {source.year && (
                <div className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  <span>{source.year}</span>
                </div>
              )}
              {source.citations !== undefined && source.citations > 0 && (
                <div className="flex items-center gap-1">
                  <Award className="w-3 h-3" />
                  <span>{source.citations} citations</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Quality indicators */}
        <div className="flex items-center gap-3 pt-2 text-xs text-muted-foreground border-t">
          <div className="flex items-center gap-1">
            <span className="font-medium">Quality:</span>
            <Badge variant="outline" className="text-xs">
              {(source.score * 100).toFixed(0)}%
            </Badge>
          </div>
          <div className="flex items-center gap-1">
            <span className="font-medium">Content:</span>
            <span>{(source.textLength / 1000).toFixed(1)}K chars</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
