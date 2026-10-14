import { describe, expect, it } from 'vitest'
import { formatNumber, parseNumber } from './number'

describe('parseNumber', () => {
  it.each([
    ['8000', 8000],
    ['8.000', 8],
    ['1.234,5', 1234.5],
    ['1,234.5', 1234.5],
    ['0,25', 0.25],
    ['-3,5', -3.5],
    ['  12  ', 12],
    ['.5', 0.5],
    ['1,5', 1.5],
  ])('reads %s as %s', (text, value) => expect(parseNumber(text)).toBe(value))

  it.each(['', '   ', 'abc', '1,2,3', '12px', '--1', '1e3'])('refuses %j', (text) =>
    expect(parseNumber(text)).toBeNull(),
  )
})

describe('formatNumber', () => {
  it('writes the decimal mark as a comma and never groups digits', () => {
    expect(formatNumber(1234.5)).toBe('1234,5')
    expect(formatNumber(8000)).toBe('8000')
    expect(formatNumber(0.123456, 2)).toBe('0,12')
  })
})
