#!/bin/bash
# ci_signing_setup.sh - GitHub Actions: Developer ID certificate (P12 + P12_PW) into a temporary keychain and the App Store
# Connect API key (P8 + KEY_ID + ISSUER) for notarytool. Exports SIGN_ID / NOTARY_KEY / NOTARY_KEY_ID / NOTARY_ISSUER to
# $GITHUB_ENV. Without the secrets it does nothing (ad-hoc build).
set -euo pipefail
if [ -z "${P12:-}" ] || [ -z "${P8:-}" ]; then echo "no signing secrets -> ad-hoc build"; exit 0; fi
KC="$RUNNER_TEMP/xrero-sign.keychain-db"; KCPW="$(uuidgen)"
security create-keychain -p "$KCPW" "$KC"
security set-keychain-settings -lut 21600 "$KC"
security unlock-keychain -p "$KCPW" "$KC"
echo "$P12" | base64 --decode > "$RUNNER_TEMP/devid.p12"
curl -fsSL -o "$RUNNER_TEMP/DeveloperIDG2CA.cer" https://www.apple.com/certificateauthority/DeveloperIDG2CA.cer
security import "$RUNNER_TEMP/DeveloperIDG2CA.cer" -k "$KC" -A || true
security import "$RUNNER_TEMP/devid.p12" -k "$KC" -P "$P12_PW" -A -t cert -f pkcs12
rm -f "$RUNNER_TEMP/devid.p12"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KCPW" "$KC" >/dev/null
security list-keychains -d user -s "$KC" $(security list-keychains -d user | tr -d '"')
security find-identity -v -p codesigning "$KC"
ID="$(security find-identity -v -p codesigning "$KC" | grep -o '"Developer ID Application: [^"]*"' | head -1 | tr -d '"')"
test -n "$ID"
echo "SIGN_ID=$ID" >> "$GITHUB_ENV"
printf '%s\n' "$P8" > "$RUNNER_TEMP/AuthKey.p8"
{ echo "NOTARY_KEY=$RUNNER_TEMP/AuthKey.p8"; echo "NOTARY_KEY_ID=$KEY_ID"; echo "NOTARY_ISSUER=$ISSUER"; } >> "$GITHUB_ENV"
xcrun notarytool history --key "$RUNNER_TEMP/AuthKey.p8" --key-id "$KEY_ID" --issuer "$ISSUER" | head -8
