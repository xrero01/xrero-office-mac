/*XR-ACCT-START*/
/* Xrero account on macOS (start page + every editor) - the same Xrero account as Xrero Office for Windows and
 * iPhone/iPad, talking straight to xrero.com/office/api (on Windows the native shell does this; on Mac nobody would).
 *
 * 24 Oct 2026 (owner: «لازم الناس تسجل ... زي ما احنا عملنا»): the account is REQUIRED, like Windows - without one the
 * start page and every editor stay behind the sign-in card (no skip). Kept from the App Store rules: creating an
 * account is possible in the app, and so is DELETING it (5.1.1(v)); email + password only - no third-party sign-in, so
 * Sign in with Apple is not required (4.8); documents stay on the Mac; the privacy policy is one click away. Offline,
 * an account that was signed in keeps working (validate fails -> the stored account stays).
 *
 * State (shared localStorage of the app's pages):  xr-acct-token = the account token,
 *   xr-acct = {locked, name, email}  - read by the editors' header chip (same key the Windows start page writes). */
(function () {
  if (!/Mac/i.test(navigator.platform || '')) return;
  if (window.__xrAcct) return;
  window.__xrAcct = true;

  var API = 'https://xrero.com/office/api/';
  var PRIVACY = 'https://xrero.com/privacy';
  var K_TOKEN = 'xr-acct-token', K_INFO = 'xr-acct', K_PLAN = 'xr-acct-plan', K_WELCOME = 'xr-acct-welcome';
  var isEditor = /\/main\/index\.html$/.test(location.pathname);
  var REQUIRED = true;                              // no account -> the card cannot be closed

  function ls(k, v) {
    try {
      if (v === undefined) return localStorage.getItem(k);
      if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v);
    } catch (e) {}
    return null;
  }
  function lang() {
    var v = ls('xr-lang');
    if (v === 'ar' || v === 'en') return v;
    try {
      var l = (new URLSearchParams(location.search).get('lang') || '').toLowerCase();
      if (l) return l.indexOf('ar') === 0 ? 'ar' : 'en';
    } catch (e) {}
    return (navigator.language || '').toLowerCase().indexOf('ar') === 0 ? 'ar' : 'en';
  }
  var S = {
    en: {
      title: 'Xrero account', welcome: 'Welcome to Xrero Office',
      intro: 'Create your free Xrero account, or sign in with the one you use in Xrero Office for Windows and iPhone. Your documents stay on your Mac.',
      signin: 'Sign in', create: 'Create account', name: 'Name', email: 'Email', password: 'Password (8+ characters)',
      skip: 'Continue without an account', close: 'Close', privacy: 'Privacy Policy',
      signout: 'Sign out', del: 'Delete account', delTitle: 'Delete your Xrero account?',
      delText: 'Your account is removed from xrero.com. Documents on this Mac are not touched. Enter your password to confirm.',
      delGo: 'Delete permanently', cancel: 'Cancel', deleted: 'Your account was deleted.', plan: 'Plan',
      net: 'Could not reach xrero.com. Check your internet connection and try again.',
      disabled: 'This account is disabled.', fill: 'Please fill in every field.', short: 'The password must have at least 8 characters.',
      chip: 'Sign in', expired: 'Your sign-in has expired. Sign in again, then delete the account.'
    },
    ar: {
      title: 'حساب Xrero', welcome: 'مرحبًا بك في Xrero Office',
      intro: 'أنشئ حساب Xrero المجاني، أو سجّل الدخول بنفس الحساب الذي تستخدمه في Xrero Office على ويندوز والآيفون. مستنداتك تبقى على جهاز الماك.',
      signin: 'تسجيل الدخول', create: 'إنشاء حساب', name: 'الاسم', email: 'البريد الإلكتروني', password: 'كلمة المرور (8 أحرف على الأقل)',
      skip: 'المتابعة بدون حساب', close: 'إغلاق', privacy: 'سياسة الخصوصية',
      signout: 'تسجيل الخروج', del: 'حذف الحساب', delTitle: 'حذف حساب Xrero؟',
      delText: 'سيُحذف حسابك من xrero.com. المستندات الموجودة على هذا الماك لن تتأثر. أدخل كلمة المرور للتأكيد.',
      delGo: 'حذف نهائي', cancel: 'إلغاء', deleted: 'تم حذف حسابك.', plan: 'الخطة',
      net: 'تعذّر الوصول إلى xrero.com. تحقق من اتصالك بالإنترنت وحاول مرة أخرى.',
      disabled: 'هذا الحساب موقوف.', fill: 'يرجى تعبئة جميع الحقول.', short: 'يجب أن تتكون كلمة المرور من 8 أحرف على الأقل.',
      chip: 'تسجيل الدخول', expired: 'انتهت صلاحية تسجيل الدخول. سجّل الدخول مرة أخرى ثم احذف الحساب.'
    }
  };
  function T() { return S[lang()]; }

  // ------------------------------------------------------------------ account state
  function info() {
    try { var a = JSON.parse(ls(K_INFO) || 'null'); return a && !a.locked && ls(K_TOKEN) ? a : null; } catch (e) { return null; }
  }
  function store(name, email, plan) {
    ls(K_INFO, JSON.stringify({ locked: false, name: name || '', email: email || '' }));
    if (plan) ls(K_PLAN, plan);
  }
  function signOut() {
    ls(K_TOKEN, null); ls(K_PLAN, null);
    ls(K_INFO, JSON.stringify({ locked: true }));
  }
  function post(path, body) {
    // text/plain = a "simple" request: no CORS preflight; the server answers with Access-Control-Allow-Origin
    return fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { status: r.status, j: j }; });
      });
  }
  function refresh() {
    var t = ls(K_TOKEN);
    if (!t) return Promise.resolve(null);
    return post('validate', { token: t }).then(function (r) {
      if (r.status === 401 || r.status === 403) { signOut(); return null; }
      if (r.j && r.j.ok) {
        var a = info() || {};
        store(r.j.name || a.name, r.j.email || a.email, r.j.plan || 'free');
      }
      return info();
    }, function () { return info(); });          // offline: keep the account as it is
  }
  function login(email, password, name, create) {
    var body = create ? { name: name, email: email, password: password } : { email: email, password: password };
    return post(create ? 'signup' : 'login', body).then(function (r) {
      if (!(r.j && r.j.ok && r.j.token)) {
        throw new Error(r.status === 403 ? T().disabled : ((r.j && r.j.error) || T().net));
      }
      ls(K_TOKEN, r.j.token);
      store(r.j.name || name, email, 'free');
      return refresh();
    }, function () { throw new Error(T().net); });
  }
  function deleteAccount(password) {
    var t = ls(K_TOKEN);
    if (!t) { signOut(); return Promise.resolve(); }
    return post('delete', { token: t, password: password }).then(function (r) {
      if (r.j && r.j.ok) { signOut(); return; }
      if (r.status === 401) { signOut(); throw new Error(T().expired); }   // nothing was deleted: sign in again first
      throw new Error((r.j && r.j.error) || T().net);
    }, function () { throw new Error(T().net); });
  }

  // ------------------------------------------------------------------ the account window
  var CSS =
    '#xr-acct-ov{position:fixed;inset:0;z-index:2147483600;background:rgba(0,0,0,.35);display:flex;align-items:center;' +
    'justify-content:center;font:13px -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif}' +
    '#xr-acct-ov .c{width:400px;max-width:92vw;max-height:92vh;overflow:auto;box-sizing:border-box;background:#fff;color:#222;' +
    'border-radius:14px;padding:26px 28px;box-shadow:0 12px 48px rgba(0,0,0,.25)}' +
    '#xr-acct-ov h2{margin:0 0 8px;font-size:19px;font-weight:600}' +
    '#xr-acct-ov p{margin:0 0 16px;color:#666;line-height:1.5}' +
    '#xr-acct-ov .tabs{display:flex;background:#eef1f2;border-radius:8px;padding:3px;margin-bottom:14px}' +
    '#xr-acct-ov .tabs button{flex:1;border:0;background:transparent;padding:7px;border-radius:6px;font:inherit;cursor:pointer;color:#333}' +
    '#xr-acct-ov .tabs button.on{background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.12);font-weight:600}' +
    '#xr-acct-ov input{display:block;width:100%;box-sizing:border-box;margin:0 0 10px;padding:9px 11px;border:1px solid #cfd6d9;' +
    'border-radius:7px;font:inherit;background:#fff;color:#222}' +
    '#xr-acct-ov .go{display:block;width:100%;border:0;border-radius:8px;background:#0585A1;color:#fff;font:inherit;' +
    'font-weight:600;padding:10px;cursor:pointer;margin-top:4px}' +
    '#xr-acct-ov .go:disabled{opacity:.55;cursor:default}' +
    '#xr-acct-ov .go.red{background:#c62828}' +
    '#xr-acct-ov .ln{display:block;width:100%;border:0;background:transparent;color:#0585A1;font:inherit;padding:9px;cursor:pointer;margin-top:6px}' +
    '#xr-acct-ov .ln.red{color:#c62828}' +
    '#xr-acct-ov .err{color:#c62828;min-height:18px;margin:6px 0 0}' +
    '#xr-acct-ov .ok{color:#2e7d32;min-height:18px;margin:6px 0 0}' +
    '#xr-acct-ov .who{display:flex;align-items:center;gap:12px;margin:6px 0 16px}' +
    '#xr-acct-ov .av{width:46px;height:46px;border-radius:50%;background:#0585A1;color:#fff;display:flex;align-items:center;' +
    'justify-content:center;font-size:17px;font-weight:600;flex:none}' +
    '#xr-acct-ov .who b{display:block;font-size:15px}#xr-acct-ov .who span{color:#666}' +
    '#xr-acct-ov a{color:#0585A1}' +
    '#xr-acct-ov .foot{text-align:center;margin-top:10px}' +
    '@media (prefers-color-scheme: dark){#xr-acct-ov .c{background:#2b2b2b;color:#eee}#xr-acct-ov p,#xr-acct-ov .who span{color:#aaa}' +
    '#xr-acct-ov input{background:#1f1f1f;color:#eee;border-color:#555}#xr-acct-ov .tabs{background:#3a3a3a}' +
    '#xr-acct-ov .tabs button{color:#ddd}#xr-acct-ov .tabs button.on{background:#555}}' +
    '#xr-acct-start{position:fixed;top:10px;z-index:2147483000;border:1px solid #cfd6d9;background:#fff;color:#0585A1;' +
    'border-radius:16px;padding:5px 13px;font:600 12px -apple-system,BlinkMacSystemFont,Arial,sans-serif;cursor:pointer}' +
    '#xr-b-signin-mac{display:inline-flex;align-items:center}';

  function css() {
    if (document.getElementById('xr-acct-css')) return;
    var s = document.createElement('style'); s.id = 'xr-acct-css'; s.textContent = CSS;
    (document.head || document.documentElement).appendChild(s);
  }
  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;          // user text is always TEXT, never HTML
    return e;
  }
  function initials(a) {
    var n = (a.name || a.email || '?').trim().split(/\s+/);
    return ((n[0] || '?')[0] + (n.length > 1 ? n[n.length - 1][0] : '')).toUpperCase();
  }
  function walled() { return REQUIRED && !info(); }
  function close() {
    var o = document.getElementById('xr-acct-ov');
    if (o) o.parentNode.removeChild(o);
    if (walled()) { open(true); return; }           // signed out (or account deleted): straight back to the sign-in card
    update();
  }

  function open(welcome) {
    css();
    var old = document.getElementById('xr-acct-ov');   // not close(): with no account close() reopens the card
    if (old) old.parentNode.removeChild(old);
    var t = T();
    var ov = el('div', { id: 'xr-acct-ov', dir: lang() === 'ar' ? 'rtl' : 'ltr', lang: lang() });
    var c = el('div', { 'class': 'c', role: 'dialog', 'aria-modal': 'true', 'aria-label': t.title });
    ov.appendChild(c);
    var wall = walled();
    if (wall) { ov.setAttribute('data-wall', '1'); ov.style.background = '#eef3f4'; }
    ov.addEventListener('mousedown', function (e) { if (e.target === ov && !welcome && !wall) close(); });
    ov.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !wall) close(); });
    document.body.appendChild(ov);
    var a = info();
    if (a) signedIn(c, a); else signedOut(c, welcome);
  }

  function signedOut(c, welcome) {
    var t = T(), create = false;
    c.innerHTML = '';
    c.appendChild(el('h2', {}, welcome ? t.welcome : t.title));
    c.appendChild(el('p', {}, t.intro));
    var tabs = el('div', { 'class': 'tabs', role: 'tablist' });
    var b1 = el('button', { type: 'button', id: 'xr-acct-tab-in', 'class': 'on' }, t.signin);
    var b2 = el('button', { type: 'button', id: 'xr-acct-tab-new' }, t.create);
    tabs.appendChild(b1); tabs.appendChild(b2); c.appendChild(tabs);
    var name = el('input', { id: 'xr-acct-name', type: 'text', placeholder: t.name, autocomplete: 'name' });
    var mail = el('input', { id: 'xr-acct-email', type: 'email', placeholder: t.email, autocomplete: 'email' });
    var pw = el('input', { id: 'xr-acct-password', type: 'password', placeholder: t.password, autocomplete: 'current-password' });
    name.style.display = 'none';
    c.appendChild(name); c.appendChild(mail); c.appendChild(pw);
    var go = el('button', { type: 'button', id: 'xr-acct-submit', 'class': 'go' }, t.signin);
    var err = el('div', { 'class': 'err', role: 'alert' });
    c.appendChild(go); c.appendChild(err);
    function mode(n) {
      create = n;
      b1.className = n ? '' : 'on'; b2.className = n ? 'on' : '';
      name.style.display = n ? 'block' : 'none';
      pw.setAttribute('autocomplete', n ? 'new-password' : 'current-password');
      go.textContent = n ? t.create : t.signin;
      err.textContent = '';
    }
    b1.onclick = function () { mode(false); };
    b2.onclick = function () { mode(true); };
    function submit() {
      var e = mail.value.trim(), p = pw.value, n = name.value.trim();
      if (!e || !p || (create && !n)) { err.textContent = t.fill; return; }
      if (create && p.length < 8) { err.textContent = t.short; return; }
      go.disabled = true; err.textContent = '';
      login(e, p, n, create).then(function () { close(); }, function (x) { go.disabled = false; err.textContent = x.message; });
    }
    go.onclick = submit;
    pw.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    var priv = el('div', { 'class': 'foot' });
    var link = el('a', { href: PRIVACY, target: '_blank', rel: 'noopener', id: 'xr-acct-privacy' }, t.privacy);
    priv.appendChild(link); c.appendChild(priv);
    if (!walled()) {                                // required account: no "continue without" and no close
      var skip = el('button', { type: 'button', id: welcome ? 'xr-acct-skip' : 'xr-acct-close', 'class': 'ln' }, welcome ? t.skip : t.close);
      skip.onclick = close;
      c.appendChild(skip);
    }
    setTimeout(function () { mail.focus(); }, 50);
  }

  function signedIn(c, a) {
    var t = T();
    c.innerHTML = '';
    c.appendChild(el('h2', {}, t.title));
    var who = el('div', { 'class': 'who' });
    who.appendChild(el('div', { 'class': 'av' }, initials(a)));
    var d = el('div');
    d.appendChild(el('b', {}, a.name || t.title));
    d.appendChild(el('span', {}, a.email || ''));
    var plan = ls(K_PLAN);
    if (plan) { d.appendChild(el('br')); d.appendChild(el('span', {}, t.plan + ': ' + plan)); }
    who.appendChild(d); c.appendChild(who);
    var out = el('button', { type: 'button', id: 'xr-acct-signout', 'class': 'go' }, t.signout);
    out.onclick = function () { signOut(); close(); };
    c.appendChild(out);
    var del = el('button', { type: 'button', id: 'xr-acct-delete', 'class': 'ln red' }, t.del);
    del.onclick = function () { confirmDelete(c); };
    c.appendChild(del);
    var priv = el('div', { 'class': 'foot' });
    priv.appendChild(el('a', { href: PRIVACY, target: '_blank', rel: 'noopener' }, t.privacy));
    c.appendChild(priv);
    var cl = el('button', { type: 'button', id: 'xr-acct-close', 'class': 'ln' }, t.close);
    cl.onclick = close;
    c.appendChild(cl);
  }

  function confirmDelete(c) {
    var t = T();
    c.innerHTML = '';
    c.appendChild(el('h2', {}, t.delTitle));
    c.appendChild(el('p', {}, t.delText));
    var pw = el('input', { id: 'xr-acct-delete-password', type: 'password', placeholder: t.password, autocomplete: 'current-password' });
    c.appendChild(pw);
    var go = el('button', { type: 'button', id: 'xr-acct-delete-confirm', 'class': 'go red' }, t.delGo);
    var err = el('div', { 'class': 'err', role: 'alert' });
    c.appendChild(go); c.appendChild(err);
    go.onclick = function () {
      go.disabled = true; err.textContent = '';
      deleteAccount(pw.value).then(function () {
        c.innerHTML = '';
        c.appendChild(el('h2', {}, t.title));
        c.appendChild(el('div', { 'class': 'ok' }, t.deleted));
        var cl = el('button', { type: 'button', id: 'xr-acct-close', 'class': 'ln' }, t.close);
        cl.onclick = close; c.appendChild(cl);
      }, function (x) { go.disabled = false; err.textContent = x.message; });
    };
    var back = el('button', { type: 'button', 'class': 'ln' }, t.cancel);
    back.onclick = function () { var a = info(); if (a) signedIn(c, a); else close(); };
    c.appendChild(back);
    setTimeout(function () { pw.focus(); }, 50);
  }

  // ------------------------------------------------------------------ entry points
  // start page: a small pill (Sign in / the account name), top corner opposite the reading direction's start
  function startPill() {
    var b = document.getElementById('xr-acct-start');
    if (!b) {
      b = el('button', { type: 'button', id: 'xr-acct-start' });
      b.onclick = function () { open(false); };
      document.body.appendChild(b);
    }
    var a = info(), t = T(), rtl = lang() === 'ar';
    var label = a ? (a.name || a.email || t.title) : t.chip;
    if (b.textContent !== label) b.textContent = label;
    b.setAttribute('aria-label', a ? t.title + ': ' + label : t.chip);
    b.style.right = rtl ? 'auto' : '14px';
    b.style.left = rtl ? '14px' : 'auto';
  }
  // editors: the header has its own account chip + menu (shown when signed in); add a Sign in button otherwise
  function editorButton() {
    var box = document.getElementById('xr-hdr-btns');
    if (!box) return;
    var mine = document.getElementById('xr-b-signin-mac');
    if (info() || document.getElementById('xr-b-acct')) { if (mine) mine.parentNode.removeChild(mine); return; }
    if (mine) return;
    var b = el('button', { type: 'button', id: 'xr-b-signin-mac', 'class': 'xr-share' }, T().chip);
    b.setAttribute('aria-label', T().chip);
    b.onclick = function (e) { e.stopPropagation(); open(false); };
    box.appendChild(b);
  }
  function update() {
    if (!document.body) return;
    css();
    if (walled() && !document.getElementById('xr-acct-ov')) { open(true); return; }   // nothing opens without an account
    if (isEditor) editorButton(); else startPill();
  }
  // the editors' own account menu ("My account" / "Sign out") goes to the Windows shell - answer it here
  document.addEventListener('click', function (e) {
    var tg = e.target && e.target.closest ? e.target.closest('#xr-am-view,#xr-am-out') : null;
    if (!tg) return;
    if (tg.id === 'xr-am-view') { e.stopPropagation(); e.preventDefault(); open(false); var m = document.getElementById('xr-acct-menu'); if (m) m.classList.remove('show'); }
    else ls(K_TOKEN, null);                         // the chip's own handler marks xr-acct locked
  }, true);

  function start() {
    update();
    setInterval(update, 800);
    if (isEditor) { if (walled()) open(true); return; }
    refresh().then(function (a) {
      update();
      if (!a) { ls(K_WELCOME, '1'); if (!document.getElementById('xr-acct-ov')) open(true); }
    });
  }
  window.XreroAccount = { open: open, refresh: refresh, signOut: signOut };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
/*XR-ACCT-END*/
