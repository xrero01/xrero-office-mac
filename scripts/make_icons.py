#!/usr/bin/env python3
"""Xrero Office icons for the Mac (15 Nov 2026, the new teal kit approved by the owner).

usage: python scripts/make_icons.py <icon-kit/master dir>

The kit's artwork is full-bleed 1024 x 1024. The Mac icon grid puts the icon body in an 824 x 824 rounded square
(continuous corners) centred on the 1024 canvas, with a soft drop shadow underneath. This script applies that grid
and writes (all committed, so the macOS build only copies them):

    assets/icons/AppIcon.icns        app icon            <- office-*-1024.png
    assets/icons/xr-doc.icns         document files      <- writer-*-1024.png
    assets/icons/xr-sheet.icns       spreadsheet files   <- calc-*-1024.png
    assets/icons/xr-slide.icns       presentation files  <- slides-*-1024.png
    assets/icons/xr-pdf.icns         PDF files           <- pdf-*-1024.png
    assets/icons/preview/*.png       512 px previews of each (for review only)
    web/xr-home.js                   the start page tile pictures (KIND block, 200 px WebP data URIs) and the
                                     small plain pictures of the Recent list (KIND_PLAIN, 64 px)
    assets/icons/small/*.png         small plain pictures, icon body only (no grid margin): the title-bar tab icons
                                     (tab-doc / tab-sheet / tab-slide / tab-pdf) and the start tab's app icon (tab-app),
                                     drawn into the bundle by scripts/tab_logo.swift

"named" artwork (small word Office/Doc/Sheet/Slide/PDF) is used above 32 px, "plain" at 32 px and below.
"""
import base64, io, math, os, re, struct, sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter

KIT = sys.argv[1]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "icons")
os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)

SS = 4                    # supersampling for smooth edges
CANVAS, BODY = 1024, 824  # Mac icon grid
OFF = (CANVAS - BODY) // 2


def squircle_mask(size, n=5.0):
    """continuous-corner rounded square (superellipse |x|^n + |y|^n = 1), drawn at SS x and scaled down"""
    s = size * SS
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    r = s / 2.0
    pts = []
    for i in range(2048):
        t = 2 * math.pi * i / 2048
        c, si = math.cos(t), math.sin(t)
        x = r + r * (abs(c) ** (2 / n)) * (1 if c >= 0 else -1)
        y = r + r * (abs(si) ** (2 / n)) * (1 if si >= 0 else -1)
        pts.append((x, y))
    d.polygon(pts, fill=255)
    return m.resize((size, size), Image.LANCZOS)


MASK = squircle_mask(BODY)


def on_grid(art):
    """1024 full-bleed artwork -> 1024 RGBA Mac icon (inset rounded square + soft shadow)"""
    art = art.convert("RGB").resize((BODY, BODY), Image.LANCZOS)
    body = Image.new("RGBA", (BODY, BODY))
    body.paste(art, (0, 0), MASK)
    # soft shadow: black, 12 px down, 22 px blur, 38 % (+ a tight 2 px contact shadow, 18 %)
    sh = Image.new("L", (CANVAS, CANVAS), 0)
    sh.paste(MASK, (OFF, OFF + 12))
    sh = sh.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.38))
    ct = Image.new("L", (CANVAS, CANVAS), 0)
    ct.paste(MASK, (OFF, OFF + 2))
    ct = ct.filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * 0.18))
    alpha = ImageChops.lighter(sh, ct)
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    out.putalpha(alpha)
    out.alpha_composite(body, (OFF, OFF))
    return out


def png(im, px):
    b = io.BytesIO()
    im.resize((px, px), Image.LANCZOS).save(b, "PNG", optimize=True)
    return b.getvalue()


# icns entries (all PNG): type, pixel size. iconutil writes the same set.
ICNS = [("icp4", 16), ("icp5", 32), ("ic11", 32), ("ic12", 64), ("ic07", 128), ("ic13", 256),
        ("ic08", 256), ("ic14", 512), ("ic09", 512), ("ic10", 1024)]


def write_icns(path, named, plain):
    chunks = b""
    for t, px in ICNS:
        data = png(plain if px <= 32 else named, px)
        chunks += t.encode() + struct.pack(">I", len(data) + 8) + data
    open(path, "wb").write(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def body(art, px):
    """the plain artwork as a small picture: the rounded icon body alone (no grid margin, no shadow), px x px"""
    art = art.convert("RGB").resize((BODY, BODY), Image.LANCZOS)
    out = Image.new("RGBA", (BODY, BODY), (0, 0, 0, 0))
    out.paste(art, (0, 0), MASK)
    return out.resize((px, px), Image.LANCZOS)


SETS = [("office", "AppIcon"), ("writer", "xr-doc"), ("calc", "xr-sheet"), ("slides", "xr-slide"), ("pdf", "xr-pdf")]
SMALL = {"office": "tab-app", "writer": "tab-doc", "calc": "tab-sheet", "slides": "tab-slide", "pdf": "tab-pdf"}
os.makedirs(os.path.join(OUT, "small"), exist_ok=True)
tiles, plains = {}, {}
for kit, name in SETS:
    named = on_grid(Image.open(os.path.join(KIT, kit + "-named-1024.png")))
    plain = on_grid(Image.open(os.path.join(KIT, kit + "-plain-1024.png")))
    small = body(Image.open(os.path.join(KIT, kit + "-plain-1024.png")), 128)
    small.save(os.path.join(OUT, "small", SMALL[kit] + ".png"), optimize=True)
    if kit != "office":
        b = io.BytesIO()
        small.resize((64, 64), Image.LANCZOS).save(b, "WEBP", quality=90, method=6)
        plains[kit] = "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()
    write_icns(os.path.join(OUT, name + ".icns"), named, plain)
    named.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "preview", name + "-512.png"), optimize=True)
    plain.resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, "preview", name + "-plain-64.png"), optimize=True)
    if kit != "office":
        # start page tile: the icon body only (no grid margin / shadow - the card is the frame), 200 px for 2x screens
        b = io.BytesIO()
        named.crop((OFF, OFF, OFF + BODY, OFF + BODY)).resize((200, 200), Image.LANCZOS).save(b, "WEBP", quality=88, method=6)
        tiles[kit] = "data:image/webp;base64," + base64.b64encode(b.getvalue()).decode()
    print("made", name, os.path.getsize(os.path.join(OUT, name + ".icns")), "bytes")

# start page pictures -> web/xr-home.js (between the KIND markers)
home = os.path.join(ROOT, "web", "xr-home.js")
s = open(home, encoding="utf-8").read()
block = ("/*XR-KIND-START (scripts/make_icons.py)*/var KIND = {" +
         ",".join("%s:'%s'" % (k, v) for k, v in
                  (("word", tiles["writer"]), ("cell", tiles["calc"]), ("slide", tiles["slides"]), ("form", tiles["pdf"]))) +
         "};\n  var KIND_PLAIN = {" +
         ",".join("%s:'%s'" % (k, v) for k, v in
                  (("word", plains["writer"]), ("cell", plains["calc"]), ("slide", plains["slides"]), ("form", plains["pdf"]))) +
         "};/*XR-KIND-END*/")
s2, n = re.subn(r"/\*XR-KIND-START.*?/\*XR-KIND-END\*/", lambda m: block, s, flags=re.S)
if n != 1:
    raise SystemExit("web/xr-home.js: KIND markers not found")
open(home, "w", encoding="utf-8", newline="\n").write(s2)
print("start page tiles:", {k: len(v) for k, v in tiles.items()})
