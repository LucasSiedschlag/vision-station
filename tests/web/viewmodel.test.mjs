import test from 'node:test';
import assert from 'node:assert/strict';
import { operatorView, canTrigger, applyMessage, warningsOf, percent, atLeast, describeError } from '../../src/vision_station/web/static/viewmodel.js';

const status = (over = {}) => ({
  state: 'Ready', message: 'Aguardando objeto', detail: '', warnings: [], recording_failures: 0,
  job: { id: 'j', name: 'Caixa M', version: 7 }, last_result: null,
  camera: { connected: true }, counters: { PASS: 0, FAIL: 0, ERROR: 0, total: 0 }, ...over,
});

test('every verdict has a word, not only a colour', () => {
  const pass = operatorView(status({ state: 'ShowingResult', last_result: { outcome: 'PASS', reason: '' } }));
  assert.deepEqual([pass.tone, pass.headline], ['pass', 'APROVADO']);
  const fail = operatorView(status({ state: 'ShowingResult', last_result: { outcome: 'FAIL', reason: 'Fita ausente em 40% da emenda' } }));
  assert.deepEqual([fail.tone, fail.headline, fail.sub], ['fail', 'REPROVADO', 'Fita ausente em 40% da emenda']);
  const error = operatorView(status({ state: 'ShowingResult', last_result: { outcome: 'ERROR', reason: 'Câmera desconectada durante a inspeção' } }));
  assert.deepEqual([error.tone, error.headline], ['error', 'ERRO']);
  const unknown = operatorView(status({ state: 'ShowingResult', last_result: { outcome: 'WHATEVER' } }));
  assert.equal(unknown.tone, 'error'); // an unexpected outcome is never shown as a pass
});

test('the other states', () => {
  assert.equal(operatorView(status()).headline, 'Aguardando objeto');
  assert.equal(operatorView(status({ state: 'WaitingStill' })).tone, 'wait');
  assert.deepEqual([operatorView(status({ state: 'Inspecting' })).tone, operatorView(status({ state: 'Inspecting' })).headline], ['busy', 'Inspecionando…']);
  assert.equal(operatorView(status({ state: 'CameraLost' })).headline, 'Câmera desconectada');
  const fault = operatorView(status({ state: 'Fault', detail: 'ajuste não aplicado: exposure' }));
  assert.deepEqual([fault.tone, fault.sub], ['fault', 'ajuste não aplicado: exposure']);
  assert.equal(operatorView(status({ state: 'Paused' })).headline, 'Em manutenção');
  assert.equal(operatorView(status({ state: 'Preparing' })).headline, 'Preparando…');
  assert.equal(operatorView(status({ message: 'Aguardando etiqueta' })).headline, 'Aguardando etiqueta'); // text from the job
});

test('no connection or no status shows that, never a stale verdict', () => {
  assert.equal(operatorView(null, true).tone, 'off');
  assert.equal(operatorView(status({ state: 'ShowingResult', last_result: { outcome: 'PASS' } }), false).tone, 'off');
});

test('trigger only when the station is ready', () => {
  assert.equal(canTrigger(status()), true);
  assert.equal(canTrigger(status({ state: 'WaitingStill' })), true);
  for (const state of ['Inspecting', 'ShowingResult', 'Fault', 'Paused', 'CameraLost', 'Preparing']) assert.equal(canTrigger(status({ state })), false, state);
  assert.equal(canTrigger(null), false);
});

test('messages from the live socket update the status', () => {
  let s = applyMessage(null, { type: 'state', state: 'Ready' });
  assert.equal(s, null); // nothing to update before the first status
  s = applyMessage(null, { type: 'status', ...status() });
  assert.equal(s.state, 'Ready');
  assert.equal(s.type, undefined);
  s = applyMessage(s, { type: 'state', state: 'Inspecting', message: 'Inspecionando…' });
  assert.deepEqual([s.state, s.message], ['Inspecting', 'Inspecionando…']);
  s = applyMessage(s, { type: 'result', outcome: 'FAIL', reason: 'x', scores: { t: 0.5 }, duration_ms: 120, record_id: 'r1' });
  assert.deepEqual(s.counters, { PASS: 0, FAIL: 1, ERROR: 0, total: 1 });
  assert.deepEqual([s.last_result.outcome, s.last_record_id], ['FAIL', 'r1']);
  const again = applyMessage(s, { type: 'result', outcome: 'PASS', reason: '', scores: {}, duration_ms: 90, record_id: 'r2' });
  assert.deepEqual(again.counters, { PASS: 1, FAIL: 1, ERROR: 0, total: 2 });
  assert.equal(s.counters.total, 1); // the old status was not changed
  const refreshed = applyMessage(again, { type: 'status', ...status({ counters: { PASS: 5, FAIL: 1, ERROR: 0, total: 6 } }) });
  assert.equal(refreshed.counters.total, 6); // the heartbeat has the truth
});

test('warnings come from the job, the recorder and the camera', () => {
  assert.deepEqual(warningsOf(null), []);
  const w = warningsOf(status({ warnings: ['zoom: não suportado'], recording_failures: 2, camera: { connected: false } }));
  assert.equal(w.length, 3);
  assert.ok(w.some((x) => x.includes('2 resultado')));
});

test('small helpers', () => {
  assert.equal(percent(1, 4), 25);
  assert.equal(percent(1, 0), 0);
  assert.equal(atLeast('maintainer', 'supervisor'), true);
  assert.equal(atLeast('operator', 'supervisor'), false);
  assert.equal(describeError({ detail: 'texto' }), 'texto');
  assert.equal(describeError({ detail: { problems: ['a', 'b'] } }), 'a; b');
  assert.equal(describeError({ detail: { message: 'm' } }), 'm');
  assert.equal(describeError(new Error('boom')), 'boom');
});
