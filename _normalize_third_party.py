#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Keep third-party analytics/ads lazy and disabled on local static hosts."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__"}

EAGER_CLARITY_RE = re.compile(r'\s*<script\s+type="text/javascript">[\s\S]*?www\.clarity\.ms/tag/[\s\S]*?</script>', re.I)
THIRD_PARTY_HINT_RE = re.compile(
    r'\s*<link\s+rel="(?:dns-prefetch|preconnect)"\s+href="(?:https?:)?//(?:pagead2\.googlesyndication\.com|www\.googletagmanager\.com|www\.clarity\.ms)"(?:\s+crossorigin)?\s*/?>',
    re.I,
)
STANDALONE_THIRD_PARTY_SCRIPT_RE = re.compile(
    r'\s*<script\b[^>]+\bsrc="https://(?:www\.googletagmanager\.com/gtag/js|pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js)[^"]*"[^>]*></script>'
    r'\s*(?:<script>[\s\S]*?gtag\([\s\S]*?</script>)?',
    re.I,
)
THIRD_PARTY_BLOCK_RE = re.compile(
    r'\s*<script>\(function\(\)\{[\s\S]*?'
    r'(?:pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js|googletagmanager\.com/gtag/js|www\.clarity\.ms/tag)'
    r'[\s\S]*?\}\)\(\);</script>',
    re.I,
)

LOCAL_HELPER = """function isLocalStaticHost(){
  return /^(localhost|127\\.0\\.0\\.1|\\[::1\\])$/.test(location.hostname);
}
"""


def normalize(src: str) -> str:
    next_src = EAGER_CLARITY_RE.sub("", src)
    next_src = THIRD_PARTY_HINT_RE.sub("", next_src)
    if re.search(r'<meta\s+name="robots"\s+content="[^"]*\bnoindex\b', next_src, re.I):
        next_src = STANDALONE_THIRD_PARTY_SCRIPT_RE.sub("", next_src)
        next_src = THIRD_PARTY_BLOCK_RE.sub("", next_src)
        return next_src

    if "function load() {" not in next_src:
        return next_src

    if "function isLocalStaticHost()" not in next_src:
        next_src = re.sub(
            r"(function isInternalPage\(\)\{\s*[\s\S]*?\n\})\nfunction getTrafficType\(\)",
            r"\1\n" + LOCAL_HELPER + "function getTrafficType()",
            next_src,
            count=1,
        )

    next_src = next_src.replace(
        "if (isBot()) return; // skip everything for bots",
        "if (isBot() || isLocalStaticHost()) return; // skip everything for bots/local static tests",
    )
    next_src = next_src.replace(
        "function load() {\n// AdSense",
        "function load() {\nif (/^(localhost|127\\.0\\.0\\.1|\\[::1\\])$/.test(location.hostname)) return;\n// AdSense",
    )
    return next_src


def main() -> None:
    changed = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        src = path.read_text(encoding="utf-8")
        next_src = normalize(src)
        if next_src != src:
            path.write_text(next_src, encoding="utf-8")
            changed += 1
            print("normalized third-party loader", path.relative_to(ROOT).as_posix())
    print(f"Normalized third-party loaders in {changed} files")


if __name__ == "__main__":
    main()
