# Opname360

Opname360 runs a retail shop's stock, point of sale, stock counts, and bookkeeping. It is a FastAPI app on PostgreSQL, and it serves its own React frontend.

Read these documents for the rest of the project:

- [docs/plan.md](docs/plan.md) says what is built and in what order.
- [GLOSSARY.md](GLOSSARY.md) defines the words the code and the shop use.
- [docs/adr/](docs/adr/) records why things are the way they are.

## Set up a development machine

You need [uv](https://docs.astral.sh/uv/), Docker, and Node.js. If you use Colima instead of Docker Desktop, run `colima start` first.

```bash
cp .env.example .env
docker compose up -d --wait          # PostgreSQL on port 5433, ready when this returns
uv sync
uv run alembic upgrade head          # create the tables
uv run opname360 create-owner        # the first account, asks for username, full name, and password
(cd frontend && npm install && npm run build)
```

`uv sync` also makes the agent skills for FastAPI, SQLModel, and Typer work. Their links in `.claude/skills/` and `.agents/skills/` are committed and point into `.venv`. After you add a library, run `uvx library-skills --all --claude` to link its skill, if it has one.

## Run the app

```bash
docker compose up -d --wait          # starts PostgreSQL if it is stopped
uv run fastapi dev                   # http://127.0.0.1:8000, API docs at /docs
```

FastAPI serves the built frontend from `frontend/dist`, so rebuild it after a frontend change. For hot reload, also run `npm run dev` in `frontend/` and open http://localhost:5173. The dev server forwards `/api` to FastAPI.

In production, run `ENVIRONMENT=production uv run fastapi run`. Session cookies then require HTTPS.

## Check a change

```bash
uv run pytest                        # needs PostgreSQL running
uv run ruff check . && uv run ruff format .
uv run ty check src
(cd frontend && npm run lint && npm run e2e)   # e2e builds the frontend, then drives a browser
```

pytest uses its own database, `opname360_test`, and rebuilds it from the migrations at the start of every run. Each test rolls back its changes. The threaded concurrency tests commit instead, then empty the tables.

Run `ty` on `src` only. The `tests/` folder doesn't pass `ty` yet.

The browser tests in `frontend/e2e/` start their own server on port 8765. That server uses the test database, wiped and seeded first. Before the first run, install the browser with `npx playwright install chromium` in `frontend/`.

To prove a change on screen with screenshots and traces, use the verification skill in `.claude/skills/verify-opname360/`. Its `SKILL.md` gives the commands.

## Update the schema and client after an API change

If tables changed, generate a migration and read it before you apply it. If endpoints or schemas changed, regenerate the frontend client and format it.

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
cd frontend
npm run generate-client
npx prettier@3.10.1 --no-semi --single-quote --write src/client
```

`npm run generate-client` writes `frontend/src/client/` from the API's OpenAPI schema, so don't edit those files by hand. The generator doesn't format its output. Prettier formats it like the committed files, so the diff shows only the real change.

## Where the code lives

```
src/opname360/
├── main.py              # the FastAPI app: API under /api/v1, then the frontend
├── cli.py               # `opname360` setup commands
├── core/                # config (.env), database engine, password and token hashing, errors, formatting
├── api/
│   ├── main.py          # api_router: includes every feature router
│   ├── deps.py          # SessionDep, CurrentUserDep, and the role checks (OwnerDep, AdminDep, SellerDep)
│   └── routes/          # one module per feature: HTTP only, no business logic
├── models/              # SQLModel tables and request and response schemas, one module per feature
└── services/            # business rules and queries, no FastAPI imports
alembic/                 # migrations
frontend/                # React, Vite, TypeScript, Tailwind, shadcn/ui
tests/                   # one test per business rule
```

A request goes from a route to a service, and the service reads and writes the models. A service that refuses raises an `AppError` from `core/errors.py` with an Indonesian message. The app turns the error into the matching HTTP status, and the frontend shows the message unchanged.

## Conventions

Backend code follows the official agent skills for FastAPI, SQLModel, and Typer. The [Conventions section of docs/plan.md](docs/plan.md#conventions) lists how this project applies them.

The frontend stays on TypeScript 6. The API client generator needs TypeScript's JavaScript API, and TypeScript 7 removed it.
