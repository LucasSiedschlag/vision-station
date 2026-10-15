import { describe, expect, it } from 'vitest'
import { atLeast, can, capabilities, type Capability } from './permissions'

// docs/frontend.md §8, row by row. The server enforces the same table; this is what the screens show.
const table: [Capability, boolean, boolean, boolean][] = [
  // capability, operator, supervisor, maintainer
  ['seeStation', true, true, true],
  ['triggerAndMarkWrong', true, true, true],
  ['jobs', false, true, true],
  ['results', false, true, true],
  ['audit', false, true, true],
  ['about', false, true, true],
  ['overrideVerification', false, false, true],
  ['editor', false, false, true],
  ['camera', false, false, true],
  ['dataset', false, false, true],
  ['settings', false, false, true],
  ['access', false, false, true],
  ['stationCommands', false, false, true],
]

describe('permissions', () => {
  it.each(table)(
    '%s: operator %s, supervisor %s, maintainer %s',
    (capability, operator, supervisor, maintainer) => {
      expect(can('operator', capability)).toBe(operator)
      expect(can('supervisor', capability)).toBe(supervisor)
      expect(can('maintainer', capability)).toBe(maintainer)
    },
  )

  it('covers every capability that exists', () => {
    expect(table.map(([c]) => c).sort()).toEqual(Object.keys(capabilities).sort())
  })

  it('a maintainer can do whatever a supervisor can, and a supervisor whatever an operator can', () => {
    for (const [capability] of table) {
      if (can('operator', capability)) expect(can('supervisor', capability)).toBe(true)
      if (can('supervisor', capability)) expect(can('maintainer', capability)).toBe(true)
    }
    expect(atLeast('maintainer', 'supervisor')).toBe(true)
    expect(atLeast('operator', 'supervisor')).toBe(false)
  })
})
