// @vitest-environment node
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

// TD-30: every text a person reads comes from src/texts.ts, as a Lingui message in both languages. A Portuguese
// literal anywhere else would stay Portuguese in English, so it fails here.

const root = fileURLToPath(new URL('..', import.meta.url)).replaceAll('\\', '/')

// the component gallery is for developers and stays Portuguese only (VIA-0060)
// app/locale.tsx names each language in its own language (Português, English)
const ALLOWED = ['texts.ts', 'features/design/', 'api/schema.d.ts', 'locales/', 'app/locale.tsx']

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? files(path) : [path.replaceAll('\\', '/')] // Windows paths use a backslash
  })
}

function withoutComments(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1')
}

describe('texts in two languages', () => {
  it('has no Portuguese text outside texts.ts', () => {
    const hits = files(root)
      .filter((f) => /\.tsx?$/.test(f) && !/\.test\.tsx?$/.test(f) && !f.includes('/test/'))
      .filter((f) => !ALLOWED.some((a) => f.replace(root, '').startsWith(a)))
      .flatMap((f) =>
        withoutComments(readFileSync(f, 'utf8'))
          .split('\n')
          .filter((line) => /[ãõáéíóúâêôçÃÕÁÉÍÓÚÂÊÔÇ]/.test(line))
          .map((line) => `${f.replace(root, 'src/')}: ${line.trim()}`),
      )
    expect(hits).toEqual([])
  })
})
