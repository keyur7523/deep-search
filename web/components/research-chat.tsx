"use client"

import { useState, useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  User,
  Bot,
  Search,
  FileText,
  CheckCircle,
  Clock,
  AlertCircle,
  Sparkles,
  BookOpen,
  Globe,
  ExternalLink
} from "lucide-react"
import { ResearchThread, ResearchMessage } from "@/lib/types"
import { formatDistanceToNow } from "date-fns"
import { useRunMessages } from "@/hooks/useRunMessages"
import { API_BASE } from "@/lib/config"
import ReactMarkdown from "react-markdown"

interface ResearchChatProps {
  runId: string | null
  onExportReport?: () => void
}

export function ResearchChat({ runId, onExportReport }: ResearchChatProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const msgs = useRunMessages(API_BASE, runId)
  const [reportContent, setReportContent] = useState<string>("")
  const [isLoadingReport, setIsLoadingReport] = useState(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  // Fetch report when research is complete
  useEffect(() => {
    const isComplete = msgs.some(msg => msg.kind === 'complete')
    if (isComplete && runId && !reportContent) {
      fetchReport()
    }
  }, [msgs, runId, reportContent])

  const fetchReport = async () => {
    if (!runId) return
    
    try {
      setIsLoadingReport(true)
      
      // Try with the provided runId first
      let response = await fetch(`${API_BASE}/runs/${runId}/report`)
      
      // If that fails and the runId looks short, try to find the full ID
      if (!response.ok && runId.length < 24) {
        console.log('Short runId detected, fetching runs to find full ID...')
        const runsResponse = await fetch(`${API_BASE}/runs`)
        if (runsResponse.ok) {
          const runsData = await runsResponse.json()
          const fullRun = runsData.runs?.find((r: any) => r.id.endsWith(runId))
          if (fullRun) {
            console.log('Found full run ID:', fullRun.id)
            response = await fetch(`${API_BASE}/runs/${fullRun.id}/report`)
          }
        }
      }
      
      if (response.ok) {
        const data = await response.json()
        setReportContent(data.markdown || "")
      } else {
        console.error('Failed to fetch report:', response.status, response.statusText)
      }
    } catch (error) {
      console.error('Failed to fetch report:', error)
    } finally {
      setIsLoadingReport(false)
    }
  }

  const getMessageIcon = (kind: string, role: string) => {
    if (role === 'user') return <User className="w-4 h-4" />
    
    switch (kind) {
      case 'status':
        return <Clock className="w-4 h-4" />
      case 'query':
        return <Search className="w-4 h-4" />
      case 'fetch':
        return <BookOpen className="w-4 h-4" />
      case 'reflect':
        return <CheckCircle className="w-4 h-4" />
      case 'draft':
        return <FileText className="w-4 h-4" />
      case 'section':
        return <CheckCircle className="w-4 h-4" />
      case 'complete':
        return <Sparkles className="w-4 h-4" />
      case 'error':
        return <AlertCircle className="w-4 h-4" />
      case 'info':
        return <Bot className="w-4 h-4" />
      default:
        return <Bot className="w-4 h-4" />
    }
  }

  const getMessageColor = (kind: string, role: string) => {
    if (role === 'user') return 'bg-primary text-primary-foreground'
    
    switch (kind) {
      case 'status':
        return 'bg-blue-100 text-blue-800 border border-blue-200'
      case 'query':
        return 'bg-green-100 text-green-800 border border-green-200'
      case 'fetch':
        return 'bg-purple-100 text-purple-800 border border-purple-200'
      case 'reflect':
        return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'draft':
        return 'bg-orange-100 text-orange-800 border border-orange-200'
      case 'section':
        return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'complete':
        return 'bg-yellow-100 text-yellow-800 border border-yellow-200'
      case 'error':
        return 'bg-red-100 text-red-800 border border-red-200'
      case 'info':
        return 'bg-muted text-muted-foreground'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const renderMessageContent = (text: string) => {
    const lines = text.split('\n')
    return (
      <div className="space-y-1">
        {lines.map((line, index) => (
          <p key={index} className="text-sm whitespace-pre-wrap">
            {line}
          </p>
        ))}
      </div>
    )
  }

  const renderMessageMetadata = (meta: any) => {
    if (!meta) return null

    const { section, sources, academic, web, quality, citations, query, url, round, idx } = meta

    return (
      <div className="mt-2 space-y-1">
        {section && (
          <Badge variant="outline" className="text-xs">
            Section {section}
          </Badge>
        )}
        
        {sources && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <BookOpen className="w-3 h-3" />
            <span>{sources} sources</span>
            {academic && web && (
              <span>({academic} academic, {web} web)</span>
            )}
          </div>
        )}
        
        {quality && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Quality: {quality.toFixed(1)}/10</span>
          </div>
        )}
        
        {citations && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{citations} citations</span>
          </div>
        )}
        
        {query && (
          <div className="text-xs text-muted-foreground italic">
            Query: "{query}"
          </div>
        )}
        
        {url && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs"
            onClick={() => window.open(url, '_blank')}
          >
            <ExternalLink className="w-3 h-3 mr-1" />
            View Source
          </Button>
        )}
      </div>
    )
  }

  const isComplete = msgs.some(msg => msg.kind === 'complete')

  if (!runId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <Sparkles className="w-16 h-16 mx-auto text-muted-foreground/50" />
          <div>
            <h3 className="text-lg font-semibold text-foreground">Welcome to Deep Research</h3>
            <p className="text-muted-foreground">
              Select a research run from the sidebar or start a new research project
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex bg-background">
      {/* Main Content Area */}
      <div className={`flex flex-col ${isComplete ? 'flex-1' : 'flex-1'}`}>
        {/* Header */}
        <div className="p-4 border-b border-border bg-muted/30">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Research Run {runId.slice(-8)}</h2>
              <div className="flex items-center gap-2 mt-1">
                <Badge variant="outline" className={`text-xs ${
                  isComplete ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                }`}>
                  {isComplete ? 'completed' : 'active'}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {msgs.length} messages
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {isComplete && (
                <Button size="sm" variant="outline" onClick={onExportReport}>
                  Export Report
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Content - Split when complete */}
        {isComplete ? (
          <div className="flex flex-1">
            {/* Report Area */}
            <div className="flex-1 flex flex-col">
              <div className="p-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Report</span>
                </div>
              </div>
              <ScrollArea className="flex-1">
                <div className="p-4">
                  {isLoadingReport ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                        <p className="text-sm text-muted-foreground">Loading report...</p>
                      </div>
                    </div>
                  ) : reportContent ? (
                    <div className="prose prose-sm max-w-none markdown-content">
                      <ReactMarkdown
                        components={{
                          h1: ({children}) => <h1 className="text-2xl font-bold mb-4 text-foreground">{children}</h1>,
                          h2: ({children}) => <h2 className="text-xl font-semibold mb-3 mt-6 text-foreground">{children}</h2>,
                          h3: ({children}) => <h3 className="text-lg font-medium mb-2 mt-4 text-foreground">{children}</h3>,
                          p: ({children}) => <p className="mb-3 text-foreground leading-relaxed">{children}</p>,
                          strong: ({children}) => <strong className="font-semibold text-foreground">{children}</strong>,
                          em: ({children}) => <em className="italic text-foreground">{children}</em>,
                          ul: ({children}) => <ul className="list-disc list-inside mb-4 space-y-1">{children}</ul>,
                          ol: ({children}) => <ol className="list-decimal list-inside mb-4 space-y-1">{children}</ol>,
                          li: ({children}) => <li className="text-foreground">{children}</li>,
                          blockquote: ({children}) => <blockquote className="border-l-4 border-primary pl-4 italic text-muted-foreground my-4">{children}</blockquote>,
                          code: ({children}) => <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono">{children}</code>,
                        }}
                      >
                        {reportContent}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="bg-muted/50 p-4 rounded-lg">
                      <p className="text-sm text-muted-foreground">
                        📊 Research completed successfully with {msgs.filter(m => m.kind === 'fetch').length} sources analyzed.
                      </p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Report generation in progress...
                      </p>
                      <div className="mt-4 space-y-2">
                        {msgs.filter(m => m.kind === 'section').map((msg, i) => (
                          <div key={i} className="text-sm bg-background p-2 rounded border">
                            ✅ {msg.text}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </div>

            {/* Logs Sidebar */}
            <div className="w-80 border-l border-border flex flex-col">
              <div className="p-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Logs</span>
                </div>
              </div>
              <ScrollArea className="flex-1">
                <div className="p-2 space-y-2">
                  {msgs.map((message) => (
                    <div key={message._id} className="p-2 rounded border bg-background">
                      <div className="flex items-center gap-2 mb-1">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${getMessageColor(message.kind, message.role)}`}>
                          {getMessageIcon(message.kind, message.role)}
                        </div>
                        <span className="text-xs font-medium capitalize">
                          {message.role === 'user' ? 'User' : 'Assistant'}
                        </span>
                        <span className="text-xs text-muted-foreground uppercase">
                          {message.kind}
                        </span>
                      </div>
                      <div className="text-xs text-foreground">
                        {message.text}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(message.t).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </div>
        ) : (
          /* Messages during research */
          <ScrollArea className="flex-1" ref={scrollAreaRef}>
            <div className="p-4 space-y-4">
              {msgs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Bot className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No messages yet</p>
                </div>
              ) : (
                msgs.map((message) => (
                  <div key={message._id} className="flex gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getMessageColor(message.kind, message.role)}`}>
                      {getMessageIcon(message.kind, message.role)}
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground capitalize">
                          {message.role === 'user' ? 'You' : 'Assistant'}
                        </span>
                        <span className="mr-2 opacity-60 text-xs text-muted-foreground uppercase">
                          {message.kind}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(message.t).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="text-sm text-foreground">
                        {renderMessageContent(message.text)}
                      </div>
                      {renderMessageMetadata(message.meta)}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  )
}
