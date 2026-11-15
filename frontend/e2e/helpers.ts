import type { Page } from '@playwright/test'

/** The Owner account created by tests/e2e_seed.py. */
export const OWNER = { username: 'demo', password: 'demo-pemilik-1' }

export async function signIn(page: Page, username: string, password: string) {
  await page.getByLabel('Nama pengguna').fill(username)
  await page.getByLabel('Kata sandi').fill(password)
  await page.getByRole('button', { name: 'Masuk' }).click()
}

/** Saves a screenshot when E2E_SHOTS names a folder; otherwise does nothing. */
export async function shot(page: Page, name: string) {
  const folder = process.env.E2E_SHOTS
  if (folder) await page.screenshot({ path: `${folder}/${name}.png` })
}
