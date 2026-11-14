# Slice 5: Ledger

**When it's done:** every stock, sales, opname and cash event is in double-entry books without anyone typing a journal; the Admin records Cash-outs and pays Suppliers; the Owner reads a Profit and Loss and a Balance Sheet in T layout.

Needs slices 1 to 4. The reasoning is in [ADR 0003](../adr/0003-built-in-double-entry-ledger.md). New words used below: an **account** is one line of the chart of accounts; a **journal entry** is one balanced set of debits and credits; **posting** is writing the journal entry for a document.

## Data

- **Account:** code, name, type (asset, liability, equity, revenue, COGS, expense), whether it is a cash or bank account, whether the system posts to it, active flag.
- **Journal entry** and its **lines:** number, time, description, the document it came from, debit and credit per account. A line on Accounts Payable names the Supplier; one on Employee Receivable names the employee.
- **System accounts:** which account plays each role below (Inventory, Sales, COGS and so on).
- **Cash-out:** number, date, paid from which cash or bank account, expense account, amount, description, paid to whom.
- **Cash transfer:** from one cash or bank account to another.
- **Supplier payment:** Supplier, the owed Goods Receipts it pays, amount, paid from which account.
- **Employee Charge settlement:** paid back in cash, or deducted from salary.
- **Lock date:** nothing can be posted on or before it.

## Chart of accounts

A preset for an Indonesian retail shop, which the Owner can extend. Accounts the system posts to can be renamed but not deleted.

| Type | Preset accounts |
|---|---|
| Asset | Kas Besar, Kas Kasir, Bank, Persediaan, Piutang Karyawan |
| Liability | Hutang Usaha |
| Equity | Modal, Prive, Saldo Awal, Laba Ditahan |
| Revenue | Penjualan, Diskon Penjualan, Retur Penjualan, Pendapatan Lain, Selisih Lebih Persediaan, Selisih Lebih Kas |
| COGS | Harga Pokok Penjualan |
| Expense | Selisih Kurang Persediaan, Barang Rusak, Selisih Kurang Kas, Biaya Produksi Dibebankan, Gaji, Sewa, Listrik dan Air, Perlengkapan, Biaya Lain |

## Automatic postings

| Event | Debit | Credit |
|---|---|---|
| Goods Receipt, paid | Persediaan | the cash or bank account paid from |
| Goods Receipt, owed | Persediaan | Hutang Usaha |
| Supplier payment | Hutang Usaha | cash or bank |
| Supplier Return | Hutang Usaha, or cash if already paid (at the receipt's cost) | Persediaan (at stock cost); any difference to Harga Pokok Penjualan |
| Production Receipt | Persediaan | Biaya Produksi Dibebankan |
| Sale | Kas Kasir or the Payment Method's bank account; Diskon Penjualan | Penjualan |
| ...and its cost | Harga Pokok Penjualan | Persediaan |
| Resellable Return | Retur Penjualan; Persediaan | cash or bank; Harga Pokok Penjualan |
| Damaged Return | Retur Penjualan; Barang Rusak | cash or bank; Harga Pokok Penjualan |
| Void | the sale's entries, mirrored | |
| Shortage, Company Loss | Selisih Kurang Persediaan | Persediaan |
| Shortage, Employee Charge | Piutang Karyawan (the amount charged); Selisih Kurang Persediaan (any part not charged) | Persediaan |
| Surplus | Persediaan | Selisih Lebih Persediaan |
| Opening Opname | Persediaan | Saldo Awal |
| Negative Stock filled (costing rule 6) | Harga Pokok Penjualan | Persediaan (or the other way round) |
| Shift opened | Kas Kasir | Kas Besar |
| Shift closed | Kas Besar (counted cash); Selisih Kurang Kas (if short) | Kas Kasir; Selisih Lebih Kas (if over) |
| Cash shortage, Employee Charge | Piutang Karyawan | Selisih Kurang Kas |
| Cash-out | the expense account | the cash or bank account |
| Cash transfer | the receiving account | the paying account |
| Employee Charge settled | cash, or Gaji when deducted from salary | Piutang Karyawan |

Money paid for making goods (fabric, tailor) is a Cash-out to Biaya Produksi Dibebankan, the same account a Production Receipt credits. When the costs typed on Production Receipts match what was really paid, that account nets to zero; what remains shows how far off they were.

## Rules

Each one gets a test.

1. Every journal entry balances: debits equal credits. An unbalanced entry can't be saved.
2. Journal entries are never edited or deleted. A document's Reversal posts the mirror entry.
3. Completing a document and posting its journal entry happen together or not at all.
4. Each row of the postings table produces exactly those lines, for a worked example.
5. Backfill: when the Ledger is switched on, every document completed before it is posted in the order it happened, each dated when it happened. Running it twice posts nothing twice.
6. After backfill, Persediaan equals the total stock value in the Stok screen, and it stays equal after every later document.
7. For any day, Penjualan, Diskon Penjualan, Retur Penjualan and Harga Pokok Penjualan in the Ledger give the same gross profit as the slice 4 reports.
8. Kas Kasir is zero whenever no Shift is open.
9. A Cash-out paid from Kas Kasir during a Shift lowers that Shift's expected cash.
10. A supplier payment can't exceed what is owed on the Goods Receipts it pays; a fully paid receipt shows as paid.
11. Opening balances (cash, bank, debts, capital on the day the books start) are entered once against Saldo Awal; stock comes from the Opening Opname, not from here.
12. Nothing can be posted on or before the lock date. Only the Owner moves it.
13. Balance Sheet: assets equal liabilities plus equity on any date. Profit of earlier years shows as Laba Ditahan and this year's as Laba Tahun Berjalan, worked out when the report runs; there is no year-end closing entry.
14. Profit and Loss for a period: net sales, COGS, gross profit, expenses by account, other income, net profit.
15. Admin and Owner record and read everything here; only the Owner changes the system accounts, the lock date, and a Payment Method's account. Cashiers see none of it.

## Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Akun | Owner, Admin | Chart of accounts |
| Pengaturan Akun | Owner | System accounts; the account behind each Payment Method |
| Saldo Awal | Owner | Opening balances |
| Kas Keluar | Owner, Admin | Cash-outs |
| Pindah Kas | Owner, Admin | Cash transfers, e.g. depositing cash at the bank |
| Bayar Hutang | Owner, Admin | Owed Goods Receipts per Supplier; pay them |
| Ganti Rugi Karyawan | Owner | Adds settling to the slice 2 screen |
| Jurnal Umum | Owner, Admin | Manual journal entries for everything else (capital, withdrawals, depreciation) |
| Jurnal | Owner, Admin | Every journal entry, with a link to its document |
| Buku Besar | Owner, Admin | One account's entries with a running balance |
| Neraca Saldo | Owner, Admin | Trial balance |
| Laba Rugi | Owner, Admin | Profit and Loss for a period |
| Neraca | Owner, Admin | Balance Sheet in T layout on a date |
| Hutang Usaha | Owner, Admin | What is owed per Supplier and receipt |
| Tutup Periode | Owner | Lock date |

Laba Rugi and Neraca print and export to Excel.

## Steps

1. **Books:** accounts with the preset, journal entries (balanced, immutable, reversible), Jurnal Umum, Jurnal, Buku Besar, Neraca Saldo.
2. **Stock postings and backfill:** Goods Receipt, Production Receipt, Supplier Return, Stock Opname.
3. **POS postings:** sales, returns, Exchanges, Voids, Shifts; Payment Method accounts.
4. **Cash and debts:** Kas Keluar, Pindah Kas, Bayar Hutang, Employee Charge settlement, Saldo Awal.
5. **Statements:** Laba Rugi, Neraca, Hutang Usaha, Tutup Periode.
6. **Browser test:** receive goods on credit → sell some → record a Cash-out → pay the Supplier → Laba Rugi and Neraca show the expected figures and the Neraca balances.

## Not in this slice

- VAT (PPN), fixed-asset registers, payroll, bank reconciliation, a cash-flow statement, budgets.
- Receivables from customers: every sale is paid at the counter.
