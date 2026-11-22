# Kasir

A Cashier, or the Owner, opens a Shift with a cash float, scans items into a cart, takes payment, and prints a Receipt (`PJ-YYMM-NNNN`). Promotions apply automatically. Returns and exchanges start from a Receipt number. The Shift closes with a blind count of the drawer, and any shortfall waits for the Owner's decision.

## Sub-features

- `shift-open` opens a Shift with `Modal kas`.
- `sale-scan` adds items by barcode; scanning again raises the quantity.
- `sale-pay` takes cash with change, exact cash, or another method.
- `sale-promo` shows an active promotion's discount in the cart.
- `return-exchange` returns or exchanges items from a Receipt (`TT-…`, `RJ-…`).
- `shift-close` closes with a blind cash count; `Sesuai` or `Kurang Rp …`.
- `medicine-refusal` refuses a medicine with expired or unknown batches. See the medicine feature.

## How to get to it (user POV)

- Sidebar `Kasir` (Owner and Cashier). Admins have no till.
- On the till, the links `Retur / Tukar`, `Transaksi` and `Tutup shift`.

## Driving it with Playwright

Preconditions:

- A SKU with stock (see [goods-receipt.md](./goods-receipt.md), or create it through the API: `products/`, `suppliers/`, `goods-receipts/` with `{ supplier_id, received_on, lines: [{ sku_id, quantity, unit_cost }] }`, then `goods-receipts/<id>/complete`).
- No Shift open on the drawer.
- For a Cashier, an account from `api(page.request, 'users/', { … role: 'cashier' })` and a separate browser context.

- **Open Shift.** `openMenu(page, 'Kasir')`, `getByLabel('Modal kas').fill('200000')`, then `getByRole('button', { name: 'Buka shift' }).click()`. Text matching `/^Shift SH-\d{4}-\d{4}/` is visible.
- **Scan.** `getByLabel('Barcode', { exact: true }).fill(barcode)`, then `.press('Enter')`. `getByLabel('Jumlah <sku name>')` has the value `1`.
- **Pay cash.** `getByRole('button', { name: 'Bayar' }).click()`, then `getByRole('button', { name: 'Rp 200.000' })` or `{ name: 'Uang pas' }`, then `getByRole('button', { name: 'Selesai' }).click()`. Text `Kembali Rp …` and a link matching `/^PJ-/` are visible.
- **Exchange.** `getByRole('link', { name: 'Retur / Tukar' }).click()`. Fill `getByLabel('Nomor struk')` with the `PJ-` number and press `Enter`. Fill `getByLabel('Jumlah retur <sku name>')` with `1`, scan the replacement, then `Bayar` and `Uang pas` and `Selesai`. A link matching `/^TT-/` is visible.
- **Close Shift.** `getByRole('link', { name: 'Tutup shift' }).click()`, fill `getByLabel('Uang tunai di laci')`, click `getByRole('button', { name: 'Tutup shift' })`, then the dialog's `Tutup shift`. Text `Sesuai`, or `Kurang Rp …` for a short drawer, is visible.
- **Proof.** Call `proof()` on the cart, the payment result and the closed Shift. Second view: Kartu Stok shows the sale (`Penjualan`), or `sql.sh "SELECT number, total, status FROM receipt ORDER BY id DESC LIMIT 3"`.

## Gotchas

- Always close the Shift before the journey ends. An open Shift blocks every later journey's `Buka shift`.
- The expected drawer is the float plus cash taken minus change and refunds. A wrong count gives `Kurang` or `Lebih`, which is a result, not a crash.
- Selling with too little stock is allowed (Negative Stock), except for medicine.
- Steps are proven in `frontend/e2e/pos.spec.ts`.
