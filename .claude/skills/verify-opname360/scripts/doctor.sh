#!/usr/bin/env bash
# Read-only: is the launched instance worth driving? Exit 0 only if every
# check passes.
set -uo pipefail
. "$(dirname "$0")/env.sh"

if [[ ! -f "$STATE" ]]; then
  echo "NO INSTANCE: nothing recorded in $STATE. Run scripts/launch.sh."
  exit 1
fi
. "$STATE"

failed=0
check() { # check <label> <command...>
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then echo "ok    $label"; else echo "FAIL  $label"; failed=1; fi
}
owned_by_us() { [[ -n "$PID" && "$(port_owner)" == "$PID" ]]; }
frontend_served() { curl -fsS "$URL/" | grep -q 'id="root"'; }
owner_seeded() {
  [[ "$(docker compose exec -T db psql -U opname360 -d "$VERIFY_DB" -tAc \
    "SELECT count(*) FROM \"user\" WHERE username = '$OWNER_USER'")" == 1 ]]
}
not_stale() { # the server doesn't reload and the build is fixed at launch
  [[ -z "$(find src alembic frontend/src frontend/index.html -newer "$RUN_DIR/launched" \
    -type f -not -path '*/__pycache__/*' 2>/dev/null | head -1)" ]]
}

check "server PID ${PID:-?} is alive" kill -0 "${PID:-0}"
check "port $VERIFY_PORT belongs to that PID" owned_by_us
check "API health answers at $URL" curl -fsS "$URL/api/v1/health/"
check "built frontend is served" frontend_served
check "database $VERIFY_DB has the Owner $OWNER_USER" owner_seeded
check "no source changed since launch (else relaunch)" not_stale
check "browser exists at $VERIFY_BROWSER" test -x "$VERIFY_BROWSER"

echo "url $URL · launched at commit $COMMIT (now $(git rev-parse --short HEAD)) · evidence $EVIDENCE"
exit "$failed"
