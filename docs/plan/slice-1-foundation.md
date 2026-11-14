# Slice 1: Foundation

**When it's done:** staff sign in with their own accounts, the catalogue is in the system with a Barcode on every SKU, goods can be received, and anyone in the back office can see current stock and each SKU's Stock Card.

Shared patterns (documents, costing rules, security) are in [plan.md](../plan.md).

## Data

- **User:** username, full name, password hash, role (Owner, Admin, Cashier), active flag. No email. **Session** rows, so deactivating a user signs them out at once.
- **Activity Log:** who, when, what action, on which document.
- **Category** (with its Costing Method), **Sub-category**, **Product**.
- **SKU:** code, size, colour (both optional text), Barcode, Stock Unit, Purchase Pack name and size, Selling Price, latest unit cost, active flag. **Selling Price history:** price, who changed it, when.
- **Location:** seeded with one, "Toko".
- **Stock Movement:** append-only. SKU, Location, signed quantity, unit cost, reason, source document, quantity and stock value after it, who, when.
- **Stock balance:** quantity and stock value per SKU and Location, updated in the same transaction as the movement, under a row lock.
- **Cost Layer:** per receipt, for FIFO Categories only.
- **Supplier:** name, phone, address, active flag.
- **Goods Receipt**, **Production Receipt**, **Supplier Return:** each with lines, a document number, a date, a note, and a status (draft → completed → reversed). A Goods Receipt also records the Supplier, the Supplier's invoice number, and "paid" or "owed". A Supplier Return points at the Goods Receipt it sends goods back from.

## Rules

Each one gets a test.

1. Only the Owner manages users. Cashiers can do nothing in this slice. Admin and Owner do everything else.
2. A deactivated user is signed out at once and can't sign in. The last active Owner can't be deactivated.
3. A Barcode belongs to exactly one SKU. A SKU without a manufacturer Barcode gets a generated one.
4. A Category can't be deleted while it has Products; a SKU with Stock Movements can't be deleted, only made inactive.
5. Changing a Selling Price keeps the old price in the history with who changed it and when.
6. A draft document can be edited. Completing it writes its Stock Movements; from then on it can't be edited or deleted, only reversed.
7. Goods Receipt: a line entered as 2 boxes of 12 at Rp 60.000 per box becomes 24 pcs at Rp 5.000.
8. Moving Average: receiving 10 at Rp 5.000 then 10 at Rp 6.000 gives an average of Rp 5.500. FIFO: the same receipts stay two Cost Layers, used oldest first.
9. Supplier Return: can't return more than that Goods Receipt brought in, minus earlier returns.
10. A Reversal writes the opposite Stock Movements and links both documents. If the goods are already gone, the SKU goes into Negative Stock and is flagged.
11. Goods arriving for a SKU in Negative Stock fill the gap first (costing rule 6).
12. Two documents completed at the same moment for the same SKU leave the correct balance.
13. Every create, complete and reverse appears in the Activity Log.
14. Import: a file with any invalid row imports nothing, and the preview lists every problem by row.

## Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Masuk | all | Sign in |
| Pengguna | Owner | Add staff, set role, deactivate, reset password |
| Kategori | Owner, Admin | Categories with Costing Method, Sub-categories |
| Produk | Owner, Admin | Search and filter; Product form with its SKUs (size, colour, Barcode, unit, pack, price) |
| Cetak Label | Owner, Admin | Pick SKUs and copies, print Code 128 labels with name, size and price |
| Impor Produk | Owner, Admin | Download the Excel template, upload, preview errors, import. The template has a "last purchase cost" column, used later as the opening cost in the Opening Opname |
| Pemasok | Owner, Admin | Suppliers |
| Barang Masuk | Owner, Admin | Goods Receipts: scan to add lines, save draft, complete, reverse |
| Hasil Produksi | Owner, Admin | Production Receipts, same pattern |
| Retur Pembelian | Owner, Admin | Pick a Goods Receipt, choose lines and quantities to send back |
| Stok | Owner, Admin | Quantity and value per SKU, filter by Category and Sub-category, Negative Stock highlighted |
| Kartu Stok | Owner, Admin | Stock Card for one SKU |
| Log Aktivitas | Owner | Activity Log |

## Steps

Each step ends with something to open in the browser.

1. **Base:** PostgreSQL, Alembic, test setup; React app served by FastAPI; sign-in with lockout, roles, first Owner created by a setup command, Pengguna screen. The placeholder `Item` is removed.
2. **Catalogue:** Kategori and Produk screens, Barcodes, Selling Price with history.
3. **Stock core and Goods Receipt:** Stock Movements, balances, both Costing Methods, Pemasok, Barang Masuk, Stok, Kartu Stok.
4. **Other documents:** Hasil Produksi, Retur Pembelian, Reversals, Log Aktivitas.
5. **Labels and import:** Cetak Label, Impor Produk.
6. **Browser test** of the main path: sign in → create a Product with SKUs → receive goods → see the Stock Card.

## Not in this slice

- Paying off what's owed to a Supplier. A Goods Receipt only records "paid" or "owed"; settling debts comes with the Ledger (slice 5).
- Selling, counting, reports, journal entries.
- Hosting. Everything runs locally until this slice works. FastAPI Cloud (`uv run fastapi deploy`) is the first candidate for the app, as the fastapi skill recommends; where the PostgreSQL database lives is decided at the same time.
