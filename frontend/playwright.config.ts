import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run against scripts/e2e_station.py: the real API serving the built interface, with a simulated camera
// that the tests control. Build the interface first (`npm run build`).
const port = 8780
const freshPort = 8781 // a clean installation, for the commissioning wizard (e2e/setup.spec.ts)

export default defineConfig({
  testDir: 'e2e',
  // one simulated station is shared by the tests, so they run one after another
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  expect: { timeout: 10_000 },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: 'pt-BR',
    timezoneId: 'America/Sao_Paulo',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `uv run python scripts/e2e_station.py --port ${port}`,
      cwd: '..',
      url: `http://127.0.0.1:${port}/api/state`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // not reused: the wizard test uses up the clean state, so each run starts its own
      command: `uv run python scripts/e2e_station.py --port ${freshPort} --fresh`,
      cwd: '..',
      url: `http://127.0.0.1:${freshPort}/api/state`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
