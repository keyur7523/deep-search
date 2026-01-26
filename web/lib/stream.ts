export type ResearchMsg = {
  _id: string; 
  runId: string; 
  t: string; 
  role: "system"|"user"|"assistant";
  kind: "status"|"query"|"fetch"|"reflect"|"draft"|"section"|"complete"|"error"|"info";
  text: string; 
  meta?: any;
};

export function openRunEvents(apiBase: string, runId: string, onMsg: (m:ResearchMsg)=>void, onError?: (e: Event)=>void) {
  const url = `${apiBase.replace(/\/+$/,"")}/runs/${runId}/events/stream`;
  const es = new EventSource(url);

  // Track consecutive parse errors to detect persistent issues
  let parseErrorCount = 0;
  const MAX_PARSE_ERRORS = 5;

  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      parseErrorCount = 0; // Reset on successful parse

      // IMPORTANT: Call onMsg BEFORE closing to ensure data is processed
      onMsg(data);

      // Check for completion signal after processing the message
      if (data.done) {
        es.close();
      }
    } catch (e) {
      parseErrorCount++;
      console.error('[SSE] Failed to parse message:', e, 'Raw data:', ev.data?.substring(0, 100));

      // MEMORY LEAK FIX: Close connection after too many parse errors
      // This prevents infinite reconnection attempts with malformed data
      if (parseErrorCount >= MAX_PARSE_ERRORS) {
        console.error(`[SSE] Closing EventSource after ${MAX_PARSE_ERRORS} consecutive parse errors`);
        es.close();
        onError?.(new Event('parse-error'));
      }
    }
  };

  es.onerror = (e) => {
    console.error('[SSE] Connection error:', e);
    // Close on error to prevent memory leaks from infinite reconnects
    es.close();
    onError?.(e);
  };

  return () => es.close();
}
