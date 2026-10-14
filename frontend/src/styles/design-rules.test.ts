// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// "One visible system" (audit principle #3): screens and components use the tokens, never raw values.

const root = fileURLToPath(new URL('..', import.meta.url))

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path]
  })
}

const sources = files(root).filter(
  (f) =>
    /\.(tsx?|css)$/.test(f) &&
    !/\.test\.tsx?$/.test(f) &&
    !f.endsWith('schema.d.ts') &&
    !f.endsWith('tokens.css'),
)
const code = sources.map((f) => ({ file: f.replace(root, 'src/'), text: readFileSync(f, 'utf8') }))

describe('the design rules', () => {
  it('has sources to check', () => expect(code.length).toBeGreaterThan(10))

  it('writes no colour value outside tokens.css', () => {
    const hits = code.flatMap(({ file, text }) =>
      [...text.matchAll(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/g)]
        .filter(
          (m) =>
            !text.slice(Math.max(0, m.index - 30), m.index).includes('box-shadow') &&
            !(file.endsWith('globals.css') && /rgb\(0 0 0/.test(text.slice(m.index, m.index + 14))),
        )
        .map((m) => `${file}: ${m[0]}`),
    )
    expect(hits).toEqual([])
  })

  it('uses no arbitrary pixel, colour or size values in class names', () => {
    const hits = code.flatMap(({ file, text }) =>
      [...text.matchAll(/\b(?:[a-z-]+:)*[a-z-]+-\[[^\]]*(?:px|rem|em|#|rgb)[^\]]*\]/g)].map(
        (m) => `${file}: ${m[0]}`,
      ),
    )
    expect(hits).toEqual([])
  })

  it("uses none of Tailwind's default palette (it is switched off, so such a class would do nothing)", () => {
    const palette =
      /\b(?:bg|text|border|ring|fill|stroke|from|to|via)-(?:red|green|blue|gray|grey|slate|zinc|neutral|stone|amber|yellow|orange|lime|emerald|teal|cyan|sky|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?\b/g
    const hits = code.flatMap(({ file, text }) =>
      [...text.matchAll(palette)].map((m) => `${file}: ${m[0]}`),
    )
    expect(hits).toEqual([])
  })

  it('writes no user-facing font size or radius outside the scales', () => {
    const hits = code.flatMap(({ file, text }) =>
      [
        ...text.matchAll(
          /\b(?:text-(?:\d+\b|\[)|rounded-(?:\d|\[|sm\b|md\b|lg\b|xl\b|2xl\b|3xl\b|full\b|none\b))[^\s"'`]*/g,
        ),
      ].map((m) => `${file}: ${m[0]}`),
    )
    expect(hits).toEqual([])
  })
})
