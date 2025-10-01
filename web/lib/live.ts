export type LiveMsg = { runId:string; kind:string; msg:string; ts:string; meta?:any };

export function openLiveStream(apiBase: string, runId: string, onMsg: (m: LiveMsg) => void) {
  const url = `${apiBase.replace(/\/+$/,"")}/runs/${runId}/live/stream`;
  const es = new EventSource(url);
  es.onmessage = (e) => { try { onMsg(JSON.parse(e.data)); } catch {} };
  es.onerror = () => { /* browser will auto-reconnect */ };
  return () => es.close();
}
