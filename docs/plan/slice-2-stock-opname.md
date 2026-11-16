# Slice 2: Stock Opname

**Status: built.** Every rule below has an API test in `tests/test_opname_*.py` and `tests/test_opening_opname.py`, and the main path has a browser test (`frontend/e2e/stock-opname.spec.ts`).

**When it's done:** the shop can run its Opening Opname, count any part of its stock without closing, and the Owner can review the result on a phone, order Recounts, and decide who bears each Shortage.

Needs slice 1. Shared patterns are in [plan.md](../plan.md); the reasoning for counting while open is in [ADR 0004](../adr/0004-opname-does-not-freeze-sales.md).

## Data

- **Stock Opname:** number, Location, Scope (everything, chosen Categories, chosen Sub-categories, or a chosen list of SKUs), whether it is the Opening Opname, status, and who opened it, closed counting and approved it, with times.
- **Checker assignment:** which users count in this session.
- **Opname Line:** one per SKU in Scope. System Quantity at its first count and when that was, Physical Quantity, Variance, the "moved while counting" flag, unit cost used, and for a Shortage its Variance Resolution: reason, Company Loss or Employee Charge, the employee and the amount.
- **Count entry:** each scan or typed quantity: line, quantity, Checker, time. A Recount cancels a line's entries; it doesn't delete them.
- **Unknown barcode:** a scanned code that matches no SKU, kept for the Admin to sort out.
- **Employee Charge:** employee, amount, where it came from, outstanding or settled.

## Statuses

Counting → Review → Approved. A session can be cancelled from Counting or Review and leaves no trace in stock. An Approved session can only be reversed.

## Rules

Each one gets a test.

**Opening a session**

1. Opening creates a line for every active SKU in Scope, plus inactive SKUs that still have stock there.
2. A SKU can be in only one unfinished Stock Opname per Location at a time.

**Counting**

3. Only assigned Checkers can count. Any role can be a Checker.
4. Blind Count: until Review, nobody is shown a System Quantity or a Variance for the session, and the API doesn't send them. Progress shows only which lines are counted.
5. The first count of a SKU records its System Quantity at that moment. Later counts add to the Physical Quantity and leave that snapshot alone.
6. A scan adds 1, a typed quantity adds what was typed, and counts from different Checkers add up: 3 on display and 2 in the storeroom make 5.
7. A Barcode outside the Scope is refused with a message. An unknown barcode is refused and listed for the Admin.
8. If the SKU was sold, returned or received between its first and last count, the line is flagged "moved while counting": the count may be off, and the approver should order a Recount.
9. Counting can't be closed while a line is uncounted. Each one must be counted or confirmed as zero by the Admin.

**Review and approval**

10. The approver is an Owner or Admin who was not a Checker in this session.
11. Recount clears the line's entries and snapshot and sends that line back to Counting; the rest of the session waits in Review.
12. Every Shortage needs a reason (damaged, lost, miscounted, unknown) and a Variance Resolution before approval. Company Loss is the default.
13. Only the Owner can choose Employee Charge. It names one employee; the amount defaults to the Shortage at unit cost and the Owner can change it.
14. A Surplus is valued by costing rule 5. If the SKU has never had a cost, a unit cost must be entered before approval.
15. Nothing changes System Quantity before approval. Approval writes one Stock Movement per line that has a Variance, for the amount of the Variance, on top of whatever the System Quantity is by then. Example: snapshot 5, counted 4, one more sold before approval (system now 4): the movement is −1 and the System Quantity becomes 3.
16. Approval creates the Employee Charges and makes the session immutable.
17. Reversing an approved session writes the opposite Stock Movements and cancels its Employee Charges that are still outstanding.

**Opening Opname**

18. It can only be opened while the Location has no Stock Movements, and its Scope is always everything.
19. Every counted line needs an opening unit cost, pre-filled from the import's "last purchase cost".
20. Approval writes opening Stock Movements (and Cost Layers in FIFO Categories). They are opening stock, not Surpluses, and need no Variance Resolution.

**Everyday use**

21. Damaged stock found on the shelf is recorded with a Partial Opname of that SKU, with the reason "damaged". There is no separate write-off document.

## Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Stok Opname | Owner, Admin | Sessions with status, Scope and progress |
| Buka Opname | Owner, Admin | Choose Location, Scope and Checkers |
| Hitung | assigned Checkers | Phone screen: scan with a scanner or the phone's camera, or type a quantity; shows what this Checker has counted so far |
| Progres | Owner, Admin | Counted and uncounted lines, unknown barcodes, confirm zeros, close counting |
| Tinjau | approver | Lines with Variance in quantity and value, flags, Recount, reason and Variance Resolution, approve. Works on a phone |
| Berita Acara | Owner, Admin | Printable record of an approved session, with signature lines |
| Ganti Rugi Karyawan | Owner | Employee Charges per employee, with the outstanding total |

## Steps

1. **Open and count:** Buka Opname, Hitung, Blind Count, unknown barcodes.
2. **Progress and review:** Progres, closing counting, Tinjau with flags and Recount.
3. **Approval:** stock adjustments, Variance Resolution, Employee Charges, Reversal, Berita Acara.
4. **Opening Opname.**
5. **Browser test:** open a Partial Opname → two Checkers count → approve with one Company Loss and one Employee Charge → the Stock Card shows both adjustments.

## Decided while building

- **Numbers:** `SO-2611-0001`, given when the session opens, because Checkers see it from the start. A cancelled session keeps its number.
- **Taking back a count:** a Checker can cancel their own entries while the line can still be counted (a double scan, a wrong SKU). A line left with no entries is uncounted again and takes a fresh snapshot at its next count.
- **Confirming zero** is a Count Entry of 0 by the Admin, so it records the System Quantity the same way a count does. Lines can be confirmed one by one or all at once.
- **Items without a Barcode:** Checkers find them by name, limited to the SKUs in Scope.
- **Camera scanning** uses the browser's own barcode reader: Chrome on Android, not yet Safari on iPhone. A label held in view counts once until it has been out of view for a second.
- **Blind Count for staff who count:** an Owner or Admin who is a Checker never sees that session's System Quantities or Variances, even after counting closes.
- **Who decides what:** any Owner or Admin who did not count may review, recount, give reasons and approve. Only the Owner chooses an Employee Charge; an Admin can approve a session with the Owner's charges but not change them.
- **Values in Review are estimates.** A Shortage is estimated at the average cost; approval takes it out by the Costing Method. An Employee Charge without an amount set takes what approval actually took out, rounded to whole rupiah.
- **A Surplus of a SKU that never had a cost** sets the SKU's latest unit cost to the cost entered.
- **Reversing an approved session** works like other documents: Owner or Admin, a reason, a `BTL` number.
- **Unknown barcodes** are listed per code with how often and who scanned last. Adding the missing product is done by hand in the catalogue.
- **The Opening Opname switch** only shows while no stock has moved at the Location.

## Not in this slice

- Settling an Employee Charge (paid back or deducted from salary): slice 5.
- Suggesting a Scope from Fast-moving SKUs or ABC Class A: slice 4. Until then the SKUs are picked by hand.
- Counting by Batch: slice 6.
