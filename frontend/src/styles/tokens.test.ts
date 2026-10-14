// @vitest-environment node
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// The tokens are written once, in tokens.css. These tests read that file and check the contrast of every pair
// the screens use (WCAG 2.2 AA: 4.5:1 for text, 3:1 for the edges of controls), in both themes.

const css = readFileSync(new URL('./tokens.css', import.meta.url), 'utf8')

type Theme = 'light' | 'dark'

function token(name: string, theme: Theme): string {
  const match = new RegExp(`--${name}:\\s*([^;]+);`).exec(css)
  if (!match?.[1]) throw new Error(`token --${name} not found`)
  const value = match[1].trim()
  const pair = /^light-dark\(\s*(#[0-9a-fA-F]{6})\s*,\s*(#[0-9a-fA-F]{6})\s*\)/.exec(value)
  if (pair) return (theme === 'light' ? pair[1] : pair[2])!
  if (/^#[0-9a-fA-F]{6}/.test(value)) return value.slice(0, 7)
  throw new Error(`token --${name} is not a colour: ${value}`)
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5]
    .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [
    number,
    number,
    number,
  ]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

const textPairs: [string, string][] = [
  ['fg', 'bg-0'],
  ['fg', 'bg-1'],
  ['fg', 'bg-2'],
  ['fg', 'bg-3'],
  ['fg-muted', 'bg-0'],
  ['fg-muted', 'bg-1'],
  ['fg-muted', 'bg-2'],
  ['fg-muted', 'bg-3'],
  ['on-accent', 'accent'],
  ['on-ok', 'ok'],
  ['on-fail', 'fail'],
  ['on-warn', 'warn'],
  ['accent-text', 'bg-1'],
  ['accent-text', 'bg-2'],
  ['accent-text', 'bg-0'],
  ['ok-text', 'bg-1'],
  ['fail-text', 'bg-1'],
  ['warn-text', 'bg-1'],
  ['ok-text', 'ok-surface'],
  ['fail-text', 'fail-surface'],
  ['warn-text', 'warn-surface'],
  ['busy-text', 'busy-surface'],
  ['fg', 'ok-surface'],
  ['fg', 'fail-surface'],
  ['fg', 'warn-surface'],
  ['fg', 'busy-surface'],
]

describe.each<Theme>(['dark', 'light'])('%s theme', (theme) => {
  it.each(textPairs)('text %s on %s has at least 4.5:1', (fg, bg) => {
    expect(contrast(token(fg, theme), token(bg, theme))).toBeGreaterThanOrEqual(4.5)
  })

  it.each(['bg-0', 'bg-1', 'bg-2'])('the edge of a control is at least 3:1 on %s', (bg) => {
    expect(contrast(token('border-control', theme), token(bg, theme))).toBeGreaterThanOrEqual(3)
  })

  it('the focus ring (accent-text) is at least 3:1 on every surface', () => {
    for (const bg of ['bg-0', 'bg-1', 'bg-2', 'bg-3'])
      expect(contrast(token('accent-text', theme), token(bg, theme))).toBeGreaterThanOrEqual(3)
  })
})

describe('the token file', () => {
  it('keeps the system small: 4 neutrals, 4 status hues, one accent', () => {
    const names = [...css.matchAll(/^\s*--([a-z0-9-]+):/gm)].map((m) => m[1]!)
    const colours = names.filter((n) => /^(bg-|border|fg|accent|on-|ok|fail|warn|busy)/.test(n))
    expect(colours.length).toBeLessThanOrEqual(34)
  })

  it('forces a theme only through data-theme, and defaults to dark when the system has no preference', () => {
    expect(css).toMatch(/:root\[data-theme='dark'\]\s*{\s*color-scheme: dark;/)
    expect(css).toMatch(/:root\[data-theme='light'\]\s*{\s*color-scheme: light;/)
  })
})
