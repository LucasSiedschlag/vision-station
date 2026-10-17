import AxeBuilder from '@axe-core/playwright'
import { expect, test as base, type APIRequestContext, type Page } from '@playwright/test'

/** Controls of the simulated station (scripts/e2e_station.py). */
export class Station {
  constructor(private readonly request: APIRequestContext) {}

  object(state: 'on' | 'off') {
    return this.request.post(`/__e2e/object/${state}`)
  }

  outcome(value: 'PASS' | 'FAIL' | 'ERROR') {
    return this.request.post(`/__e2e/outcome/${value}`)
  }

  /** The station language (TD-30). */
  language(value: 'pt-BR' | 'en') {
    return this.request.post(`/__e2e/language/${value}`)
  }

  async state(): Promise<{
    state: string
    counters: { PASS: number; FAIL: number; ERROR: number; total: number }
  }> {
    return (await this.request.get('/api/state')).json()
  }

  /** Empty bench, outcome PASS, and wait until the station is ready for the next object. */
  async reset() {
    await this.request.post('/__e2e/reset')
    await expect.poll(async () => (await this.state()).state, { timeout: 15_000 }).toBe('Ready')
  }
}

export const test = base.extend<{ station: Station }>({
  station: async ({ request }, use) => {
    const station = new Station(request)
    await station.reset()
    await use(station)
    await station.reset()
  },
})

export { expect }

/** Every WCAG 2.2 A and AA rule axe knows, on the page as it is now. Returns what was found, as short lines. */
export async function accessibilityProblems(page: Page): Promise<string[]> {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze()
  return result.violations.map(
    (v) =>
      `${v.impact} · ${v.id}: ${v.help} (${v.nodes.length}) ${v.nodes
        .slice(0, 3)
        .map((n) => n.target.join(' '))
        .join(' | ')}`,
  )
}

/** Fails the test on anything the browser reports as an error, and on any request that leaves this machine. */
export function watchTheBrowser(page: Page) {
  const problems: string[] = []
  page.on('console', (m) => m.type() === 'error' && problems.push(`console: ${m.text()}`))
  page.on('pageerror', (e) => problems.push(`page error: ${e.message}`))
  page.on('request', (r) => {
    const url = new URL(r.url())
    if (
      !['127.0.0.1', 'localhost'].includes(url.hostname) &&
      !['data:', 'blob:'].includes(url.protocol)
    )
      problems.push(`external request: ${r.url()}`)
  })
  return problems
}

/** Starts the page already signed in, as a login would leave it (the token the API gives, in the session storage). */
export async function signInAs(
  page: Page,
  request: APIRequestContext,
  role: 'supervisor' | 'maintainer',
) {
  const response = await request.post('/api/login', { data: { role, password: `${role}-pass` } })
  const body = await response.json()
  await page.addInitScript(
    ([token, who, seconds]) =>
      sessionStorage.setItem(
        'vision-station-session',
        JSON.stringify({ token, role: who, expires: Date.now() + Number(seconds) * 1000 }),
      ),
    [body.token, body.role, String(body.expires_in_s)],
  )
}
