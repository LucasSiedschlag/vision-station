import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Badge, StatusIndicator } from './badge'
import { Button } from './button'
import { ConfirmDialog, Dialog, DialogContent, DialogTrigger } from './dialog'
import { EmptyState, ErrorState } from './feedback'
import { Field } from './field'
import { FileDrop } from './file-drop'
import { Input } from './input'
import { SegmentedControl } from './segmented-control'
import { Select } from './select'
import { Stepper } from './stepper'
import { Switch } from './switch'

describe('Button', () => {
  it('is a button that does not submit forms unless asked', () => {
    render(<Button>Salvar</Button>)
    expect(screen.getByRole('button', { name: 'Salvar' })).toHaveAttribute('type', 'button')
  })

  it('keeps the density font size next to a text colour (the class merger must not drop one of them)', () => {
    render(<Button variant="primary">Entrar</Button>)
    const classes = screen.getByRole('button').className.split(' ')
    expect(classes).toContain('fs-control')
    expect(classes).toContain('text-on-accent')
  })

  it('while loading it is disabled, busy, and keeps its label so the width does not jump', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Salvar
      </Button>,
    )
    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveTextContent('Salvar')
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('StatusIndicator and Badge', () => {
  it('always carry a word, so a status is never only a colour', () => {
    render(
      <>
        <StatusIndicator tone="ok" label="Aprovado" />
        <StatusIndicator tone="unknown" label="Desconhecido" />
        <Badge tone="fail">Reprovado</Badge>
      </>,
    )
    expect(screen.getByText('Aprovado')).toBeInTheDocument()
    expect(screen.getByText('Desconhecido')).toBeInTheDocument()
    expect(screen.getByText('Reprovado')).toBeInTheDocument()
  })
})

describe('Field', () => {
  it('ties the label, the hint and the error to the control', () => {
    render(
      <Field label="Exposição" hint="Em microssegundos" error="Fora da faixa">
        {(p) => <Input {...p} />}
      </Field>,
    )
    const input = screen.getByLabelText('Exposição')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const described = input.getAttribute('aria-describedby')!.split(' ')
    expect(described).toHaveLength(2)
    expect(screen.getByRole('alert')).toHaveTextContent('Fora da faixa')
    expect(document.getElementById(described[0]!)).toHaveTextContent('Em microssegundos')
  })

  it('has no aria-invalid or description when there is nothing to say', () => {
    render(<Field label="Nome">{(p) => <Input {...p} />}</Field>)
    const input = screen.getByLabelText('Nome')
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(input).not.toHaveAttribute('aria-describedby')
  })
})

describe('Dialog', () => {
  it('opens with a title, closes on Escape and gives the focus back to its opener', async () => {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Abrir</Button>
        </DialogTrigger>
        <DialogContent title="Resultado incorreto?" description="Qual era o resultado certo?">
          <Button>Estava OK</Button>
        </DialogContent>
      </Dialog>,
    )
    const opener = screen.getByRole('button', { name: 'Abrir' })
    await userEvent.click(opener)
    expect(screen.getByRole('dialog', { name: 'Resultado incorreto?' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })

  it('keeps the focus inside while open', async () => {
    render(
      <Dialog defaultOpen>
        <DialogContent title="Título">
          <Button>Um</Button>
        </DialogContent>
      </Dialog>,
    )
    const dialog = screen.getByRole('dialog')
    for (let i = 0; i < 6; i++) {
      await userEvent.tab()
      expect(dialog).toContainElement(document.activeElement as HTMLElement)
    }
  })
})

describe('ConfirmDialog', () => {
  function Host({ onConfirm }: { onConfirm: () => void }) {
    const [open, setOpen] = useState(true)
    return (
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Ativar versão 7 de Tampa azul?"
        description="A estação passa a usar esta versão."
        confirmLabel="Ativar versão 7"
        onConfirm={onConfirm}
      />
    )
  }

  it('asks for the action by name and does not confirm by accident', async () => {
    const onConfirm = vi.fn()
    render(<Host onConfirm={onConfirm} />)
    expect(
      screen.getByRole('alertdialog', { name: 'Ativar versão 7 de Tampa azul?' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus() // Enter would cancel, not confirm
    await userEvent.keyboard('{Enter}')
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('gives the focus back to the button that opened it, even without a trigger (opened from state)', async () => {
    function Opener() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <Button onClick={() => setOpen(true)}>Ativar</Button>
          <ConfirmDialog
            open={open}
            onOpenChange={setOpen}
            title="Ativar?"
            description="Isto muda a estação."
            confirmLabel="Ativar"
            onConfirm={() => setOpen(false)}
          />
        </>
      )
    }
    render(<Opener />)
    const opener = screen.getByRole('button', { name: 'Ativar' })
    await userEvent.click(opener)
    expect(await screen.findByRole('alertdialog')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })

  it('confirms only when the named button is pressed', async () => {
    const onConfirm = vi.fn()
    render(<Host onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: 'Ativar versão 7' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })
})

describe('SegmentedControl, Switch and Select', () => {
  it('a segmented control always has a value: the chosen one cannot be unselected', async () => {
    const onChange = vi.fn()
    render(
      <SegmentedControl
        label="Formato"
        value="mjpeg"
        onValueChange={onChange}
        options={[
          { value: 'mjpeg', label: 'MJPEG' },
          { value: 'yuyv', label: 'YUYV' },
        ]}
      />,
    )
    await userEvent.click(screen.getByRole('radio', { name: 'MJPEG' }))
    expect(onChange).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('radio', { name: 'YUYV' }))
    expect(onChange).toHaveBeenCalledWith('yuyv')
  })

  it('a switch is labelled and toggles with the keyboard', async () => {
    const onChange = vi.fn()
    render(
      <Switch
        checked={false}
        onCheckedChange={onChange}
        label="Alerta sonoro"
        hint="Desligado por padrão"
      />,
    )
    const control = screen.getByRole('switch', { name: 'Alerta sonoro' })
    expect(control).toHaveAccessibleDescription('Desligado por padrão')
    control.focus()
    await userEvent.keyboard(' ')
    expect(onChange).toHaveBeenCalledWith(true)
  })

  it('a select is a labelled combobox that lists options and reports the choice', async () => {
    const onChange = vi.fn()
    render(
      <Field label="Modo">
        {(p) => (
          <Select
            {...p}
            value="manual"
            onValueChange={onChange}
            options={[
              { value: 'manual', label: 'Manual' },
              { value: 'external', label: 'Externo' },
            ]}
          />
        )}
      </Field>,
    )
    const trigger = screen.getByRole('combobox', { name: 'Modo' })
    expect(trigger).toHaveTextContent('Manual')
    await userEvent.click(trigger)
    await userEvent.click(await screen.findByRole('option', { name: 'Externo' }))
    expect(onChange).toHaveBeenCalledWith('external')
  })
})

describe('FileDrop', () => {
  const file = (name: string) => new File(['x'], name)

  it('passes on a file with an accepted extension', async () => {
    const onFiles = vi.fn()
    render(<FileDrop accept=".vjob,.vbak" label="Escolher arquivo" onFiles={onFiles} />)
    await userEvent.upload(screen.getByLabelText('Escolher arquivo'), file('Tampa_v7.vjob'))
    expect(onFiles).toHaveBeenCalledWith([expect.objectContaining({ name: 'Tampa_v7.vjob' })])
  })

  it('refuses another type with a message and passes nothing on', async () => {
    const onFiles = vi.fn()
    render(<FileDrop accept=".vjob,.vbak" label="Escolher arquivo" onFiles={onFiles} />)
    const input = screen.getByLabelText('Escolher arquivo') as HTMLInputElement
    // the browser's accept filter is bypassed on purpose: a dropped file is not filtered by it
    await userEvent.upload(input, file('notas.txt'), { applyAccept: false })
    expect(onFiles).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('notas.txt')
  })
})

describe('EmptyState, ErrorState and Stepper', () => {
  it('an empty state says what the screen is for and offers the first action', () => {
    render(
      <EmptyState
        title="Nenhum job ainda"
        description="Importe um arquivo."
        action={<Button>Importar</Button>}
      />,
    )
    expect(screen.getByText('Nenhum job ainda')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Importar' })).toBeInTheDocument()
  })

  it('an error state offers a retry and folds the technical detail away', async () => {
    const onRetry = vi.fn()
    render(
      <ErrorState
        message="Não foi possível ler os resultados."
        detail="HTTP 503"
        onRetry={onRetry}
      />,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('HTTP 503')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Detalhes' }))
    expect(screen.getByText('HTTP 503')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Tentar de novo' }))
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('the stepper says the state of each step in words and marks the current one', async () => {
    const onSelect = vi.fn()
    render(
      <Stepper
        onSelect={onSelect}
        steps={[
          { id: 'a', label: 'Câmera', status: 'done' },
          { id: 'b', label: 'Regiões', status: 'current' },
          { id: 'c', label: 'Ferramentas', status: 'error' },
        ]}
      />,
    )
    expect(screen.getByRole('button', { name: /Câmera, concluído/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Regiões, passo atual/ })).toHaveAttribute(
      'aria-current',
      'step',
    )
    expect(screen.getByRole('button', { name: /Ferramentas, com erro/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Ferramentas/ }))
    expect(onSelect).toHaveBeenCalledWith('c')
  })
})
