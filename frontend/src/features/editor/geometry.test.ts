import { describe, expect, it } from 'vitest'
import {
  anchorToFrame,
  describe as describeRect,
  frameToAnchor,
  fromCorners,
  move,
  normalize,
  resize,
  rgbToHsv,
  type Rect,
} from './geometry'

describe('region geometry', () => {
  it('normalizes and keeps rectangles inside the image', () => {
    expect(normalize([0.8, 0.9, 0.2, -0.1])).toEqual([0.2, 0, 0.8, 0.9])
    expect(fromCorners(0.5, 0.5, 1.2, 0.7)).toEqual([0.5, 0.5, 1, 0.7])
  })

  it('moves without leaving the image or changing size', () => {
    expect(move([0.1, 0.1, 0.3, 0.2], 0.1, 0.1)).toEqual([0.2, 0.2, 0.4, 0.3])
    expect(move([0.1, 0.1, 0.3, 0.2], 0.9, -0.5)).toEqual([0.8, 0, 1, 0.1])
  })

  it('resizes from each handle, keeping the opposite side and a minimum size', () => {
    const r: Rect = [0.2, 0.2, 0.6, 0.6]
    expect(resize(r, 'se', 0.8, 0.9)).toEqual([0.2, 0.2, 0.8, 0.9])
    expect(resize(r, 'nw', 0.1, 0.05)).toEqual([0.1, 0.05, 0.6, 0.6])
    expect(resize(r, 'n', 0.99, 0.3)).toEqual([0.2, 0.3, 0.6, 0.6])
    expect(resize(r, 'w', 0.7, 0)).toEqual([0.595, 0.2, 0.6, 0.6]) // dragged past the other side: stops at the minimum
  })

  it('converts between anchor-relative and frame coordinates both ways', () => {
    const anchor: Rect = [0.25, 0.2, 0.75, 0.8]
    const onFrame = anchorToFrame([0.3, 0, 0.7, 0.2], anchor)
    expect(onFrame).toEqual([0.4, 0.2, 0.6, 0.32])
    expect(frameToAnchor(onFrame, anchor)).toEqual([0.3, 0, 0.7, 0.2])
  })

  it('describes a region in pixels', () => {
    expect(describeRect([0.25, 0.5, 0.75, 1], 640, 480)).toBe('x 160, y 240, 320 × 240 px')
  })

  it("gives OpenCV's HSV scale", () => {
    expect(rgbToHsv(255, 0, 0)).toEqual([0, 255, 255])
    expect(rgbToHsv(0, 0, 255)).toEqual([120, 255, 255])
    expect(rgbToHsv(128, 128, 128)).toEqual([0, 0, 128])
  })
})
