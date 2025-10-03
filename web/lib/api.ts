import { API_BASE } from './config'
import { 
  APIError, 
  validateTopic, 
  validateResearchParams, 
  retryWithBackoff,
  logError 
} from './errorUtils'
import type {
  StartRunRequest,
  CreateProjectResponse,
  StartRunResponse,
  GetRunsResponse,
  GetReportResponse
} from './types'

/**
 * Wrapper for fetch with error handling
 */
async function fetchWithError(
  url: string,
  options?: RequestInit
): Promise<Response> {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new APIError(
        response.status,
        errorData.message || `Request failed with status ${response.status}`,
        errorData
      )
    }

    return response
  } catch (error) {
    if (error instanceof APIError) {
      throw error
    }
    
    // Network or other errors
    logError('fetchWithError', error, { url, options })
    throw new APIError(
      0,
      'Network error. Please check your connection and try again.',
      error
    )
  }
}

/**
 * Creates a new research project
 */
export async function createProject(
  topic: string, 
  maxParagraphs: number = 5
): Promise<CreateProjectResponse> {
  try {
    validateTopic(topic)

    const response = await retryWithBackoff(() =>
      fetchWithError(`${API_BASE}/projects`, {
        method: 'POST',
        body: JSON.stringify({ 
          title: topic,
          goal: "",
          maxParagraphs: maxParagraphs
        }),
      })
    )

    const data = await response.json()
    console.log('CREATE PROJECT RESPONSE:', data)  // ADD THIS
    console.log('PROJECT ID:', data.project_id)     // ADD THIS
    return data
  } catch (error) {
    logError('createProject', error, { topic, maxParagraphs })
    throw error
  }
}

/**
 * Starts a new research run
 */
export async function startRun(
  projectId: string,
  rounds: number = 2,
  searchProvider: string = 'hybrid',
  resultsPerRound: number = 8,
  keepPerParagraph: number = 6
): Promise<StartRunResponse> {
  try {
    if (rounds < 1 || rounds > 5) {
      throw new APIError(400, 'Rounds must be between 1 and 5')
    }

    const response = await retryWithBackoff(() =>
      fetchWithError(`${API_BASE}/projects/${projectId}/runs`, {
        method: 'POST',
        body: JSON.stringify({
          rounds: rounds,
          resultsPerRound: resultsPerRound,
          keepPerParagraph: keepPerParagraph,
          searchProvider: searchProvider
        }),
      })
    )

    const data = await response.json()
    console.log('🔍 START RUN RESPONSE:', data)  // ADD THIS
    console.log('🔍 RUN ID:', data.run_id)       // ADD THIS
    return data
  } catch (error) {
    logError('startRun', error, { projectId, rounds, searchProvider })
    throw error
  }
}

/**
 * Gets recent research runs
 */
export async function getRecentRuns(limit: number = 20): Promise<GetRunsResponse['runs']> {
  try {
    const response = await fetchWithError(`${API_BASE}/runs?limit=${limit}`)
    const data: GetRunsResponse = await response.json()
    return data.runs || []
  } catch (error) {
    logError('getRecentRuns', error, { limit })
    // Return empty array on error to allow graceful degradation
    return []
  }
}

/**
 * Gets a specific run by ID
 */
export async function getRun(runId: string): Promise<StartRunResponse> {
  try {
    const response = await fetchWithError(`${API_BASE}/runs/${runId}`)
    return await response.json()
  } catch (error) {
    logError('getRun', error, { runId })
    throw error
  }
}

/**
 * Gets the report for a completed run
 */
export async function getReport(runId: string): Promise<GetReportResponse> {
  try {
    const response = await retryWithBackoff(() =>
      fetchWithError(`${API_BASE}/runs/${runId}/report`)
    )
    return await response.json()
  } catch (error) {
    logError('getReport', error, { runId })
    throw error
  }
}

/**
 * Deletes a research run
 */
export async function deleteRun(runId: string): Promise<void> {
  try {
    await fetchWithError(`${API_BASE}/runs/${runId}`, {
      method: 'DELETE',
    })
  } catch (error) {
    logError('deleteRun', error, { runId })
    throw error
  }
}

/**
 * Cancels an in-progress run
 */
export async function cancelRun(runId: string): Promise<void> {
  try {
    await fetchWithError(`${API_BASE}/runs/${runId}/cancel`, {
      method: 'POST',
    })
  } catch (error) {
    logError('cancelRun', error, { runId })
    throw error
  }
}

/**
 * Health check endpoint
 */
export async function healthCheck(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'GET',
    })
    return response.ok
  } catch (error) {
    logError('healthCheck', error)
    return false
  }
}