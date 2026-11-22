import { expect, test } from '@playwright/test'

import { api, daysFromToday, openMenu, proof, signIn, tag } from './helpers'

/**
 * features/medicine-batches-and-expiry.md: a medicine is received with its
 * Batch on Barang Masuk, one bottle is sold at Kasir, Kartu Stok shows the
 * Batch at 9, and Kedaluwarsa lists it within 30 days.
 */
test('medicine: receive a batch, sell one, see it in Kartu Stok and Kedaluwarsa', async ({
  page,
}, testInfo) => {
  const t = tag()
  const name = `Pil Kunyit ${t}`
  const batch = `KJ-${t}`
  const supplier = `PT Herbal ${t}`

  await signIn(page)
  // Preconditions: a Category that tracks batches, the medicine, a Supplier.
  const category = await api(page.request, 'categories/', {
    name: `Obat Verifikasi ${t}`,
    tracks_batches: true,
  })
  const withSub = await api(
    page.request,
    `categories/${category.id}/sub-categories`,
    { name: 'Pil' },
  )
  const product = await api(page.request, 'products/', {
    name,
    sub_category_id: withSub.sub_categories[0].id,
    skus: [{ selling_price: 35000, stock_unit: 'botol' }],
  })
  const sku: { id: number; barcode: string } = product.skus[0]
  await api(page.request, 'suppliers/', { name: supplier })

  await test.step('Barang Masuk: 10 bottles of one batch', async () => {
    await openMenu(page, 'Barang Masuk')
    await page.getByRole('link', { name: 'Barang masuk baru' }).click()
    await page.getByLabel('Pemasok', { exact: true }).click()
    await page.getByRole('option', { name: supplier }).click()
    await page.getByLabel('Tambah barang').fill(sku.barcode)
    await page.getByLabel('Tambah barang').press('Enter')
    await page.getByLabel(`Jumlah ${name}`).fill('10')
    await page.getByLabel(`Harga beli per botol ${name}`).fill('20000')
    await page.getByLabel(`Nomor batch ${name}`).fill(batch.toLowerCase())
    await page
      .getByLabel(`Tanggal kedaluwarsa ${name}`)
      .fill(daysFromToday(20))
    await proof(page, testInfo, 'receipt-filled')
    await page.getByRole('button', { name: 'Selesaikan' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Selesaikan' })
      .click()
    await expect(
      page.getByRole('heading', { name: /^BM-\d{4}-\d{4}$/ }),
    ).toBeVisible()
    await proof(page, testInfo, 'receipt-completed')
  })

  await test.step('Kasir: sell one bottle, then close the shift', async () => {
    await openMenu(page, 'Kasir')
    await page.getByLabel('Modal kas').fill('100000')
    await page.getByRole('button', { name: 'Buka shift' }).click()
    await expect(page.getByText(/^Shift SH-\d{4}-\d{4}/)).toBeVisible()
    await page.getByLabel('Barcode', { exact: true }).fill(sku.barcode)
    await page.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(page.getByLabel(`Jumlah ${name}`)).toHaveValue('1')
    await page.getByRole('button', { name: 'Bayar' }).click()
    await page.getByRole('button', { name: 'Uang pas' }).click()
    await page.getByRole('button', { name: 'Selesai' }).click()
    await expect(page.getByRole('link', { name: /^PJ-/ })).toBeVisible()
    await proof(page, testInfo, 'sale-done')
    await page.getByRole('link', { name: 'Tutup shift' }).click()
    await page.getByLabel('Uang tunai di laci').fill('135000')
    await page.getByRole('button', { name: 'Tutup shift' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Tutup shift' })
      .click()
    await expect(page.getByText('Sesuai')).toBeVisible()
  })

  await test.step('Kartu Stok: the batch holds 9', async () => {
    await page.goto(`/stok/${sku.id}`)
    await expect(page.getByRole('heading', { name })).toBeVisible()
    const row = page.getByRole('listitem').filter({ hasText: batch })
    await expect(row).toContainText('9 botol')
    await proof(page, testInfo, 'stock-card')
    // A second view of the stored state, read through the API.
    const card = await api(page.request, `stock/skus/${sku.id}/card`)
    expect(
      card.batches.map((b: { number: string; quantity: string }) => [
        b.number,
        Number(b.quantity),
      ]),
    ).toEqual([[batch, 9]])
  })

  await test.step('Kedaluwarsa: listed within 30 days, with Excel', async () => {
    await openMenu(page, 'Kedaluwarsa')
    await page.getByLabel('Kedaluwarsa dalam').click()
    await page.getByRole('option', { name: 'Dalam 30 hari' }).click()
    await expect(
      page.getByRole('heading', { name: 'Kedaluwarsa dalam 30 hari' }),
    ).toBeVisible()
    const row = page.getByRole('row', { name: new RegExp(name) })
    await expect(row).toContainText(batch)
    await expect(row).toContainText('20 hari lagi')
    await expect(row).toContainText('9 botol')
    await expect(row).toContainText('Rp 180.000')
    await expect(page.getByRole('link', { name: 'Excel' })).toHaveAttribute(
      'href',
      /reports\/expiry\/excel\?days=30$/,
    )
    await proof(page, testInfo, 'expiry-report')
  })
})
