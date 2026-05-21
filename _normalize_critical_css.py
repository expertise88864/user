#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract @media print rules from every page's inline <style> into a
single shared external stylesheet loaded with media="print".

Round 2-H from OPEN_SOURCE_INTEGRATIONS.md (pragmatic Python-only
alternative to beasties — no Node dependency required).

Why @media print is the right first cut:
  1. Identical across all 114 pages (~2 KB each → 228 KB of redundant
     inline weight site-wide before HTML compression).
  2. Browsers don't fetch `<link rel="stylesheet" media="print">`
     during normal page load — only when the user invokes Cmd+P /
     File→Print. So extraction = pure cold-load weight savings with
     ZERO render-blocking cost.
  3. Safe to extract: print rules never affect interactive painting,
     so we can move them out of the critical path entirely.

Idempotent: detects existing `<link ... media="print">` matching our
canonical href and skips. Strips `@media print { ... }` from inline
<style> blocks each run.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

try:
    sys.path.insert(0, str(ROOT))
    from _normalize_css_links import ASSET_VERSION as _ASSET_VERSION
except Exception:
    _ASSET_VERSION = "202605191900"

PRINT_CSS_PATH = ROOT / "assets" / "dn-print.css"
PRINT_LINK = (
    f'<link rel="stylesheet" media="print" '
    f'href="/assets/dn-print.css?v={_ASSET_VERSION}" '
    f'id="dn-print-css">'
)

# SEO_AUDIT B4 — below-fold CSS extraction. Conservative: only extract
# rules that are KNOWN to be below the fold (mag-footer, .home-faq).
# Everything else stays inline to avoid FOUC.
BELOW_FOLD_CSS_PATH = ROOT / "assets" / "dn-below-fold.css"
BELOW_FOLD_LINK = (
    f'<link rel="stylesheet" '
    f'href="/assets/dn-below-fold.css?v={_ASSET_VERSION}" '
    f'id="dn-below-fold-css">'
)

# @media print { ... }  with balanced-brace matching
PRINT_MEDIA_RE = re.compile(
    r"@media\s+print\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
    re.IGNORECASE,
)

# Below-fold rule families — each pattern matches ONE rule (selector
# + braces). Carefully scoped to avoid matching above-fold selectors.
BELOW_FOLD_RULE_RES = [
    # .mag-footer { ... } and all its nested selectors
    re.compile(r"\.mag-footer\b[^{}]*\{[^{}]*\}", re.MULTILINE),
    # Footer-section-specific selectors derived from .mag-footer
    re.compile(r"\.mag-foot-(?:cols|col|brand|copy|meta|links)\b[^{}]*\{[^{}]*\}", re.MULTILINE),
]

# Detect existing extracted-link tags (for idempotency).
EXISTING_LINK_RE = re.compile(
    r'<link[^>]+id="(?:dn-print-css|dn-below-fold-css)"[^>]*>',
    re.IGNORECASE,
)

SKIP_NAMES = {"404.html", "offline.html", "reset-sw.html", "admin.html"}
SKIP_DIRS = {".git", "node_modules", "pagefind", "admin"}


def extract_from_file(path: Path,
                       canonical_print_css: list[str],
                       canonical_below_fold_css: list[str]) -> int:
    """Extract @media print + below-fold rules from inline <style>.

    Returns total number of rules extracted (0 if no change).
    canonical_* lists mutate — first-run rules get appended for
    later writing to the shared external stylesheets.
    """
    src = path.read_text(encoding="utf-8")
    extracted_count = 0
    print_extracted = 0
    below_fold_extracted = 0

    def replace_style(m: re.Match) -> str:
        nonlocal extracted_count, print_extracted, below_fold_extracted
        css = m.group(1)
        print_chunks = []
        below_fold_chunks = []

        def collect_print(mm: re.Match) -> str:
            nonlocal print_extracted
            print_chunks.append(mm.group(0))
            print_extracted += 1
            return ""

        def collect_below(mm: re.Match) -> str:
            nonlocal below_fold_extracted
            below_fold_chunks.append(mm.group(0))
            below_fold_extracted += 1
            return ""

        new_css = PRINT_MEDIA_RE.sub(collect_print, css)
        for pattern in BELOW_FOLD_RULE_RES:
            new_css = pattern.sub(collect_below, new_css)

        # First file we see contributes the canonical version; later
        # files just strip locally (they should be identical).
        if print_chunks and not canonical_print_css:
            canonical_print_css.extend(print_chunks)
        if below_fold_chunks and not canonical_below_fold_css:
            canonical_below_fold_css.extend(below_fold_chunks)
        extracted_count = print_extracted + below_fold_extracted
        return m.group(0).replace(css, new_css)

    new_src = re.sub(
        r"<style\b[^>]*>([\s\S]*?)</style>",
        replace_style,
        src,
    )

    if extracted_count == 0:
        return 0

    # Inject the <link> tags if not already present.
    if print_extracted and "dn-print-css" not in new_src:
        head_close = new_src.find("</head>")
        if head_close != -1:
            new_src = new_src[:head_close] + PRINT_LINK + new_src[head_close:]
    if below_fold_extracted and "dn-below-fold-css" not in new_src:
        head_close = new_src.find("</head>")
        if head_close != -1:
            new_src = new_src[:head_close] + BELOW_FOLD_LINK + new_src[head_close:]

    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
        return extracted_count
    return 0


def main() -> int:
    targets: list[Path] = []
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        if fp.name in SKIP_NAMES:
            continue
        targets.append(fp)

    canonical_print_chunks: list[str] = []
    canonical_below_fold_chunks: list[str] = []
    total_extracted = 0
    files_changed = 0

    for fp in targets:
        n = extract_from_file(fp, canonical_print_chunks, canonical_below_fold_chunks)
        if n:
            total_extracted += n
            files_changed += 1

    # Write the shared print CSS
    if canonical_print_chunks:
        PRINT_CSS_PATH.parent.mkdir(exist_ok=True)
        header = (
            "/* Auto-generated by _normalize_critical_css.py — DO NOT EDIT.\n"
            " * Print-only rules extracted from inline <style> blocks.\n"
            " * Loaded via <link rel=\"stylesheet\" media=\"print\"> so\n"
            " * browsers fetch only when the user actually prints.\n"
            " */\n"
        )
        PRINT_CSS_PATH.write_text(
            header + "\n".join(canonical_print_chunks) + "\n",
            encoding="utf-8",
        )

    # Write the shared below-fold CSS
    if canonical_below_fold_chunks:
        BELOW_FOLD_CSS_PATH.parent.mkdir(exist_ok=True)
        header = (
            "/* Auto-generated by _normalize_critical_css.py — DO NOT EDIT.\n"
            " * Below-fold rules (mag-footer family) extracted from inline\n"
            " * <style> blocks. SEO_AUDIT B4. Loaded via standard\n"
            " * <link rel=\"stylesheet\"> — below-fold means no LCP impact;\n"
            " * cached across pages for instant subsequent loads.\n"
            " */\n"
        )
        BELOW_FOLD_CSS_PATH.write_text(
            header + "\n".join(canonical_below_fold_chunks) + "\n",
            encoding="utf-8",
        )

    print(f"[critical-css] extracted {total_extracted} rules from "
          f"{files_changed} pages")
    if PRINT_CSS_PATH.exists():
        print(f"  - {PRINT_CSS_PATH.relative_to(ROOT).as_posix()}: "
              f"{PRINT_CSS_PATH.stat().st_size} bytes")
    if BELOW_FOLD_CSS_PATH.exists():
        print(f"  - {BELOW_FOLD_CSS_PATH.relative_to(ROOT).as_posix()}: "
              f"{BELOW_FOLD_CSS_PATH.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
