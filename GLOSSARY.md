# Opname360

Stock, sales and bookkeeping for one retail business selling uniforms, non-uniform clothing, stationery and (later) Chinese medicine, run day to day by staff while the owner is away from the shop. Terms are English; `_ID_` gives the word used in the shop and the Indonesian UI.

## People

**Owner**:
The business owner, not present in the shop, who reads reports and approves Stock Opname results remotely.
_ID_: Pemilik

**Admin**:
Back-office staff who receives goods, records production and cash-out, and runs Stock Opname sessions.
_ID_: Admin

**Cashier**:
Staff who sells, takes returns and handles cash and bank payments at the counter; cannot receive or adjust stock.
_ID_: Kasir
_Avoid_: POS account

Every staff member signs in as themselves with exactly one of these roles; there are no shared accounts.

**Checker**:
A staff member assigned to count SKUs in a Stock Opname.
_ID_: Checker, petugas opname
_Avoid_: Counter (confused with the shop counter), auditor

**Supplier**:
A business the shop buys goods from.
_ID_: Pemasok, supplier

## Catalogue

**Product**:
A named thing the shop sells, grouping its sizes and colours, e.g. "Kemeja Putih SD". Never stocked or sold directly; its SKUs are.
_ID_: Produk, barang

**SKU**:
One sellable variant of a Product (e.g. Kemeja Putih SD, size 10): the unit that is stocked, counted, priced and sold.
_Avoid_: Item, variant, article

**Barcode**:
The scannable code that identifies exactly one SKU: the manufacturer's code when it has one, otherwise a label the shop prints.

**Category**:
The top-level grouping of Products: Uniform (Seragam), Non-Uniform (Non-Seragam), Stationery (ATK), Chinese Medicine (Obat China).
_ID_: Kategori, divisi
_Avoid_: Division

**Sub-category**:
The second and last grouping level, under a Category, e.g. Uniform → Hats, Ties, Accessories, Mosquito Nets.
_ID_: Sub-kategori

**Stock Unit**:
The single unit a SKU is stocked, counted and sold in: pcs, set, meter.
_ID_: Satuan
_Avoid_: UOM

**Purchase Pack**:
A larger unit a SKU may be bought in, converting to Stock Units on receipt (1 box = 12 pcs). A pack sold whole is its own SKU, not a Purchase Pack.
_ID_: Satuan beli (box, lusin, rim)

**Fast-moving SKU**:
A SKU ranked high by units sold over the last 30 days.
_ID_: Barang fast moving

**ABC Class**:
A SKU's share of revenue over a period: A makes up the top 80%, B the next 15%, C the rest.
_ID_: Kontribusi omzet
_Avoid_: Pareto class, tier

## Stock

**Location**:
A physical place where stock is kept and counted. The business starts with one: the shop.
_ID_: Lokasi

**Stock Movement**:
A single change to the quantity of one SKU at one Location, with its reason (sale, receipt, production, return, opname adjustment).
_ID_: Mutasi stok
_Avoid_: Mutation, transaction

**Stock Card**:
The chronological list of Stock Movements for one SKU at one Location, with the running balance.
_ID_: Kartu stok

**System Quantity**:
How many of a SKU are at a Location according to the recorded Stock Movements.
_ID_: Stok komputer, stok sistem
_Avoid_: Book stock

**Physical Quantity**:
How many of a SKU were actually found when counted.
_ID_: Stok fisik

**Stock Value**:
What the System Quantity of a SKU at a Location cost, according to its Costing Method.
_ID_: Nilai stok, nilai persediaan

**Goods Receipt**:
Goods from a Supplier entering stock, each SKU at its unit cost, either paid on the spot or owed to the Supplier.
_ID_: Barang masuk, penerimaan barang
_Avoid_: Purchase order (not used), purchase

**Supplier Return**:
Goods sent back to the Supplier they were received from.
_ID_: Retur pembelian

**Production Receipt**:
Finished goods made by or for the business entering stock at a unit cost the Admin enters.
_ID_: Barang jadi masuk, hasil produksi

**Shop Day**:
00:00 to 24:00 in the shop's timezone; the unit of daily reports.
_ID_: Hari

**Negative Stock**:
A System Quantity below zero, because a sale was recorded before its goods were received. Flagged to the Owner, never blocked.
_ID_: Stok minus

## Selling

**Selling Price**:
The one price a SKU sells for before any Promotion. Only the Owner or Admin changes it.
_ID_: Harga jual

**Promotion**:
A percentage or fixed-amount discount on chosen SKUs, Products, Categories or Sub-categories for a set period, applied automatically; when several apply, the biggest wins.
_ID_: Promo, diskon
_Avoid_: Voucher, discount code

**Shift**:
One Cashier's working period at the cash drawer, opened with a cash float and closed with a blind cash count. Sales happen only inside an open Shift.
_ID_: Shift kasir

**Float**:
The cash put in the drawer when a Shift opens.
_ID_: Modal kas

**Cash Variance**:
Counted cash minus expected cash at Shift close, where expected cash is the Float plus cash taken minus cash given back.
_ID_: Selisih kas

**Payment Method**:
A way a customer pays (cash, bank transfer, QRIS, card), each tied to one cash or bank account.
_ID_: Metode pembayaran

**Receipt**:
The record of one completed POS transaction, identified by a number printed as a barcode.
_ID_: Struk, nota

**Customer Return**:
A SKU from a Receipt brought back within the Return Window: either a Resellable Return, which goes back into stock, or a Damaged Return, which is written off.
_ID_: Retur penjualan; retur tipe A (resellable), retur tipe B (damaged)

**Return Window**:
The number of days after a sale during which a Customer Return is accepted.
_ID_: Batas waktu retur

**Exchange**:
A Customer Return and a new sale in one transaction, settling only the price difference either way.
_ID_: Tukar tambah
_Avoid_: Trade-in

**Void**:
Cancelling a Receipt within its own open Shift, with a reason. After the Shift closes, only a Customer Return can undo a sale.
_ID_: Batal, void

## Records

**Reversal**:
A new document that cancels the effect of a completed document and points to it. Completed documents are never edited or deleted.
_ID_: Dokumen pembatalan
_Avoid_: Edit, delete, correction

**Activity Log**:
The record of who did what and when, readable by the Owner.
_ID_: Log aktivitas

## Costing

**Cost Layer**:
A quantity of one SKU that entered stock together at one unit cost: one receipt or one production batch.

**Costing Method**:
The rule that turns Cost Layers into COGS: Moving Average or FIFO. Set per Category; a switch affects only what happens after it.
_ID_: Metode HPP

**COGS**:
The cost of the SKUs sold, as computed by the Costing Method.
_ID_: HPP (Harga Pokok Penjualan)
_Avoid_: Modal, cost price

**Batch**:
For medicine: a quantity of one SKU sharing a batch number and expiry date. The earliest-expiring Batch is sold first.
_ID_: Batch, nomor batch

## Stock Opname

**Stock Opname**:
A session in which Checkers count the SKUs in its Scope; once approved, its Variances correct the System Quantity.
_ID_: Stok opname
_Avoid_: Stock take, stock count, audit

**Scope**:
The SKUs a Stock Opname covers: all of them, one Category, or a chosen list.

**Partial Opname**:
A Stock Opname whose Scope is less than all SKUs, typically the Fast-moving SKUs or ABC Class A.
_ID_: Opname parsial

**Opening Opname**:
The full Stock Opname at go-live whose Physical Quantities become the opening stock, since no earlier figure is trusted.
_ID_: Opname awal

**Opname Line**:
One SKU counted in a Stock Opname, holding the System Quantity at the moment it was counted and the Physical Quantity.

**Blind Count**:
Counting without being shown the System Quantity.

**Count Entry**:
One scan or typed quantity by one Checker, adding to an Opname Line's Physical Quantity.
_ID_: Hitungan

**Moved While Counting**:
The mark on an Opname Line whose SKU was sold, returned or received between its first and last Count Entry, so its count may be off.
_ID_: Bergerak saat dihitung

**Variance**:
Physical Quantity minus the System Quantity on the Opname Line. Negative is a Shortage, positive a Surplus.
_ID_: Selisih (kurang / lebih)

**Recount**:
Clearing an Opname Line so it is counted again.
_ID_: Hitung ulang

**Variance Resolution**:
The approver's decision on a Shortage or a negative Cash Variance, with a reason: Company Loss or Employee Charge.

**Company Loss**:
A Shortage the business absorbs as an expense.
_ID_: Kerugian perusahaan

**Employee Charge**:
A Shortage that a named employee owes back to the business.
_ID_: Ganti rugi karyawan, piutang karyawan

## Accounting

**Ledger**:
The business's double-entry books, into which stock, sales, opname and cash events post automatically.
_ID_: Buku besar

**Account**:
One line of the chart of accounts, e.g. Kas Besar, Persediaan, Penjualan.
_ID_: Akun

**Journal Entry**:
One balanced set of debits and credits in the Ledger, written for one document.
_ID_: Jurnal

**Posting**:
Writing the Journal Entry for a completed document. It happens by itself; staff type a Journal Entry only for what no document covers.

**Opening Balance**:
What the business had in cash, bank, debts and capital on the day the Ledger starts. Opening stock comes from the Opening Opname instead.
_ID_: Saldo awal

**Lock Date**:
The date on or before which nothing more can be posted.
_ID_: Tutup periode

**Cash Transfer**:
Money moved from one cash or bank Account to another, e.g. depositing cash at the bank.
_ID_: Pindah kas

**Supplier Payment**:
Money paid to a Supplier for Goods Receipts that were owed.
_ID_: Bayar hutang

**Settlement**:
An employee clearing an Employee Charge, by paying it back or by deduction from salary.
_ID_: Pelunasan ganti rugi

**Net Sales**:
Price times quantity, minus discounts and refunds, over a period. Voided Receipts count for nothing; a return counts when it happens.
_ID_: Penjualan bersih
_Avoid_: Omzet for this figure when discounts or refunds matter, revenue

**Gross Profit**:
Net Sales minus COGS. No expenses are taken off.
_ID_: Laba kotor
_Avoid_: Profit, laba (alone)

**Balance Sheet**:
Assets, liabilities and equity at a date, shown in T-account layout.
_ID_: Neraca (bentuk T)

**Profit and Loss**:
Revenue minus COGS and expenses over a period. Hourly figures stop at gross profit (sales minus COGS); expenses only appear per day or longer.
_ID_: Laba rugi

**Cash-out**:
Money paid out of a cash or bank account for an expense, recorded by the Admin.
_ID_: Kas keluar
