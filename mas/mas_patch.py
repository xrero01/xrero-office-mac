#!/usr/bin/env python3
"""mas_patch.py <Xrero Office.app> <build number>  (runs ON macOS, after build_mac.sh made the app)

Turns the website build into the Mac App Store variant:
  * Sparkle (self-updater, not allowed in the App Store) is removed; the main binary's Sparkle load command is
    re-pointed (same length) at XreroUI.framework (mas/XreroUI.m, an inert SUUpdater for the MainMenu nib);
  * the updater keys leave Info.plist; App Store keys are added (build number, export compliance);
  * the stapled notarization ticket of the official bundle is dropped (it belongs to Ascensio's signature).
"""
import os, plistlib, shutil, struct, sys

APP, BUILD = sys.argv[1], sys.argv[2]
C = os.path.join(APP, "Contents")
OLD = b"@rpath/Sparkle.framework/Versions/B/Sparkle"
NEW = b"@rpath/XreroUI.framework/Versions/B/XreroUI"
assert len(OLD) == len(NEW), (len(OLD), len(NEW))

def log(*a):
    print("[mas]", *a, flush=True)

# ------------------------------------------------------------------ Info.plist
pl = os.path.join(C, "Info.plist")
p = plistlib.load(open(pl, "rb"))
for k in [k for k in p if k.startswith("SU")]:
    p.pop(k)
p["CFBundleVersion"] = str(BUILD)
p["ITSAppUsesNonExemptEncryption"] = False
p["LSApplicationCategoryType"] = "public.app-category.productivity"
p.setdefault("LSMinimumSystemVersion", "11.0")
plistlib.dump(p, open(pl, "wb"), fmt=plistlib.FMT_XML)
log("Info.plist", p["CFBundleIdentifier"], p["CFBundleShortVersionString"], "build", p["CFBundleVersion"],
    "SU keys left:", [k for k in p if k.startswith("SU")])

# ------------------------------------------------------------------ Sparkle out
sp = os.path.join(C, "Frameworks", "Sparkle.framework")
if os.path.isdir(sp):
    shutil.rmtree(sp)
    log("removed", sp)

def repoint(path):
    """Rewrite the Sparkle LC_LOAD_DYLIB path in every slice of a (fat) Mach-O. Returns the number of slices changed."""
    data = bytearray(open(path, "rb").read())
    slices = []
    magic = struct.unpack(">I", data[:4])[0]
    if magic == 0xcafebabe:
        for i in range(struct.unpack(">I", data[4:8])[0]):
            _, _, off, size, _ = struct.unpack(">IIIII", data[8 + 20 * i:28 + 20 * i])
            slices.append(off)
    else:
        slices.append(0)
    changed = 0
    for base in slices:
        if struct.unpack("<I", data[base:base + 4])[0] != 0xfeedfacf:
            continue
        ncmds = struct.unpack("<I", data[base + 16:base + 20])[0]
        o = base + 32
        for _ in range(ncmds):
            cmd, size = struct.unpack("<II", data[o:o + 8])
            if cmd in (0xc, 0x80000018):
                noff = struct.unpack("<I", data[o + 8:o + 12])[0]
                s = o + noff
                name = bytes(data[s:o + size]).split(b"\0")[0]
                if name == OLD:
                    data[s:s + len(NEW)] = NEW
                    changed += 1
            o += size
    if changed:
        open(path, "wb").write(bytes(data))
    return changed

macos = os.path.join(C, "MacOS")
total = 0
for f in os.listdir(macos):
    fp = os.path.join(macos, f)
    if os.path.isfile(fp):
        n = repoint(fp)
        if n:
            log("re-pointed Sparkle ->", NEW.decode(), "in", f, "slices:", n)
        total += n
if not total:
    raise SystemExit("[mas] no Sparkle load command found in Contents/MacOS - the bundle changed, check before signing")

# any other Mach-O still referring to Sparkle?
left = []
for root, dirs, files in os.walk(C):
    for f in files:
        fp = os.path.join(root, f)
        try:
            with open(fp, "rb") as fh:
                head = fh.read(4)
                if head not in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe"):
                    continue
                if OLD in fh.read():
                    left.append(fp)
        except OSError:
            pass
if left:
    raise SystemExit("[mas] still linked to Sparkle: %s" % left)

# ------------------------------------------------------------------ stapled ticket of the official signature
for root, dirs, files in os.walk(C):
    if root.endswith("/Contents") and "CodeResources" in files and "_CodeSignature" not in root:
        os.remove(os.path.join(root, "CodeResources"))
        log("dropped stapled ticket", root)
log("done")
