#!/usr/bin/env bash
# Tear down what launch.sh started, and only that. Keeps .verify/evidence/.
set -uo pipefail
. "$(dirname "$0")/env.sh"

if [[ ! -f "$STATE" ]]; then
  echo "nothing to clean up"
  exit 0
fi
. "$STATE"

if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in $(seq 20); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
  kill -9 "$PID" 2>/dev/null || true
  echo "stopped server PID $PID"
fi

# The verification database is scratch; launch.sh recreates it.
if db_running; then
  docker compose exec -T db dropdb -U opname360 --if-exists "$VERIFY_DB" &&
    echo "dropped $VERIFY_DB"
fi
if [[ "${STARTED_DB:-0}" == 1 ]]; then docker compose stop db >/dev/null 2>&1 && echo "stopped postgres"; fi
if [[ "${STARTED_COLIMA:-0}" == 1 ]]; then colima stop >/dev/null 2>&1 && echo "stopped colima"; fi

rm -rf "$RUN_DIR"
if [[ -n "$(port_owner)" ]]; then echo "WARNING: port $VERIFY_PORT is still held by PID $(port_owner)"; fi
echo "cleaned up; evidence kept in ${EVIDENCE:-$EVIDENCE_ROOT}"
