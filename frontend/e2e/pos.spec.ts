import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

async function api(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(`/api/v1/${path}`, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

type Sku = { id: number; barcode: string; size: string }

/** A cashier, and polo shirts in sizes S and M with 10 each in stock. */
async function setUp(owner: Page) {
  const request = owner.request
  await api(request, 'users/', {
    username: 'rina',
    full_name: 'Rina Kasir',
    role: 'cashier',
    password: 'sandi-rina-1',
  })
  const category = await api(request, 'categories/', { name: 'Seragam POS' })
  const withSub = await api(
    request,
    `categories/${category.id}/sub-categories`,
    { name: 'Kaos' },
  )
  const product = await api(request, 'products/', {
    name: 'Kaos Olahraga',
    sub_category_id: withSub.sub_categories[0].id,
    skus: [
      { size: 'S', selling_price: 60000 },
      { size: 'M', selling_price: 65000 },
    ],
  })
  const supplier = await api(request, 'suppliers/', { name: 'CV Kasir Jaya' })
  const receipt = await api(request, 'goods-receipts/', {
    supplier_id: supplier.id,
    received_on: '2026-11-16',
    lines: product.skus.map((sku: Sku) => ({
      sku_id: sku.id,
      quantity: 10,
      unit_cost: 40000,
    })),
  })
  await api(request, `goods-receipts/${receipt.id}/complete`, {})
  return product.skus as Sku[]
}

async function scan(page: Page, code: string) {
  await page.getByLabel('Barcode', { exact: true }).fill(code)
  await page.getByLabel('Barcode', { exact: true }).press('Enter')
}

/**
 * Slice 3 end to end: a Cashier opens a Shift, sells, and closes it with a
 * blind cash count.
 */
test('pos: open a shift, sell, close', async ({ browser }) => {
  const owner = await (await browser.newContext()).newPage()
  await owner.goto('/')
  await signIn(owner, OWNER.username, OWNER.password)
  await expect(owner.getByRole('heading', { name: /^Halo/ })).toBeVisible()
  const [small, medium] = await setUp(owner)

  const till = await (
    await browser.newContext({ viewport: { width: 1280, height: 800 } })
  ).newPage()
  await till.goto('/')
  await signIn(till, 'rina', 'sandi-rina-1')
  await expect(till.getByRole('heading', { name: /^Halo/ })).toBeVisible()

  await test.step('the cashier opens a shift', async () => {
    await openMenu(till, 'Kasir')
    await till.getByLabel('Modal kas').fill('200000')
    await shot(till, 'pos-01-open-shift')
    await till.getByRole('button', { name: 'Buka shift' }).click()
    await expect(till.getByText(/^Shift SH-\d{4}-\d{4}/)).toBeVisible()
  })

  await test.step('scans two shirts and takes cash', async () => {
    await scan(till, small.barcode)
    await scan(till, small.barcode)
    await scan(till, medium.barcode)
    await expect(till.getByLabel('Jumlah Kaos Olahraga · S')).toHaveValue('2')
    await expect(till.getByText('Rp 185.000').last()).toBeVisible()
    await shot(till, 'pos-02-cart')
    await till.getByRole('button', { name: 'Bayar' }).click()
    await till.getByRole('button', { name: 'Rp 200.000' }).click()
    await expect(till.getByText('Kembali')).toBeVisible()
    await shot(till, 'pos-03-pay')
    await till.getByRole('button', { name: 'Selesai' }).click()
    await expect(till.getByText('Kembali Rp 15.000')).toBeVisible()
    await shot(till, 'pos-04-done')
    await till.getByRole('link', { name: /^PJ-/ }).click()
    await expect(till.getByText('Rp 120.000')).toBeVisible()
    await shot(till, 'pos-04-receipt')
    await till.getByRole('button', { name: 'Kembali' }).click()
  })

  await test.step('closes the shift with a blind count', async () => {
    await till.getByRole('link', { name: 'Tutup shift' }).click()
    await till.getByLabel('Uang tunai di laci').fill('380000')
    await till.getByRole('button', { name: 'Tutup shift' }).click()
    await till
      .getByRole('dialog')
      .getByRole('button', { name: 'Tutup shift' })
      .click()
    await expect(till.getByText('Kurang Rp 5.000')).toBeVisible()
    await shot(till, 'pos-05-closed')
  })
})
