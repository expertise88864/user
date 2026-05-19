# Open-source projects worth borrowing or integrating

_Generated 2026-05-19 · Companion to CODE_REVIEW.md_

After ~22 batches of in-house SEO + perf work, the site already covers
the foundations: bilingual JSON-LD, robots SERP directives, OG/Twitter
rich cards, Speculation Rules, IndexNow, llms.txt + llms-full.txt,
Pagefind, Web Vitals tracking, 22 CI gates. This document scans the
open-source landscape for tools that **add net value** vs. duplicating
existing work.

Each entry has:
- **What it does** — one-sentence summary
- **Fit for DermNotes** — ✅ adopt / 🔵 borrow patterns / ⚪ reference / ❌ redundant
- **Integration plan** — concrete next step or "why skip"

Prioritized for impact on a near-zero-traffic medical-content site.

---

## Tier 1 — adopt now (high ROI, low risk)

### A. GoogleChrome/web-vitals (with `+attribution`) ✅

- **What:** Tiny (~2 KB brotli) official library for LCP/CLS/INP/FCP/TTFB
  with bfcache awareness and **attribution data** that tells you which
  DOM element caused poor LCP/CLS/INP.
- **Why now:** The hand-rolled PerformanceObserver setup in
  `blog/blog-shared.js:1507-1592` (which we just added disconnect calls
  to in batch `dac3ad09`) measures the metrics but doesn't tell you
  which element to fix. The `attribution` build adds the offending
  element/event/loadingDelay for each metric — turns GA4 from "your
  LCP is bad" into "your LCP is bad because `<img class='hero'>` took
  2.8 s to render."
- **Integration plan:**
  1. Add `<script type="module">import { onLCP, onCLS, onINP, onFCP, onTTFB } from 'https://unpkg.com/web-vitals@4/dist/web-vitals.attribution.iife.js';</script>` OR self-host the iife build (recommended for CSP + offline reliability).
  2. Replace lines 1507-1592 of `blog/blog-shared.js` with the library's `onX(callback)` pattern.
  3. Extend the GA4 `send()` to pass `attribution.target`, `attribution.loadingDelay`, etc. as additional params.
  4. **Bundle cost:** +2 KB (attribution build is ~3.5 KB total). We already gained budget headroom in `b5243670` by moving descriptions to blog-hub; net wash.
- **Why this works for DermNotes:** Once attribution data flows, you can build a per-page report showing "article X has bad INP on calculator widget Y" — actionable instead of aggregate.

### B. untitaker/hyperlink ✅

- **What:** Rust CLI that link-checks **1.1 GB of HTML in 4 s** (700 pages in 220 ms; with `--check-anchors` in 850 ms). Emits GitHub Actions errors inline.
- **Why now:** The current `_check_internal_links.py` is Python and likely much slower on each CI run. More importantly, it doesn't validate **anchor IDs** (e.g. `href="#takehome"` that the article TOC links to). Several articles ship anchor links to H2 IDs that I haven't verified exist.
- **Integration plan:**
  1. Add to `.github/workflows/quality.yml` as a parallel job: `cargo install hyperlink` (or download the prebuilt binary), then `hyperlink . --check-anchors --github-actions`.
  2. Keep the Python `_check_internal_links.py` for now (covers EN-link audit which hyperlink doesn't natively do); merge later if hyperlink's coverage suffices.
- **Why this works:** Anchor-ID validation catches 4xx UX bugs where the user clicks a TOC link and the article scrolls to nowhere. Currently silent.

### C. iaincollins/structured-data-testing-tool 🔵

- **What:** CLI (`sdtt`) + library that validates JSON-LD/Microdata/RDFa
  against Schema.org and Google's rich-result presets. Accepts URL,
  file, or string input.
- **Fit:** Borrow as a complementary check, NOT replace `_audit_jsonld.py`.
  Our audit is more opinionated (enforces MedicalScholarlyArticle vs
  MedicalWebPage policy); sdtt is broader (validates against Google's
  exact rich-result requirements).
- **Integration plan (optional):**
  ```bash
  for file in blog/*.html; do
    sdtt --file "$file" --schemas "MedicalWebPage,FAQPage,BreadcrumbList,Speakable"
  done
  ```
  Run as a non-blocking informational check (`continue-on-error: true`)
  to surface schema warnings that our stricter audit might miss. Skip
  if it duplicates `_check_seo_signals.check_*` coverage too much.

---

## Tier 2 — borrow patterns / read but don't adopt wholesale

### D. Auriti-Labs/geo-optimizer-skill 🔵

- **What:** 47 GEO audits including some we don't have:
  - `/.well-known/ai.txt` AI bot policy file
  - `/ai/summary.json` machine-readable site summary endpoint
  - Citation-manipulation pattern detection (8 patterns)
  - CDN crawler-blocking diagnostics
  - JS-rendering dependency check (does the page work without JS for AI crawlers?)
- **Worth borrowing:**
  1. **Add `/.well-known/ai.txt`** — emerging spec parallel to robots.txt for AI bot consent. Easy: write a static file + vercel.json header. Some AI crawlers already check it.
  2. **Add `/ai/summary.json`** — single-fetch machine summary of the site. Smaller than `llms.txt` for tooling that just wants metadata.
  3. **JS-rendering check** — fetch each page with curl and verify the H1 + first paragraph is present in raw HTML (not just JS-injected). Catches cases where Google crawls before our JS runs.
- **Integration plan:** Create `_normalize_ai_well_known.py` that emits both files. The 47-audit toolkit itself overlaps too much with our `_check_seo_signals.py` to adopt wholesale.

### E. cxcscmu/AutoGEO (ICLR 2026 research) ⚪

- **What:** Research framework + paper showing what content patterns AI engines prefer:
  - Citations & references (we have Vancouver-style references ✓)
  - Statistics / specific numbers (we have these ✓)
  - Expert author signals (we have Physician schema ✓)
  - Position of key claims (TL;DR at top — we have ✓)
  - Token count of key passages (longer ≠ better; AI prefers concise key sentences)
- **Worth doing:** Read the [arXiv paper](https://arxiv.org/abs/2510.11438) for signal categories. Don't adopt the auto-rewriting (medical content needs human review). Apply findings as a content checklist in `article_writing_spec.md`.
- **Why skip the toolkit:** AutoGEO uses RL to rewrite text; for YMYL medical content, automated rewriting risks accuracy. The signal categories are the value.

### F. amplifying-ai/awesome-generative-engine-optimization ⚪

- **What:** Curated list of GEO tools, guides, research.
- **Use:** Subscribe / bookmark as a reading list. Re-check every 2-3 months for new tools.
- **Why skip integration:** It's a list, not code.

---

## Tier 3 — Don't adopt (redundant with existing infrastructure)

| Tool | Why skip |
|---|---|
| **firecrawl/llmstxt-generator** | We already have `_gen_llms_full.py`. Theirs requires Firecrawl + OpenAI API keys; ours runs offline from our own catalog (more accurate). Also: project deprecated after 2025-06-30 per their README. |
| **balaji1233/llms.txt-...-Generator-For-SEO** | Streamlit app for one-shot generation. We auto-regenerate on every build via REGEN_STEPS. |
| **AgriciDaniel/claude-seo** | 25-sub-skill Claude Code SEO toolkit. Useful for *running an audit*, but we already have `_check_seo_signals.py` (12 checks) + `_check_meta.py` (~15 checks) + `_check_api_security.py` + 19 other gates covering the same ground. |
| **spatie/schema-org** | PHP library for fluent schema building. Wrong language; our `_normalize_schema.py` is Python and does this. |
| **dougblackjr/ee-json-ld** | ExpressionEngine-specific (not our CMS). |
| **funbox/optimizt** | CLI image optimizer. We don't have many raster images (most visuals are inline SVG); the 47 OG card PNGs are already 1200×630 generated server-side. Not worth a build step. |
| **felixsandstrom/seo-link-analyzer** | Python tool that exports to Google Sheets. We have `_dashboard.py` doing similar with no external dependency. |
| **WordPress llms-txt plugins** | We're not on WordPress. |

---

## What we have that the OSS landscape lacks

The research turned up **zero tools specifically designed for
medical/YMYL content optimization** beyond generic schema validators.
Our pipeline already does several things the OSS toolkits don't:

| Capability | Where in our code | OSS equivalent |
|---|---|---|
| Cat-based MedicalScholarlyArticle vs MedicalWebPage policy | `_normalize_schema.RESEARCH_SLUGS` | None — most tools emit one or the other indiscriminately |
| `:root` palette CI guard (defends against scaffolder bugs) | `_check_meta.check_articles_have_root_palette` | None |
| Mojibake detector for hand-injected cards | `_check_seo_signals.check_no_mojibake_in_data_attrs` | None |
| Speculation Rules SSG injection (every page) | `_inject_speculation_rules.py` | Most static-site generators ship with hand-written rules; no normalizer |
| Idempotent OG `article:*` block via marker comments | `_normalize_og_article_meta.BLOCK_RE` | Generic injectors clobber on every run |
| Bilingual `data-zh` / `data-en` attribute system | `applyTextOnly` in blog-shared | Most sites generate full ZH and EN mirrors separately (heavier, doubles content) |
| Hreflang reciprocity audit | `_check_seo_signals.check_hreflang_reciprocity` | None I found — most tools check sitemap presence only |
| Cache-key/Vercel header strategy with SWR for OG images | `vercel.json` | Most tutorials skip the SWR layer |

These are the kind of opinionated decisions worth keeping; the OSS
landscape mostly converges on generic patterns that don't fit medical
content well.

---

## Recommended action order (prioritized)

1. **🟢 Adopt** GoogleChrome/web-vitals with attribution (Tier 1A) — 1 commit, +2 KB, unlocks "which element is slow" data in GA4.
2. **🟢 Adopt** untitaker/hyperlink (Tier 1B) — 1 workflow file addition, catches anchor-ID bugs we have today.
3. **🟡 Borrow** Auriti-Labs ideas for `/.well-known/ai.txt` + `/ai/summary.json` (Tier 2D) — 1 new normalizer script, ~30 lines.
4. **📖 Read** AutoGEO paper (Tier 2E) — apply signal categories to `article_writing_spec.md` (content-side work, not code).
5. **⏸ Optional** structured-data-testing-tool (Tier 1C) — only if `_audit_jsonld.py` ever misses something Google's official validator catches.
6. **❌ Skip** all Tier 3 tools — already covered.

Tracking notes for Codex audit:
- The GoogleChrome library swap (#1) replaces ~85 lines of custom
  observer code with ~15 lines using the official API + attribution.
  Net code reduction.
- The hyperlink integration (#2) adds a 4-second CI job; should be
  parallel to the existing internal-link check, not replace it.
- `/.well-known/ai.txt` (#3) needs to play nicely with the existing
  robots.txt allowlist policy — the format is still in flux per
  ai-bot-management.org.

---

## Sources

- [amplifying-ai/awesome-generative-engine-optimization](https://github.com/amplifying-ai/awesome-generative-engine-optimization) — curated GEO list
- [Auriti-Labs/geo-optimizer-skill](https://github.com/Auriti-Labs/geo-optimizer-skill) — 47 GEO audits + CLI/MCP
- [cxcscmu/AutoGEO](https://github.com/cxcscmu/AutoGEO) — ICLR 2026 GEO framework
- [GoogleChrome/web-vitals](https://github.com/GoogleChrome/web-vitals) — official RUM library
- [iaincollins/structured-data-testing-tool](https://github.com/iaincollins/structured-data-testing-tool) — JSON-LD validator CLI
- [untitaker/hyperlink](https://github.com/untitaker/hyperlink) — fast link checker
- [firecrawl/llmstxt-generator](https://github.com/firecrawl/llmstxt-generator) — llms.txt generator (deprecated)
- [ihuzaifashoukat/llmoptimizer](https://github.com/ihuzaifashoukat/llmoptimizer) — multi-framework llms.txt
- [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo) — Claude SEO skill bundle
- [funbox/optimizt](https://github.com/funbox/optimizt) — image optimizer CLI
- [Pagefind](https://github.com/Pagefind/pagefind) — already integrated; v1.5+ has CJK auto-segmentation
- [AutoGEO arXiv paper](https://arxiv.org/abs/2510.11438) — "What Generative Search Engines Like..."
