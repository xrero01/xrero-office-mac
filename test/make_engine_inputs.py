#!/usr/bin/env python3
"""make_engine_inputs.py <font dir> - the PDF inputs of the engine checks (scripts/engine_checks.py), written to
test/inputs/. The font dir holds IBMPlexSansArabic-Regular.ttf + -Bold.ttf (IBM Plex Sans Arabic, SIL OFL 1.1).

ar_form_embedded.pdf  an Arabic form whose text fields use an EMBEDDED Arabic font (/DR /PlexAr, the whole font, like
                      the Windows store demo's /Dubai and like many real Arabic forms): "client" and "ref" use it,
                      "office" uses Helvetica (no Arabic: the app types Arabic there in a system face). APP-BACKLOG 18:
                      Arabic typed into an embedded-font field was saved as separate, overlapping letters.
ar_bold_lamalef.pdf   bold and regular Arabic headings with lam-alef, the fonts embedded as subsets the way PyMuPDF does
                      (doc.subset_fonts) - store NOTES "bold lam-alef": the app drew bold "ملاحظات" as "مادحظات".
                      Line 3 is the same bold heading with the subset's TrueType hinting removed (diagnosis only).
"""
import io, os, sys
import pymupdf as fitz

FD = os.path.abspath(sys.argv[1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inputs")
REG, BOLD = (os.path.join(FD, "IBMPlexSansArabic-%s.ttf" % w) for w in ("Regular", "Bold"))
CSS = ("@font-face{font-family:plex;src:url(IBMPlexSansArabic-Regular.ttf)}"
       "@font-face{font-family:plex;font-weight:bold;src:url(IBMPlexSansArabic-Bold.ttf)}div{font-family:plex}")

# the fields of ar_form_embedded.pdf: name, label, DA font (PlexAr = the embedded Arabic font, Helv = Helvetica)
FORM = (("client", "اسم العميل", "PlexAr"), ("ref", "رقم المرجع", "PlexAr"), ("office", "المكتب", "Helv"))


def html(pg, rect, text, size, bold=False, color="1F2A2E"):
    h = '<div dir="rtl" style="font-size:%gpt;color:#%s;font-weight:%s">%s</div>' % (
        size, color, "bold" if bold else "normal", text)
    spare, _ = pg.insert_htmlbox(rect, h, css=CSS, archive=fitz.Archive(FD), scale_low=1)
    assert spare >= 0, text


def form():
    doc = fitz.open()
    pg = doc.new_page(width=595.28, height=841.89)
    W = pg.rect.width
    html(pg, fitz.Rect(50, 40, W - 50, 70), "نموذج بيانات العميل", 18, True, "0585A1")
    rects = {}
    for i, (name, label, _) in enumerate(FORM):
        y = 100 + i * 40
        html(pg, fitz.Rect(W - 170, y + 4, W - 50, y + 24), label, 11, False, "3D4B50")
        rects[name] = fitz.Rect(50, y, W - 180, y + 24)
        pg.draw_rect(rects[name] + (-0.5, -0.5, 0.5, 0.5), color=(0.67, 0.78, 0.81), width=0.8)
    for name, _, _ in FORM:
        w = fitz.Widget()
        w.field_name, w.rect = name, rects[name]
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w.border_width = 2                      # (no colour: not drawn; the frame above is on the page)
        w.fill_color = (0.965, 0.98, 0.984)
        w.text_font, w.text_fontsize, w.text_color = "Helv", 14, (0.12, 0.16, 0.18)
        a = pg.add_widget(w)
        doc.xref_set_key(a.xref, "Q", "2")       # right aligned, as in an Arabic form
    doc.set_metadata({"title": "Arabic form, embedded field font", "author": "Xrero", "creator": "Xrero",
                      "producer": "Xrero", "subject": "", "keywords": ""})
    doc.subset_fonts()                         # the labels' fonts as subsets (as producers do)
    # the fields' font: the WHOLE Arabic font in the form's resources (/DR), added after subsetting so every glyph a
    # user types is there (the same set-up as the Windows store demo's /Dubai)
    fx = pg.insert_font(fontname="PlexAr", fontfile=REG)
    for wdg in pg.widgets():
        face = dict((n, f) for n, _, f in FORM)[wdg.field_name]
        if face != "Helv":
            da = doc.xref_get_key(wdg.xref, "DA")[1]
            doc.xref_set_key(wdg.xref, "DA", "(" + da.replace("/Helv", "/" + face) + ")")
    af = doc.xref_get_key(doc.pdf_catalog(), "AcroForm")
    if af[0] == "xref":
        doc.xref_set_key(int(af[1].split()[0]), "DR/Font/PlexAr", "%d 0 R" % fx)
    else:
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/DR/Font/PlexAr", "%d 0 R" % fx)
    p = os.path.join(OUT, "ar_form_embedded.pdf")
    doc.save(p, garbage=3, deflate=True)
    print("wrote", p, {k: list(map(round, r)) for k, r in rects.items()})


def dehint(ttf_bytes):
    """the same font program without TrueType hinting (fpgm / prep / cvt and the glyphs' instructions)"""
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(ttf_bytes))
    for t in ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX"):
        if t in f:
            del f[t]
    g = f["glyf"]
    for name in f.getGlyphOrder():
        gl = g[name]
        if hasattr(gl, "program"):
            from fontTools.ttLib.tables import ttProgram
            gl.program = ttProgram.Program()
            gl.program.fromBytecode(b"")
    out = io.BytesIO()
    f.save(out)
    return out.getvalue()


LAMALEF = (("bold", "ملاحظات الاجتماع", True), ("regular", "ملاحظات الاجتماع", False),
           ("bold_nohint", "ملاحظات الاجتماع", True))
LAMALEF_Y = 40          # line i is the box (50, 40 + 70 i, W - 50, 90 + 70 i) - engine_checks.py reads the same


def lamalef():
    import re
    W, H = 595.28, 300
    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)
    for i, (_, t, b) in enumerate(LAMALEF[:2]):
        html(pg, fitz.Rect(50, LAMALEF_Y + i * 70, W - 50, LAMALEF_Y + 50 + i * 70), t, 22, b)
    doc.set_metadata({"title": "Bold lam-alef", "author": "Xrero", "creator": "Xrero", "producer": "Xrero",
                      "subject": "", "keywords": ""})
    doc.subset_fonts()
    # line 3 (diagnosis): the same bold line in a document of its own, its bold subset then without TrueType hinting,
    # placed on the page as a form XObject with its own font objects (so lines 1 and 3 differ only in hinting)
    one = fitz.open()
    p1 = one.new_page(width=W, height=60)
    html(p1, fitz.Rect(50, 5, W - 50, 55), LAMALEF[2][1], 22, True)
    one.subset_fonts()
    one = fitz.open("pdf", one.tobytes(garbage=3, deflate=True))
    for x in range(1, one.xref_length()):
        m = re.search(r"/FontFile2 (\d+) 0 R", one.xref_object(x))
        if m:
            ff = int(m.group(1))
            one.update_stream(ff, dehint(one.xref_stream(ff)))
    i = 2
    pg.show_pdf_page(fitz.Rect(0, LAMALEF_Y - 5 + i * 70, W, LAMALEF_Y + 55 + i * 70), one, 0)
    p = os.path.join(OUT, "ar_bold_lamalef.pdf")
    doc.save(p, garbage=3, deflate=True)
    print("wrote", p)


if __name__ == "__main__":
    form()
    lamalef()
