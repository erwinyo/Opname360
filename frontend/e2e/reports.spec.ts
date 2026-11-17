import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

async function api(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(`/api/v1/${path}`, { data })
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

/** A cashier, and a Rp 1.000.000 jacket with 5 in stock at Rp 600.000. */
async function setUp(owner: Page): Promise<string> {
  const request = owner.request
  await api(request, 'users/', {
    username: 'yanti',
    full_name: 'Yanti Kasir',
    role: 'cashier',
    password: 'sandi-yanti-1',
  })
  const category = await api(request, 'categories/', {
    name: 'Jaket Laporan',
  })
  const withSub = await api(
    request,
    `categories/${category.id}/sub-categories`,
    { name: 'Almamater' },
  )
  const product = await api(request, 'products/', {
    name: 'Jaket Almamater',
    sub_category_id: withSub.sub_categories[0].id,
    skus: [{ size: 'L', selling_price: 1000000 }],
  })
  const supplier = await api(request, 'suppliers/', {
    name: 'CV Laporan Jaya',
  })
  const receipt = await api(request, 'goods-receipts/', {
    supplier_id: supplier.id,
    received_on: '2026-11-16',
    lines: [{ sku_id: product.skus[0].id, quantity: 5, unit_cost: 600000 }],
  })
  await api(request, `goods-receipts/${receipt.id}/complete`, {})
  return product.skus[0].barcode
}

const digits = new Intl.NumberFormat('id-ID')
const rupiah = (amount: number) => `Rp ${digits.format(amount)}`
/** The rupiah amount in a text: "… -Rp 1.500" -> -1500. */
function amountOf(text: string): number {
  const [, sign, amount] = /(-?)Rp ([\d.]+)/.exec(text) ?? ['', '', '0']
  return Number(sign + amount.replaceAll('.', ''))
}

/** This hour in the shop, as the chart's bars are named: "16.00–17.00". */
function shopHour(): string {
  const hour = Number(
    new Intl.DateTimeFormat('en-GB', {
      hour: 'numeric',
      hourCycle: 'h23',
      timeZone: 'Asia/Jakarta',
    }).format(new Date()),
  )
  const label = (h: number) => `${String(h).padStart(2, '0')}.00`
  return `${label(hour)}–${label(hour + 1)}`
}

/**
 * Slice 4 end to end: the Owner watches the dashboard on a phone while a
 * Cashier sells; the totals and this hour's bar change without a reload.
 */
test('reports: the dashboard follows a sale live', async ({ browser }) => {
  const owner = await (
    await browser.newContext({ viewport: { width: 390, height: 844 } })
  ).newPage()
  await owner.goto('/')
  await signIn(owner, OWNER.username, OWNER.password)
  await expect(owner.getByRole('heading', { name: 'Dasbor' })).toBeVisible()
  const barcode = await setUp(owner)

  const netSales = owner.getByTestId('net-sales')
  const grossProfit = owner.getByTestId('gross-profit')
  const thisHour = owner.locator(`rect[aria-label^="${shopHour()}"]`)
  const before = {
    net: amountOf(await netSales.innerText()),
    profit: amountOf(await grossProfit.innerText()),
    hour: (await thisHour.count())
      ? amountOf((await thisHour.getAttribute('aria-label')) ?? '')
      : 0,
  }
  await shot(owner, 'reports-01-dashboard')

  await test.step('a cashier sells the jacket at the till', async () => {
    const till = await (
      await browser.newContext({ viewport: { width: 1280, height: 800 } })
    ).newPage()
    await till.goto('/')
    await signIn(till, 'yanti', 'sandi-yanti-1')
    await expect(till.getByRole('heading', { name: /^Halo/ })).toBeVisible()
    await openMenu(till, 'Kasir')
    await till.getByLabel('Modal kas').fill('100000')
    await till.getByRole('button', { name: 'Buka shift' }).click()
    await till.getByLabel('Barcode', { exact: true }).fill(barcode)
    await till.getByLabel('Barcode', { exact: true }).press('Enter')
    await expect(till.getByText('Rp 1.000.000').last()).toBeVisible()
    await till.getByRole('button', { name: 'Bayar' }).click()
    await till.getByRole('button', { name: 'Uang pas' }).click()
    await till.getByRole('button', { name: 'Selesai' }).click()
    await expect(till.getByRole('link', { name: /^PJ-/ })).toBeVisible()
  })

  await test.step('the dashboard changes without a reload', async () => {
    await expect(netSales).toHaveText(rupiah(before.net + 1000000), {
      timeout: 10000,
    })
    await expect(grossProfit).toHaveText(rupiah(before.profit + 400000))
    await expect(thisHour).toHaveAttribute(
      'aria-label',
      `${shopHour()}: penjualan bersih ${rupiah(before.hour + 1000000)}`,
    )
    await shot(owner, 'reports-02-after-sale')
  })

  await test.step('class A opens an opname of its SKUs', async () => {
    await owner.goto('/laporan/kontribusi-omzet')
    await expect(owner.getByRole('tab', { name: /Kelas A/ })).toBeVisible()
    await shot(owner, 'reports-03-abc')
    await owner.getByRole('button', { name: 'Opname dari Kelas A' }).click()
    await expect(
      owner.getByRole('heading', { name: 'Buka stok opname' }),
    ).toBeVisible()
    await expect(owner.getByText('Jaket Almamater · L')).toBeVisible()
  })

  await test.step('Penjualan downloads as Excel', async () => {
    await owner.goto('/laporan/penjualan')
    const download = owner.waitForEvent('download')
    await owner.getByRole('link', { name: 'Excel' }).click()
    expect((await download).suggestedFilename()).toMatch(
      /^penjualan-.+-day\.xlsx$/,
    )
  })
})
