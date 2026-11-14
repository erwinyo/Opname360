# One deployment: FastAPI serves the React frontend

The frontend is a React + Vite + TypeScript single-page app in `frontend/`, built to `frontend/dist` and served by FastAPI with `app.frontend()`, so the whole system ships as one deployable with no separate web server or CORS. A single-page app was chosen over server-rendered pages (Jinja + HTMX) because the POS needs fast scan-driven input and the owner's dashboard updates live. The API client is generated from FastAPI's OpenAPI schema and never edited by hand.
