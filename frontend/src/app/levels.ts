import { create } from 'zustand'
import { useSession, type Role } from '@/api/session'

/**
 * The settings level (docs/frontend.md §17, FR-UI-10): Essencial (1), Avançado (2), Especialista (3). A level is a
 * view, not a permission: it changes which settings are shown, never a value. It is remembered in this browser per
 * role and per family of screens, so the editor and the settings can differ.
 */
export type Level = 1 | 2 | 3
export const LEVELS: readonly Level[] = [1, 2, 3]
export type Family = 'editor' | 'settings'

const KEY = 'vision-station-levels'
export const DEFAULT_LEVEL: Level = 1

type Saved = Partial<Record<Role, Partial<Record<Family, Level>>>>

function isLevel(value: unknown): value is Level {
  return value === 1 || value === 2 || value === 3
}

function load(): Saved {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? '{}') as Saved
    return saved && typeof saved === 'object' ? saved : {}
  } catch {
    return {}
  }
}

function save(saved: Saved) {
  try {
    localStorage.setItem(KEY, JSON.stringify(saved))
  } catch {
    /* a private window: the choice lasts until the page is closed */
  }
}

export const useLevels = create<{ saved: Saved }>(() => ({ saved: load() }))

/** The level a person chose for a family of screens (the default one until they choose). */
export function useLevel(family: Family): [Level, (level: Level) => void] {
  const role = useSession((s) => s.role)
  const level = useLevels((s) => s.saved[role]?.[family])
  return [isLevel(level) ? level : DEFAULT_LEVEL, (next) => setLevel(role, family, next)]
}

export function setLevel(role: Role, family: Family, level: Level) {
  const saved: Saved = {
    ...useLevels.getState().saved,
    [role]: { ...useLevels.getState().saved[role], [family]: level },
  }
  save(saved)
  useLevels.setState({ saved })
}
