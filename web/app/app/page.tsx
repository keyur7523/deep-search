"use client"

import { useState, useEffect } from "react"
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
import { startRun, getRunStatus, getOutline, getReport, getRecentRuns } from "@/lib/api"
import ThinkingNow from "@/components/thinking-now"
import { API_BASE } from "@/lib/config"

export default function AppPage() {
  const [leftPanelWidth, setLeftPanelWidth] = useState(320)
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [runStatus, setRunStatus] = useState<{status: string, progress: number} | null>(null)
  const [outline, setOutline] = useState<any[]>([])
  const [finalMarkdown, setFinalMarkdown] = useState<string>("")

  // Load the most recent run on page load
  useEffect(() => {
    const loadRecentRun = async () => {
      try {
        const recentRuns = await getRecentRuns(1)
        if (recentRuns.length > 0 && recentRuns[0].status === "completed") {
          setCurrentRunId(recentRuns[0].id)
        }
      } catch (error) {
        console.error("Failed to load recent runs:", error)
      }
    }
    
    loadRecentRun()
  }, [])

  // Poll status every 2 seconds
  useEffect(() => {
    if (!currentRunId) return
    
    const pollStatus = async () => {
      try {
        const status = await getRunStatus(currentRunId)
        setRunStatus(status)
        
        // If done, fetch the report
        if (status.status === "done") {
          try {
            const report = await getReport(currentRunId)
            setFinalMarkdown(report.markdown)
          } catch (error) {
            console.error("Failed to fetch report:", error)
          }
        }
      } catch (error) {
        console.error("Failed to poll status:", error)
      }
    }

    // Initial poll
    pollStatus()
    
    // Set up interval
    const interval = setInterval(pollStatus, 2000)
    return () => clearInterval(interval)
  }, [currentRunId])

  // Poll outline every 3 seconds
  useEffect(() => {
    if (!currentRunId) return
    
    const pollOutline = async () => {
      try {
        const outlineData = await getOutline(currentRunId)
        setOutline(outlineData)
      } catch (error) {
        console.error("Failed to fetch outline:", error)
      }
    }

    // Initial poll
    pollOutline()
    
    // Set up interval
    const interval = setInterval(pollOutline, 3000)
    return () => clearInterval(interval)
  }, [currentRunId])

  const handleTopicSubmit = async (data: { topic: string; maxParagraphs: number; roundsPerParagraph: number }) => {
    console.log("Starting new research:", data)
    try {
      const run = await startRun(data)
      setCurrentRunId(run.id)
      setRunStatus({ status: "running", progress: 0 })
      setOutline([])
      setFinalMarkdown("")
    } catch (error) {
      console.error("Failed to start run:", error)
    }
  }

  const overallProgress = runStatus?.progress || 0

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
              {outline && outline.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-foreground mb-3">Outline</h3>
                  <div className="space-y-2">
                    {outline.map((item) => (
                      <OutlineItem
                        key={item._id}
                        item={{
                          id: item._id,
                          index: item.idx,
                          title: item.heading,
                          brief: item.brief,
                          progress: item.status === "done" ? 100 : item.status === "drafting" ? 80 : item.status === "searching" ? 40 : 0,
                          status: item.status
                        }}
                        onClick={() => console.log("[v0] Clicked item:", item._id)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Progress bar at bottom */}
            {runStatus && (
              <div className="p-4 border-t border-border">
                <ProgressStrip
                  overall={overallProgress}
                  items={outline.map((item) => ({ 
                    id: item._id, 
                    progress: item.status === "done" ? 100 : item.status === "drafting" ? 80 : item.status === "searching" ? 40 : 0 
                  }))}
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
              <div className="text-center py-12 text-muted-foreground">
                Sources will be available in a future update.
              </div>
            </TabsContent>

            <TabsContent value="notes" className="flex-1 m-0 p-6">
              <div className="text-center py-12 text-muted-foreground">
                Notes will be available in a future update.
              </div>
            </TabsContent>

            <TabsContent value="draft" className="flex-1 m-0 p-6">
              {finalMarkdown ? (
                <MarkdownViewer
                  content={finalMarkdown}
                  onExportMd={() => console.log("Export markdown")}
                  onExportPdf={() => console.log("Export PDF")}
                  onRegenerate={(id) => console.log("Regenerate paragraph:", id)}
                  onAddHint={(id, hint) => console.log("Add hint:", id, hint)}
                />
              ) : runStatus?.status === "done" ? (
                <div className="text-center py-12 text-muted-foreground">
                  Report is ready but couldn't be loaded. Check console for errors.
                </div>
              ) : runStatus?.status === "running" ? (
                <div className="text-center py-12 text-muted-foreground">
                  Research in progress... Final report will appear here when complete.
                </div>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  No report yet. Start a research run to generate content.
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
