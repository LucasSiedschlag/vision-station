import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * The image overlays, *Marcações* (docs/frontend.md §18, FR-UI-9): what is drawn over the image, one switch per layer
 * and a master switch (*Medições*: what each tool measured, VIA-0124). They are drawn by the client from what the server measured, so turning one off asks for nothing.
 * Remembered in this browser.
 */
export const LAYERS = ['regions', 'measures', 'anchors', 'labels', 'mask', 'presence', 'grid'] as const
export type Layer = (typeof LAYERS)[number]

/** The editor's defaults (§18): everything on but the pixel grid. The mask only shows while a colour range is being edited. */
export const DEFAULT_LAYERS: Record<Layer, boolean> = {
  regions: true,
  measures: true,
  anchors: true,
  labels: true,
  mask: true,
  presence: true,
  grid: false,
}

interface LayerState {
  master: boolean
  on: Record<Layer, boolean>
  setMaster: (on: boolean) => void
  toggle: (layer: Layer, on: boolean) => void
}

export const useLayers = create<LayerState>()(
  persist(
    (set) => ({
      master: true,
      on: DEFAULT_LAYERS,
      setMaster: (master) => set({ master }),
      toggle: (layer, on) => set((s) => ({ on: { ...s.on, [layer]: on } })),
    }),
    {
      name: 'vision-station-layers',
      version: 2,
      // a layer added after the choice was saved starts as the default says
      migrate: (saved) => {
        const s = (saved ?? {}) as Partial<LayerState>
        return { ...s, on: { ...DEFAULT_LAYERS, ...s.on } } as LayerState
      },
    },
  ),
)

/** The layers that are drawn: none when the master switch is off. */
export function drawn(state: Pick<LayerState, 'master' | 'on'>): Record<Layer, boolean> {
  return Object.fromEntries(LAYERS.map((l) => [l, state.master && state.on[l]])) as Record<
    Layer,
    boolean
  >
}

/** How many layers are on, for the button ("Marcações · 5/6"). */
export const countOn = (on: Record<Layer, boolean>) => LAYERS.filter((l) => on[l]).length
