#!/usr/bin/env bash
# Read-only query against the verification database, to prove side effects:
#   sql.sh "SELECT number, status FROM goods_receipt ORDER BY id DESC LIMIT 3"
set -euo pipefail
. "$(dirname "$0")/env.sh"

docker compose exec -T db psql -U opname360 -d "$VERIFY_DB" -v ON_ERROR_STOP=1 \
  -c "SET default_transaction_read_only = on" -c "$1"
