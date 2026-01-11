"use client"

import React, { Component, ErrorInfo, ReactNode } from "react"
import { AlertCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mb-4">
            <AlertCircle className="w-8 h-8 text-red-600" />
          </div>
          <h2 className="text-xl font-semibold text-foreground mb-2">
            Something went wrong
          </h2>
          <p className="text-muted-foreground mb-4 max-w-md">
            An unexpected error occurred. Please try refreshing the page or click the button below.
          </p>
          {this.state.error && (
            <details className="mb-4 text-sm text-muted-foreground max-w-md">
              <summary className="cursor-pointer hover:text-foreground">
                Error details
              </summary>
              <pre className="mt-2 p-2 bg-muted rounded text-left overflow-auto text-xs">
                {this.state.error.message}
              </pre>
            </details>
          )}
          <Button onClick={this.handleReset} variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Try again
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
