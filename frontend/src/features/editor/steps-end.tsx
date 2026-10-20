import { CheckCircle2, ClipboardCheck, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { describeError } from '@/api/mutations'
import { editorApi, useTypes } from '@/api/queries/editor'
import { StatusIndicator } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { Input, Textarea } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Table, TBody, TD, TH, THead, TR } from '@/components/ui/table'
import { text } from '@/texts'
import { BilingualField } from './BilingualField'
import { draftFiles, toRequest, useDraft, type Draft, type JobJson } from './draft'
import type { StepProps } from './steps'
import { summarizeChanges } from './summary'

const t = text.editor
const edit = (change: (d: Draft) => void, history = true) =>
  useDraft.getState().edit(change, history)

// --- 6. result and outputs -----------------------------------------------------------------------------

/** Which tools decide the result, and what the operator screen says while it waits (docs/frontend.md §7.3 step 6). */
export function OutputsStep({ draft }: StepProps) {
  const tools: JobJson[] = draft.job.tools ?? []
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.outputsIntro}</p>
      <ul className="flex flex-col gap-2">
        {tools.map((tool, i) => (
          <li key={tool.id} className="rounded-control border border-line p-3">
            <Switch
              checked={tool.affects_result !== false}
              onCheckedChange={(on) =>
                edit((d) => {
                  if (on) delete d.job.tools[i].affects_result
                  else d.job.tools[i].affects_result = false
                })
              }
              label={`${t.decides}: ${tool.id}`}
              hint={t.decidesHint}
            />
          </li>
        ))}
      </ul>
      <BilingualField
        label={t.waiting}
        hint={t.waitingHint}
        value={draft.job.ui?.waiting}
        onChange={(next) =>
          edit(
            (d) =>
              ((d.job.ui ??= {}).waiting = next['pt-BR'].trim() || next.en.trim() ? next : null),
            false,
          )
        }
      />
      <p className="text-sm text-fg-muted">{t.machineOutputs}</p>
    </div>
  )
}

// --- 7. validate ---------------------------------------------------------------------------------------

/** The job on every sample, against what each should give: the run that activation does too (design rule 4). */
export function ValidateStep({ draft, report, verifying, verify }: StepProps) {
  const samples = draft.expected?.cases.length ?? 0
  const failed = report ? report.cases.filter((c) => !c.ok).length : 0
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.validateIntro}</p>
      <Button variant="primary" loading={verifying} onClick={() => void verify()}>
        <ClipboardCheck aria-hidden className="size-4" />
        {t.validateAll}
      </Button>
      {samples === 0 && !report ? <p className="text-sm text-fg-muted">{t.validateEmpty}</p> : null}
      {report?.message ? (
        <p role="status" className="text-sm text-fail-text">
          {report.message}
        </p>
      ) : null}
      {report && report.cases.length > 0 ? (
        <>
          <p role="status" className="flex flex-wrap items-center gap-2">
            {failed === 0 ? (
              <StatusIndicator tone="ok" label={t.validateOk} />
            ) : (
              <StatusIndicator tone="fail" label={t.validateSome(failed, report.cases.length)} />
            )}
            {report.max_ms !== null && report.max_ms !== undefined ? (
              <span className="ml-auto font-mono text-xs text-fg-muted tabular-nums">
                {t.slowest(report.max_ms)}
              </span>
            ) : null}
          </p>
          <Table>
            <THead>
              <TR>
                <TH>{t.colSample}</TH>
                <TH>{t.colExpected}</TH>
                <TH>{t.colGot}</TH>
              </TR>
            </THead>
            <TBody>
              {report.cases.map((c) => (
                <TR key={c.image}>
                  <TD className="font-mono text-xs">{c.image.replace('tests/images/', '')}</TD>
                  <TD>{t.sampleKind[c.expected]}</TD>
                  <TD>
                    <span className="flex items-center gap-2">
                      {c.ok ? (
                        <CheckCircle2 aria-hidden className="size-4 text-ok-text" />
                      ) : (
                        <XCircle aria-hidden className="size-4 text-fail-text" />
                      )}
                      <span>{c.outcome ? t.outcome[c.outcome] : t.notRun}</span>
                      {c.ok ? null : <span className="text-xs text-fail-text">{c.message}</span>}
                    </span>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </>
      ) : null}
    </div>
  )
}

// --- 8. save ---------------------------------------------------------------------------------------------

/** The name, what changed in words, and the way to save it as the next version. */
export function SaveStep({ draft, fields, openSave }: StepProps) {
  const types = useTypes()
  const [check, setCheck] = useState<{
    ok: boolean
    message?: string | null
    fields: Record<string, string>
  } | null>(null)
  const run = async () => {
    try {
      const r = await editorApi.validate(toRequest(draft))
      setCheck({ ok: r.ok, message: r.message, fields: r.fields })
    } catch (e) {
      toast.error(describeError(e))
    }
  }
  const all = { ...fields, ...(check?.fields ?? {}) }
  const changes = summarizeChanges(draft, types.data)
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-fg-muted">{t.saveIntro}</p>
      <Field label={t.jobName}>
        {(props) => (
          <Input
            {...props}
            value={draft.job.job?.name ?? ''}
            onChange={(e) => edit((d) => (d.job.job.name = e.target.value), false)}
          />
        )}
      </Field>
      <Field label={t.description}>
        {(props) => (
          <Textarea
            {...props}
            rows={2}
            value={draft.job.job?.description ?? ''}
            onChange={(e) => edit((d) => (d.job.job.description = e.target.value), false)}
          />
        )}
      </Field>
      <section aria-labelledby="changes-title" className="flex flex-col gap-2">
        <h3 id="changes-title" className="text-sm font-semibold">
          {t.changes}
        </h3>
        {changes.length === 0 ? (
          <p className="text-sm text-fg-muted">{t.noChanges}</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {changes.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}
      </section>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={openSave}>
          {t.save}
        </Button>
        <Button onClick={() => void run()}>{t.checkFields}</Button>
      </div>
      {check ? (
        <div role="status" className="flex flex-col gap-1 text-sm">
          {check.ok ? (
            <StatusIndicator tone="ok" label={t.valid} />
          ) : (
            <StatusIndicator tone="fail" label={check.message ?? t.invalid} />
          )}
        </div>
      ) : null}
      {Object.keys(all).length > 0 ? (
        <ul aria-label={t.fieldErrors} className="flex flex-col gap-1 text-sm text-fail-text">
          {Object.entries(all).map(([k, v]) => (
            <li key={k}>
              <span className="font-mono">{k}</span>: {v}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-sm text-fg-muted">{t.files(draftFiles(draft).length)}</p>
    </div>
  )
}
