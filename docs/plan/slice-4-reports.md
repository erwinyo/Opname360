# Slice 4: Reports

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

## Not in this slice

- Net profit after expenses, and the Balance Sheet: slice 5.
- Reorder suggestions, slow-stock reports, sales targets.
