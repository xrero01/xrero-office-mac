# Mac App Store pictures - notes (16 Nov 2026)

Five pictures per language, in the listing's order (`mas/mas_metadata.py` SHOTS):

| # | en-US | ar-SA | What it shows |
|---|-------|-------|---------------|
| 1 | mac_en_editor.png | mac_ar_editor.png | the document editor, an Arabic-led report with an English part, caret in the Arabic summary |
| 2 | mac_en_start.png | mac_ar_start.png | the start page, the signed-in account (a team), seven demo files under Recent files |
| 3 | mac_en_sheet.png | mac_ar_sheet.png | the spreadsheet editor: E5 selected (`=SUM(B5:D5)` in the formula bar), the file's column chart |
| 4 | mac_en_slides.png | mac_ar_slides.png | the presentation editor: caret after the title of the bilingual title slide, the four slides in the side panel |
| 5 | mac_en_pdf.png | mac_ar_pdf.png | the PDF editor: Comment tab, a form filled in the app, a highlight, a pen circle and a sticky note made in the app |

The document picture is first: it shows the app's point (Arabic and English, right to left) in the picture that
search results show. The start page is second and carries the account line next to the account pill.

All ten are real captures of the App Store variant (sandboxed test copy, ad hoc) on the CI Mac:
`build-mac.yml` with `test_only=true` runs `mas/store_capture.py`. The pictures here come from run 34
(43838154183, every capture check green; round 3 - runs 32 and 33 each failed one new check, below). They are
composed with
`v20/mac/store_new_icons` (`prep.py` + `compose.js`, Cairo, the same background and window place for all ten:
the window 2400 px wide, 83 % of the picture). English pictures come from the app in en-US, Arabic pictures from
the app in ar-SA. Demo files only (`mas/store_demo.py`): neutral UAE content, counts and dates, no money amounts,
no names, no e-mail addresses. The account shown is a team ("Operations team" / "فريق العمليات", initials OT / فع),
stored locally; nothing talks to xrero.com during the capture. (Round 3: the earlier "فريق المشاريع" gave the joined
initials "فم", which an Arabic reader takes for the word "mouth". The initials skip the article, as before.)

How each picture is made (and what is not done in the app):
- **Window**: one size for all ten, 1376 x 800 pt. `store_capture.py` measures, in the English and Arabic
  spreadsheet and presentation editors, the narrowest window at which no ribbon group folds into "More"
  (`ribbon-fit.json`), and `mas/hidpi.swift` gives the CI display a 1600 x 1200 mode for it.
- **Start page**: seven demo files are opened from `/Users/Shared/Office files` (the Recent files' location
  column shows that folder, not the CI checkout), and their times are set to working hours (09:30-10:40) in the
  app's own recent list. Round 3: four rows left the lower third of the window empty, so three small files a user
  of the same team would have opened earlier come first (`store_extra_*`: an office guide, a training plan, a
  welcome slide - real files, opened in the app; only their names, kinds and times are in the picture).
- **Sheet**: the table's totals are SUM formulas. E5 is selected the way the name box does it (`asc_findCell`).
  The chart is the file's own chart part (16 x 9.4 cm, so it fills the columns beside the table), drawn by the
  editor; its legend is a list on the right (one row paired the colours with the wrong quarters when read right to
  left). Column A is indented one step from its start side.
- **Slides**: a real click into slide 1's title. The caret is then put after the title's last letter with the
  editor's own `MoveCursorToEndPos`, because the End key does not do that on macOS. The title's frame sits 0.3 in
  clear of its first and last letter. Round 3: the headline says "Presentations in Arabic and English", so the
  title slide of each deck is bilingual, as UAE decks often are: the title in the deck's language, and under it the
  same title in the other language ("مراجعة الربع الثالث" in the English deck, "Q3 review" in the Arabic one),
  each paragraph in its own direction and face.
- **PDF**: the Comment tab is clicked, the footer line is selected with the mouse and highlighted with the Highlight
  button, a circle is drawn around the date field with the red pen, and a sticky note is added with right click >
  Add comment. Then the form is filled the way a user does it: Tab to each field, type, and Enter to tick the
  boxes. After the pictures the form is saved (Cmd+S), read back from the file and opened again in the app: the
  fields, the ticks and the three marks are all kept (run 34, both languages). Round 3: the highlight stopped one
  letter short, before the line's full stop. The mouse drag now ends past the line (3 pt in English, 15 pt in
  Arabic), the capture reads back what the selection holds and selects again (further past, then from the other
  end) while the full stop is missing, and it checks that the highlight's rectangle covers the line. In English
  that was enough (run 32). In Arabic every drag left out the line's last letter (runs 32 and 33): the app's PDF
  viewer drops the last letter of a right-to-left line from a selection that runs past the line's end. So the
  Arabic demo line ends with a no-break space after the full stop (invisible; MuPDF keeps it in the same span),
  which is the letter left out; the full stop is highlighted (run 34). A real Arabic PDF line selected this way
  loses its last letter in the app (the viewer code is the same sdkjs as on Windows, not checked there); not changed
  in the app. The text fields have a 2 pt border with no colour: the editor insets a
  field's text by twice its border width (sdkjs `CTextField.RecalculateContentRect`), so typed text sits 4 pt in
  from the frame, which is drawn on the page just outside the field. "For office use" is at the foot of the page,
  so the window's bottom edge runs through blank page, not under that heading.
- **Caret**: for the window and Retina captures of pictures 1, 4 and 5, the editor's caret blink timer is paused
  with its caret shown, then started again. This shows the editor's own caret at its own place, not an added one.

## Real-UI issues found while making them

Fixed in the Mac app (`scripts/patch_bundle.py` / `web/xr-*.js`, Mac bundle only; the Windows payload is unchanged):
- **Window title right to left** (round 3, XR-TITLE-RTL): in every Arabic editor the file name over the ribbon sat
  about 90 pt left of the window's centre (English: centred). Not a composing effect - the editor's header centres
  the title by padding it by the difference between the space on its left and on its right (`Header.js`
  `updateDocNamePosition`), and both measures are physical: the box's left offset and the width of the next header
  group. Right to left the next group is on the left and the quick-access buttons on the right, so both measured the
  left side and the title was centred in the space beside the buttons. Right to left the two sides now swap; left
  to right nothing changes. The capture checks the title's centre against the window's in all eight editor pictures.
  The Windows app has the same fault.
- **Active ribbon tab** (round 3, XR-TABLINE): its underline kept each editor's own colour (documents #446995,
  spreadsheets #3A8056, presentations #B75B44, PDF #AA5252); on the one teal header the documents and spreadsheet
  underlines all but disappeared, so no tab looked active. It is white in all four, like the tab names. Setting
  only the colour variables (`--highlight-toolbar-tab-underline-*`, !important on `.theme-white`, the same file and
  selector as the teal header) was not enough on the Mac (run 32 still measured the editors' own colours, although
  Chrome drew that stylesheet white), so the underline itself is set white as well (`border-top-color`); run 33 and
  34 measured white in all eight editor pictures.
- **Present button** (round 3, XR-PRESENT, the presentation editor's status bar): its label ran into the split
  divider (Bootstrap's `.btn-group .btn + .btn` margin wins over the payload's 7 px), and the chevron was half dark
  on the red (only its top border was made white). The label now ends 9 px before the divider, in the Mac system
  font, and the chevron is white. The Arabic label was "عرض تقديمي" - the noun "a presentation", the Presentation
  app's own name on the start page - on a button that starts the slide show; it is now "بدء العرض", the words of
  the button's own tooltip. The button keeps its red (the app's colour for it, also on Windows).
- **PDF forms, ticks lost on Save** (run 28): a check box ticked with Enter showed the tick, but Save wrote it as
  "Off", so the saved file and the reopened copy had no ticks, and the editor logged "changesError". sdkjs 9.4
  `CPDFDoc.EnterDownActiveField` toggles the box outside an editing action and never commits it; a mouse click
  goes through `OnMouseUpField` (the toggle inside `DoAction`, then the commit). The Mac editors send Enter on a
  box down that same path (`pdfKeyTick` in the editors' shim). The Windows app still has this engine behaviour.
- **Arabic spreadsheet ribbon**: the Home tab's "Format" button (shown once the window is wide enough for the cells
  group) was English; now "تنسيق". The number-format dialog's "Format" label is now "التنسيق".
- **Arabic spreadsheet Collaboration tab**: "العمل المشترك", while the other three editors say "التعاون"; now
  "التعاون" in all four.
- **Arabic PDF editor**: the Collaboration ribbon tab was in English. Now "التعاون".
- **Arabic start page, Recent files' folder** (run 29): the location column laid a Latin path out right to left,
  so "/Users/Shared/Office files" read "Users/Shared/Office files/" (the first slash at the far end). The path now
  takes its direction from its own text (`unicode-bidi: plaintext`, `web/xr-home.js`) and stays right aligned;
  Arabic folder names inside a path still read right to left.
- **Arabic start page**: the Recent files' date column said "مفتوحة مؤخرا"; now "آخر فتح" (the English
  column is "Last opened"). The four app cards use the plain kit pictures (no English badge on them).
- **Arabic account initials**: the article is skipped ("فريق العمليات" -> "فع", not "فا"), on the start page pill
  and on the editors' account chip. Two Arabic initials are drawn joined, so some pairs read as a word (round 3:
  "فم" = "mouth"); the pictures' team name was chosen so the pair is not a word. Real users' pairs can still form
  one (for example "مع"); not changed in the app.
- **Arabic spreadsheet formula bar**: a formula took the right-to-left direction of the interface, so
  `=SUM(B5:D5)` read `SUM(B5:D5)=`. Each line now takes its direction from its own text
  (`unicode-bidi: plaintext`) and stays right aligned (`XR-FBIDI`).

Not fixed (engine behaviour; the capture works around it or avoids it):
- **Arabic PDF, bold lam-alef** (run 27): the app's PDF renderer drew the bold heading "ملاحظات" as "مادحظات" (the
  lam-alef ligature broken). The regular weight ("الاجتماع", "الأقل") was right, and MuPDF draws the same file
  correctly. The page text is IBM Plex Sans Arabic Bold, embedded as a subset by PyMuPDF; whether the subset is the
  cause is not proven. Real Arabic PDFs with such bold text will show the same fault in the app (and on Windows).
  The demo form avoids bold words with lam-alef ("تفاصيل إضافية", "خاص بالمكتب"); `store_demo.py` asserts it.
- **Arabic PDF form, first letter lost** (runs 23-31): in the right-to-left form, the first input typed into the
  date field after tabbing into it does not arrive. Typed letter by letter, "2" was lost and "4/11/2026" stayed.
  Typed as one piece, the whole piece was lost. The capture reads the value back and types the missing start
  again, as a user would on seeing it. The English form and the Arabic fields that start with letters keep
  everything. This needs a separate look at sdkjs `pdf/src/forms` (font loading on the first digit is suspected,
  not proven).
- **Arabic text in PDF form fields**: the demo's fields use Helvetica (no Arabic), so the app types Arabic in a
  fallback face; it is set to 14 pt in the Arabic form (11 pt in the English one) so it reads at the size of the
  labels.
- **Backspace in that field** (run 25): Backspace sent by the capture (a DevTools key event) deleted nothing. This
  may be specific to synthetic key events. It was not checked with a real keyboard.
- **Presentation status bar language**: Arabic slide text written as `lang="ar-AE"` is reported as "العربية –
  المملكة العربية السعودية". The document editor reports the same kind of text as "...الإمارات العربية المتحدة".
  The Arabic slides picture shows the Saudi Arabia wording.
- **Caret on the dark title slide** (picture 4): the caret is held shown (checked), but the editor draws it dark,
  so it does not stand out on the ink-coloured slide (run 33 caught it light once; run 34, the pictures, dark). The
  title's selection frame and the ribbon (its font, 54, Bold) show the edit.
- **Caret in the Arabic Notes field** (picture 5, ar): the field is right aligned, and the engine draws the caret
  at the right edge of its Arabic line after typing, not at the line's left end.
- **Spreadsheet chart with a reversed category axis** (right-to-left chart, `orientation maxMin`): the editor
  turned the first category label on its side and dropped the others. The Arabic chart's categories therefore
  run left to right, the same as in the English chart.
- **Tab titles** are cut after about 14 Latin characters ("Projects 2026...."), and a file name with digits
  displays out of order right to left. The demo files are opened under short names.
- **Window chrome**: the CI display has no 2x mode (`mas/hidpi.swift` lists the modes in
  `out/store/display.log`). The title bar is the 1x capture scaled 2x in all ten pictures. The page below it is
  the app's own Retina render.
- **CI host prompt**: run 26's 1x capture of the Arabic start page caught the runner's own macOS prompt ("Allow
  hosted-compute- to find devices on local networks?") over the page. That prompt is not from Xrero, and it is not
  in the pictures, which take only the title bar from that capture.
- The editors are opened with the CI account's name in their address (`username=Anka`). That name is not shown
  anywhere on screen; the capture checks the visible text and the title bars for user names and e-mail addresses.
- **Digits in the Arabic document picture** (round 3 review): the style gallery says "العنوان ١ / ٢ / ٣"
  (Arabic-Indic digits: the editor's own Arabic text for its heading styles), while the rest of the window uses
  Western digits. No demo or capture choice changes the editor's style names, and it is the translation's choice
  (common in ar-SA), not a fault, so it is left as the app shows it. Western digits inside Arabic lines ("29",
  "2026") look taller and heavier than the Arabic around them: they are Geeza Pro's own Western digits - the
  editor sets every letter of a right-to-left run in its complex-script face (sdkjs `GetFontSlot`: isRTL ->
  the CS slot), so the run's Latin face plays no part. Only another Arabic face would change them; Geeza Pro stays.
- **"AI" ribbon tab**: the AI plugin's tab is real interface and stays in the pictures; no caption or store text
  makes a claim about it.

Store text: the description in `mas_metadata.py` now says "plus PDF viewing, form filling and comments" (it said
"plus PDF viewing" while picture 5 shows a form filled and annotated), after the round trip above held in run
31. Not sent to App Store Connect from here (`mas-meta` is a separate, owner-run step). The round-3 review also
asked to rename the description's headings "REAL ARABIC SUPPORT" / "دعم حقيقي للعربية" and "A FULL EDITOR, NOT A
VIEWER" / "محرر كامل وليس مجرد عارض" (comparison wording the captions no longer use). That is the owner's text and it
does not contradict the pictures, so it is left for the owner.

Captions (round 3, `store_new_icons/compose.js`; round 2 kept as `compose_2026-11-16e.js`): "بالصيغ" instead of
"مع الصيغ" (a word-for-word "with"), "بصيغة docx / xlsx / pptx" instead of "كملفات" (and in the document line the
document is what is saved, not its paragraphs: "ويُحفظ المستند بصيغة docx"), the PDF headline "املأ نماذج PDF وعلّق
عليها" and its line ending "وأضف الملاحظات" (so "أضف تعليقات" is not said twice). No headline is wider than 2200 px:
the Arabic start headline ran the window's full width, so it is set a little smaller rather than reworded.
