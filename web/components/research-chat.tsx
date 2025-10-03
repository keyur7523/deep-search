"use client"

import { useState, useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
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
  ExternalLink,
  Settings,
  ChevronDown,
  MessageSquarePlus,
  X
} from "lucide-react"
import { useRunMessages } from "@/hooks/useRunMessages"
import { API_BASE } from "@/lib/config"
import { createProject, startRun } from "@/lib/api"
import ReactMarkdown from "react-markdown"
import jsPDF from "jspdf"

interface ResearchChatProps {
  runId: string | null
  onRunStarted?: (runId: string) => void
  onRunCreated?: (run: any) => void
  onStartNewChat?: () => void
}

const MODEL_TO_PROVIDER: Record<string, string> = {
  "Academic + Web": "hybrid",
  "Academic Only (SerpAPI)": "serpapi",
  "Academic Only (CrossRef)": "crossref",
  "Web Only": "brave",
  "Brave Search": "brave"
}

const MIN_TOPIC_LENGTH = 10

export function ResearchChat({ runId, onRunStarted, onRunCreated, onStartNewChat }: ResearchChatProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const msgs = useRunMessages(API_BASE, runId)
  const [reportContent, setReportContent] = useState<string>("")
  const [isLoadingReport, setIsLoadingReport] = useState(false)
  const [isExportingPDF, setIsExportingPDF] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const [selectedModel, setSelectedModel] = useState("Academic + Web")
  const [topic, setTopic] = useState("")
  const [sections, setSections] = useState(5)
  const [depth, setDepth] = useState(3)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (!target.closest('[data-dropdown]')) {
        setShowSettings(false)
        setShowModelDropdown(false)
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [])

  useEffect(() => {
    if (runId) {
      setReportContent("")
      setIsLoadingReport(false)
    }
  }, [runId])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n' && runId) {
        e.preventDefault()
        onStartNewChat?.()
      }
      if (e.key === 'Enter' && !runId && topic.trim() && !isCreating) {
        handleStartResearch()
      }
      if (e.key === 'Escape') {
        setShowSettings(false)
        setShowModelDropdown(false)
      }
    }
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [runId, topic, isCreating])

  const handleStartResearch = async () => {
    if (topic.trim().length < MIN_TOPIC_LENGTH) {
      setError(`Topic must be at least ${MIN_TOPIC_LENGTH} characters`)
      return
    }
    
    try {
      setIsCreating(true)
      setError(null)
      
      console.log('1. Creating project:', { topic, sections })
      
      // Create project
      const projectResponse = await createProject(topic, sections)
      console.log('2. Project response:', projectResponse)
      
      // Extract project_id from response
      const projectId = projectResponse.project_id
      console.log('3. Project ID:', projectId)
      
      // Start run with the project ID
      const runResponse = await startRun(
        projectId,
        depth,
        MODEL_TO_PROVIDER[selectedModel] || 'hybrid'
      )
      console.log('4. Run response:', runResponse)
      
      // Extract run_id from response
      const runId = runResponse.run_id
      console.log('5. Run ID:', runId)
      
      // Create run object for parent
      const newRun = {
        id: runId,
        title: topic,
        status: 'running',
        createdAt: new Date(),
        progress: 0
      }
      
      // Notify parent components
      onRunCreated?.(newRun)
      onRunStarted?.(runId)
      
      // Reset form
      setTopic("")
      setShowSettings(false)
      setShowModelDropdown(false)
      
    } catch (error) {
      console.error('Error starting research:', error)
      setError(error instanceof Error ? error.message : 'Failed to start research. Please try again.')
    } finally {
      setIsCreating(false)
    }
  }

  // Fetch report when research is complete 
  useEffect(() => {
    const isComplete = msgs.some(msg => msg.kind === 'complete')
    if (isComplete && runId) {
      // Always fetch when runId changes or completion detected
      fetchReport()
    }
  }, [msgs, runId])

  const fetchReport = async () => {
    if (!runId) return
    
    try {
      setIsLoadingReport(true)
      const response = await fetch(`${API_BASE}/runs/${runId}/report`)
      
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

  const exportToPDF = async () => {
    if (!reportContent) {
      alert('No report content available to export.')
      return
    }
    
    try {
      setIsExportingPDF(true)
      
      const pdf = new jsPDF('p', 'mm', 'a4')
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const margin = 20
      const maxWidth = pageWidth - (margin * 2)
      
      pdf.setFontSize(20)
      pdf.setTextColor(109, 40, 217)
      pdf.text('Research Report', margin, margin + 10)
      
      pdf.setFontSize(12)
      pdf.setTextColor(100, 100, 100)
      pdf.text(`Run ID: ${runId?.slice(-8) || 'Unknown'}`, margin, margin + 20)
      pdf.text(`Generated: ${new Date().toLocaleDateString()}`, margin, margin + 30)
      
      pdf.setDrawColor(109, 40, 217)
      pdf.setLineWidth(0.5)
      pdf.line(margin, margin + 35, pageWidth - margin, margin + 35)
      
      let yPosition = margin + 45
      const lineHeight = 7
      const fontSize = 11
      
      pdf.setFontSize(fontSize)
      pdf.setTextColor(0, 0, 0)
      
      const lines = reportContent.split('\n')
      
      for (const line of lines) {
        if (line.trim() === '') {
          yPosition += lineHeight
          continue
        }
        
        if (line.startsWith('#')) {
          const headerLevel = line.match(/^#+/)?.[0].length || 1
          const headerText = line.replace(/^#+\s*/, '')
          
          pdf.setFontSize(fontSize + (4 - headerLevel))
          pdf.setFont('helvetica', 'bold')
          
          if (yPosition > pageHeight - margin - 20) {
            pdf.addPage()
            yPosition = margin + 10
          }
          
          pdf.text(headerText, margin, yPosition)
          yPosition += lineHeight + 5
          pdf.setFont('helvetica', 'normal')
          pdf.setFontSize(fontSize)
          continue
        }
        
        pdf.setFont('helvetica', 'normal')
        pdf.setFontSize(fontSize)
        
        const words = line.split(' ')
        let currentLine = ''
        
        for (const word of words) {
          const testLine = currentLine + (currentLine ? ' ' : '') + word
          const textWidth = pdf.getTextWidth(testLine)
          
          if (textWidth > maxWidth && currentLine !== '') {
            if (yPosition > pageHeight - margin - 10) {
              pdf.addPage()
              yPosition = margin + 10
            }
            
            pdf.text(currentLine, margin, yPosition)
            yPosition += lineHeight
            currentLine = word
          } else {
            currentLine = testLine
          }
        }
        
        if (currentLine) {
          if (yPosition > pageHeight - margin - 10) {
            pdf.addPage()
            yPosition = margin + 10
          }
          
          pdf.text(currentLine, margin, yPosition)
          yPosition += lineHeight
        }
      }
      
      const totalPages = pdf.getNumberOfPages()
      for (let i = 1; i <= totalPages; i++) {
        pdf.setPage(i)
        pdf.setFontSize(8)
        pdf.setTextColor(150, 150, 150)
        pdf.text('Generated by Deep Research', margin, pageHeight - 10)
        pdf.text(`Page ${i} of ${totalPages}`, pageWidth - margin - 20, pageHeight - 10)
      }
      
      pdf.save(`research-report-${runId?.slice(-8) || 'unknown'}.pdf`)
      
    } catch (error) {
      console.error('Error exporting PDF:', error)
      alert(`Failed to export PDF: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setIsExportingPDF(false)
    }
  }

  const getMessageIcon = (kind: string, role: string) => {
    if (role === 'user') return <User className="w-4 h-4" />
    
    switch (kind) {
      case 'status': return <Clock className="w-4 h-4" />
      case 'query': return <Search className="w-4 h-4" />
      case 'fetch': return <BookOpen className="w-4 h-4" />
      case 'reflect': return <CheckCircle className="w-4 h-4" />
      case 'draft': return <FileText className="w-4 h-4" />
      case 'section': return <CheckCircle className="w-4 h-4" />
      case 'complete': return <Sparkles className="w-4 h-4" />
      case 'error': return <AlertCircle className="w-4 h-4" />
      default: return <Bot className="w-4 h-4" />
    }
  }

  const getMessageColor = (kind: string, role: string) => {
    if (role === 'user') return 'bg-primary text-primary-foreground'
    
    switch (kind) {
      case 'status': return 'bg-blue-100 text-blue-800 border border-blue-200'
      case 'query': return 'bg-green-100 text-green-800 border border-green-200'
      case 'fetch': return 'bg-purple-100 text-purple-800 border border-purple-200'
      case 'reflect': return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'draft': return 'bg-orange-100 text-orange-800 border border-orange-200'
      case 'section': return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'complete': return 'bg-yellow-100 text-yellow-800 border border-yellow-200'
      case 'error': return 'bg-red-100 text-red-800 border border-red-200'
      default: return 'bg-muted text-muted-foreground'
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

    const { section, sources, academic, web, quality, citations, query, url } = meta

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
            aria-label="View source in new tab"
          >
            <ExternalLink className="w-3 h-3 mr-1" />
            View Source
          </Button>
        )}
      </div>
    )
  }

  const isComplete = msgs.some(msg => msg.kind === 'complete')
  const isTopicValid = topic.trim().length >= MIN_TOPIC_LENGTH
  const topicError = topic.length > 0 && !isTopicValid 
    ? `Topic must be at least ${MIN_TOPIC_LENGTH} characters` 
    : null

  if (!runId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-8 w-full max-w-4xl mx-auto px-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent mb-4">
              Deep Research
            </h1>
          </div>
          
          <div className="relative w-full mx-auto" data-dropdown>
            <div className="relative">
              <input
                type="text"
                placeholder="What is your research topic for today?"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && isTopicValid && !isCreating) {
                    handleStartResearch()
                  }
                }}
                className="w-full h-12 md:h-16 px-6 text-base md:text-lg border border-gray-300 rounded-2xl focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20 outline-none transition-all shadow-lg bg-white/90 backdrop-blur-sm"
                aria-label="Research topic input"
                aria-invalid={!!topicError}
                aria-describedby={topicError ? "topic-error" : undefined}
              />
            </div>
            
            {(topicError || error) && (
              <div id="topic-error" className="mt-2 text-sm text-red-600 text-left px-2">
                {error || topicError}
              </div>
            )}
            
            <div className="flex items-center justify-between mt-4 px-2 flex-wrap gap-2">
              <button
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors bg-white/80 rounded-lg hover:bg-white border border-gray-200 shadow-sm"
                aria-label="Toggle settings"
                aria-expanded={showSettings}
              >
                <Settings className="w-4 h-4" />
                <span className="text-sm font-medium">Settings</span>
              </button>
              
              <button
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors bg-white/80 rounded-lg hover:bg-white border border-gray-200 shadow-sm"
                aria-label="Select model"
                aria-expanded={showModelDropdown}
              >
                <span className="text-sm font-medium">{selectedModel}</span>
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
            
            {showSettings && (
              <div className="absolute top-32 left-0 bg-white border border-gray-200 rounded-xl shadow-xl p-4 w-64 z-[var(--z-dropdown,20)]">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Settings</h3>
                  <button
                    onClick={() => setShowSettings(false)}
                    className="text-gray-400 hover:text-gray-600"
                    aria-label="Close settings"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="sections-select" className="text-sm font-medium text-gray-700 block mb-2">
                      Sections
                    </label>
                    <select 
                      id="sections-select"
                      value={sections} 
                      onChange={(e) => setSections(parseInt(e.target.value))}
                      className="w-full h-10 px-3 border border-gray-200 rounded-lg focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20 outline-none"
                    >
                      {[3, 4, 5, 6, 7, 8].map(num => (
                        <option key={num} value={num}>{num}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div>
                    <label htmlFor="depth-select" className="text-sm font-medium text-gray-700 block mb-2">
                      Depth
                    </label>
                    <select 
                      id="depth-select"
                      value={depth} 
                      onChange={(e) => setDepth(parseInt(e.target.value))}
                      className="w-full h-10 px-3 border border-gray-200 rounded-lg focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20 outline-none"
                    >
                      {[1, 2, 3, 4, 5].map(num => (
                        <option key={num} value={num}>{num}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}
            
            {showModelDropdown && (
              <div className="absolute top-32 right-0 bg-white border border-gray-200 rounded-xl shadow-xl p-2 w-56 z-[var(--z-dropdown,20)]">
                <div className="space-y-1">
                  {Object.keys(MODEL_TO_PROVIDER).map((model) => (
                    <button
                      key={model}
                      onClick={() => {
                        setSelectedModel(model)
                        setShowModelDropdown(false)
                      }}
                      className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${
                        selectedModel === model ? 'bg-purple-50 text-purple-700' : 'hover:bg-gray-50'
                      }`}
                    >
                      {model}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          <button 
            onClick={handleStartResearch}
            disabled={!isTopicValid || isCreating}
            className="w-75 h-12 md:h-16 px-8 md:px-12 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-small text-lg md:text-xl rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center mx-auto disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={isCreating ? 'Starting research' : 'Start research'}
          >
            {isCreating ? 'Starting...' : 'Start Research'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex bg-background relative">
      {runId && onStartNewChat && (
        <button
          onClick={onStartNewChat}
          className="fixed bottom-6 right-6 z-[var(--z-fab,40)] bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white p-4 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center gap-2"
          aria-label="Start new research chat (Ctrl+N)"
          title="Start new research (Ctrl+N)"
        >
          <MessageSquarePlus className="w-5 h-5" />
          <span className="text-sm font-medium hidden md:inline">New Chat</span>
        </button>
      )}
      
      <div className="flex flex-col flex-1">
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
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={exportToPDF}
                  disabled={isExportingPDF || !reportContent}
                  aria-label="Download report as PDF"
                >
                  {isExportingPDF ? 'Generating...' : 'Download PDF'}
                </Button>
              )}
            </div>
          </div>
        </div>

        {isComplete ? (
          <div className="flex flex-1 overflow-hidden">
            <div className="flex-1 flex flex-col min-h-0">
              <div className="p-4 border-b border-border flex-shrink-0">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Report</span>
                </div>
              </div>
              <div className="flex-1 overflow-auto">
                <div className="p-4 md:p-6">
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
                        Research completed successfully with {msgs.filter(m => m.kind === 'fetch').length} sources analyzed.
                      </p>
                      <p className="text-sm text-muted-foreground mt-2">
                        Report generation in progress...
                      </p>
                      <div className="mt-4 space-y-2">
                        {msgs.filter(m => m.kind === 'section').map((msg, i) => (
                          <div key={i} className="text-sm bg-background p-2 rounded border">
                            {msg.text}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="w-80 border-l border-border flex flex-col min-h-0 hidden lg:flex">
              <div className="p-4 border-b border-border flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Logs</span>
                </div>
              </div>
              <div className="flex-1 overflow-auto">
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
                      <div className="text-xs text-foreground line-clamp-2">
                        {message.text}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {new Date(message.t).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <ScrollArea className="flex-1" ref={scrollAreaRef}>
            <div className="p-4 space-y-4 max-w-4xl mx-auto">
              {msgs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Bot className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No messages yet</p>
                </div>
              ) : (
                msgs.map((message) => (
                  <div key={message._id} className="flex gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${getMessageColor(message.kind, message.role)}`}>
                      {getMessageIcon(message.kind, message.role)}
                    </div>
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
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
                      <div className="text-sm text-foreground break-words">
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