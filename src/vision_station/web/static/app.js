import { html, render, useState, useEffect, useRef } from './lib.js';
import { createStore, useStore } from './store.js';
import { session, connectLive, logout } from './api.js';
import { applyMessage, formatClock, ROLE_LABEL, atLeast } from './viewmodel.js';
import { Toasts, Badge, Button } from './ui.js';
import { Operator } from './views/operator.js';
import { LoginDialog } from './views/login.js';

// Screens, in the order of the menu. `min` is the role that sees it. Later screens are added here.
export const routes = [
  { path: '/', title: 'Operador', min: 'operator', component: Operator },
];

const route = createStore(location.hash.slice(1) || '/');
window.addEventListener('hashchange', () => route.set(location.hash.slice(1) || '/'));

function useLive() {
  const [status, setStatus] = useState(null);
  const [connected, setConnected] = useState(false);
  const [frame, setFrame] = useState(null);
  const lastFrame = useRef(0);
  useEffect(() => {
    const stop = connectLive({
      onConnection: setConnected,
      onMessage: (msg) => setStatus((s) => applyMessage(s, msg)),
      onFrame: (blob) => { lastFrame.current = Date.now(); setFrame(blob); },
    });
    // no frame for 3 s: show "no image" instead of the last one
    const timer = setInterval(() => lastFrame.current && Date.now() - lastFrame.current > 3000 && setFrame(null), 1000);
    return () => { stop(); clearInterval(timer); };
  }, []);
  return { status, connected, frame };
}

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 15000); return () => clearInterval(t); }, []);
  return html`<span class="clock">${formatClock(now)}</span>`;
}

function Header({ status, connected, onLogin }) {
  const s = useStore(session);
  const current = useStore(route);
  const visible = routes.filter((r) => atLeast(s.role, r.min));
  return html`<header class="topbar">
    <div class="brand">Vision Station</div>
    <div class="jobinfo">${status?.job?.name ? html`<strong>${status.job.name}</strong> <span class="muted">v${status.job.version}</span>` : html`<span class="muted">Nenhum job</span>`}</div>
    ${visible.length > 1 ? html`<nav>${visible.map((r) => html`<a href=${`#${r.path}`} class=${current === r.path ? 'active' : ''}>${r.title}</a>`)}</nav>` : null}
    <div class="topbar-right">
      <${Badge} tone=${connected ? 'ok' : 'error'}>${connected ? 'Conectado' : 'Sem conexão'}<//>
      <${Clock} />
      ${s.role === 'operator'
        ? html`<${Button} onClick=${onLogin}>Entrar<//>`
        : html`<span class="muted">${ROLE_LABEL[s.role]}</span><${Button} onClick=${logout}>Sair<//>`}
    </div>
  </header>`;
}

function App() {
  const live = useLive();
  const s = useStore(session);
  const path = useStore(route);
  const [logging, setLogging] = useState(false);
  const current = routes.find((r) => r.path === path && atLeast(s.role, r.min)) || routes[0];
  const View = current.component;
  return html`<${Header} status=${live.status} connected=${live.connected} onLogin=${() => setLogging(true)} />
    <main><${View} ...${live} role=${s.role} /></main>
    ${logging ? html`<${LoginDialog} onClose=${() => setLogging(false)} />` : null}
    <${Toasts} />`;
}

render(html`<${App} />`, document.getElementById('app'));
