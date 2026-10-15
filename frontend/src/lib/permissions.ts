import type { Role } from '@/api/session'

/** Roles in increasing order of rights. The Maintainer can do everything the Supervisor can (docs/frontend.md §8). */
export const ROLES: readonly Role[] = ['operator', 'supervisor', 'maintainer']

export function atLeast(role: Role, needed: Role): boolean {
  return ROLES.indexOf(role) >= ROLES.indexOf(needed)
}

/**
 * What each role may do. This only decides what the screens show; the server enforces the same table on every
 * endpoint, so hiding a button is a convenience, never the protection.
 */
export const capabilities = {
  seeStation: 'operator',
  triggerAndMarkWrong: 'operator',
  jobs: 'supervisor',
  results: 'supervisor',
  audit: 'supervisor',
  about: 'supervisor',
  overrideVerification: 'maintainer',
  editor: 'maintainer',
  camera: 'maintainer',
  dataset: 'maintainer',
  settings: 'maintainer',
  access: 'maintainer',
  stationCommands: 'maintainer',
} as const satisfies Record<string, Role>

export type Capability = keyof typeof capabilities

export function can(role: Role, capability: Capability): boolean {
  return atLeast(role, capabilities[capability])
}
