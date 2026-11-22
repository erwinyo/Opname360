# Sourced by the other scripts: where things live, and which instance they mean.
# Not run on its own.

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
cd "$ROOT"

RUN_DIR="$ROOT/.verify/run"            # scratch state: cleanup.sh removes it
EVIDENCE_ROOT="$ROOT/.verify/evidence" # proof: no script ever removes it
STATE="$RUN_DIR/state.env"

VERIFY_PORT="${VERIFY_PORT:-8766}"
URL="http://127.0.0.1:$VERIFY_PORT"
VERIFY_DB=opname360_verify_test # must end in _test: tests/database.py refuses to wipe others
# Playwright's own browsers are not installed; drive the Chromium-based Dia.
VERIFY_BROWSER="${VERIFY_BROWSER:-/Applications/Dia.app/Contents/MacOS/Dia}"
OWNER_USER=demo
OWNER_PASSWORD=demo-pemilik-1 # created by tests/e2e_seed.py

# The dev DATABASE_URL from .env, pointed at the verification database.
DEV_DB_URL="$(grep -E '^DATABASE_URL=' .env | cut -d= -f2-)"
VERIFY_DB_URL="${DEV_DB_URL%/*}/$VERIFY_DB"

db_running() {
  docker info >/dev/null 2>&1 &&
    docker compose ps --status running --services 2>/dev/null | grep -qx db
}

port_owner() {
  lsof -t -nP -iTCP:"$VERIFY_PORT" -sTCP:LISTEN 2>/dev/null | head -1
}
