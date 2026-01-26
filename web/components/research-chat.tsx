"use client"

import React, { useState, useEffect, useRef } from "react"
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
import { useAgentEventStream } from "@/hooks/useAgentEventStream"
import { API_BASE } from "@/lib/config"
import { createProject, createRunV2 } from "@/lib/api"
import type { AgentMode } from "@/lib/types"
import ReactMarkdown from "react-markdown"
import jsPDF from "jspdf"
import { AnimatePresence, SlideDown, FadeIn, motion } from "@/components/ui/animations"
import { SkeletonReport } from "@/components/ui/skeletons"
import { useResearchStore } from "@/stores"
import { buildOutlineFromReport } from "@/lib/outline"

interface ResearchChatProps {
  runId: string | null
  onRunStarted?: (runId: string) => void
  onRunCreated?: (run: any) => void
  onStartNewChat?: () => void
}

interface ResearchMessage {
  _id: string
  role: 'user' | 'assistant'
  kind: 'status' | 'query' | 'fetch' | 'reflect' | 'draft' | 'section' | 'complete' | 'error' | 'info' | 'thinking' | 'action' | 'result'
  text: string
  t: string
  meta?: {
    section?: number
    sources?: number
    academic?: number
    web?: number
    quality?: number
    citations?: number
    query?: string
    url?: string
    score?: number
    decision?: string
    round?: number
    idx?: number
  }
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
  const settingsRef = useRef<HTMLDivElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const regularMsgs = useRunMessages(API_BASE, runId)
  const [agentEvents, setAgentEvents] = useState<ResearchMessage[]>([])
  const [isExportingPDF, setIsExportingPDF] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showModelDropdown, setShowModelDropdown] = useState(false)
  const [selectedModel, setSelectedModel] = useState("Academic + Web")
  const [topic, setTopic] = useState("")
  const [sections, setSections] = useState(5)
  const [depth, setDepth] = useState(3)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [researchMode, setResearchMode] = useState<AgentMode>("auto")
  const [liveMessage, setLiveMessage] = useState("")
  const {
    report,
    setReport,
    setOutline,
    setCurrentRunId,
    setStatus,
    setProgress,
    setError: setRunError,
    reset,
  } = useResearchStore()

  useAgentEventStream(runId)

  // Combine regular messages and agent events
  const msgs = regularMsgs.length > 0 ? regularMsgs : agentEvents

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs])

  // Enhanced aria-live announcements for accessibility
  useEffect(() => {
    const latest = msgs[msgs.length - 1]
    if (!latest?.text) return
    const label = latest.kind === 'error' ? 'Error' : 'Update'
    setLiveMessage(`${label}: ${latest.text}`)
  }, [msgs])

  // Announce progress changes
  const { progress, status } = useResearchStore()
  const prevProgressRef = React.useRef(progress)
  const prevStatusRef = React.useRef(status)

  useEffect(() => {
    // Announce significant progress changes (every 25%)
    if (progress !== prevProgressRef.current) {
      const prevMilestone = Math.floor(prevProgressRef.current / 25)
      const currentMilestone = Math.floor(progress / 25)
      if (currentMilestone > prevMilestone && progress > 0) {
        setLiveMessage(`Research ${progress}% complete`)
      }
      prevProgressRef.current = progress
    }
  }, [progress])

  useEffect(() => {
    // Announce status transitions
    if (status !== prevStatusRef.current) {
      const statusMessages: Record<string, string> = {
        'researching': 'Research started',
        'writing': 'Writing report',
        'completed': 'Research completed successfully',
        'error': 'An error occurred during research',
      }
      if (statusMessages[status]) {
        setLiveMessage(statusMessages[status])
      }
      prevStatusRef.current = status
    }
  }, [status])

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
    if (!showSettings) return
    const container = settingsRef.current
    if (!container) return
    const focusable = container.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    first?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || focusable.length === 0) return
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last?.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first?.focus()
      }
    }
    container.addEventListener('keydown', onKeyDown)
    return () => container.removeEventListener('keydown', onKeyDown)
  }, [showSettings])

  useEffect(() => {
    if (!showModelDropdown) return
    const container = modelRef.current
    if (!container) return
    const focusable = container.querySelectorAll<HTMLElement>(
      'button, [href], [tabindex]:not([tabindex="-1"])'
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    first?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || focusable.length === 0) return
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last?.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first?.focus()
      }
    }
    container.addEventListener('keydown', onKeyDown)
    return () => container.removeEventListener('keydown', onKeyDown)
  }, [showModelDropdown])

  useEffect(() => {
    // Always clear state when runId changes (including when it becomes null)
    if (!runId) {
      reset()
      setAgentEvents([])
      return
    }
    setCurrentRunId(runId)
    setStatus('researching')
    setProgress(0)
    setReport("")
    setAgentEvents([])
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
      
      // Create project
      const projectResponse = await createProject(topic, sections)
      const projectId = projectResponse.project_id
      
      // Use V2 endpoint with agentic routing
      const runResponse = await createRunV2(projectId, {
        forceMode: researchMode === "auto" ? undefined : researchMode,
        deepMode: depth > 3,
        minCitations: depth * 5,
        searchProvider: MODEL_TO_PROVIDER[selectedModel] || 'hybrid',
        maxParagraphs: sections,
        rounds: depth
      })
      
      const runId = runResponse.run_id
      
      // Create run object for parent
      const newRun = {
        id: runId,
        title: topic,
        status: 'running',
        createdAt: new Date(),
        progress: 0,
        mode: runResponse.mode
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
      setRunError(error instanceof Error ? error.message : 'Failed to start research. Please try again.')
      setStatus('error')
    } finally {
      setIsCreating(false)
    }
  }

  const fetchReport = async () => {
    if (!runId) return
    
    try {
      console.log('📡 Fetching report from:', `${API_BASE}/runs/${runId}/report`)
      const response = await fetch(`${API_BASE}/runs/${runId}/report`)
      
      console.log('📡 Report response status:', response.status)
      
      if (response.ok) {
        const data = await response.json()
        console.log('📡 Report data received:', data.markdown ? `${data.markdown.length} chars` : 'no markdown')
        if (data.markdown) {
          setReport(data.markdown)
          setOutline(buildOutlineFromReport(data.markdown))
          console.log('✅ Report content set!')
        }
      } else {
        console.log('❌ Report not ready, status:', response.status)
      }
    } catch (error) {
      console.log('❌ Report fetch error:', error)
    }
  }

  const exportToPDF = async () => {
    if (!report) {
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
      
      const lines = report.split('\n')
      
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
      case 'thinking':
      case 'status': return <Clock className="w-4 h-4" />
      case 'query':
      case 'action': return <Search className="w-4 h-4" />
      case 'fetch': return <BookOpen className="w-4 h-4" />
      case 'reflect': return <CheckCircle className="w-4 h-4" />
      case 'draft': return <FileText className="w-4 h-4" />
      case 'section':
      case 'result': return <CheckCircle className="w-4 h-4" />
      case 'complete': return <Sparkles className="w-4 h-4" />
      case 'error': return <AlertCircle className="w-4 h-4" />
      default: return <Bot className="w-4 h-4" />
    }
  }

  const getMessageColor = (kind: string, role: string) => {
    if (role === 'user') return 'bg-primary text-primary-foreground'
    
    switch (kind) {
      case 'thinking':
      case 'status': return 'bg-blue-100 text-blue-800 border border-blue-200'
      case 'query':
      case 'action': return 'bg-green-100 text-green-800 border border-green-200'
      case 'fetch': return 'bg-purple-100 text-purple-800 border border-purple-200'
      case 'reflect': return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'draft': return 'bg-orange-100 text-orange-800 border border-orange-200'
      case 'section':
      case 'result': return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
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

    const { section, sources, academic, web, quality, citations, query, url, score, decision } = meta

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
        
        {(quality || score) && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Quality: {(quality || score)?.toFixed(1)}/10</span>
          </div>
        )}
        
        {citations && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>{citations} citations</span>
          </div>
        )}
        
        {decision && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span>Decision: {decision}</span>
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

  // Check if research is far enough along to show report panel
  const paragraphCount = msgs.filter(m => m.kind === 'result' && m.text.includes('Created paragraph')).length
  const lastMsg = msgs[msgs.length - 1]
  const agentsFinished = msgs.length > 0 && (
    paragraphCount >= 3 || // If we have 3+ paragraphs, start trying to fetch report
    paragraphCount >= sections || // Or if we have all requested sections
    lastMsg?.text?.toLowerCase().includes('all tasks complete') ||
    lastMsg?.text?.toLowerCase().includes('done') || // Backend sends "done"
    lastMsg?.kind === 'complete' // Backend sends kind: 'complete'
  )
  
  // Debug logging
  if (msgs.length > 0 && lastMsg) {
    console.log('🔍 Completion check:', {
      paragraphCount,
      sections,
      lastMsgText: lastMsg.text,
      lastMsgKind: lastMsg.kind,
      agentsFinished
    })
  }
  
  const isComplete = agentsFinished || !!report
  const isTopicValid = topic.trim().length >= MIN_TOPIC_LENGTH
  const topicError = topic.length > 0 && !isTopicValid 
    ? `Topic must be at least ${MIN_TOPIC_LENGTH} characters` 
    : null

  useEffect(() => {
    if (!isComplete && sections > 0) {
      const computed = Math.min(90, Math.round((paragraphCount / sections) * 100))
      setProgress(Number.isFinite(computed) ? computed : 0)
      setStatus('researching')
    }
  }, [isComplete, paragraphCount, sections, setProgress, setStatus])

  useEffect(() => {
    if (isComplete) {
      setStatus('completed')
      setProgress(100)
    }
  }, [isComplete, setProgress, setStatus])

  // Fetch report when research is complete
  useEffect(() => {
    if (!runId) return
    if (!isComplete) return // Wait for agents to finish
    if (report) return // Already have report

    let isCancelled = false

    // Start polling immediately when agents finish
    fetchReport()

    // Then poll every 3 seconds until we get the report
    const interval = setInterval(async () => {
      if (isCancelled) return

      try {
        const response = await fetch(`${API_BASE}/runs/${runId}/report`)
        if (response.ok) {
          const data = await response.json()
          if (data.markdown && !isCancelled) {
            setReport(data.markdown)
            setOutline(buildOutlineFromReport(data.markdown))
            clearInterval(interval) // Stop polling once we have content
          }
        }
      } catch (error) {
        // Silently continue polling on error
      }
    }, 3000)

    return () => {
      isCancelled = true
      clearInterval(interval)
    }
  }, [runId, isComplete, report])

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
            
            <AnimatePresence>
              {(topicError || error) && (
                <FadeIn>
                  <div id="topic-error" className="mt-2 text-sm text-red-600 text-left px-2">
                    {error || topicError}
                  </div>
                </FadeIn>
              )}
            </AnimatePresence>
            
            <div className="flex items-center justify-between mt-4 px-2 flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowSettings(!showSettings)}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors bg-white/80 rounded-lg hover:bg-white border border-gray-200 shadow-sm"
                aria-label="Toggle settings"
                aria-expanded={showSettings}
                aria-controls="research-settings-panel"
              >
                <Settings className="w-4 h-4" />
                <span className="text-sm font-medium">Settings</span>
              </button>
              
              <button
                type="button"
                onClick={() => setShowModelDropdown(!showModelDropdown)}
                className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors bg-white/80 rounded-lg hover:bg-white border border-gray-200 shadow-sm"
                aria-label="Select model"
                aria-expanded={showModelDropdown}
                aria-controls="model-select-panel"
              >
                <span className="text-sm font-medium">{selectedModel}</span>
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
            
            <AnimatePresence>
              {showSettings && (
              <SlideDown
                id="research-settings-panel"
                ref={settingsRef}
                role="dialog"
                aria-modal="true"
                aria-label="Research settings"
                className="absolute top-32 left-0 bg-white border border-gray-200 rounded-xl shadow-xl p-4 w-64 z-[var(--z-dropdown,20)]"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Settings</h3>
                  <button
                    type="button"
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
                  <div>
                    <label htmlFor="mode-select" className="text-sm font-medium text-gray-700 block mb-2">
                      Research Mode
                    </label>
                    <select 
                      id="mode-select"
                      value={researchMode} 
                      onChange={(e) => setResearchMode(e.target.value as AgentMode)}
                      className="w-full h-10 px-3 border border-gray-200 rounded-lg focus:border-purple-400 focus:ring-2 focus:ring-purple-400/20 outline-none"
                    >
                      <option value="auto">Auto (Recommended)</option>
                      <option value="simple">Simple (Fast)</option>
                      <option value="agentic">Agentic (Deep)</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      {researchMode === "auto" && "System decides based on topic"}
                      {researchMode === "simple" && "Fast, linear pipeline"}
                      {researchMode === "agentic" && "Multi-agent with quality gates"}
                    </p>
                  </div>
                </div>
              </SlideDown>
              )}
            </AnimatePresence>
            
            <AnimatePresence>
              {showModelDropdown && (
                <SlideDown
                  id="model-select-panel"
                  ref={modelRef}
                  role="menu"
                  aria-label="Model selection"
                  className="absolute top-32 right-0 bg-white border border-gray-200 rounded-xl shadow-xl p-2 w-56 z-[var(--z-dropdown,20)]"
                >
                  <div className="space-y-1">
                    {Object.keys(MODEL_TO_PROVIDER).map((model) => (
                      <button
                        key={model}
                        onClick={() => {
                          setSelectedModel(model)
                          setShowModelDropdown(false)
                        }}
                        role="menuitem"
                        className={`w-full text-left px-3 py-2 text-sm rounded-lg transition-colors ${
                          selectedModel === model ? 'bg-purple-50 text-purple-700' : 'hover:bg-gray-50'
                        }`}
                      >
                        {model}
                      </button>
                    ))}
                  </div>
                </SlideDown>
              )}
            </AnimatePresence>
          </div>
          
          <motion.button
            onClick={handleStartResearch}
            disabled={!isTopicValid || isCreating}
            className="w-75 h-12 md:h-16 px-8 md:px-12 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-small text-lg md:text-xl rounded-xl shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center mx-auto disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={isCreating ? 'Starting research' : 'Start research'}
            whileTap={{ scale: 0.98 }}
          >
            {isCreating ? 'Starting...' : 'Start Research'}
          </motion.button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex bg-background relative">
      <div className="sr-only" role="status" aria-live="polite">
        {liveMessage}
      </div>
      {runId && onStartNewChat && (
        <motion.button
          onClick={onStartNewChat}
          className="fixed bottom-6 right-6 z-[var(--z-fab,40)] bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white p-4 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center gap-2"
          aria-label="Start new research chat (Ctrl+N)"
          title="Start new research (Ctrl+N)"
          whileTap={{ scale: 0.98 }}
        >
          <MessageSquarePlus className="w-5 h-5" />
          <span className="text-sm font-medium hidden md:inline">New Chat</span>
        </motion.button>
      )}
      
      <div className="flex flex-col flex-1 overflow-hidden">
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
                  {msgs.length} events
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {isComplete && (
                <Button 
                  size="sm" 
                  variant="outline" 
                  onClick={exportToPDF}
                  disabled={isExportingPDF || !report}
                  aria-label="Download report as PDF"
                >
                  {isExportingPDF ? 'Generating...' : 'Download PDF'}
                </Button>
              )}
            </div>
          </div>
        </div>

        {isComplete ? (
          <div className="flex flex-1 min-h-0 h-[calc(100vh-140px)] overflow-hidden">
            {/* Research Report - Left Panel with independent scroll */}
            <div className="flex-1 flex flex-col min-h-0 h-full overflow-hidden">
              <div className="p-4 border-b border-border flex-shrink-0">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Report</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="p-4 md:p-6">
                  {report ? (
                    <div className="prose prose-sm max-w-none markdown-content">
                      <ReactMarkdown
                        skipHtml={true}
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
                          // Security: Render links safely with rel="noopener noreferrer"
                          a: ({href, children}) => (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-primary hover:underline"
                            >
                              {children}
                            </a>
                          ),
                        }}
                      >
                        {report}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                        <span>Generating report... Compiling {paragraphCount} sections.</span>
                      </div>
                      <SkeletonReport />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Research Logs - Right Panel with independent scroll */}
            <div className="w-80 border-l border-border flex flex-col min-h-0 hidden lg:flex h-full overflow-hidden">
              <div className="p-4 border-b border-border flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  <span className="text-sm font-medium">Research Logs</span>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="p-2 space-y-2">
                  {msgs.map((message, idx) => (
                    <div key={message._id || idx} className="p-2 rounded border bg-background">
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
                  <p>Agents are working...</p>
                </div>
              ) : (
                msgs.map((message, idx) => (
                  <div key={message._id || idx} className="flex gap-3">
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
