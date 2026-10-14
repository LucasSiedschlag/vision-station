import { create } from 'zustand'

export type ThemePreference = 'system' | 'dark' | 'light'
const KEY = 'vision-station-theme'

function read(): ThemePreference {
  try {
    const stored = localStorage.getItem(KEY)
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
  } catch {
    /* no storage */
  }
  return 'system'
}

/** `system` removes the attribute so the tokens follow prefers-color-scheme; the others force a theme. */
export function applyTheme(
  preference: ThemePreference,
  root: HTMLElement = document.documentElement,
) {
  if (preference === 'system') delete root.dataset.theme
  else root.dataset.theme = preference
}

interface ThemeState {
  preference: ThemePreference
  setPreference: (preference: ThemePreference) => void
}

export const useTheme = create<ThemeState>((set) => ({
  preference: read(),
  setPreference: (preference) => {
    try {
      localStorage.setItem(KEY, preference)
    } catch {
      /* ignore */
    }
    applyTheme(preference)
    set({ preference })
  },
}))

/** Call once before the first render, so the chosen theme is there from the first paint. */
export function initTheme() {
  applyTheme(useTheme.getState().preference)
}
