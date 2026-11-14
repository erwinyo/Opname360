# Slice 6: Later

Two features that are decided but not needed at go-live, and the list of what is deliberately left out. Each of the two is planned in detail when its time comes.

## Medicine Batches

**When it's done:** Chinese medicine can be stocked and sold with batch numbers and expiry dates, and nothing expired is sold by accident. Start it when the client is ready to launch that Category.

- A Category can be marked as tracking Batches. Its Goods Receipt lines then need a batch number and an expiry date.
- Stock is kept per Batch. A sale takes from the Batch that expires first.
- An expired Batch can't be sold; the Cashier sees why.
- A report lists Batches expiring within 30, 60 and 90 days.
- In a Stock Opname the Checker picks the Batch after scanning, and Variances are per Batch.
- Expired stock is written off with a Partial Opname, reason "expired".

To confirm with the client first: whether selling these medicines needs a licence, and whether the supplier's packaging carries batch and expiry in a barcode.

## Switching the Costing Method

**When it's done:** the Owner can change a Category between Moving Average and FIFO from a screen ([ADR 0002](../adr/0002-costing-method-per-category.md)). Until then the method is fixed when the Category is created.

- Only the Owner can switch, and the switch takes effect the moment it is confirmed. It can't be backdated.
- FIFO → Moving Average: the remaining Cost Layers become one average.
- Moving Average → FIFO: each SKU's remaining stock becomes one Cost Layer at its current average cost.
- Stock value is the same just before and just after. Past COGS and past reports don't change.
- The switch is written to the Activity Log with the stock value at that moment.

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
