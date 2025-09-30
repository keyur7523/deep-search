"use client"

import { useState, useEffect } from "react"
import { ResearchSidebar } from "@/components/research-sidebar"
import { ResearchChat } from "@/components/research-chat"
import { ResearchThread, NewResearchRequest } from "@/lib/types"
import { getResearchThreads, getResearchThread, startNewResearch } from "@/lib/api"
import { API_BASE } from "@/lib/config"

export default function AppPage() {
  const [threads, setThreads] = useState<ResearchThread[]>([])
  const [currentThread, setCurrentThread] = useState<ResearchThread | null>(null)
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [isLoadingThread, setIsLoadingThread] = useState(false)

  // Load research threads on mount
  useEffect(() => {
    loadThreads()
  }, [])

  // Poll for updates when a thread is active
  useEffect(() => {
    if (!currentThread || currentThread.status === 'completed' || currentThread.status === 'failed') {
      return
    }

    const pollInterval = setInterval(async () => {
      try {
        const updatedThread = await getResearchThread(currentThread.id)
        setCurrentThread(updatedThread)
        
        // Update the thread in the threads list
        setThreads(prev => prev.map(t => t.id === updatedThread.id ? updatedThread : t))
      } catch (error) {
        console.error('Failed to poll thread updates:', error)
      }
    }, 2000)

    return () => clearInterval(pollInterval)
  }, [currentThread])

  const loadThreads = async () => {
    try {
      setIsLoadingThreads(true)
      const threadsData = await getResearchThreads()
      setThreads(threadsData)
    } catch (error) {
      console.error('Failed to load threads:', error)
    } finally {
      setIsLoadingThreads(false)
    }
  }

  const handleThreadSelect = async (threadId: string) => {
    try {
      setIsLoadingThread(true)
      const thread = await getResearchThread(threadId)
      setCurrentThread(thread)
    } catch (error) {
      console.error('Failed to load thread:', error)
    } finally {
      setIsLoadingThread(false)
    }
  }

  const handleNewResearch = async (data: NewResearchRequest) => {
    try {
      const newThread = await startNewResearch(data)
      
      // Add to threads list
      setThreads(prev => [newThread, ...prev])
      
      // Select the new thread
      setCurrentThread(newThread)
      
      // Start polling for updates
      const pollInterval = setInterval(async () => {
        try {
          const updatedThread = await getResearchThread(newThread.id)
          setCurrentThread(updatedThread)
          setThreads(prev => prev.map(t => t.id === updatedThread.id ? updatedThread : t))
          
          // Stop polling when completed
          if (updatedThread.status === 'completed' || updatedThread.status === 'failed') {
            clearInterval(pollInterval)
          }
        } catch (error) {
          console.error('Failed to poll thread updates:', error)
          clearInterval(pollInterval)
        }
      }, 2000)
      
    } catch (error) {
      console.error('Failed to start research:', error)
    }
  }

  const handleExportReport = () => {
    if (currentThread?.finalReport) {
      // Create a blob with the markdown content
      const blob = new Blob([currentThread.finalReport], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      
      // Create a temporary link and click it to download
      const link = document.createElement('a')
      link.href = url
      link.download = `${currentThread.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_research.md`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Left Sidebar - Research History */}
      <div className="w-80 border-r border-border">
        <ResearchSidebar
          threads={threads}
          currentThreadId={currentThread?.id}
          onThreadSelect={handleThreadSelect}
          onNewResearch={handleNewResearch}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <ResearchChat
          thread={currentThread}
          isLoading={isLoadingThread}
          onExportReport={handleExportReport}
        />
      </div>
    </div>
  )
}