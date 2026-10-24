/*XR-HOME-START*/
/* The four Xrero Office apps on the Mac start page, the same cards as Windows (24 Oct 2026, owner: «تفتح 4 تطبيقات زي
 * ما احنا عملنا», then «خليه نفس الي علي الكمبيوتر»): Document (DOCX), Spreadsheet (XLSX), Presentation (PPTX) and PDF -
 * the start page's own cards, unchanged. On a Mac window the row was wider than the panel (side paddings of 104 + 112
 * px) and the PDF card was cut off behind a scroll bar; here the row fits the panel and wraps on a narrow window. */
(function () {
  if (!/Mac/i.test(navigator.platform || '')) return;
  if (window.__xrHome) return;
  window.__xrHome = true;
  var CSS =
    '#area-document-creation-grid{overflow:visible!important;padding:12px 16px 0!important;margin-left:0!important;margin-right:0!important;min-height:0!important}' +
    '#area-document-creation-grid .document-creation-grid{padding-inline:0!important;padding-left:0!important;padding-right:0!important;' +
    'justify-content:center;flex-wrap:wrap;gap:20px}' +
    '#area-document-creation-grid .document-creation-grid>*{margin-right:0!important;margin-left:0!important}' +
    // the four cards keep their Windows size (172 px) and narrow down to 136 px before a narrow window wraps the row
    '#area-document-creation-grid .document-creation-item{flex:1 1 136px;width:auto!important;max-width:172px;min-width:136px}' +
    '#area-document-creation-grid .document-creation-item .icon{max-width:100%}';
  function add() {
    if (document.getElementById('xr-home-css')) return;
    var st = document.createElement('style'); st.id = 'xr-home-css'; st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }
  add();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', add);
})();
/*XR-HOME-END*/
