// Talking to the station's API: requests with the login token, and the live socket.
import { createStore } from './store.js';

const KEY = 'vision-station-session';

function loadSession() {
  try {
    const s = JSON.parse(sessionStorage.getItem(KEY) || 'null');
    if (s && s.expires > Date.now()) return s;
  } catch (e) { /* no storage: the session just lasts until reload */ }
  return { token: null, role: 'operator', expires: 0 };
}

// role is only what the screen shows; the server decides what is allowed
export const session = createStore(loadSession());

function saveSession(s) {
  session.set(s);
  try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* ignore */ }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function request(method, path, body, { raw = false } = {}) {
  const headers = {};
  const { token } = session.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (body instanceof Blob || body instanceof ArrayBuffer) {
    payload = body;
    headers['Content-Type'] = 'application/octet-stream';
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, { method, headers, body: payload });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch (e) { /* not JSON */ }
    if (res.status === 401 && token) saveSession({ token: null, role: 'operator', expires: 0 }); // expired or revoked
    throw new ApiError(res.status, detail);
  }
  if (raw) return res;
  const type = res.headers.get('content-type') || '';
  return type.includes('application/json') ? res.json() : res;
}

export const get = (path) => request('GET', path);
export const post = (path, body) => request('POST', path, body ?? {});

export async function login(role, password) {
  const r = await post('/login', { role, password });
  saveSession({ token: r.token, role: r.role, expires: Date.now() + r.expires_in_s * 1000 });
  return r.role;
}

export async function logout() {
  try { await post('/logout'); } catch (e) { /* already out */ }
  saveSession({ token: null, role: 'operator', expires: 0 });
}

// The live socket: status and events as JSON text, camera frames as JPEG bytes. Reconnects by itself.
export function connectLive({ onMessage, onFrame, onConnection }) {
  let ws = null;
  let closed = false;
  let delay = 500;
  const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/live`;

  function open() {
    ws = new WebSocket(url);
    ws.binaryType = 'blob';
    ws.onopen = () => { delay = 500; onConnection(true); };
    ws.onmessage = (e) => {
      if (typeof e.data === 'string') onMessage(JSON.parse(e.data));
      else onFrame(e.data);
    };
    ws.onclose = () => {
      onConnection(false);
      if (!closed) setTimeout(open, delay = Math.min(delay * 2, 5000));
    };
    ws.onerror = () => ws.close();
  }
  open();
  return () => { closed = true; ws && ws.close(); };
}
