import { i18n, type Messages } from '@lingui/core'
import { I18nProvider as LinguiProvider } from '@lingui/react'
import { Fragment, useEffect, type ReactNode } from 'react'
import { I18nProvider as AriaProvider } from 'react-aria-components'
import { create } from 'zustand'

/**
 * The interface language (TD-30, docs/frontend.md §11.1). One source drives Lingui (the texts), React Aria
 * (numbers in fields) and the formatters in lib/ (numbers and dates):
 *
 * - the operator screen speaks the **station language** (system.yaml, Configurações › Estação);
 * - a person with a login may choose another one, remembered in this browser; logging out returns to the station's.
 */
export type Locale = 'pt-BR' | 'en'
export const LOCALES: readonly Locale[] = ['pt-BR', 'en']

/** Each language by its own name, the same in every language (a person looks for the word they know). */
export const LANGUAGE_NAMES: Record<Locale, string> = { 'pt-BR': 'Português', en: 'English' }

const STATION_KEY = 'vision-station-station-language' // the last station language seen: no flash of Portuguese on start
const CHOICE_KEY = 'vision-station-language'

// each catalog is a chunk of its own: the operator screen loads only the language it shows
const catalogs: Record<Locale, () => Promise<{ messages: Messages }>> = {
  'pt-BR': () => import('@/locales/pt-BR/messages.po'),
  en: () => import('@/locales/en/messages.po'),
}

export function isLocale(value: unknown): value is Locale {
  return value === 'pt-BR' || value === 'en'
}

function read(key: string): Locale | null {
  try {
    const value = localStorage.getItem(key)
    return isLocale(value) ? value : null
  } catch {
    return null
  }
}

function write(key: string, value: Locale | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    /* a private window: the choice lasts until the page is closed */
  }
}

interface LocaleState {
  /** The language on screen now. */
  locale: Locale
  /** The station language, from the status. */
  station: Locale
  /** What a person with a login chose in this browser; null: the station's. */
  choice: Locale | null
}

export const useLocale = create<LocaleState>(() => ({
  locale: i18n.locale && isLocale(i18n.locale) ? i18n.locale : 'pt-BR',
  station: read(STATION_KEY) ?? 'pt-BR',
  choice: read(CHOICE_KEY),
}))

/** Load the catalog of a language and show it. */
export async function activate(locale: Locale): Promise<void> {
  if (i18n.locale !== locale) {
    const { messages } = await catalogs[locale]()
    i18n.loadAndActivate({ locale, messages })
  }
  useLocale.setState({ locale })
}

/** The language to show: the person's choice while logged in, the station's otherwise. */
export function wanted(loggedIn: boolean): Locale {
  const { station, choice } = useLocale.getState()
  return loggedIn && choice ? choice : station
}

/** The station language arrived with the status. */
export function setStationLocale(station: Locale) {
  if (station === useLocale.getState().station) return
  write(STATION_KEY, station)
  useLocale.setState({ station })
}

/** A person with a login chose a language (user menu, login dialog); null: follow the station. */
export function chooseLocale(choice: Locale | null) {
  write(CHOICE_KEY, choice)
  useLocale.setState({ choice })
}

/** The language a page opens in, before the first status: the last station language seen. */
export function initialLocale(): Locale {
  return useLocale.getState().station
}

/**
 * Gives the language to Lingui and React Aria. The pages below are mounted again when it changes, so every text
 * is read in the new language; the live socket and the query cache sit above and are kept.
 */
export function LocaleProvider({ children }: { children: ReactNode }) {
  const locale = useLocale((s) => s.locale)
  return (
    <LinguiProvider i18n={i18n}>
      <AriaProvider locale={locale}>
        <Fragment key={locale}>{children}</Fragment>
      </AriaProvider>
    </LinguiProvider>
  )
}

/** The locale for Intl formatters outside React (lib/number, lib/datetime). */
export function currentLocale(): Locale {
  return useLocale.getState().locale
}

/**
 * Keeps the screen in the right language: the station's (from the status) on the operator screen and after a
 * logout, the person's choice while logged in. Mounted once, in the root layout.
 */
export function useLocaleSync(station: Locale | undefined, loggedIn: boolean) {
  const choice = useLocale((s) => s.choice)
  const known = useLocale((s) => s.station)
  useEffect(() => {
    if (station) setStationLocale(station)
  }, [station])
  useEffect(() => {
    const target = loggedIn && choice ? choice : known
    if (target !== useLocale.getState().locale) void activate(target)
  }, [loggedIn, choice, known])
}
