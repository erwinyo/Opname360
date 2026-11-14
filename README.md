# Opname360

FastAPI + SQLModel API, laid out to grow into a large application.

## Run

```bash
uv sync
cp .env.example .env      # optional; defaults work without it
uv run fastapi dev        # http://127.0.0.1:8000/docs
```

Production: `uv run fastapi run`. The entrypoint is set in `pyproject.toml` (`[tool.fastapi]`).

## Check

```bash
uv run pytest
uv run ruff check . && uv run ruff format .
uv run ty check
```

## Layout

```
src/opname360/
├── main.py              # creates the FastAPI app, lifespan, mounts api_router
├── core/
│   ├── config.py        # Settings, read from env / .env
│   └── db.py            # engine, table creation, get_session
├── api/
│   ├── main.py          # api_router (/api/v1): includes every feature router
│   ├── deps.py          # shared dependencies (SessionDep, later CurrentUserDep, ...)
│   └── routes/          # one module per feature: HTTP only, no business logic
│       ├── health.py
│       └── items.py
├── models/              # SQLModel tables + request/response schemas, one module per feature
│   └── item.py
└── services/            # business logic and DB queries, no FastAPI imports
    └── items.py
tests/                   # pytest, in-memory SQLite via dependency override
```

Requests flow `routes` → `services` → `models`. Routes handle HTTP concerns (status codes, 404s, params), services hold the logic and can be called from anywhere (CLI, background jobs, tests).

## Adding a feature

Using `items` as the pattern, for a feature called `locations`:

1. `models/location.py`: `LocationBase`, `Location(table=True)`, `LocationCreate`, `LocationUpdate`, `LocationPublic`. Export them from `models/__init__.py`.
2. `services/locations.py`: functions taking a `Session`.
3. `api/routes/locations.py`: `router = APIRouter(prefix="/locations", tags=["locations"])`.
4. Register it in `api/main.py`: `api_router.include_router(locations.router)`.
5. `tests/test_locations.py`.

## Conventions

The official agent skills for FastAPI, SQLModel and Typer are linked into `.claude/skills/` and `.agents/skills/` (via `uvx library-skills --all --claude`; rerun it after `uv sync` on a fresh clone). Backend code follows them; the full list of conventions is in [docs/plan.md](docs/plan.md). In short:

- `Annotated[...]` for every parameter and dependency, with a reusable alias (`SessionDep`).
- Router prefix, tags and shared dependencies go on the `APIRouter`, not in `include_router()`.
- Plain `def` endpoints unless everything inside is truly async (SQLModel sessions are sync).
- `response_model=...Public` when returning table models, so internal fields never leak.
- No `...` defaults, no `RootModel`.

Tables are created on startup with `create_all`. Once the schema needs to change on a live database, switch to Alembic migrations.
