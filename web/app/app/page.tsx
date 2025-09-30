"use client"

import { useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/app-shell"
import { ResizablePanel } from "@/components/resizable-panel"
import { TopicForm } from "@/components/topic-form"
import { OutlineItem } from "@/components/outline-item"
import { ProgressStrip } from "@/components/progress-strip"
import { SourcesTable } from "@/components/sources-table"
import { NotesLog } from "@/components/notes-log"
import { MarkdownViewer } from "@/components/markdown-viewer"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ChevronRight, Plus } from "lucide-react"
import { startRun, getRunStatus } from "@/lib/api"
import ThinkingNow from "@/components/thinking-now"
import { API_BASE } from "@/lib/config"

export default function AppPage() {
  const [leftPanelWidth, setLeftPanelWidth] = useState(320)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)

  const {
    data: runDetails,
    isLoading,
    mutate,
  } = useSWR(currentRunId ? ["run", currentRunId] : null, () => (currentRunId ? getRunStatus(currentRunId) : null), {
    refreshInterval: (data) => {
      // Poll every 2 seconds if running, stop if completed
      return data?.status === "running" ? 2000 : 0
    },
    revalidateOnFocus: false,
  })

  const handleTopicSubmit = async (data: { topic: string; maxParagraphs: number; roundsPerParagraph: number }) => {
    console.log("Starting new research:", data)
    try {
      const run = await startRun(data)
      setCurrentRunId(run.id)
      mutate() // Trigger revalidation
    } catch (error) {
      console.error("Failed to start run:", error)
    }
  }

  const overallProgress = runDetails?.progress || 0

  return (
    <>
      <ThinkingNow apiBase={API_BASE} runId={currentRunId} />
      <AppShell showLeftRail={false}>
        <div className="flex h-[calc(100vh-4rem)]">
        {/* Left Panel - Outline & Progress */}
        <ResizablePanel
          defaultWidth={leftPanelWidth}
          minWidth={280}
          maxWidth={480}
          onResize={setLeftPanelWidth}
          className="border-r border-border hidden md:block"
        >
          <div className="h-full flex flex-col">
            {/* Top bar with breadcrumb */}
            <div className="px-4 py-3 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Project</span>
                <ChevronRight className="w-4 h-4" />
                <span className="text-foreground font-medium">Run #{currentRunId?.slice(0, 6) || "..."}</span>
              </div>
              <Button size="sm" variant="ghost" className="h-8" onClick={() => setCurrentRunId(null)}>
                <Plus className="w-4 h-4 mr-1" />
                New
              </Button>
            </div>

            {/* Left panel content */}
            <div className="flex-1 overflow-auto p-4 space-y-6">
              {/* Topic Form */}
              <div>
                <h3 className="text-sm font-semibold text-foreground mb-3">New Research</h3>
                <TopicForm onSubmit={handleTopicSubmit} />
              </div>

              <Separator />

              {/* Outline */}
              {runDetails?.outline && (
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-3">Outline</h3>
                  <div className="space-y-2">
                    {runDetails.outline.map((item) => (
                      <OutlineItem
                        key={item.id}
                        item={item}
                        onClick={() => console.log("[v0] Clicked item:", item.id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Progress bar at bottom */}
            {runDetails && (
              <div className="p-4 border-t border-border">
                <ProgressStrip
                  overall={overallProgress}
                  items={runDetails.outline.map((item) => ({ id: item.id, progress: item.progress || 0 }))}
                />
              </div>
            )}
          </div>
        </ResizablePanel>

        {/* Right Panel - Tabbed Content */}
        <div className="flex-1 flex flex-col bg-background">
          <Tabs defaultValue="sources" className="flex-1 flex flex-col">
            <div className="border-b border-border px-4">
              <TabsList className="h-12 bg-transparent">
                <TabsTrigger
                  value="sources"
                  className="data-[state=active]:border-[#6d28d9] data-[state=active]:text-[#6d28d9]"
                >
                  Sources
                </TabsTrigger>
                <TabsTrigger
                  value="notes"
                  className="data-[state=active]:border-[#6d28d9] data-[state=active]:text-[#6d28d9]"
                >
                  Notes
                </TabsTrigger>
                <TabsTrigger
                  value="draft"
                  className="data-[state=active]:border-[#6d28d9] data-[state=active]:text-[#6d28d9]"
                >
                  Draft
                </TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="sources" className="flex-1 m-0 p-6">
              {isLoading ? (
                <div className="text-center py-12 text-muted-foreground">Loading sources...</div>
              ) : runDetails?.sources && runDetails.sources.length > 0 ? (
                <SourcesTable sources={runDetails.sources} />
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  No sources yet. Start a research run to see sources.
                </div>
              )}
            </TabsContent>

            <TabsContent value="notes" className="flex-1 m-0 p-6">
              {isLoading ? (
                <div className="text-center py-12 text-muted-foreground">Loading notes...</div>
              ) : runDetails?.notes && runDetails.notes.length > 0 ? (
                <NotesLog notes={runDetails.notes} />
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  No notes yet. Reflections will appear here during research.
                </div>
              )}
            </TabsContent>

            <TabsContent value="draft" className="flex-1 m-0 p-6">
              {isLoading ? (
                <div className="text-center py-12 text-muted-foreground">Loading draft...</div>
              ) : runDetails?.draft ? (
                <MarkdownViewer
                  content={runDetails.draft}
                  onExportMd={() => console.log("Export markdown")}
                  onExportPdf={() => console.log("Export PDF")}
                  onRegenerate={(id) => console.log("Regenerate paragraph:", id)}
                  onAddHint={(id, hint) => console.log("Add hint:", id, hint)}
                />
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  No draft yet. Content will appear as research progresses.
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </AppShell>
    </>
  )
}
