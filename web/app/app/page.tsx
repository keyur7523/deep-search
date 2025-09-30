"use client"

import { useState, useEffect } from "react"
import { ResearchChat } from "@/components/research-chat"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { 
  Plus, 
  History, 
  Play, 
  CheckCircle, 
  Clock, 
  AlertCircle,
  Search,
  FileText
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { createProject, startRun } from "@/lib/api"

interface ResearchRun {
  id: string
  title: string
  status: 'queued' | 'planning' | 'running' | 'done' | 'failed'
  createdAt: Date
  progress: number
}

export default function AppPage() {
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [runs, setRuns] = useState<ResearchRun[]>([])
  const [isCreating, setIsCreating] = useState(false)
  
  // New research form state
  const [topic, setTopic] = useState("")
  const [maxParagraphs, setMaxParagraphs] = useState(5)
  const [roundsPerParagraph, setRoundsPerParagraph] = useState(3)
  const [searchProvider, setSearchProvider] = useState("hybrid")

  const handleExportReport = () => {
    console.log('Export report for run:', currentRunId)
  }

  const handleStartResearch = async () => {
    if (!topic.trim()) return
    
    try {
      setIsCreating(true)
      
      // Create project
      const project = await createProject(topic)
      
      // Start run
      const run = await startRun({
        topic: topic,
        maxParagraphs: maxParagraphs,
        roundsPerParagraph: roundsPerParagraph,
        searchProvider: searchProvider
      })
      
      // Add to runs list
      const newRun: ResearchRun = {
        id: run.id,
        title: topic,
        status: 'queued',
        createdAt: new Date(),
        progress: 0
      }
      
      setRuns(prev => [newRun, ...prev])
      setCurrentRunId(run.id)
      
      // Reset form
      setTopic("")
      setIsCreating(false)
      
    } catch (error) {
      console.error('Failed to start research:', error)
      setIsCreating(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'running':
        return <Play className="w-4 h-4 text-blue-600" />
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-600" />
      default:
        return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'done':
        return 'bg-green-100 text-green-800'
      case 'running':
        return 'bg-blue-100 text-blue-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Left Sidebar */}
      <div className="w-80 border-r border-border flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-6 h-6 text-primary" />
            <h1 className="text-lg font-semibold">Deep Research</h1>
          </div>
          
          {/* New Research Form */}
          <div className="space-y-3">
            <div>
              <Label htmlFor="topic" className="text-sm font-medium">
                Research Topic
              </Label>
              <Input
                id="topic"
                placeholder="e.g., Climate Change Impacts"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="mt-1"
              />
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="maxParagraphs" className="text-sm font-medium">
                  Sections
                </Label>
                <Select value={maxParagraphs.toString()} onValueChange={(v) => setMaxParagraphs(parseInt(v))}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[3, 4, 5, 6, 7, 8].map(num => (
                      <SelectItem key={num} value={num.toString()}>{num}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label htmlFor="rounds" className="text-sm font-medium">
                  Depth
                </Label>
                <Select value={roundsPerParagraph.toString()} onValueChange={(v) => setRoundsPerParagraph(parseInt(v))}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[1, 2, 3, 4, 5].map(num => (
                      <SelectItem key={num} value={num.toString()}>{num}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            <div>
              <Label htmlFor="searchProvider" className="text-sm font-medium">
                Search Type
              </Label>
              <Select value={searchProvider} onValueChange={setSearchProvider}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hybrid">🎓 Academic + Web</SelectItem>
                  <SelectItem value="scholar">📚 Academic Only (SerpAPI)</SelectItem>
                  <SelectItem value="crossref">📖 Academic Only (CrossRef)</SelectItem>
                  <SelectItem value="serpapi">🌐 Web Only</SelectItem>
                  <SelectItem value="brave">🔍 Brave Search</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <Button 
              onClick={handleStartResearch}
              disabled={!topic.trim() || isCreating}
              className="w-full"
            >
              <Plus className="w-4 h-4 mr-2" />
              {isCreating ? 'Starting...' : 'Start Research'}
            </Button>
          </div>
        </div>
        
        {/* Research History */}
        <div className="flex-1 overflow-hidden">
          <div className="p-4 border-b border-border">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-sm font-medium">Research History</h2>
            </div>
          </div>
          
          <ScrollArea className="flex-1">
            <div className="p-2">
              {runs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">No research runs yet</p>
                  <p className="text-xs">Start your first research above</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {runs.map((run) => (
                    <div
                      key={run.id}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        currentRunId === run.id 
                          ? 'bg-accent border border-primary/20' 
                          : 'hover:bg-accent/50'
                      }`}
                      onClick={() => setCurrentRunId(run.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-medium truncate">
                            {run.title}
                          </h3>
                          <div className="flex items-center gap-2 mt-1">
                            {getStatusIcon(run.status)}
                            <Badge 
                              variant="secondary" 
                              className={`text-xs ${getStatusColor(run.status)}`}
                            >
                              {run.status}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {formatDistanceToNow(run.createdAt, { addSuffix: true })}
                            </span>
                          </div>
                        </div>
                        <div className="text-right ml-2">
                          <div className="text-xs font-medium">{run.progress}%</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <ResearchChat
          runId={currentRunId}
          onExportReport={handleExportReport}
        />
      </div>
    </div>
  )
}