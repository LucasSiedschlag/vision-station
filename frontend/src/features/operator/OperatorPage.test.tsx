import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useLive } from '@/api/live'
import { OperatorPage } from './OperatorPage'

const status = {
  state: 'Ready' as const,
  message: 'Aguardando caixa',
  detail: '',
  warnings: [],
  job: { id: 'j', name: 'Caixa M — fita vermelha', version: 7 },
  last_result: null,
  last_record_id: null,
  camera: { connected: true, last_frame_age_s: 0.2, last_error: null },
  counters: { PASS: 2, FAIL: 1, ERROR: 0, total: 3 },
  recording_failures: 0,
  version: '0.1.0',
}

describe('OperatorPage (skeleton)', () => {
  beforeEach(() =>
    useLive.setState({ status: null, frame: null, connected: false, connecting: true }),
  )

  it('says it is connecting before the first status, and shows no verdict', () => {
    render(<OperatorPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Conectando…')
    expect(screen.queryByText('Aguardando caixa')).not.toBeInTheDocument()
  })

  it('shows the job, the state and the counters from the live store', () => {
    useLive.setState({ status, connected: true, connecting: false })
    render(<OperatorPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Conectado')
    expect(screen.getByText('Caixa M — fita vermelha')).toBeInTheDocument()
    expect(screen.getByText('Aguardando caixa')).toBeInTheDocument()
    expect(screen.getByText('3 · 2 · 1 · 0')).toBeInTheDocument()
  })

  it('says offline when the socket is down', () => {
    useLive.setState({ status, connected: false, connecting: false })
    render(<OperatorPage />)
    expect(screen.getByRole('status')).toHaveTextContent('Sem conexão')
  })
})
