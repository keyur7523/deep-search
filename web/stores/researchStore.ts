import { create } from 'zustand'
import type { Run, Source, OutlineItem } from '@/lib/types'

type ResearchStatus = 'idle' | 'starting' | 'researching' | 'writing' | 'completed' | 'error' | 'cancelled'

interface ResearchState {
  // Current research run
  currentRunId: string | null
  status: ResearchStatus
  progress: number

  // Research data
  sources: Source[]
  outline: OutlineItem[]
  report: string

  // Agent events for live updates
  agentEvents: AgentEvent[]
  currentAgent: string | null
  currentTask: string | null

  // Error handling
  error: string | null

  // Actions
  setCurrentRunId: (id: string | null) => void
  setStatus: (status: ResearchStatus) => void
  setProgress: (progress: number) => void

  setSources: (sources: Source[]) => void
  addSource: (source: Source) => void
  updateSource: (id: string, updates: Partial<Source>) => void

  setOutline: (outline: OutlineItem[]) => void
  addOutlineItem: (item: OutlineItem) => void
  updateOutlineItem: (id: string, updates: Partial<OutlineItem>) => void

  setReport: (report: string) => void
  appendToReport: (text: string) => void

  addAgentEvent: (event: AgentEvent) => void
  setCurrentAgent: (agent: string | null) => void
  setCurrentTask: (task: string | null) => void

  setError: (error: string | null) => void

  // Reset
  reset: () => void
}

export interface AgentEvent {
  id: string
  timestamp: Date
  type: 'search' | 'extract' | 'analyze' | 'write' | 'error' | 'info'
  agent: string
  message: string
  data?: Record<string, unknown>
}

const initialState = {
  currentRunId: null,
  status: 'idle' as ResearchStatus,
  progress: 0,
  sources: [],
  outline: [],
  report: '',
  agentEvents: [],
  currentAgent: null,
  currentTask: null,
  error: null,
}

export const useResearchStore = create<ResearchState>()((set) => ({
  ...initialState,

  // Run management
  setCurrentRunId: (id) => set({ currentRunId: id }),
  setStatus: (status) => set({ status }),
  setProgress: (progress) => set({ progress: Math.max(0, Math.min(100, progress)) }),

  // Sources management
  setSources: (sources) => set({ sources }),
  addSource: (source) => set((state) => ({
    sources: [...state.sources, source]
  })),
  updateSource: (id, updates) => set((state) => ({
    sources: state.sources.map((s) =>
      s.id === id ? { ...s, ...updates } : s
    )
  })),

  // Outline management
  setOutline: (outline) => set({ outline }),
  addOutlineItem: (item) => set((state) => ({
    outline: [...state.outline, item]
  })),
  updateOutlineItem: (id, updates) => set((state) => ({
    outline: state.outline.map((o) =>
      o.id === id ? { ...o, ...updates } : o
    )
  })),

  // Report management
  setReport: (report) => set({ report }),
  appendToReport: (text) => set((state) => ({
    report: state.report + text
  })),

  // Agent events
  addAgentEvent: (event) => set((state) => ({
    agentEvents: [...state.agentEvents.slice(-99), event] // Keep last 100 events
  })),
  setCurrentAgent: (agent) => set({ currentAgent: agent }),
  setCurrentTask: (task) => set({ currentTask: task }),

  // Error handling
  setError: (error) => set({ error }),

  // Reset to initial state
  reset: () => set(initialState),
}))
