# Opname360

Stock, POS and bookkeeping for a retail shop, built so the owner can trust the numbers from anywhere. FastAPI + SQLModel + PostgreSQL, with a React frontend served by the same app.

- What is being built, and in what order: [docs/plan.md](docs/plan.md)
- The words used in the code and the shop: [GLOSSARY.md](GLOSSARY.md)
- Why things are the way they are: [docs/adr/](docs/adr/)

## Set up

Needs [uv](https://docs.astral.sh/uv/), Docker and Node.js.

```bash
cp .env.example .env
docker compose up -d                 # PostgreSQL on port 5433
uv sync
uv run alembic upgrade head          # create the tables
uv run opname360 create-owner        # the first account; asks for a password
(cd frontend && npm install && npm run build)
uvx library-skills --all --claude    # link the libraries' agent skills
```

## Run

```bash
uv run fastapi dev                   # http://127.0.0.1:8000, API docs at /docs
```

FastAPI serves the built frontend from `frontend/dist`. While working on the frontend, run `npm run dev` in `frontend/` as well and open http://localhost:5173 for hot reload; it forwards `/api` to FastAPI.

Production: `ENVIRONMENT=production uv run fastapi run`.

## Check

```bash
uv run pytest                        # needs the database from compose.yaml
uv run ruff check . && uv run ruff format .
uv run ty check
(cd frontend && npm run lint && npm run e2e)   # e2e builds, then drives a real browser
```

Tests run against a real PostgreSQL database (`opname360_test`), rebuilt from the migrations on every run. Each test's changes are rolled back.

The browser tests in `frontend/e2e/` start their own server on port 8765 against that same test database, wiped and seeded first. First time only: `npx playwright install chromium` in `frontend/`.

## After changing the API

```bash
uv run alembic revision --autogenerate -m "what changed"   # if tables changed
uv run alembic upgrade head
(cd frontend && npm run generate-client)                   # if endpoints or schemas changed
```

`frontend/src/client/` is generated from the API's OpenAPI schema. Don't edit it by hand.

## Layout

```
src/opname360/
├── main.py              # the FastAPI app: API under /api/v1, then the frontend
├── cli.py               # `opname360` setup commands
├── core/                # config (.env), db engine, password and token hashing, errors
├── api/
│   ├── main.py          # api_router: includes every feature router
│   ├── deps.py          # SessionDep, CurrentUserDep, OwnerDep
│   └── routes/          # one module per feature: HTTP only, no business logic
├── models/              # SQLModel tables + request/response schemas, one module per feature
└── services/            # business rules and queries, no FastAPI imports
alembic/                 # migrations
frontend/                # React + Vite + TypeScript + Tailwind + shadcn/ui
tests/                   # one test per business rule
```

Requests flow `routes` → `services` → `models`. A service that has to refuse raises an `AppError` (`core/errors.py`) with a message in Indonesian; the app turns it into the matching HTTP status and the frontend shows the message as is.

## Conventions

Backend code follows the official agent skills for FastAPI, SQLModel and Typer, linked into `.claude/skills/` and `.agents/skills/`. The full list is in [docs/plan.md](docs/plan.md#conventions).

The frontend stays on TypeScript 6: the API client generator needs TypeScript's JavaScript API, which version 7 no longer has.
