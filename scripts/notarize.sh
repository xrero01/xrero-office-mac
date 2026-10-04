#!/bin/bash
# notarize.sh <file.zip|file.dmg>   (env NOTARY_KEY = AuthKey .p8 path, NOTARY_KEY_ID, NOTARY_ISSUER)
# Submits to Apple's notary service and waits; on rejection prints Apple's log (which file, which problem).
set -euo pipefail
F="$1"
OUT="$(xcrun notarytool submit "$F" --key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER" \
        --wait --timeout 150m --output-format json)"
echo "$OUT"
ID="$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))')"
STATUS="$(echo "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')"
if [ "$STATUS" != "Accepted" ]; then
  [ -n "$ID" ] && xcrun notarytool log "$ID" --key "$NOTARY_KEY" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER" || true
  echo "notarization: $STATUS"; exit 1
fi
echo "notarized: $F"
