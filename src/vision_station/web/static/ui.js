// Shared pieces: buttons, badges, dialogs, toasts. Kept small on purpose; each screen builds on these.
import { html, useState, useEffect } from './lib.js';
import { createStore } from './store.js';
import { useStore } from './store.js';

export const toasts = createStore([]);
let nextToast = 1;

export function toast(message, tone = 'info', ms = 5000) {
  const id = nextToast++;
  toasts.set((list) => [...list, { id, message, tone }]);
  setTimeout(() => toasts.set((list) => list.filter((t) => t.id !== id)), ms);
}

export function Toasts() {
  const list = useStore(toasts);
  return html`<div class="toasts" aria-live="polite">
    ${list.map((t) => html`<div class=${`toast toast-${t.tone}`} key=${t.id}>${t.message}</div>`)}
  </div>`;
}

export function Button({ children, tone = 'default', big = false, busy = false, ...rest }) {
  return html`<button class=${`btn btn-${tone}${big ? ' btn-big' : ''}`} disabled=${busy || rest.disabled} ...${rest}>${busy ? '…' : children}</button>`;
}

export function Badge({ tone = 'default', children }) {
  return html`<span class=${`badge badge-${tone}`}>${children}</span>`;
}

export function Dialog({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return html`<div class="overlay" onClick=${(e) => e.target === e.currentTarget && onClose()}>
    <div class="dialog" role="dialog" aria-modal="true" aria-label=${title}>
      <h2>${title}</h2>
      ${children}
    </div>
  </div>`;
}

export function Field({ label, children, hint }) {
  return html`<label class="field"><span class="field-label">${label}</span>${children}${hint ? html`<span class="field-hint">${hint}</span>` : null}</label>`;
}

// Runs an async action and reports its error as a toast; gives back [run, busy].
export function useAction(fn, describe) {
  const [busy, setBusy] = useState(false);
  const run = async (...args) => {
    setBusy(true);
    try {
      return await fn(...args);
    } catch (e) {
      toast(describe ? describe(e) : e.message, 'error');
    } finally {
      setBusy(false);
    }
  };
  return [run, busy];
}
