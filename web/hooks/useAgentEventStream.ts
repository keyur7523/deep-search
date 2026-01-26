'use client'

import { useEffect, useRef } from 'react'
import { subscribeToAgentEvents } from '@/lib/api'
import { useResearchStore } from '@/stores'

export function useAgentEventStream(runId: string | null) {
  const addAgentEvent = useResearchStore((state) => state.addAgentEvent)
  const setStatus = useResearchStore((state) => state.setStatus)
  const streamRunIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!runId) return
    if (streamRunIdRef.current === runId) return
    streamRunIdRef.current = runId

    const unsubscribe = subscribeToAgentEvents(
      runId,
      (event) => {
        const mappedType = event.kind === 'error'
          ? 'error'
          : event.kind === 'action'
            ? 'search'
            : event.kind === 'result'
              ? 'write'
              : 'info'
        addAgentEvent({
          id: event.id,
          timestamp: new Date(event.timestamp),
          type: mappedType,
          agent: event.agent,
          message: event.text,
          data: event.meta,
        })
      },
      () => {
        setStatus('writing')
      },
      () => {
        setStatus('error')
      }
    )

    return () => {
      unsubscribe()
      streamRunIdRef.current = null
    }
  }, [runId, addAgentEvent, setStatus])
}
