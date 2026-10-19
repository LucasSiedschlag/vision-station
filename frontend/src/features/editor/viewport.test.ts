import { describe, expect, it } from 'vitest'
import {
  FIT,
  GRID_FROM,
  MINIMAP_FROM,
  actualSize,
  centreOn,
  clampView,
  maxZoom,
  panBy,
  scaleOf,
  visibleRect,
  zoomAt,
} from './viewport'

const box = { width: 800, height: 450 }
const imageWidth = 1920

describe('the zoom and pan of the image workspace', () => {
  it('starts fitted, and 100 % of this image is 2,4 times the fit', () => {
    expect(scaleOf(1, box, imageWidth)).toBeCloseTo(800 / 1920)
    expect(actualSize(FIT, box, imageWidth).z).toBeCloseTo(1920 / 800)
    expect(scaleOf(actualSize(FIT, box, imageWidth).z, box, imageWidth)).toBeCloseTo(1)
  })

  it('zooms around the pointer: the image point under it stays under it', () => {
    const view = zoomAt(FIT, 4, 400, 225, box, imageWidth)
    expect(view.z).toBe(4)
    // the point at the middle of the box is the middle of the image before and after
    expect((400 - view.x) / (box.width * view.z)).toBeCloseTo(0.5)
    const corner = zoomAt(FIT, 2, 0, 0, box, imageWidth) // around the top-left corner: it stays put
    expect(corner).toEqual({ z: 2, x: 0, y: 0 })
  })

  it('never zooms out past the fit nor in past 16 screen pixels for an image pixel', () => {
    expect(zoomAt(FIT, 0.1, 400, 225, box, imageWidth)).toEqual(FIT)
    const top = zoomAt(FIT, 1000, 400, 225, box, imageWidth)
    expect(scaleOf(top.z, box, imageWidth)).toBeCloseTo(16)
    expect(top.z).toBe(maxZoom(box, imageWidth))
  })

  it('keeps the image covering the box when panned', () => {
    const zoomed = zoomAt(FIT, 2, 400, 225, box, imageWidth)
    const farRight = panBy(zoomed, 5000, 5000, box, imageWidth)
    expect(farRight.x).toBe(0)
    expect(farRight.y).toBe(0)
    const farLeft = panBy(zoomed, -5000, -5000, box, imageWidth)
    expect(farLeft.x).toBe(box.width - box.width * 2)
    expect(farLeft.y).toBe(box.height - box.height * 2)
    expect(clampView({ z: 1, x: -300, y: -300 }, box, imageWidth)).toEqual(FIT)
  })

  it('says which part of the image is shown, for the mini-map, and centres on a point', () => {
    expect(visibleRect(FIT, box)).toEqual([0, 0, 1, 1])
    const view = centreOn({ z: 4, x: 0, y: 0 }, 0.5, 0.5, box, imageWidth)
    const [x0, y0, x1, y1] = visibleRect(view, box)
    expect([x0, y0, x1, y1].map((v) => Math.round(v * 1000) / 1000)).toEqual([
      0.375, 0.375, 0.625, 0.625,
    ])
  })

  it('shows the mini-map above 200 % and the grid above 800 %', () => {
    expect(MINIMAP_FROM).toBe(2)
    expect(GRID_FROM).toBe(8)
    expect(scaleOf(maxZoom(box, imageWidth), box, imageWidth)).toBeGreaterThan(GRID_FROM)
  })
})
