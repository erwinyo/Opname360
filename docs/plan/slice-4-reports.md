# Slice 4: Reports

**Status: built.** Every rule below has an API test in `tests/test_daily_stock.py`, `test_sales_reports.py`, `test_product_reports.py` and `test_variance_reports.py`, and the main path has a browser test (`frontend/e2e/reports.spec.ts`), which also opens an opname from Class A and downloads an Excel file.

**When it's done:** the Owner opens a phone anywhere and sees today's sales and gross profit hour by hour as they happen, what's in stock, what sells, and where stock went missing.

Needs slices 1 to 3. This slice adds no new business records: every figure is worked out from Stock Movements, Receipts and Stock Opnames. Charts follow the `dataviz` skill.

## Reports

| Report | Shows |
|---|---|
| **Dasbor** | Today so far: net sales, gross profit, number of Receipts; a chart of sales, COGS and gross profit per hour over the shop's opening hours; things needing attention |
| **Laporan Stok Harian** | For one Shop Day, per SKU: opening quantity, in, out, closing quantity, closing value at cost. Grouped by Category and Sub-category with subtotals |
| **Penjualan** | Net sales for a period by day, Cashier, Payment Method or Category, down to the single Receipt |
| **Laba Kotor per Jam** | The dashboard's hourly figures for any chosen day |
| **Fast Moving** | SKUs ranked by units sold, with revenue and current stock |
| **Kontribusi Omzet** | ABC Class per SKU for a period: revenue, share, running share, class; totals per class |
| **Selisih Opname** | Variances over a period: by SKU, by reason, by Variance Resolution, in quantity and value |

"Things needing attention" on the dashboard: SKUs in Negative Stock, Voids today, Stock Opnames waiting for approval, Shortages and Cash Variances waiting for a Variance Resolution.

## Rules

Each one gets a test.

1. Net sales = price × quantity − discounts − refunds. A voided Receipt counts for nothing.
2. A return counts in the hour and day it happens, not on the day of the original sale.
3. Gross profit = net sales − COGS. Expenses are not in any report of this slice, and the screens say "laba kotor", never "laba".
4. The 24 hourly figures of a day add up to that day's figures in Penjualan.
5. Daily stock: opening + in − out = closing, for every SKU and every subtotal, and one day's closing is the next day's opening.
6. Closing value is the stock value after the SKU's last Stock Movement of that day.
7. Days and hours are the shop's, in its timezone.
8. The dashboard shows a completed sale, return or Void within seconds, without reloading.
9. Fast Moving ranks by units sold minus units returned over the last 30 days; the period can be changed.
10. ABC Class: SKUs are sorted by net revenue; A runs until the running share reaches 80% (the SKU that crosses the line is still A), B until 95%, C is the rest, including SKUs with no sales.
11. "Opname dari Kelas A" opens Buka Opname with those SKUs already chosen; the same from Fast Moving.
12. Every table exports to Excel with the same numbers as on screen.
13. The Owner and the Admin see every report and the dashboard. A Cashier sees none.

## Screens (Indonesian)

One screen per report above, all usable on a phone. Each has a period or date picker, filters for Category and Sub-category where they apply, and an Excel button.

## Steps

1. **Daily stock:** Laporan Stok Harian with Excel export.
2. **Sales and the live dashboard:** Penjualan, Laba Kotor per Jam, Dasbor with live updates.
3. **What sells:** Fast Moving, Kontribusi Omzet, and opening a Partial Opname from either.
4. **Opname results and alerts:** Selisih Opname, the dashboard's attention list.
5. **Browser test:** the Owner has the dashboard open → a Cashier completes a sale → the hourly chart and totals change without a reload.

## Decided while building

- **Where sales figures come from:** completed Receipts, at the time each was made. COGS is the value of the Receipt's Stock Movements, exactly what the Ledger posts (slice 5). A return takes back the cost it was sold at, Resellable or Damaged; writing off a Damaged Return is a stock loss, not COGS (the Ledger books it to Barang Rusak).
- **Negative Stock cost adjustments** (costing rule 6), and their Reversals, are COGS in the hour they are booked, as the Ledger will book them. A voided Receipt's adjustments count for nothing.
- **Groupings:** a Cashier's or a Payment Method's row stops at Net Sales; COGS belongs to goods. A Payment Method shows what it took, net of change and refunds. In Penjualan by Category, a Receipt with lines in two Categories counts in both, with only that Category's lines as its amount.
- **Laporan Stok Harian** lists every SKU that had moved by the end of the day, including those back at zero, for the shop's first Location. Subtotals add quantities as they are, whatever the unit.
- **Hours shown:** the chart and the hourly tables show the shop's opening hours plus any other hour with sales. The API always gives all 24.
- **The Dasbor is the home page** of the Owner and the Admin (the menu says Dasbor instead of Beranda). Cashiers keep their greeting.
- **Live updates:** an open dashboard keeps a server-sent event stream open. The server looks at the Activity Log every 2 seconds and only says "something changed"; the dashboard then reloads its figures through the normal, role-checked endpoint. A sale shows on the Owner's phone in about 2 seconds.
- **The hourly chart** is a stacked bar per hour: HPP below, laba kotor above, so the bar is as tall as Net Sales. A negative part hangs below the line. Blue and orange from the dataviz skill's reference palette, validated on the white card. Every bar has a tooltip and keyboard focus, and the dashboard can switch the chart to a table.
- **Fast Moving** shows the top 50, with each SKU's System Quantity now. **Kontribusi Omzet** counts active SKUs that sold nothing as C; a SKU whose returns outweigh its sales is C too. Both default to the last 30 days.
- **Opname from a report** hands its SKUs to Buka Opname, with a note saying where they came from; the Admin still chooses the Checkers.
- **Selisih Opname** takes Stock Opnames approved in the period and not reversed; the Opening Opname is not a Variance. Values are what approval actually moved. A Surplus has no reason or resolution, so it is its own row, "Selisih lebih".
- **Things needing attention:** a Shortage gets its Variance Resolution when its opname is approved, so "Shortages waiting" shows as Stock Opnames waiting for approval. Each item links to its list, already filtered.
- **Excel files** are made on the server by the same functions as the screens, money rounded to whole rupiah the way the screens round.
- **Supplier Returns:** the difference a Supplier Return books to Harga Pokok Penjualan (its refund at the receipt's cost against stock's cost) counts in COGS when it is completed, and back when it is reversed, so the gross profit here matches the Ledger (slice 5, rule 7).

## Not in this slice

- Net profit after expenses, and the Balance Sheet: slice 5.
- Reorder suggestions, slow-stock reports, sales targets.
