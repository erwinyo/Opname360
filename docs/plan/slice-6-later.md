# Slice 6: Later

**Status: built.** Every rule below has an API test in `tests/test_costing_switch.py`, `test_batches.py`, `test_batch_selling.py`, `test_batch_opname.py` and `test_expiry_report.py`, and the main path has a browser test (`frontend/e2e/batches.spec.ts`).

Two features that were decided but not needed at go-live, and the list of what is deliberately left out.

Needs slices 1 to 5.

## Switching the Costing Method

**When it's done:** the Owner can change a Category between Moving Average and FIFO from a screen ([ADR 0002](../adr/0002-costing-method-per-category.md)).

### Rules

1. Only the Owner can switch, and the switch takes effect the moment it is confirmed. It can't be backdated.
2. FIFO → Moving Average: the remaining Cost Layers become one average.
3. Moving Average → FIFO: each SKU's remaining stock becomes one Cost Layer at its current average cost.
4. Stock value is the same just before and just after. Past COGS and past reports don't change.
5. The switch is written to the Activity Log with the stock value at that moment.

The Category form no longer offers the method when editing. It is chosen when the Category is created and changed only by a switch.

## Medicine Batches

**When it's done:** Chinese medicine can be stocked and sold with batch numbers and expiry dates, and nothing expired is sold by accident.

### Data

- **Category:** whether it tracks Batches. This can be set when the Category is created, or later while none of its SKUs has moved.
- **Batch:** a SKU, a batch number (unique per SKU) and an expiry date.
- **Stock Movement:** for a SKU that tracks Batches, the Batch it moved. A Batch's quantity is the sum of its movements. Stock value and costing stay per SKU, exactly as now.
- **Goods Receipt line:** a batch number and an expiry date.
- **Opname line:** the Batch it counts. A SKU that tracks Batches has one line per Batch.

### Rules

6. A Goods Receipt line for a SKU that tracks Batches needs a batch number and an expiry date before it can be completed. A batch number already known for that SKU must have the same expiry date. An expired Batch can't be received.
7. Production Receipts don't take SKUs that track Batches; medicine is bought, not made.
8. A Supplier Return sends goods back from the Batch its Goods Receipt line brought in.
9. A sale takes from the Batch that expires first, then the next. A Batch is expired once the day after its expiry date begins.
10. Nothing expired is sold by accident. The till refuses a SKU that tracks Batches, with the reason, when:
    - no Batch of it is known, so its expiry is unknown;
    - every Batch of it has expired;
    - its unexpired Batches hold fewer units than the sale needs while an expired Batch still holds some, so the unit in hand may be expired.
11. Otherwise Negative Stock still never stops a sale ([ADR 0008](../adr/0008-sales-never-blocked-by-stock.md)). Units beyond what the unexpired Batches hold leave from the one that expires first.
12. A Customer Return goes back into the Batch its sale took the SKU from; if the sale took from more than one, the one that expires first. A Void and every Reversal mirror their Batches exactly.
13. Stock Opname: when a session opens, a SKU that tracks Batches gets a line for each Batch it holds or owes, or one line without a Batch if it has none. After scanning such a SKU the Checker picks the Batch, or types a new batch number and expiry date. A line without a Batch becomes the first Batch counted. Each Batch is counted, reviewed and adjusted on its own line, so Variances are per Batch.
14. Shortage reasons gain "expired" (Kedaluwarsa). Expired stock is written off by taking it off the shelf, then running a Partial Opname for those SKUs: the expired Batch counts zero and its Shortage gets this reason.
15. The expiry report lists the Batches still in stock that expire within 30, 60 or 90 days, plus those already expired, with the quantity and its value at the SKU's average cost.

### Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Kategori | Owner, Admin | "Lacak batch & kedaluwarsa" when creating a Category; the Owner's "Ganti metode HPP" |
| Barang Masuk | Owner, Admin | Batch number and expiry date on lines that need them |
| Kartu Stok | Owner, Admin | The SKU's Batches with quantity and expiry; the Batch of each movement |
| Kasir | Cashier | The reason a medicine can't be sold |
| Hitung Stok | Checker | The Batch picker after scanning a medicine |
| Tinjau opname, Berita Acara | Owner, Admin | Batch and expiry on each line |
| Kedaluwarsa | Owner, Admin | The expiry report; the Dashboard shows how many expired Batches are still in stock |

## Steps

1. **Switching the Costing Method:** the Owner's switch, the Category form, tests for rules 1 to 5.
2. **Batches in:** Category flag, Batch, Goods Receipt lines, Production Receipt and Supplier Return rules, Kartu Stok (rules 6 to 8).
3. **Selling by Batch:** sale, return, Exchange and Void at the till (rules 9 to 12).
4. **Opname by Batch:** lines per Batch, the Checker's picker, the expired reason (rules 13 and 14).
5. **Expiry report and browser test:** Kedaluwarsa, the Dashboard count (rule 15); a browser test that switches a Category's method, then receives a medicine with a Batch, sells it and finds it in the expiry report.

## Decided while building

- **A Batch nobody recorded** that turns up on the shelf during counting gets a line of its own. Lines are only added while counting is open, not once Review has begun. A known batch number must come with the expiry date already recorded for it.
- **Expired Batches are counted like any other**, so expired stock on the shelf is on record before it is written off.
- **Per Batch, costed per SKU:** the snapshot, "moved while counting" and the Variance are per Batch line; approval moves each line's Batch, and its value follows the SKU's Costing Method as before. A Shortage in one Batch and a Surplus in another of the same SKU are two adjustments.
- **The expiry report** offers 30, 60 or 90 days on screen; "within" includes the last day. A Batch is valued at its SKU's average cost, or its latest unit cost while the SKU holds none. Its expired section hands those SKUs to a new Partial Opname (rule 14). It exports to Excel like the other reports.

## Answered by the client

Questions 21 and 22 in [client-questions.md](../client-questions.md), answered on 2026-11-22: selling these medicines needs no licence, and they are bought and sold like any other goods. Batch and expiry are typed by hand at Barang Masuk; nothing is read from the supplier's barcode.

## Deliberately left out

| Left out | Build it when |
|---|---|
| Purchase orders | They want to order from Suppliers through the system, not just record arrivals |
| Bills of materials and raw-material stock | They hold fabric that also needs a Stock Opname |
| A second Location and transfers between Locations | They open a warehouse or a branch ([ADR 0001](../adr/0001-stock-tracked-per-location.md) keeps this cheap) |
| Customer records and selling on credit | Schools or other buyers start paying later |
| Offline selling | The shop's internet proves unreliable |
| Payment-gateway integration | Confirming transfers and QRIS by eye becomes a burden or a risk |
| Buy-X-get-Y and bundle Promotions | Marketing asks for them |
| VAT (PPN) | The business becomes VAT-registered |
| Holding a sale at the POS | Queues show it's needed |
| Reading batch and expiry from a barcode (GS1) | A supplier's packaging starts carrying them and typing them becomes a burden (not needed, question 22) |
