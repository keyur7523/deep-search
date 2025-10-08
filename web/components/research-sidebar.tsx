"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { TopicForm } from "@/components/topic-form"
import { Plus, Clock, CheckCircle, XCircle, Pause, Sparkles } from "lucide-react"
import { ResearchThread } from "@/lib/types"
import type { AgentMode } from "@/lib/types"
import { formatDistanceToNow } from "date-fns"

interface ResearchSidebarProps {
  threads: ResearchThread[]
  currentThreadId?: string
  onThreadSelect: (threadId: string) => void
  onNewResearch: (data: { 
    topic: string
    maxParagraphs: number
    roundsPerParagraph: number
    searchProvider?: string
    mode?: AgentMode
    deepMode?: boolean
    minCitations?: number
  }) => void
  isLoading?: boolean
}

export function ResearchSidebar({ 
  threads, 
  currentThreadId, 
  onThreadSelect, 
  onNewResearch,
  isLoading = false 
}: ResearchSidebarProps) {
  const [showNewForm, setShowNewForm] = useState(false)

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
      case 'running':
        return <Clock className="w-3 h-3 text-blue-500" />
      case 'completed':
        return <CheckCircle className="w-3 h-3 text-green-500" />
      case 'failed':
        return <XCircle className="w-3 h-3 text-red-500" />
      case 'paused':
        return <Pause className="w-3 h-3 text-yellow-500" />
      default:
        return <Clock className="w-3 h-3 text-gray-500" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'running':
        return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200'
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'paused':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200'
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  const handleNewResearch = (data: {
    topic: string
    maxParagraphs: number
    roundsPerParagraph: number
    searchProvider?: string
    mode?: AgentMode
    deepMode?: boolean
    minCitations?: number
  }) => {
    onNewResearch(data)
    setShowNewForm(false)
  }

  return (
    <div className="h-full flex flex-col bg-background border-r border-border">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Research History</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowNewForm(!showNewForm)}
            className="h-8"
          >
            <Plus className="w-4 h-4 mr-1" />
            New
          </Button>
        </div>
        
        {showNewForm && (
          <div className="space-y-4">
            <TopicForm onSubmit={handleNewResearch} />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowNewForm(false)}
              className="w-full"
            >
              Cancel
            </Button>
          </div>
        )}
      </div>

      {/* Threads List */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-3">
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="p-3 border border-border rounded-lg animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                </div>
              ))}
            </div>
          ) : threads.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Sparkles className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No research yet</p>
              <p className="text-xs">Start your first research project</p>
            </div>
          ) : (
            threads.map((thread) => (
              <div
                key={thread.id}
                className={`p-3 border rounded-lg cursor-pointer transition-all hover:shadow-sm ${
                  currentThreadId === thread.id
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50'
                }`}
                onClick={() => onThreadSelect(thread.id)}
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-sm text-foreground line-clamp-2 flex-1">
                    {thread.title}
                  </h3>
                  <div className="flex items-center ml-2">
                    {getStatusIcon(thread.status)}
                  </div>
                </div>
                
                <div className="flex items-center justify-between mb-2">
                  <Badge 
                    variant="outline" 
                    className={`text-xs ${getStatusColor(thread.status)}`}
                  >
                    {thread.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {thread.progress}%
                  </span>
                </div>
                
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{thread.messages?.length || 0} messages</span>
                  <span>{formatDistanceToNow(new Date(thread.updatedAt), { addSuffix: true })}</span>
                </div>
                
                {thread.latestMessage && (
                  <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                    {thread.latestMessage}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}