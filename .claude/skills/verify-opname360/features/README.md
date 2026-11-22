# Opname360 verification map

This folder is the maintained source for verifying what Opname360's users see. Read this index before driving the app, then use the matching feature file as the recipe. The harness is in `../SKILL.md`.

## Baseline preconditions

- A verification instance launched by `scripts/launch.sh` and passing `scripts/doctor.sh`, at `http://127.0.0.1:8766`.
- The database holds only the Owner `demo` / `demo-pemilik-1`, the Location `Toko`, the payment methods (`Tunai` and others) and the chart of accounts. There is no catalogue, no staff and no stock until a journey creates them.
- Journeys sign in through the login screen and set up their own preconditions through the API, named with `tag()`.
- Never drive an instance this run did not launch.

## Driving conventions

- Start every journey from the baseline. Data from earlier journeys stays until the next launch, so never rely on it, and never collide with it either: use unique names.
- Use roles and accessible names (`getByRole`, `getByLabel`), never CSS classes or position. UI text is Indonesian; copy it exactly.
- Desktop screens at 1280×800. Checker screens on a phone viewport of 390×844.
- A journey that opens a Shift closes it before ending. The till has one drawer, and a Shift left open blocks the next journey from opening one.
- Run journeys through `scripts/drive.sh`, one instance, one at a time.

## Proof and skip reporting

- `proof()` before and after the decisive step: a screenshot and the screen's text snapshot.
- Assert what the user sees, then read the stored result a second way: another screen, the API, or `scripts/sql.sh`.
- Record which entry point you used. A path you didn't drive is not verified through another one.
- Report an unreachable path with the step that failed and the missing precondition.

## Feature entry contract

Each feature file starts with an H1 and one paragraph of user-visible behaviour, then exactly four H2s in this order: `Sub-features`, `How to get to it (user POV)`, `Driving it with Playwright` (starting with `Preconditions:`), and `Gotchas`.

## Features

- [Sign-in and roles](./sign-in-and-roles.md): signing in, what each role sees, staff accounts.
- [Barang Masuk and stock](./goods-receipt.md): receiving goods, then Stok and Kartu Stok. No journey ships yet.
- [Kasir](./pos-till.md): Shift, sale, payment, return or exchange, closing the drawer. No journey ships yet.
- [Stok Opname](./stock-opname.md): opening a session, blind counting on a phone, review and approval. No journey ships yet.
- [Medicine batches and Kedaluwarsa](./medicine-batches-and-expiry.md): batch tracking from Barang Masuk to the till and the expiry report. Proven by `journeys/medicine-expiry.spec.ts`.
