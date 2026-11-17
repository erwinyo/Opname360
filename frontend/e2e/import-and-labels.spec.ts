import { readFileSync, writeFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { OWNER, openMenu, shot, signIn } from './helpers'

const fixture = (name: string) => `${import.meta.dirname}/fixtures/${name}`

test('import products from Excel, then print their labels', async ({
  page,
}) => {
  await page.goto('/produk')
  await signIn(page, OWNER.username, OWNER.password)

  await test.step('the template downloads', async () => {
    await page.getByRole('link', { name: 'Impor dari Excel' }).click()
    const download = page.waitForEvent('download')
    await page.getByRole('link', { name: 'Unduh template' }).click()
    expect((await download).suggestedFilename()).toBe(
      'template-impor-produk.xlsx',
    )
  })

  await test.step('a file with mistakes is refused, row by row', async () => {
    await page
      .getByLabel('File Excel')
      .setInputFiles(fixture('katalog-salah.xlsx'))
    await expect(
      page.getByRole('heading', { name: /2 masalah ditemukan/ }),
    ).toBeVisible()
    await expect(page.getByRole('row', { name: /2 Harga jual/ })).toContainText(
      'Wajib diisi.',
    )
    await expect(page.getByRole('row', { name: /3 Barcode/ })).toContainText(
      '777 sudah dipakai di baris 2.',
    )
    await shot(page, 'import-problems')
  })

  await test.step('a correct file imports', async () => {
    await page
      .getByLabel('File Excel')
      .setInputFiles(fixture('katalog-benar.xlsx'))
    await expect(page.getByText('SKU siap diimpor.')).toContainText(
      '2 produk dengan 4 SKU',
    )
    await expect(
      page.getByText('Kategori baru: Perlengkapan Asrama, Non-Seragam'),
    ).toBeVisible()
    await shot(page, 'import-preview')
    await page.getByRole('button', { name: 'Impor 4 SKU' }).click()
    await expect(page.getByRole('heading', { name: 'Selesai' })).toBeVisible()
    await page.getByRole('link', { name: 'Lihat produk' }).click()
    await expect(
      page.getByRole('row', { name: /Kelambu Tidur/ }),
    ).toContainText('Rp 65.000 – Rp 85.000')
  })

  await test.step('print labels for one product', async () => {
    await page.getByRole('link', { name: 'Kaos Olahraga' }).click()
    await expect(
      page.getByRole('heading', { name: 'Kaos Olahraga' }),
    ).toBeVisible()
    await page.getByRole('link', { name: 'Cetak label', exact: true }).click()
    await expect(
      page.getByRole('heading', { name: 'Cetak Label' }),
    ).toBeVisible()
    await page.getByLabel('Jumlah label Kaos Olahraga · M, Biru').fill('3')
    await expect(
      page.getByRole('button', { name: 'Cetak 4 label' }),
    ).toBeVisible()
    // On screen: the preview. In print: the same four labels.
    await expect(page.locator('#root [data-label]')).toHaveCount(4)
    await expect(page.locator('#root [data-label]').first()).toContainText(
      'Rp 55.000',
    )
    await shot(page, 'labels')

    await page.emulateMedia({ media: 'print' })
    const pdf = await page.pdf({ preferCSSPageSize: true })
    await page.emulateMedia({ media: 'screen' })
    const folder = process.env.E2E_SHOTS
    if (folder) writeFileSync(`${folder}/labels.pdf`, pdf)
    const text = pdf.toString('latin1')
    expect(text.match(/\/Type\s*\/Page[^s]/g) ?? []).toHaveLength(4)
    // Every page is one 50 x 30 mm label: about 141.7 x 85 points.
    const box = text.match(/\/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)/)
    expect(Number(box?.[1])).toBeCloseTo(141.7, 0)
    expect(Number(box?.[2])).toBeCloseTo(85, 0)
  })

  await test.step('labels for a whole delivery, one per unit', async () => {
    const supplier = await (
      await page.request.post('/api/v1/suppliers/', {
        data: { name: 'CV Kaos Nusantara' },
      })
    ).json()
    const products = await (
      await page.request.get('/api/v1/products/', {
        params: { search: 'Kaos Olahraga' },
      })
    ).json()
    const [small] = products.items[0].skus
    const draft = await (
      await page.request.post('/api/v1/goods-receipts/', {
        data: {
          supplier_id: supplier.id,
          received_on: '2026-11-15',
          lines: [{ sku_id: small.id, quantity: 6, unit_cost: 30000 }],
        },
      })
    ).json()
    await page.request.post(`/api/v1/goods-receipts/${draft.id}/complete`)

    await page.goto(`/barang-masuk/${draft.id}`)
    await expect(page.getByRole('heading', { name: /^BM-/ })).toBeVisible()
    await page.getByRole('link', { name: 'Cetak label', exact: true }).click()
    await expect(
      page.getByRole('button', { name: 'Cetak 6 label' }),
    ).toBeVisible()
    await openMenu(page, 'Cetak Label')
    await expect(
      page.getByRole('button', { name: 'Cetak 0 label' }),
    ).toBeDisabled()
  })
})

// Keeps the fixtures honest: they must be real Excel files.
test('fixtures are xlsx files', () => {
  for (const name of ['katalog-benar.xlsx', 'katalog-salah.xlsx']) {
    expect(readFileSync(fixture(name)).subarray(0, 2).toString()).toBe('PK')
  }
})
