# DermNotes — Code Review

_Generated 2026-05-18. Reviewer: Claude (Sonnet 4.5)._
_Scope: 96 Python scripts · 7 JS bundles · 7 Vercel API endpoints · Service Worker · `vercel.json` · 96 HTML pages._
_Designed as a baseline for follow-up Codex audit._

> Status update (2026-06-10): this is a historical baseline. The unused
> `api/rpc.js`, `api/articles-recent.js`, `api/analytics.js`, Decap OAuth
> stack, and three unwired admin endpoints were removed after call-site
> verification. Findings below preserve the original review context.

---

## TL;DR — top 10 actions, in order

| # | File | Severity | One-line fix |
|---|---|---|---|
| 1 | All `blog/*.html` (46/48) | **Critical** | Duplicate `MedicalWebPage` JSON-LD block — one emitter is firing twice. Find the second insertion site in `_normalize_schema.py:267` (it `setdefault`s, but the block was added previously by something else). |
| 2 | `llms-full.txt` | **Critical** | 44 raw `data-en="…"` attribute strings bleeding into RAG corpus. `_gen_llms_full.py:extract_clean_body` strips tags but not attrs — strip `\sdata-en="[^"]*"` before tag-stripping. |
| 3 | 7 articles | **Critical** | Hreflang+sitemap reciprocity broken (`atopic-dermatitis-overview`, `dupilumab-long-term-maintenance`, `isotretinoin-{clinical,patient}`, `topical-acids-{clinical,patient}`, `severe-scabies-treatment`). Re-run `_gen_en_pages.py` + `_gen_feeds.py` and audit why those 7 weren't picked up. |
| 4 | All articles' JSON-LD | **Critical** | `speakable.cssSelector` references `[itemprop='description']` which exists on zero pages. Either drop the selector from `_normalize_schema.py:SPEAKABLE_SPEC` or add `itemprop="description"` to article TL;DR `<p>`s. |
| 5 | `api/auth.js:89-103` + `vercel.json:303` | **Critical (security)** | OAuth flow sends GitHub `repo,user` scope tokens via `postMessage` with only origin check. With CSP's `'unsafe-inline'` script-src still allowed, any same-origin XSS gets full repo write. Bind postMessage to OAuth `state`, scope to `public_repo`, plan a nonce-based CSP migration. |
| 6 | `api/rpc.js:139-143` | **Critical (security)** | `articles.bookmark*` accepts any 8–128 char Bearer string as a "session" with no KV-side issuance — anyone can read/write any other user's bookmarks by guessing. Either gate behind real auth or issue server-side tokens. |
| 7 | `sw.js` | **High (correctness)** | `cd-v135` HTML cache is uncapped (only `cd-runtime-v135` has the 150-entry trim). Long-tail readers grow it unbounded. Add `trimCache` to navigate branch. |
| 8 | `blog/blog-shared.js:1820` + `:1500-1547` | **High (memory)** | `setInterval(reg.update, 30 min)` never cleared; 4 PerformanceObservers in `bindWebVitals` never `disconnect()` (FCP is the only one done correctly). With Speculation Rules now site-wide, prerender restores can leak. |
| 9 | `blog/blog-shared.js:1607` | **High (INP)** | `DN.initCmdK` runs in the critical-path queue but synchronously builds the search index + injects overlay DOM + attaches global keydown/click listeners. Move to `idle()` queue; lazy-init on first `/`/`Cmd+K`. |
| 10 | 5 scripts (`_normalize_schema.py`, `_inject_related.py`, `_gen_en_pages.py`, `_gen_feeds.py`, `_normalize_robots.py`) | **High (encoding)** | No `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at module top. Any `print()` containing CJK will `UnicodeEncodeError` on a fresh Windows cp950 console. |

---

## Architecture overview

Static-first site with:

- **Authoring layer.** Articles authored as hand-written HTML in `blog/<slug>.html` with bilingual `data-zh`/`data-en` attrs. `DN.ARTICLES` catalog lives in `blog/blog-shared.js` and is the single source of truth.
- **Build pipeline.** `_run_quality.py` runs 4 phases:
  1. `REGEN_STEPS` — 20+ normalizers + injectors that mutate HTML in-place
  2. `BUILD_GENERATED_STEPS` — search index + Pagefind
  3. `CHECK_STEPS` — 22 CI gates (meta, robots, schema, perf budget, security, etc.)
  4. `POST_BUILD_STEPS` — minify + smoke test
- **EN mirror.** `_gen_en_pages.py` reads each ZH article + runs `transform()` → emits `en/blog/<slug>.html`. EN files inherit ZH structure with `data-zh`/`data-en` swapped at runtime via `DN.applyTextOnly()`.
- **Runtime.** `blog-shared.js` (70 KB min) loads on every page. 5 lazy bundles (`blog-{hub,article-reading,article-footer,article-visuals,diagrams,calculators}.min.js`) load on demand via `DN.ensure*Bundle()` promises.
- **PWA.** Service Worker at `sw.js` (version `cd-v135`) with stale-while-revalidate for assets, network-first for `?v=`-versioned HTML, offline fallback to `/offline.html`.
- **Serverless API.** 7 Vercel functions in `api/` — OG image gen, RPC (article queries + bookmarks), OAuth (Decap CMS), Web Push subscribe+send, analytics relay.

**Strong architectural decisions** (preserve these):

- Catalog-as-source-of-truth (`DN.ARTICLES` drives sitemap, JSON-LD section, OG meta, related cards, llms-full.txt).
- Idempotency markers (`<!-- dn-og-extras:start/end -->`, `class="dn-reading-time"`, etc.) wrapped in dedicated strip regex before re-insertion.
- Critical-vs-idle split in `DN.initBlog` with explicit timeout budgets.
- Bundle splitting + slug allowlist gating (saves ~100 KB on articles without diagrams).
- Inline ADR-style comments on REGEN_STEPS explaining why each step depends on the previous.

---

## Critical issues

### C1. Duplicate `MedicalWebPage` JSON-LD on 46/48 articles
Two `<script type="application/ld+json">{"@type":"MedicalWebPage",…}</script>` blocks ship on most articles. Confirmed:

- `blog/mpox-care.html`: 2 blocks
- `blog/acne-myths.html`: 2 blocks
- `blog/atopic-dermatitis-overview.html`: 2 blocks
- `blog/ai-dermatology-roles.html`: 1 block (research → MedicalScholarlyArticle, so the duplicate emitter has a bypass)

Likely cause in `_normalize_schema.py:267` — the `build_medical_webpage()` insertion fires when `has_article_schema(src2)` is true and no `MedicalWebPage` exists yet, BUT the test runs on `src2` (post-rewrite), so if `normalize_obj()` just converted an Article→MedicalWebPage, both the converted block AND a freshly-built one end up in HTML.

**Fix:** Check for `MedicalWebPage` presence again after the loop and skip if any exists. Or move `build_medical_webpage` to only fire on articles whose source HTML had NO ld+json blocks at all.

### C2. `data-en` attribute strings bleed into `llms-full.txt`
44 instances of `data-en="…"` in the AI/LLM corpus file. Example pattern: `"…例行使用)。" data-en="AD is a purely clinical…">異位性…`. AI crawlers ingesting this for RAG will see broken HTML in their "clean text" content.

**Fix in `_gen_llms_full.py:extract_clean_body`** (around line 95): before stripping tags, also strip attributes inside opening tags. Add a pass:
```python
body_html = re.sub(r'\sdata-(en|zh)="[^"]*"', '', body_html)
```

### C3. 7 EN articles missing from `sitemap.xml`
EN files exist on disk but `sitemap.xml` has no `<loc>` for them:
- `atopic-dermatitis-overview` (tier-1 cluster anchor!)
- `dupilumab-long-term-maintenance`
- `isotretinoin-clinical`, `isotretinoin-patient`
- `topical-acids-clinical`, `topical-acids-patient`
- `severe-scabies-treatment` (correct — this one is unpublished:true)

Also missing: hreflang `en` link in the corresponding ZH articles, and back-link from EN to ZH.

**Fix:** Audit `_gen_en_pages.py:sync_source_hreflang()` (line ~669) and `_gen_feeds.py`. The likely cause: `is_noindex(en_html)` returns true for these articles, so the hreflang cluster is omitted (`_gen_en_pages.py:650`). 6 of these 7 articles ARE indexable per `_check_seo_signals.py` audit — verify the noindex test isn't false-positive on the new `noindex,follow,max-image-preview:large,…` directive format.

### C4. `speakable.cssSelector` points to nonexistent attribute
`_normalize_schema.py:SPEAKABLE_SPEC` (line ~110):
```python
SPEAKABLE_SPEC = {
    "@type": "SpeakableSpecification",
    "cssSelector": ["h1", "[itemprop='description']", ".dn-summary"],
}
```
Zero pages have `itemprop="description"`. Google Assistant TTS will only pick `h1` + `.dn-summary` (and `.dn-summary` may also not exist on all articles — verify).

**Fix:** Either drop `[itemprop='description']` OR add `itemprop="description"` to article TL;DR `<p>` blocks via a new normalizer.

### C5. OAuth token postMessage allows same-origin XSS to harvest GitHub `repo,user` scope
`api/auth.js:89-103` — popup `postMessage(token, e.origin === targetOrigin)`. Since CSP allows `'unsafe-inline'` (vercel.json:303), any same-origin XSS can open the popup and intercept the postMessage. Token has scope `repo,user` — full write access to the entire admin repo + user email read.

**Fix path:**
1. **Short term:** Bind postMessage to `oauth_state` cookie — popup must echo state, server-side render rejects mismatches.
2. **Scope reduction:** Change `SCOPES` from `'repo,user'` to `'public_repo'` (admin/user repo is public).
3. **Medium term:** Migrate CSP to nonce-based — drop `'unsafe-inline'`.

### C6. `articles.bookmark*` accepts any client-asserted "session"
`api/rpc.js:139-143`:
```js
function getSession(req) {
  const auth = req.headers.get('authorization') || '';
  const m = auth.match(/^Bearer ([A-Za-z0-9_-]{8,128})$/);
  return m ? m[1] : null;
}
```
Reads/writes `bm:<session>` keys directly. No KV-side issuance, no expiry, no binding to user. Anyone can pick any string and persist data under it; anyone else who guesses or sniffs the string sees their bookmarks.

**Fix:** Either:
- Disable the bookmark endpoint until real auth exists, OR
- Issue tokens server-side, store `bm:session:<id>` → user metadata, expire after N days, never return tokens to clients other than the one that initiated.

---

## High-priority improvements

### Build pipeline

- **`_run_quality.py` ordering risk.** `_normalize_robots_meta.py` runs AFTER `_gen_en_pages.py`, but `_gen_en_pages.set_noindex()` overwrites the robots meta tag with its own template. We patched the template (batch21) to include `max-image-preview` etc., but the same risk exists for `_normalize_og_article_meta.py` if EN-gen ever extends to re-emit OG meta. Document with comment.

- **CI guard gaps in `_check_seo_signals.py`:**
  - No `json.loads()` validation of speculation rules JSON. A typo in the constant in `_inject_speculation_rules.py:SPEC_RULES_JSON` would silently break Chrome prerender.
  - No hreflang reciprocity audit (would have caught C3).
  - No check that `speakable.cssSelector` selectors actually exist in DOM (would have caught C4).
  - No check that `MedicalWebPage` blocks are ≤1 per page (would have caught C1).

- **Regex fragility — `\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}`** used in 5+ scripts (`_normalize_og_article_meta.py:51`, `_inject_related.py:46`, `_inject_404.py:28`, `_check_meta.py:535`, `_normalize_schema.py:150`). Any future article field containing `{` or `}` literally (e.g., `"description: 'use {x} carefully'"`) silently drops the entry. Today's data is safe.

- **`_inject_related.py:139-141` triple-sort is dead code.** Only the last sort (by score desc, reverse=True) survives Python's stable sort. Collapse to:
  ```python
  scored.sort(key=lambda x: (-x[0], x[1]["date"] or ""), reverse=True)
  ```

- **`_check_meta.py:203` future-date regex** matches `202[6-9]` only. Will silently pass 2030+ dates. Use `\d{4}`.

- **`_check_meta.py:266` `<div class="toc"` regex** is whitespace-sensitive — `<div  class="toc"` (double space) bypasses the no-manual-TOC guard. Use `<div\s+[^>]*\bclass=["']toc["']`.

- **Encoding inconsistency.** 54 of 96 scripts set `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")` at module top. Some use `sys.stdout.reconfigure()` instead. 5 critical scripts (`_normalize_schema.py`, `_inject_related.py`, `_gen_en_pages.py`, `_gen_feeds.py`, `_normalize_robots.py`) do NEITHER — any `print()` with CJK content crashes on cp950 console.

### JS runtime

- **Bundle-load promise never resets on failure.** `DN.ensure*Bundle()` (5 occurrences in `blog-shared.js`) caches the promise — if the script `onerror` fires, the rejected promise is permanent. Next caller awaits same rejection. Reset to `null` in `.catch`.

- **`MutationObserver` on `document.body` with `subtree:true`** (`blog-shared.js:1808`) — fires on every calculator render, every lightbox open, every dark-mode toggle. 80 ms debounce + `hasNew` short-circuit is correct, but `n.querySelector('[data-zh]')` on every added Element is wasteful. Scope to `#proseZh` + footer.

- **`DN.applyTextOnly` runs full DOM walk on every lang switch AND every MutationObserver tick.** ~600 elements × 5 queries on calculator-heavy pages. Cache the node list per language between swaps.

- **`bindGAEvents` (`blog-shared.js:1416-1480`) attaches `document.click` delegated handler twice** (related-card + outbound). Collapse to one. `{ passive: true, capture: true }` on outbound click is silently ignored — `passive` is meaningless for click.

- **`addScrollToTop` scroll handler doesn't rAF-throttle** (`blog-shared.js:251`). Writes `btn.style.display` on every scroll event = forced reflow. Use the `ticking` pattern from `addStickyCTA`.

- **`DN.markRead` + `bindScrollMemory` both write localStorage in scroll hot paths.** Batch them.

### Service Worker

- **`sw.js:53` `trimCache` is FIFO but comment says LRU.** No access tracking; `cache.keys()` returns insertion order. Either rename to FIFO or implement actual LRU via `cache.put()` on hit.

- **`sw.js:32-37` `skipWaiting()` in install + the update toast in `blog-shared.js:681-703`** create dual code paths. Either drop `skipWaiting()` or drop the toast — current state can race and cause double-reloads.

- **`sw.js:34` `Promise.allSettled` on precache** swallows critical errors. The fallback chain `/offline.html → /` relies on those being cached. Use `Promise.all` for the critical 3 (offline + index + manifest), `allSettled` for the rest.

- **`sw.js:223` `w.url.endsWith(url)`** — `/blog/myths` matches `/blog/acne-myths`. Use URL parsing.

### Security headers

- **CSP `'unsafe-inline'` in script-src** (`vercel.json:303`) — provides almost no XSS mitigation. Migrate to nonce-based.
- **CSP missing `report-uri`/`report-to`** — silent CSP violations.
- **CSP missing `require-trusted-types-for 'script'`** — would harden DOM-XSS sinks.
- **CSP `connect-src` includes `api.github.com`, `uploads.github.com`, `raw.githubusercontent.com`, `api.languagetool.org`** — admin-only; scope to `/admin/(.*)` route.
- **`_check_secrets.py` patterns** cover GitHub PAT, OpenAI, Anthropic, AWS, PEM blocks, Vercel KV tokens, and GitHub OAuth client secrets.

### API endpoints

- **Resolved 2026-06-10:** the unused RPC, recent-article, analytics, and Web Push endpoints were retired. Push enrollment had no live caller, so the VAPID tooling, runtime handlers, and `web-push` dependency were removed instead of preserving dormant attack surface.

### SEO / HTML

- **`llms.txt` numbers contradict reality.** Header says "47 articles + 50 EN mirrors"; disk has 48+48 (1 unpublished); `llms-full.txt` says "45". Templatize from a single source.

- **Homepage + blog hub have NO `hreflang` link tags.** `index.html` and `blog/index.html` don't advertise their EN counterparts. Search engines can't discover `/en/` from `/`.

- **PWA manifest incomplete.** Missing `screenshots[]` (richer install UI), `share_target` (you have a content site), 144/256/384 icon sizes. `theme_color` may be stale (verify matches `#7a9285`).

- **EN body density uneven.** `en/blog/mpox-care.html` has only ~412 EN words + 275 leaked ZH chars in `<main>`. Risk of "thin/duplicate content" flag. Audit which EN files are below ~800 words and `noindex` them.

---

## Medium / polish

- **`blog-shared.js` is 1827 lines.** Cuttable: `DN.DIAGRAM_SLUGS` + `DN.CALC_SLUGS` (2 KB) → move into their lazy bundles. `injectKeyFactCSS` + `injectChartScrollCSS` (CSS-in-JS) → into `tw-mini.css`. `DN.numberMap` IIFE → bake at build time.

- **13 `/* ignore */` catches in blog-shared.js.** Most justified (localStorage quota, gtag missing). Two questionable: line 1107 (calculator render error silently swallowed) + line 1823 (SW register failure silently swallowed). Add one-line `console.warn` guarded by hostname check.

- **`_check_meta.py:565` `sys.stdout.reconfigure()` called inside `main()`.** Move to module top guarded by `hasattr`.

- **`_gen_en_pages.py:679` `open(...).read()` without context manager.** File handle leak. Use `Path(...).read_text(...)`.

- **`_gen_feeds.py:267,301` `datetime.strptime(a['date'], '%Y-%m-%d')`** crashes on malformed date in `DN.ARTICLES`. Add validation in `_check_meta.check_articles_dates` (currently only checks for future dates, not format).

- **`og.js:135` returns `Access-Control-Allow-Origin: *` for SVG.** SVG can carry script; safe via `<img src>` but unsafe via `<object>`/`fetch+innerHTML`. Drop the wildcard.

- **`og.js:52-55` `wrapText` ellipsis** uses `last.replace(/.{2}$/, '…')` on potential surrogate pairs (4-byte emoji). Use `Array.from(last).slice(0, -2).join('')`.

- **`vercel.json:295` `X-Frame-Options: SAMEORIGIN`** is redundant with CSP `frame-ancestors 'self'`. Harmless but ⊆.

- **`_dashboard.py` flagged stale articles =0** but the threshold is 30 days. With most articles modified in the past 14 days, refresh that cadence to keep visible recency.

- **Sitemap priority differentiation works** (0.2–1.0 across 8 unique values) — good signal layer.

---

## Strengths worth preserving

- **No `shell=True` anywhere** across all subprocess calls (`_run_quality`, `_run_pagefind`, etc.). All pass arg lists.
- **`_normalize_schema.py:_extract_prose_container`** uses proper depth-counting parser instead of lazy regex — exactly the right call for nested `<div>`s. Reuse this pattern in any future HTML-region extractors.
- **Idempotency markers + dedicated strip regexes** across 5+ injectors are the discipline that prevents drift. The lesson from `_inject_reading_time.py` (early bug where strip regex was too tight) is preserved in the docstring — keep this institutional memory.
- **REGEN_STEPS inline comments read like ADRs** — explain WHY each step depends on the previous. Future contributors won't accidentally reorder.
- **Bundle splitting + slug-allowlist gating** saves real bytes (~100 KB diagrams off 27 articles, 57 KB calc off 17). Don't regress.
- **`applyTextOnly` 3-case logic with the 2026-05-14 incident comment** is exactly the kind of inline note that prevents future regressions.
- **Critical-vs-idle split in `initBlog`** with explicit timeouts. Right pattern.
- **JSON-LD schema-type policy** (MedicalScholarlyArticle vs MedicalWebPage based on cat) is deliberate, single-sourced, and aligned with Google's medical-content guidance.
- **All hreflang URLs use both `zh-Hant` AND `zh-Hant-TW` plus `x-default`** — correct for TC.
- **Cache strategy in vercel.json** is sophisticated: HTML `must-revalidate`, hashed assets `immutable`, OG images `stale-while-revalidate`.
- **HSTS preload** (`max-age=63072000; includeSubDomains; preload`) is full strength.
- **`X-XSS-Protection: 0`** correctly disables the legacy XSS auditor (modern OWASP guidance).
- **`og.js` escapes XML and caps query lengths** — XML injection closed.
- **`articles-recent.js` caps head read at 4 KB, cancels reader, bounds concurrency at 8** — defensive.
- **22 CI gates run on every push.** Quality gate has high coverage.
- **`_check_seo_signals.py`** (added batch18) locks in batches 12–17 SERP signals as deploy-blocking.
- **`_dashboard.py`** (added batch22) gives ops visibility into orphan articles + short articles + missing signals.

---

## Codex audit hints

When following up:

1. **Verify C1 fix doesn't break the existing `MedicalWebPage` policy in `_normalize_schema.normalize_obj`** — the type-conversion logic (Article→MedicalWebPage based on `_is_research_article`) is correct; what's broken is the safety-net `build_medical_webpage()` that fires on top of it.

2. **C3 root cause is probably in `_gen_en_pages.set_noindex` / `is_noindex` interaction.** The new robots meta format (`noindex,follow,max-image-preview:large,…`) may be confusing `is_noindex(src)` if that function does substring match on `'noindex'` without word boundary AND `_gen_en_pages.transform` then suppresses hreflang. Trace the data flow.

3. **The agent-reviewed sample articles were** `acne-myths`, `mpox-care`, `atopic-dermatitis-overview`, `ai-dermatology-roles`, `laser-dermatology`. To replicate findings on different samples, the bugs reproduce on ~46 of 48 articles for C1, all articles for C2/C4.

4. **Critical-path Python regex patterns to harden** are listed under "Regex fragility" — `\{[^{}]*?slug:'…'[^{}]*?\}`, future-date `202[6-9]`, `<div class="toc"`. These are time bombs for future content additions.

5. **JS critical fixes** are the bundle-promise reset (#7) + initCmdK move to idle (#8). Both are 5-line diffs with high impact.

6. **Security fixes (#5, #6)** require coordination — don't break the existing CMS flow when fixing OAuth, and bookmark API may need to be temporarily disabled.

7. **22 CI gates currently pass.** Adding new checks for hreflang reciprocity / MedicalWebPage uniqueness / speakable selector existence will turn red immediately — fix the violations first, then enable the guards.

8. **The user is a solo author** with content in active flow. Prefer fixes that don't require rewriting authoring patterns. SSG-injection layer can be enhanced; hand-edited markup should stay touchable.
