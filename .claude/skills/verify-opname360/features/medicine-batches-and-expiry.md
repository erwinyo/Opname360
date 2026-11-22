# Medicine batches and Kedaluwarsa

A Category can track batches. Its goods then arrive on Barang Masuk with a batch number and an expiry date. The till sells from the batch that expires first and refuses what may be expired. Kartu Stok shows every batch. Stock Opname counts each batch on its own line. The Kedaluwarsa report lists batches still in stock that have expired or expire within 30, 60 or 90 days, exports to Excel, and opens a write-off opname. Dasbor counts expired batches still in stock.

## Sub-features

- `batch-category` turns on "Lacak batch & kedaluwarsa" for a Category.
- `batch-receive` requires a batch number and expiry on Barang Masuk; an expired batch is refused.
- `batch-sell` sells from the batch that expires first.
- `batch-refuse` makes the till refuse, with the reason, when every batch has expired or none is known.
- `batch-card` shows each batch with its quantity and expiry on Kartu Stok.
- `batch-opname` makes the Checker pick a batch, or type a new one, after scanning a medicine.
- `expiry-report` lists batches by expiry window, with value and Excel export.
- `expiry-writeoff` opens a Partial Opname for the expired batches' SKUs from the report.
- `expiry-dashboard` shows "N batch kedaluwarsa masih ada stoknya" on Dasbor.

## How to get to it (user POV)

- Sidebar `Kategori`: create a Category with the switch `Lacak batch & kedaluwarsa`.
- Sidebar `Barang Masuk`: batch inputs appear under medicine lines.
- Sidebar `Kasir`: sell by barcode as usual.
- `/stok/<sku id>`: the `Batch` section of Kartu Stok.
- Sidebar `Laporan` › `Kedaluwarsa`.
- Sidebar `Hitung Stok` on the Checker's phone.

## Driving it with Playwright

Preconditions:

- Through the API: `categories/` with `{ name, tracks_batches: true }`, a sub-category, `products/` with `skus: [{ selling_price: 35000, stock_unit: 'botol' }]`, and `suppliers/`.
- No Shift open.
- `journeys/medicine-expiry.spec.ts` covers `batch-receive`, `batch-sell`, `batch-card` and `expiry-report`. Run it with `scripts/drive.sh medicine-expiry`.

- **Receive.** On Barang Masuk, add the SKU, then fill `getByLabel('Jumlah <name>')` with `10` and `getByLabel('Harga beli per botol <name>')` with `20000`. Fill `getByLabel('Nomor batch <name>')` with a number and `getByLabel('Tanggal kedaluwarsa <name>')` with a date `YYYY-MM-DD` (`daysFromToday(20)`). Complete with `Selesaikan` twice. A `BM-` heading appears.
- **Sell.** Open a Shift, scan, `Bayar`, `Uang pas`, `Selesai`, then close the Shift (see [pos-till.md](./pos-till.md)).
- **Refusal.** With only expired stock, scan the medicine at Kasir. The line still enters the cart, but a red paragraph under `Total` gives the server's reason, naming the expired batch, and `getByRole('button', { name: 'Bayar' })` stays disabled.
- **Kartu Stok.** `page.goto('/stok/<sku id>')`. `getByRole('listitem').filter({ hasText: '<batch>' })` contains `9 botol` and `Sampai <date>`, or `Kedaluwarsa <date>` in red.
- **Report.** `openMenu(page, 'Kedaluwarsa')`, `getByLabel('Kedaluwarsa dalam').click()`, then `getByRole('option', { name: 'Dalam 30 hari' }).click()`. Wait for the heading `Kedaluwarsa dalam 30 hari`. `getByRole('row', { name: /<name>/ })` contains the batch, `20 hari lagi`, `9 botol` and `Rp 180.000`. `getByRole('link', { name: 'Excel' })` has an href ending `reports/expiry/excel?days=30`.
- **Write-off.** With an expired batch in stock, the section `Sudah kedaluwarsa` and the button `Opname barang ini` appear. Clicking it opens `Buka opname` with those SKUs chosen.
- **Opname picker.** On the phone, scan the medicine. A panel `Batch yang mana?` lists the batches as buttons named by number. Click one, or fill `getByPlaceholder('No. batch')` and `getByLabel('Tanggal kedaluwarsa')` and click `Hitung batch ini`. `getByRole('status')` reads `<name> (batch <number>): +N botol`.
- **Proof.** `journeys/medicine-expiry.spec.ts` saves `01-receipt-filled`, `02-receipt-completed`, `03-sale-done`, `04-stock-card` and `05-expiry-report`. Its second view is `api(page.request, 'stock/skus/<id>/card')`, whose `batches` hold `[batch, 9]`. Or use `sql.sh "SELECT b.number, sum(m.quantity) FROM batch b JOIN stock_movement m ON m.batch_id = b.id GROUP BY b.number"`.

## Gotchas

- Batch numbers are stored in upper case: typing `kj-01` shows `KJ-01`.
- An expired batch can't be received, so a journey can't create expired stock through screens or the API. To test refusal, write-off or the Dasbor count, the journey fails at that precondition, and this line records why. pytest covers those rules (`tests/test_batch_selling.py`, `test_batch_opname.py`, `test_expiry_report.py`) by moving the date in the database.
- The report shows the previous window's rows until the new ones load. Wait for the heading `Kedaluwarsa dalam N hari` before asserting.
- "Within N days" counts from the shop's date (WIB) and includes day N.
- Excel downloads need a signed-in session. Check the link's href rather than fetching the file in the browser.
