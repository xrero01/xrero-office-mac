#!/bin/bash
# build_stub.sh <Xrero Office.app> <arm64|x86_64|universal>
# Builds XreroUI.framework (mas/XreroUI.m) into the app's Frameworks, install name = the path mas_patch.py wrote.
set -euo pipefail
APP="$1"; ARCH="$2"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FW="$APP/Contents/Frameworks/XreroUI.framework"
rm -rf "$FW"
mkdir -p "$FW/Versions/B/Resources"
ARCHS=(-arch arm64); [ "$ARCH" = "x86_64" ] && ARCHS=(-arch x86_64); [ "$ARCH" = "universal" ] && ARCHS=(-arch arm64 -arch x86_64)
clang "${ARCHS[@]}" -mmacosx-version-min=11.0 -O2 -Wall -Werror -fobjc-arc -dynamiclib \
  -install_name "@rpath/XreroUI.framework/Versions/B/XreroUI" \
  -framework AppKit -framework Foundation \
  -o "$FW/Versions/B/XreroUI" "$ROOT/mas/XreroUI.m"
cat > "$FW/Versions/B/Resources/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>com.xrero.office.ui</string>
  <key>CFBundleName</key><string>XreroUI</string>
  <key>CFBundleExecutable</key><string>XreroUI</string>
  <key>CFBundlePackageType</key><string>FMWK</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
</dict></plist>
EOF
ln -s B "$FW/Versions/Current"
ln -s Versions/Current/XreroUI "$FW/XreroUI"
ln -s Versions/Current/Resources "$FW/Resources"
lipo -info "$FW/Versions/B/XreroUI"
otool -L "$APP/Contents/MacOS/XreroOffice" | grep -E "XreroUI|Sparkle"
# the class the nib asks for must be there
nm -gU "$FW/Versions/B/XreroUI" | grep -q '_OBJC_CLASS_$_SUUpdater'
echo "stub ok"
