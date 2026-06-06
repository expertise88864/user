#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Normalize analytics across all HTML to a single, consistent mechanism.

Problem this fixes (see audit): GA4 (G-XFF3L5QD10) + Clarity were instrumented
THREE different ways across the site — the good /assets/inline/analytics-loader.js
(bot-filtered, idle-loaded, single config), a legacy eager gtag/js tag with NO bot
filter, a legacy gtag-bootstrap.js, and a couple of inline gtag('config') blocks.
Pages ended up double-/triple-firing page_views, while 37 pages had NO analytics
at all (incl. ~24 real articles, support, notes). Net: the "~visitors/day" number
was simultaneously inflated (double hits + bots) and deflated (uninstrumented pages).

Fix: every content page references analytics-loader.js EXACTLY ONCE and nothing else.
Internal/utility pages (admin, reset-sw, offline) get no analytics (the loader would
self-suppress on admin/reset-sw anyway; offline can't transmit).

Usage:  python _normalize_analytics.py            # dry-run (report only)
        python _normalize_analytics.py --apply     # write changes
"""
import os, io, sys, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
APPLY = '--apply' in sys.argv

SKIP_DIRS = ('.git', 'pagefind', '__pycache__', 'astro-rewrite', '_pdf_extracts', 'node_modules')

# Pages that should NOT carry audience analytics.
EXCLUDE = {
    'admin.html',
    os.path.join('admin', 'cms.html'),
    os.path.join('admin', 'edit.html'),
    os.path.join('admin', 'index.html'),
    'reset-sw.html',
    os.path.join('en', 'reset-sw.html'),
    'offline.html',
}

KEEPER = '<script src="/assets/inline/analytics-loader.js" defer></script>'

# Exact legacy src-tags to remove.
LEGACY_TAGS = [
    '<script async src="https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10"></script>',
    '<script src="https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10"></script>',
    '<script src="/assets/inline/gtag-bootstrap.js" defer></script>',
    '<script src="/assets/inline/gtag-bootstrap.js"></script>',
    '<script defer src="/assets/inline/gtag-bootstrap.js"></script>',
]

# Inline <script> blocks (opening tag EXACTLY "<script>", no attributes) that
# contain the GA id — covers the inline gtag('config') block AND the inline
# loader copy. The DN i18n init and the admin app block do NOT contain the id,
# so they are never matched.
INLINE_GA_RE = re.compile(r'<script>(?:(?!</script>).)*?G-XFF3L5QD10(?:(?!</script>).)*?</script>', re.S)


def collect_html():
    out = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in files:
            if fn.endswith('.html'):
                out.append(os.path.join(root, fn))
    return sorted(out)


def normalize(src):
    """Return (new_src, n_removed_tags, n_removed_inline)."""
    s = src
    n_tags = 0
    for tag in LEGACY_TAGS:
        c = s.count(tag)
        if c:
            s = s.replace(tag, '')
            n_tags += c
    n_inline = 0
    def _sub(m):
        nonlocal n_inline
        n_inline += 1
        return ''
    s = INLINE_GA_RE.sub(_sub, s)
    return s, n_tags, n_inline


def main():
    changes = []
    for p in collect_html():
        rel = os.path.relpath(p, HERE)
        excluded = rel in EXCLUDE
        src = open(p, 'r', encoding='utf-8', errors='replace').read()
        s, n_tags, n_inline = normalize(src)

        # Dedup keeper: keep first, drop the rest.
        k = s.count(KEEPER)
        n_dedup = 0
        if k > 1:
            first = s.index(KEEPER)
            head = s[:first + len(KEEPER)]
            tail = s[first + len(KEEPER):].replace(KEEPER, '')
            n_dedup = k - 1
            s = head + tail
            k = 1

        # Inject keeper if a content page is missing it.
        injected = False
        if not excluded and k == 0:
            if '</head>' in s:
                s = s.replace('</head>', KEEPER + '</head>', 1)
                injected = True
            elif '</body>' in s:
                s = s.replace('</body>', KEEPER + '</body>', 1)
                injected = True

        # If excluded but somehow has a keeper, strip it.
        stripped_excluded = 0
        if excluded and k >= 1:
            stripped_excluded = s.count(KEEPER)
            s = s.replace(KEEPER, '')

        if s != src:
            changes.append((rel, n_tags, n_inline, n_dedup, injected, stripped_excluded))
            if APPLY:
                open(p, 'w', encoding='utf-8').write(s)

    print(("APPLIED" if APPLY else "DRY-RUN") + " — analytics normalization")
    print("files changed:", len(changes))
    rem_tags = sum(c[1] for c in changes)
    rem_inline = sum(c[2] for c in changes)
    dedup = sum(c[3] for c in changes)
    inj = sum(1 for c in changes if c[4])
    excl_strip = sum(c[5] for c in changes)
    print(f"  legacy src-tags removed: {rem_tags}")
    print(f"  inline GA blocks removed: {rem_inline}")
    print(f"  duplicate loaders removed: {dedup}")
    print(f"  loaders injected (was missing): {inj}")
    print(f"  loaders stripped from excluded pages: {excl_strip}")
    print()
    for rel, nt, ni, nd, ij, es in changes:
        flags = []
        if nt: flags.append(f"-{nt}tag")
        if ni: flags.append(f"-{ni}inline")
        if nd: flags.append(f"-{nd}dup")
        if ij: flags.append("+loader")
        if es: flags.append(f"-{es}excl")
        print(f"  {rel:55} {' '.join(flags)}")


if __name__ == '__main__':
    main()
