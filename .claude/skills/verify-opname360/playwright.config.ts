import { defineConfig } from '@playwright/test'

// Run through scripts/drive.sh, which points this at the launched instance
// and gives every drive its own evidence folder.
const baseURL = process.env.VERIFY_BASE_URL
const outputDir = process.env.VERIFY_OUT
if (!baseURL || !outputDir) {
  throw new Error('Run journeys through scripts/drive.sh, not directly.')
}

export default defineConfig({
  testDir: './journeys',
  outputDir,
  // One instance, one database: journeys run one at a time.
  workers: 1,
  timeout: 60_000,
  reporter: [['list'], ['json', { outputFile: `${outputDir}/results.json` }]],
  use: {
    baseURL,
    launchOptions: { executablePath: process.env.VERIFY_BROWSER },
    viewport: { width: 1280, height: 800 },
    screenshot: 'on',
    trace: 'on',
    // Video needs Playwright's ffmpeg, which is not installed.
    video: 'off',
  },
})
