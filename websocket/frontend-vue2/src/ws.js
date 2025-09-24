export function connectWS(url, { onOpen, onMessage, onClose, onError } = {}) {
  const ws = new WebSocket(url);
  ws.onopen = () => onOpen && onOpen();
  ws.onmessage = ev => {
    try { onMessage && onMessage(JSON.parse(ev.data)); }
    catch (e) { console.error("WS parse error", e, ev.data); }
  };
  ws.onclose = () => onClose && onClose();
  ws.onerror = (e) => onError && onError(e);
  return ws;
}
