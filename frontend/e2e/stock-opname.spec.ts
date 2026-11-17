import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

const PHONE = { width: 390, height: 844 }

async function api(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(`/api/v1/${path}`, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

/** Two shirts with 10 in stock each at Rp 5.000, and two cashiers. */
async function setUp(owner: Page) {
  const request = owner.request
  for (const [username, name] of [
    ['tono', 'Tono Kasir'],
    ['wati', 'Wati Kasir'],
  ]) {
    await api(request, 'users/', {
      username,
      full_name: name,
      role: 'cashier',
      password: `sandi-${username}-1`,
    })
  }
  const category = await api(request, 'categories/', { name: 'Seragam Opname' })
  const withSub = await api(
    request,
    `categories/${category.id}/sub-categories`,
    { name: 'Kemeja' },
  )
  const product = await api(request, 'products/', {
    name: 'Kemeja Putih SD',
    sub_category_id: withSub.sub_categories[0].id,
    skus: [
      { size: '8', selling_price: 80000 },
      { size: '10', selling_price: 85000 },
    ],
  })
  const supplier = await api(request, 'suppliers/', { name: 'CV Opname Jaya' })
  const receipt = await api(request, 'goods-receipts/', {
    supplier_id: supplier.id,
    received_on: '2026-11-16',
    lines: product.skus.map((sku: { id: number }) => ({
      sku_id: sku.id,
      quantity: 10,
      unit_cost: 5000,
    })),
  })
  await api(request, `goods-receipts/${receipt.id}/complete`, {})
  return product.skus as { id: number; barcode: string }[]
}

async function phoneOf(
  browser: import('@playwright/test').Browser,
  username: string,
) {
  const page = await (await browser.newContext({ viewport: PHONE })).newPage()
  await page.goto('/')
  await signIn(page, username, `sandi-${username}-1`)
  await expect(
    page.getByRole('heading', { name: /^(Halo|Dasbor)/ }),
  ).toBeVisible()
  return page
}

/**
 * Slice 2 end to end: a Partial Opname is opened, two Checkers count it on
 * their phones without seeing the stock, and the Owner approves it with one
 * Company Loss and one Employee Charge; the Stock Card shows both.
 */
test('stock opname: count blind, review, approve', async ({ browser }) => {
  const owner = await (await browser.newContext()).newPage()
  await owner.goto('/')
  await signIn(owner, OWNER.username, OWNER.password)
  await expect(owner.getByRole('heading', { name: 'Dasbor' })).toBeVisible()
  const [size8, size10] = await setUp(owner)
  let number = ''

  await test.step('the owner opens a partial opname of two SKUs', async () => {
    await openMenu(owner, 'Stok Opname')
    await owner.getByRole('link', { name: 'Buka opname' }).click()
    const finder = owner.getByLabel('Tambah barang')
    for (const [n, sku] of [size8, size10].entries()) {
      await finder.fill(sku.barcode)
      await finder.press('Enter')
      await expect(owner.getByRole('main').getByRole('listitem')).toHaveCount(
        n + 1,
      )
    }
    await owner.getByLabel('Tono Kasir').check()
    await owner.getByLabel('Wati Kasir').check()
    await shot(owner, 'opname-01-open')
    await owner.getByRole('button', { name: 'Buka opname' }).click()
    await expect(owner.getByText('0 dari 2 SKU dihitung')).toBeVisible()
    number =
      (await owner.getByRole('heading', { level: 1 }).textContent()) ?? ''
    expect(number).toMatch(/^SO-\d{4}-\d{4}$/)
  })

  await test.step('two checkers count on their phones', async () => {
    const budi = await phoneOf(browser, 'tono')
    await budi
      .getByRole('link', { name: `Anda ditugaskan menghitung ${number}` })
      .click()
    // On display: 6 of size 8 typed, then 4 of size 10.
    await budi.getByLabel('Jumlah').fill('6')
    await budi.getByLabel('Barcode', { exact: true }).fill(size8.barcode)
    await budi.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(budi.getByRole('status')).toHaveText(
      'Kemeja Putih SD · 8: +6 pcs',
    )
    await expect(budi.getByLabel('Jumlah')).toHaveValue('1')
    for (let n = 0; n < 4; n++) {
      await budi.getByLabel('Barcode', { exact: true }).fill(size10.barcode)
      await budi.getByLabel('Barcode', { exact: true }).press('Enter')
      await expect(budi.getByText(`2 SKU, ${n + 2} kali hitung`)).toBeVisible()
    }
    // A label from another shop is refused and kept for the Admin.
    await budi.getByLabel('Barcode', { exact: true }).fill('8990000000001')
    await budi.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(budi.getByRole('status')).toContainText('tidak dikenal')
    // Never a System Quantity on the phone.
    await expect(budi.getByText('Sistem')).toHaveCount(0)
    await shot(budi, 'opname-02-count-phone')

    const sari = await phoneOf(browser, 'wati')
    await sari.goto('/hitung')
    await sari.getByRole('link', { name: new RegExp(number) }).click()
    // In the storeroom: 2 of size 8 found by name, 3 of size 10 scanned.
    await sari.getByLabel('Jumlah').fill('2')
    await sari.getByLabel('Barang tanpa barcode').fill('kemeja')
    await sari.getByRole('button', { name: /Kemeja Putih SD · 8/ }).click()
    await expect(sari.getByRole('status')).toHaveText(
      'Kemeja Putih SD · 8: +2 pcs',
    )
    await sari.getByLabel('Jumlah').fill('3')
    await sari.getByLabel('Barcode', { exact: true }).fill(size10.barcode)
    await sari.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(sari.getByText('2 SKU, 2 kali hitung')).toBeVisible()
    await shot(sari, 'opname-03-count-phone')
  })

  await test.step('the owner closes counting and reviews', async () => {
    await owner.reload()
    await expect(owner.getByText('2 dari 2 SKU dihitung')).toBeVisible()
    await expect(owner.getByText('8990000000001')).toBeVisible()
    await owner.getByRole('button', { name: 'Tutup penghitungan' }).click()
    await expect(owner.getByText('Peninjauan', { exact: true })).toBeVisible()
    // Size 8: 10 in the system, 8 found. Size 10: 10 and 7.
    const line8 = owner
      .getByRole('listitem')
      .filter({ hasText: 'Kemeja Putih SD · 8' })
    const line10 = owner
      .getByRole('listitem')
      .filter({ hasText: 'Kemeja Putih SD · 10' })
    await expect(line8.getByText('-2 pcs')).toBeVisible()
    await expect(line10.getByText('-3 pcs')).toBeVisible()

    await line8.getByLabel('Alasan kurang').click()
    await owner.getByRole('option', { name: 'Hilang' }).click()
    await line10.getByLabel('Alasan kurang').click()
    await owner.getByRole('option', { name: 'Hilang' }).click()
    await line10.getByLabel('Ditanggung').click()
    await owner.getByRole('option', { name: 'Ganti rugi karyawan' }).click()
    await line10.getByLabel('Karyawan').click()
    await owner.getByRole('option', { name: 'Tono Kasir' }).click()
    await expect(line10.getByLabel('Karyawan')).toHaveText('Tono Kasir')
    await shot(owner, 'opname-04-review')

    await owner.getByRole('button', { name: 'Setujui opname' }).click()
    await owner.getByRole('button', { name: 'Setujui', exact: true }).click()
    await expect(
      owner.getByText('Disetujui', { exact: true }).first(),
    ).toBeVisible()
    await expect(
      line10.getByText('Ganti rugi karyawan oleh Tono Kasir'),
    ).toBeVisible()
  })

  await test.step('the stock card and the charges show it', async () => {
    for (const [sku, change] of [
      [size8, '-2'],
      [size10, '-3'],
    ] as const) {
      await owner.goto(`/stok/${sku.id}`)
      const latest = owner.getByRole('row').nth(1)
      await expect(latest).toContainText('Stok opname')
      await expect(latest).toContainText(number)
      await expect(latest).toContainText(change)
    }
    await shot(owner, 'opname-05-stock-card')

    await openMenu(owner, 'Ganti Rugi Karyawan')
    await expect(
      owner.getByRole('button', { name: /Tono Kasir/ }),
    ).toContainText('Rp 15.000')
    await shot(owner, 'opname-06-charges')

    await owner.goto('/stok-opname')
    await owner.getByRole('link', { name: number }).click()
    await owner.getByRole('link', { name: 'Berita acara' }).click()
    await expect(
      owner.getByRole('main').getByText(`No. ${number}`),
    ).toBeVisible()
    await shot(owner, 'opname-07-berita-acara')
  })

  await test.step('the owner reviews on a phone too', async () => {
    const phone = await (
      await browser.newContext({ viewport: PHONE })
    ).newPage()
    await phone.goto('/stok-opname')
    await signIn(phone, OWNER.username, OWNER.password)
    await phone.getByRole('link', { name: number }).click()
    await expect(phone.getByText('Kemeja Putih SD · 10')).toBeVisible()
    await shot(phone, 'opname-08-review-phone')
  })
})
