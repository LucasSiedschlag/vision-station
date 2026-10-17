// the Lingui Vite plugin turns a .po catalog into compiled messages on import
declare module '*.po' {
  import type { Messages } from '@lingui/core'
  export const messages: Messages
}
