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

export function savedDraft(key: string): Draft | null {
  try {
    return JSON.parse(localStorage.getItem(storageKey(key)) ?? 'null') as Draft | null
  } catch {
    return null
  }
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

export const DEFAULT_PROFILE = {
  resolution: [1920, 1080],
  pixel_format: 'mjpeg',
  exposure: { mode: 'manual', value_us: 33000 },
  gain: { mode: 'manual', value: 0 },
  white_balance: { mode: 'manual', kelvin: 4500 },
  focus: { mode: 'manual', value: 30 },
  power_line_hz: 60,
  low_light_compensation: false,
}

/** A job to start from: manual trigger, generous quality limits, no regions or tools yet. */
export function newDraft(profile: JobJson | null): Draft {
  return {
    key: 'new',
    base: null,
    job: {
      format: 1,
      job: {
        name: text.jobs.newJob, // the default name of a new job, in the language on screen
        description: '',
        author: '',
        created_at: new Date().toISOString(),
        id: crypto.randomUUID(),
        version: 1,
      },
      camera_profile: 'camera/profile.yaml',
      trigger: { mode: 'manual' },
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
