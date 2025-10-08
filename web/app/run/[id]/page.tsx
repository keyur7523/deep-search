"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { AppShell } from "@/components/app-shell"
import { AgentEventViewer } from "@/components/agent-event-viewer"
import { TaskGraphViewer } from "@/components/task-graph-viewer"
import { getReport } from "@/lib/api"
import ReactMarkdown from "react-markdown"
import { Button } from "@/components/ui/button"
import { Download, Copy } from "lucide-react"

export default function RunPage() {
  const params = useParams()
  const runId = params.id as string
  
  const [report, setReport] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const reportData = await getReport(runId)
        setReport(reportData.markdown || "")
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

        {/* Report */}
        <div className="border rounded-lg p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Research Report</h2>
            {report && (
              <Button variant="outline" size="sm" onClick={handleCopy}>
                <Copy className="w-4 h-4 mr-2" />
                {copied ? "Copied!" : "Copy"}
              </Button>
            )}
          </div>
          
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
              <p>Generating report...</p>
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
    </AppShell>
  )
}