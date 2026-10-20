import { describe, expect, it } from 'vitest'
import { freeName, isUpright, regionOnPicture, regionOutline } from './fixtures'

const size = { width: 640, height: 480 }
const close = (got: [number, number][], want: [number, number][]) =>
  got.forEach((p, i) => {
    expect(p[0]).toBeCloseTo(want[i]![0], 5)
    expect(p[1]).toBeCloseTo(want[i]![1], 5)
  })

describe('regions on a fixture that is turned', () => {
  const fixture = {
    taught: [220 / 640, 195 / 480, 420 / 640, 285 / 480] as [number, number, number, number],
    angle: 20,
    scale: 1.2,
  }

  it('turns and scales a region like the server cuts it (numbers from geometry/pose.py)', () => {
    close(regionOutline(fixture, [0.1, 0.2, 0.6, 0.7], size), [
      [0.341731, 0.504975],
      [0.517924, 0.41947],
      [0.546782, 0.525185],
      [0.370589, 0.61069],
    ])
    close(regionOutline(fixture, [0, 0, 1, 1], size), [
      [0.29495, 0.47979],
      [0.647334, 0.30878],
      [0.70505, 0.52021],
      [0.352666, 0.69122],
    ])
  })

  it('is the plain rectangle of the taught box when the fixture is placed as taught', () => {
    close(regionOutline({ ...fixture, angle: 0, scale: 1 }, [0, 0, 1, 1], size), [
      [220 / 640, 195 / 480],
      [420 / 640, 195 / 480],
      [420 / 640, 285 / 480],
      [220 / 640, 285 / 480],
    ])
    expect(isUpright({ angle: 0, scale: 1 })).toBe(true)
    expect(isUpright({ angle: 0.1, scale: 1 })).toBe(false)
    expect(isUpright({ angle: 0, scale: 1.01 })).toBe(false)
  })
})

describe('names', () => {
  it('gives a name that no fixture or region has', () => {
    const job = {
      geometry: { fixtures: [{ name: 'anchor' }, { name: 'ancora' }], rois: { ancora2: {} } },
    }
    expect(freeName(job)).toBe('ancora3')
    expect(freeName({ geometry: {} })).toBe('ancora')
  })
})

describe('a region as it lies on a picture', () => {
  const roi = {
    relative_to: 'anchor',
    rect: [0.25, 0, 0.75, 0.2] as [number, number, number, number],
  }
  const taught = [0.3, 0.3, 0.6, 0.6]

  it('is its own rectangle when it is on the frame', () => {
    expect(
      regionOnPicture(undefined, { relative_to: 'frame', rect: [0.1, 0.1, 0.5, 0.5] }, size),
    ).toEqual({ rect: [0.1, 0.1, 0.5, 0.5] })
  })

  it('is a rectangle of the frame, to be edited, when the fixture is placed as taught', () => {
    const placed = regionOnPicture({ angle: 0, scale: 1, taught }, roi, size)
    expect(placed?.outline).toBeUndefined()
    expect(placed?.rect[0]).toBeCloseTo(0.375)
    expect(placed?.rect[2]).toBeCloseTo(0.525)
    expect(placed?.rect[3]).toBeCloseTo(0.36)
  })

  it('is the turned outline, only to be seen, when the fixture is turned', () => {
    const placed = regionOnPicture({ angle: 15, scale: 1, taught }, roi, size)
    expect(placed?.outline).toHaveLength(4)
    const xs = placed!.outline!.map((p) => p[0])
    expect(placed!.rect[0]).toBeCloseTo(Math.min(...xs)) // the box around it, for the selection
  })

  it('is nothing when the picture does not show the fixture', () => {
    expect(regionOnPicture(undefined, roi, size)).toBeNull()
    expect(regionOnPicture({ angle: 0, scale: 1, taught: null }, roi, size)).toBeNull()
  })
})
