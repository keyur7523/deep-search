// Research run types
export interface ResearchRun {
  id: string
  title: string
  status: 'queued' | 'planning' | 'running' | 'done' | 'failed'
  createdAt: Date
  progress: number
}

// Research message types
export interface ResearchMessage {
  _id: string
  role: 'user' | 'assistant'
  kind: 'status' | 'query' | 'fetch' | 'reflect' | 'draft' | 'section' | 'complete' | 'error' | 'info'
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
    round?: number
    idx?: number
  }
}

// Research thread (not currently used but kept for future)
export interface ResearchThread {
  id: string
  projectId: string
  title: string
  status: 'queued' | 'planning' | 'running' | 'completed' | 'failed' | 'paused'
  progress: number
  messages: ResearchMessage[]
  createdAt: Date
  updatedAt: Date
  latestMessage?: string
}

// API request types
export interface StartRunRequest {
  topic: string
  maxParagraphs: number
  roundsPerParagraph: number
  searchProvider: string
}

// API response types
export interface CreateProjectResponse {
  project_id: string
}

export interface StartRunResponse {
  run_id: string
}

export interface GetRunsResponse {
  runs: Array<{
    id: string
    topic: string
    status: string
    createdAt: string
    progress: number
  }>
}

export interface GetReportResponse {
  markdown: string
}

// Component prop types
export interface ResearchChatProps {
  runId: string | null
  onRunStarted?: (runId: string) => void
  onRunCreated?: (run: ResearchRun) => void
  onStartNewChat?: () => void
  onExportReport?: () => void
}