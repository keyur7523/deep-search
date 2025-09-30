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

interface ResearchChatProps {
  thread: ResearchThread | null
  isLoading?: boolean
  onExportReport?: () => void
}

export function ResearchChat({ thread, isLoading = false, onExportReport }: ResearchChatProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thread?.messages])

  const getMessageIcon = (type: string) => {
    switch (type) {
      case 'user':
        return <User className="w-4 h-4" />
      case 'system':
        return <Bot className="w-4 h-4" />
      case 'progress':
        return <Clock className="w-4 h-4" />
      case 'search':
        return <Search className="w-4 h-4" />
      case 'source':
        return <BookOpen className="w-4 h-4" />
      case 'result':
        return <CheckCircle className="w-4 h-4" />
      case 'complete':
        return <Sparkles className="w-4 h-4" />
      case 'error':
        return <AlertCircle className="w-4 h-4" />
      default:
        return <Bot className="w-4 h-4" />
    }
  }

  const getMessageColor = (type: string) => {
    switch (type) {
      case 'user':
        return 'bg-primary text-primary-foreground'
      case 'system':
        return 'bg-muted text-muted-foreground'
      case 'progress':
        return 'bg-blue-100 text-blue-800 border border-blue-200'
      case 'search':
        return 'bg-green-100 text-green-800 border border-green-200'
      case 'source':
        return 'bg-purple-100 text-purple-800 border border-purple-200'
      case 'result':
        return 'bg-emerald-100 text-emerald-800 border border-emerald-200'
      case 'complete':
        return 'bg-yellow-100 text-yellow-800 border border-yellow-200'
      case 'error':
        return 'bg-red-100 text-red-800 border border-red-200'
      default:
        return 'bg-muted text-muted-foreground'
    }
  }

  const renderMessageContent = (message: ResearchMessage) => {
    const lines = message.content.split('\n')
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

  const renderMessageMetadata = (message: ResearchMessage) => {
    if (!message.metadata) return null

    const { section, sectionTitle, sources, academic, web, quality, citations, query, url } = message.metadata

    return (
      <div className="mt-2 space-y-1">
        {section && sectionTitle && (
          <Badge variant="outline" className="text-xs">
            Section {section}: {sectionTitle}
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

  if (!thread) {
    return (
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <Sparkles className="w-16 h-16 mx-auto text-muted-foreground/50" />
          <div>
            <h3 className="text-lg font-semibold text-foreground">Welcome to Deep Research</h3>
            <p className="text-muted-foreground">
              Select a research thread from the sidebar or start a new research project
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col bg-background">
      {/* Thread Header */}
      <div className="p-4 border-b border-border bg-muted/30">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">{thread.title}</h2>
            <div className="flex items-center gap-2 mt-1">
              <Badge 
                variant="outline" 
                className={`text-xs ${
                  thread.status === 'completed' ? 'bg-green-100 text-green-800' :
                  thread.status === 'active' ? 'bg-blue-100 text-blue-800' :
                  thread.status === 'failed' ? 'bg-red-100 text-red-800' :
                  'bg-gray-100 text-gray-800'
                }`}
              >
                {thread.status}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {thread.messages?.length || 0} messages
              </span>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {thread.status === 'completed' && (
              <Button size="sm" variant="outline" onClick={onExportReport}>
                Export Report
              </Button>
            )}
            <div className="text-right">
              <div className="text-sm font-medium text-foreground">{thread.progress}%</div>
              <Progress value={thread.progress} className="w-20 h-2" />
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollAreaRef}>
        <div className="p-4 space-y-4">
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex gap-3 animate-pulse">
                  <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                    <div className="h-3 bg-gray-200 rounded w-3/4"></div>
                  </div>
                </div>
              ))}
            </div>
          ) : thread.messages?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No messages yet</p>
            </div>
          ) : (
            thread.messages?.map((message) => (
              <div key={message.id} className="flex gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getMessageColor(message.type)}`}>
                  {getMessageIcon(message.type)}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-foreground capitalize">
                      {message.type === 'user' ? 'You' : 'Assistant'}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
                    </span>
                  </div>
                  <div className="text-sm text-foreground">
                    {renderMessageContent(message)}
                  </div>
                  {renderMessageMetadata(message)}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Final Report Preview */}
      {thread.status === 'completed' && thread.finalReport && (
        <div className="border-t border-border p-4 bg-muted/20">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4" />
            <span className="text-sm font-medium">Final Report</span>
          </div>
          <div className="text-sm text-muted-foreground max-h-32 overflow-hidden">
            <div className="prose prose-sm max-w-none">
              {thread.finalReport.substring(0, 200)}...
            </div>
          </div>
          <Button 
            size="sm" 
            variant="outline" 
            className="mt-2"
            onClick={onExportReport}
          >
            View Full Report
          </Button>
        </div>
      )}
    </div>
  )
}
