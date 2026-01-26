// Research run types
export interface ResearchRun {
  id: string
  title: string
  status: 'queued' | 'planning' | 'running' | 'done' | 'failed'
  createdAt: Date
  progress: number
}

// Zustand store types (shared)
export interface Run {
  id: string
  title: string
  status: string
  createdAt: Date
  progress: number
}

export interface Source {
  id: string
  url: string
  title: string
  type?: 'academic' | 'web' | string
  authors?: string
  year?: string
  venue?: string
  citations?: number
  score?: number
  textLength?: number
  sectionTitle?: string
  sectionIdx?: number
}

export interface OutlineItem {
  id: string
  index: number
  title: string
  brief: string
  status: 'queued' | 'searching' | 'reflecting' | 'drafting' | 'done' | 'needs review'
  progress?: number
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

export type AgentMode = "simple" | "agentic" | "auto";

export type AgentTaskStatus = "pending" | "running" | "done" | "failed";

export interface AgentTask {
  id: string;
  type: string;
  status: AgentTaskStatus;
  parentId?: string;
  createdAt: string;
}

export interface AgentGraphNode {
  id: string;
  type: string;
  status: AgentTaskStatus;
  label: string;
}

export interface AgentGraphEdge {
  source: string;
  target: string;
}

export interface AgentGraph {
  nodes: AgentGraphNode[];
  edges: AgentGraphEdge[];
}

export interface AgentEvent {
  id: string;
  agent: string;
  kind: "thinking" | "action" | "result" | "error";
  text: string;
  meta: Record<string, any>;
  timestamp: string;
}

export interface RoutingExplanation {
  mode: AgentMode;
  score: number;
  threshold: number;
  factors: {
    topicLength: number;
    detectedDomains: string[];
    deepMode: boolean;
    minCitations: number;
    requireRecent: boolean;
  };
  reasoning: string;
}

export interface CreateRunResponse {
  run_id: string;
  mode: AgentMode;
  routing: RoutingExplanation;
}
