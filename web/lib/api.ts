import type { OutlineItemData } from "@/components/outline-item"
import type { Source } from "@/components/sources-table"
import type { Note } from "@/components/notes-log"
import type { ResearchThread, ResearchMessage, NewResearchRequest } from "@/lib/types"
import { API_BASE } from "@/lib/config"

export interface Project {
  id: string
  name: string
  createdAt: Date
}

export interface Run {
  id: string
  projectId: string
  topic: string
  status: "running" | "completed" | "failed"
  progress: number
  createdAt: Date
}

export interface RunDetails {
  id: string
  topic: string
  status: "running" | "completed" | "failed"
  progress: number
  outline: OutlineItemData[]
  sources: Source[]
  notes: Note[]
  draft: string
}

// Real API functions using API_BASE
export async function createProject(name: string): Promise<Project> {
  const response = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      title: name,
      goal: '',
    }),
  })
  
  if (!response.ok) {
    throw new Error(`Failed to create project: ${response.statusText}`)
  }
  
  const data = await response.json()
  return {
    id: data.project_id,
    name,
    createdAt: new Date(),
  }
}

export async function startRun(data: {
  topic: string
  maxParagraphs: number
  roundsPerParagraph: number
  searchProvider?: string
}): Promise<Run> {
  // First create a project for this run
  const project = await createProject(data.topic)
  
  // Then create a run for the project
  const response = await fetch(`${API_BASE}/projects/${project.id}/runs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      rounds: data.roundsPerParagraph,
      resultsPerRound: 8,
      keepPerParagraph: data.maxParagraphs,
      searchProvider: data.searchProvider || "hybrid",
    }),
  })
  
  if (!response.ok) {
    throw new Error(`Failed to start run: ${response.statusText}`)
  }
  
  const runData = await response.json()
  return {
    id: runData.run_id,
    projectId: project.id,
    topic: data.topic,
    status: "running",
    progress: 0,
    createdAt: new Date(),
  }
}

export async function getRunStatus(runId: string): Promise<{status: string, progress: number}> {
  const response = await fetch(`${API_BASE}/runs/${runId}/status`)
  
  if (!response.ok) {
    throw new Error(`Failed to get run status: ${response.statusText}`)
  }
  
  return await response.json()
}

export async function getOutline(runId: string): Promise<OutlineItemData[]> {
  const response = await fetch(`${API_BASE}/runs/${runId}/outline`)
  
  if (!response.ok) {
    throw new Error(`Failed to get outline: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.items || []
}

export async function listSources(runId: string): Promise<Source[]> {
  const response = await fetch(`${API_BASE}/runs/${runId}/status`)
  
  if (!response.ok) {
    throw new Error(`Failed to get sources: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.sources || []
}

export async function getReport(runId: string): Promise<{ markdown: string }> {
  const response = await fetch(`${API_BASE}/runs/${runId}/report`)
  
  if (!response.ok) {
    throw new Error(`Failed to get report: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data
}

export async function getParagraphs(runId: string): Promise<Array<{draftMd: string, idx: number, quality: number, citations: Record<string, any>}>> {
  const response = await fetch(`${API_BASE}/runs/${runId}/paragraphs`)
  
  if (!response.ok) {
    throw new Error(`Failed to get paragraphs: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.paragraphs || []
}

export async function getRecentRuns(limit: number = 5): Promise<RunDetails[]> {
  const response = await fetch(`${API_BASE}/runs?limit=${limit}`)
  
  if (!response.ok) {
    throw new Error(`Failed to get recent runs: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.runs || []
}

// New Research Thread API functions
export async function getResearchThreads(limit: number = 20): Promise<ResearchThread[]> {
  const response = await fetch(`${API_BASE}/research/threads?limit=${limit}`)
  
  if (!response.ok) {
    throw new Error(`Failed to get research threads: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.threads || []
}

export async function getResearchThread(threadId: string): Promise<ResearchThread> {
  const response = await fetch(`${API_BASE}/research/threads/${threadId}`)
  
  if (!response.ok) {
    throw new Error(`Failed to get research thread: ${response.statusText}`)
  }
  
  return await response.json()
}

export async function getResearchMessages(threadId: string, limit: number = 50): Promise<ResearchMessage[]> {
  const response = await fetch(`${API_BASE}/research/threads/${threadId}/messages?limit=${limit}`)
  
  if (!response.ok) {
    throw new Error(`Failed to get research messages: ${response.statusText}`)
  }
  
  const data = await response.json()
  return data.messages || []
}

export async function startNewResearch(data: NewResearchRequest): Promise<ResearchThread> {
  // First create a project
  const project = await createProject(data.topic)
  
  // Then create a run for the project
  const response = await fetch(`${API_BASE}/projects/${project.id}/runs`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      rounds: data.roundsPerParagraph,
      resultsPerRound: 8,
      keepPerParagraph: data.maxParagraphs,
      searchProvider: data.searchProvider || "hybrid",
    }),
  })
  
  if (!response.ok) {
    throw new Error(`Failed to start research: ${response.statusText}`)
  }
  
  const runData = await response.json()
  
  // Return the thread data
  return {
    id: runData.run_id,
    title: data.topic,
    status: "active",
    messages: [],
    createdAt: new Date(),
    updatedAt: new Date(),
    progress: 0,
    metadata: {
      maxParagraphs: data.maxParagraphs,
      roundsPerParagraph: data.roundsPerParagraph,
      searchProvider: data.searchProvider || "hybrid",
      totalSources: 0,
      qualityScore: 0
    }
  }
}
