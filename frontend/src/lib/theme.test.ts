import { beforeEach, describe, expect, it } from 'vitest'
import { applyTheme, useTheme } from './theme'

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('forces a theme through data-theme and releases it for "system"', () => {
    applyTheme('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    applyTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    applyTheme('system')
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('remembers the choice', () => {
    useTheme.getState().setPreference('light')
    expect(localStorage.getItem('vision-station-theme')).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(useTheme.getState().preference).toBe('light')
  })
})
