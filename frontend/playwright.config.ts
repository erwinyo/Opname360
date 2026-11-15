import { defineConfig } from '@playwright/test'

// The browser tests get their own server on the test database, wiped and
// seeded before every run (see tests/e2e_seed.py).
try {
  process.loadEnvFile('../.env')
} catch {
  // No .env: TEST_DATABASE_URL must come from the environment.
}

const PORT = 8765

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    command: `uv run python -m tests.e2e_seed && uv run fastapi run --host 127.0.0.1 --port ${PORT}`,
    cwd: '..',
    url: `http://127.0.0.1:${PORT}/api/v1/health/`,
    env: { DATABASE_URL: process.env.TEST_DATABASE_URL ?? '' },
    reuseExistingServer: false,
  },
})
