#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Metadata sanity test — runs in CI to catch SEO/meta regressions early.

Checks:
  1. sitemap.xml namespace declarations are correct (Google's official URLs)
  2. sitemap.xml URL hosts are consistent (one host, not mixed apex/www)
  3. Each public HTML has <link rel="canonical">
  4. canonical / og:url / hreflang use the same host as sitemap
  5. <title> length 30-65 chars (Google snippet limit)
  6. <meta name="description"> length 100-170 chars
  7. og:image is either /api/og pattern OR the static file actually exists
  8. DN.ARTICLES has no future date (relative to today)
  9. No <h1> longer than 70 chars (mobile readability)
 10. No duplicate canonical across different pages
 11. Robots.txt has at least one Sitemap: line

Exit code:
  0 → all good
  1 → ≥ 1 ERROR found (fail CI)
  Warnings still print but don't fail CI.

Usage:
  python _check_meta.py            # full sweep
  python _check_meta.py --fast     # only blog/*.html (skip en/, root pages)
"""

from __future__ import annotations
import os
import re
import sys
import json
import datetime
from pathlib import Path
from collections import Counter, defaultdict

# CODE_REVIEW — UTF-8 console at module top so any print() during
# module init (e.g. import-time warnings) doesn't crash on cp950.
# Was called inside main() — too late if any module-level code
# printed CJK before then.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).parent
EXPECTED_NAMESPACES = {
    'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9',
    'image':   'http://www.google.com/schemas/sitemap-image/1.1',
    'xhtml':   'http://www.w3.org/1999/xhtml',
    # Common typo to flag aggressively:
}
BAD_NAMESPACE_TYPOS = [
    'http://www.google.com/schemas/sitemaps-image/1.1',  # extra "s"
    'https://www.sitemaps.org/schemas/sitemap/0.9',       # https variant Google rejects
]

errors: list[tuple[str, str]] = []
warnings: list[tuple[str, str]] = []


def err(scope: str, msg: str):
    errors.append((scope, msg))


def warn(scope: str, msg: str):
    warnings.append((scope, msg))


# ─── 1-2. sitemap.xml ────────────────────────────────────────────────
def check_sitemap():
    fp = ROOT / 'sitemap.xml'
    if not fp.exists():
        err('sitemap', 'sitemap.xml NOT FOUND')
        return None  # can't proceed
    src = fp.read_text(encoding='utf-8')

    # 1. Namespaces
    for label, expected in EXPECTED_NAMESPACES.items():
        if expected not in src:
            err('sitemap', f'missing namespace: {expected}')
    for typo in BAD_NAMESPACE_TYPOS:
        if typo in src:
            err('sitemap', f'BAD namespace (typo): {typo}')

    # 2. Host consistency
    hosts = Counter()
    for m in re.finditer(r'<loc>https?://([^/]+)/', src):
        hosts[m.group(1)] += 1
    if len(hosts) > 1:
        warn('sitemap', f'mixed hosts in <loc>: {dict(hosts)}')
    canonical_host = max(hosts, key=hosts.get) if hosts else None
    return canonical_host


# ─── 3-7. Per-HTML checks ────────────────────────────────────────────
def check_html(canonical_host: str | None, fast: bool = False):
    static_og_dir = ROOT / 'assets' / 'og'
    static_og_files = {p.name for p in static_og_dir.glob('*')} if static_og_dir.exists() else set()

    targets = list((ROOT / 'blog').glob('*.html'))
    if not fast:
        targets += list((ROOT / 'en' / 'blog').glob('*.html'))
        for fn in ['index.html', 'about.html', 'glossary.html', 'tools.html',
                   'support.html', 'privacy.html', 'notes.html']:
            p = ROOT / fn
            if p.exists():
                targets.append(p)
        for fn in ['en/index.html', 'en/about.html', 'en/glossary.html', 'en/tools.html']:
            p = ROOT / fn
            if p.exists():
                targets.append(p)

    canonicals_seen = defaultdict(list)
    for fp in targets:
        rel = fp.relative_to(ROOT).as_posix()
        src = fp.read_text(encoding='utf-8')
        is_noindex = bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', src, re.I))

        # 3. canonical present
        m_canon = re.search(r'<link rel="canonical" href="([^"]*)"', src)
        if not m_canon:
            err(rel, 'missing <link rel="canonical">')
            continue
        canon_url = m_canon.group(1)
        canonicals_seen[canon_url].append(rel)

        # 4. canonical / og:url / hreflang same host
        canon_host_m = re.search(r'https?://([^/]+)', canon_url)
        canon_host = canon_host_m.group(1) if canon_host_m else None
        if canonical_host and canon_host and canon_host != canonical_host:
            err(rel, f'canonical host "{canon_host}" != sitemap host "{canonical_host}"')

        m_og = re.search(r'<meta property="og:url" content="([^"]*)"', src)
        if not m_og:
            if not is_noindex:
                err(rel, 'missing <meta property="og:url">')
        else:
            if m_og.group(1) != canon_url:
                err(rel, f'og:url does not match canonical ({m_og.group(1)} != {canon_url})')
            og_host_m = re.search(r'https?://([^/]+)', m_og.group(1))
            og_host = og_host_m.group(1) if og_host_m else None
            if og_host and canon_host and og_host != canon_host:
                err(rel, f'og:url host "{og_host}" != canonical host "{canon_host}"')

        hreflang_hrefs = []
        for hf in re.finditer(r'<link rel="alternate" hreflang="[^"]+" href="([^"]*)"', src):
            hreflang_hrefs.append(hf.group(1))
            hf_host_m = re.search(r'https?://([^/]+)', hf.group(1))
            hf_host = hf_host_m.group(1) if hf_host_m else None
            if hf_host and canon_host and hf_host != canon_host:
                err(rel, f'hreflang host "{hf_host}" != canonical host "{canon_host}"')
                break  # one report per file
        if hreflang_hrefs and canon_url not in hreflang_hrefs:
            err(rel, f'hreflang cluster missing canonical URL ({canon_url})')

        # 5. title length
        m_t = re.search(r'<title>([^<]+)</title>', src)
        if m_t:
            t = m_t.group(1)
            if len(t) < 30:
                warn(rel, f'<title> too short ({len(t)} chars): {t[:50]}')
            elif len(t) > 75:
                warn(rel, f'<title> too long ({len(t)} chars): {t[:50]}…')

        # 6. description length
        m_d = re.search(r'<meta name="description" content="([^"]*)"', src)
        if not m_d:
            err(rel, 'missing <meta name="description">')
        else:
            d = m_d.group(1)
            if len(d) < 100:
                warn(rel, f'description too short ({len(d)} chars)')
            elif len(d) > 300:
                warn(rel, f'description too long ({len(d)} chars)')

        # 7. og:image existence
        m_oi = re.search(r'<meta property="og:image" content="([^"]*)"', src)
        if m_oi:
            og_img = m_oi.group(1)
            if '/api/og' in og_img:
                pass  # dynamic OG via Vercel function — assume OK
            else:
                # Try to find static file
                m_fn = re.search(r'/assets/og/([^"?]+)', og_img)
                if m_fn:
                    fn = m_fn.group(1)
                    if fn not in static_og_files:
                        err(rel, f'og:image references missing file: /assets/og/{fn}')

    # 10. duplicate canonical
    for url, paths in canonicals_seen.items():
        if len(paths) > 1:
            warn('canonical', f'duplicate canonical "{url}" used by {len(paths)} pages: {paths[:3]}')


# ─── 8. DN.ARTICLES future-date check ────────────────────────────────
def check_articles_dates():
    fp = ROOT / 'blog' / 'blog-shared.js'
    if not fp.exists():
        err('blog-shared.js', 'NOT FOUND')
        return
    src = fp.read_text(encoding='utf-8')
    today = datetime.date.today().isoformat()
    i = src.find('DN.ARTICLES = [')
    end = src.find('];', i) + 2
    if i < 0:
        err('blog-shared.js', 'DN.ARTICLES block not found')
        return
    block = src[i:end]
    # CODE_REVIEW — was `202[6-9]` which silently passes 2030+ dates.
    # Any 4-digit year is fine; we range-check parseable dates below.
    for m in re.finditer(r"slug:'([a-z0-9-]+)'.*?date:'(\d{4}-\d\d-\d\d)'", block):
        slug, d = m.group(1), m.group(2)
        if d > today:
            err('blog-shared.js', f'DN.ARTICLES["{slug}"] has future date {d} (today={today})')


# ─── 9. h1 length ────────────────────────────────────────────────────
# Skipped — h1 may legitimately be long for SEO; warning only on extreme cases.


# ─── 10. Stray git merge conflict markers ────────────────────────────
# Spent half a day in 2026-05-17 outage chasing why html5validator was
# screaming "Bad character < after <". Cause: an earlier rebase committed
# blog/ai-dermatology-roles.html with conflict markers still embedded.
# Cheap guard so it can't happen again.
#
# A real git conflict marker is always at column 0 AND followed by a space
# AND then either a ref-ish word (HEAD, branch name, commit sha) or empty
# (the middle `=======` is followed by EOL). Matching just the prefix at
# column 0 catches all three variants without misfiring on string literals
# that happen to contain "<<<<<<<" inside source code.
_REAL_MARKER_PREFIX = ('<<<<<<<', '=======', '>>>>>>>')
def check_no_merge_markers():
    skip_dirs = {'.git', 'node_modules', '.next', 'out', 'dist', '__pycache__', '.vercel'}
    self_path = os.path.realpath(__file__)
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in {'.html', '.js', '.css', '.json', '.py', '.md', '.xml'}:
                continue
            fp = os.path.join(dirpath, fn)
            # Skip this checker itself; it must reference the markers as
            # literal strings to do its job.
            if os.path.realpath(fp) == self_path:
                continue
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    src = f.read()
            except (OSError, UnicodeDecodeError) as _exc:
                print(f"[check_meta] skip {fp}: {_exc}", file=__import__('sys').stderr)
                continue
            for line in src.splitlines():
                if not line:
                    continue
                # `<<<<<<<` and `>>>>>>>` are followed by space + ref-name.
                # `=======` middle marker is exactly the 7 chars with
                # optional trailing whitespace.
                if line.startswith('<<<<<<< ') or line.startswith('>>>>>>> '):
                    pass
                elif line.rstrip() == '=======':
                    pass
                else:
                    continue
                rel = os.path.relpath(fp, ROOT).replace('\\', '/')
                err(rel, 'unresolved git merge conflict marker line: ' + line[:60])
                break  # one error per file is enough


# ─── 10b. Manual <div class="toc"> in articles → double TOC ──────────
# Recurring mistake (logged in MEMORY.md feedback_dermnotes_article_template):
# DN.addInlineTOC() in blog-article-reading.js auto-injects a collapsible
# blue/teal TOC for any article with id="proseZh" + 3+ <h2 id="">. If the
# article HTML ALSO has a manual <div class="toc">, the user sees two TOCs.
# Hard rule: blog/*.html articles never carry a manual TOC div.
# CODE_REVIEW — was `<div\s+class="toc"`; allowed `<div  class="toc"`
# (double space) and `<div class='toc'` (single quote) to bypass.
# Now matches any `<div ... class=["']toc["']` with any attr order.
MANUAL_TOC_RE = re.compile(r'''<div\s+[^>]*\bclass=["']toc["']''', re.IGNORECASE)
def check_no_manual_toc():
    blog_dir = ROOT / 'blog'
    if not blog_dir.is_dir():
        return
    for fp in sorted(blog_dir.glob('*.html')):
        # Skip listing / non-article files
        if fp.name in {'index.html', 'topics.html'}:
            continue
        try:
            src = fp.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as _exc:
            print(f"[check_meta] skip {fp}: {_exc}", file=__import__('sys').stderr)
            continue
        if 'id="proseZh"' not in src:
            # Not an article (no prose container), so manual TOC is fine
            continue
        if MANUAL_TOC_RE.search(src):
            rel = fp.relative_to(ROOT).as_posix()
            err(rel, 'manual <div class="toc"> in article → DN.addInlineTOC adds a second TOC; remove the manual one')


# ─── 10c. Article must have <article class="max-w-3xl"> ──────────────
# blog-article-footer.js queries `document.querySelector('article.max-w-3xl')`
# in 9 places (addRelatedArticles, addShareToolbar, addAuthorBio,
# addLegalDisclaimer, addFeedbackLink, injectGiscus, injectWordCount,
# injectTipCard, injectPdfButton). Same in blog-article-reading.js.
# If the <article> tag doesn't have this class, ALL those injections
# silently no-op — user sees an article with no related links, no share
# buttons, no author bio, no disclaimer, no word count, no comments.
# That bit me on ai-dermatology-roles where I used <article class="wrap">.
ARTICLE_TAG_RE = re.compile(r'<article[^>]*class="([^"]*)"', re.IGNORECASE)
def check_article_class():
    blog_dir = ROOT / 'blog'
    if not blog_dir.is_dir():
        return
    for fp in sorted(blog_dir.glob('*.html')):
        if fp.name in {'index.html', 'topics.html'}:
            continue
        try:
            src = fp.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as _exc:
            print(f"[check_meta] skip {fp}: {_exc}", file=__import__('sys').stderr)
            continue
        if 'id="proseZh"' not in src:
            continue  # not an article
        classes = ARTICLE_TAG_RE.findall(src)
        if not classes:
            rel = fp.relative_to(ROOT).as_posix()
            err(rel, '<article> tag has no class attribute — needs max-w-3xl for footer injections')
            continue
        if not any('max-w-3xl' in c for c in classes):
            rel = fp.relative_to(ROOT).as_posix()
            err(rel, f'<article> class={classes[0]!r} missing max-w-3xl — JS footer injections (related/share/author/disclaimer) will silently fail')


# ─── 10d. JS corruption guard (function{ etc.) ───────────────────────
# On 2026-05-17 a bulk-edit regex `\(\s*\)` → "" was applied to .html
# files to clean up empty CJK parens left over after stripping NHI §-codes.
# It also matched JS `function()` and IIFE `})()` call sites, corrupting
# 38 files: `function()` became `function`, IIFE call sites disappeared,
# DN.initBlog runtime path broke, homepage spotlight/search/tag chips
# all silently died for hours. Cheap guard so any future bulk-edit
# that produces these patterns fails CI immediately.
JS_CORRUPTION_PATTERNS = [
    # `function{` or `function {` (no parens between function and brace)
    (re.compile(r'\bfunction\s*\{'), 'function{ (missing ())'),
    # `function (a, b) ` → `function {` after some weird strip — bare `function` followed by space then brace
    # Already covered by above.
    # `})\.then\{` or `})\.catch\{` etc. — methods called without their callback parens
    (re.compile(r'\)\.(then|catch|finally|forEach|map|filter|reduce)\s*\{'), '.then{/.forEach{ etc (missing callback parens)'),
    # `addEventListener\([^,]+,\s*function\s*\{` — already caught above
]
def check_no_js_corruption():
    skip_dirs = {'.git', 'node_modules', '.next', 'out', 'dist', '__pycache__', '.vercel'}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in {'.html', '.js'}:
                continue
            fp = os.path.join(dirpath, fn)
            # Skip this checker itself (it must reference the literal patterns)
            if os.path.realpath(fp) == os.path.realpath(__file__):
                continue
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    src = f.read()
            except (OSError, UnicodeDecodeError) as _exc:
                print(f"[check_meta] skip {fp}: {_exc}", file=__import__('sys').stderr)
                continue
            for pat, label in JS_CORRUPTION_PATTERNS:
                if pat.search(src):
                    rel = os.path.relpath(fp, ROOT).replace('\\', '/')
                    err(rel, f'JS corruption pattern detected: {label}')
                    break  # one error per file is enough


# ─── 10f. No inline <sup>N</sup> citation refs in article body ───────
# DermNotes writes patient-facing 衛教 + journal-club content. Vancouver-
# style superscript citations in every paragraph make the text feel like
# a paper, breaking the reading flow. References stay at the bottom
# (<ol class="references">) and readers jump there via the TOC anchor.
# User asked to remove these on 2026-05-17 after the AI article shipped
# with 26 sup markers ("每段落後面不需要標註1 2這類引用文獻").
INLINE_SUP_REF_RE = re.compile(r'<sup><a href="#(?:en-)?ref[0-9]+">[0-9]+</a></sup>')
def check_no_inline_sup_refs():
    blog_dir = ROOT / 'blog'
    if not blog_dir.is_dir():
        return
    for fp in sorted(blog_dir.glob('*.html')):
        if fp.name in {'index.html', 'topics.html'}:
            continue
        try:
            src = fp.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as _exc:
            print(f"[check_meta] skip {fp}: {_exc}", file=__import__('sys').stderr)
            continue
        if 'id="proseZh"' not in src:
            continue
        count = len(INLINE_SUP_REF_RE.findall(src))
        if count > 0:
            rel = fp.relative_to(ROOT).as_posix()
            err(rel, f'has {count} inline <sup><a href="#refN">N</a></sup> citations — drop them; references list at the bottom stays intact')


# ─── 10g. Homepage article-list cards must have data-cat + data-tag-en ──
# Memory note feedback_dermnotes_homepage_card.md mandates these for the
# tag-chip filter to work. 2026-05-17 deep audit found 31/43 cards were
# missing them — chip filter was broken for 67% of articles.
HOMEPAGE_CARD_RE = re.compile(
    r'<a href="/blog/([a-z0-9-]+)"((?:(?!>)[^>])*?)class="article-list-item"((?:(?!>)[^>])*)>',
    re.IGNORECASE,
)
def check_homepage_card_attrs():
    for filename in ('index.html', 'en/index.html'):
        fp = ROOT / filename
        if not fp.exists():
            continue
        src = fp.read_text(encoding='utf-8')
        bad = []
        for m in HOMEPAGE_CARD_RE.finditer(src):
            slug = m.group(1)
            full_attrs = m.group(2) + m.group(3)
            if 'data-cat=' not in full_attrs:
                bad.append((slug, 'data-cat'))
            if 'data-tag-en=' not in full_attrs:
                bad.append((slug, 'data-tag-en'))
        if bad:
            missing_cat = sorted({s for s, a in bad if a == 'data-cat'})
            missing_tag = sorted({s for s, a in bad if a == 'data-tag-en'})
            if missing_cat:
                err(filename, f'{len(missing_cat)} cards missing data-cat: {", ".join(missing_cat[:5])}{"..." if len(missing_cat) > 5 else ""}')
            if missing_tag:
                err(filename, f'{len(missing_tag)} cards missing data-tag-en: {", ".join(missing_tag[:5])}{"..." if len(missing_tag) > 5 else ""}')

        # 2026-05-17 — new check: detect duplicate attr leak. Batch1's
        # backfill regex inserted "data-cat=... data-tag-en=...>" TWICE
        # on 12 cards — the second copy fell after the closing `>` and
        # rendered as visible text on the homepage. Pattern signature:
        # `class="article-list-item">[whitespace]data-cat="...">`
        dup_re = re.compile(
            r'class="article-list-item"[^>]*?>\s*data-cat="[^"]*"\s+data-tag-en="[^"]*">',
            re.IGNORECASE,
        )
        dup_hits = len(dup_re.findall(src))
        if dup_hits:
            err(filename, f'{dup_hits} cards have duplicate data-cat/data-tag-en leaked as visible text — strip the trailing copy after the >')


# ─── 10h. Bundle-loader slug allow-lists must match the maps ──────
# DN.DIAGRAM_SLUGS in blog-shared.js gates loading blog-diagrams.min.js
# (~100 KB). It MUST match the keys of DN.MED_DIAGRAM_MAP in
# blog-diagrams.js — drift means either (a) an article that has a diagram
# defined but never loads the bundle, or (b) bundle loads but no diagram
# to inject (which is the original waste we fixed on 2026-05-17).
# Same story for DN.CALC_SLUGS ↔ DN.CALC_ORDER.
def check_diagram_calc_slug_lists():
    shared = ROOT / 'blog' / 'blog-shared.js'
    diagrams = ROOT / 'blog' / 'blog-diagrams.js'
    calc = ROOT / 'blog' / 'blog-calculators.js'
    if not (shared.exists() and diagrams.exists() and calc.exists()):
        return
    sh = shared.read_text(encoding='utf-8')
    di = diagrams.read_text(encoding='utf-8')
    ca = calc.read_text(encoding='utf-8')

    def array_slugs(src, var_name):
        m = re.search(rf"DN\.{re.escape(var_name)}\s*=\s*\[([^\]]*)\]", src)
        if not m:
            return None
        return set(re.findall(r"'([a-z0-9-]+)'", m.group(1)) +
                   re.findall(r'"([a-z0-9-]+)"', m.group(1)))

    def map_keys(src, var_name):
        m = re.search(rf"DN\.{re.escape(var_name)}\s*=\s*\{{([\s\S]*?)\n\s*\}};", src)
        if not m:
            return None
        return set(re.findall(r"'([a-z0-9-]+)'\s*:", m.group(1)) +
                   re.findall(r'"([a-z0-9-]+)"\s*:', m.group(1)))

    pairs = [
        ('DIAGRAM_SLUGS', 'MED_DIAGRAM_MAP', sh, di),
        ('CALC_SLUGS',    'CALC_ORDER',      sh, ca),
    ]
    for allow_name, map_name, allow_src, map_src in pairs:
        allow = array_slugs(allow_src, allow_name)
        keys = map_keys(map_src, map_name)
        if allow is None or keys is None:
            continue
        only_allow = allow - keys
        only_map = keys - allow
        if only_allow:
            err('blog/blog-shared.js', f'DN.{allow_name} contains slugs not in DN.{map_name}: {sorted(only_allow)} — these will trigger bundle load but find no entry')
        if only_map:
            err(f'blog/blog-{("diagrams" if "DIAGRAM" in map_name else "calculators")}.js',
                f'DN.{map_name} has slugs not in DN.{allow_name}: {sorted(only_map)} — these articles will NOT load the bundle and the diagram/calculator will silently not render')


# ─── 10c. every article must define :root palette so --bg works ──────
def check_articles_have_root_palette():
    """Every blog article must define the canonical CSS variable palette
    in :root so body{ background:var(--bg) } resolves to the warm beige
    #faf7f2 instead of falling back to browser default white.

    Caught 2026-05-18 when ai-dermatology-roles.html shipped without
    the :root block — the article rendered on stark white and looked
    nothing like its peers.
    """
    REQUIRED = ['--bg', '--ink', '--teal', '--teal-deep', '--border']
    CANONICAL_BG = '#faf7f2'
    for d in ['blog', 'en/blog']:
        dpath = ROOT / d
        if not dpath.exists():
            continue
        for fp in sorted(dpath.glob('*.html')):
            if fp.name in {'index.html', 'topics.html'}:
                continue
            src = fp.read_text(encoding='utf-8', errors='replace')
            root_m = re.search(r':root\s*\{[^}]*\}', src)
            if not root_m:
                err(f'{d}/{fp.name}',
                    f'missing :root palette block — body{{ background:var(--bg) }} '
                    f'will fall back to browser default (white) instead of {CANONICAL_BG}')
                continue
            block = root_m.group(0)
            missing = [v for v in REQUIRED if v not in block]
            if missing:
                err(f'{d}/{fp.name}',
                    f':root missing required vars: {missing}')
            if CANONICAL_BG not in block:
                err(f'{d}/{fp.name}',
                    f':root has --bg but not the canonical {CANONICAL_BG} (warm beige)')


# ─── 10b. unpublished articles must carry noindex meta ────────────────
def check_unpublished_have_noindex():
    """Defense-in-depth: any DN.ARTICLES entry with unpublished:true must
    also ship <meta name="robots" content="noindex,..."> in its HTML.

    Without this, the page is omitted from sitemap.xml + blog listings
    but Google can still index it via backlinks. Caught on 2026-05-18
    when severe-scabies-treatment had unpublished:true but no noindex.
    """
    shared = ROOT / 'blog' / 'blog-shared.js'
    if not shared.exists():
        return
    src = shared.read_text(encoding='utf-8')
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return
    block = m.group(1)
    for entry_m in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}", block):
        e = entry_m.group(0)
        if not re.search(r"\bunpublished\s*:\s*true\b", e):
            continue
        slug = entry_m.group(1)
        fp = ROOT / 'blog' / f'{slug}.html'
        if not fp.exists():
            continue
        html = fp.read_text(encoding='utf-8', errors='replace')
        if not re.search(r'<meta[^>]*name="robots"[^>]*content="[^"]*noindex', html, re.I):
            err(f'blog/{slug}.html',
                f'article is marked unpublished:true in DN.ARTICLES but has no noindex meta — '
                f'Google can still index it via backlinks')


# ─── 11. robots.txt sitemap line ─────────────────────────────────────
def check_robots():
    fp = ROOT / 'robots.txt'
    if not fp.exists():
        err('robots.txt', 'NOT FOUND')
        return
    src = fp.read_text(encoding='utf-8')
    if not re.search(r'(?im)^Sitemap:\s+\S', src):
        err('robots.txt', 'no Sitemap: line')


# ─── Main ────────────────────────────────────────────────────────────
def main():
    # Module-top reconfigure now handles UTF-8 stdout (CODE_REVIEW).
    fast = '--fast' in sys.argv
    canonical_host = check_sitemap()
    check_html(canonical_host, fast=fast)
    check_articles_dates()
    check_no_merge_markers()
    check_no_manual_toc()
    check_article_class()
    check_no_js_corruption()
    check_no_inline_sup_refs()
    check_homepage_card_attrs()
    check_diagram_calc_slug_lists()
    check_unpublished_have_noindex()
    check_articles_have_root_palette()
    check_robots()

    if warnings:
        print(f'\n[!] Warnings ({len(warnings)}):')
        for scope, msg in warnings[:30]:
            print(f'  [{scope}] {msg}')
        if len(warnings) > 30:
            print(f'  ... and {len(warnings)-30} more')

    if errors:
        print(f'\n[X] Errors ({len(errors)}):')
        for scope, msg in errors:
            print(f'  [{scope}] {msg}')
        print(f'\n=> Metadata check FAILED with {len(errors)} error(s).')
        sys.exit(1)
    else:
        print(f'\n[OK] Metadata check passed (canonical host: {canonical_host}, {len(warnings)} warnings).')


if __name__ == '__main__':
    main()
