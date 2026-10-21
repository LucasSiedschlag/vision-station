import { CheckCircle2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import { useLive } from '@/api/live'
import { describeError } from '@/api/mutations'
import { systemChecks, useSaveSystem, useSystem } from '@/api/queries/admin'
import { useSetupCameras, type SetupCamera } from '@/api/queries/setup'
import { LiveCanvas } from '@/components/domain/LiveCanvas'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/feedback'
import { cn } from '@/lib/cn'
import { text } from '@/texts'
import c920 from '@/assets/cameras/c920.jpg'
import generic from '@/assets/cameras/generic.jpg'

const t = text.setup.camera

/** The picture of a validated model, by its id; any other camera has the generic one. */
const PICTURES: Record<string, string> = { c920 }

const sameConnection = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)

/** The result of a test belongs to the camera it was made on: choosing another camera hides it. */
type Check = { of: number; ok: boolean; message: string } | null

/**
 * The camera step of the wizard (docs/frontend.md §7.11): the cameras connected to this PC to choose from, so the
 * driver and the device come from the choice. Only two things are said of a camera: validated or not.
 * A change of camera takes effect after a restart, so the step is done when the image arrives, not when it is saved.
 */
export function CameraStep({ done }: { done: boolean }) {
  const cameras = useSetupCameras()
  const system = useSystem()
  const save = useSaveSystem()
  const frame = useLive((s) => s.frame)
  const [picked, setPicked] = useState<number | null>(null)
  const [check, setCheck] = useState<Check>(null)
  const [testing, setTesting] = useState(false)
  const [restart, setRestart] = useState(false)

  const list = cameras.data?.cameras ?? []
  const configured = system.data?.config.camera
  // the camera the installation already has is the one chosen, until someone chooses another
  const current =
    picked ??
    (configured ? list.findIndex((c) => sameConnection(c.connection, configured.connection)) : -1)
  const selected: SetupCamera | undefined = list[current]

  if (cameras.isPending || system.isPending) return <Skeleton className="h-40 w-full" />
  if (cameras.isError || system.isError)
    return (
      <p role="alert" className="text-sm text-fail-text">
        {describeError(cameras.error ?? system.error)}
      </p>
    )

  const camera = { ...system.data.config.camera }
  const test = async () => {
    if (!selected) return
    setTesting(true)
    try {
      const out = await systemChecks.camera({
        ...camera,
        driver: selected.driver,
        connection: selected.connection,
      })
      setCheck({ of: current, ok: out.ok, message: out.message })
    } catch (error) {
      setCheck({ of: current, ok: false, message: describeError(error) })
    } finally {
      setTesting(false)
    }
  }
  const use = () => {
    if (!selected) return
    save.mutate(
      {
        ...system.data.config,
        camera: { ...camera, driver: selected.driver, connection: selected.connection },
      },
      {
        onSuccess: (out) => {
          if (out.restart_required.includes('camera')) setRestart(true)
          else toast.success(t.inUse)
        },
        onError: (error) => toast.error(describeError(error)),
      },
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {done ? (
        <div className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">{t.liveTitle}</h3>
          <div className="relative h-56 overflow-hidden rounded-card bg-surface-2">
            <LiveCanvas frame={frame} />
          </div>
        </div>
      ) : null}

      {!cameras.data.available ? (
        <p className="text-sm text-fg-muted">{t.cannotList}</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-fg-muted">{t.none}</p>
      ) : (
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">{t.legend}</legend>
          {list.map((c, index) => (
            <label
              key={`${c.name}-${index}`}
              className={cn(
                'flex cursor-pointer items-center gap-4 rounded-card border p-3 hover:bg-surface-3',
                index === current ? 'border-accent bg-surface-3' : 'border-line',
              )}
            >
              <input
                type="radio"
                name="camera"
                className="size-4"
                checked={index === current}
                onChange={() => setPicked(index)}
              />
              <img
                src={(c.model && PICTURES[c.model]) || generic}
                alt=""
                draggable={false}
                className="h-16 w-20 shrink-0 rounded-control bg-surface-2 object-contain"
              />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="truncate font-medium">{c.name}</span>
                <span>
                  <Badge tone={c.validated ? 'ok' : 'neutral'}>
                    {c.validated ? t.validated : t.notValidated}
                  </Badge>
                </span>
                {!c.validated && index === current ? (
                  <span className="text-xs text-fg-muted">{t.notValidatedHelp}</span>
                ) : null}
              </span>
            </label>
          ))}
        </fieldset>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => void cameras.refetch()} loading={cameras.isFetching}>
          {t.search}
        </Button>
        <Button onClick={() => void test()} disabled={!selected} loading={testing}>
          {t.test}
        </Button>
        <Button variant="primary" onClick={use} disabled={!selected} loading={save.isPending}>
          {t.use}
        </Button>
      </div>

      {check && check.of === current ? (
        <p
          role="status"
          className={cn(
            'flex items-center gap-2 text-sm',
            check.ok ? 'text-ok-text' : 'text-fail-text',
          )}
        >
          {check.ok ? (
            <CheckCircle2 aria-hidden className="size-4" />
          ) : (
            <XCircle aria-hidden className="size-4" />
          )}
          {check.message}
        </p>
      ) : null}
      {restart ? (
        <p role="status" className="rounded-card border border-warn bg-warn-surface p-3 text-sm">
          {t.savedRestart}
        </p>
      ) : null}
      <p className="text-xs text-fg-muted">
        <Link to="/settings" className="underline">
          {t.advanced}
        </Link>
      </p>
    </div>
  )
}
