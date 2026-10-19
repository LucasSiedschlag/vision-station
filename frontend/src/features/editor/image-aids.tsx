import { createContext, useContext, type ReactNode } from 'react'
import type { HsvRange } from '@/components/vision/hsv-model'
import type { Rect } from './geometry'

/**
 * What a control in the inspector can ask of the image beside it (docs/frontend.md §19.4): its pixels, a drag on
 * it that samples colours, and a colour mask drawn over it. The page provides it; a control used elsewhere (the
 * design gallery) gets `null` and leaves those parts out.
 */
export interface ImageAids {
  /** The pixels of the image on show. */
  pixels: ImageData | null
  /** The region of the tool being edited, when it is drawn on the frame; null: the whole image. */
  region: Rect | null
  /** Waiting for a drag on the image: what it will be used for. */
  sampling: 'include' | 'exclude' | null
  /** Waits for the person to drag over the image and gives the dragged part as a PNG (base64); null when it was cancelled. */
  sample: (mode: 'include' | 'exclude') => Promise<string | null>
  cancelSample: () => void
  /** The range whose pixels are hatched on the image; null clears it. */
  showMask: (range: HsvRange | null) => void
}

const Aids = createContext<ImageAids | null>(null)

export const ImageAidsProvider = Aids.Provider
export const useImageAids = () => useContext(Aids)

/** The region of the tool inside, for the controls that look at "the region" (the hue histogram of the picker). */
export function AidsRegion({ rect, children }: { rect: Rect | null; children: ReactNode }) {
  const aids = useImageAids()
  return <Aids.Provider value={aids ? { ...aids, region: rect } : null}>{children}</Aids.Provider>
}
