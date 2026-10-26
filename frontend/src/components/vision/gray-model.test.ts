import { describe, expect, it } from 'vitest'
import parity from '@/test/gray-parity.json'
import { grayHistogram, grayOf, objectShare, otsu } from './gray-model'

describe('the browser agrees with OpenCV (the fixture comes from scripts/make_gray_fixture.py)', () => {
  it('converts every colour of the grid to the same gray', () => {
    const wrong = parity.colours.filter((c, i) => grayOf(c[0]!, c[1]!, c[2]!) !== parity.gray[i])
    expect(wrong).toEqual([])
  })

  it("finds Otsu's level in every histogram", () => {
    for (const { counts, level } of parity.otsu) expect(otsu(counts)).toBe(level)
  })
})

describe('the histogram of a region', () => {
  const data = (px: number[][]) =>
    ({ width: px.length, height: 1, data: Uint8ClampedArray.from(px.flatMap(([r, g, b]) => [r!, g!, b!, 255])) }) as ImageData

  it('counts the pixels inside the region only', () => {
    const img = data([[0, 0, 0], [255, 255, 255], [255, 255, 255], [0, 0, 0]])
    const whole = grayHistogram(img, [0, 0, 1, 1])
    expect([whole[0], whole[255]]).toEqual([2, 2])
    const right = grayHistogram(img, [0.5, 0, 1, 1])
    expect([right[0], right[255]]).toEqual([1, 1])
  })
})

describe('what the threshold takes as object', () => {
  const counts = Array.from({ length: 256 }, (_, i) => (i === 10 ? 3 : i === 200 ? 1 : 0))
  it('is gray <= t for dark and gray > t for light', () => {
    expect(objectShare(counts, 10, 'dark')).toBeCloseTo(0.75)
    expect(objectShare(counts, 10, 'light')).toBeCloseTo(0.25)
    expect(objectShare(counts, 9, 'dark')).toBe(0)
  })
})
