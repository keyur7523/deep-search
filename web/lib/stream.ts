export type ResearchMsg = {
  _id: string; 
  runId: string; 
  t: string; 
  role: "system"|"user"|"assistant";
  kind: "status"|"query"|"fetch"|"reflect"|"draft"|"section"|"complete"|"error"|"info";
  text: string; 
  meta?: any;
};

export function openRunEvents(apiBase: string, runId: string, onMsg: (m:ResearchMsg)=>void) {
  const url = `${apiBase.replace(/\/+$/,"")}/runs/${runId}/events/stream`;
  const es = new EventSource(url);
  es.onmessage = (ev) => { 
    try { 
      onMsg(JSON.parse(ev.data)); 
    } catch {} 
  };
  es.onerror = () => { 
    /* auto-reconnect by browser */ 
  };
  return () => es.close();
}
