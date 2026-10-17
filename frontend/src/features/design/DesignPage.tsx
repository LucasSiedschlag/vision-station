import { Download, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { parseColor } from 'react-aria-components'
import { toast } from 'sonner'
import { Badge, StatusIndicator, type Tone } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTrigger,
  Sheet,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { EmptyState, ErrorState, Skeleton } from '@/components/ui/feedback'
import { Field } from '@/components/ui/field'
import { FileDrop } from '@/components/ui/file-drop'
import { ColorArea, ColorField, ColorSlider } from '@/components/ui/color'
import { Input, Textarea } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import { Select } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Spinner } from '@/components/ui/spinner'
import { Stepper, type Step } from '@/components/ui/stepper'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/cn'
import { useTheme, type ThemePreference } from '@/lib/theme'

const neutrals = [
  'surface-0',
  'surface-1',
  'surface-2',
  'surface-3',
  'line',
  'line-strong',
  'line-control',
  'fg',
  'fg-muted',
]
const accents = ['accent', 'accent-text']
const statuses: { name: string; solid: string; text: string; surface: string; on: string }[] = [
  { name: 'ok', solid: 'bg-ok', text: 'text-ok-text', surface: 'bg-ok-surface', on: 'text-on-ok' },
  {
    name: 'fail',
    solid: 'bg-fail',
    text: 'text-fail-text',
    surface: 'bg-fail-surface',
    on: 'text-on-fail',
  },
  {
    name: 'warn',
    solid: 'bg-warn',
    text: 'text-warn-text',
    surface: 'bg-warn-surface',
    on: 'text-on-warn',
  },
  {
    name: 'busy',
    solid: 'bg-accent',
    text: 'text-busy-text',
    surface: 'bg-busy-surface',
    on: 'text-on-accent',
  },
]
const swatch: Record<string, string> = {
  'surface-0': 'bg-surface-0',
  'surface-1': 'bg-surface-1',
  'surface-2': 'bg-surface-2',
  'surface-3': 'bg-surface-3',
  line: 'bg-line',
  'line-strong': 'bg-line-strong',
  'line-control': 'bg-line-control',
  fg: 'bg-fg',
  'fg-muted': 'bg-fg-muted',
  accent: 'bg-accent',
  'accent-text': 'bg-accent-text',
}
const sizes = [
  ['text-xs', 'text-xs', '12 / 16'],
  ['text-sm', 'text-sm', '14 / 20'],
  ['text-base', 'text-base', '16 / 24'],
  ['text-lg', 'text-lg', '20 / 28'],
  ['text-xl', 'text-xl', '24 / 32'],
  ['text-2xl', 'text-2xl', '32 / 40'],
  ['text-3xl', 'text-3xl', '48 / 56'],
] as const
const tones: Tone[] = ['ok', 'fail', 'warn', 'busy', 'neutral', 'unknown']
const toneLabel: Record<Tone, string> = {
  ok: 'Aprovado',
  fail: 'Reprovado',
  warn: 'Atenção',
  busy: 'Inspecionando',
  neutral: 'Aguardando',
  unknown: 'Desconhecido',
}

function Section({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <h2 id={id} className="border-b border-line pb-2 text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  )
}

const steps: Step[] = [
  { id: 'camera', label: 'Câmera', status: 'done' },
  { id: 'trigger', label: 'Gatilho', status: 'done' },
  { id: 'regions', label: 'Âncora e regiões', status: 'current' },
  { id: 'tools', label: 'Ferramentas', status: 'error' },
  { id: 'reference', label: 'Referência', status: 'todo' },
]

/** The component gallery: every token and component in every state, in both themes and both densities. Not linked from the menu. */
export function DesignPage() {
  const { preference, setPreference } = useTheme()
  const [kiosk, setKiosk] = useState(false)
  const [mode, setMode] = useState('image_presence')
  const [exposure, setExposure] = useState<number | null>(8000)
  const [gain, setGain] = useState<number | null>(null)
  const [thr, setThr] = useState([0.9])
  const [hue, setHue] = useState([95, 125])
  const [color, setColor] = useState(() => parseColor('hsb(210, 80%, 70%)'))
  const [on, setOn] = useState(true)
  const [pick, setPick] = useState<string>()
  const [confirm, setConfirm] = useState(false)
  const [sheet, setSheet] = useState(false)

  return (
    <div
      data-density={kiosk ? 'kiosk' : 'compact'}
      className="mx-auto flex max-w-6xl flex-col gap-10 p-6"
    >
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Sistema de design</h1>
          <p className="text-fg-muted">
            Tokens e componentes do Vision Station (docs/frontend.md §6).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <SegmentedControl
            label="Tema"
            value={preference}
            onValueChange={(v) => setPreference(v as ThemePreference)}
            options={[
              { value: 'system', label: 'Sistema' },
              { value: 'dark', label: 'Escuro' },
              { value: 'light', label: 'Claro' },
            ]}
          />
          <Switch checked={kiosk} onCheckedChange={setKiosk} label="Densidade quiosque" />
        </div>
      </header>

      <Section id="colors" title="Cores">
        <div className="grid grid-swatches gap-3">
          {[...neutrals, ...accents].map((name) => (
            <div key={name} className="flex flex-col gap-1 text-xs">
              <div className={cn('h-12 rounded-control border border-line', swatch[name])} />
              <code>{name}</code>
            </div>
          ))}
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          {statuses.map((s) => (
            <div key={s.name} className="flex flex-col gap-2 rounded-card border border-line p-3">
              <code className="text-xs">{s.name}</code>
              <div className={cn('rounded-control px-3 py-2 text-sm font-medium', s.solid, s.on)}>
                Sólido
              </div>
              <div
                className={cn('rounded-control px-3 py-2 text-sm font-medium', s.surface, s.text)}
              >
                Superfície + texto
              </div>
            </div>
          ))}
        </div>
        <p className="text-sm text-fg-muted">
          Cor significa status e nada mais, e sempre vem com ícone e palavra.
        </p>
      </Section>

      <Section id="type" title="Tipografia, espaço e forma">
        <div className="flex flex-col gap-2">
          {sizes.map(([name, cls, spec]) => (
            <div key={name} className="flex items-baseline gap-4">
              <code className="w-36 shrink-0 text-xs text-fg-muted">
                {name} · {spec}
              </code>
              <span className={cls}>Tampa fora da cor em 40% da área</span>
            </div>
          ))}
          <div className="flex items-baseline gap-4">
            <code className="w-36 shrink-0 text-xs text-fg-muted">display</code>
            <span className="text-display font-bold leading-none">APROVADO</span>
          </div>
          <p className="font-mono text-base tabular-nums">
            Números em mono: 0123456789 · 1.234,5 µs · 14:32:07
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          {[1, 2, 3, 4, 6, 8, 12, 16].map((n) => (
            <div key={n} className="flex flex-col items-center gap-1 text-xs">
              <div className="bg-accent" style={{ width: n * 4, height: n * 4 }} />
              <code>{n * 4}</code>
            </div>
          ))}
          <div
            className="size-16 rounded-control border border-line-control"
            title="radius-control"
          />
          <div className="size-16 rounded-card border border-line-control" title="radius-card" />
          <div className="h-8 w-20 rounded-pill border border-line-control" title="radius-pill" />
        </div>
      </Section>

      <Section id="buttons" title="Botões e status">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary">Primário</Button>
          <Button>Secundário</Button>
          <Button variant="ghost">Fantasma</Button>
          <Button variant="danger">Perigo</Button>
          <Button variant="primary" loading>
            Salvando
          </Button>
          <Button disabled>Desabilitado</Button>
          <Button variant="secondary">
            <Download aria-hidden className="size-4" /> Exportar
          </Button>
          <Tooltip content="Editar o job">
            <Button variant="ghost" aria-label="Editar">
              <Pencil aria-hidden className="size-4" />
            </Button>
          </Tooltip>
          <Spinner label="Carregando" />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {tones.map((t) => (
            <Badge key={t} tone={t}>
              {toneLabel[t]}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-6">
          {tones.map((t) => (
            <StatusIndicator
              key={t}
              tone={t}
              label={toneLabel[t]}
              detail={t === 'ok' ? '30 fps' : undefined}
            />
          ))}
        </div>
      </Section>

      <Section id="forms" title="Formulários">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Nome do job" hint="Aparece na tela do operador.">
            {(p) => <Input {...p} defaultValue="Tampa azul — etiqueta de lote" />}
          </Field>
          <Field label="Nome do job" error="O nome não pode ficar vazio.">
            {(p) => <Input {...p} defaultValue="" />}
          </Field>
          <Field label="Exposição" hint="Use vírgula para decimais.">
            {(p) => (
              <NumberField
                {...p}
                value={exposure}
                onChange={setExposure}
                unit="µs"
                min={100}
                max={33000}
                step={100}
              />
            )}
          </Field>
          <Field label="Ganho" required error={gain === null ? 'Informe o ganho.' : undefined}>
            {(p) => (
              <NumberField {...p} value={gain} onChange={setGain} unit="dB" min={0} max={24} />
            )}
          </Field>
          <Field label="Modo do gatilho">
            {(p) => (
              <Select
                {...p}
                value={mode}
                onValueChange={setMode}
                options={[
                  { value: 'image_presence', label: 'Presença na imagem' },
                  { value: 'manual', label: 'Manual' },
                  { value: 'external', label: 'Externo' },
                  { value: 'continuous', label: 'Contínuo', disabled: true },
                ]}
              />
            )}
          </Field>
          <Field label="Observações">
            {(p) => <Textarea {...p} placeholder="Notas desta versão" />}
          </Field>
        </div>
        <div className="flex flex-wrap items-center gap-6">
          <Switch
            checked={on}
            onCheckedChange={setOn}
            label="Alerta sonoro em REPROVADO"
            hint="Desligado por padrão."
          />
          <SegmentedControl
            label="Formato"
            value={pick ?? 'mjpeg'}
            onValueChange={setPick}
            options={[
              { value: 'mjpeg', label: 'MJPEG' },
              { value: 'yuyv', label: 'YUYV' },
            ]}
          />
        </div>
        <FileDrop
          accept=".vjob,.vbak"
          label="Escolher arquivo de job"
          onFiles={(files) => toast.success(`Arquivo recebido: ${files[0]?.name}`)}
        />
      </Section>

      <Section id="ranges" title="Números, faixas e cores">
        <p className="text-fg-muted">
          React Aria (TD-29): números no idioma da interface; fora da faixa fica marcado, nunca
          trocado.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Atraso do disparo" hint="Fora da faixa: marcado, não corrigido.">
            {(p) => (
              <NumberField {...p} value={1200} onChange={() => {}} unit="ms" min={0} max={1000} />
            )}
          </Field>
          <Field label="Altura da peça">
            {(p) => (
              <NumberField
                {...p}
                value={42.5}
                onChange={() => {}}
                unit="mm"
                decimals={1}
                isDisabled
              />
            )}
          </Field>
          <Field label="Pontuação mínima" hint="Vazio usa o padrão do tipo.">
            {(p) => (
              <NumberField
                {...p}
                value={null}
                onChange={() => {}}
                min={0}
                max={1}
                step={0.01}
                decimals={2}
                placeholder="padrão: 0,6"
              />
            )}
          </Field>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <Slider
            label="Cobertura mínima da cor"
            value={thr}
            onChange={setThr}
            min={0}
            max={1}
            step={0.01}
            decimals={2}
            fields
          />
          <Slider
            label="Matiz"
            thumbLabels={['Início', 'Fim']}
            value={hue}
            onChange={setHue}
            min={0}
            max={179}
            unit="°"
            fields
          />
          <Slider
            label="Folga"
            value={[5]}
            onChange={() => {}}
            min={0}
            max={20}
            unit="°"
            isDisabled
          />
        </div>
        <div className="flex flex-wrap items-start gap-6">
          <ColorArea
            aria-label="Cor de referência"
            value={color}
            onChange={setColor}
            className="w-56"
          />
          <div className="flex min-w-64 flex-1 flex-col gap-4">
            <ColorSlider label="Matiz" channel="hue" value={color} onChange={setColor} />
            <ColorSlider label="Saturação" channel="saturation" value={color} onChange={setColor} />
            <ColorSlider label="Brilho" channel="brightness" value={color} onChange={setColor} />
            <ColorSlider
              label="Matiz (desativado)"
              channel="hue"
              value={color}
              onChange={() => {}}
              isDisabled
            />
            <ColorField
              label="Cor (hex)"
              value={color}
              onChange={(c) => c && setColor(c)}
              className="w-40"
            />
          </div>
        </div>
      </Section>

      <Section id="overlays" title="Diálogos, painéis e avisos">
        <div className="flex flex-wrap gap-3">
          <Dialog>
            <DialogTrigger asChild>
              <Button>Abrir diálogo</Button>
            </DialogTrigger>
            <DialogContent
              title="Resultado incorreto?"
              description="O sistema disse REPROVADO. Qual era o resultado certo?"
            >
              <DialogFooter>
                <Button variant="primary">Estava OK</Button>
                <Button variant="danger">Estava NÃO OK</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button onClick={() => setConfirm(true)}>Confirmar ação</Button>
          <Button onClick={() => setSheet(true)}>Abrir painel lateral</Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button>Ações da linha</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem>Abrir</DropdownMenuItem>
              <DropdownMenuItem>Exportar</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem danger>
                <Trash2 aria-hidden className="size-4" /> Excluir rascunho
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            onClick={() =>
              toast.success('Backup feito', { description: 'backup_2026-10-14_1530.vbak' })
            }
          >
            Aviso de sucesso
          </Button>
          <Button
            onClick={() =>
              toast.error('Não foi possível gravar o backup', {
                description: 'A pasta não existe.',
                duration: Infinity,
              })
            }
          >
            Aviso de erro
          </Button>
        </div>
        <ConfirmDialog
          open={confirm}
          onOpenChange={setConfirm}
          title="Ativar versão 7 de Tampa azul?"
          description="A estação passa a inspecionar com esta versão depois da verificação."
          confirmLabel="Ativar versão 7"
          onConfirm={() => setConfirm(false)}
        />
        <Sheet
          open={sheet}
          onOpenChange={setSheet}
          title="Detalhe do resultado"
          description="14:32:07 · 310 ms"
        >
          <p>O conteúdo do painel rola dentro dele.</p>
        </Sheet>
      </Section>

      <Section id="data" title="Dados e estados">
        <Tabs defaultValue="table">
          <TabsList aria-label="Estados da tabela">
            <TabsTrigger value="table">Com dados</TabsTrigger>
            <TabsTrigger value="loading">Carregando</TabsTrigger>
            <TabsTrigger value="empty">Vazio</TabsTrigger>
            <TabsTrigger value="error">Erro</TabsTrigger>
          </TabsList>
          <TabsContent value="table">
            <Table>
              <THead>
                <TR>
                  <TH>Hora</TH>
                  <TH>Job</TH>
                  <TH>Resultado</TH>
                  <TH className="text-right">Duração</TH>
                </TR>
              </THead>
              <TBody>
                <TR>
                  <TD>14:32:07</TD>
                  <TD>Tampa azul v7</TD>
                  <TD>
                    <StatusIndicator tone="ok" label="Aprovado" />
                  </TD>
                  <TD numeric>310 ms</TD>
                </TR>
                <TR>
                  <TD>14:31:02</TD>
                  <TD>Tampa azul v7</TD>
                  <TD>
                    <StatusIndicator tone="fail" label="Reprovado" detail="Tampa ausente" />
                  </TD>
                  <TD numeric>290 ms</TD>
                </TR>
                <TR aria-selected>
                  <TD>14:29:48</TD>
                  <TD>Tampa azul v7</TD>
                  <TD>
                    <StatusIndicator tone="warn" label="Erro" detail="Câmera desconectada" />
                  </TD>
                  <TD numeric>1.204 ms</TD>
                </TR>
              </TBody>
            </Table>
          </TabsContent>
          <TabsContent value="loading">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-2/3" />
            </div>
          </TabsContent>
          <TabsContent value="empty">
            <Card>
              <EmptyState
                title="Nenhum job ainda"
                description="Importe um arquivo ou crie um job para começar."
                action={<Button variant="primary">Importar arquivo</Button>}
              />
            </Card>
          </TabsContent>
          <TabsContent value="error">
            <Card>
              <ErrorState
                message="Não foi possível ler os resultados."
                detail="HTTP 503: sem imagem da câmera"
                onRetry={() => toast.info('Tentando de novo…')}
              />
            </Card>
          </TabsContent>
        </Tabs>
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Passos do editor</CardTitle>
            </CardHeader>
            <CardContent>
              <Stepper steps={steps} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Superfícies de resultado</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2">
              {statuses.map((s) => (
                <div
                  key={s.name}
                  className={cn(
                    'grid min-h-20 place-items-center rounded-card border border-line text-xl font-bold',
                    s.surface,
                    s.text,
                  )}
                >
                  {
                    { ok: 'APROVADO', fail: 'REPROVADO', warn: 'ERRO', busy: 'INSPECIONANDO' }[
                      s.name
                    ]
                  }
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </Section>
    </div>
  )
}
