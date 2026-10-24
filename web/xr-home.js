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

  // About in the sidebar, as on Windows (24 Oct 2026, owner: «اين صفحة about»). The start page has the item but keeps
  // it hidden until the Windows shell sends its version; on Mac nothing does (the native About is in the app menu), so
  // the item is shown here and opens the same About window with the Mac app's own version.
  var VERSION = '__XR_VERSION__';
  function isAr() {
    try { var v = localStorage.getItem('xr-lang'); if (v) return v === 'ar'; } catch (e) {}
    return document.documentElement.getAttribute('dir') === 'rtl' || /(^|\s)rtl(\s|$)/.test(document.body ? document.body.className : '');
  }
  function aboutBody() {
    var ar = isAr();
    var t = ar ? { ver: 'الإصدار', lic: 'مرخّص بموجب', src: '</> الشيفرة المصدرية', rights: '© Xrero 2026. جميع الحقوق محفوظة.', arch: 'Apple silicon' }
               : { ver: 'Version', lic: 'Licensed under', src: '</> Source', rights: '© Xrero 2026. All rights reserved.', arch: 'Apple silicon' };
    var esc = function (x) { return String(x).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); };
    return '<div class="flexbox"><div class="box-ver">' +
      '<section class="hbox"><div id="idx-about-cut-logo"><svg class="ver-logo">' +
      '<use id="idx-ver-logo--light" href="#idx-logo-light" /><use id="idx-ver-logo--dark" href="#idx-logo-dark" /></svg></div>' +
      '<div class="vbox"><p id="idx-about-appname">Xrero Office</p>' +
      '<p id="idx-about-version"><span>' + t.ver + '</span> ' + esc(VERSION) + ' (' + t.arch + ')</p></div></section><p></p>' +
      '<div class="separator"></div><div class="box-copyright">' +
      '<div class="about-field">' + t.lic + ' <a class="link" target="popup" href="https://www.gnu.org/licenses/agpl-3.0.html">GNU AGPL v3</a></div>' +
      '<div class="about-field"><a class="link" target="popup" href="https://xrero.com/office">xrero.com/office</a></div>' +
      '<div class="about-field"><a class="link" target="popup" href="https://github.com/xrero01/xrero-office-mac">' + esc(t.src) + '</a></div>' +
      '<div class="ver-copyright">' + esc(t.rights) + '</div></div></div></div>';
  }
  function showAbout() {
    if (typeof window.AboutDialog !== 'function' || !window.$) return;
    var d = new window.AboutDialog();
    d.show();
    d.setBody(window.$(aboutBody()));
  }
  function aboutItem() {
    var a = document.querySelector('.tool-menu a[action="about"]');
    if (!a) return;
    var li = a.closest('li');
    if (!li) return;
    if (li.classList.contains('extra')) li.classList.remove('extra');
    if (getComputedStyle(li).display === 'none') {
      // still hidden by another rule of the start page: show it the way the Settings item is shown
      var st = document.querySelector('.tool-menu a[action="settings"]');
      var sd = st && st.closest('li') ? getComputedStyle(st.closest('li')).display : 'list-item';
      li.style.setProperty('display', sd === 'none' ? 'list-item' : sd, 'important');
    }
  }
  // before the start page's own handler (it would look for the Windows shell's About data, which never comes on Mac)
  document.addEventListener('click', function (e) {
    var a = e.target && e.target.closest ? e.target.closest('.tool-menu a[action="about"]') : null;
    if (!a) return;
    e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation();
    showAbout();
  }, true);
  setInterval(aboutItem, 800);
})();
/*XR-HOME-END*/
