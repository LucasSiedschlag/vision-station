import { describe, expect, it } from 'vitest'
import { formatNumber } from './number'

describe('formatNumber', () => {
  it('writes the decimal mark as a comma and never groups digits', () => {
    expect(formatNumber(1234.5)).toBe('1234,5')
    expect(formatNumber(8000)).toBe('8000')
    expect(formatNumber(0.123456, 2)).toBe('0,12')
  })
})
