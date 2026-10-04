# Xrero Office for macOS — build & test

Builds **Xrero Office.app** (Apple silicon + Intel) from the official ONLYOFFICE Desktop Editors 9.4.0 macOS
bundles (AGPL-3.0, SHA-256 pinned) plus the Xrero web layer (`xrero-payload.zip` release asset: branded
editors with the 20.0.9 Arabic PDF fix + Xrero start page), then tests the result on a real Mac runner:

1. `scripts/build_mac.sh` — extract, rebrand (`scripts/patch_bundle.py`: name, bundle id, icon, menus,
   updater feed, Windows-only buttons hidden, sign-in wall removed), regenerate the converter's V8
   snapshots with the bundle's own `x2t`, ad-hoc sign, DMG.
2. `scripts/test_converter.py` — Arabic Word/Excel/PowerPoint → PDF with the bundle's converter; the
   text layer must read correctly in PDFium (Chrome/Edge).
3. `scripts/ui_test.py` — launches the real app, start page, opens a .docx, types English + Arabic,
   bold, Cmd+S, screenshots.

Run: Actions → build-mac → Run workflow. Output: a pre-release with the DMGs + test evidence.
The DMGs are ad-hoc signed (no Apple Developer ID): first launch needs System Settings →
Privacy & Security → Open Anyway.
