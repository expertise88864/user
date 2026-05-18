#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject SERP-friendly robots directives into every HTML page.

Two directives have outsize effects on CTR + impressions and are
completely safe to add site-wide:

  max-image-preview:large
    Allows Google to show a LARGE image preview in SERPs / Discover
    instead of the default tiny thumbnail. For visual medical content
    (rash photos, derm diagrams, treatment comparisons) this dramatically
    improves click-through.

  max-snippet:-1
    Allows Google to show the FULL snippet length instead of cutting
    off at ~155 chars. Helpful for long medical descriptions that
    encode value-prop signals beyond the title.

We also add `max-video-preview:-1` for future-proofing video embeds.

Behaviour:
  - Page already has <meta name="robots" content="..."> with noindex:
    KEEP the noindex (don't unlock indexing) but inject the max-*
    directives. Useful for partial-EN pages that may become indexable.

  - Page already has <meta name="robots" content="..."> with index:
    Inject the max-* directives if missing.

  - Page has NO <meta name="robots"> tag:
    Insert one with index,follow,max-image-preview:large,
    max-snippet:-1,max-video-preview:-1 right after <head>.

Run as part of REGEN_STEPS. Idempotent.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent

ROBOTS_META_RE = re.compile(
    r'<meta\s+name="robots"\s+content="([^"]+)"\s*/?>',
    re.IGNORECASE,
)

EXTRA_DIRECTIVES = [
    "max-image-preview:large",
    "max-snippet:-1",
    "max-video-preview:-1",
]


def merge_directives(existing: str) -> str:
    parts = [p.strip() for p in existing.split(",") if p.strip()]
    seen = set(parts)
    for d in EXTRA_DIRECTIVES:
        # max-* directives are unique by their prefix (max-image-preview etc.)
        # so check by prefix to avoid duplicate keys.
        prefix = d.split(":")[0] + ":"
        if not any(p.startswith(prefix) for p in parts):
            parts.append(d)
            seen.add(d)
    return ",".join(parts)


def normalize_file(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    m = ROBOTS_META_RE.search(src)
    if m:
        new_content = merge_directives(m.group(1))
        if new_content == m.group(1):
            return False
        new_tag = f'<meta name="robots" content="{new_content}" />'
        next_src = src[:m.start()] + new_tag + src[m.end():]
    else:
        # No existing robots meta — insert a permissive one after </title>
        # or as the first tag in <head>. Default = index,follow + max-* dirs.
        default = "index,follow," + ",".join(EXTRA_DIRECTIVES)
        new_tag = f'<meta name="robots" content="{default}" />'
        # Prefer to inject right after </title> so it sits with other meta.
        title_close = src.find("</title>")
        if title_close != -1:
            insert_at = title_close + len("</title>")
            next_src = src[:insert_at] + new_tag + src[insert_at:]
        else:
            # Fallback: right after <head>
            head_open = re.search(r"<head[^>]*>", src, re.I)
            if not head_open:
                return False
            insert_at = head_open.end()
            next_src = src[:insert_at] + new_tag + src[insert_at:]

    if next_src == src:
        return False
    path.write_text(next_src, encoding="utf-8")
    return True


SKIP_NAMES = {"404.html", "offline.html", "reset-sw.html", "admin.html"}


def main() -> int:
    targets: list[Path] = []
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in {".git", "node_modules", "pagefind"} for p in parts):
            continue
        if fp.name in SKIP_NAMES:
            continue
        # Skip admin shell — it shouldn't be crawled regardless.
        if fp.relative_to(ROOT).parts[0] == "admin":
            continue
        targets.append(fp)

    changed = sum(1 for fp in targets if normalize_file(fp))
    print(f"Normalized robots meta in {changed} of {len(targets)} HTML files")
    print(f"  Added directives: {', '.join(EXTRA_DIRECTIVES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
