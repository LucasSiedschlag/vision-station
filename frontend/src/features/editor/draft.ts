import { create } from 'zustand'
import { text } from '@/texts'
import type { components } from '@/api/schema'

export type JobJson = Record<string, any> // eslint-disable-line @typescript-eslint/no-explicit-any -- job.yaml as JSON; the server validates it
export type FileInfo = components['schemas']['JobFileOut']
export type Expected = {
  tolerance?: number
  cases: {
    image: string
    outcome: 'PASS' | 'FAIL' | 'ERROR'
    scores?: Record<string, number>
    reason_contains?: string | null
  }[]
}

const EXPECTED = 'tests/expected.yaml'
const HISTORY = 100

/** What is being edited. Everything the server needs to save a version, and nothing it sets itself. */
export interface Draft {
  key: string // job id, or "new"
  base: { id: string; version: number } | null // the version it starts from (its files are copied)
  latest?: number | null // the newest version seen when it was opened; saving checks it is still the newest
  job: JobJson
  profile: JobJson
  baseFiles: FileInfo[] // files of the base version
  addFiles: Record<string, string> // path -> base64 (added or replaced)
  removeFiles: string[]
  expected: Expected | null
  baseExpected: string // the base's expected set as JSON, to know if it changed
  /** The base version's job and camera profile as they were opened, to say in words what changed. Drafts kept by an older build have none. */
  baseJob?: JobJson
  baseProfile?: JobJson
  notes: string
}

interface DraftState {
  draft: Draft | null
  dirty: boolean
  /** the draft came back from this browser's storage, not from the server */
  recovered: boolean
  past: Draft[]
  future: Draft[]
  load: (draft: Draft, recovered?: boolean) => void
  forgetRecovered: () => void
  /** Change the draft. `history: false` for the many small steps of a drag (the first step records it). */
  edit: (change: (d: Draft) => void, history?: boolean) => void
  undo: () => void
  redo: () => void
  clear: () => void
}

const storageKey = (key: string) => `vision-station-draft:${key}`

/** A draft the editor can open: job format 3 with its blocks. One kept by an older version of the editor is not. */
function usable(draft: Draft | null): draft is Draft {
  const job = draft?.job
  return (
    !!job &&
    job.format === 3 &&
    !!job.acquisition &&
    !!job.geometry?.rois &&
    Array.isArray(job.tools) &&
    !!draft.profile
  )
}

/** The draft this browser kept for `key`; one that cannot be opened any more is forgotten, never shown as a crash. */
export function savedDraft(key: string): Draft | null {
  let draft: Draft | null = null
  try {
    draft = JSON.parse(localStorage.getItem(storageKey(key)) ?? 'null') as Draft | null
  } catch {
    return null
  }
  if (draft === null || usable(draft)) return draft
  forgetDraft(key)
  return null
}

export function forgetDraft(key: string) {
  try {
    localStorage.removeItem(storageKey(key))
  } catch {
    /* no storage */
  }
}

function persist(draft: Draft) {
  try {
    localStorage.setItem(storageKey(draft.key), JSON.stringify(draft))
  } catch {
    /* no storage (or full): the draft lives only in memory */
  }
}

export const useDraft = create<DraftState>((set, get) => ({
  draft: null,
  dirty: false,
  recovered: false,
  past: [],
  future: [],
  load: (draft, recovered = false) =>
    set({ draft, dirty: recovered, recovered, past: [], future: [] }),
  forgetRecovered: () => set({ recovered: false }),
  edit: (change, history = true) => {
    const current = get().draft
    if (!current) return
    const next = structuredClone(current)
    change(next)
    next.profile = completeProfile(next.profile)
    set((s) => ({
      draft: next,
      dirty: true,
      past: history ? [...s.past, current].slice(-HISTORY) : s.past,
      future: history ? [] : s.future,
    }))
    persist(next)
  },
  undo: () => {
    const { past, draft, future } = get()
    const previous = past.at(-1)
    if (!previous || !draft) return
    set({ draft: previous, past: past.slice(0, -1), future: [draft, ...future], dirty: true })
    persist(previous)
  },
  redo: () => {
    const { past, draft, future } = get()
    const next = future[0]
    if (!next || !draft) return
    set({ draft: next, past: [...past, draft], future: future.slice(1), dirty: true })
    persist(next)
  },
  clear: () => set({ draft: null, dirty: false, recovered: false, past: [], future: [] }),
}))

/** Paths of the files the draft will have once saved. */
export function draftFiles(d: Draft): string[] {
  const paths = new Set(d.baseFiles.map((f) => f.path).filter((p) => !d.removeFiles.includes(p)))
  for (const p of Object.keys(d.addFiles)) paths.add(p)
  return [...paths].sort()
}

const toBase64 = (text: string) => btoa(String.fromCharCode(...new TextEncoder().encode(text)))

/** The body the API takes (JobDraft): the expected set goes as a file when it changed (JSON is valid YAML). */
export function toRequest(d: Draft) {
  const addFiles = { ...d.addFiles }
  if (d.expected && JSON.stringify(d.expected) !== d.baseExpected)
    addFiles[EXPECTED] = toBase64(JSON.stringify(d.expected, null, 2))
  const removeFiles = d.removeFiles.filter((p) => !(p in addFiles))
  if (!d.expected && d.baseExpected !== 'null' && d.baseFiles.some((f) => f.path === EXPECTED))
    removeFiles.push(EXPECTED)
  return {
    job: d.job,
    profile: d.profile,
    base: d.base,
    latest: d.latest ?? d.base?.version ?? null,
    add_files: addFiles,
    remove_files: removeFiles,
    notes: d.notes,
  }
}

/** A camera profile is written in full (FR-JOB-16): every setting is in the file, a setting not in use as `null`. The
 * editor changes the profile in small steps that leave keys out; this fills them in after each edit, with the usual
 * values, so what is sent and saved is always complete and the server never has a default of its own to apply. */
export function completeProfile(p: JobJson): JobJson {
  const exposure = p.exposure ?? { mode: 'auto' }
  const once = exposure.auto_once ?? {}
  const pair = (x: JobJson | undefined, field: string) => ({
    ...(x ?? { mode: 'auto' }),
    [field]: x?.[field] ?? null,
  })
  return {
    ...p,
    pixel_format: p.pixel_format ?? null,
    exposure: {
      ...exposure,
      value_us: exposure.value_us ?? null,
      auto_once: {
        target_brightness: once.target_brightness ?? 10,
        max_exposure_us: once.max_exposure_us ?? 100_000,
        region: once.region ?? null,
      },
    },
    gain: pair(p.gain, 'value'),
    white_balance: pair(p.white_balance, 'kelvin'),
    focus: pair(p.focus, 'value'),
    zoom: p.zoom ?? null,
    power_line_hz: p.power_line_hz ?? 60,
    low_light_compensation: p.low_light_compensation ?? false,
    orientation: p.orientation ?? 'normal',
  }
}

export const DEFAULT_PROFILE = completeProfile({
  resolution: [1920, 1080],
  pixel_format: 'mjpeg',
  exposure: { mode: 'manual', value_us: 33000 },
  gain: { mode: 'manual', value: 0 },
  white_balance: { mode: 'manual', kelvin: 4500 },
  focus: { mode: 'manual', value: 30 },
})

/** A job to start from: manual trigger, generous quality limits, no regions or tools yet. */
export function newDraft(profile: JobJson | null): Draft {
  return {
    key: 'new',
    base: null,
    job: {
      format: 3,
      job: {
        name: text.jobs.newJob, // the default name of a new job, in the language on screen
        description: '',
        author: '',
        created_at: new Date().toISOString(),
        id: crypto.randomUUID(),
        version: 1,
      },
      acquisition: {
        trigger: { type: 'manual' },
        image: { profile: 'camera/profile.yaml', calibration: null },
      },
      quality: { brightness: { min: 15, max: 245 }, sharpness_min_ratio: 0.5 },
      geometry: { rois: {} },
      tools: [],
      decision: 'all_pass',
      ui: { waiting: null },
    },
    profile: profile ?? DEFAULT_PROFILE,
    baseFiles: [],
    addFiles: {},
    removeFiles: [],
    expected: null,
    baseExpected: 'null',
    notes: '',
  }
}

/** The locator of the job's first fixture, the one the editor calls the anchor (docs/frontend.md §7.3); null when there is none. */
export const locatorOf = (job: JobJson): JobJson | null =>
  job.geometry?.fixtures?.[0]?.locator ?? null

/** Sets the locator of the first fixture (named `anchor`), keeping its range and the fixtures after it; null removes the fixtures. */
export function setLocator(geometry: JobJson, locator: JobJson | null) {
  if (locator === null) {
    geometry.fixtures = []
    return
  }
  const [first, ...rest] = (geometry.fixtures ?? []) as JobJson[]
  geometry.fixtures = [{ ...(first ?? { name: 'anchor' }), locator }, ...rest]
}

/**
 * After a tool is taken out: a group left with fewer than two tools is no OR any more, and the server refuses it
 * (TD-33). The group is dissolved, so a tool left alone is required by itself, as a tool with no group is.
 */
export function dissolveSmallGroups(d: Draft) {
  const tools = (d.job.tools ?? []) as JobJson[]
  for (const id of Object.keys(d.job.groups ?? {})) {
    const members = tools.filter((tool) => tool.group === id)
    if (members.length >= 2) continue
    for (const tool of members) delete tool.group
    delete d.job.groups[id]
  }
  if (d.job.groups && !Object.keys(d.job.groups).length) delete d.job.groups
}

/** The text of a job in a language: `{pt-BR, en}`, or a bare text (Portuguese). An empty one falls back to the other language. */
export function textIn(value: unknown, language: 'pt-BR' | 'en'): string {
  if (typeof value === 'string') return value
  const t = (value ?? {}) as Record<string, string>
  const other = language === 'en' ? 'pt-BR' : 'en'
  return t[language] || t[other] || ''
}

/** The text exactly as written in one language, with no fallback: what its own field shows. */
export const writtenIn = (value: unknown, language: 'pt-BR' | 'en'): string =>
  typeof value === 'string'
    ? language === 'pt-BR'
      ? value
      : ''
    : (((value ?? {}) as Record<string, string>)[language] ?? '')

/** The text with one language changed; the other is kept. An empty text in both is `null` for an optional one. */
export function withText(
  value: unknown,
  language: 'pt-BR' | 'en',
  written: string,
): { 'pt-BR': string; en: string } {
  return {
    'pt-BR': language === 'pt-BR' ? written : writtenIn(value, 'pt-BR'),
    en: language === 'en' ? written : writtenIn(value, 'en'),
  }
}
