/**
 * Error handling utilities for the Deep Research application
 */

export class APIError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public details?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

export class ValidationError extends Error {
  constructor(message: string, public field?: string) {
    super(message)
    this.name = 'ValidationError'
  }
}

/**
 * Handles API errors and returns user-friendly messages
 */
export function handleAPIError(error: unknown): string {
  if (error instanceof APIError) {
    switch (error.statusCode) {
      case 400:
        return 'Invalid request. Please check your input and try again.'
      case 401:
        return 'Authentication required. Please log in again.'
      case 403:
        return 'You do not have permission to perform this action.'
      case 404:
        return 'The requested resource was not found.'
      case 429:
        return 'Too many requests. Please wait a moment and try again.'
      case 500:
        return 'Server error. Please try again later.'
      case 503:
        return 'Service temporarily unavailable. Please try again later.'
      default:
        return error.message || 'An unexpected error occurred.'
    }
  }

  if (error instanceof ValidationError) {
    return error.message
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'An unexpected error occurred. Please try again.'
}

/**
 * Validates research topic input
 */
export function validateTopic(topic: string, minLength: number = 10): void {
  if (!topic || topic.trim().length === 0) {
    throw new ValidationError('Topic cannot be empty', 'topic')
  }

  if (topic.trim().length < minLength) {
    throw new ValidationError(
      `Topic must be at least ${minLength} characters long`,
      'topic'
    )
  }

  if (topic.length > 500) {
    throw new ValidationError(
      'Topic cannot exceed 500 characters',
      'topic'
    )
  }
}

/**
 * Validates research parameters
 */
export function validateResearchParams(
  sections: number,
  depth: number
): void {
  if (sections < 3 || sections > 8) {
    throw new ValidationError(
      'Sections must be between 3 and 8',
      'sections'
    )
  }

  if (depth < 1 || depth > 5) {
    throw new ValidationError(
      'Depth must be between 1 and 5',
      'depth'
    )
  }
}

/**
 * Wraps async functions with error handling
 */
export async function withErrorHandling<T>(
  fn: () => Promise<T>,
  errorMessage?: string
): Promise<{ data?: T; error?: string }> {
  try {
    const data = await fn()
    return { data }
  } catch (error) {
    console.error('Error in withErrorHandling:', error)
    return {
      error: errorMessage || handleAPIError(error)
    }
  }
}

/**
 * Retry logic with exponential backoff
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: Error

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))
      
      // Don't retry on client errors (4xx)
      if (error instanceof APIError && error.statusCode >= 400 && error.statusCode < 500) {
        throw error
      }

      if (i < maxRetries - 1) {
        const delay = baseDelay * Math.pow(2, i)
        await new Promise(resolve => setTimeout(resolve, delay))
      }
    }
  }

  throw lastError!
}

/**
 * Formats error messages for display
 */
export function formatErrorMessage(error: unknown): string {
  const message = handleAPIError(error)
  
  // Add helpful context based on error type
  if (message.includes('network') || message.includes('fetch')) {
    return `${message} Please check your internet connection.`
  }

  if (message.includes('timeout')) {
    return `${message} The server took too long to respond.`
  }

  return message
}

/**
 * Checks if an error is retryable
 */
export function isRetryableError(error: unknown): boolean {
  if (error instanceof APIError) {
    // Retry on server errors and rate limiting
    return error.statusCode >= 500 || error.statusCode === 429
  }

  if (error instanceof Error) {
    // Retry on network errors
    return (
      error.message.includes('network') ||
      error.message.includes('timeout') ||
      error.message.includes('fetch')
    )
  }

  return false
}

/**
 * Logs errors to console with context
 */
export function logError(
  context: string,
  error: unknown,
  additionalInfo?: Record<string, any>
): void {
  console.error(`[${context}] Error:`, {
    error: error instanceof Error ? {
      name: error.name,
      message: error.message,
      stack: error.stack
    } : error,
    ...additionalInfo,
    timestamp: new Date().toISOString()
  })
}