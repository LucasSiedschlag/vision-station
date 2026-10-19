import { describe, expect, it } from 'vitest'
import parity from '@/test/hsv-parity.json'
import { rgbToHsv } from '@/features/editor/geometry'
import {
  fromPercent,
  hueHistogram,
  hueSpans,
  hueWidth,
  inRange,
  maskOf,
  rangeOf,
  toPercent,
  widen,
  type HsvRange,
} from './hsv-model'

describe('the browser agrees with OpenCV (the fixture comes from scripts/make_hsv_fixture.py)', () => {
  it('converts every colour of the grid to the same HSV', () => {
    const wrong = parity.colours.filter((c, i) => {
      const [h, s, v] = rgbToHsv(c[0]!, c[1]!, c[2]!)
      const want = parity.hsv[i]!
      return h !== want[0] || s !== want[1] || v !== want[2]
    })
    expect(wrong).toEqual([])
  })

  it('puts the same pixels inside each range, the one through red included', () => {
    for (const range of parity.ranges) {
      const r = { ...range, hue: range.hue as [number, number] | null }
      const wrong = parity.colours.filter((c, i) => {
        const [h, s, v] = rgbToHsv(c[0]!, c[1]!, c[2]!)
        return inRange(h, s, v, r) !== (range.inside[i] === 1)
      })
      expect(wrong).toEqual([])
    }
    expect(parity.ranges.some((r) => r.hue && r.hue[0]! > r.hue[1]!)).toBe(true)
  })

  it('builds the mask of an image the same way', () => {
    const colours = parity.colours.slice(0, 200)
    const data = new Uint8ClampedArray(colours.flatMap((c) => [...c, 255]))
    const image = { data, width: colours.length, height: 1 } as ImageData
    const range = parity.ranges[1]!
    const mask = maskOf(image, { ...range, hue: range.hue as [number, number] })
    expect(Array.from(mask)).toEqual(range.inside.slice(0, 200))
  })
})

describe('the range', () => {
  it('reads the tool parameters, with the defaults of the tool', () => {
    expect(rangeOf({})).toEqual({ hue: null, s_min: 0, s_max: 255, v_min: 0, v_max: 255 })
    expect(rangeOf({ hue: [100, 125], s_min: 90 })).toMatchObject({ hue: [100, 125], s_min: 90 })
  })

  it('knows a band through red from its two bounds', () => {
    expect(hueSpans([170, 10])).toEqual([
      [170, 179],
      [0, 10],
    ])
    expect(hueWidth([170, 10])).toBe(21)
    expect(hueWidth([100, 125])).toBe(26)
  })

  it('converts percentages and gives the same level back where it matters', () => {
    expect(toPercent(255)).toBe(100)
    expect(fromPercent(100)).toBe(255)
    expect(fromPercent(toPercent(128))).toBe(128) // 50 % is 128 either way
    expect(fromPercent(150)).toBe(255) // never out of the scale
  })
})

describe('Folga', () => {
  const base: HsvRange = { hue: [100, 120], s_min: 100, s_max: 200, v_min: 60, v_max: 220 }

  it('is taken from the base, so moving it back and forth does not drift', () => {
    const there = widen(base, 6)
    expect(there.hue).toEqual([94, 126])
    expect(there.s_min).toBeLessThan(100)
    expect(widen(base, 0)).toEqual(base)
    expect(widen(base, 6)).toEqual(there)
  })

  it('wraps through red and keeps the scales inside 0–255', () => {
    expect(widen({ ...base, hue: [175, 5] }, 4).hue).toEqual([171, 9])
    expect(widen({ ...base, hue: [2, 10] }, 4).hue).toEqual([178, 14]) // out through zero
    const wide = widen({ ...base, s_max: 250, v_min: 3 }, 20)
    expect([wide.s_max, wide.v_min]).toEqual([255, 0])
  })

  it('narrows, down to one hue, and never past it', () => {
    expect(widen(base, -4).hue).toEqual([104, 116])
    const one = widen(base, -50)
    expect(one.hue?.[0]).toBe(one.hue?.[1])
    expect(one.s_min).toBeLessThanOrEqual(one.s_max)
  })

  it('leaves any hue alone', () => {
    expect(widen({ ...base, hue: null }, 5).hue).toBeNull()
  })

  it('covers the whole circle when it grows that far', () => {
    expect(widen(base, 100).hue).toEqual([0, 179])
  })
})

describe('the hue histogram', () => {
  it('counts the saturated pixels by hue and ignores grays', () => {
    const blue: [number, number, number][] = [
      [0, 0, 200],
      [0, 0, 200],
      [100, 100, 100],
    ]
    const bins = hueHistogram(blue)
    expect(bins).toHaveLength(180)
    expect(bins[120]).toBe(2) // blue is 240°
    expect(bins.reduce((a, b) => a + b, 0)).toBe(2)
  })
})
