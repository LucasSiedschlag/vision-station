import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { StateOut } from '@/api/live'
import { verdictOf } from '@/features/operator/view'
import { stateFixture } from '@/test/render'
import { indicators, StatusStrip } from './StatusStrip'
import { VerdictPanel } from './VerdictPanel'

const status = (over: Record<string, unknown> = {}) => stateFixture(over) as StateOut

describe('VerdictPanel', () => {
  it('is a live region that announces the word and the reason together', () => {
    const verdict = verdictOf(
      status({
        state: 'ShowingResult',
        last_result: {
          outcome: 'FAIL',
          reason: 'Fita ausente em 40% da emenda',
          scores: {},
          duration_ms: 290,
          at: null,
        },
      }),
      'connected',
    )
    render(<VerdictPanel verdict={verdict} />)
    const panel = screen.getByRole('status', { name: 'Resultado' })
    expect(panel).toHaveAttribute('aria-live', 'assertive')
    expect(panel).toHaveTextContent('REPROVADO')
    expect(panel).toHaveTextContent('Fita ausente em 40% da emenda')
    expect(panel.querySelector('svg')).toHaveAttribute('aria-hidden', 'true') // the icon is decoration; the word carries the meaning
  })

  it.each([
    ['ok', 'APROVADO', 'border-ok'],
    ['fail', 'REPROVADO', 'border-fail'],
    ['warn', 'ERRO', 'border-warn'],
  ] as const)('a %s result is the status colour plus the word %s', (_tone, word, edge) => {
    const outcome = { ok: 'PASS', fail: 'FAIL', warn: 'ERROR' }[_tone]
    render(
      <VerdictPanel
        verdict={verdictOf(
          status({
            state: 'ShowingResult',
            last_result: { outcome, reason: '', scores: {}, duration_ms: 1, at: null },
          }),
          'connected',
        )}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent(word)
    expect(screen.getByRole('status').className).toContain(edge)
  })

  it('without a connection it shows the old result only as old', () => {
    const shown = status({
      state: 'ShowingResult',
      last_result: { outcome: 'PASS', reason: '', scores: {}, duration_ms: 1, at: null },
    })
    render(<VerdictPanel verdict={verdictOf(shown, 'offline')} />)
    const panel = screen.getByRole('status')
    expect(panel).toHaveTextContent('Sem conexão')
    expect(panel.querySelector('p')).toHaveTextContent('Sem conexão') // the headline is the lost connection, not the old verdict
    expect(panel).toHaveTextContent('Pode estar desatualizado')
  })
})

describe('StatusStrip', () => {
  it('names three indicators, each with a word', () => {
    render(<StatusStrip status={status()} connection="connected" />)
    expect(screen.getByRole('button', { name: 'Sistema: conectado' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Câmera: ok' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Registro: ok' })).toBeInTheDocument()
  })

  it('a camera that is gone and a log that fails are failures, in words', () => {
    const items = indicators(
      status({
        camera: {
          connected: false,
          last_frame_age_s: null,
          last_error: 'CameraError: usb disconnected',
        },
        recording_failures: 2,
      }),
      'connected',
    )
    expect(items.map((i) => [i.id, i.tone, i.word])).toEqual([
      ['system', 'ok', 'conectado'],
      ['camera', 'fail', 'desconectada'],
      ['log', 'fail', 'com falhas'],
    ])
    expect(items[1]?.detail).toEqual(['CameraError: usb disconnected'])
    expect(items[2]?.detail).toEqual(['2 resultados não gravados'])
  })

  it('what it cannot know it shows as unknown, never as fine', () => {
    for (const connection of ['offline', 'connecting'] as const) {
      const items = indicators(status(), connection)
      expect(items[1]?.tone).toBe('unknown')
      expect(items[2]?.tone).toBe('unknown')
    }
    expect(indicators(null, 'connected')[1]?.tone).toBe('unknown')
    expect(indicators(status(), 'offline')[0]).toMatchObject({ tone: 'fail', word: 'sem conexão' })
    expect(indicators(null, 'connecting')[0]).toMatchObject({ tone: 'busy', word: 'conectando' })
  })
})
