import { writeFile } from 'node:fs/promises'

import { expect } from '@playwright/test'
import type { APIRequestContext, Page, TestInfo } from '@playwright/test'

/** Created by tests/e2e_seed.py on every launch. */
export const OWNER = { username: 'demo', password: 'demo-pemilik-1' }

/** Sign in on the login screen; resolves once the home screen is up. */
export async function signIn(
  page: Page,
  username = OWNER.username,
  password = OWNER.password,
) {
  await page.goto('/')
  await page.getByLabel('Nama pengguna').fill(username)
  await page.getByLabel('Kata sandi').fill(password)
  await page.getByRole('button', { name: 'Masuk' }).click()
  // Owner and Admin land on Dasbor, a Cashier on "Halo, <name>".
  await expect(
    page.getByRole('heading', { name: /^(Dasbor|Halo)/ }),
  ).toBeVisible()
}

/** Open a screen from the sidebar by its exact label. */
export async function openMenu(page: Page, name: string) {
  await page
    .getByRole('navigation')
    .getByRole('link', { name, exact: true })
    .click()
}

/**
 * Preconditions through the real API, as the signed-in user (the page's
 * cookie). Never use it for the step being proven: drive that on screen.
 */
export async function api(
  request: APIRequestContext,
  path: string,
  data?: object,
) {
  const response =
    data === undefined
      ? await request.get(`/api/v1/${path}`)
      : await request.post(`/api/v1/${path}`, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

/**
 * Evidence for one moment: a full-page screenshot and the accessibility
 * tree as text, numbered in order, in this journey's evidence folder.
 */
export async function proof(page: Page, testInfo: TestInfo, name: string) {
  const n = String(testInfo.attachments.length / 2 + 1).padStart(2, '0')
  const png = testInfo.outputPath(`${n}-${name}.png`)
  const aria = testInfo.outputPath(`${n}-${name}.aria.yml`)
  await page.screenshot({ path: png, fullPage: true })
  // The screen's content without the sidebar; the whole page where there is
  // no layout (sign-in, print views).
  const main = page.getByRole('main')
  const scope = (await main.count()) > 0 ? main : page.locator('body')
  await writeFile(aria, await scope.ariaSnapshot())
  await testInfo.attach(`${n}-${name}`, { path: png, contentType: 'image/png' })
  await testInfo.attach(`${n}-${name}.aria`, {
    path: aria,
    contentType: 'text/yaml',
  })
}

/** Short and unique, so a journey can run again on the same instance. */
export function tag(): string {
  return Date.now().toString(36).slice(-5).toUpperCase()
}

/** `days` from today in the browser's timezone, as date inputs want it. */
export function daysFromToday(days: number): string {
  const day = new Date()
  day.setDate(day.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}
