#!/usr/bin/env bash
# Run journeys against the launched instance and keep their evidence.
#   drive.sh medicine-expiry          # journeys whose file name matches
#   drive.sh -g "Kedaluwarsa"         # any playwright test argument works
set -euo pipefail
. "$(dirname "$0")/env.sh"

if ! "$SKILL_DIR/scripts/doctor.sh"; then
  echo "REFUSED: the instance failed doctor.sh (above). Fix or relaunch first." >&2
  exit 1
fi
. "$STATE"

out="$EVIDENCE/drive-$(date +%H%M%S)"
status=0
(
  cd frontend
  VERIFY_BASE_URL="$URL" VERIFY_OUT="$out" VERIFY_BROWSER="$VERIFY_BROWSER" \
    NODE_PATH="$ROOT/frontend/node_modules" \
    npx --no-install playwright test -c "$SKILL_DIR/playwright.config.ts" "$@"
) || status=$?
echo "evidence: $out"
exit "$status"
