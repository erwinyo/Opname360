# Stok Opname

The Owner or Admin opens a count session (`SO-YYMM-NNNN`) over all SKUs, some Categories, or chosen SKUs, and assigns Checkers. Checkers count on their phones without ever seeing the system quantity. When counting closes, the approver reviews each difference, gives every shortage a reason, decides who bears it, and approves. Approval adjusts stock, and Kartu Stok shows the adjustment.

## Sub-features

- `opname-open` opens a session with a scope and Checkers.
- `opname-count` counts on the phone by scan, typed quantity, or name search.
- `opname-blind` never shows a system quantity to a Checker.
- `opname-unknown` records an unknown barcode for the Admin.
- `opname-review` shows each line's difference after counting closes.
- `opname-resolve` takes a shortage reason and who bears it (company or an employee).
- `opname-approve` adjusts stock and creates any employee charge.
- `opname-batch` counts medicine per Batch. See the medicine feature.

## How to get to it (user POV)

- Sidebar `Stok Opname`, then `Buka opname`.
- A Checker's home shows `Anda ditugaskan menghitung <SO number>`, or sidebar `Hitung Stok`.
- Reports such as Fast Moving and Kedaluwarsa have an "Opname …" button that opens a session for their SKUs.

## Driving it with Playwright

Preconditions:

- SKUs with stock (see [goods-receipt.md](./goods-receipt.md)).
- At least one Checker account (role `cashier` works) from `api(page.request, 'users/', …)`, signed in through its own context with a 390×844 viewport.
- None of those SKUs in another unfinished session.

- **Open.** `openMenu(page, 'Stok Opname')`, then `getByRole('link', { name: 'Buka opname' }).click()`. For each SKU, fill `getByLabel('Tambah barang')` with its barcode and press `Enter`. Tick `getByLabel('<checker full name>')`, then `getByRole('button', { name: 'Buka opname' }).click()`. Text `0 dari N SKU dihitung` and an `SO-` level-1 heading are visible.
- **Count by scan.** On the phone, `getByRole('link', { name: 'Anda ditugaskan menghitung <SO number>' }).click()`. Fill `getByLabel('Jumlah')` with `6`, then fill `getByLabel('Barcode', { exact: true })` with the barcode and press `Enter`. `getByRole('status')` reads `<sku name>: +6 pcs`.
- **Count by name.** `getByLabel('Barang tanpa barcode').fill('<part of name>')`, then `getByRole('button', { name: /<sku name>/ }).click()`.
- **Blind.** `getByText('Sistem')` has a count of `0` on the phone.
- **Close.** As the Owner, reload. Text `N dari N SKU dihitung` is visible. Click `getByRole('button', { name: 'Tutup penghitungan' })`. Text `Peninjauan` is visible.
- **Resolve.** For a line, `getByRole('listitem').filter({ hasText: '<sku name>' })` shows `-2 pcs`. In it, `getByLabel('Alasan kurang').click()`, then the option `Hilang`, `Rusak`, `Salah hitung`, `Tidak diketahui` or `Kedaluwarsa`. Optionally use `getByLabel('Ditanggung')` with `Ganti rugi karyawan`, then `getByLabel('Karyawan')`.
- **Approve.** `getByRole('button', { name: 'Setujui opname' }).click()`, then `getByRole('button', { name: 'Setujui', exact: true }).click()`. Text `Disetujui` is visible.
- **Proof.** Call `proof()` on the phone count and the review. Second view: on Kartu Stok (`/stok/<id>`) the newest row contains `Stok opname`, the SO number and the difference. Or `sql.sh "SELECT number, status FROM stock_opname ORDER BY id DESC LIMIT 1"`.

## Gotchas

- The approver must not be one of the session's Checkers. With `demo` as approver, Checkers must be other accounts.
- Counting can't close while any line is uncounted. Use `Konfirmasi nol` on the session page for lines with nothing found.
- Only the Owner may charge a shortage to an employee.
- Steps are proven in `frontend/e2e/stock-opname.spec.ts`.
