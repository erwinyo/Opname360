import { expect, test } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

/**
 * Slice 1 end to end, through the screens only: staff sign in with their
 * own accounts, the catalogue gets a Barcode on every SKU, goods come in,
 * and the back office sees the stock and the Stock Card.
 */
test('main path: a new admin sets up a product and receives it', async ({
  browser,
}) => {
  const owner = await (await browser.newContext()).newPage()
  const admin = await (await browser.newContext()).newPage()
  let barcode = ''

  await test.step('the owner creates an admin account', async () => {
    await owner.goto('/pengguna')
    await signIn(owner, OWNER.username, OWNER.password)
    await owner.getByRole('button', { name: 'Tambah pengguna' }).click()
    await owner.getByLabel('Nama lengkap').fill('Rina Admin')
    await owner.getByLabel('Nama pengguna').fill('rina')
    await owner.getByLabel('Peran').click()
    await owner.getByRole('option', { name: 'Admin' }).click()
    await owner.getByLabel('Kata sandi').fill('sandi-rina-1')
    await owner.getByRole('button', { name: 'Buat akun' }).click()
    await expect(owner.getByRole('row', { name: /Rina Admin/ })).toBeVisible()
  })

  await test.step('the admin signs in and builds the catalogue', async () => {
    await admin.goto('/')
    await signIn(admin, 'rina', 'sandi-rina-1')
    await expect(admin.getByRole('heading', { name: 'Dasbor' })).toBeVisible()
    // An Admin has no Pengguna menu.
    await expect(
      admin.getByRole('navigation').getByRole('link', { name: 'Pengguna' }),
    ).toHaveCount(0)

    await openMenu(admin, 'Kategori')
    await admin.getByRole('button', { name: 'Tambah kategori' }).click()
    await admin.getByLabel('Nama kategori').fill('Seragam SD')
    await admin.getByRole('button', { name: 'Simpan' }).click()
    await admin.getByLabel('Sub-kategori baru di Seragam SD').fill('Celana')
    await admin
      .getByRole('button', { name: 'Tambah sub-kategori di Seragam SD' })
      .click()
    await expect(admin.getByText('Celana')).toBeVisible()

    await openMenu(admin, 'Produk')
    await admin.getByRole('link', { name: 'Tambah produk' }).click()
    await admin.getByLabel('Nama produk').fill('Celana Merah SD')
    await admin.getByLabel('Sub-kategori').click()
    await admin.getByRole('option', { name: 'Celana' }).click()
    const skus = admin.locator('fieldset')
    await skus.nth(0).getByLabel('Ukuran').fill('8')
    await skus.nth(0).getByLabel('Harga jual').fill('70000')
    await skus.nth(0).getByRole('button', { name: 'Duplikat' }).click()
    await skus.nth(1).getByLabel('Ukuran').fill('10')
    await skus.nth(1).getByLabel('Harga jual').fill('75000')
    await admin.getByRole('button', { name: 'Simpan produk' }).click()
    await expect(
      admin.getByRole('row', { name: /Celana Merah SD/ }),
    ).toContainText('Rp 70.000 – Rp 75.000')

    await admin.getByRole('link', { name: 'Celana Merah SD' }).click()
    barcode = await skus.nth(1).getByLabel('Barcode').inputValue()
    expect(barcode).toMatch(/^2\d{7}$/)
  })

  await test.step('the admin receives 12 by scanning', async () => {
    await openMenu(admin, 'Barang Masuk')
    await admin.getByRole('link', { name: 'Barang masuk baru' }).click()
    // A supplier made on the spot is picked straight away.
    await admin.getByRole('button', { name: 'Baru' }).click()
    await admin.getByLabel('Nama pemasok').fill('Toko Kain Makmur')
    await admin.getByRole('button', { name: 'Simpan' }).click()
    await expect(admin.getByLabel('Pemasok', { exact: true })).toContainText(
      'Toko Kain Makmur',
    )
    await admin.getByLabel('Tambah barang').fill(barcode)
    await admin.getByLabel('Tambah barang').press('Enter')
    await admin.getByLabel('Jumlah Celana Merah SD · 10').fill('12')
    await admin
      .getByLabel('Harga beli per pcs Celana Merah SD · 10')
      .fill('40000')
    await admin.getByRole('button', { name: 'Selesaikan' }).click()
    await admin
      .getByRole('dialog')
      .getByRole('button', { name: 'Selesaikan' })
      .click()
    await expect(admin.getByRole('heading', { name: /^BM-/ })).toBeVisible()
  })

  await test.step('the admin sees the stock and its card', async () => {
    await openMenu(admin, 'Stok')
    await admin.getByLabel('Cari stok').fill('Celana Merah')
    const row = admin.getByRole('row', { name: /Celana Merah SD · 10/ })
    await expect(row).toContainText('12 pcs')
    await expect(row).toContainText('Rp 480.000')
    await expect(
      admin.getByRole('row', { name: /Celana Merah SD · 8/ }),
    ).toContainText('0 pcs')

    await row.getByRole('link').click()
    await expect(admin.getByText('Kartu stok')).toBeVisible()
    const entry = admin.getByRole('row', { name: /BM-/ })
    await expect(entry).toContainText('+12')
    await expect(entry).toContainText('Rina Admin')
    await shot(admin, 'main-path-stock-card')
  })

  await test.step('the owner checks from a phone', async () => {
    await owner.setViewportSize({ width: 390, height: 844 })
    await owner.goto('/stok')
    await owner.getByLabel('Cari stok').fill(barcode)
    // Searching by Barcode leaves exactly that one SKU.
    await expect(owner.getByRole('row', { name: /pcs/ })).toHaveCount(1)
    await expect(
      owner.getByRole('row', { name: /Celana Merah SD · 10/ }),
    ).toContainText('12 pcs')
    await expect(owner.getByText('Nilai stok (sesuai filter)')).toBeVisible()
    await shot(owner, 'main-path-owner-phone')

    await owner.goto('/log-aktivitas')
    await expect(
      owner.getByText(/Menyelesaikan barang masuk BM-.* dari Toko Kain Makmur/),
    ).toBeVisible()
  })
})
