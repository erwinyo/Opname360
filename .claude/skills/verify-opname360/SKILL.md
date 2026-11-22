---
name: verify-opname360
description: Launch a disposable Opname360 (FastAPI + React retail POS, stock opname and bookkeeping) and drive its web screens in a real browser with Playwright, capturing screenshots, text snapshots and traces as proof. Use it to prove a change works the way a shop user would see it, before saying it is done, or to reproduce a bug on screen. Covers launch, doctor, journeys and cleanup, plus a feature map under features/.
---

# Verify Opname360

Opname360 is a web app. Its screens are the surface users touch: Owner and Admin at a desktop, Cashier at the till, Checker on a phone. The same server also exposes the JSON API (`/api/v1`, docs at `/docs`) and a small CLI (`uv run opname360 --help`). Prove behaviour on the screens. Use the API only to set up preconditions and as a second read of stored state.

Everything below runs from the repo root. Scripts live in `.claude/skills/verify-opname360/scripts/`, called `scripts/` from here on.

## Launch

```bash
.claude/skills/verify-opname360/scripts/launch.sh
```

It refuses if an instance is already recorded or port 8766 is taken. Otherwise it:

1. Starts Docker through Colima if it isn't running, then the `db` service from `compose.yaml` (PostgreSQL on 5433) if it isn't up. Whatever it started, cleanup stops.
2. Creates the database `opname360_verify_test` if missing, then wipes and migrates it and creates the Owner **`demo` / `demo-pemilik-1`** (`tests/e2e_seed.py`). That is the only seed data.
3. Builds the frontend (`npm run build`). The server serves `frontend/dist`, so an unbuilt change is invisible.
4. Starts `.venv/bin/fastapi run` on `http://127.0.0.1:8766` against that database, without reload.

Ready is the line `READY http://127.0.0.1:8766 (PID …)`. It prints only after the health endpoint answers, the built page is served, and `demo` can sign in. It takes about 20 s from cold. Any failure prints `LAUNCH FAILED`; run cleanup before launching again.

It is isolated from everything else on the machine. The dev server (port 8000, database `opname360`), the browser tests (8765) and pytest (`opname360_test`) all use other ports and databases. **One verification instance at a time**: there is one port and one database, and launch refuses a second.

## Doctor

```bash
.claude/skills/verify-opname360/scripts/doctor.sh
```

Read-only. Exit 0 means every line is `ok`: the server PID is alive and owns port 8766, the API and the built screens answer, the database has `demo`, no file in `src/`, `alembic/` or `frontend/src/` changed since launch, and the browser exists. Run it first whenever anything looks off. `drive.sh` runs it too and refuses on any `FAIL`.

A `FAIL` on "no source changed since launch" means the server and build are stale. Run cleanup, then launch again. Never prove a change against a stale instance.

## Drive

Journeys are Playwright tests in `.claude/skills/verify-opname360/journeys/`, run through:

```bash
.claude/skills/verify-opname360/scripts/drive.sh <file-name-filter> [playwright args]
.claude/skills/verify-opname360/scripts/drive.sh medicine-expiry        # the shipped journey
.claude/skills/verify-opname360/scripts/drive.sh medicine -g "Kartu"     # filter by title
```

The browser is **Dia** (`/Applications/Dia.app`, Chromium-based), because Playwright's own browsers are not installed on this Mac. Set `VERIFY_BROWSER=/path/to/chromium-binary` to use another. It runs headless at 1280×800; use `await page.setViewportSize({ width: 390, height: 844 })` for the Checker's phone screens.

To prove a change, write `journeys/<feature>-<what>.spec.ts` following `journeys/medicine-expiry.spec.ts`:

- `signIn(page)` signs in as `demo` on the login screen. Pass a username and password for staff you created.
- `api(page.request, 'path/', body?)` creates preconditions through the real API with the signed-in cookie. Never use it for the step you are proving.
- `openMenu(page, 'Barang Masuk')` opens a sidebar screen by its exact label.
- `proof(page, testInfo, 'name')` saves a numbered full-page screenshot and the screen's accessibility tree as text.
- `tag()` gives a unique suffix. Name everything you create with it, so the journey can run again on the same instance.

Selectors are accessible roles and labels, and the labels are Indonesian. The feature map under `features/` lists the exact ones per screen. Every selector there also passes in `frontend/e2e/*.spec.ts`, which shows more complete flows.

## Evidence

Each launch gets `.verify/evidence/<run-id>/`: `seed.log`, `build.log`, and `server.log` (every request the server handled). Each drive adds `drive-<time>/`, which holds:

- one folder per journey with its `NN-<name>.png` and `NN-<name>.aria.yml` from `proof()`,
- `test-finished-1.png`,
- `trace.zip`, opened with `cd frontend && npx playwright show-trace <path>`,
- `results.json` with the pass or fail of every step.

`drive.sh` prints the folder as its last line. `.verify/` is git-ignored, and no script deletes `.verify/evidence/`.

What counts as proof:

- **Drive the real user path.** Click and type through the screens a user would use. Set up preconditions through the API, but never the behaviour being proven, and never through test-only endpoints. Opname360 has none and needs none.
- **Capture the action and the resulting state.** Call `proof()` before the decisive click and after the screen settles. Assert on what the user sees: text, a document number such as `BM-2611-0001`, a status.
- **Verify side effects with a second view.** Read the stored result another way than the screen that made it. Use another screen (Kartu Stok after Barang Masuk), the API (`api(page.request, 'stock/skus/<id>/card')`), or the database:

  ```bash
  .claude/skills/verify-opname360/scripts/sql.sh "SELECT number, status FROM goods_receipt ORDER BY id DESC LIMIT 3"
  ```

  `sql.sh` runs in a read-only transaction and refuses writes.
- **No mocks.** Every part of the app is real: database, server and browser. It has no external services to stub.
- **Report a failure as a failure.** If a journey needs a precondition the app can't reach, the journey fails and the reason goes in that feature's Gotchas. Never weaken an assertion to get a pass.

## Cleanup

```bash
.claude/skills/verify-opname360/scripts/cleanup.sh
```

It stops the server PID that launch recorded, drops `opname360_verify_test`, and stops PostgreSQL and Colima only if launch started them. Then it removes `.verify/run/`. It never kills by process name and never touches `.verify/evidence/`. Run it after every attempt, failed launches included. A second run prints `nothing to clean up`.

## Helpers

| Script | Does |
| --- | --- |
| `scripts/launch.sh` | Starts the instance; prints `READY` and the evidence folder |
| `scripts/doctor.sh` | Read-only health check; exit 0 only when all pass |
| `scripts/drive.sh <filter> [args]` | Runs matching journeys with Playwright; prints the evidence folder |
| `scripts/sql.sh "<SELECT …>"` | Read-only query on the verification database |
| `scripts/cleanup.sh` | Stops what launch started; keeps evidence |
| `scripts/env.sh` | Shared settings, sourced by the others; not run directly |

## Feature map

`features/README.md` indexes the user-facing features, with how to reach each one, how to drive it, and what proves it works. Keep it current when screens change.
