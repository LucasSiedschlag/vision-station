import { defineConfig } from '@lingui/conf'
import { formatter } from '@lingui/format-po'

// Interface texts in Portuguese (the source) and English (TD-30, docs/frontend.md §11). Messages are written in
// pt-BR in src/texts.ts; `npm run i18n:extract` updates the catalogs and CI fails on a missing English text.
export default defineConfig({
  sourceLocale: 'pt-BR',
  locales: ['pt-BR', 'en'],
  catalogs: [
    {
      path: '<rootDir>/src/locales/{locale}/messages',
      include: ['<rootDir>/src'],
      exclude: ['**/*.test.*', '**/test/**'],
    },
  ],
  orderBy: 'messageId',
  // no file names or line numbers: the catalogs change only when a text changes
  format: formatter({
    origins: false,
    lineNumbers: false,
    customHeaderAttributes: { 'POT-Creation-Date': '2026-10-17' },
  }),
})
