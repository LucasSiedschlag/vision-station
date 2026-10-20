import type { components } from '@/api/schema'
import { anchorToFrame, type Rect } from './geometry'
import type { JobJson } from './draft'

/**
 * A fixture as the server found it on a picture (docs/frontend.md §7.3, architecture §14): where it is, how it is turned,
 * and the box it was taught with, which regions are fractions of. The editor draws regions on it and edits them only
 * where they can be edited: on a picture where the fixture is placed as taught.
 */
export type FixtureShape = components['schemas']['FixtureShape']
export type Outline = [number, number][]

/** Placed as taught: a region is a plain rectangle of the picture. */
export const isUpright = (f: Pick<FixtureShape, 'angle' | 'scale'>) =>
  f.angle === 0 && f.scale === 1

/** Points turned by `angle` degrees counter-clockwise on the screen (y grows downwards), as `geometry/pose.py` does. */
function turn([x, y]: [number, number], angle: number): [number, number] {
  const a = (angle * Math.PI) / 180
  const c = Math.cos(a)
  const s = Math.sin(a)
  return [x * c + y * s, -x * s + y * c]
}

/**
 * The outline of a region of a fixture (fractions of the picture), turned and scaled with it. A region is a rectangle of
 * fractions of the fixture's taught box, in its own axes; `[0, 0, 1, 1]` is the whole fixture. `size` is the picture's,
 * because a turn is done in pixels, not in fractions of a picture that is not square.
 */
export function regionOutline(
  fixture: Pick<FixtureShape, 'angle' | 'scale'> & { taught: Rect },
  region: Rect,
  size: { width: number; height: number },
): Outline {
  const [x0, y0, x1, y1] = fixture.taught
  const fw = (x1 - x0) * size.width * fixture.scale
  const fh = (y1 - y0) * size.height * fixture.scale
  const cx = ((x0 + x1) / 2) * size.width
  const cy = ((y0 + y1) / 2) * size.height
  const [r0, s0, r1, s1] = region
  const local: [number, number][] = [
    [r0 * fw - fw / 2, s0 * fh - fh / 2],
    [r1 * fw - fw / 2, s0 * fh - fh / 2],
    [r1 * fw - fw / 2, s1 * fh - fh / 2],
    [r0 * fw - fw / 2, s1 * fh - fh / 2],
  ]
  return local.map((p) => {
    const [x, y] = turn(p, fixture.angle)
    return [(x + cx) / size.width, (y + cy) / size.height]
  })
}

/** The fixtures of a job, in order. */
export const fixturesOf = (job: JobJson): JobJson[] => job.geometry?.fixtures ?? []

/** A name for a new fixture that no region or fixture has. */
export function freeName(job: JobJson, base = 'ancora'): string {
  const taken = new Set([
    'frame',
    ...fixturesOf(job).map((f) => f.name as string),
    ...Object.keys(job.geometry?.rois ?? {}),
  ])
  let n = 2
  let name = base
  while (taken.has(name)) name = `${base}${n++}`
  return name
}

/**
 * A region of a job as it lies on a picture: for a region of the frame its own rectangle; for a region of a fixture, the
 * rectangle it makes on the frame when the fixture is placed as taught (so it can be edited), or its turned outline
 * when it is not (shown, never edited there). Null when the picture does not show the fixture.
 */
export function regionOnPicture(
  fixture: (Pick<FixtureShape, 'angle' | 'scale'> & { taught?: number[] | null }) | undefined,
  roi: { relative_to: string; rect: Rect },
  picture: { width: number; height: number },
): { rect: Rect; outline?: Outline } | null {
  if (roi.relative_to === 'frame') return { rect: roi.rect }
  if (!fixture?.taught) return null
  const taught = fixture.taught as Rect
  if (isUpright(fixture)) return { rect: anchorToFrame(roi.rect, taught) }
  const points = regionOutline({ ...fixture, taught }, roi.rect, picture)
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  return {
    rect: [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)],
    outline: points,
  }
}
