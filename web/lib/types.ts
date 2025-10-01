export interface ResearchThread {
  id: string
  title: string
  status: 'active' | 'completed' | 'failed' | 'paused'
  messages: ResearchMessage[]
  createdAt: Date
  updatedAt: Date
  completedAt?: Date
  progress: number
  outline?: OutlineItem[]
  finalReport?: string
  metadata?: {
    maxParagraphs: number
    roundsPerParagraph: number
    searchProvider: string
    totalSources: number
    qualityScore?: number
  }
}

export interface ResearchMessage {
  id: string
  threadId: string
  type: 'user' | 'system' | 'progress' | 'result' | 'error' | 'outline' | 'search' | 'source' | 'draft' | 'complete'
  content: string
  timestamp: Date
  metadata?: {
    section?: number
    sectionTitle?: string
    sources?: number
    academic?: number
    web?: number
    quality?: number
    url?: string
    sourceType?: 'academic' | 'web'
    citations?: number
    duration?: number
    round?: number
    query?: string
    rationale?: string
  }
  isStreaming?: boolean
}

export interface OutlineItem {
  id: string
  index: number
  title: string
  brief: string
  status: 'queued' | 'searching' | 'drafting' | 'done' | 'failed'
  progress: number
  sources?: number
  quality?: number
}

export interface Source {
  id: string
  title: string
  url: string
  snippet: string
  type: 'academic' | 'web'
  authors?: string
  year?: number
  citations?: number
  section: number
  quality?: number
}

export interface NewResearchRequest {
  topic: string
  maxParagraphs: number
  roundsPerParagraph: number
  searchProvider?: string
}

export interface ResearchProgress {
  threadId: string
  status: 'planning' | 'running' | 'completed' | 'failed'
  progress: number
  currentSection?: number
  totalSections?: number
  currentActivity?: string
  estimatedTimeRemaining?: number
}
