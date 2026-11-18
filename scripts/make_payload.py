"""make_payload.py <source dir> <out zip> - the Xrero web payload of the Mac build (release asset xrero-payload.zip,
tag payload-<version>, unpacked by build-mas.yml / build-mac.yml and applied by patch_bundle.py).

<source dir> has the Windows install layout: editors/ + index.html. For 21.0 it is v20/payload-21.0-r5, the editors tree
and start page extracted (byte-identical) from the Windows 21.0 round-5 MSIX. The zip holds the same set as
payload-20.0.9 (checked entry by entry against the 20.0.9 MSIX):
  - editors/**   every file (sdkjs, sdkjs-plugins, web-apps, webext) except editors/sdkjs/<editor>/sdk-all.bin
                 (the Windows V8 snapshots: the Mac converter is JavaScriptCore and loads sdk-all*.js directly)
  - login/index.html   = <source>/index.html (the Xrero start page; patch_bundle.py adapts it to the Mac)
Writes <out zip>.sha256 too."""
import hashlib, os, re, sys, zipfile

SNAPSHOT = re.compile(r"^editors/sdkjs/[^/]+/sdk-all\.bin$")


def main(src, out):
    if not os.path.isdir(os.path.join(src, "editors")) or not os.path.isfile(os.path.join(src, "index.html")):
        raise SystemExit("source needs editors/ and index.html: " + src)
    entries, skipped = [], []
    for root, dirs, files in os.walk(os.path.join(src, "editors")):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, src).replace(os.sep, "/")
            (skipped if SNAPSHOT.match(rel) else entries).append((rel, p))
    entries.append(("login/index.html", os.path.join(src, "index.html")))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, p in entries:
            z.write(p, rel)
    for must in ["editors/sdkjs/word/sdk-all.js", "editors/sdkjs/word/sdk-all-min.js", "editors/sdkjs/pdf/src/engine/drawingfile.wasm",
                 "editors/web-apps/apps/documenteditor/main/app.js", "editors/web-apps/apps/pdfeditor/main/app.js",
                 "editors/webext/noconnect.html", "login/index.html"]:
        if must not in {r for r, _ in entries}:
            raise SystemExit("missing " + must)
    h = hashlib.sha256(open(out, "rb").read()).hexdigest()
    with open(out + ".sha256", "w", newline="\n") as f:
        f.write("%s  %s\n" % (h, os.path.basename(out)))
    print("%s: %d files (left out %d V8 snapshots: %s), %.1f MB, sha256 %s"
          % (out, len(entries), len(skipped), [r for r, _ in skipped], os.path.getsize(out) / 1e6, h))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), sys.argv[2])
