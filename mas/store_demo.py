#!/usr/bin/env python3
"""store_demo.py [out.docx]  (python-docx; run on any machine, the result is committed as mas/store_demo.docx)

The neutral sample document the Mac App Store pictures show (mas/store_capture.py opens it as "Quarterly report.docx"
in the English app and as "التقرير الربعي.docx" in the Arabic app): a bilingual UAE business report with an English
title, an Arabic right-to-left heading + paragraph, an English bullet list and a small Arabic right-to-left table.
No customer names, no money amounts, no test strings. Fonts that every Mac has (Helvetica Neue; Arial for Arabic)."""
import os, sys
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "store_demo.docx")
LATIN, ARABIC = "Helvetica Neue", "Arial"
INK, TEAL, GREY, WHITE = RGBColor(0x0B, 0x3F, 0x4B), RGBColor(0x05, 0x85, 0xA1), RGBColor(0x5B, 0x6B, 0x70), RGBColor(0xFF, 0xFF, 0xFF)


def el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn("w:" + k), v)
    return e


def put(parent, new, before):
    """insert <new> before the first child named in <before> (OOXML element order), else append"""
    for c in parent:
        if c.tag in [qn("w:" + n) for n in before]:
            c.addprevious(new)
            return new
    parent.append(new)
    return new


# element order inside w:rPr after the ones used here (ECMA-376 CT_RPr sequence)
RPR_AFTER_B = ["i", "iCs", "caps", "smallCaps", "strike", "dstrike", "outline", "shadow", "emboss", "imprint", "noProof",
               "snapToGrid", "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight",
               "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang", "eastAsianLayout"]
RPR_AFTER_SZ = RPR_AFTER_B[RPR_AFTER_B.index("highlight"):]
RPR_AFTER_RTL = RPR_AFTER_B[RPR_AFTER_B.index("cs"):]
RPR_AFTER_LANG = ["eastAsianLayout", "specVanish", "oMath"]


def fonts(rPr, latin=LATIN, cs=ARABIC):
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = el("w:rFonts"); rPr.insert(1 if rPr.find(qn("w:rStyle")) is not None else 0, rf)
    for a, v in (("w:ascii", latin), ("w:hAnsi", latin), ("w:eastAsia", latin), ("w:cs", cs)):
        rf.set(qn(a), v)


def run(p, text, size=11, bold=False, color=None, rtl=False):
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.font.bold = bold
    if color is not None:
        r.font.color.rgb = color
    rPr = r._r.get_or_add_rPr()
    fonts(rPr)
    if bold and rtl:
        put(rPr, el("w:bCs"), RPR_AFTER_B)
    put(rPr, el("w:szCs", val=str(int(size * 2))), RPR_AFTER_SZ)
    if rtl:
        put(rPr, el("w:rtl"), RPR_AFTER_RTL)
    put(rPr, el("w:lang", val="en-US", bidi="ar-AE"), RPR_AFTER_LANG)
    return r


def para(container, rtl=False, before=0, after=6, align=None, style=None):
    p = container.add_paragraph(style=style) if style else container.add_paragraph()
    if rtl:   # w:bidi first: python-docx then puts w:spacing / w:jc after it, in schema order
        put(p._p.get_or_add_pPr(), el("w:bidi"), ["adjustRightInd", "snapToGrid", "spacing", "ind", "jc"])
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if align is not None:
        p.alignment = align
    return p


def shade(cell, fill):
    put(cell._tc.get_or_add_tcPr(), el("w:shd", val="clear", color="auto", fill=fill),
        ["noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"])


d = Document()
for s in d.sections:                       # A4
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.3)
    s.top_margin, s.bottom_margin = Cm(2.0), Cm(2.0)
normal = d.styles["Normal"]
normal.font.size = Pt(11)
fonts(normal.element.get_or_add_rPr())

# English title + the line under it
p = para(d, after=2)
run(p, "Quarterly Report", 26, True, INK)
p = para(d, after=14)
run(p, "Q3 2026  ·  Dubai, Abu Dhabi and Sharjah", 12, False, GREY)

# Arabic heading + paragraph (right to left)
p = para(d, rtl=True, after=4)
run(p, "ملخص الربع الثالث", 15, True, TEAL, rtl=True)
p = para(d, rtl=True, after=12)
p.paragraph_format.line_spacing = 1.25
run(p, "يستعرض هذا التقرير أبرز ما أنجزته فرق العمل في دبي وأبوظبي والشارقة خلال الربع الثالث، "
       "ويحدد أولويات العمل للربع القادم. أُعدّ التقرير باللغتين العربية والإنجليزية في مستند واحد.", 12, rtl=True)

# English bullet list
p = para(d, after=4)
run(p, "Highlights", 15, True, TEAL)
for t in ("New office opened in Sharjah",
          "29 projects delivered across three emirates",
          "One bilingual template for Arabic and English documents"):
    p = para(d, after=3, style="List Bullet")
    run(p, t, 11.5)

# Arabic table (right to left)
p = para(d, rtl=True, before=10, after=6)
run(p, "المشاريع حسب المكتب", 15, True, TEAL, rtl=True)
# The editor engine draws every table left to right (it has no w:bidiVisual), so the columns are stored in visual
# order: the first column (المكتب) is the right-most one, as an Arabic reader expects - in any word processor.
rows = [tuple(reversed(r)) for r in (("المكتب", "المشاريع المنجزة", "الحالة"),
                                     ("دبي", "14", "ضمن الخطة"),
                                     ("أبوظبي", "9", "ضمن الخطة"),
                                     ("الشارقة", "6", "مكتب جديد"))]
t = d.add_table(rows=len(rows), cols=3)
tblPr = t._tbl.tblPr
b = el("w:tblBorders")
for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
    b.append(el("w:" + side, val="single", sz="6", space="0", color="C9DCE0"))
put(tblPr, b, ["shd", "tblLayout", "tblCellMar", "tblLook"])
for i, row in enumerate(rows):
    for j, text in enumerate(row):
        c = t.cell(i, j)
        c.width = Cm(5.46)
        c._tc.remove(c.paragraphs[0]._p)
        cp = para(c, rtl=True, before=3, after=3, align=WD_ALIGN_PARAGRAPH.CENTER if j == 1 else None)
        run(cp, text, 11.5, bold=(i == 0), color=WHITE if i == 0 else INK, rtl=True)
        if i == 0:
            shade(c, "0585A1")
        elif i % 2 == 0:
            shade(c, "EEF6F7")

cp = d.core_properties
cp.title, cp.author, cp.last_modified_by, cp.comments, cp.subject, cp.keywords = "Quarterly Report", "Xrero", "Xrero", "", "", ""
d.save(OUT)
print("wrote", OUT)
