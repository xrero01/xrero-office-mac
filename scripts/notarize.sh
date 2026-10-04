#!/bin/bash
# notarize.sh <file.zip|file.dmg> [max wait, default 150m]   (env NOTARY_KEY = AuthKey .p8 path, NOTARY_KEY_ID, NOTARY_ISSUER)
# Submits to Apple's notary service and waits. Exit 0 = Accepted, 2 = still "In Progress" when the wait ran out (the
# submission id is kept in <file>.notary-id; Apple keeps processing it), 1 = rejected (Apple's log says which file and why).
set -uo pipefail
F="$1"; WAIT="${2:-150m}"
ERR="$(mktemp)"
OUT="$(xcrun notarytool submit "$F" --key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER" \
        --wait --timeout "$WAIT" --output-format json 2>"$ERR")"
echo "$OUT"; cat "$ERR"
ID="$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)"
[ -z "$ID" ] && ID="$(grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' <<<"$OUT$(cat "$ERR")" | head -1)"
STATUS="$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)"
[ -n "$ID" ] && echo "$ID" > "$F.notary-id"
case "$STATUS" in
  Accepted) echo "notarized: $F"; exit 0 ;;
  "In Progress"|"") echo "notarization still in progress after $WAIT: $F (submission ${ID:-?})"; exit 2 ;;
  *) [ -n "$ID" ] && xcrun notarytool log "$ID" --key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER" || true
     echo "notarization: $STATUS"; exit 1 ;;
esac
