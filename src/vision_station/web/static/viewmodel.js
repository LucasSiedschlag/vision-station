// Pure functions that turn what the system reports into what a screen shows. No DOM here, so node can test them.

export const ROLES = ['operator', 'supervisor', 'maintainer'];
export const ROLE_LABEL = { operator: 'Operador', supervisor: 'Supervisor', maintainer: 'Mantenedor' };

export function atLeast(role, needed) {
  return ROLES.indexOf(role) >= ROLES.indexOf(needed);
}

// What the big panel of the operator screen shows. Colour is never the only signal: every tone also has a word (NFR-USA-2).
export function operatorView(status, connected = true) {
  if (!connected || !status) {
    return { tone: 'off', headline: 'Sem conexão', sub: 'Aguardando o sistema…', result: null };
  }
  const result = status.last_result;
  switch (status.state) {
    case 'ShowingResult':
      if (result?.outcome === 'PASS') return { tone: 'pass', headline: 'APROVADO', sub: result.reason || '', result };
      if (result?.outcome === 'FAIL') return { tone: 'fail', headline: 'REPROVADO', sub: result.reason || '', result };
      return { tone: 'error', headline: 'ERRO', sub: result?.reason || 'Não foi possível inspecionar', result };
    case 'Inspecting':
      return { tone: 'busy', headline: 'Inspecionando…', sub: '', result: null };
    case 'CameraLost':
      return { tone: 'error', headline: 'Câmera desconectada', sub: 'Reconectando automaticamente', result: null };
    case 'Fault':
      return { tone: 'fault', headline: 'Falha na verificação', sub: status.detail || 'Chamar manutenção', result: null };
    case 'Paused':
      return { tone: 'warn', headline: 'Em manutenção', sub: '', result: null };
    case 'Starting':
    case 'Preparing':
      return { tone: 'busy', headline: 'Preparando…', sub: '', result: null };
    default:
      return { tone: 'wait', headline: status.message || 'Aguardando objeto', sub: '', result: null };
  }
}

export function canTrigger(status) {
  return !!status && (status.state === 'Ready' || status.state === 'WaitingStill');
}

// Applies one message from the live socket to the status the screen holds.
export function applyMessage(status, msg) {
  if (msg.type === 'status') {
    const { type, ...rest } = msg;
    return rest;
  }
  if (!status) return status;
  if (msg.type === 'state') {
    return { ...status, state: msg.state, message: msg.message };
  }
  if (msg.type === 'result') {
    const counters = { ...status.counters };
    counters[msg.outcome] = (counters[msg.outcome] || 0) + 1;
    counters.total = (counters.total || 0) + 1;
    return {
      ...status,
      counters,
      last_result: { outcome: msg.outcome, reason: msg.reason, scores: msg.scores, duration_ms: msg.duration_ms },
      last_record_id: msg.record_id,
    };
  }
  return status;
}

export function warningsOf(status) {
  if (!status) return [];
  const out = [...(status.warnings || [])];
  if (status.recording_failures > 0) out.push(`Falha ao gravar ${status.recording_failures} resultado(s) no registro`);
  if (status.camera && !status.camera.connected) out.push('Câmera desconectada');
  return out;
}

export function percent(part, total) {
  return total ? Math.round((100 * part) / total) : 0;
}

export function formatClock(date) {
  return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

export function describeError(err) {
  if (!err) return '';
  const d = err.detail;
  if (typeof d === 'string') return d;
  if (d && typeof d === 'object') return d.message || (d.problems || []).join('; ') || JSON.stringify(d);
  return err.message || String(err);
}
