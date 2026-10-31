import { describe, expect, it } from 'vitest'
import { dissolveSmallGroups, type Draft } from './draft'

const text = { 'pt-BR': 'Sem logo nem texto', en: 'No logo or text' }
const draftOf = (tools: Record<string, unknown>[], groups?: Record<string, unknown>) =>
  ({ job: { tools, ...(groups ? { groups } : {}) } }) as unknown as Draft

describe('dissolveSmallGroups (TD-33)', () => {
  it('a group left with one tool is dissolved and the tool stays, required by itself', () => {
    const d = draftOf([{ id: 'a', group: 'marca' }, { id: 'c' }], { marca: { reason_fail: text } })
    dissolveSmallGroups(d)
    expect(d.job.tools[0]).toEqual({ id: 'a' })
    expect(d.job).not.toHaveProperty('groups')
  })

  it('a group left with none is dropped', () => {
    const d = draftOf([{ id: 'c' }], { marca: { reason_fail: text } })
    dissolveSmallGroups(d)
    expect(d.job).not.toHaveProperty('groups')
  })

  it('a group that keeps two tools is left as it is, and so are the other groups', () => {
    const d = draftOf(
      [
        { id: 'a', group: 'marca_h' },
        { id: 'b', group: 'marca_h' },
        { id: 'c', group: 'marca_v' },
      ],
      { marca_h: { reason_fail: text }, marca_v: { reason_fail: text } },
    )
    dissolveSmallGroups(d)
    expect(Object.keys(d.job.groups)).toEqual(['marca_h'])
    expect(d.job.tools.map((t: { group?: string }) => t.group)).toEqual([
      'marca_h',
      'marca_h',
      undefined,
    ])
  })
})
