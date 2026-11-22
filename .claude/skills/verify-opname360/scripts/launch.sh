#!/usr/bin/env bash
# Start one disposable Opname360 for verification on 127.0.0.1:8766, with
# its own database (wiped, migrated, seeded with the Owner demo) and a fresh
# frontend build. Prints READY when the app is usable.
set -euo pipefail
. "$(dirname "$0")/env.sh"

if [[ -f "$STATE" ]]; then
  echo "REFUSED: an instance is already recorded in $STATE." >&2
  echo "Run scripts/doctor.sh to check it, or scripts/cleanup.sh to remove it." >&2
  exit 1
fi
if [[ -n "$(port_owner)" ]]; then
  echo "REFUSED: port $VERIFY_PORT is held by PID $(port_owner), which this run did not start." >&2
  exit 1
fi
if [[ ! -x "$VERIFY_BROWSER" ]]; then
  echo "REFUSED: no browser at $VERIFY_BROWSER. Set VERIFY_BROWSER to a Chromium-based browser." >&2
  exit 1
fi

RUN_ID="$(date +%Y%m%d-%H%M%S)"
EVIDENCE="$EVIDENCE_ROOT/$RUN_ID"
STARTED_COLIMA=0
STARTED_DB=0
PID=
mkdir -p "$RUN_DIR" "$EVIDENCE"

save_state() {
  cat >"$STATE" <<EOF
RUN_ID=$RUN_ID
EVIDENCE=$EVIDENCE
STARTED_COLIMA=$STARTED_COLIMA
STARTED_DB=$STARTED_DB
PID=$PID
COMMIT=$(git rev-parse --short HEAD)
EOF
}
save_state
trap 'echo "LAUNCH FAILED (see above and $EVIDENCE). Run scripts/cleanup.sh before trying again." >&2' ERR

# Docker (Colima on this Mac), then PostgreSQL from compose.yaml.
if ! docker info >/dev/null 2>&1; then
  command -v colima >/dev/null || { echo "Docker is not running and colima is not installed." >&2; exit 1; }
  echo "starting colima"
  colima start >/dev/null 2>&1
  STARTED_COLIMA=1
  save_state
fi
if ! db_running; then
  echo "starting postgres"
  docker compose up -d --wait db >/dev/null 2>&1
  STARTED_DB=1
  save_state
fi
until docker compose exec -T db pg_isready -q -U opname360; do sleep 1; done

# The verification database: created once, wiped and migrated every launch.
exists="$(docker compose exec -T db psql -U opname360 -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '$VERIFY_DB'")"
[[ -n "$exists" ]] || docker compose exec -T db createdb -U opname360 "$VERIFY_DB"
echo "seeding $VERIFY_DB"
uv sync --quiet
TEST_DATABASE_URL="$VERIFY_DB_URL" uv run --quiet python -m tests.e2e_seed >"$EVIDENCE/seed.log" 2>&1

# Source edited after this moment makes the instance stale (doctor.sh).
touch "$RUN_DIR/launched"
echo "building frontend"
(cd frontend && npm run build) >"$EVIDENCE/build.log" 2>&1

DATABASE_URL="$VERIFY_DB_URL" ENVIRONMENT=local nohup "$ROOT/.venv/bin/fastapi" run \
  --host 127.0.0.1 --port "$VERIFY_PORT" >"$EVIDENCE/server.log" 2>&1 &
PID=$!
save_state

# Ready means usable: the API answers, the built screens are served, and the
# Owner can sign in against the seeded database.
for _ in $(seq 60); do
  curl -fsS "$URL/api/v1/health/" >/dev/null 2>&1 && break
  kill -0 "$PID" 2>/dev/null || { echo "server exited; see $EVIDENCE/server.log" >&2; false; }
  sleep 0.5
done
curl -fsS "$URL/api/v1/health/" >/dev/null
curl -fsS "$URL/" | grep -q 'id="root"'
curl -fsS -o /dev/null -X POST -H 'content-type: application/json' \
  -d "{\"username\":\"$OWNER_USER\",\"password\":\"$OWNER_PASSWORD\"}" "$URL/api/v1/auth/login"

echo "READY $URL (PID $PID, commit $(git rev-parse --short HEAD))"
echo "sign in as $OWNER_USER / $OWNER_PASSWORD"
echo "evidence: $EVIDENCE"
