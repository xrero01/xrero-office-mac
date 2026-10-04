#!/usr/bin/env python3
"""test_converter.py <Xrero Office.app> <arm64|x86_64> <test dir> <out dir>
Exports every test/inputs file to PDF with the bundle's own x2t and checks the Arabic text layer
(the 20.0.9 fix) with PDFium (Chrome/Edge's engine) and MuPDF. Writes <out>/converter-<arch>.json + page PNGs."""
import json, os, re, subprocess, sys, unicodedata
import pymupdf as fitz
import pypdfium2 as pdfium

APP, ARCH, TDIR, OUT = sys.argv[1:5]
CONV = os.path.join(APP, "Contents", "Resources", "converter")
X2T = os.path.join(CONV, "x2t")
RUN = ["arch", "-x86_64"] if ARCH == "x86_64" else []
os.makedirs(OUT, exist_ok=True)
FONTS = os.path.join(OUT, "fonts-" + ARCH)
os.makedirs(FONTS, exist_ok=True)
PUNCT = "،.:؛,;()[]{}«»\"'!?؟-–—/ـ‎‏‪‫‬‭‮﻿"

def norm(w):
    return unicodedata.normalize("NFKC", w).strip(PUNCT + " ")

def recall(truth, got):
    key = lambda w: "".join(sorted(norm(w)))
    pool = {}
    for g in got:
        k = key(g)
        if k: pool[k] = pool.get(k, 0) + 1
    hit = 0; miss = []
    for w in truth:
        k = key(w)
        if not k: continue
        if pool.get(k, 0): pool[k] -= 1; hit += 1
        else: miss.append(w)
    return hit, len([w for w in truth if norm(w)]), miss[:8]

r = subprocess.run(RUN + [X2T, "-create-allfonts", FONTS], cwd=CONV, capture_output=True, text=True)
print("allfonts rc", r.returncode, os.listdir(FONTS)[:6], flush=True)

truth = json.load(open(os.path.join(TDIR, "truth.json"), encoding="utf-8"))
result = {"arch": ARCH, "files": {}, "totals": {}}
tot = {"pdfium": [0, 0], "mupdf": [0, 0]}
for f, words in truth.items():
    src = os.path.join(TDIR, "inputs", f)
    pdf = os.path.join(OUT, "%s-%s.pdf" % (os.path.splitext(f)[0], ARCH))
    xml = pdf + ".xml"
    open(xml, "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="utf-8"?><TaskQueueDataConvert>'
        '<m_sFileFrom>%s</m_sFileFrom><m_sFileTo>%s</m_sFileTo>'
        '<m_sAllFontsPath>%s</m_sAllFontsPath><m_sFontDir>%s</m_sFontDir>'
        '<m_sThemeDir>%s</m_sThemeDir><m_bIsNoBase64>true</m_bIsNoBase64></TaskQueueDataConvert>'
        % (src, pdf, os.path.join(FONTS, "AllFonts.js"), FONTS,
           os.path.join(APP, "Contents", "Resources", "editors", "sdkjs", "slide", "themes")))
    if os.path.exists(pdf): os.remove(pdf)
    p = subprocess.run(RUN + [X2T, xml], cwd=CONV, capture_output=True, text=True, timeout=600)
    entry = {"rc": p.returncode}
    if p.returncode == 0 and os.path.exists(pdf):
        d = fitz.open(pdf)
        d[0].get_pixmap(dpi=90).save(pdf[:-4] + ".png")
        entry["producer"] = d.metadata.get("producer")
        mu = [w for pg in d for w in pg.get_text("text").split()]
        pd = pdfium.PdfDocument(pdf)
        pf = [w for i in range(len(pd)) for w in pd[i].get_textpage().get_text_range().split()]
        for name, got in (("pdfium", pf), ("mupdf", mu)):
            h, n, miss = recall(words, got)
            entry[name] = "%d/%d" % (h, n); entry[name + "_miss"] = miss
            tot[name][0] += h; tot[name][1] += n
    else:
        entry["stderr"] = (p.stderr or "")[-400:]
    result["files"][f] = entry
    print(f, entry, flush=True)
for k, (h, n) in tot.items():
    result["totals"][k] = round(100.0 * h / max(n, 1), 1)
print("TOTALS", result["totals"], flush=True)
json.dump(result, open(os.path.join(OUT, "converter-%s.json" % ARCH), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
# gate: the Arabic text layer must read correctly in Chrome/Edge's engine
sys.exit(0 if result["totals"].get("pdfium", 0) >= 90 else 3)
