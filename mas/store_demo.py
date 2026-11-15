#!/usr/bin/env python3
"""store_demo.py [out dir]  (python-docx; run on any machine, the results are committed next to this file)

The neutral sample documents the Mac App Store pictures show (mas/store_capture.py opens them from Finder):
  store_demo.docx     English app, as "Q3 report.docx"
  store_demo_ar.docx  Arabic app, as "التقرير الربعي.docx"
16 Nov 2026 (store-picture review): the pictures' headline is "Real Arabic, right to left", so Arabic leads the page
in both: an Arabic title (28 pt) and summary (14 pt), an Arabic numbered list, then a short English list - the
bilingual part. The second line is English in the English file and Arabic in the Arabic one. All of it is laid out
right to left by the editor itself (bidi paragraphs, bidi numbering) - no right-to-left table: the editor engine draws
every table left to right (it has no w:bidiVisual), so a table would only look right-to-left by storing its columns
backwards. No customer names, no money amounts, no test strings. Fonts that every Mac has: Helvetica Neue (Latin),
Geeza Pro (Arabic - heavier than Arial's Arabic at these sizes)."""
import os, sys
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
LATIN, ARABIC = "Helvetica Neue", "Geeza Pro"
INK, TEAL, GREY = RGBColor(0x0B, 0x3F, 0x4B), RGBColor(0x05, 0x85, 0xA1), RGBColor(0x5B, 0x6B, 0x70)


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
    # Arabic text says it is Arabic (the status bar shows the language at the caret: the pictures put it here)
    put(rPr, el("w:lang", val="ar-AE" if rtl else "en-US", bidi="ar-AE"), RPR_AFTER_LANG)
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


SUMMARY = ("يستعرض هذا التقرير أبرز ما أنجزته فرق العمل في دبي وأبوظبي والشارقة خلال الربع الثالث، "
           "ويحدد أولويات العمل للربع القادم. أُعدّ التقرير باللغتين العربية والإنجليزية في مستند واحد.")


def make(path, second_line_ar):
    d = Document()
    for s in d.sections:                       # A4
        s.page_width, s.page_height = Cm(21.0), Cm(29.7)
        s.left_margin = s.right_margin = Cm(2.3)
        s.top_margin, s.bottom_margin = Cm(1.3), Cm(2.0)   # the whole page top fits the editor window of the pictures
    normal = d.styles["Normal"]
    normal.font.size = Pt(11)
    fonts(normal.element.get_or_add_rPr())

    # Arabic title + the line under it
    p = para(d, rtl=True, after=2)
    run(p, "التقرير الربعي", 28, True, INK, rtl=True)
    p = para(d, rtl=True, after=12)
    if second_line_ar:
        run(p, "الربع الثالث 2026  ·  الإمارات العربية المتحدة", 13, False, GREY, rtl=True)
    else:
        # (English words only from the spelling dictionary: the editor underlines Latin-script city names it does not
        # know, and it does not read w:noProof - the cities are named in the Arabic text)
        run(p, "Quarterly Report  ·  Q3 2026  ·  United Arab Emirates", 13, False, GREY)

    # Arabic summary (the pictures put the caret in this paragraph)
    p = para(d, rtl=True, after=4)
    run(p, "ملخص الربع الثالث", 18, True, TEAL, rtl=True)
    p = para(d, rtl=True, after=10)
    p.paragraph_format.line_spacing = 1.15
    run(p, SUMMARY, 14, rtl=True)

    # Arabic numbered list (right to left, the editor's own numbering)
    p = para(d, rtl=True, after=4)
    run(p, "أبرز النتائج", 16, True, TEAL, rtl=True)
    for t in ("افتتاح مكتب جديد في الشارقة",
              "تسليم 29 مشروعًا في ثلاث إمارات",
              "قالب واحد للمستندات العربية والإنجليزية"):
        p = para(d, rtl=True, after=3, style="List Number")
        run(p, t, 14, rtl=True)

    # English list (left to right): the same report in its second language
    p = para(d, before=8, after=4)
    run(p, "Highlights", 14, True, TEAL)
    for t in ("A new office opened this quarter",
              "29 projects delivered across three emirates",
              "One bilingual template for Arabic and English documents"):
        p = para(d, after=2, style="List Bullet")
        run(p, t, 11.5)

    cp = d.core_properties
    cp.title, cp.author, cp.last_modified_by, cp.comments, cp.subject, cp.keywords = "التقرير الربعي", "Xrero", "Xrero", "", "", ""
    d.save(path)
    print("wrote", path)


make(os.path.join(OUT, "store_demo.docx"), second_line_ar=False)
make(os.path.join(OUT, "store_demo_ar.docx"), second_line_ar=True)
