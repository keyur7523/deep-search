"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { AppShell } from "@/components/app-shell"
import { AgentEventViewer } from "@/components/agent-event-viewer"
import { TaskGraphViewer } from "@/components/task-graph-viewer"
import { SkeletonOutlineItem, SkeletonReport } from "@/components/ui/skeletons"
import { getReport } from "@/lib/api"
import ReactMarkdown from "react-markdown"
import { Button } from "@/components/ui/button"
import { Copy } from "lucide-react"
import { PageTransition, motion } from "@/components/ui/animations"
import { useResearchStore } from "@/stores"
import { buildOutlineFromReport } from "@/lib/outline"
import { OutlineItem } from "@/components/outline-item"

export default function RunPage() {
  const params = useParams()
  const runId = params.id as string
  
  const [report, setReport] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)
  const outline = useResearchStore((state) => state.outline)
  const setOutline = useResearchStore((state) => state.setOutline)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const reportData = await getReport(runId)
        const markdown = reportData.markdown || ""
        setReport(markdown)
        setOutline(buildOutlineFromReport(markdown))
        setLoading(false)
      } catch (error) {
        console.log("Report not ready yet")
        setLoading(false)
      }
    }
    
    // Poll every 3 seconds
    fetchReport()
    const interval = setInterval(fetchReport, 3000)
    return () => clearInterval(interval)
  }, [runId])

  const handleCopy = () => {
    navigator.clipboard.writeText(report)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <AppShell>
      <PageTransition>
        <div className="container max-w-7xl mx-auto px-4 md:px-6 py-8">
        {/* Header */}
        <header className="mb-6">
          <h1 className="text-2xl font-bold">Research Run {runId.slice(-8)}</h1>
        </header>

        {/* Agent Visualizations */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <TaskGraphViewer runId={runId} />
          <AgentEventViewer runId={runId} />
        </div>

        {/* Outline */}
        <div className="border rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Outline</h2>
            <span className="text-xs text-muted-foreground">{outline.length} items</span>
          </div>
          {loading ? (
            <div className="space-y-3">
              <SkeletonOutlineItem />
              <SkeletonOutlineItem />
              <SkeletonOutlineItem />
            </div>
          ) : outline.length === 0 ? (
            <p className="text-muted-foreground">Outline will appear when the report is ready.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {outline.map((item) => (
                <OutlineItem key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        {/* Report */}
        <div className="border rounded-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Research Report</h2>
            {report && (
              <Button asChild variant="outline" size="sm">
                <motion.button onClick={handleCopy} whileTap={{ scale: 0.98 }}>
                  <Copy className="w-4 h-4 mr-2" />
                  {copied ? "Copied!" : "Copy"}
                </motion.button>
              </Button>
            )}
          </div>
          
          {loading ? (
            <div className="py-4">
              <SkeletonReport />
            </div>
          ) : report ? (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{report}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-muted-foreground">Report will appear when agents complete synthesis...</p>
          )}
        </div>
        </div>
      </PageTransition>
    </AppShell>
  )
}
