import type { OutlineItemData } from "@/components/outline-item"
import type { Source } from "@/components/sources-table"
import type { Note } from "@/components/notes-log"
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

export async function getRunStatus(runId: string): Promise<RunDetails> {
  const response = await fetch(`${API_BASE}/runs/${runId}/status`)
  
  if (!response.ok) {
    throw new Error(`Failed to get run status: ${response.statusText}`)
  }
  
  const data = await response.json()
  
  // Transform the backend response to match frontend interface
  return {
    id: data.id || runId,
    topic: data.topic || "Research Topic",
    status: data.status || "running",
    progress: data.progress || 0,
    outline: data.outline || [],
    sources: data.sources || [],
    notes: data.notes || [],
    draft: data.draft || "",
  }
}

export async function streamOutline(runId: string): Promise<OutlineItemData[]> {
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

export async function getReport(runId: string): Promise<{ content: string; sources: Source[] }> {
  const response = await fetch(`${API_BASE}/runs/${runId}/report`)
  
  if (!response.ok) {
    throw new Error(`Failed to get report: ${response.statusText}`)
  }
  
  const data = await response.json()
  return {
    content: data.content || "# Research Report\n\nContent here...",
    sources: data.sources || [],
  }
}
