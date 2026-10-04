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
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs
from _normalize_css_links import ASSET_VERSION
from _site_html import site_html_files

HERE = os.path.dirname(os.path.abspath(__file__))
APPLY = '--apply' in sys.argv

# Pages that should NOT carry audience analytics.
EXCLUDE = {
    'admin.html',
    os.path.join('admin', 'cms.html'),
    os.path.join('admin', 'edit.html'),
    os.path.join('admin', 'index.html'),
    'reset-sw.html',
    os.path.join('en', 'reset-sw.html'),
    'offline.html',
    os.path.join('en', 'admin.html'),
    os.path.join('en', 'offline.html'),
}

KEEPER = f'<script src="/assets/inline/analytics-loader.js?v={ASSET_VERSION}" defer></script>'

# Exact legacy src-tags to remove.
LEGACY_TAGS = [
    '<script async src="https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10"></script>',
    '<script src="https://www.googletagmanager.com/gtag/js?id=G-XFF3L5QD10"></script>',
    '<script src="/assets/inline/gtag-bootstrap.js" defer></script>',
    '<script src="/assets/inline/gtag-bootstrap.js"></script>',
    '<script defer src="/assets/inline/gtag-bootstrap.js"></script>',
]

# Inspect actual executable script elements, preserving comments and inert JSON.
# Offsets refer to the original source so unrelated article markup stays exact.
class _ScriptBlocks(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0] + [match.end() for match in re.finditer('\n', source)]
        self.current = None
        self.blocks = []
        self.inert_depth = 0

    def source_offset(self):
        line, column = self.getpos()
        return self.line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag in {'template', 'noscript'}:
            self.inert_depth += 1
        elif tag == 'script' and not self.inert_depth:
            start = self.source_offset()
            self.current = (start, start + len(self.get_starttag_text()), dict(attrs))

    def handle_startendtag(self, tag, attrs):
        if tag == 'script':
            raise ValueError('Self-closing script block; analytics normalization aborted')

    def handle_endtag(self, tag):
        if tag in {'template', 'noscript'}:
            self.inert_depth = max(0, self.inert_depth - 1)
        elif tag == 'script' and self.current is not None:
            start, content_start, attrs = self.current
            content_end = self.source_offset()
            end = self.source.index('>', content_end) + 1
            self.blocks.append((start, end, attrs, self.source[content_start:content_end]))
            self.current = None


def script_blocks(source):
    parser = _ScriptBlocks(source)
    parser.feed(source)
    parser.close()
    if parser.current is not None:
        raise ValueError('Unclosed script block; analytics normalization aborted')
    return parser.blocks


def executable_script(attrs):
    script_type = (attrs.get('type') or '').split(';', 1)[0].strip().lower()
    return script_type in {'', 'module', 'text/javascript', 'application/javascript'}


def current_loader(attrs):
    url = urlsplit(attrs.get('src') or '')
    return (executable_script(attrs) and not url.scheme and not url.netloc
            and url.path == '/assets/inline/analytics-loader.js')


def legacy_script_edits(source):
    edits = []
    for start, end, attrs, body in script_blocks(source):
        if not executable_script(attrs):
            continue
        src = attrs.get('src')
        if src:
            url = urlsplit(src)
            bootstrap = not url.scheme and not url.netloc and url.path == '/assets/inline/gtag-bootstrap.js'
            google = (url.hostname in {'www.googletagmanager.com', 'googletagmanager.com'}
                      and url.path == '/gtag/js'
                      and 'G-XFF3L5QD10' in parse_qs(url.query).get('id', []))
            clarity = url.hostname == 'www.clarity.ms' and url.path.startswith('/tag/')
            if bootstrap or google or clarity:
                edits.append((start, end, 'external'))
            continue
        google = ('G-XFF3L5QD10' in body and
                  (re.search(r"\bgtag\s*\(\s*(['\"])config\1", body)
                   or 'googletagmanager.com/gtag/js' in body))
        clarity = ('clarity.ms/tag/' in body and
                   ('createElement' in body or re.search(r'\bclarity\s*\(', body)))
        if google or clarity:
            edits.append((start, end, 'inline'))
    return edits


def collect_html():
    return [str(path) for path in site_html_files(HERE)]


def normalize(src):
    """Return (new_src, n_removed_tags, n_removed_inline)."""
    # Only actual executable elements count as loaders. Comments, script
    # examples and inert JSON must not be normalized, deduplicated or stripped.
    s = src
    loaders = [(start, end) for start, end, attrs, _ in script_blocks(s)
               if current_loader(attrs)]
    for start, end in reversed(loaders):
        s = s[:start] + KEEPER + s[end:]
    edits = legacy_script_edits(s)
    n_tags = sum(kind == 'external' for _, _, kind in edits)
    n_inline = sum(kind == 'inline' for _, _, kind in edits)
    for start, end, _ in reversed(edits):
        s = s[:start] + s[end:]
    return s, n_tags, n_inline


def main():
    # Validate the complete inventory and decode every source before any write.
    # An invalid or linked later source must not leave a partly rewritten site.
    sources = []
    for path in collect_html():
        with open(path, 'r', encoding='utf-8') as fp:
            sources.append((path, fp.read()))
    changes = []
    prepared = []
    for p, src in sources:
        rel = os.path.relpath(p, HERE)
        excluded = rel in EXCLUDE or rel.startswith('admin' + os.sep)
        s, n_tags, n_inline = normalize(src)

        # Dedup keeper: keep first, drop the rest.
        loaders = [(start, end) for start, end, attrs, _ in script_blocks(s)
                   if current_loader(attrs)]
        k = len(loaders)
        n_dedup = 0
        if k > 1:
            for start, end in reversed(loaders[1:]):
                s = s[:start] + s[end:]
            n_dedup = k - 1
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
            stripped_excluded = k
            for start, end, attrs, _ in reversed(script_blocks(s)):
                if current_loader(attrs):
                    s = s[:start] + s[end:]

        if s != src:
            changes.append((rel, n_tags, n_inline, n_dedup, injected, stripped_excluded))
            prepared.append((p, s))

    if APPLY:
        for p, s in prepared:
            with open(p, 'w', encoding='utf-8') as fp:
                fp.write(s)

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
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
