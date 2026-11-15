import { expect, test } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

const BARCODE = '8991234567890'

test('receive goods by scanning, in boxes, and see the stock', async ({
  page,
}) => {
  await page.goto('/')
  await signIn(page, OWNER.username, OWNER.password)
  await expect(page.getByRole('heading', { name: /Halo/ })).toBeVisible()

  await test.step('a pen sold per piece, bought per box of 12', async () => {
    const category = await page.request.post('/api/v1/categories/', {
      data: { name: 'ATK', costing_method: 'fifo' },
    })
    const categoryId = (await category.json()).id
    const withSub = await page.request.post(
      `/api/v1/categories/${categoryId}/sub-categories`,
      { data: { name: 'Pulpen' } },
    )
    const subCategoryId = (await withSub.json()).sub_categories[0].id
    const product = await page.request.post('/api/v1/products/', {
      data: {
        name: 'Pulpen Biru',
        sub_category_id: subCategoryId,
        skus: [
          {
            barcode: BARCODE,
            selling_price: 3000,
            purchase_pack_name: 'box',
            purchase_pack_size: 12,
          },
        ],
      },
    })
    expect(product.status()).toBe(201)
  })

  await test.step('add a supplier', async () => {
    await openMenu(page, 'Pemasok')
    await page.getByRole('button', { name: 'Tambah pemasok' }).click()
    await page.getByLabel('Nama pemasok').fill('CV Alat Tulis')
    await page.getByLabel('Telepon').fill('0812 3456 789')
    await page.getByRole('button', { name: 'Simpan' }).click()
    await expect(
      page.getByRole('row', { name: /CV Alat Tulis/ }),
    ).toContainText('Aktif')
  })

  await test.step('scan twice, switch to boxes, complete', async () => {
    await openMenu(page, 'Barang Masuk')
    await page.getByRole('link', { name: 'Barang masuk baru' }).click()
    await page.getByLabel('Pemasok', { exact: true }).click()
    await page.getByRole('option', { name: 'CV Alat Tulis' }).click()
    await page.getByLabel('No. faktur pemasok').fill('INV-2611-07')

    const scanner = page.getByLabel('Tambah barang')
    await scanner.fill(BARCODE)
    await scanner.press('Enter')
    await expect(page.getByLabel('Jumlah Pulpen Biru')).toHaveValue('1')
    await scanner.fill(BARCODE)
    await scanner.press('Enter')
    await expect(page.getByLabel('Jumlah Pulpen Biru')).toHaveValue('2')

    await page.getByLabel('Satuan Pulpen Biru').click()
    await page.getByRole('option', { name: 'box (12 pcs)' }).click()
    await page.getByLabel('Harga beli per box Pulpen Biru').fill('60000')
    await expect(page.getByText('Rp 120.000').first()).toBeVisible()
    await shot(page, 'receipt-form')

    await page.getByRole('button', { name: 'Selesaikan' }).click()
    const confirm = page.getByRole('dialog')
    await expect(confirm).toContainText('senilai Rp 120.000')
    await confirm.getByRole('button', { name: 'Selesaikan' }).click()

    await expect(
      page.getByRole('heading', { name: /^BM-\d{4}-\d{4}$/ }),
    ).toBeVisible()
    const row = page.getByRole('row', { name: /Pulpen Biru/ })
    await expect(row).toContainText('24 pcs')
    await expect(row).toContainText('2 box × 12')
    await expect(row).toContainText('Rp 5.000')
    await expect(row).toContainText('Rp 60.000 / box')
    await shot(page, 'receipt-view')
  })

  await test.step('stock and stock card show the delivery', async () => {
    await openMenu(page, 'Stok')
    await expect(
      page.getByRole('heading', { name: 'Stok', exact: true }),
    ).toBeVisible()
    const row = page.getByRole('row', { name: /Pulpen Biru/ })
    await expect(row).toContainText('24 pcs')
    await expect(row).toContainText('Rp 120.000')
    await shot(page, 'stock')

    await row.getByRole('link', { name: 'Pulpen Biru' }).click()
    await expect(
      page.getByRole('heading', { name: 'Pulpen Biru' }),
    ).toBeVisible()
    const entry = page.getByRole('row', { name: /BM-/ })
    await expect(entry).toContainText('Barang masuk')
    await expect(entry).toContainText('+24')
    await expect(entry).toContainText('Demo Pemilik')
    await shot(page, 'stock-card')
  })

  await test.step('a draft changes nothing until completed', async () => {
    await openMenu(page, 'Barang Masuk')
    await page.getByRole('link', { name: 'Barang masuk baru' }).click()
    await page.getByLabel('Pemasok', { exact: true }).click()
    await page.getByRole('option', { name: 'CV Alat Tulis' }).click()
    await page.getByLabel('Tambah barang').fill('pulpen')
    await page.getByLabel('Tambah barang').press('Enter')
    await page.getByLabel('Jumlah Pulpen Biru').fill('5')
    await page.getByLabel('Harga beli per pcs Pulpen Biru').fill('5200')
    await page.getByRole('button', { name: 'Simpan draf' }).click()

    const draft = page.getByRole('row', { name: /Draf/ }).first()
    await expect(draft).toContainText('Rp 26.000')
    await shot(page, 'receipts')

    await openMenu(page, 'Stok')
    await expect(
      page.getByRole('heading', { name: 'Stok', exact: true }),
    ).toBeVisible()
    await expect(
      page.getByRole('row', { name: /Pulpen Biru/ }),
    ).toContainText('24 pcs')
  })
})
