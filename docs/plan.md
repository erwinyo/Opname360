# Build plan

Status: **agreed, not started.** Vocabulary is in [GLOSSARY.md](../GLOSSARY.md), decisions in [adr/](adr/), open client questions in [client-questions.md](client-questions.md).

## How the work runs

- Work happens on a branch per slice (`slice-1-foundation`), one commit per step. Merging to `main` is the owner's call.
- Work stops after every step so the result can be opened in the browser before the next step starts.

## Slices

Each slice works end to end (API, screens, tests) before the next starts.

| # | Slice | What the shop can do when it's done |
|---|---|---|
| 1 | Foundation | Sign in, set up the catalogue, print barcode labels, receive goods, see stock and the Stock Card |
| 2 | Stock Opname | Run the Opening Opname and Partial Opnames, approve Variances |
| 3 | POS | Sell, return, exchange, take payments, run Shifts and Promotions, print Receipts |
| 4 | Reports | Daily stock report, live hourly Profit and Loss, Fast-moving SKUs, ABC Class |
| 5 | Ledger | Chart of accounts, automatic journal entries, Cash-out, supplier debts, Profit and Loss, Balance Sheet |
| 6 | Later | Medicine Batches, screen for switching the Costing Method |

Only slice 1 is planned in detail below. Each later slice gets its own plan before it starts.

## Stack

- **Backend:** FastAPI, SQLModel, PostgreSQL 17 (Docker), Alembic migrations, argon2 password hashing, server-side sessions in an HTTP-only cookie.
- **Frontend:** React, Vite, TypeScript, React Router, TanStack Query, Tailwind with shadcn/ui components. API client generated from the OpenAPI schema. UI text in Indonesian, written directly in the screens (no translation layer).
- **Tests:** pytest against a real PostgreSQL test database, one test per business rule. One browser test (Playwright) per slice covering its main path.
- **Numbers:** quantities allow 3 decimals (for meters); Selling Prices and payments are whole rupiah; unit costs keep 4 decimals so Moving Average doesn't drift.

## Conventions

Backend code follows the official agent skills shipped by the libraries themselves, linked into `.claude/skills/` and `.agents/skills/` by `uvx library-skills --all --claude`: **fastapi**, **sqlmodel**, **typer**. Load the matching skill before writing that kind of code. Where this plan and a skill disagree, the skill wins unless an ADR says otherwise.

What that means here:

- **Parameters and dependencies** use `Annotated[...]` with a reusable alias: `SessionDep`, `CurrentUserDep`, `AdminDep`, `OwnerDep`.
- **Routers** carry their own prefix, tags and role check (`dependencies=[Depends(...)]`), not `include_router()`.
- **Endpoints** are plain `def`, because SQLModel sessions are blocking. One HTTP operation per function.
- **Responses** declare a return type, or `response_model=...Public` when returning a table model, so fields like the password hash never leak.
- **List filters and paging** are grouped in parameter models: `Annotated[StockFilter, Query()]`.
- **Models** use the split pattern: `SkuBase`, `Sku(table=True)`, `SkuCreate`, `SkuUpdate`, `SkuPublic`. No `...` defaults, no `RootModel`.
- **Related tables live in one module** (a document and its lines; Category, Sub-category, Product and SKU). Links across modules are foreign keys; a `Relationship` across modules uses `TYPE_CHECKING` and string annotations.
- **Queries** use `session.exec(select(...))` and `session.get(...)`. No `sessionmaker`, no `session.query`, no raw SQLAlchemy models. SQLAlchemy escape hatches (`sa_column`, `sa_type`) only when `Field()` can't express it.
- **Timestamps** are plain `datetime` fields filled with `datetime.now(UTC)`: stored as UTC, always timezone-aware. The Shop Day is worked out from the shop's timezone when reporting.
- **Live updates** (slice 4) use `response_class=EventSourceResponse` and `yield`.
- **Frontend** is served with `app.frontend('/', directory='frontend/dist')`; its API client is regenerated from the OpenAPI schema whenever the API changes and never edited by hand.
- **CLI** is an explicit `typer.Typer()` app with `Annotated` options.
- **Tooling:** uv, Ruff, ty; `fastapi dev` and `fastapi run` with the entrypoint in `pyproject.toml`.

One deliberate difference: the sqlmodel skill suggests SQLite for tests; this project tests on PostgreSQL ([ADR 0007](adr/0007-postgresql-everywhere.md)).

## Folder layout

The layered layout from the scaffold stays: one module per feature in each layer.

```
src/opname360/
├── main.py                 app, mounts /api/v1, serves frontend/dist
├── cli.py                  setup commands (create the first Owner)
├── core/                   config, db, security (hashing, sessions)
├── api/
│   ├── deps.py             SessionDep, CurrentUserDep, role checks
│   └── routes/             auth, users, catalogue, suppliers, stock,
│                           goods_receipts, production_receipts,
│                           supplier_returns, activity_log
├── models/                 same feature names: tables + request/response schemas
└── services/               same feature names, plus costing.py
alembic/                    migrations
frontend/                   React app (src/pages, src/components, src/client generated)
tests/
compose.yaml                PostgreSQL for dev and tests
```

## Slice 1: Foundation

### Data

- **User:** username, full name, password hash, role (Owner, Admin, Cashier), active flag. No email. **Session** rows so deactivating a user signs them out at once.
- **Activity Log:** who, when, what action, on which document.
- **Category** (with its Costing Method), **Sub-category**, **Product**, **SKU** (code, size, colour, Barcode, Stock Unit, Purchase Pack name and size, Selling Price, active flag), **Selling Price history**.
- **Location:** seeded with one, "Toko".
- **Stock Movement:** append-only; SKU, Location, signed quantity, unit cost, reason, source document, balance after, who, when.
- **Stock balance:** quantity and total cost per SKU and Location, updated in the same transaction as the movement, under a row lock.
- **Cost Layer:** per receipt, for FIFO Categories only.
- **Supplier**, **Goods Receipt**, **Production Receipt**, **Supplier Return**, each with lines, a document number, and a status: draft → completed → reversed.

### Rules (each one gets a test)

1. Only the Owner manages users. Cashiers can do nothing in this slice. Admin and Owner do everything else.
2. A Barcode belongs to exactly one SKU. A SKU without a manufacturer Barcode gets a generated one.
3. A draft document can be edited. Completing it writes its Stock Movements; from then on it can't be edited or deleted, only reversed.
4. Goods Receipt: a line entered as 2 boxes of 12 at Rp 60.000 per box becomes 24 pcs at Rp 5.000.
5. Moving Average: receiving 10 at Rp 5.000 then 10 at Rp 6.000 gives an average of Rp 5.500. FIFO: the same receipts stay two Cost Layers, used oldest first.
6. Supplier Return: can't return more than that Goods Receipt brought in, minus earlier returns.
7. A Reversal writes the opposite Stock Movements and links both documents. If the goods are already gone, the SKU goes into Negative Stock and is flagged.
8. Two documents completed at the same moment for the same SKU leave the correct balance.
9. Every create, complete and reverse appears in the Activity Log.

### Screens (Indonesian)

| Screen | Who | What |
|---|---|---|
| Masuk | all | Sign in |
| Pengguna | Owner | Add staff, set role, deactivate, reset password |
| Kategori | Owner, Admin | Categories with Costing Method, Sub-categories |
| Produk | Owner, Admin | Search and filter; Product form with its SKUs (size, colour, Barcode, unit, pack, price) |
| Cetak Label | Owner, Admin | Pick SKUs and copies, print Code 128 labels with name, size and price |
| Impor Produk | Owner, Admin | Download the Excel template, upload, preview errors, import |
| Pemasok | Owner, Admin | Suppliers |
| Barang Masuk | Owner, Admin | Goods Receipts: scan to add lines, save draft, complete, reverse |
| Hasil Produksi | Owner, Admin | Production Receipts, same pattern |
| Retur Pembelian | Owner, Admin | Pick a Goods Receipt, choose lines and quantities to send back |
| Stok | Owner, Admin | Quantity and value per SKU, filter by Category and Sub-category, Negative Stock highlighted |
| Kartu Stok | Owner, Admin | Stock Card for one SKU |
| Log Aktivitas | Owner | Activity Log |

### Steps

Each step ends with something to open in the browser.

1. **Base:** PostgreSQL, Alembic, test setup; React app served by FastAPI; sign-in, roles, first Owner created by a setup command, Pengguna screen. The placeholder `Item` is removed.
2. **Catalogue:** Kategori and Produk screens, Barcodes, Selling Price with history.
3. **Stock core and Goods Receipt:** Stock Movements, balances, both Costing Methods, Pemasok, Barang Masuk, Stok, Kartu Stok.
4. **Other documents:** Hasil Produksi, Retur Pembelian, Reversals, Log Aktivitas.
5. **Labels and import:** Cetak Label, Impor Produk.
6. **Browser test** of the main path: sign in → create a Product with SKUs → receive goods → see the Stock Card.

### Not in slice 1

- Paying off what's owed to a Supplier. A Goods Receipt only records "paid" or "owed"; settling debts comes with the Ledger (slice 5).
- Selling, counting, reports, journal entries.
- Hosting. Everything runs locally until this slice works. FastAPI Cloud (`uv run fastapi deploy`) is the first candidate for the app, as the fastapi skill recommends; where the PostgreSQL database lives is decided at the same time.
