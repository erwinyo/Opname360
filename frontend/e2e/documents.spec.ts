import { expect, test } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

const BARCODE = '8990000000123'

/** A shirt SKU, a supplier, and a completed receipt of 10 at Rp 5.000. */
async function seed(request: APIRequestContext) {
  const category = await (
    await request.post('/api/v1/categories/', { data: { name: 'Seragam SMP' } })
  ).json()
  const withSub = await (
    await request.post(`/api/v1/categories/${category.id}/sub-categories`, {
      data: { name: 'Kemeja' },
    })
  ).json()
  const product = await (
    await request.post('/api/v1/products/', {
      data: {
        name: 'Kemeja Putih SMP',
        sub_category_id: withSub.sub_categories[0].id,
        skus: [{ size: 'M', barcode: BARCODE, selling_price: 95000 }],
      },
    })
  ).json()
  const supplier = await (
    await request.post('/api/v1/suppliers/', {
      data: { name: 'PT Konveksi Jaya' },
    })
  ).json()
  const draft = await (
    await request.post('/api/v1/goods-receipts/', {
      data: {
        supplier_id: supplier.id,
        received_on: '2026-11-15',
        lines: [{ sku_id: product.skus[0].id, quantity: 10, unit_cost: 5000 }],
      },
    })
  ).json()
  const receipt = await (
    await request.post(`/api/v1/goods-receipts/${draft.id}/complete`)
  ).json()
  return { skuId: product.skus[0].id as number, receipt }
}

test('return goods, cancel documents, record production', async ({
  page,
}) => {
  await page.goto('/')
  await signIn(page, OWNER.username, OWNER.password)
  await expect(page.getByRole('heading', { name: /Halo/ })).toBeVisible()
  const { skuId, receipt } = await seed(page.request)
  let returnNumber = ''

  await test.step('return 3 shirts from the receipt', async () => {
    await page.goto(`/barang-masuk/${receipt.id}`)
    await page.getByRole('link', { name: 'Retur ke pemasok' }).click()
    const amount = page.getByLabel('Jumlah retur Kemeja Putih SMP · M')
    await amount.fill('11')
    await expect(page.getByText('Paling banyak 10 pcs.')).toBeVisible()
    await amount.fill('3')
    await page.getByLabel('Alasan atau catatan').fill('Jahitan lepas')
    await expect(page.getByText('Rp 15.000')).toBeVisible()
    await shot(page, 'return-form')
    await page.getByRole('button', { name: 'Selesaikan' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Selesaikan' })
      .click()
    const heading = page.getByRole('heading', { name: /^RB-\d{4}-\d{4}$/ })
    await expect(heading).toBeVisible()
    returnNumber = (await heading.textContent()) ?? ''
    await shot(page, 'return-view')
  })

  await test.step('a receipt with a return cannot be cancelled', async () => {
    await page.goto(`/barang-masuk/${receipt.id}`)
    await expect(page.getByRole('row', { name: /Kemeja/ })).toContainText(
      '3 pcs',
    )
    await page.getByRole('button', { name: 'Batalkan' }).click()
    await page.getByLabel('Alasan').fill('Salah pemasok')
    await page.getByRole('button', { name: 'Batalkan dokumen' }).click()
    await expect(page.getByRole('dialog').getByRole('alert')).toContainText(
      `sudah diretur (${returnNumber})`,
    )
    await page.getByRole('button', { name: 'Batal', exact: true }).click()
  })

  await test.step('cancel the return, then the receipt', async () => {
    await openMenu(page, 'Retur Pembelian')
    await page.getByRole('link', { name: returnNumber }).click()
    await page.getByRole('button', { name: 'Batalkan' }).click()
    await page.getByRole('button', { name: 'Batalkan dokumen' }).click()
    await expect(page.getByText('Tulis alasan pembatalan.')).toBeVisible()
    await page.getByLabel('Alasan').fill('Pemasok menolak retur')
    await page.getByRole('button', { name: 'Batalkan dokumen' }).click()
    await expect(page.getByRole('note')).toContainText('Pemasok menolak retur')
    await expect(page.getByText('Dibatalkan', { exact: true })).toBeVisible()

    await page.goto(`/barang-masuk/${receipt.id}`)
    await page.getByRole('button', { name: 'Batalkan' }).click()
    await page.getByLabel('Alasan').fill('Salah pemasok')
    await page.getByRole('button', { name: 'Batalkan dokumen' }).click()
    await expect(page.getByRole('note')).toContainText('Salah pemasok')
    await expect(page.getByRole('button', { name: 'Batalkan' })).toHaveCount(0)
    await shot(page, 'receipt-reversed')
  })

  await test.step('the stock card shows every step, ending at zero', async () => {
    await page.goto(`/stok/${skuId}`)
    await expect(page.getByText('0 pcs').first()).toBeVisible()
    await expect(page.getByRole('row', { name: /Pembatalan/ })).toHaveCount(2)
    await expect(page.getByRole('row', { name: /Retur pembelian/ })).toHaveCount(
      1,
    )
    await shot(page, 'stock-card-reversals')
  })

  await test.step('record shirts made by a tailor', async () => {
    await openMenu(page, 'Hasil Produksi')
    await page.getByRole('link', { name: 'Hasil produksi baru' }).click()
    await page.getByLabel('Catatan').fill('Penjahit Bu Ani')
    await page.getByLabel('Tambah barang').fill(BARCODE)
    await page.getByLabel('Tambah barang').press('Enter')
    await page.getByLabel('Jumlah Kemeja Putih SMP · M').fill('20')
    await page.getByLabel('Biaya per pcs Kemeja Putih SMP · M').fill('45000')
    await expect(page.getByText('Rp 900.000').first()).toBeVisible()
    await page.getByRole('button', { name: 'Selesaikan' }).click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Selesaikan' })
      .click()
    await expect(
      page.getByRole('heading', { name: /^HP-\d{4}-\d{4}$/ }),
    ).toBeVisible()
    await shot(page, 'production-view')

    await page.goto(`/stok/${skuId}`)
    await expect(page.getByText('20 pcs')).toBeVisible()
    await expect(page.getByText('Rp 900.000').first()).toBeVisible()
  })

  await test.step('the owner sees it all in the activity log', async () => {
    await openMenu(page, 'Log Aktivitas')
    await expect(
      page.getByText(`Membatalkan barang masuk ${receipt.number}`),
    ).toBeVisible()
    await expect(
      page.getByText(`Membatalkan retur pembelian ${returnNumber}`),
    ).toBeVisible()
    await shot(page, 'activity-log')
  })
})
