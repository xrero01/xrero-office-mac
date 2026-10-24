/*XR-HOME-START*/
/* The four Xrero Office apps on the Mac start page (24 Oct 2026, owner: «تفتح 4 تطبيقات زي ما احنا عملنا»): Windows
 * installs Writer, Calc, Slides and PDF as four apps; the Mac App Store app is one bundle, so its start page opens with
 * the same four as large tiles, in the Windows accent colours. The small "create" row of the start page is hidden
 * (the tiles do the same thing). Documents / Spreadsheets / Presentations = a new file; PDF = choose a PDF to open. */
(function () {
  if (!/Mac/i.test(navigator.platform || '')) return;
  if (window.__xrHome) return;
  window.__xrHome = true;

  function lang() {
    var v = null;
    try { v = localStorage.getItem('xr-lang'); } catch (e) {}
    if (v === 'ar' || v === 'en') return v;
    return (navigator.language || '').toLowerCase().indexOf('ar') === 0 ? 'ar' : 'en';
  }
  var L = {
    en: { head: 'What do you want to work on?',
      word: ['Documents', 'Letters, reports, contracts'], cell: ['Spreadsheets', 'Tables, budgets, invoices'],
      slide: ['Presentations', 'Slides for meetings and clients'], pdf: ['PDF', 'Open, read and edit a PDF'] },
    ar: { head: 'على ماذا تريد أن تعمل؟',
      word: ['المستندات', 'خطابات، تقارير، عقود'], cell: ['جداول البيانات', 'جداول، ميزانيات، فواتير'],
      slide: ['العروض التقديمية', 'شرائح للاجتماعات والعملاء'], pdf: ['PDF', 'افتح ملف PDF واقرأه وعدّله'] }
  };
  // one simple document mark per app, white on the accent
  var ICON = {
    word: '<path d="M7 3h7l5 5v13H7z" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 3v5h5M9.5 12h7M9.5 15h7M9.5 18h5" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
    cell: '<rect x="4" y="5" width="16" height="14" rx="1.5" fill="none" stroke="#fff" stroke-width="1.6"/><path d="M4 10h16M4 14.5h16M10 5v14" stroke="#fff" stroke-width="1.6"/>',
    slide: '<rect x="3.5" y="4.5" width="17" height="11" rx="1.5" fill="none" stroke="#fff" stroke-width="1.6"/><path d="M12 15.5V20M8.5 20h7M7.5 12l3-3 2 2 3.5-4" fill="none" stroke="#fff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    pdf: '<path d="M7 3h7l5 5v13H7z" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/><path d="M14 3v5h5" stroke="#fff" stroke-width="1.6"/><text x="13" y="18" text-anchor="middle" font-size="5.6" font-weight="700" fill="#fff" font-family="-apple-system,Arial">PDF</text>'
  };
  var APPS = [
    { k: 'word', c: '#2B579A', go: function () { window.sdk.command('create:new', 'word'); } },
    { k: 'cell', c: '#107C41', go: function () { window.sdk.command('create:new', 'cell'); } },
    { k: 'slide', c: '#C0392B', go: function () { window.sdk.command('create:new', 'slide'); } },
    { k: 'pdf', c: '#D9472B', go: function () { window.sdk.command('open:folder', ''); } }
  ];
  var CSS =
    '#xr-home{padding:8px 16px 0;margin-bottom:36px;font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}' +
    '#xr-home h2{margin:0 0 16px;font-size:20px;font-weight:600;color:var(--text-normal,#222)}' +
    '#xr-home .g{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:16px}' +
    '@media (max-width:900px){#xr-home .g{grid-template-columns:repeat(2,minmax(150px,1fr))}}' +
    '#xr-home button{display:flex;flex-direction:column;align-items:flex-start;gap:14px;text-align:start;border:0;cursor:pointer;' +
    'border-radius:16px;padding:20px 18px 18px;min-height:168px;color:#fff;font:inherit;' +
    'box-shadow:0 2px 6px rgba(0,0,0,.10),0 10px 24px rgba(0,0,0,.08);transition:transform .15s ease,box-shadow .15s ease}' +
    '#xr-home button:hover{transform:translateY(-2px);box-shadow:0 4px 10px rgba(0,0,0,.14),0 16px 32px rgba(0,0,0,.12)}' +
    '#xr-home button:focus-visible{outline:3px solid #0585A1;outline-offset:3px}' +
    '#xr-home .i{width:52px;height:52px;border-radius:13px;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center}' +
    '#xr-home .i svg{width:32px;height:32px}' +
    '#xr-home b{display:block;font-size:18px;font-weight:600;line-height:1.25}' +
    '#xr-home span{display:block;font-size:13px;opacity:.9;margin-top:4px;line-height:1.4}' +
    '#area-document-creation-grid{display:none!important}';

  function build() {
    var grid = document.getElementById('area-document-creation-grid');
    if (!grid || !window.sdk) return false;
    var t = L[lang()];
    var box = document.getElementById('xr-home');
    if (box && box.getAttribute('data-lang') === lang()) return true;
    if (!document.getElementById('xr-home-css')) {
      var st = document.createElement('style'); st.id = 'xr-home-css'; st.textContent = CSS;
      (document.head || document.documentElement).appendChild(st);
    }
    if (!box) {
      box = document.createElement('section');
      box.id = 'xr-home';
      grid.parentNode.insertBefore(box, grid);
    }
    box.setAttribute('data-lang', lang());
    box.setAttribute('dir', lang() === 'ar' ? 'rtl' : 'ltr');
    box.innerHTML = '';
    var h = document.createElement('h2'); h.textContent = t.head; box.appendChild(h);
    var g = document.createElement('div'); g.className = 'g'; box.appendChild(g);
    APPS.forEach(function (a) {
      var b = document.createElement('button');
      b.type = 'button'; b.id = 'xr-home-' + a.k; b.style.background = a.c;
      b.innerHTML = '<div class="i"><svg viewBox="0 0 24 24" aria-hidden="true">' + ICON[a.k] + '</svg></div>';
      var d = document.createElement('div');
      var n = document.createElement('b'); n.textContent = t[a.k][0];
      var s = document.createElement('span'); s.textContent = t[a.k][1];
      d.appendChild(n); d.appendChild(s); b.appendChild(d);
      b.setAttribute('aria-label', t[a.k][0]);
      b.onclick = function () { try { a.go(); } catch (e) {} };
      g.appendChild(b);
    });
    return true;
  }
  // the start page draws its panels after load and redraws on a language change
  setInterval(build, 700);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
/*XR-HOME-END*/
