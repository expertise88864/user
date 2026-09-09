/* admin-extras.js — feature additions for /admin.html (the WYSIWYG admin).
 *
 * Adds (loaded as a module by admin.html):
 *   1. SEO Score panel    — live-updates as you type
 *   2. Spell-check        — Chinese typo detection (LanguageTool API)
 *   3. Medical dictionary — auto-link first mention with <dfn title="…">
 *   4. Article reorder    — drag-drop to set DN.ARTICLES order in blog-shared.js
 *   5. Version rollback   — pick from last 30 commits, restore any
 *   6. Font / typography  — change body-font / heading-font live, persist as CSS var
 *   7. Image editor       — crop / resize before upload
 *   8. FAQPage JSON-LD    — auto-extract <details>/<summary> Q&A → schema
 *
 * Uses the editor's shared session-auth.js controller for its tab-scoped
 * credential and reads the current file from the DOM (#filePath text).
 *
 * SECURITY 2026-05-25 — migrated PAT from localStorage to sessionStorage:
 *   1. sessionStorage clears on tab close → drastically smaller XSS
 *      attack window than localStorage (which persists indefinitely).
 *   2. 24-hour expiry timestamp stored alongside; getPat() returns ''
 *      after expiry and clears the entry → forces re-paste.
 *   3. The shared controller removes legacy localStorage credentials;
 *      the main editor prompts for a new PAT when login is required.
 *
 * SECURITY 2026-05-25 (Phase 2) — hybrid cookie auth for /api/admin/*:
 *   - When setPat() is called we ALSO POST the PAT to /api/admin/login,
 *     which stores it in Vercel KV server-side and sets an HttpOnly
 *     cookie. Same-origin API calls use that cookie. Direct GitHub calls
 *     still use the JS-readable, tab-scoped PAT; HttpOnly does not protect
 *     that separate copy from XSS.
 *   - The 8 direct-to-api.github.com calls (commits, image upload via
 *     GitHub Contents API, version rollback, etc.) still send the PAT
 *     in an Authorization header because the browser is the one talking
 *     to GitHub directly there — there's no server in the middle that
 *     could hold the PAT for us. Removing those would require proxying
 *     every GitHub call through a custom /api/admin/* endpoint, which
 *     is Phase 3 (deferred — high churn for marginal gain since the
 *     PAT now expires in 24h and sessionStorage clears on tab close).
 *
 * Hook into admin.html via a single tag:
 *   <script type="module" src="/admin/admin-extras.js"></script>
 */

(function () {
  'use strict';

  const REPO = 'expertise88864/user';
  const BRANCH = 'main';
  // The main editor loads the shared authentication controller first.
  const getPat = () => window.cdAdminAuth ? window.cdAdminAuth.getPat() : '';
  function getCurrentFile() {
    const t = (document.getElementById('filePath') || {}).textContent || '';
    return t === '尚未選擇檔案' ? null : t;
  }
  function getCurrentSha() {
    // CURRENT_SHA is shown in #shaInfo as e.g. "sha:abc123"; if not, null
    const t = (document.getElementById('shaInfo') || {}).textContent || '';
    const m = t.match(/[0-9a-f]{7,40}/);
    return m ? m[0] : null;
  }

  function ready(cb) {
    if (document.getElementById('editorPane')) cb();
    else setTimeout(() => ready(cb), 60);
  }

  // ─────────────────────────────────────────────────────────────
  // STYLES — injected once
  // ─────────────────────────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById('admin-extras-css')) return;
    const css = `
.ax-panel{position:fixed;right:14px;top:74px;width:316px;max-height:calc(100vh - 96px);overflow-y:auto;background:#fff;border:1px solid #dcd5c8;border-radius:14px;box-shadow:0 14px 36px -16px rgba(12,81,89,.32);z-index:60;font-family:'Inter','Noto Sans TC',sans-serif;font-size:13px;color:#2a2620}
.ax-panel.collapsed{height:42px;overflow:hidden}
.ax-panel header{padding:10px 14px;border-bottom:1px solid #ebe4d8;display:flex;align-items:center;justify-content:space-between;cursor:pointer;background:#f5fbfa}
.ax-panel header h3{margin:0;font-size:13px;font-weight:700;color:#0c5159}
.ax-panel .ax-tabs{display:flex;border-bottom:1px solid #ebe4d8;background:#fafaf6}
.ax-panel .ax-tabs button{flex:1;padding:8px 6px;font-size:11.5px;border:none;background:transparent;cursor:pointer;color:#5e574e;font-weight:600;border-bottom:2px solid transparent}
.ax-panel .ax-tabs button.active{color:#0c5159;border-bottom-color:#0c5159}
.ax-panel .ax-body{padding:14px;line-height:1.7}
.ax-panel .ax-tab{display:none}
.ax-panel .ax-tab.active{display:block}
.ax-meter{background:#ebe4d8;border-radius:8px;height:10px;overflow:hidden;margin:6px 0}
.ax-meter-fill{height:100%;background:linear-gradient(90deg,#fca5a5 0%,#fcd34d 50%,#86efac 100%);transition:width .3s ease}
.ax-checks{margin:8px 0;padding-left:0;list-style:none}
.ax-checks li{padding:4px 0;font-size:12px;display:flex;gap:6px;align-items:flex-start}
.ax-checks .ok{color:#065f46}
.ax-checks .warn{color:#92400e}
.ax-checks .err{color:#7f1d1d}
.ax-checks li::before{content:'•';margin-right:4px}
.ax-checks li.ok::before{content:'✓';color:#22c55e}
.ax-checks li.warn::before{content:'!';color:#f59e0b}
.ax-checks li.err::before{content:'✗';color:#ef4444}
.ax-btn{padding:6px 10px;font-size:12px;border:1px solid #dcd5c8;border-radius:6px;background:#fff;cursor:pointer;color:#4d6358;font-weight:600;margin:4px 4px 4px 0}
.ax-btn:hover{border-color:#7a9285}
.ax-btn.primary{background:linear-gradient(180deg,#a4b5a8,#4d6358);color:#fff;border-color:#4d6358}
.ax-typo-issue{padding:6px 8px;margin:4px 0;background:#fef3c7;border:1px solid #fcd34d;border-radius:6px;font-size:11.5px;line-height:1.55;cursor:pointer}
.ax-typo-issue:hover{background:#fde68a}
.ax-typo-issue strong{color:#92400e}
.ax-version{padding:8px 10px;border:1px solid #ebe4d8;border-radius:8px;margin:4px 0;font-size:11.5px;cursor:pointer;background:#fff;line-height:1.5}
.ax-version:hover{border-color:#7a9285;background:#f5fbfa}
.ax-version .ax-v-msg{color:#2a2620;font-weight:600}
.ax-version .ax-v-time{color:#8b8378;font-size:10.5px}
.ax-reorder-list{list-style:none;margin:0;padding:0;max-height:380px;overflow-y:auto}
.ax-reorder-list li{padding:6px 8px;border:1px solid #ebe4d8;border-radius:6px;margin:3px 0;font-size:11.5px;background:#fff;cursor:grab}
.ax-reorder-list li.dragging{opacity:.4;cursor:grabbing}
.ax-reorder-list li.drag-over{border-color:#0c5159;background:#ecfdf5}
.ax-font-row{display:flex;gap:6px;margin:6px 0;align-items:center;flex-wrap:wrap}
.ax-font-row label{font-size:11.5px;color:#5e574e;flex:0 0 90px}
.ax-font-row select{flex:1;padding:5px 8px;font-size:12px;border:1px solid #dcd5c8;border-radius:6px;background:#fff}
.ax-image-editor{position:fixed;inset:40px;background:#fff;border-radius:16px;z-index:200;display:flex;flex-direction:column;box-shadow:0 24px 48px -16px rgba(12,81,89,.55)}
.ax-image-editor header{padding:14px 18px;border-bottom:1px solid #ebe4d8;display:flex;justify-content:space-between;align-items:center}
.ax-image-editor canvas{max-width:100%;max-height:100%;display:block;margin:auto}
.ax-image-editor .ax-canvas-wrap{flex:1;overflow:auto;padding:14px;display:flex;align-items:center;justify-content:center;background:repeating-conic-gradient(#f5fbfa 0 25%,#fff 0 50%) 0/24px 24px}
.ax-image-editor footer{padding:12px 18px;border-top:1px solid #ebe4d8;display:flex;gap:8px;justify-content:flex-end}
.ax-toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#0c5159;color:#fff;padding:10px 18px;border-radius:8px;z-index:300;font-size:13px;box-shadow:0 8px 24px -10px rgba(0,0,0,.4);animation:axSlide .3s ease}
@keyframes axSlide{from{opacity:0;transform:translate(-50%,12px)}to{opacity:1;transform:translate(-50%,0)}}
.ax-dfn-btn{position:absolute;background:#0c5159;color:#fff;border:none;border-radius:6px;padding:4px 8px;font-size:11px;cursor:pointer;z-index:50;box-shadow:0 4px 10px rgba(0,0,0,.25)}
`;
    const style = document.createElement('style');
    style.id = 'admin-extras-css';
    style.textContent = css;
    document.head.appendChild(style);
  }

  // ─────────────────────────────────────────────────────────────
  // TOAST
  // ─────────────────────────────────────────────────────────────
  function toast(msg, ms) {
    const el = document.createElement('div');
    el.className = 'ax-toast';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms || 2200);
  }

  // ─────────────────────────────────────────────────────────────
  // PANEL SHELL — tabbed UI for all features
  // ─────────────────────────────────────────────────────────────
  function buildPanel() {
    const panel = document.createElement('div');
    panel.className = 'ax-panel';
    panel.id = 'axPanel';
    panel.innerHTML = `
<header><h3>🛠 編輯助手</h3><span style="font-size:11px;color:#8b8378">▾ 點此摺疊</span></header>
<div class="ax-tabs">
  <button type="button" data-tab="seo" class="active">SEO</button>
  <button type="button" data-tab="spell">錯字</button>
  <button type="button" data-tab="dict">詞典</button>
  <button type="button" data-tab="font">字型</button>
  <button type="button" data-tab="version">歷史</button>
  <button type="button" data-tab="reorder">排序</button>
  <button type="button" data-tab="picks">熱門</button>
</div>
<div class="ax-body">
  <div class="ax-tab active" data-tab="seo">
    <div style="font-size:12px;color:#5e574e;margin-bottom:6px">文章檢查與搜尋摘要</div>
    <div style="font-size:18px;font-weight:800;color:#0c5159" id="axSeoScore" role="status">請先載入文章</div>
    <p style="font-size:12px;color:#5e574e">檢查待儲存內容；提示不代表搜尋排名、點閱率或發布通過。</p>
    <div style="padding:10px;border:1px solid #dcd5c8;border-radius:8px;overflow-wrap:anywhere">
      <strong id="axSeoTitle"></strong><div id="axSeoUrl" style="font-size:11px"></div><p id="axSeoDescription" style="margin:6px 0;font-size:13px"></p>
      <small>摘要示意，Google 可能依查詢與裝置改寫。</small>
    </div>
    <ul class="ax-checks" id="axSeoChecks"></ul>
    <button type="button" class="ax-btn" id="axSeoRefresh">重新檢查</button>
    <button type="button" class="ax-btn" id="axFaqGen">產生 FAQPage JSON-LD</button>
  </div>
  <div class="ax-tab" data-tab="spell">
    <div style="font-size:12px;color:#5e574e">中文錯字 / 標點 / 全形偵測（用 LanguageTool API）</div>
    <button type="button" class="ax-btn primary" id="axSpellRun" style="margin-top:8px">🔍 開始檢查</button>
    <div id="axSpellStats" style="font-size:11px;color:#8b8378;margin-top:8px"></div>
    <div id="axSpellList"></div>
  </div>
  <div class="ax-tab" data-tab="dict">
    <div style="font-size:12px;color:#5e574e">皮膚科專業詞彙自動加 &lt;dfn&gt; tooltip 解釋（首次提到才加）</div>
    <button type="button" class="ax-btn primary" id="axDictRun" style="margin-top:8px">⚡ 自動加 dfn</button>
    <button type="button" class="ax-btn" id="axDictUndo">↩ 復原</button>
    <div id="axDictStats" style="font-size:11px;color:#8b8378;margin-top:8px"></div>
    <details style="margin-top:10px"><summary style="font-size:11.5px;cursor:pointer;color:#0c5159">📖 詞典內容（${''}個詞）</summary>
    <div id="axDictList" style="font-size:11px;line-height:1.7;margin-top:6px;max-height:240px;overflow-y:auto"></div></details>
  </div>
  <div class="ax-tab" data-tab="font">
    <div style="font-size:12px;color:#5e574e;margin-bottom:8px">即時調整網站字型（會寫進 /assets/theme.css）</div>
    <div class="ax-font-row">
      <label>內文字型</label>
      <select id="axBodyFont">
        <option value="">— 維持目前 —</option>
        <option value="'Inter','Noto Sans TC',sans-serif">Inter + Noto Sans TC（預設）</option>
        <option value="'Source Han Sans TC','Noto Sans TC',sans-serif">思源黑體</option>
        <option value="'PingFang TC','Microsoft JhengHei',sans-serif">PingFang / 微軟正黑</option>
        <option value="Georgia,'Noto Serif TC',serif">Georgia + Noto Serif TC</option>
      </select>
    </div>
    <div class="ax-font-row">
      <label>標題字型</label>
      <select id="axHeadFont">
        <option value="">— 維持目前 —</option>
        <option value="'Noto Serif TC',Georgia,serif">Noto Serif TC（預設）</option>
        <option value="'Source Han Serif TC','Noto Serif TC',serif">思源宋體</option>
        <option value="'Inter','Noto Sans TC',sans-serif">Inter（無襯線）</option>
      </select>
    </div>
    <div class="ax-font-row">
      <label>內文字級</label>
      <select id="axBodySize">
        <option value="">— 維持 —</option>
        <option value="14.5px">14.5px (緊湊)</option>
        <option value="16px">16px (標準)</option>
        <option value="17px">17px (舒適)</option>
        <option value="18px">18px (大字)</option>
      </select>
    </div>
    <button type="button" class="ax-btn primary" id="axFontApply" style="margin-top:8px">套用至全站</button>
    <button type="button" class="ax-btn" id="axFontPreview">僅預覽（不存）</button>
  </div>
  <div class="ax-tab" data-tab="version">
    <div style="font-size:12px;color:#5e574e">最近 30 個版本（點任一版本可還原）</div>
    <button type="button" class="ax-btn primary" id="axVersionLoad" style="margin-top:8px">↻ 載入歷史</button>
    <div id="axVersionList" style="margin-top:8px"></div>
  </div>
  <div class="ax-tab" data-tab="reorder">
    <div style="font-size:12px;color:#5e574e">拖曳調整文章在「最新文章」清單的順序</div>
    <button type="button" class="ax-btn primary" id="axReorderLoad" style="margin-top:8px">📋 載入清單</button>
    <ol class="ax-reorder-list" id="axReorderList"></ol>
    <button type="button" class="ax-btn primary" id="axReorderSave" style="display:none;margin-top:8px">💾 儲存新順序</button>
  </div>
  <div class="ax-tab" data-tab="picks">
    <div style="font-size:12px;color:#5e574e">設定首頁「熱門推薦」5-12 篇文章(立即生效,不需 redeploy)</div>
    <button type="button" class="ax-btn primary" id="axPicksLoad" style="margin-top:8px">📥 載入目前清單</button>
    <ol class="ax-reorder-list" id="axPicksList" style="margin-top:8px"></ol>
    <div style="display:flex;gap:6px;margin-top:8px">
      <input id="axPicksAdd" placeholder="新增 slug (如 acne-myths)" style="flex:1;padding:5px 8px;font-size:12px;border:1px solid #dcd5c8;border-radius:6px"/>
      <button type="button" class="ax-btn" id="axPicksAddBtn">+</button>
    </div>
    <button type="button" class="ax-btn primary" id="axPicksSave" style="display:none;margin-top:8px">💾 儲存(寫入 KV)</button>
    <div id="axPicksStats" style="font-size:11px;color:#8b8378;margin-top:8px"></div>
  </div>
</div>`;
    document.body.appendChild(panel);

    // Tab switching
    panel.querySelectorAll('.ax-tabs button').forEach(b => {
      b.addEventListener('click', () => {
        panel.querySelectorAll('.ax-tabs button').forEach(x => x.classList.remove('active'));
        panel.querySelectorAll('.ax-tab').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        panel.querySelector('.ax-tab[data-tab="' + b.dataset.tab + '"]').classList.add('active');
      });
    });

    // Header collapse
    panel.querySelector('header').addEventListener('click', () => {
      panel.classList.toggle('collapsed');
    });

    return panel;
  }

  // ─────────────────────────────────────────────────────────────
  // ① SEO Score
  // ─────────────────────────────────────────────────────────────
  function getEditorDocument() {
    const f = document.querySelector('iframe.editor');
    return (f && f.contentDocument) || null;
  }

  function collectSeoFacts(doc, file) {
    const language = doc.documentElement.lang.toLowerCase();
    // Some generated English pages retain #proseZh for their translated body.
    // Follow the visible body, not the historical ID's language suffix.
    const bodies = (language.startsWith('en') ? ['#proseEn','#proseZh'] : ['#proseZh','#proseEn']).map(id => doc.querySelector(id));
    const region = bodies.find(el => el && !el.hidden && el.style.display !== 'none' && el.getAttribute('aria-hidden') !== 'true') ||
      doc.querySelector('[data-edit-region]') || doc.querySelector('article .prose') ||
      doc.querySelector('article') || doc.querySelector('main');
    const content = region ? region.cloneNode(true) : doc.createElement('div');
    content.querySelectorAll('script,style,template,noscript,nav,footer,[hidden],[aria-hidden="true"]').forEach(n => n.remove());
    content.querySelectorAll('[style]').forEach(n => {if (n.style.display === 'none') n.remove();});
    // Count one language only when the fallback region contains bilingual bodies.
    content.querySelectorAll(language.startsWith('en') ? '#proseZh' : '#proseEn').forEach(n => n.remove());
    const headingRoot = doc.querySelector('main') || region;
    return {
      file, title:(doc.querySelector('title')?.textContent || '').trim(),
      description:(doc.querySelector('meta[name="description"]')?.getAttribute('content') || '').trim(),
      text:(content.textContent || '').replace(/\s+/g,''),
      h1Count:headingRoot ? headingRoot.querySelectorAll('h1').length : 0,
      h2Count:content.querySelectorAll('h2').length,
      links:Array.from(content.querySelectorAll('a[href]'), a => a.getAttribute('href')),
      images:Array.from(content.querySelectorAll('img'), img => img.getAttribute('alt')),
      canonicals:Array.from(doc.querySelectorAll('link[rel~="canonical"]'), n => n.getAttribute('href') || ''),
      jsonld:Array.from(doc.querySelectorAll('script[type="application/ld+json"]'), n => n.textContent),
    };
  }

  function analyzeSeoFacts(facts) {
    const checks = [];
    const add = (id, ok, msg) => checks.push({id,ok,msg});
    const origin = 'https://chendermatologist.com';
    const route = ('/' + facts.file.replace(/^\/+/, '').replace(/(^|\/)index\.html$/, '$1').replace(/\.html$/, '')).replace(/\/$/, '') || '/';
    const expected = new URL(route, origin);
    add('title', facts.title ? 'ok' : 'err', facts.title ? `標題 ${Array.from(facts.title).length} 字；確認能直接說明文章主題` : '缺少標題');
    add('description', facts.description ? 'ok' : 'err', facts.description ? `摘要 ${Array.from(facts.description).length} 字；確認能回答讀者來此的問題` : '缺少搜尋摘要');
    add('h1', facts.h1Count === 1 ? 'ok' : facts.h1Count ? 'warn' : 'err', facts.h1Count ? `${facts.h1Count} 個主標題；確認主題清楚且層級一致` : '找不到文章主標題');
    add('body', facts.text ? 'ok' : 'err', facts.text ? `本文 ${Array.from(facts.text).length} 字元、${facts.h2Count} 個小節；不含導覽列與頁尾，不需為湊字數擴寫` : '本文沒有可閱讀文字');
    let internal = 0, external = 0, invalid = 0;
    for (const href of facts.links) {
      try {
        if (!href.trim()) { invalid++; continue; }
        const url = new URL(href, expected);
        if (['mailto:','tel:'].includes(url.protocol)) continue;
        if (!['http:','https:'].includes(url.protocol)) { invalid++; continue; }
        if (url.origin === origin) { if (url.pathname !== expected.pathname || url.search !== expected.search) internal++; }
        else external++;
      } catch (_) { invalid++; }
    }
    add('links', invalid ? 'err' : 'ok', `本文連結：${internal} 個站內頁面、${external} 個外部參考${invalid ? `、${invalid} 個無效或不安全網址` : ''}`);
    if (!internal) add('related', 'warn', '本文尚無其他站內頁面連結；有相關內容時再加入，不需硬湊數量');
    if (external) add('citations', 'ok', '一般編輯引用不必加 nofollow；付費或使用者內容的連結需另依性質標示');
    const missingAlt = facts.images.filter(alt => alt === null).length;
    const emptyAlt = facts.images.filter(alt => alt !== null && !alt.trim()).length;
    if (missingAlt) add('alt', 'err', `${missingAlt} 張圖片缺少 alt 屬性`);
    else if (facts.images.length) add('alt', 'ok', `${facts.images.length} 張圖片都有 alt 屬性`);
    if (emptyAlt) add('decorative', 'warn', `${emptyAlt} 張圖使用空白 alt；確認為裝飾圖，資訊圖需描述內容`);
    let canonical;
    try { canonical = new URL(facts.canonicals[0]); } catch (_) { /* reported below */ }
    if (facts.canonicals.length !== 1 || !canonical || canonical.origin !== origin || canonical.hash || canonical.search || canonical.username || canonical.password) {
      add('canonical','err','需有一個有效的本站 HTTPS canonical，且不含查詢參數或片段');
    } else if (canonical.href !== expected.href) {
      add('canonical','warn',`canonical 指向 ${canonical.href}，與目前檔案 ${expected.href} 不同；確認是否刻意合併重複頁面`);
    } else add('canonical','ok','canonical 與目前檔案網址一致');
    const validNode = node => node && typeof node === 'object' && !Array.isArray(node) &&
      (typeof node['@type'] === 'string' && node['@type'].trim() ||
       Array.isArray(node['@type']) && node['@type'].length && node['@type'].every(t => typeof t === 'string' && t.trim()) ||
       typeof node['@id'] === 'string' && node['@id'].trim() ||
       Array.isArray(node['@graph']) && node['@graph'].length && node['@graph'].every(validNode));
    let invalidJson = 0;
    facts.jsonld.forEach(raw => {
      try { const data = JSON.parse(raw); if (!(Array.isArray(data) ? data.length && data.every(validNode) : validNode(data))) invalidJson++; }
      catch (_) { invalidJson++; }
    });
    if (!facts.jsonld.length) add('jsonld','err','缺少 JSON-LD 結構化資料');
    else if (invalidJson) add('jsonld','err',`${invalidJson} 個 JSON-LD 無法解析或缺少基本型別／圖譜`);
    else add('jsonld','ok',`${facts.jsonld.length} 個 JSON-LD 通過基本格式檢查；完整 schema 由發布 CI 驗證`);
    return checks;
  }

  function runSeoCheck() {
    const file = getCurrentFile();
    const raw = window.adminState?.editedContent;
    if (!file || !file.endsWith('.html') || !raw) {
      document.getElementById('axSeoScore').textContent = '請先載入 HTML 文章';
      ['axSeoTitle','axSeoUrl','axSeoDescription','axSeoChecks'].forEach(id => {document.getElementById(id).textContent = '';});
      return;
    }
    // Inspect the save snapshot, not the script-free WYSIWYG preview.
    const doc = new DOMParser().parseFromString(raw, 'text/html');
    const facts = collectSeoFacts(doc, file);
    const checks = analyzeSeoFacts(facts);
    const warnings = checks.filter(c => c.ok === 'warn').length;
    const errors = checks.filter(c => c.ok === 'err').length;
    document.getElementById('axSeoScore').textContent = `${errors} 個需修正 · ${warnings} 個待確認`;
    document.getElementById('axSeoTitle').textContent = facts.title || '（尚無標題）';
    document.getElementById('axSeoUrl').textContent = facts.canonicals[0] || '（尚無 canonical）';
    document.getElementById('axSeoDescription').textContent = facts.description || '（尚無摘要）';
    const ul = document.getElementById('axSeoChecks');
    ul.textContent = '';
    checks.forEach(c => {
      const li = document.createElement('li');
      li.className = c.ok;
      li.textContent = c.msg;
      ul.appendChild(li);
    });
  }

  // ─────────────────────────────────────────────────────────────
  // ② FAQ-Page JSON-LD generator (E11)
  // ─────────────────────────────────────────────────────────────
  function generateFaqJsonLd() {
    const doc = getEditorDocument();
    if (!doc) { toast('先載入文章'); return; }
    const faqs = [];
    doc.querySelectorAll('details').forEach(d => {
      const sum = d.querySelector('summary');
      if (!sum) return;
      const q = sum.textContent.trim();
      const ansEl = d.cloneNode(true);
      ansEl.querySelector('summary').remove();
      const a = ansEl.textContent.trim();
      if (q && a) faqs.push({ q, a });
    });
    if (!faqs.length) {
      toast('沒找到 <details><summary> 結構，跳過');
      return;
    }
    const json = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map(f => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    };
    const script = doc.createElement('script');
    script.type = 'application/ld+json';
    script.textContent = JSON.stringify(json, null, 2);
    // Remove old auto-generated one first
    doc.querySelectorAll('script[data-ax="faq-jsonld"]').forEach(s => s.remove());
    script.setAttribute('data-ax', 'faq-jsonld');
    doc.head.appendChild(script);
    toast(`✓ 加了 ${faqs.length} 個 FAQ 到 JSON-LD`);
  }

  // ─────────────────────────────────────────────────────────────
  // ③ Spell check (LanguageTool API)
  // ─────────────────────────────────────────────────────────────
  async function runSpellCheck() {
    const doc = getEditorDocument();
    if (!doc) { toast('先載入文章'); return; }
    const text = doc.body.textContent.slice(0, 20000);  // 20k char API limit
    const stats = document.getElementById('axSpellStats');
    const list = document.getElementById('axSpellList');
    stats.textContent = '查詢中...';
    list.textContent = '';
    try {
      const r = await fetch('https://api.languagetool.org/v2/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ text, language: 'zh-CN' }).toString(),
      });
      const j = await r.json();
      const matches = j.matches || [];
      stats.textContent = `共 ${matches.length} 個建議（${text.length} 字）`;
      matches.slice(0, 30).forEach(m => {
        const ctx = m.context && m.context.text || '';
        const issue = document.createElement('div');
        issue.className = 'ax-typo-issue';
        const sug = (m.replacements && m.replacements[0] && m.replacements[0].value) || '無建議';
        const message = document.createElement('strong');
        message.textContent = m.message || '錯誤';
        const context = document.createElement('span');
        context.textContent = `“…${ctx}…” → `;
        const code = document.createElement('code');
        code.textContent = sug;
        issue.append(message, document.createElement('br'), context, code);
        list.appendChild(issue);
      });
      if (!matches.length) {
        stats.textContent = '✓ 沒發現問題';
      }
    } catch (e) {
      stats.textContent = '查詢失敗，請稍後再試';
    }
  }

  // ─────────────────────────────────────────────────────────────
  // ④ Medical dictionary auto-link
  // ─────────────────────────────────────────────────────────────
  const MEDICAL_DICT = {
    'EASI': 'Eczema Area and Severity Index — 異位性皮膚炎面積與嚴重度指標,0-72 分',
    'SCORAD': 'SCORing Atopic Dermatitis — 異膚評分系統,含主觀症狀',
    'DLQI': 'Dermatology Life Quality Index — 皮膚科生活品質量表,>10 表顯著影響',
    'POEM': 'Patient-Oriented Eczema Measure — 病人自評濕疹嚴重度,7 題',
    'IGA': 'Investigator Global Assessment — 醫師整體評估,0-4 分',
    'TCS': 'Topical Corticosteroids — 外用皮質類固醇',
    'TCI': 'Topical Calcineurin Inhibitors — 外用 calcineurin 抑制劑(普特皮、醫立妥)',
    'JAK': 'Janus Kinase — 細胞內訊息激酶,JAK 抑制劑為新型免疫調節藥',
    'PDE4': 'Phosphodiesterase-4 — 酵素標靶,Crisaborole / Roflumilast 屬此類',
    'BPO': 'Benzoyl Peroxide — 過氧化苯甲醯,常用治痘外用藥',
    'TEWL': 'Transepidermal Water Loss — 經皮水分流失,異膚患者升高',
    'NHI': 'National Health Insurance — 全民健保',
    'AAD': 'American Academy of Dermatology — 美國皮膚科醫學會',
    'TDA': 'Taiwanese Dermatological Association — 臺灣皮膚科醫學會',
    'AD': 'Atopic Dermatitis — 異位性皮膚炎',
    'PIH': 'Post-Inflammatory Hyperpigmentation — 發炎後色素沉著',
    'PIE': 'Post-Inflammatory Erythema — 發炎後紅斑(紅疤)',
    'BSA': 'Body Surface Area — 體表面積百分比',
    'NB-UVB': 'Narrowband UVB(311 nm)— 窄波長紫外光療',
    'PDL': 'Pulsed Dye Laser — 脈衝染料雷射',
    'IPL': 'Intense Pulsed Light — 脈衝光,非雷射',
    'IL-4': 'Interleukin-4 — Th2 主要 cytokine',
    'IL-13': 'Interleukin-13 — Th2 cytokine,Tralokinumab / Lebrikizumab 標靶',
    'IL-31': 'Interleukin-31 — 癢 cytokine,Nemolizumab 標靶',
    'Th2': 'T helper 2 — 異膚主導免疫路徑',
    'FLG': 'Filaggrin — 皮膚屏障蛋白基因,異膚常見突變',
    'MACE': 'Major Adverse Cardiovascular Events — 重大心血管事件',
    'EoE': 'Eosinophilic Esophagitis — 嗜酸性食道炎',
    'HSV': 'Herpes Simplex Virus — 單純皰疹病毒',
    'TKI': 'Tyrosine Kinase Inhibitor — 酪胺酸激酶抑制劑',
    'A 酸': 'Retinoid 類藥物 — 維他命 A 衍生物,治痘 / 抗老',
    '異膚': 'Atopic Dermatitis 異位性皮膚炎 — 慢性發炎性皮膚病',
    '玫瑰斑': 'Rosacea — 慢性紅斑性面部疾病',
    '乾癬': 'Psoriasis — 慢性免疫介導發炎性皮膚病',
    '圓禿': 'Alopecia Areata — 自體免疫性掉髮',
    '化膿性汗腺炎': 'Hidradenitis Suppurativa — 慢性反覆化膿性疾病',
    '帶狀疱疹': 'Herpes Zoster — 水痘病毒再活化所致',
    '蕁麻疹': 'Urticaria — 突發性風疹塊'
  };

  function fillDictList() {
    const div = document.getElementById('axDictList');
    if (!div) return;
    div.textContent = '';
    Object.entries(MEDICAL_DICT).forEach(([k, v]) => {
      const row = document.createElement('div');
      const term = document.createElement('strong');
      term.style.color = '#0c5159';
      term.textContent = k;
      row.append(term, document.createTextNode(' — ' + v));
      div.appendChild(row);
    });
    // also inject count into the summary text
    const sum = div.parentElement.querySelector('summary');
    if (sum) sum.textContent = `📖 詞典內容（${Object.keys(MEDICAL_DICT).length} 個詞）`;
  }

  let _dictUndo = null;
  function applyDict() {
    const doc = getEditorDocument();
    if (!doc) { toast('先載入文章'); return; }
    const article = doc.querySelector('article') || doc.body;
    _dictUndo = article.innerHTML;
    let added = 0;
    const seen = new Set();
    Object.keys(MEDICAL_DICT).sort((a, b) => b.length - a.length).forEach(term => {
      if (seen.has(term)) return;
      // only the FIRST occurrence in plain text nodes
      const walker = doc.createTreeWalker(article, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        // skip if inside <a>, <dfn>, <code>, headings already
        let p = node.parentNode;
        let skip = false;
        while (p && p !== article) {
          const tn = p.tagName;
          if (tn === 'A' || tn === 'DFN' || tn === 'CODE' || tn === 'H1' || tn === 'H2' || tn === 'H3') { skip = true; break; }
          p = p.parentNode;
        }
        if (skip) continue;
        const txt = node.nodeValue;
        const idx = txt.indexOf(term);
        if (idx === -1) continue;
        const before = txt.slice(0, idx);
        const after = txt.slice(idx + term.length);
        const dfn = doc.createElement('dfn');
        dfn.title = MEDICAL_DICT[term];
        dfn.style.cssText = 'border-bottom:1px dotted #0c5159;cursor:help;font-style:normal';
        dfn.textContent = term;
        const frag = doc.createDocumentFragment();
        if (before) frag.appendChild(doc.createTextNode(before));
        frag.appendChild(dfn);
        if (after) frag.appendChild(doc.createTextNode(after));
        node.parentNode.replaceChild(frag, node);
        added++;
        seen.add(term);
        break;
      }
    });
    document.getElementById('axDictStats').textContent = `✓ 加了 ${added} 個 dfn`;
    toast(`✓ 加了 ${added} 個專業詞彙 dfn`);
  }
  function undoDict() {
    if (_dictUndo === null) return toast('沒有可復原項目');
    const doc = getEditorDocument();
    if (!doc) return;
    const article = doc.querySelector('article') || doc.body;
    article.innerHTML = _dictUndo;
    _dictUndo = null;
    document.getElementById('axDictStats').textContent = '已復原';
    toast('已復原');
  }

  // ─────────────────────────────────────────────────────────────
  // ⑤ Font / typography control
  // ─────────────────────────────────────────────────────────────
  const THEME_PATH = 'assets/theme.css';

  function buildThemeCss(bodyFont, headFont, bodySize) {
    let css = '/* admin-managed theme overrides — generated by /admin/admin-extras.js */\n:root{\n';
    if (bodyFont) css += `  --font-body: ${bodyFont};\n`;
    if (headFont) css += `  --font-display: ${headFont};\n`;
    if (bodySize) css += `  --font-body-size: ${bodySize};\n`;
    css += '}\n';
    if (bodyFont) css += `body{font-family:var(--font-body)!important}\n`;
    if (headFont) css += `h1,h2,h3,h4,.font-display{font-family:var(--font-display)!important}\n`;
    if (bodySize) css += `article p,article li,article td{font-size:var(--font-body-size)!important}\n`;
    return css;
  }

  function previewFont() {
    const bodyFont = document.getElementById('axBodyFont').value;
    const headFont = document.getElementById('axHeadFont').value;
    const bodySize = document.getElementById('axBodySize').value;
    const css = buildThemeCss(bodyFont, headFont, bodySize);
    const doc = getEditorDocument();
    if (!doc) { toast('先載入文章'); return; }
    let style = doc.querySelector('style[data-ax="theme-preview"]');
    if (!style) {
      style = doc.createElement('style');
      style.setAttribute('data-ax', 'theme-preview');
      doc.head.appendChild(style);
    }
    style.textContent = css;
    toast('預覽已套用（未儲存）');
  }

  async function applyFont() {
    const bodyFont = document.getElementById('axBodyFont').value;
    const headFont = document.getElementById('axHeadFont').value;
    const bodySize = document.getElementById('axBodySize').value;
    if (!bodyFont && !headFont && !bodySize) { toast('未選擇任何項目'); return; }
    if (!getPat()) { toast('GitHub Token 已過期或未設定，請重新貼上'); return; }
    const css = buildThemeCss(bodyFont, headFont, bodySize);
    const b64 = btoa(unescape(encodeURIComponent(css)));
    // Get current sha if exists
    let sha = null;
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${THEME_PATH}?ref=${BRANCH}`, {
        headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json' },
      });
      if (r.ok) { const j = await r.json(); sha = j.sha; }
    } catch (e) { /* not exists */ }
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${THEME_PATH}`, {
        method: 'PUT',
        headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'admin: update site theme', content: b64, branch: BRANCH, sha }),
      });
      if (r.ok) toast('✓ 字型設定已存進 ' + THEME_PATH + '（下次部署生效，記得在 layout 加 <link>）');
      else { toast('儲存失敗，請稍後再試（HTTP ' + r.status + '）'); }
    } catch (e) { toast('網路錯誤，儲存字型設定失敗'); }
  }

  // ─────────────────────────────────────────────────────────────
  // ⑥ Version rollback
  // ─────────────────────────────────────────────────────────────
  async function loadVersions() {
    if (!getCurrentFile()) { toast('先選一個檔案'); return; }
    const pat = getPat();
    if (!pat) { toast('GitHub Token 已過期或未設定，請重新貼上'); return; }
    let j;
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/commits?path=${encodeURIComponent(getCurrentFile())}&per_page=30&sha=${BRANCH}`, {
        headers: { Authorization: 'token ' + pat, Accept: 'application/vnd.github+json' },
      });
      j = await r.json();
    } catch (e) { toast('網路錯誤，讀取版本歷史失敗'); return; }
    if (!Array.isArray(j)) { toast('讀取失敗'); return; }
    const list = document.getElementById('axVersionList');
    list.textContent = '';
    j.forEach(c => {
      const div = document.createElement('div');
      div.className = 'ax-version';
      const date = c.commit && c.commit.author && c.commit.author.date;
      const time = date ? new Date(date).toLocaleString('zh-TW') : '';
      const msg = ((c.commit && c.commit.message) || '').split('\n')[0].slice(0, 60);
      const shortSha = String(c.sha || '').slice(0, 7);
      const msgEl = document.createElement('div');
      msgEl.className = 'ax-v-msg';
      msgEl.textContent = msg;
      const timeEl = document.createElement('div');
      timeEl.className = 'ax-v-time';
      timeEl.textContent = `${time} · ${shortSha}`;
      div.append(msgEl, timeEl);
      div.addEventListener('click', () => rollbackTo(c.sha));
      list.appendChild(div);
    });
  }

  async function rollbackTo(sha) {
    if (!confirm(`確定要還原到 ${sha.slice(0, 7)}?目前未存的改動會遺失。`)) return;
    if (!getPat()) { toast('GitHub Token 已過期或未設定，請重新貼上'); return; }
    // Fetch file content at that commit
    let j;
    try {
      const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${getCurrentFile()}?ref=${sha}`, {
        headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json' },
      });
      j = await r.json();
    } catch (e) { toast('網路錯誤，讀取舊版失敗'); return; }
    if (!j || !j.content) { toast('讀取舊版失敗'); return; }
    // Write back to main with current sha
    const writeR = await fetch(`https://api.github.com/repos/${REPO}/contents/${getCurrentFile()}`, {
      method: 'PUT',
      headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: `admin: rollback to ${sha.slice(0, 7)}`,
        content: j.content.replace(/\n/g, ''),
        branch: BRANCH,
        sha: getCurrentSha(),
      }),
    });
    if (writeR.ok) {
      toast('✓ 已還原。重新載入...');
      setTimeout(() => location.reload(), 1500);
    } else {
      toast('還原失敗，請稍後再試（HTTP ' + writeR.status + '）');
    }
  }

  // ─────────────────────────────────────────────────────────────
  // ⑦ Article reorder (changes DN.ARTICLES order in blog-shared.js)
  // ─────────────────────────────────────────────────────────────
  let _orderArr = [];
  async function loadReorder() {
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/blog/blog-shared.js?ref=${BRANCH}`, {
      headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json' },
    });
    const j = await r.json();
    if (!j.content) { toast('讀取 blog-shared.js 失敗'); return; }
    const src = atob(j.content.replace(/\n/g, ''));
    // Find DN.ARTICLES = [ ... ]; and parse top-level slug strings
    const m = src.match(/DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];/);
    if (!m) { toast('找不到 DN.ARTICLES'); return; }
    // Pull slugs (first quoted string in each object)
    const slugRegex = /\{[^}]*?slug:\s*['"]([^'"]+)['"]/g;
    const slugs = [];
    let mm;
    while ((mm = slugRegex.exec(m[1])) !== null) slugs.push(mm[1]);
    _orderArr = slugs.slice();
    const ol = document.getElementById('axReorderList');
    ol.textContent = '';
    slugs.forEach(s => {
      const li = document.createElement('li');
      li.draggable = true;
      li.dataset.slug = s;
      li.textContent = s;
      ol.appendChild(li);
    });
    addDragHandlers(ol);
    document.getElementById('axReorderSave').style.display = 'inline-flex';
    document.getElementById('axReorderSave')._sha = j.sha;
    document.getElementById('axReorderSave')._origSrc = src;
    toast(`載入 ${slugs.length} 篇文章`);
  }

  function addDragHandlers(ol) {
    let dragSrc = null;
    ol.querySelectorAll('li').forEach(li => {
      li.addEventListener('dragstart', e => { dragSrc = li; li.classList.add('dragging'); });
      li.addEventListener('dragend', () => { li.classList.remove('dragging'); ol.querySelectorAll('li').forEach(x => x.classList.remove('drag-over')); });
      li.addEventListener('dragover', e => { e.preventDefault(); li.classList.add('drag-over'); });
      li.addEventListener('dragleave', () => li.classList.remove('drag-over'));
      li.addEventListener('drop', e => {
        e.preventDefault();
        if (dragSrc && dragSrc !== li) {
          const rect = li.getBoundingClientRect();
          const after = e.clientY > rect.top + rect.height / 2;
          ol.insertBefore(dragSrc, after ? li.nextSibling : li);
          _orderArr = Array.from(ol.querySelectorAll('li')).map(x => x.dataset.slug);
        }
      });
    });
  }

  async function saveReorder() {
    const btn = document.getElementById('axReorderSave');
    const sha = btn._sha;
    const src = btn._origSrc;
    // Build a new ordered DN.ARTICLES literal — we keep the original objects but reorder them.
    const m = src.match(/(DN\.ARTICLES\s*=\s*\[)([\s\S]*?)(\];)/);
    if (!m) return toast('找不到 DN.ARTICLES');
    const inner = m[2];
    // Split inner into objects (top-level { ... })
    const objs = [];
    let depth = 0, start = 0;
    for (let i = 0; i < inner.length; i++) {
      const c = inner[i];
      if (c === '{') { if (depth === 0) start = i; depth++; }
      else if (c === '}') { depth--; if (depth === 0) objs.push(inner.slice(start, i + 1)); }
    }
    // Map slug → object
    const map = {};
    objs.forEach(o => { const sm = o.match(/slug:\s*['"]([^'"]+)['"]/); if (sm) map[sm[1]] = o; });
    const newInner = '\n  ' + _orderArr.map(s => map[s]).filter(Boolean).join(',\n  ') + '\n';
    const newSrc = src.replace(m[0], m[1] + newInner + m[3]);
    // Commit
    const enc = unescape(encodeURIComponent(newSrc));
    const b64 = btoa(enc);
    const w = await fetch(`https://api.github.com/repos/${REPO}/contents/blog/blog-shared.js`, {
      method: 'PUT',
      headers: { Authorization: 'token ' + getPat(), Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'admin: reorder DN.ARTICLES', content: b64, branch: BRANCH, sha }),
    });
    if (w.ok) toast('✓ 已儲存,重跑 minify 後生效');
    else { toast('失敗，請稍後再試（HTTP ' + w.status + '）'); }
  }

  // ─────────────────────────────────────────────────────────────
  // ⑧ G2 — POPULAR_PICKS admin (KV-backed; no redeploy needed)
  // ─────────────────────────────────────────────────────────────
  let _picksArr = [];
  let _picksObserver = null;
  function renderPicks() {
    const ol = document.getElementById('axPicksList');
    ol.textContent = '';
    _picksArr.forEach((s, idx) => {
      const slug = String(s || '');
      const li = document.createElement('li');
      li.draggable = true;
      li.dataset.slug = slug;
      const span = document.createElement('span');
      span.style.flex = '1';
      span.textContent = slug;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'ax-btn';
      remove.dataset.rm = String(idx);
      remove.style.margin = '0 0 0 4px';
      remove.style.padding = '2px 8px';
      remove.textContent = '×';
      li.append(span, remove);
      li.style.display = 'flex';
      li.style.alignItems = 'center';
      ol.appendChild(li);
    });
    addDragHandlers(ol);
    ol.querySelectorAll('button[data-rm]').forEach(b => {
      b.addEventListener('click', e => {
        e.stopPropagation();
        const i = parseInt(b.dataset.rm, 10);
        _picksArr.splice(i, 1);
        renderPicks();
      });
    });
    document.getElementById('axPicksSave').style.display = _picksArr.length ? 'inline-flex' : 'none';
    // Watch for drag reorder. CODE_REVIEW 2026-05-31 — was `new MutationObserver()
    // .observe()` on EVERY renderPicks() call (load + each add/remove), so N
    // observers accumulated and all fired on the next mutation (O(N²) + leak in
    // a long admin session). Reuse a single observer: disconnect, then re-observe
    // the (stable-id) list element.
    if (!_picksObserver) {
      _picksObserver = new MutationObserver(() => {
        const list = document.getElementById('axPicksList');
        if (list) _picksArr = Array.from(list.querySelectorAll('li')).map(x => x.dataset.slug);
      });
    }
    _picksObserver.disconnect();
    _picksObserver.observe(ol, { childList: true });
  }
  async function loadPicks() {
    document.getElementById('axPicksStats').textContent = '載入中...';
    try {
      const r = await fetch('/api/admin/popular-picks');
      const j = await r.json();
      _picksArr = (j.picks || []).slice();
      renderPicks();
      document.getElementById('axPicksStats').textContent = j.fallback
        ? `(KV 為空,顯示預設 fallback ${_picksArr.length} 篇)`
        : `已載入 ${_picksArr.length} 篇 (來自 KV)`;
    } catch (e) {
      document.getElementById('axPicksStats').textContent = '載入失敗，請稍後再試';
    }
  }
  function addPick() {
    const inp = document.getElementById('axPicksAdd');
    const v = inp.value.trim();
    if (!/^[a-z0-9-]+$/.test(v)) { toast('slug 格式錯誤(只允許 a-z 0-9 -)'); return; }
    if (_picksArr.includes(v)) { toast('已在清單中'); return; }
    if (_picksArr.length >= 12) { toast('最多 12 篇'); return; }
    _picksArr.push(v);
    inp.value = '';
    renderPicks();
  }
  async function savePicks() {
    if (!getPat()) { toast('請先完成登入，再儲存熱門文章'); return; }
    if (!_picksArr.length) { toast('清單不能空'); return; }
    // Cookie-first: setPat() waits for /api/admin/login, so the HttpOnly
    // session is ready before this control can be used. Do not resend the
    // browser-held PAT to same-origin admin APIs.
    const r = await fetch('/api/admin/popular-picks', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ picks: _picksArr }),
    });
    const j = await r.json();
    if (r.ok) {
      toast('✓ 已儲存到 KV ' + _picksArr.length + ' 篇,前台立即生效');
      document.getElementById('axPicksStats').textContent = '已儲存 (' + new Date().toLocaleTimeString() + ')';
    } else {
      toast('儲存失敗，請稍後再試（HTTP ' + r.status + '）');
    }
  }

  // ─────────────────────────────────────────────────────────────
  // BOOTSTRAP
  // ─────────────────────────────────────────────────────────────
  ready(() => {
    injectStyles();
    buildPanel();
    fillDictList();

    document.getElementById('axSeoRefresh').addEventListener('click', runSeoCheck);
    document.getElementById('axFaqGen').addEventListener('click', generateFaqJsonLd);
    document.getElementById('axSpellRun').addEventListener('click', runSpellCheck);
    document.getElementById('axDictRun').addEventListener('click', applyDict);
    document.getElementById('axDictUndo').addEventListener('click', undoDict);
    document.getElementById('axFontApply').addEventListener('click', applyFont);
    document.getElementById('axFontPreview').addEventListener('click', previewFont);
    document.getElementById('axVersionLoad').addEventListener('click', loadVersions);
    document.getElementById('axReorderLoad').addEventListener('click', loadReorder);
    document.getElementById('axReorderSave').addEventListener('click', saveReorder);
    document.getElementById('axPicksLoad').addEventListener('click', loadPicks);
    document.getElementById('axPicksAddBtn').addEventListener('click', addPick);
    document.getElementById('axPicksAdd').addEventListener('keydown', e => { if (e.key === 'Enter') addPick(); });
    document.getElementById('axPicksSave').addEventListener('click', savePicks);

    // Auto-run SEO check whenever editor content changes (debounced)
    let seoTimer = null;
    // CODE_REVIEW 2026-05-31: replaced a 4s forever-setInterval. It ran
    // getEditorDocument() + (when the SEO tab was active) a heavy runSeoCheck()
    // with full outerHTML serialization every 4 seconds for the ENTIRE admin
    // session, even with no editor open and the SEO tab inactive -> constant
    // background CPU and typing jank. Now event-driven + debounced, no polling:
    // a passive input listener inside the editor iframe (re-attached on iframe
    // navigation) plus a delegated SEO-tab-open trigger. Preserves the original
    // guards (only runs when the SEO tab is active AND an editor doc exists);
    // degrades gracefully to the manual refresh button if the iframe can't be
    // wired.
    function seoTabActive() {
      return !!document.querySelector('.ax-tab[data-tab="seo"].active');
    }
    function scheduleSeoCheck() {
      if (!seoTabActive()) return;
      if (!getCurrentFile()) return;
      clearTimeout(seoTimer);
      seoTimer = setTimeout(runSeoCheck, 600);
    }
    function attachSeoInput() {
      const doc = getEditorDocument();
      if (!doc || doc._seoInputHooked) return;
      doc._seoInputHooked = true;
      doc.addEventListener('input', scheduleSeoCheck, { passive: true });
      scheduleSeoCheck();
    }
    function wireEditorSeoInput() {
      const f = document.querySelector('iframe.editor');
      if (!f) return;
      if (!f._seoLoadHooked) {
        f._seoLoadHooked = true;
        f.addEventListener('load', attachSeoInput);
      }
      attachSeoInput();
    }
    document.addEventListener('click', function (e) {
      if (e.target && e.target.closest && e.target.closest('.ax-tabs [data-tab="seo"], .ax-tab[data-tab="seo"]')) {
        wireEditorSeoInput();
        setTimeout(scheduleSeoCheck, 50);
      }
    });
    document.addEventListener('input', function (e) {
      if (e.target && e.target.closest && e.target.closest('#editorPane textarea')) scheduleSeoCheck();
    });
    document.addEventListener('cd-editor-content-changed', scheduleSeoCheck);
    wireEditorSeoInput();
    const frameWrap = document.querySelector('.frame-wrap');
    if (frameWrap) new MutationObserver(() => {
      wireEditorSeoInput();
      scheduleSeoCheck();
    }).observe(frameWrap, {childList:true});

    // Run once on first file load
    setTimeout(runSeoCheck, 1500);
  });
})();
