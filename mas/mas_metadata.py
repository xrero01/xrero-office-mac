#!/usr/bin/env python3
"""mas_metadata.py - fills the macOS App Store version of Xrero Office (App Store Connect API key from the secrets):
store text (en-US, ar-SA) based on the iOS version with Mac wording, Mac screenshots (APP_DESKTOP, mas/store/*.png),
App Review contact + Mac notes, and the newest processed macOS build. It does NOT submit for review.
Env: ASC_KEY, ASC_KEY_ID, ASC_ISSUER."""
import hashlib, json, os, sys, time, urllib.error, urllib.request

import jwt

APP_ID = "6819063639"
API = "https://api.appstoreconnect.apple.com"
ROOT = os.path.dirname(os.path.abspath(__file__))

TEXT = {
    "en-US": {
        "description": """Xrero Office is a free office suite for documents, spreadsheets and presentations - built Arabic-first and working fully offline on your Mac.

OPEN AND EDIT THE FILES YOU ALREADY HAVE
- Documents (.docx), spreadsheets (.xlsx) and presentations (.pptx), plus PDF viewing
- Open from Finder, iCloud Drive, Downloads or email attachments
- Save in the same format, ready to share with colleagues using other office apps

REAL ARABIC SUPPORT
- Right-to-left paragraphs, tables and slides that look right
- Arabic and English typing in the same document

A FULL EDITOR, NOT A VIEWER
- Text styles, headings, lists, tables, images, colors and page layout
- Formulas, cell formatting and multiple sheets
- Slides with layouts, themes and transitions
- Tabs: several documents open in one window

PRIVATE BY DESIGN
- Your files stay on your Mac - no account needed, no tracking
- Works without an internet connection

Xrero Office is free and open-source software (AGPL-3.0), based on ONLYOFFICE.""",
        "promotionalText": "Free, offline and Arabic-first. Open, edit and save .docx, .xlsx and .pptx files on your Mac. No account needed.",
    },
    "ar-SA": {
        "description": """أوفيس Xrero حزمة مكتبية مجانية للمستندات والجداول والعروض التقديمية، مصممة للعربية أولاً وتعمل بالكامل دون إنترنت على جهاز الماك.

افتح ملفاتك وعدّلها
- المستندات (.docx) والجداول (.xlsx) والعروض التقديمية (.pptx) وعرض ملفات PDF
- افتح من Finder أو iCloud Drive أو التنزيلات أو مرفقات البريد
- احفظ بنفس الصيغة لتشاركها مع زملائك الذين يستخدمون برامج مكتبية أخرى

دعم حقيقي للعربية
- فقرات وجداول وشرائح من اليمين إلى اليسار تظهر بشكل صحيح
- اكتب بالعربية والإنجليزية في نفس المستند

محرر كامل وليس مجرد عارض
- أنماط النصوص والعناوين والقوائم والجداول والصور والألوان وتخطيط الصفحة
- المعادلات وتنسيق الخلايا وأوراق العمل المتعددة
- شرائح بتخطيطات وسمات وانتقالات
- تبويبات: عدة مستندات مفتوحة في نافذة واحدة

الخصوصية أولاً
- ملفاتك تبقى على جهازك: بلا حساب وبلا تتبّع
- يعمل دون اتصال بالإنترنت

أوفيس Xrero برنامج مجاني ومفتوح المصدر (AGPL-3.0) مبني على ONLYOFFICE.""",
        "promotionalText": "مجاني ويعمل دون إنترنت ومصمم للعربية أولاً. افتح ملفات docx وxlsx وpptx وعدّلها واحفظها على الماك. بلا حساب.",
    },
}
SHOTS = {"en-US": ["mac_en_start.png", "mac_en_editor.png"], "ar-SA": ["mac_ar_start.png", "mac_ar_editor.png"]}

NOTES = """XRERO OFFICE FOR MAC - APP REVIEW INFORMATION

PURPOSE AND AUDIENCE
Xrero Office is a free, open-source office suite (documents, spreadsheets, presentations) for Mac, iPhone and iPad. It is made for Arabic-speaking users, mainly in the United Arab Emirates and the Gulf, and for anyone who needs to open, edit and save Microsoft Office files (.docx, .xlsx, .pptx) with correct right-to-left Arabic. No account, no subscription, no in-app purchases.

HOW TO USE (no login)
1. Launch the app: the start page opens (Home, Open local file, Templates).
2. Click Document, Spreadsheet or Presentation to create a file, or Open local file / drag a .docx, .xlsx or .pptx file onto the window.
3. Edit with the toolbar (bold, fonts, alignment, right-to-left paragraphs, tables, formulas, slides) and save with Command-S. Each document opens in a tab.
Sample files: https://github.com/xrero01/xrero-office-ios/tree/main/store/samples

THIS MAC VERSION
The Mac app is the ONLYOFFICE Desktop Editors 9.4.0 app (AGPL-3.0) with the Xrero interface, sandboxed for the Mac App Store. It has no self-updater (updates come only from the App Store). Apple silicon Macs, macOS 12 or later.

EXTERNAL SERVICES
None are needed: editing and file conversion run on the Mac. Optional features contact a service only when the user chooses to: connecting the app to the user's own document server (ownCloud, Nextcloud) from the start page, and editor plugins that the user opens (for example an AI assistant plugin, which works only with the user's own provider key). There is no analytics, advertising or tracking.

REGIONAL DIFFERENCES
None. The app works the same in all regions; the interface is available in English and Arabic.

REGULATED INDUSTRY / THIRD-PARTY MATERIAL
Not a regulated industry. Built on open-source software it is licensed to redistribute (ONLYOFFICE Desktop Editors, AGPL-3.0, Ascensio System SIA). The complete source of this build is published at https://github.com/xrero01/xrero-office-mac as the AGPL requires."""


def token():
    now = int(time.time())
    return jwt.encode({"iss": os.environ["ASC_ISSUER"], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      os.environ["ASC_KEY"], algorithm="ES256", headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"})


def call(method, path, body=None):
    url = path if path.startswith("http") else API + path
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise SystemExit("ASC %s %s -> %s %s" % (method, path, e.code, e.read().decode(errors="replace")[:1500]))


def versions():
    vs = call("GET", "/v1/apps/%s/appStoreVersions?limit=20" % APP_ID)["data"]
    mac = [v for v in vs if v["attributes"]["platform"] == "MAC_OS"]
    ios = [v for v in vs if v["attributes"]["platform"] == "IOS"]
    if not mac:
        raise SystemExit("no macOS version - run build-mas first")
    return mac[0], ios[0]


def localizations(mac, ios):
    src = {l["attributes"]["locale"]: l["attributes"] for l in
           call("GET", "/v1/appStoreVersions/%s/appStoreVersionLocalizations" % ios["id"])["data"]}
    have = {l["attributes"]["locale"]: l for l in
            call("GET", "/v1/appStoreVersions/%s/appStoreVersionLocalizations" % mac["id"])["data"]}
    out = {}
    for loc, t in TEXT.items():
        a = {"description": t["description"], "promotionalText": t["promotionalText"],
             "keywords": src.get(loc, {}).get("keywords"), "supportUrl": src.get(loc, {}).get("supportUrl"),
             "marketingUrl": src.get(loc, {}).get("marketingUrl")}
        a = {k: v for k, v in a.items() if v}
        if loc in have:
            r = call("PATCH", "/v1/appStoreVersionLocalizations/%s" % have[loc]["id"],
                     {"data": {"type": "appStoreVersionLocalizations", "id": have[loc]["id"], "attributes": a}})
        else:
            a["locale"] = loc
            r = call("POST", "/v1/appStoreVersionLocalizations", {"data": {"type": "appStoreVersionLocalizations",
                     "attributes": a, "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": mac["id"]}}}}})
        out[loc] = r["data"]["id"]
        print("text", loc, "ok (description %d chars)" % len(t["description"]))
    return out


def screenshots(locs):
    for loc, lid in locs.items():
        sets = call("GET", "/v1/appStoreVersionLocalizations/%s/appScreenshotSets" % lid)["data"]
        desk = [s for s in sets if s["attributes"]["screenshotDisplayType"] == "APP_DESKTOP"]
        if desk:
            sid = desk[0]["id"]
            for old in call("GET", "/v1/appScreenshotSets/%s/appScreenshots" % sid)["data"]:
                call("DELETE", "/v1/appScreenshots/%s" % old["id"])
        else:
            sid = call("POST", "/v1/appScreenshotSets", {"data": {"type": "appScreenshotSets",
                       "attributes": {"screenshotDisplayType": "APP_DESKTOP"},
                       "relationships": {"appStoreVersionLocalization": {"data": {"type": "appStoreVersionLocalizations", "id": lid}}}}})["data"]["id"]
        for name in SHOTS[loc]:
            data = open(os.path.join(ROOT, "store", name), "rb").read()
            r = call("POST", "/v1/appScreenshots", {"data": {"type": "appScreenshots",
                     "attributes": {"fileName": name, "fileSize": len(data)},
                     "relationships": {"appScreenshotSet": {"data": {"type": "appScreenshotSets", "id": sid}}}}})["data"]
            for op in r["attributes"]["uploadOperations"]:
                chunk = data[op["offset"]:op["offset"] + op["length"]]
                req = urllib.request.Request(op["url"], method=op["method"], data=chunk,
                                             headers={h["name"]: h["value"] for h in op["requestHeaders"]})
                urllib.request.urlopen(req, timeout=120).read()
            call("PATCH", "/v1/appScreenshots/%s" % r["id"], {"data": {"type": "appScreenshots", "id": r["id"],
                 "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
            print("screenshot", loc, name, "uploaded")


def review(mac, ios):
    src = call("GET", "/v1/appStoreVersions/%s/appStoreReviewDetail" % ios["id"])["data"]["attributes"]
    a = {k: src.get(k) for k in ("contactFirstName", "contactLastName", "contactPhone", "contactEmail") if src.get(k)}
    a.update({"demoAccountRequired": False, "notes": NOTES})
    try:
        cur = call("GET", "/v1/appStoreVersions/%s/appStoreReviewDetail" % mac["id"])["data"]
    except SystemExit:
        cur = None
    if cur:
        call("PATCH", "/v1/appStoreReviewDetails/%s" % cur["id"], {"data": {"type": "appStoreReviewDetails", "id": cur["id"], "attributes": a}})
    else:
        call("POST", "/v1/appStoreReviewDetails", {"data": {"type": "appStoreReviewDetails", "attributes": a,
             "relationships": {"appStoreVersion": {"data": {"type": "appStoreVersions", "id": mac["id"]}}}}})
    print("review details ok (notes %d chars)" % len(NOTES))


def build(mac, wait_min=60):
    for i in range(wait_min * 2):
        bs = call("GET", "/v1/builds?filter[app]=%s&filter[preReleaseVersion.platform]=MAC_OS&sort=-uploadedDate&limit=5" % APP_ID)["data"]
        if bs:
            b = bs[0]
            st = b["attributes"]["processingState"]
            print("newest macOS build", b["attributes"]["version"], st, flush=True)
            if st == "VALID":
                call("PATCH", "/v1/appStoreVersions/%s/relationships/build" % mac["id"], {"data": {"type": "builds", "id": b["id"]}})
                print("build", b["attributes"]["version"], "attached to macOS", mac["attributes"]["versionString"])
                return
            if st in ("FAILED", "INVALID"):
                raise SystemExit("build processing " + st)
        time.sleep(30)
    raise SystemExit("no processed macOS build after %d minutes" % wait_min)


if __name__ == "__main__":
    mac, ios = versions()
    print("macOS version", mac["attributes"]["versionString"], mac["attributes"]["appStoreState"])
    locs = localizations(mac, ios)
    screenshots(locs)
    review(mac, ios)
    build(mac)
    print("DONE - not submitted for review")
