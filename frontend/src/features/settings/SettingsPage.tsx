import { CheckCircle2, XCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { ApiError } from '@/api/client'
import { describeError } from '@/api/mutations'
import {
  systemChecks,
  useSaveSystem,
  useSystem,
  type SystemConfig,
  type SystemOut,
} from '@/api/queries/admin'
import { Link } from 'react-router'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Field } from '@/components/ui/field'
import { ErrorState, Skeleton } from '@/components/ui/feedback'
import { Input } from '@/components/ui/input'
import { NumberField } from '@/components/ui/number-field'
import { Select } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { text } from '@/texts'
import { LANGUAGE_NAMES, LOCALES, type Locale } from '@/app/locale'

const t = text.settings
type Check = { ok: boolean; message: string } | null
const list = (value: string) =>
  value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  )
}

function CheckResult({ check }: { check: Check }) {
  if (!check) return null
  const Icon = check.ok ? CheckCircle2 : XCircle
  return (
    <p
      role="status"
      className={`flex items-center gap-2 text-sm ${check.ok ? 'text-ok-text' : 'text-fail-text'}`}
    >
      <Icon aria-hidden className="size-4" />
      {check.message}
    </p>
  )
}

/** The installation's settings (docs/frontend.md §7.6, architecture §4.5). */
export function SettingsPage() {
  const system = useSystem()
  if (system.isPending)
    return (
      <main className="mx-auto max-w-3xl p-6">
        <Skeleton className="h-96 w-full" />
      </main>
    )
  if (system.isError)
    return (
      <main className="mx-auto max-w-3xl p-6">
        <ErrorState
          message={t.loadError}
          detail={describeError(system.error)}
          onRetry={() => void system.refetch()}
        />
      </main>
    )
  return <SettingsForm system={system.data} />
}

function SettingsForm({ system }: { system: SystemOut }) {
  const [config, setConfig] = useState<SystemConfig>(system.config)
  const [fields, setFields] = useState<Record<string, string>>({})
  const [folderCheck, setFolderCheck] = useState<Check>(null)
  const [cameraCheck, setCameraCheck] = useState<Check>(null)
  const [busy, setBusy] = useState('')
  const save = useSaveSystem()
  const set = <K extends keyof SystemConfig>(section: K, change: Partial<SystemConfig[K]>) =>
    setConfig((c) => ({ ...c, [section]: { ...(c[section] as object), ...change } }))
  const conn = (config.camera.connection ?? {}) as Record<string, unknown>
  const setConn = (key: string, value: unknown) => {
    const next = { ...conn }
    if (value === null || value === '' || value === undefined) delete next[key]
    else next[key] = value
    set('camera', { connection: next })
  }
  const err = (path: string) => fields[path]

  const run = async (
    which: string,
    fn: () => Promise<{ ok: boolean; message: string }>,
    setter: (c: Check) => void,
  ) => {
    setBusy(which)
    try {
      setter(await fn())
    } catch (e) {
      setter({ ok: false, message: describeError(e) })
    } finally {
      setBusy('')
    }
  }

  const submit = () =>
    save.mutate(config, {
      onSuccess: (out) => {
        setFields({})
        if (out.changed.length === 0) toast.message(t.nothingChanged)
        else toast.success(t.saved(out.changed.map((s) => t.sections[s] ?? s).join(', ')))
      },
      onError: (e) => {
        if (e instanceof ApiError && e.fields)
          setFields(
            Object.fromEntries(
              Object.entries(e.fields).map(([k, v]) => [k.replace(/^body\./, ''), v]),
            ),
          )
        toast.error(describeError(e))
      },
    })

  const restart = save.data?.restart_required.length
    ? save.data.restart_required
    : system.restart_pending
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{t.title}</h1>
        <p className="text-sm text-fg-muted">{t.intro}</p>
        <p className="font-mono text-xs text-fg-muted">{t.dataRoot(system.data_root)}</p>
        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Link to="/setup" className={buttonVariants({ variant: 'ghost' })}>
            {text.setup.reopen}
          </Link>
          <span className="text-xs text-fg-muted">{text.setup.reopenHelp}</span>
        </div>
      </div>
      {restart.length ? (
        <p
          role="status"
          className="rounded-control border border-warn-text/40 bg-warn-surface px-3 py-2 text-sm text-warn-text"
        >
          {t.restart} {restart.map((s) => t.sections[s] ?? s).join(', ')}.
        </p>
      ) : null}
      {system.last_backup_error ? (
        <p
          role="alert"
          className="rounded-control border border-fail-text/40 bg-fail-surface px-3 py-2 text-sm text-fail-text"
        >
          {t.backupError(system.last_backup_error)}
        </p>
      ) : null}

      <Section title={t.station}>
        <Field label={t.name} error={err('station.name')}>
          {(p) => (
            <Input
              {...p}
              value={config.station.name}
              onChange={(e) => set('station', { name: e.target.value })}
            />
          )}
        </Field>
        <Field label={t.shifts} hint={t.shiftsHint} error={err('station.shift_starts')}>
          {(p) => (
            <Input
              {...p}
              defaultValue={config.station.shift_starts.join(', ')}
              onChange={(e) => set('station', { shift_starts: list(e.target.value) })}
            />
          )}
        </Field>
        <Field label={t.idle} error={err('station.idle_logout_min')}>
          {(p) => (
            <NumberField
              {...p}
              value={config.station.idle_logout_min}
              onChange={(v) => set('station', { idle_logout_min: v ?? 10 })}
              unit={t.minutes}
              min={1}
              max={240}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.resultMin} hint={t.resultMinHint} error={err('station.result_min_s')}>
          {(p) => (
            <NumberField
              {...p}
              value={config.station.result_min_s}
              onChange={(v) => set('station', { result_min_s: v ?? 2 })}
              unit={t.seconds}
              min={0}
              max={30}
              decimals={1}
            />
          )}
        </Field>
        <Field label={t.language} hint={t.languageHint} error={err('station.language')}>
          {(p) => (
            <Select
              {...p}
              value={config.station.language}
              onValueChange={(v) => set('station', { language: v as Locale })}
              options={LOCALES.map((value) => ({ value, label: LANGUAGE_NAMES[value] }))}
            />
          )}
        </Field>
        <Field label={t.markings} hint={t.markingsHint} error={err('station.markings')}>
          {(p) => (
            <Select
              {...p}
              value={config.station.markings}
              onValueChange={(v) =>
                set('station', { markings: v as 'always' | 'on_fail' | 'never' })
              }
              options={(['always', 'on_fail', 'never'] as const).map((value) => ({
                value,
                label: t.markingsOptions[value],
              }))}
            />
          )}
        </Field>
        <Switch
          checked={config.station.operator_markings}
          onCheckedChange={(c) => set('station', { operator_markings: c })}
          label={t.operatorMarkings}
        />
        <Switch
          checked={config.station.fail_sound}
          onCheckedChange={(c) => set('station', { fail_sound: c })}
          label={t.failSound}
        />
      </Section>

      <Section title={t.camera}>
        <Field label={t.driver}>
          {(p) => (
            <Select
              {...p}
              value={config.camera.driver}
              onValueChange={(v) => set('camera', { driver: v, connection: {} })}
              options={system.camera_drivers.map((d) => ({ value: d, label: t.drivers[d] ?? d }))}
            />
          )}
        </Field>
        {config.camera.driver === 'uvc' ? (
          <>
            <Field label={t.deviceName} hint={t.deviceNameHint}>
              {(p) => (
                <Input
                  {...p}
                  value={String(conn.device_name ?? '')}
                  onChange={(e) => setConn('device_name', e.target.value)}
                />
              )}
            </Field>
            <Field label={t.devicePath}>
              {(p) => (
                <Input
                  {...p}
                  value={String(conn.device_path ?? '')}
                  onChange={(e) => setConn('device_path', e.target.value)}
                />
              )}
            </Field>
            <Field label={t.deviceIndex}>
              {(p) => (
                <NumberField
                  {...p}
                  value={typeof conn.device_index === 'number' ? conn.device_index : null}
                  onChange={(v) => setConn('device_index', v)}
                  min={0}
                  decimals={0}
                />
              )}
            </Field>
          </>
        ) : config.camera.driver === 'file' ? (
          <>
            <Field label={t.folder}>
              {(p) => (
                <Input
                  {...p}
                  value={String(conn.path ?? '')}
                  onChange={(e) => setConn('path', e.target.value)}
                />
              )}
            </Field>
            <Switch
              checked={Boolean(conn.loop)}
              onCheckedChange={(c) => setConn('loop', c || null)}
              label={t.loop}
            />
            <Field label={t.fps}>
              {(p) => (
                <NumberField
                  {...p}
                  value={typeof conn.fps === 'number' ? conn.fps : null}
                  onChange={(v) => setConn('fps', v)}
                  min={1}
                  max={60}
                  decimals={0}
                />
              )}
            </Field>
          </>
        ) : (
          <>
            <Field label={t.host}>
              {(p) => (
                <Input
                  {...p}
                  value={String(conn.host ?? '')}
                  onChange={(e) => setConn('host', e.target.value)}
                />
              )}
            </Field>
            <Field label={t.port}>
              {(p) => (
                <NumberField
                  {...p}
                  value={typeof conn.port === 'number' ? conn.port : null}
                  onChange={(v) => setConn('port', v)}
                  decimals={0}
                />
              )}
            </Field>
            <Field label={t.user}>
              {(p) => (
                <Input
                  {...p}
                  value={String(conn.user ?? '')}
                  onChange={(e) => setConn('user', e.target.value)}
                />
              )}
            </Field>
          </>
        )}
        <Field label={t.keyring} hint={t.keyringHint} error={err('camera')}>
          {(p) => (
            <Input
              {...p}
              value={config.camera.keyring_entry ?? ''}
              onChange={(e) => set('camera', { keyring_entry: e.target.value || null })}
            />
          )}
        </Field>
        <Button
          loading={busy === 'camera'}
          onClick={() =>
            void run('camera', () => systemChecks.camera(config.camera), setCameraCheck)
          }
        >
          {t.testCamera}
        </Button>
        <CheckResult check={cameraCheck} />
      </Section>

      <Section title={t.recording}>
        <Field label={t.sample} hint={t.sampleHint}>
          {(p) => (
            <NumberField
              {...p}
              value={config.recording.pass_sample_every}
              onChange={(v) => set('recording', { pass_sample_every: v ?? 1 })}
              unit={t.images}
              min={1}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.retention} hint={t.retentionHint}>
          {(p) => (
            <NumberField
              {...p}
              value={config.recording.retention_days ?? null}
              onChange={(v) => set('recording', { retention_days: v })}
              unit={t.days}
              min={1}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.minFree} hint={t.retentionHint}>
          {(p) => (
            <NumberField
              {...p}
              value={config.recording.min_free_gb ?? null}
              onChange={(v) => set('recording', { min_free_gb: v })}
              unit={t.gb}
              min={1}
              decimals={0}
            />
          )}
        </Field>
      </Section>

      <Section title={t.backup}>
        <Field label={t.backupFolder} hint={t.backupFolderHint}>
          {(p) => (
            <Input
              {...p}
              value={config.backup.folder ?? ''}
              onChange={(e) => set('backup', { folder: e.target.value || null })}
            />
          )}
        </Field>
        <Button
          disabled={!config.backup.folder}
          loading={busy === 'folder'}
          onClick={() =>
            void run(
              'folder',
              () => systemChecks.folder(config.backup.folder ?? ''),
              setFolderCheck,
            )
          }
        >
          {t.testFolder}
        </Button>
        <CheckResult check={folderCheck} />
        <Field label={t.every} hint={t.everyHint}>
          {(p) => (
            <NumberField
              {...p}
              value={config.backup.every_hours ?? null}
              onChange={(v) => set('backup', { every_hours: v })}
              unit={t.hours}
              min={1}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.keep}>
          {(p) => (
            <NumberField
              {...p}
              value={config.backup.keep}
              onChange={(v) => set('backup', { keep: v ?? 30 })}
              min={1}
              max={1000}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.include}>
          {(p) => (
            <Select
              {...p}
              value={config.backup.include}
              onValueChange={(v) => set('backup', { include: v as 'all' | 'latest' })}
              options={[
                { value: 'all', label: t.includeAll },
                { value: 'latest', label: t.includeLatest },
              ]}
            />
          )}
        </Field>
      </Section>

      <Section title={t.network}>
        <Field label={t.listen} hint={t.listenHint} error={err('network.host')}>
          {(p) => (
            <Input
              {...p}
              value={config.network.host}
              onChange={(e) => set('network', { host: e.target.value })}
            />
          )}
        </Field>
        <Field label={t.port}>
          {(p) => (
            <NumberField
              {...p}
              value={config.network.port}
              onChange={(v) => set('network', { port: v ?? 8765 })}
              min={1}
              max={65535}
              decimals={0}
            />
          )}
        </Field>
        <Field label={t.allowedHosts}>
          {(p) => (
            <Input
              {...p}
              defaultValue={config.network.allowed_hosts.join(', ')}
              onChange={(e) => set('network', { allowed_hosts: list(e.target.value) })}
            />
          )}
        </Field>
        <Field
          label={t.allowedOrigins}
          hint={t.allowedOriginsHint}
          error={err('network.allowed_origins')}
        >
          {(p) => (
            <Input
              {...p}
              defaultValue={config.network.allowed_origins.join(', ')}
              onChange={(e) => set('network', { allowed_origins: list(e.target.value) })}
            />
          )}
        </Field>
      </Section>

      <div className="flex justify-end">
        <Button variant="primary" loading={save.isPending} onClick={submit}>
          {t.save}
        </Button>
      </div>
    </main>
  )
}
