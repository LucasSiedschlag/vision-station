// The operator screen: readable from 2 m, colour and words together, nothing to learn (NFR-USA-1/2, FR-UI-1..5).
import { html, useState, useEffect, useRef } from '../lib.js';
import { Button, Dialog, Badge, toast, useAction } from '../ui.js';
import { post } from '../api.js';
import { operatorView, canTrigger, warningsOf, percent, describeError } from '../viewmodel.js';

function LiveCanvas({ frame, tone }) {
  const canvas = useRef(null);
  const bitmap = useRef(null);

  const draw = () => {
    const c = canvas.current;
    if (!c || !bitmap.current) return;
    const { width, height } = c.getBoundingClientRect();
    if (c.width !== Math.round(width) || c.height !== Math.round(height)) {
      c.width = Math.round(width);
      c.height = Math.round(height);
    }
    const ctx = c.getContext('2d');
    const bmp = bitmap.current;
    const scale = Math.min(c.width / bmp.width, c.height / bmp.height);
    const w = bmp.width * scale;
    const h = bmp.height * scale;
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(bmp, (c.width - w) / 2, (c.height - h) / 2, w, h);
  };

  useEffect(() => {
    if (!frame) return;
    let live = true;
    createImageBitmap(frame).then((bmp) => {
      if (!live) return bmp.close();
      bitmap.current?.close();
      bitmap.current = bmp;
      draw();
    }).catch(() => {});
    return () => { live = false; };
  }, [frame]);

  useEffect(() => {
    window.addEventListener('resize', draw);
    return () => window.removeEventListener('resize', draw);
  }, []);

  return html`<div class=${`live live-${tone}`}>
    <canvas ref=${canvas} aria-label="Imagem ao vivo da câmera"></canvas>
    ${frame ? null : html`<div class="live-empty">Sem imagem da câmera</div>`}
  </div>`;
}

function Counters({ counters = {} }) {
  const total = counters.total || 0;
  const cell = (label, value, tone) => html`<div class=${`counter counter-${tone}`}>
    <div class="counter-value">${value ?? 0}</div>
    <div class="counter-label">${label}</div>
    ${tone !== 'total' && total ? html`<div class="counter-pct">${percent(value, total)}%</div>` : null}
  </div>`;
  return html`<div class="counters" aria-label="Contadores do turno">
    ${cell('Total', total, 'total')}${cell('Aprovadas', counters.PASS, 'pass')}${cell('Reprovadas', counters.FAIL, 'fail')}${cell('Erros', counters.ERROR, 'error')}
  </div>`;
}

function IncorrectDialog({ recordId, outcome, onClose }) {
  const [send, busy] = useAction(async (correct) => {
    await post(`/results/${recordId}/incorrect`, { correct, by: 'operador' });
    toast('Marcado como incorreto. A imagem vai para o treinamento.', 'ok');
    onClose();
  }, describeError);
  return html`<${Dialog} title="Este resultado estava errado?" onClose=${onClose}>
    <p>O sistema disse <strong>${outcome === 'PASS' ? 'APROVADO' : outcome === 'FAIL' ? 'REPROVADO' : 'ERRO'}</strong>. Qual era o resultado certo?</p>
    <div class="dialog-actions dialog-actions-big">
      <${Button} tone="pass" big busy=${busy} onClick=${() => send('PASS')}>Estava OK<//>
      <${Button} tone="fail" big busy=${busy} onClick=${() => send('FAIL')}>Estava NÃO OK<//>
    </div>
    <div class="dialog-actions"><${Button} onClick=${onClose}>Cancelar<//></div>
  <//>`;
}

export function Operator({ status, connected, frame }) {
  const view = operatorView(status, connected);
  const warnings = warningsOf(status);
  const [asking, setAsking] = useState(false);
  const [trigger, triggering] = useAction(() => post('/trigger'), describeError);
  const recordId = status?.last_record_id;

  return html`<div class="operator">
    <section class="operator-live"><${LiveCanvas} frame=${frame} tone=${view.tone} /></section>
    <aside class="operator-side">
      <div class=${`verdict verdict-${view.tone}`} role="status" aria-live="assertive">
        <div class="verdict-headline">${view.headline}</div>
        ${view.sub ? html`<div class="verdict-sub">${view.sub}</div>` : null}
      </div>
      ${view.result && recordId
        ? html`<${Button} big onClick=${() => setAsking(true)}>Resultado incorreto?<//>`
        : null}
      <${Button} tone="primary" big busy=${triggering} disabled=${!canTrigger(status)} onClick=${() => trigger()}>Inspecionar agora<//>
      <${Counters} counters=${status?.counters} />
      ${warnings.length
        ? html`<ul class="warnings">${warnings.map((w) => html`<li><${Badge} tone="warn">Aviso<//> ${w}</li>`)}</ul>`
        : null}
    </aside>
    ${asking ? html`<${IncorrectDialog} recordId=${recordId} outcome=${view.result?.outcome} onClose=${() => setAsking(false)} />` : null}
  </div>`;
}
