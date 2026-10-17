import type { ReactNode } from 'react'
import { I18nProvider } from 'react-aria-components'

/**
 * The interface language. React Aria formats and reads numbers with it (`0,80` in pt-BR, `0.80` in
 * en). Portuguese only until UI-C2 adds English and the language switch (TD-30).
 */
export const locale = 'pt-BR'

export function LocaleProvider({ children }: { children: ReactNode }) {
  return <I18nProvider locale={locale}>{children}</I18nProvider>
}
