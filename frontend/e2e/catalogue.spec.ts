import { expect, test } from '@playwright/test'

import { OWNER, shot, signIn } from './helpers'

test('the catalogue: categories, a product, its SKUs and prices', async ({
  page,
}) => {
  await page.goto('/kategori')
  await signIn(page, OWNER.username, OWNER.password)

  await test.step('create a category with a sub-category', async () => {
    await expect(page.getByText('Belum ada kategori.')).toBeVisible()
    await page.getByRole('button', { name: 'Tambah kategori' }).click()
    await page.getByLabel('Nama kategori').fill('Seragam')
    await page.getByLabel('Metode HPP').click()
    await page.getByRole('option', { name: 'FIFO' }).click()
    await shot(page, 'category-dialog')
    await page.getByRole('button', { name: 'Simpan' }).click()
    await expect(page.getByText('HPP FIFO')).toBeVisible()

    await page.getByLabel('Sub-kategori baru di Seragam').fill('Kemeja')
    await page.getByRole('button', { name: 'Tambah', exact: true }).click()
    await expect(page.getByText('0 produk')).toBeVisible()
    await shot(page, 'categories')
  })

  const skus = page.locator('fieldset')

  await test.step('create a product with two sizes', async () => {
    await page.getByRole('link', { name: 'Produk' }).click()
    await expect(page.getByText('Belum ada produk.')).toBeVisible()
    await page.getByRole('link', { name: 'Tambah produk' }).click()

    await page.getByRole('button', { name: 'Simpan produk' }).click()
    await expect(page.getByText('Nama produk wajib diisi.')).toBeVisible()
    await expect(page.getByText('Harga jual wajib diisi.')).toBeVisible()

    await page.getByLabel('Nama produk').fill('Kemeja Putih SD')
    await page.getByLabel('Sub-kategori').click()
    await page.getByRole('option', { name: 'Kemeja' }).click()
    await skus.nth(0).getByLabel('Ukuran').fill('10')
    await skus.nth(0).getByLabel('Harga jual').fill('85000')
    await expect(skus.nth(0).getByLabel('Harga jual')).toHaveValue('85.000')
    await skus.nth(0).getByRole('button', { name: 'Duplikat' }).click()
    await skus.nth(1).getByLabel('Ukuran').fill('12')
    await shot(page, 'product-form')
    await page.getByRole('button', { name: 'Simpan produk' }).click()

    const row = page.getByRole('row', { name: /Kemeja Putih SD/ })
    await expect(row).toContainText('Seragam › Kemeja')
    await expect(row).toContainText('2 SKU')
    await expect(row).toContainText('Rp 85.000')
  })

  let barcode = ''

  await test.step('change one price and see it in the history', async () => {
    await page.getByRole('link', { name: 'Kemeja Putih SD' }).click()
    barcode = await skus.nth(1).getByLabel('Barcode').inputValue()
    expect(barcode).toMatch(/^2\d{7}$/)
    await skus.nth(1).getByLabel('Harga jual').fill('90000')
    await page.getByRole('button', { name: 'Simpan produk' }).click()
    await expect(
      page.getByRole('row', { name: /Kemeja Putih SD/ }),
    ).toContainText('Rp 85.000 – Rp 90.000')
    await shot(page, 'products')

    await page.getByRole('link', { name: 'Kemeja Putih SD' }).click()
    await skus.nth(1).getByRole('button', { name: 'Riwayat harga' }).click()
    const history = page.getByRole('dialog')
    await expect(history).toContainText('Rp 85.000 → Rp 90.000')
    await expect(history).toContainText('Demo Pemilik')
    await shot(page, 'price-history')
    await page.keyboard.press('Escape')
    await page.getByRole('link', { name: 'Batal' }).click()
  })

  await test.step('find a product by barcode', async () => {
    await page.getByLabel('Cari produk').fill('tidak-ada')
    await expect(page.getByText('Tidak ada produk yang cocok.')).toBeVisible()
    await page.getByLabel('Cari produk').fill(barcode)
    await expect(
      page.getByRole('row', { name: /Kemeja Putih SD/ }),
    ).toBeVisible()
  })

  await test.step('a category in use cannot be deleted', async () => {
    await page.getByRole('link', { name: 'Kategori' }).click()
    await expect(page.getByText('1 produk')).toBeVisible()
    await page.getByRole('button', { name: 'Tindakan untuk Seragam' }).click()
    await page.getByRole('menuitem', { name: 'Hapus kategori' }).click()
    await page.getByRole('button', { name: 'Hapus', exact: true }).click()
    await expect(page.getByRole('dialog').getByRole('alert')).toContainText(
      'masih berisi produk',
    )
  })
})
