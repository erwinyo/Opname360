# Barang Masuk and stock

The Admin or Owner records goods arriving from a Supplier, by scanning or searching for items. Each line has a quantity, in pieces or in purchase packs, and a buying price. Completing the receipt adds the stock and gives it a number (`BM-YYMM-NNNN`). A draft changes nothing. Stok lists every SKU's quantity and value, and Kartu Stok lists one SKU's movements.

## Sub-features

- `gr-scan` adds a line by scanning a barcode; scanning again adds one more.
- `gr-pack` switches a line to purchase packs (for example box of 12).
- `gr-complete` completes the receipt and increases stock.
- `gr-draft` saves a draft that leaves stock unchanged.
- `stock-list` shows quantity and value per SKU on Stok.
- `stock-card` shows the receipt as a movement on Kartu Stok.

## How to get to it (user POV)

- Sidebar `Barang Masuk`, then the link `Barang masuk baru`.
- Sidebar `Stok`, then a SKU's name to open its Kartu Stok (`/stok/<sku id>`).
- Sidebar `Pemasok` to add a Supplier first.

## Driving it with Playwright

Preconditions:

- A Category, Sub-category, product and Supplier. Create them through the API: `categories/` with `{ name }`, `categories/<id>/sub-categories` with `{ name }`, `products/` with `{ name, sub_category_id, skus: [{ selling_price, purchase_pack_name: 'box', purchase_pack_size: 12 }] }`, and `suppliers/` with `{ name }`. Read the SKU's `barcode` from the product response.

- **Start.** `openMenu(page, 'Barang Masuk')`, then `getByRole('link', { name: 'Barang masuk baru' }).click()`.
- **Supplier.** `getByLabel('Pemasok', { exact: true }).click()`, then `getByRole('option', { name: <supplier> }).click()`. Optionally fill `getByLabel('No. faktur pemasok')`.
- **Scan.** `getByLabel('Tambah barang').fill(barcode)`, then `.press('Enter')`. `getByLabel('Jumlah <product name>')` has the value `1`. Scan again and it becomes `2`.
- **Packs and price.** `getByLabel('Satuan <name>').click()`, then `getByRole('option', { name: 'box (12 pcs)' }).click()`. Fill `getByLabel('Harga beli per box <name>')` with `60000`. The total `Rp 120.000` is visible.
- **Complete.** `getByRole('button', { name: 'Selesaikan' }).click()`. The dialog says `senilai Rp 120.000`. Click `getByRole('dialog').getByRole('button', { name: 'Selesaikan' })`. A heading matching `/^BM-\d{4}-\d{4}$/` appears.
- **Stock.** `openMenu(page, 'Stok')`. `getByRole('row', { name: /<name>/ })` contains `24 pcs` and `Rp 120.000`.
- **Kartu Stok.** Click the SKU's link. `getByRole('row', { name: /BM-/ })` contains `Barang masuk` and `+24`.
- **Draft.** Fill a new receipt, then `getByRole('button', { name: 'Simpan draf' }).click()`. Stok is unchanged.
- **Proof.** Call `proof()` on the filled form, the completed receipt and Kartu Stok. Second view: `sql.sh "SELECT number, status FROM goods_receipt ORDER BY id DESC LIMIT 3"`.

## Gotchas

- Line labels use the SKU's display name, `Product · size, color`. A SKU with no size or colour is just the product name.
- The buying-price label follows the unit chosen: `Harga beli per pcs <name>` or `per box`.
- A completed receipt can't be edited. Undo it with a Reversal from its page.
- Medicine lines also need a batch number and expiry date before `Selesaikan` works. See [medicine-batches-and-expiry.md](./medicine-batches-and-expiry.md).
- Steps are proven in `frontend/e2e/receiving.spec.ts`.
