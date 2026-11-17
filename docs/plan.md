# Build plan

Status: **agreed on 2026-11-15. Slices 1 to 4 are built** (branches `slice-1-foundation`, `slice-2-stock-opname`, `slice-3-pos` and `slice-4-reports`); the shop can go live (see Go-live), and slice 5 is next.

Vocabulary is in [GLOSSARY.md](../GLOSSARY.md), decisions in [adr/](adr/), open client questions in [client-questions.md](client-questions.md).

## Slices

Each slice works end to end (API, screens, tests) before the next starts.

| # | Slice | What the shop can do when it's done | Steps |
|---|---|---|---|
| 1 | [Foundation](plan/slice-1-foundation.md) | Sign in, set up the catalogue, print barcode labels, receive goods, see stock and the Stock Card | 6 |
| 2 | [Stock Opname](plan/slice-2-stock-opname.md) | Run the Opening Opname and Partial Opnames while open for business; the Owner approves and decides who bears each Shortage | 5 |
| 3 | [POS](plan/slice-3-pos.md) | Sell, return, exchange, take payments, run Shifts and Promotions, print Receipts. Smartlink can be switched off | 6 |
| 4 | [Reports](plan/slice-4-reports.md) | The Owner sees live sales and gross profit by hour, daily stock, what sells, and where stock went missing | 5 |
| 5 | [Ledger](plan/slice-5-ledger.md) | Cash-out, supplier debts, Profit and Loss, Balance Sheet in T layout | 6 |
| 6 | [Later](plan/slice-6-later.md) | Medicine Batches, switching the Costing Method, and the list of what's deliberately left out | planned when needed |

## How the work runs

- Work happens on a branch per slice (`slice-1-foundation`), one commit per step. Merging to `main` is the owner's call.
- Work stops after every step so the result can be opened in the browser before the next step starts.
- Before a slice starts, its plan is re-read against what the earlier slices taught and adjusted if needed.

## Go-live

The shop goes live **after slice 4**, subject to the client confirming ([question 20](client-questions.md)). Stock, opname, POS and the Owner's dashboard are what the project is for; the Ledger follows and posts everything recorded since day one ([ADR 0003](adr/0003-built-in-double-entry-ledger.md)).

1. Deploy: the app, a managed PostgreSQL database, a domain with HTTPS, nightly database backups with one tested restore.
2. Create the Owner account; the Owner creates the staff accounts.
3. Import the catalogue from Excel and print labels for everything without a manufacturer Barcode.
4. Check the hardware in the shop: scanner, receipt printer, label printer, internet with a backup connection.
5. Train staff on a copy with made-up data, then wipe it.
6. Run the Opening Opname. From its approval onward every sale goes through Opname360 and Smartlink is switched off.

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

## Security

The app is on the public internet, so from slice 1:

- HTTPS only in production. The session cookie is HTTP-only, Secure and SameSite=Lax; requests that change anything must come from the app's own origin.
- Passwords are at least 8 characters, hashed with argon2. Five failed sign-ins lock the account for 15 minutes.
- A session ends after 12 hours without use, and at once when the Owner deactivates the user.
- Every endpoint checks the role on the server. Hiding a menu is never the only protection.
- Every create, complete, approve, void and reverse is written to the Activity Log.

## Shared patterns

### Documents

Goods Receipts, Production Receipts, Supplier Returns, Stock Opnames, Receipts, Cash-outs and journal entries all behave the same way ([ADR 0009](adr/0009-completed-documents-are-immutable.md)):

- A document has a number: type prefix, year and month, running number. `BM-2611-0001` is the first Goods Receipt (Barang Masuk) of November 2026.
- While it is a draft it can be edited or discarded and affects nothing.
- Completing it writes its effects (Stock Movements, later journal entries) in one transaction. From then on it can't be edited or deleted.
- A mistake is undone by a Reversal, which mirrors the original and links to it. A Reversal has its own number (`BTL-2611-0001`); its Stock Movements point at the document they cancel.
- Prefixes so far: `BM` Goods Receipt, `HP` Production Receipt, `RB` Supplier Return, `SO` Stock Opname, `SH` Shift, `PJ` sale, `RJ` Customer Return and `TT` Exchange Receipts, `BTL` Reversal (a Receipt's Void too).

### Costing rules

These apply everywhere stock moves. Each has a test in the slice that first needs it.

1. Every Stock Movement records its quantity, its unit cost, and the SKU's quantity and stock value after it.
2. **Goods in** (Goods Receipt, Production Receipt) enter at the unit cost on the document. In a FIFO Category each one adds a Cost Layer.
3. **Goods out** (sale, Supplier Return, Shortage) leave at the current average cost under Moving Average, or from the oldest Cost Layers first under FIFO.
4. **Back from a customer** (Resellable Return): at the cost it was sold at.
5. **Surplus found in an opname:** at the current average cost (Moving Average) or the latest unit cost (FIFO). If the SKU has never had a cost, the Admin enters one.
6. **Negative Stock:** units sold beyond what the system holds leave at the SKU's latest unit cost. When goods arrive they fill the gap first; any difference between their cost and the cost already used is booked as a COGS adjustment on the day they arrive. Past sales are never touched ([ADR 0008](adr/0008-sales-never-blocked-by-stock.md)).
7. **Reversal:** mirrors the original's quantity and cost exactly.
8. When a SKU's quantity reaches zero its stock value is zero; any rounding remainder leaves with the last unit.
9. Switching a Category's Costing Method follows [ADR 0002](adr/0002-costing-method-per-category.md).

### Screens and devices

| Who | Device | Screens |
|---|---|---|
| Owner | Phone first | Dashboard, approvals, reports |
| Admin | Desktop browser | Catalogue, stock documents, opname setup, bookkeeping |
| Cashier | Desktop or tablet with a barcode scanner; Chrome set to print Receipts without a dialog | POS |
| Checker | Phone | Counting |

## Folder layout

The layered layout from the scaffold stays: one module per feature in each layer.

```
src/opname360/
├── main.py                 app, mounts /api/v1, serves frontend/dist
├── cli.py                  setup commands (create the first Owner)
├── core/                   config, db, security (hashing, sessions)
├── api/
│   ├── deps.py             SessionDep, CurrentUserDep, role checks
│   └── routes/             one module per feature
├── models/                 same feature names: tables + request/response schemas
└── services/               same feature names, plus costing.py and (slice 5) posting.py
alembic/                    migrations
frontend/                   React app (src/pages, src/components, src/client generated)
tests/
compose.yaml                PostgreSQL for dev and tests
```

Features by slice:

| Slice | Feature modules |
|---|---|
| 1 | `auth`, `users`, `activity_log`, `catalogue`, `suppliers`, `stock`, `goods_receipts`, `production_receipts`, `supplier_returns` |
| 2 | `opnames`, `employee_charges` |
| 3 | `shop_settings`, `payment_methods`, `shifts`, `receipts`, `promotions` |
| 4 | `reports`, `dashboard` |
| 5 | `accounts`, `journal`, `cash`, `supplier_payments`, `financial_reports` |
| 6 | `batches` |
