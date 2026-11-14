# Slice 3: POS

**When it's done:** a Cashier sells by scanning, takes payment and prints a Receipt; returns and exchanges go through the original Receipt; each Shift's cash is counted and reconciled. Smartlink can be switched off ([ADR 0005](../adr/0005-own-pos-replaces-smartlink.md)).

Needs slices 1 and 2. Shared patterns are in [plan.md](../plan.md).

## Data

- **Shop settings:** name, address, Receipt footer, timezone, opening hours, Return Window (7 days by default).
- **Payment Method:** name, cash or non-cash, active flag. Seeded: Tunai, Transfer Bank, QRIS, Kartu.
- **Shift:** Cashier, Location, opening float, opened and closed times, expected cash, counted cash, Cash Variance and its Variance Resolution.
- **Receipt:** number, Shift, Cashier, time, kind (sale, return, exchange), the original Receipt for a return or exchange, totals, status (completed or voided), Void reason.
- **Receipt line:** SKU, quantity, the Selling Price at that moment, the Promotion applied and its discount, line total, unit COGS. A returned line also holds the original line and its condition (Resellable or Damaged).
- **Payment:** Receipt, Payment Method, amount (negative for money paid back), reference note.
- **Promotion:** name, percentage or fixed amount, value, start and end time, and its targets (SKUs, Products, Sub-categories or Categories).

## Rules

Each one gets a test.

**Shifts**

1. Selling needs an open Shift. A Location has at most one open Shift, because there is one cash drawer.
2. Closing: the Cashier enters the counted cash without being shown the expected amount. Expected cash = float + cash taken − cash given back. Cash Variance = counted − expected.
3. A negative Cash Variance waits for the Owner's Variance Resolution: Company Loss or Employee Charge. A positive one is recorded as a gain.
4. At closing all cash in the drawer is handed over; the next Shift starts with a new float.

**Selling**

5. A scan adds 1 of that SKU; scanning it again raises the quantity. A SKU can also be found by name.
6. The price is the SKU's Selling Price at that moment. The Cashier can't change a price or give a discount.
7. A Promotion applies by itself when the time is inside its period and the line's SKU is one of its targets. If several match, the biggest discount wins; they never add up, and a price never goes below zero. Example: 10% on Uniforms and Rp 5.000 off one Rp 80.000 shirt: the shirt gets 10% (Rp 8.000).
8. Payment can be split over Payment Methods and must cover the total. Change is only given from cash. A non-cash payment needs the Cashier's confirmation that the money arrived.
9. Completing a sale writes its Stock Movements and stores each line's unit COGS. Stock never blocks it; a SKU sold below zero is flagged as Negative Stock.
10. The Receipt prints its number as a barcode. A reprint is marked as a copy.

**Void**

11. A Receipt can be voided only while its Shift is open, by the Cashier who made it or the Owner, with a reason. The Void mirrors its Stock Movements and payments.

**Returns and exchanges**

12. A Customer Return starts from the original Receipt. Only its lines can come back, each up to the quantity sold minus what already came back. A voided Receipt can't be returned.
13. A return after the Return Window is refused.
14. The refund is what was paid for those units after discount. It is paid in cash unless the Cashier picks another Payment Method.
15. A Resellable Return goes back into stock at the cost it was sold at. A Damaged Return is recorded in and straight out as written off, so the Stock Card shows both.
16. An Exchange is returned lines and new lines on one Receipt. The customer pays the difference or gets it back in cash; an even swap needs no payment.

**Roles and setup**

17. A Cashier uses only the POS (and Hitung when assigned as a Checker). An Admin can't sell. The Owner can do both.
18. Promotions and Selling Prices are set by Owner or Admin. A Promotion already used on a Receipt can't be edited, only ended early.
19. Changing the Return Window affects returns made afterwards.

## Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Buka Shift | Cashier | Enter the opening float |
| Kasir | Cashier, Owner | Scan or search, lines with price and discount, total, pay |
| Bayar | Cashier, Owner | Payment Methods, amount received, change, confirm, print |
| Retur / Tukar Tambah | Cashier, Owner | Scan the Receipt, pick lines, quantity and condition; add new SKUs for an Exchange |
| Transaksi Shift | Cashier, Owner | Receipts of the open Shift: reprint, Void |
| Tutup Shift | Cashier | Count the cash, then see and print the closing summary |
| Shift | Owner, Admin | All Shifts with Cash Variance; the Owner resolves shortages |
| Promo | Owner, Admin | Create, list (running, upcoming, ended), end early |
| Metode Pembayaran | Owner | Payment Methods |
| Pengaturan Toko | Owner | Shop settings |

## Steps

1. **Shifts and setup:** Pengaturan Toko, Metode Pembayaran, Buka Shift, a first Tutup Shift.
2. **Selling:** Kasir, Bayar, stock out with COGS, Receipt printing.
3. **Promotions.**
4. **Returns and Exchanges.**
5. **Void and closing:** Transaksi Shift, closing summary, Cash Variance resolution.
6. **Browser test:** open a Shift → sell two SKUs, one under a Promotion → exchange one for another size → close the Shift with a shortage → the Owner resolves it.

## Not in this slice

- Holding a sale to serve the next customer, customer records, selling on credit.
- Payment-gateway integration, offline selling, buy-X-get-Y, VAT.
- Taking cash out of the drawer for an expense during a Shift: slice 5.
