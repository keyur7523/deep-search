"use client"

import { useState, useEffect, useMemo } from "react"
import { ResearchChat } from "@/components/research-chat"
import { ScrollArea } from "@/components/ui/scroll-area"
import { 
  History, 
  Play, 
  CheckCircle, 
  Clock, 
  AlertCircle,
  Search
} from "lucide-react"
import { getRecentRuns } from "@/lib/api"
import { useUIStore, useResearchStore } from "@/stores"
import { useListNavigation } from "@/hooks/useKeyboardShortcuts"
import { SkeletonList } from "@/components/ui/skeletons"
import { PageTransition, StaggerContainer, StaggerItem } from "@/components/ui/animations"

interface ResearchRun {
  id: string
  title: string
  status: 'queued' | 'planning' | 'running' | 'done' | 'failed'
  createdAt: Date
  progress: number
}

export default function AppPage() {
  const [runs, setRuns] = useState<ResearchRun[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const { currentRunId, setCurrentRunId } = useResearchStore()

  // Load existing runs on mount
  useEffect(() => {
    const loadRuns = async () => {
      try {
        const recentRuns = await getRecentRuns(20)
        const formattedRuns: ResearchRun[] = recentRuns.map(run => ({
          id: run.id,
          title: run.topic,
          status: run.status === 'completed' ? 'done' : run.status === 'failed' ? 'failed' : 'running',
          createdAt: new Date(run.createdAt),
          progress: run.progress
        }))
        // Sort by createdAt in descending order (newest first)
        formattedRuns.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())
        setRuns(formattedRuns)
      } catch (error) {
        console.error('Failed to load runs:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    loadRuns()
  }, [])

  // Memoize active runs count to avoid recalculating on every render
  const activeRunsCount = useMemo(() => {
    return runs.filter(r => r.status === 'running' || r.status === 'queued' || r.status === 'planning').length
  }, [runs])

  // Update run statuses periodically - only for active runs
  useEffect(() => {
    if (activeRunsCount === 0) return

    const updateRunStatuses = async () => {
      try {
        const recentRuns = await getRecentRuns(20)
        const updatedRuns: ResearchRun[] = recentRuns.map(run => ({
          id: run.id,
          title: run.topic,
          status: run.status === 'completed' ? 'done' : run.status === 'failed' ? 'failed' : 'running',
          createdAt: new Date(run.createdAt),
          progress: run.progress
        }))
        // Sort by createdAt in descending order (newest first)
        updatedRuns.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())

        // Only update if we have runs, and preserve the order
        setRuns(prevRuns => {
          // If we have no previous runs, use the updated runs
          if (prevRuns.length === 0) return updatedRuns

          // Otherwise, merge and maintain newest-first order
          const mergedRuns = [...updatedRuns]
          // Add any runs from prevRuns that aren't in updatedRuns (in case of new runs)
          prevRuns.forEach(prevRun => {
            if (!mergedRuns.find(r => r.id === prevRun.id)) {
              mergedRuns.push(prevRun)
            }
          })
          // Re-sort to maintain newest-first order
          mergedRuns.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime())
          return mergedRuns
        })
      } catch (error) {
        console.error('Failed to update run statuses:', error)
      }
    }

    const interval = setInterval(updateRunStatuses, 5000)
    return () => clearInterval(interval)
  }, [activeRunsCount])

  const handleStartNewChat = () => {
    setCurrentRunId(null)
  }

  const handleRunStarted = (runId: string) => {
    setCurrentRunId(runId)
  }

  const handleRunCreated = (newRun: ResearchRun) => {
    console.log('Adding new run to top:', newRun)
    setRuns(prev => [newRun, ...prev])
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'running':
      case 'planning':
        return <Play className="w-4 h-4 text-blue-600" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-600" />
      default:
        return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  const { activeIndex, setActiveIndex } = useListNavigation(
    runs.length,
    (index) => {
      const run = runs[index]
      if (run) setCurrentRunId(run.id)
    },
    { enabled: runs.length > 0 }
  )

  return (
    <PageTransition className="h-full">
      <div className="flex h-screen bg-background">
      {/* Left Sidebar - Fixed */}
      {sidebarOpen && (
        <div className="w-80 border-r border-border flex flex-col fixed left-0 top-0 h-full bg-background z-[var(--z-sidebar,10)]">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center shadow-lg">
                <svg viewBox="0 0 24 24" fill="none" className="w-7 h-7 text-white" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
                  <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
                </svg>
              </div>
              <span className="font-semibold text-lg text-foreground">Deep Research</span>
            </div>
            <button
              type="button"
              onClick={toggleSidebar}
              className="text-xs text-muted-foreground hover:text-foreground"
              aria-label="Hide sidebar"
            >
              Hide
            </button>
          </div>
        </div>
        
        {/* Research History */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="p-4 border-b border-border flex-shrink-0">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-sm font-medium">Research History</h2>
            </div>
          </div>
          
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-2">
              {isLoading ? (
                <div className="p-2">
                  <SkeletonList items={6} hasIcon={false} hasSubtext={true} />
                </div>
              ) : runs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No research runs yet</p>
                  <p className="text-xs">Start your first research above</p>
                </div>
              ) : (
                <StaggerContainer className="space-y-2">
                  {runs.map((run, index) => (
                    <StaggerItem key={run.id}>
                      <button
                        className={`w-full px-3 py-2 rounded-lg transition-colors flex items-center justify-between outline-none ${
                          currentRunId === run.id || activeIndex === index
                            ? 'bg-accent border border-primary/20'
                            : 'hover:bg-accent/50'
                        }`}
                        onClick={() => setCurrentRunId(run.id)}
                        onFocus={() => setActiveIndex(index)}
                        aria-label={`View research: ${run.title}`}
                        aria-current={currentRunId === run.id ? 'page' : undefined}
                      >
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          {getStatusIcon(run.status)}
                          <span className="text-sm font-medium truncate text-left">
                            {run.title}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground ml-2">
                          {run.progress}%
                        </div>
                      </button>
                    </StaggerItem>
                  ))}
                </StaggerContainer>
              )}
            </div>
          </ScrollArea>
        </div>
      </div>
      )}

      {/* Main Chat Area */}
      <div className={`flex-1 flex flex-col ${sidebarOpen ? 'ml-80' : 'ml-0'}`}>
        {!sidebarOpen && (
          <div className="p-3 border-b border-border bg-background flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Sidebar hidden</span>
            <button
              type="button"
              onClick={toggleSidebar}
              className="text-sm font-medium text-primary hover:underline"
            >
              Show sidebar
            </button>
          </div>
        )}
        <ResearchChat
          runId={currentRunId}
          onRunStarted={handleRunStarted}
          onRunCreated={handleRunCreated}
          onStartNewChat={handleStartNewChat}
        />
      </div>
    </div>
    </PageTransition>
  )
}
