#!/usr/bin/env python3
"""store_demo.py [out dir] [docx sheet slides pdf]  (python-docx, openpyxl, python-pptx, PyMuPDF; run on any machine,
the results are committed next to this file; no kinds named = all four)

The neutral sample documents the Mac App Store pictures show (mas/store_capture.py opens them from Finder):
  store_demo.docx           English app, as "Q3 report.docx"
  store_demo_ar.docx        Arabic app, as "التقرير الربعي.docx"
  store_demo_sheet[_ar].xlsx    picture 3: a small table with SUM formulas + a column chart (Arabic: right-to-left sheet)
  store_demo_slides[_ar].pptx   picture 4: a designed title slide + a branch-office slide, a chart slide, next steps
  store_demo_form[_ar].pdf      picture 5: a one-page fillable PDF form (text fields + check boxes, empty: the capture
                                fills it in the app) that carries a highlight, an ink circle and a sticky note
  (the PDF's page text is laid out by MuPDF with IBM Plex Sans Arabic, SIL OFL 1.1 - embedded as a subset: set
   XR_DEMO_FONTS to a folder with IBMPlexSansArabic-Regular.ttf + -Bold.ttf, otherwise the committed PDFs are kept)
All of them: one neutral UAE story (three offices, 29 projects delivered in Q3 - the report's own numbers), counts and
dates only - no money amounts, no people's names, no e-mail addresses.
16 Nov 2026 (store-picture review): the pictures' headline is "Real Arabic, right to left", so Arabic leads the page
in both: an Arabic title (28 pt) and summary (14 pt), an Arabic numbered list, then a short English list - the
bilingual part. The second line is English in the English file and Arabic in the Arabic one. All of it is laid out
right to left by the editor itself (bidi paragraphs, bidi numbering) - no right-to-left table: the editor engine draws
every table left to right (it has no w:bidiVisual), so a table would only look right-to-left by storing its columns
backwards. No customer names, no money amounts, no test strings. Fonts that every Mac has: Helvetica Neue (Latin),
Geeza Pro (Arabic - heavier than Arial's Arabic at these sizes)."""
import os, sys
from docx import Document
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
    for t in ("29 projects delivered across three emirates",          # (two: the list ends inside the picture)
              "One bilingual template for Arabic and English documents"):
        p = para(d, after=2, style="List Bullet")
        run(p, t, 11.5)

    cp = d.core_properties
    cp.title, cp.author, cp.last_modified_by, cp.comments, cp.subject, cp.keywords = "التقرير الربعي", "Xrero", "Xrero", "", "", ""
    d.save(path)
    print("wrote", path)


# ------------------------------------------------------------------------------------------------------------------
# the xlsx / pptx packages' default theme: "Office Theme", Calibri / Cambria and the stock accent colours - the demo
# files use faces every Mac has and the Xrero palette, also for anything that falls back to the theme
import io, re, zipfile

PALETTE = ("0585A1", "0B3F4B", "8CCBD8", "C9A86A", "5B6B70", "2F9E8F")


def repack(path, edit):
    """rewrite the zip package at <path>, each entry through edit(name, bytes) -> bytes (fixed entry dates)"""
    zin = zipfile.ZipFile(io.BytesIO(open(path, "rb").read()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            zi = zipfile.ZipInfo(it.filename, date_time=(2026, 11, 16, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, edit(it.filename, zin.read(it.filename)))
    open(path, "wb").write(out.getvalue())


APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Properties xmlns="http://schemas.openxmlformats.org/'
           'officeDocument/2006/extended-properties"><Application>Xrero Office</Application></Properties>')


def neutral_theme(name, data, latin, cs):
    if name == "docProps/app.xml":           # (the generators' templates name a Microsoft application here)
        return APP_XML.encode("utf-8")
    if not re.match(r"(ppt|xl)/theme/theme\d+\.xml$", name):
        return data
    t = data.decode("utf-8")
    t = re.sub(r'(<a:(?:theme|clrScheme|fontScheme|fmtScheme)\b[^>]*?\bname=")[^"]*(")', r"\g<1>Xrero\2", t)
    t = re.sub(r'(<a:(?:majorFont|minorFont)>\s*<a:latin typeface=")[^"]*(")', r"\g<1>%s\2" % latin, t)
    t = re.sub(r'(<a:(?:majorFont|minorFont)>.*?<a:cs typeface=")[^"]*(")', r"\g<1>%s\2" % cs, t, flags=re.S)
    t = re.sub(r'<a:font script="Arab" typeface="[^"]*"/>', '<a:font script="Arab" typeface="%s"/>' % cs, t)
    for i, c in enumerate(PALETTE, 1):
        t = re.sub(r'(<a:accent%d>\s*<a:srgbClr val=")[0-9A-Fa-f]{6}' % i, r"\g<1>" + c, t)
    return t.encode("utf-8")


# ------------------------------------------------------------------------------------------------------------------
# picture 3: spreadsheet - a small table (SUM formulas across and down) and a column chart of it. Arabic: the sheet is
# right to left (column A on the right, the chart on the left). The capture selects E5 (=SUM(B5:D5)): the formula bar
# shows the formula, the ribbon the cell's font.
SHEET = {
    "en": dict(rtl=False, font=LATIN, sheet="Projects", title="Projects delivered by office · 2026",
               sub="Delivered projects per quarter", head=("Office", "Q1", "Q2", "Q3", "Total"),
               rows=(("Dubai", 9, 11, 12), ("Abu Dhabi", 7, 8, 10), ("Sharjah", 3, 5, 7)), total="Total",
               chart="Projects by office", widths=(15, 10, 10, 10, 10)),
    "ar": dict(rtl=True, font=ARABIC, sheet="المشاريع", title="المشاريع المنجزة حسب المكتب · 2026",
               sub="عدد المشاريع المنجزة في كل ربع", head=("المكتب", "الربع الأول", "الربع الثاني", "الربع الثالث", "المجموع"),
               rows=(("دبي", 9, 11, 12), ("أبوظبي", 7, 8, 10), ("الشارقة", 3, 5, 7)), total="الإجمالي",
               chart="المشاريع المنجزة حسب المكتب", widths=(12, 11, 11, 11, 10)),
}
SERIES = ("0B3F4B", "0585A1", "8CCBD8")


def make_sheet(path, lang):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.views import Selection

    c = SHEET[lang]
    f = c["font"]
    wb = Workbook()
    ws = wb.active
    ws.title = c["sheet"]
    ws.sheet_view.rightToLeft = c["rtl"]
    ws.sheet_view.selection = [Selection(activeCell="E5", sqref="E5")]
    line = Side(style="thin", color="D5E3E7")

    def put_cell(ref, v, size=11, bold=False, color="1F2A2E", fill=None, align="general"):
        x = ws[ref]
        x.value = v
        x.font = Font(name=f, size=size, bold=bold, color=color)
        if fill:
            x.fill = PatternFill("solid", fgColor=fill)
        x.alignment = Alignment(horizontal=align, vertical="center")
        return x

    put_cell("A1", c["title"], 16, True, "0B3F4B")
    put_cell("A2", c["sub"], 11, False, "5B6B70")
    for i, h in enumerate(c["head"]):
        put_cell("ABCDE"[i] + "4", h, 11, True, "FFFFFF", "0585A1", "general" if i == 0 else "center")
    vals = []
    for r, (office, *q) in enumerate(c["rows"], 5):
        put_cell("A%d" % r, office)
        for i, v in enumerate(q):
            put_cell("BCD"[i] + str(r), v, align="center")
        put_cell("E%d" % r, "=SUM(B%d:D%d)" % (r, r), bold=True, align="center")
        vals.append(q)
    put_cell("A8", c["total"], bold=True, fill="E6F3F6")
    for i, col in enumerate("BCDE"):
        put_cell(col + "8", "=SUM(%s5:%s7)" % (col, col), bold=True, fill="E6F3F6", align="center")
    for r in range(4, 9):
        for col in "ABCDE":
            ws[col + str(r)].border = Border(bottom=line)
        ws.row_dimensions[r].height = 21
    ws.row_dimensions[1].height = 27
    for col, w in zip("ABCDE", c["widths"]):
        ws.column_dimensions[col].width = w
    ws.column_dimensions["F"].width = 3

    # the chart: openpyxl only places it (anchor + relations); its part is written below (chart_xml) - openpyxl's own
    # chart has the category axis on the left, text categories as numbers and no cached values, which the editor's
    # engine drew as an empty bar chart (local x2t preview, 16 Nov 2026)
    ch = BarChart()
    ch.add_data(Reference(ws, min_col=2, max_col=4, min_row=4, max_row=7), titles_from_data=True)
    ch.width, ch.height = 11.0, 8.4       # (run 23: table + chart wider than the Arabic window - the chart's far side was cut)
    ws.add_chart(ch, "G3")
    wb.properties.creator = wb.properties.lastModifiedBy = "Xrero"
    wb.properties.title = c["chart"]
    wb.save(path)

    # the formulas' results stored with them (openpyxl writes formulas only): what any spreadsheet app shows before it
    # recalculates; the editor recalculates the same values
    res = {}
    for r, q in enumerate(vals, 5):
        res["E%d" % r] = sum(q)
    for i, col in enumerate("BCD"):
        res[col + "8"] = sum(q[i] for q in vals)
    res["E8"] = sum(res["E%d" % r] for r in range(5, 8))

    def edit(name, data):
        if name == "xl/worksheets/sheet1.xml":
            t = data.decode("utf-8")
            for ref, v in res.items():
                t, n = re.subn(r'(<c r="%s"[^>]*>\s*<f>[^<]*</f>)\s*(?:<v\s*/>|<v>\s*</v>)?' % ref, r"\g<1><v>%d</v>" % v, t)
                assert n == 1, (ref, n)
            data = t.encode("utf-8")
        elif name == "xl/charts/chart1.xml":
            data = chart_xml(c, vals).encode("utf-8")
        return neutral_theme(name, data, LATIN, ARABIC)
    repack(path, edit)
    print("wrote", path, res)


def chart_xml(c, vals):
    """a clustered column chart of the table (B4:D7 by A5:A7) with its cached values. The category axis runs left to
    right in both languages: reversed (maxMin, categories from the right) the editor drew the first category's label
    turned on its side and dropped the others (run 23, Arabic picture; the local x2t preview showed the same)"""
    from xml.sax.saxutils import escape as e
    f, sh = c["font"], "'%s'" % c["sheet"]

    def rpr(tag, sz, bold=False, color="3D4B50"):
        return ('<a:%s sz="%d" b="%d"><a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:latin typeface="%s"/>'
                '<a:cs typeface="%s"/></a:%s>' % (tag, sz, int(bold), color, e(f), e(f), tag))

    def txpr(sz, color="3D4B50"):
        return ('<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr%s>%s</a:pPr><a:endParaRPr lang="en-US"/></a:p></c:txPr>'
                % (' rtl="1"' if c["rtl"] else "", rpr("defRPr", sz, False, color)))

    def strcache(items):
        return '<c:strCache><c:ptCount val="%d"/>%s</c:strCache>' % (
            len(items), "".join('<c:pt idx="%d"><c:v>%s</c:v></c:pt>' % (i, e(t)) for i, t in enumerate(items)))
    cats = [r[0] for r in c["rows"]]
    ser = ""
    for i, col in enumerate("BCD"):
        ser += ('<c:ser><c:idx val="%d"/><c:order val="%d"/><c:tx><c:strRef><c:f>%s!$%s$4</c:f>%s</c:strRef></c:tx>'
                '<c:spPr><a:solidFill><a:srgbClr val="%s"/></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr>'
                '<c:invertIfNegative val="0"/><c:cat><c:strRef><c:f>%s!$A$5:$A$7</c:f>%s</c:strRef></c:cat>'
                '<c:val><c:numRef><c:f>%s!$%s$5:$%s$7</c:f><c:numCache><c:formatCode>General</c:formatCode>'
                '<c:ptCount val="3"/>%s</c:numCache></c:numRef></c:val></c:ser>') % (
            i, i, e(sh), col, strcache([c["head"][1 + i]]), SERIES[i], e(sh), strcache(cats), e(sh), col, col,
            "".join('<c:pt idx="%d"><c:v>%d</c:v></c:pt>' % (k, q[i]) for k, q in enumerate(vals)))
    grid = '<c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="E1EAED"/></a:solidFill></a:ln></c:spPr>'
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<c:roundedCorners val="0"/><c:chart>'
            '<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr%s>%s</a:pPr><a:r>%s<a:t>%s</a:t></a:r></a:p>'
            '</c:rich></c:tx><c:overlay val="0"/></c:title><c:autoTitleDeleted val="0"/>'
            '<c:plotArea><c:layout/><c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:varyColors val="0"/>'
            '%s<c:gapWidth val="60"/><c:overlap val="-8"/><c:axId val="5101"/><c:axId val="5102"/></c:barChart>'
            '<c:catAx><c:axId val="5101"/><c:scaling><c:orientation val="%s"/></c:scaling><c:delete val="0"/>'
            '<c:axPos val="b"/><c:numFmt formatCode="General" sourceLinked="1"/><c:majorTickMark val="none"/>'
            '<c:minorTickMark val="none"/><c:tickLblPos val="nextTo"/>'
            '<c:spPr><a:ln w="9525"><a:solidFill><a:srgbClr val="BFCFD4"/></a:solidFill></a:ln></c:spPr>%s'
            '<c:crossAx val="5102"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/>'
            '<c:lblOffset val="100"/><c:noMultiLvlLbl val="0"/></c:catAx>'
            '<c:valAx><c:axId val="5102"/><c:scaling><c:orientation val="minMax"/><c:max val="16"/><c:min val="0"/></c:scaling>'
            '<c:delete val="0"/><c:axPos val="%s"/><c:majorGridlines>%s</c:majorGridlines>'
            '<c:numFmt formatCode="0" sourceLinked="0"/><c:majorTickMark val="none"/><c:minorTickMark val="none"/>'
            '<c:tickLblPos val="nextTo"/><c:spPr><a:ln><a:noFill/></a:ln></c:spPr>%s<c:crossAx val="5101"/>'
            '<c:crosses val="autoZero"/><c:crossBetween val="between"/><c:majorUnit val="4"/></c:valAx>'
            '<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr></c:plotArea>'
            '<c:legend><c:legendPos val="b"/><c:overlay val="0"/>%s</c:legend>'
            '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart>'
            '<c:spPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
            '<a:ln w="9525"><a:solidFill><a:srgbClr val="D5E3E7"/></a:solidFill></a:ln></c:spPr>%s'
            '</c:chartSpace>') % (
        ' rtl="1"' if c["rtl"] else "", rpr("defRPr", 1300, True, "0B3F4B"), rpr("rPr", 1300, True, "0B3F4B"),
        e(c["chart"]), ser, "minMax", txpr(1000), "l", grid,
        txpr(900, "5B6B70"), txpr(1000), txpr(1000))


# ------------------------------------------------------------------------------------------------------------------
# picture 4: presentation - 16:9, the Xrero palette. Slide 1 = the designed title slide (the picture: the caret at the
# end of its title), slide 2 = the branch-office slide (three figures from the report), 3 = a column chart, 4 = next
# steps. Arabic: right-to-left paragraphs (a:pPr rtl), the shapes mirrored.
SLIDES = {
    "en": dict(rtl=False, font=LATIN, title="Q3 review", sub="Projects and offices across the UAE · 2026",
               branch="New office in Sharjah", branch_sub="Opened in the third quarter of 2026",
               stats=(("29", "projects delivered in Q3"), ("3", "emirates"), ("1", "new office")),
               chart="Projects by office", offices=("Dubai", "Abu Dhabi", "Sharjah"), quarters=("Q1", "Q2", "Q3"),
               next="Next steps", steps=("One template for Arabic and English documents",
                                         "A weekly project review in every office", "The Q4 plan by the end of November")),
    "ar": dict(rtl=True, font=ARABIC, title="مراجعة الربع الثالث", sub="المشاريع والمكاتب في الإمارات · 2026",
               branch="مكتب جديد في الشارقة", branch_sub="افتُتح في الربع الثالث من عام 2026",
               stats=(("29", "مشروعًا منجزًا في الربع الثالث"), ("3", "إمارات"), ("1", "مكتب جديد")),
               chart="المشاريع المنجزة حسب المكتب", offices=("دبي", "أبوظبي", "الشارقة"),
               quarters=("الربع الأول", "الربع الثاني", "الربع الثالث"),
               next="الخطوات التالية", steps=("قالب واحد للمستندات العربية والإنجليزية",
                                              "مراجعة أسبوعية للمشاريع في كل مكتب", "خطة الربع الرابع بنهاية نوفمبر")),
}


def make_slides(path, lang):
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor as C
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
    from pptx.oxml.ns import qn as pq
    from pptx.oxml import parse_xml
    from pptx.util import Inches, Pt

    c = SLIDES[lang]
    rtl, f = c["rtl"], c["font"]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    W = 13.333
    ink, teal, light, sand, grey, pale = (C.from_string(x) for x in ("0B3F4B", "0585A1", "8CCBD8", "C9A86A", "5B6B70", "E6F3F6"))

    def X(x, w):                     # positions are written left to right; Arabic mirrors them
        return Inches(W - x - w if rtl else x)

    def text(tf, lines, size, color, bold=False, align=None, after=0, bullet=False):
        tf.word_wrap = True
        for i, t in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align if align is not None else (PP_ALIGN.RIGHT if rtl else PP_ALIGN.LEFT)
            p.space_after = Pt(after)
            pPr = p._p.get_or_add_pPr()
            if rtl:
                pPr.set("rtl", "1")
            if not bullet:
                pPr.set("indent", "0"); pPr.set("marL", "0")
                pPr.insert(0, parse_xml('<a:buNone xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"/>'))
            r = p.add_run()
            r.text = t
            r.font.size, r.font.bold, r.font.name = Pt(size), bold, f
            r.font.color.rgb = color
            rPr = r._r.get_or_add_rPr()
            rPr.set("lang", "ar-AE" if rtl else "en-US")
            rPr.find(pq("a:latin")).addnext(parse_xml('<a:cs xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="%s"/>' % f))
            # the paragraph's end mark carries the run's properties (language, face, size, bold) - the caret after the
            # title's last letter sits on it: run 23's Arabic status bar showed the interface default "...السعودية"
            # there instead of the text's ar-AE
            import copy
            old = p._p.find(pq("a:endParaRPr"))
            if old is not None:
                p._p.remove(old)
            end = copy.deepcopy(rPr)
            end.tag = pq("a:endParaRPr")
            p._p.append(end)

    def shape(sl, kind, x, y, w, h, fill=None, alpha=None, line=None, line_w=None):
        s = sl.shapes.add_shape(kind, X(x, w), Inches(y), Inches(w), Inches(h))
        if fill is None:
            s.fill.background()
        else:
            s.fill.solid(); s.fill.fore_color.rgb = fill
            if alpha is not None:
                s.fill._xPr.find(pq("a:solidFill"))[0].append(parse_xml(
                    '<a:alpha xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" val="%d"/>' % int(alpha * 1000)))
        if line is None:
            s.line.fill.background()
        else:
            s.line.color.rgb = line; s.line.width = Pt(line_w or 1)
        s.shadow.inherit = False
        sl.shapes._spTree.remove(s._element)        # decoration behind the text
        sl.shapes._spTree.insert(2, s._element)
        return s

    def place(ph, x, y, w, h, anchor=MSO_ANCHOR.TOP):
        ph.left, ph.top, ph.width, ph.height = X(x, w), Inches(y), Inches(w), Inches(h)
        ph.text_frame.vertical_anchor = anchor
        ph.text_frame.margin_left = ph.text_frame.margin_right = 0
        return ph.text_frame

    # 1 - title slide: ink background, the title block on the reading side, circles on the other
    s1 = prs.slides.add_slide(prs.slide_layouts[0])
    s1.background.fill.solid(); s1.background.fill.fore_color.rgb = ink
    for args in ((MSO_SHAPE.OVAL, 8.15, 1.35, 4.5, 4.5, teal, 72),
                 (MSO_SHAPE.OVAL, 11.05, 4.55, 1.55, 1.55, light, 55),
                 (MSO_SHAPE.OVAL, 7.85, 5.55, 0.5, 0.5, sand, None)):
        shape(s1, *args)
    shape(s1, MSO_SHAPE.OVAL, 10.65, 0.55, 1.45, 1.45, None, None, light, 2.25)
    shape(s1, MSO_SHAPE.RECTANGLE, 0.95, 3.72, 1.25, 0.08, light)
    text(place(s1.shapes.title, 0.95, 2.05, 6.9, 1.55, MSO_ANCHOR.BOTTOM), [c["title"]], 54, C.from_string("FFFFFF"), True)
    text(place(s1.placeholders[1], 0.95, 3.98, 6.9, 0.9), [c["sub"]], 22, C.from_string("C7E6EC"))

    # 2 - the branch-office slide
    s2 = prs.slides.add_slide(prs.slide_layouts[5])
    shape(s2, MSO_SHAPE.RECTANGLE, 0, 0, W, 0.16, teal)
    text(place(s2.shapes.title, 0.95, 0.7, 11.4, 0.95, MSO_ANCHOR.BOTTOM), [c["branch"]], 38, ink, True)
    tb = s2.shapes.add_textbox(X(0.95, 11.4), Inches(1.68), Inches(11.4), Inches(0.6))
    tb.text_frame.margin_left = tb.text_frame.margin_right = 0
    text(tb.text_frame, [c["branch_sub"]], 20, grey)
    for i, (num, label) in enumerate(c["stats"]):
        x = 0.95 + i * 3.86
        card = shape(s2, MSO_SHAPE.ROUNDED_RECTANGLE, x, 2.75, 3.55, 2.9, pale)
        card.adjustments[0] = 0.08
        tb = s2.shapes.add_textbox(X(x + 0.35, 2.85), Inches(3.05), Inches(2.85), Inches(2.4))
        tb.text_frame.margin_left = tb.text_frame.margin_right = 0
        text(tb.text_frame, [num], 66, teal, True)
        tb2 = s2.shapes.add_textbox(X(x + 0.35, 2.85), Inches(4.35), Inches(2.85), Inches(1.0))
        tb2.text_frame.margin_left = tb2.text_frame.margin_right = 0
        text(tb2.text_frame, [label], 19, ink)

    # 3 - the numbers as a chart
    s3 = prs.slides.add_slide(prs.slide_layouts[5])
    shape(s3, MSO_SHAPE.RECTANGLE, 0, 0, W, 0.16, teal)
    text(place(s3.shapes.title, 0.95, 0.55, 11.4, 0.95, MSO_ANCHOR.BOTTOM), [c["chart"]], 34, ink, True)
    cd = CategoryChartData()
    cd.categories = list(c["offices"])
    for qi, qn_ in enumerate(c["quarters"]):
        cd.add_series(qn_, [r[1 + qi] for r in SHEET[lang]["rows"]])
    gf = s3.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, X(0.95, 11.4), Inches(1.75), Inches(11.4), Inches(5.2), cd)
    chart = gf.chart
    chart.has_legend, chart.legend.position, chart.legend.include_in_layout = True, XL_LEGEND_POSITION.BOTTOM, False
    chart.font.size, chart.font.name = Pt(14), f
    chart.font.color.rgb = grey
    for s, col in zip(chart.plots[0].series, SERIES):
        s.format.fill.solid(); s.format.fill.fore_color.rgb = C.from_string(col)
    chart.plots[0].gap_width = 70
    chart.value_axis.major_gridlines.format.line.color.rgb = C.from_string("D5E3E7")
    chart.value_axis.format.line.fill.background()

    # 4 - next steps
    s4 = prs.slides.add_slide(prs.slide_layouts[1])
    shape(s4, MSO_SHAPE.RECTANGLE, 0, 0, W, 0.16, teal)
    text(place(s4.shapes.title, 0.95, 0.55, 11.4, 0.95, MSO_ANCHOR.BOTTOM), [c["next"]], 34, ink, True)
    body = place(s4.placeholders[1], 0.95, 1.9, 11.4, 4.6)
    text(body, c["steps"], 24, ink, after=14, bullet=True)

    import datetime
    cp = prs.core_properties
    cp.title, cp.author, cp.last_modified_by, cp.comments = c["title"], "Xrero", "Xrero", ""
    cp.created = cp.modified = datetime.datetime(2026, 11, 16)
    prs.save(path)
    repack(path, lambda n, d: neutral_theme(n, d, LATIN, ARABIC))
    print("wrote", path)


# ------------------------------------------------------------------------------------------------------------------
# picture 5: PDF - a one-page meeting-room request form. Text fields + check boxes (empty: store_capture.py fills them in
# the app with Tab / typing / Enter), plus three annotations a reviewer left: a highlight on the deadline line, an ink
# circle around the date field and a sticky note beside it. Arabic: right-to-left page, fields right aligned.
PDF = {
    "en": dict(rtl=False, title="Meeting room request", sub="Office services · United Arab Emirates",
               h1="Request details", labels=("Department", "Office", "Date", "Attendees"),
               h2="Equipment", boxes=("Display screen", "Video call", "Refreshments"), h3="Notes",
               note="Please send the request at least two working days before the meeting.",
               h4="For office use", office=("Approved by", "Room"), sticky="The main room is free on this date."),
    "ar": dict(rtl=True, title="طلب حجز قاعة اجتماعات", sub="خدمات المكاتب · الإمارات العربية المتحدة",
               h1="بيانات الطلب", labels=("القسم", "المكتب", "التاريخ", "عدد الحضور"),
               h2="التجهيزات المطلوبة", boxes=("شاشة عرض", "مكالمة فيديو", "ضيافة"), h3="ملاحظات",
               note="يُرجى إرسال الطلب قبل موعد الاجتماع بيومَي عمل على الأقل.",
               h4="للاستخدام الإداري", office=("اعتمده", "القاعة"), sticky="القاعة الكبرى متاحة في هذا التاريخ."),
}
# the fields in tab order (store_capture.py fills them in this order)
PDF_FIELDS = ("department", "office", "date", "attendees", "display", "video", "refreshments", "notes")


def make_pdf(path, lang, font_dir):
    import html
    import pymupdf as fitz

    c = PDF[lang]
    rtl = c["rtl"]
    doc = fitz.open()
    pg = doc.new_page(width=595.28, height=841.89)
    W = pg.rect.width
    arch = fitz.Archive(font_dir)
    css = ("@font-face{font-family:plex;src:url(IBMPlexSansArabic-Regular.ttf)}"
           "@font-face{font-family:plex;font-weight:bold;src:url(IBMPlexSansArabic-Bold.ttf)}"
           "div{font-family:plex;line-height:1.3}")
    INK_, TEAL_, GREY_ = (0.043, 0.247, 0.294), (0.02, 0.522, 0.631), (0.357, 0.42, 0.439)

    def R(x0, y0, x1, y1):           # left-to-right layout, mirrored for Arabic
        return fitz.Rect(W - x1, y0, W - x0, y1) if rtl else fitz.Rect(x0, y0, x1, y1)

    def put(rect, t, size, color="1F2A2E", bold=False):
        # (no text-align: MuPDF swaps left / right inside dir=rtl - the paragraph's own start side is the right one)
        h = '<div dir="%s" style="font-size:%gpt;color:#%s;font-weight:%s">%s</div>' % (
            "rtl" if rtl else "ltr", size, color, "bold" if bold else "normal", html.escape(t))
        spare, scale = pg.insert_htmlbox(rect, h, css=css, archive=arch, scale_low=1)
        assert spare >= 0, ("text does not fit", t)

    def rule(y):
        pg.draw_line((50, y), (W - 50, y), color=(0.835, 0.89, 0.906), width=0.8)

    pg.draw_rect(fitz.Rect(0, 0, W, 84), color=None, fill=INK_)
    put(R(50, 19, 545, 50), c["title"], 21, "FFFFFF", True)
    put(R(50, 52, 545, 74), c["sub"], 10.5, "C7E6EC")
    put(R(50, 98, 545, 120), c["h1"], 12.5, "0585A1", True); rule(123)
    rows = ((134, 0, 1), (168, 2, 3))
    fields = {}
    for y, a, b in rows:
        for col, i in ((0, a), (1, b)):
            x = 50 if col == 0 else 305
            put(R(x, y + 3, x + 80, y + 24), c["labels"][i], 10.5, "3D4B50")
            fields[PDF_FIELDS[i]] = R(x + 84, y, x + 240, y + 24)
    put(R(50, 204, 545, 226), c["h2"], 12.5, "0585A1", True); rule(229)
    for i, x in enumerate((50, 215, 380)):
        fields[PDF_FIELDS[4 + i]] = R(x, 241, x + 14, 255)
        put(R(x + 21, 239, x + 160, 260), c["boxes"][i], 10.5, "3D4B50")
    put(R(50, 270, 545, 292), c["h3"], 12.5, "0585A1", True); rule(295)
    fields["notes"] = R(50, 303, 545, 343)
    note = R(50, 350, 545, 368)
    put(note, c["note"], 10, "5B6B70")
    put(R(50, 398, 545, 420), c["h4"], 12.5, "0585A1", True); rule(423)
    for x, t in ((50, c["office"][0]), (305, c["office"][1])):
        put(R(x, 438, x + 80, 459), t, 10.5, "3D4B50")
        r = R(x + 84, 456, x + 240, 456.5)
        pg.draw_line((r.x0, 456), (r.x1, 456), color=(0.6, 0.68, 0.7), width=0.7)

    for name in PDF_FIELDS:
        w = fitz.Widget()
        w.field_name = name
        w.rect = fields[name]
        w.border_color, w.border_width = (0.67, 0.78, 0.81), 0.8
        w.fill_color = (0.965, 0.98, 0.984)
        if name in ("display", "video", "refreshments"):
            w.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
            w.field_value = False
        else:
            w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
            w.text_font, w.text_fontsize, w.text_color = "Helv", 11, (0.12, 0.16, 0.18)
            if name == "notes":
                w.field_flags |= fitz.PDF_TX_FIELD_IS_MULTILINE
        a = pg.add_widget(w)
        if rtl and w.field_type == fitz.PDF_WIDGET_TYPE_TEXT:
            doc.xref_set_key(a.xref, "Q", "2")            # right aligned

    # the reviewer's marks
    words = pg.get_text("words", clip=note)
    box = fitz.Rect(words[0][:4])
    for wd in words[1:]:
        box |= fitz.Rect(wd[:4])
    hl = pg.add_highlight_annot(box)
    hl.set_colors(stroke=(1.0, 0.85, 0.25)); hl.set_info(title="Xrero", content=""); hl.update()
    dr = fields["date"]
    cx, cy, rx, ry = (dr.x0 + dr.x1) / 2, (dr.y0 + dr.y1) / 2, dr.width / 2 + 9, dr.height / 2 + 8
    import math
    pts = [(cx + rx * (1 + 0.03 * math.sin(3 * t)) * math.cos(t), cy + ry * (1 + 0.05 * math.cos(2 * t)) * math.sin(t))
           for t in [-2.7 + k * (2 * math.pi + 0.5) / 60 for k in range(61)]]
    ink_ = pg.add_ink_annot([pts])
    ink_.set_border(width=1.6); ink_.set_colors(stroke=(0.78, 0.27, 0.12)); ink_.set_info(title="Xrero", content=""); ink_.update()
    sx = (dr.x1 + 12) if rtl else (dr.x0 - 32)      # between the label and the circled field
    st = pg.add_text_annot((sx, dr.y0 + 2), c["sticky"], icon="Comment")
    st.set_colors(stroke=(1.0, 0.85, 0.25)); st.set_info(title="Xrero"); st.update()

    doc.set_metadata({"title": c["title"], "author": "Xrero", "subject": "", "keywords": "", "creator": "Xrero",
                      "producer": "Xrero"})
    doc.subset_fonts()
    doc.save(path, garbage=4, deflate=True)
    print("wrote", path, {k: [round(v, 1) for v in r] for k, r in fields.items()})


KINDS = sys.argv[2:] or ["docx", "sheet", "slides", "pdf"]
if "docx" in KINDS:
    make(os.path.join(OUT, "store_demo.docx"), second_line_ar=False)
    make(os.path.join(OUT, "store_demo_ar.docx"), second_line_ar=True)
for lang, suf in (("en", ""), ("ar", "_ar")):
    if "sheet" in KINDS:
        make_sheet(os.path.join(OUT, "store_demo_sheet%s.xlsx" % suf), lang)
    if "slides" in KINDS:
        make_slides(os.path.join(OUT, "store_demo_slides%s.pptx" % suf), lang)
    if "pdf" in KINDS:
        fd = os.environ.get("XR_DEMO_FONTS", "")
        if all(os.path.isfile(os.path.join(fd, n)) for n in ("IBMPlexSansArabic-Regular.ttf", "IBMPlexSansArabic-Bold.ttf")):
            make_pdf(os.path.join(OUT, "store_demo_form%s.pdf" % suf), lang, fd)
        else:
            print("store_demo_form%s.pdf kept: XR_DEMO_FONTS has no IBM Plex Sans Arabic" % suf)
