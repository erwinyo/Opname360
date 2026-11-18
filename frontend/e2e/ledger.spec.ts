import { expect, test } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

async function api(request: APIRequestContext, path: string, data?: object) {
  const response = data
    ? await request.post(`/api/v1/${path}`, { data })
    : await request.get(`/api/v1/${path}`)
  expect(response.ok(), await response.text()).toBe(true)
  return response.json()
}

const digits = new Intl.NumberFormat('id-ID')
const rupiah = (amount: number) => `Rp ${digits.format(amount)}`

function shopToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta' }).format(
    new Date(),
  )
}

/**
 * Slice 5 end to end: goods bought on credit, some sold, a Cash-out and
 * the Supplier paid; Laba Rugi shows them and the Neraca balances.
 */
test('ledger: buy on credit, sell, spend, pay, read the books', async ({
  page,
}) => {
  await page.goto('/')
  await signIn(page, OWNER.username, OWNER.password)
  await expect(page.getByRole('heading', { name: 'Dasbor' })).toBeVisible()
  const request = page.request
  const today = shopToday()

  // 20 cash books at Rp 30.000 on credit; an expense account of our own.
  const category = await api(request, 'categories/', { name: 'Buku Ledger' })
  const withSub = await api(
    request,
    `categories/${category.id}/sub-categories`,
    { name: 'Buku Kas' },
  )
  const product = await api(request, 'products/', {
    name: 'Buku Kas Besar',
    sub_category_id: withSub.sub_categories[0].id,
    skus: [{ selling_price: 50000 }],
  })
  const sku = product.skus[0]
  const supplier = await api(request, 'suppliers/', { name: 'CV Pembukuan' })
  const draft = await api(request, 'goods-receipts/', {
    supplier_id: supplier.id,
    received_on: today,
    payment_status: 'owed',
    lines: [{ sku_id: sku.id, quantity: 20, unit_cost: 30000 }],
  })
  const receipt = await api(request, `goods-receipts/${draft.id}/complete`, {})
  await api(request, 'ledger/accounts', {
    code: '6206',
    name: 'Biaya Kebersihan',
    type: 'expense',
  })
  const before = await api(
    request,
    `ledger/profit-and-loss?start=${today}&end=${today}`,
  )

  await test.step('three are sold for cash', async () => {
    const current = await (await request.get('/api/v1/shifts/current')).json()
    const opened = current
      ? null
      : await api(request, 'shifts/', { opening_float: 100000 })
    const lines = [{ sku_id: sku.id, quantity: 3 }]
    const quote = await api(request, 'receipts/quote', { lines })
    const methods = await api(request, 'payment-methods/')
    const cash = methods.find((m: { name: string }) => m.name === 'Tunai')
    await api(request, 'receipts/', {
      lines,
      payments: [{ payment_method_id: cash.id, amount: quote.total }],
      expected_total: quote.total,
    })
    // Leave the drawer as found: the next spec opens its own Shift.
    if (opened) {
      const shift = await api(request, `shifts/${opened.id}`)
      await api(request, `shifts/${opened.id}/close`, {
        counted_cash: shift.expected_cash,
      })
    }
  })

  await test.step('a Cash-out for cleaning', async () => {
    await openMenu(page, 'Kas Keluar')
    await page.getByRole('button', { name: 'Catat kas keluar' }).click()
    await page.getByLabel('Jumlah').fill('75000')
    await page.getByLabel('Dibayar dari').click()
    await page.getByRole('option', { name: '1101 Kas Besar' }).click()
    await page.getByLabel('Untuk (akun biaya)').click()
    await page.getByRole('option', { name: '6206 Biaya Kebersihan' }).click()
    await page.getByLabel('Keterangan').fill('Sabun dan pel')
    await shot(page, 'ledger-01-cash-out')
    await page.getByRole('button', { name: 'Simpan' }).click()
    await expect(page.getByText('Sabun dan pel')).toBeVisible()
  })

  await test.step('the Supplier is paid in full', async () => {
    await openMenu(page, 'Bayar Hutang')
    await page.getByRole('combobox', { name: 'Pemasok' }).click()
    await page
      .getByRole('option', { name: `CV Pembukuan · ${rupiah(600000)}` })
      .click()
    await expect(page.getByRole('link', { name: receipt.number })).toBeVisible()
    await page.getByRole('button', { name: 'Lunas' }).click()
    await expect(page.getByText(`Total bayar ${rupiah(600000)}`)).toBeVisible()
    await shot(page, 'ledger-02-pay')
    await page.getByRole('button', { name: 'Bayar', exact: true }).click()
    await expect(page.getByText(/^Pembayaran BH-/)).toBeVisible()
    await openMenu(page, 'Hutang Usaha')
    await expect(
      page.getByRole('heading', { name: 'Hutang Usaha' }),
    ).toBeVisible()
    await expect(page.getByText('CV Pembukuan')).toHaveCount(0)
  })

  await test.step('Laba Rugi shows the sale and the expense', async () => {
    await openMenu(page, 'Laba Rugi')
    const statement = page.locator('main')
    await expect(
      statement.getByText('Biaya Kebersihan', { exact: true }).locator('..'),
    ).toContainText(rupiah(75000))
    await expect(
      statement.getByText('Penjualan bersih', { exact: true }).locator('..'),
    ).toContainText(rupiah(Number(before.net_sales) + 150000))
    await shot(page, 'ledger-03-profit-and-loss')
  })

  await test.step('the Neraca balances', async () => {
    await openMenu(page, 'Neraca')
    const assets = page
      .locator('main')
      .getByText('Total aset', { exact: true })
      .locator('..')
      .locator('dd')
    const other = page
      .locator('main')
      .getByText('Total kewajiban dan ekuitas', { exact: true })
      .locator('..')
      .locator('dd')
    await expect(assets).toBeVisible()
    expect(await assets.innerText()).toBe(await other.innerText())
    await shot(page, 'ledger-04-balance-sheet')
  })
})
