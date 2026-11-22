import { expect, test } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

const BARCODE = '8990000000017'

async function api(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(`/api/v1/${path}`, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

/** `days` from today, as a date input wants it. */
function daysFromToday(days: number): string {
  const day = new Date()
  day.setDate(day.getDate() + days)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

/**
 * Slice 6 end to end: the Owner switches a Category's Costing Method,
 * receives a medicine with its Batch, sells one, and finds the rest in the
 * expiry report.
 */
test('medicine: switch costing, receive a batch, sell, expiry report', async ({
  page,
}) => {
  await page.goto('/')
  await signIn(page, OWNER.username, OWNER.password)
  await expect(page.getByRole('heading', { name: 'Dasbor' })).toBeVisible()

  await test.step('a medicine that tracks batches', async () => {
    const request = page.request
    const category = await api(request, 'categories/', {
      name: 'Obat Herbal',
      tracks_batches: true,
    })
    const withSub = await api(
      request,
      `categories/${category.id}/sub-categories`,
      { name: 'Pil' },
    )
    await api(request, 'products/', {
      name: 'Pil Kunyit',
      sub_category_id: withSub.sub_categories[0].id,
      skus: [{ barcode: BARCODE, selling_price: 35000, stock_unit: 'botol' }],
    })
    await api(request, 'suppliers/', { name: 'PT Herbal Nusantara' })
  })

  await test.step('the owner switches the category to FIFO', async () => {
    await openMenu(page, 'Kategori')
    await page
      .getByRole('button', { name: 'Tindakan untuk Obat Herbal' })
      .click()
    await page.getByRole('menuitem', { name: 'Ganti metode HPP' }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('Ganti HPP Obat Herbal ke FIFO?')
    await shot(page, 'batches-01-switch')
    await dialog.getByRole('button', { name: 'Ganti ke FIFO' }).click()
    await expect(dialog).toBeHidden()
    const section = page.locator('section', {
      has: page.getByRole('heading', { name: 'Obat Herbal' }),
    })
    await expect(section).toContainText('HPP FIFO')
    await expect(section).toContainText('Batch')
  })

  await test.step('receives ten bottles of one batch', async () => {
    await openMenu(page, 'Barang Masuk')
    await page.getByRole('link', { name: 'Barang masuk baru' }).click()
    await page.getByLabel('Pemasok', { exact: true }).click()
    await page.getByRole('option', { name: 'PT Herbal Nusantara' }).click()
    await page.getByLabel('Tambah barang').fill(BARCODE)
    await page.getByLabel('Tambah barang').press('Enter')
    await page.getByLabel('Jumlah Pil Kunyit').fill('10')
    await page.getByLabel('Harga beli per botol Pil Kunyit').fill('20000')
    await page.getByLabel('Nomor batch Pil Kunyit').fill('kj-01')
    await page
      .getByLabel('Tanggal kedaluwarsa Pil Kunyit')
      .fill(daysFromToday(20))
    await shot(page, 'batches-02-receipt')
    await page.getByRole('button', { name: 'Selesaikan' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Selesaikan' })
      .click()
    await expect(
      page.getByRole('heading', { name: /^BM-\d{4}-\d{4}$/ }),
    ).toBeVisible()
  })

  await test.step('sells one bottle at the till', async () => {
    await openMenu(page, 'Kasir')
    await page.getByLabel('Modal kas').fill('100000')
    await page.getByRole('button', { name: 'Buka shift' }).click()
    await expect(page.getByText(/^Shift SH-\d{4}-\d{4}/)).toBeVisible()
    await page.getByLabel('Barcode', { exact: true }).fill(BARCODE)
    await page.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(page.getByLabel('Jumlah Pil Kunyit')).toHaveValue('1')
    await page.getByRole('button', { name: 'Bayar' }).click()
    await page.getByRole('button', { name: 'Uang pas' }).click()
    await page.getByRole('button', { name: 'Selesai' }).click()
    await expect(page.getByRole('link', { name: /^PJ-/ })).toBeVisible()
    // Close the drawer again: the other browser tests open their own Shift.
    await page.getByRole('link', { name: 'Tutup shift' }).click()
    await page.getByLabel('Uang tunai di laci').fill('135000')
    await page.getByRole('button', { name: 'Tutup shift' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Tutup shift' })
      .click()
    await expect(page.getByText('Sesuai')).toBeVisible()
  })

  await test.step('the rest of the batch is in the expiry report', async () => {
    await openMenu(page, 'Kedaluwarsa')
    await page.getByLabel('Kedaluwarsa dalam').click()
    await page.getByRole('option', { name: 'Dalam 30 hari' }).click()
    await expect(
      page.getByRole('heading', { name: 'Kedaluwarsa dalam 30 hari' }),
    ).toBeVisible()
    const row = page.getByRole('row', { name: /Pil Kunyit/ })
    await expect(row).toContainText('KJ-01')
    await expect(row).toContainText('20 hari lagi')
    await expect(row).toContainText('9 botol')
    await expect(row).toContainText('Rp 180.000')
    await expect(page.getByRole('link', { name: 'Excel' })).toHaveAttribute(
      'href',
      /reports\/expiry\/excel\?days=30$/,
    )
    await shot(page, 'batches-03-expiry')
  })
})
