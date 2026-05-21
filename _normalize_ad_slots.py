#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Strip visible '廣告位 · AdSense' placeholder text from every ad-slot
div until AdSense (or any ad provider) actually ships.

SEO_AUDIT A2: indexable pages were rendering literal '廣告位 · AdSense'
strings inside <div class="ad-slot">…</div> blocks. Googlebot read
this as "the site has empty / unfilled ad inventory", which is a
weak commercial-intent signal AND clutters snippet candidates.

What this normalizer does:
  1. Find every <div class="ad-slot ...">PLACEHOLDER_TEXT</div>
  2. Strip the data-zh / data-en attribute values that say "廣告位"
  3. Strip the literal "廣告位 · AdSense" / "廣告位" / "Ad slot" body
  4. Leave the empty <div class="ad-slot ..."></div> in place so:
     - When AdSense (or any provider) is wired, the markup is ready
     - CSS rule .ad-slot:empty { display: none } in tw-mini.css hides
       the empty placeholder visually (already added)

Idempotent. Wired into REGEN_STEPS to clear any future regressions.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent

# Match a <div class="...ad-slot..."> with any attrs and body
# (greedy but bounded to a single tag depth — no nested <div> expected).
AD_SLOT_RE = re.compile(
    r'(<div\s+[^>]*\bclass="[^"]*\bad-slot\b[^"]*"[^>]*?)'  # opening, group 1
    r'>'
    r'([^<]*?)'                                              # text body, group 2
    r'</div>',
    re.IGNORECASE,
)

# Strip the data-zh / data-en attrs that contain the placeholder text
PLACEHOLDER_ATTR_RE = re.compile(
    r'\s+data-(?:zh|en)="(?:廣告位|Ad\s+slot)[^"]*"',
    re.IGNORECASE,
)

# Visible text patterns inside the slot
PLACEHOLDER_BODY_RE = re.compile(
    r'^\s*(?:廣告位\s*[·•]?\s*AdSense|廣告位|Ad\s+slot[^<]*|Ad\s+placement[^<]*|AdSense)\s*$',
    re.IGNORECASE,
)


def clean_one(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    changed = 0

    def replace(m: re.Match) -> str:
        nonlocal changed
        opening = m.group(1)
        body = m.group(2)

        # Strip placeholder data-zh / data-en attrs from the opening tag
        cleaned_opening = PLACEHOLDER_ATTR_RE.sub("", opening)
        # Empty out the body if it's the placeholder text
        if PLACEHOLDER_BODY_RE.match(body):
            cleaned_body = ""
        else:
            cleaned_body = body
        result = f"{cleaned_opening}>{cleaned_body}</div>"
        if result != m.group(0):
            changed += 1
        return result

    new_src = AD_SLOT_RE.sub(replace, src)
    if new_src != src:
        path.write_text(new_src, encoding="utf-8")
    return changed


def main() -> int:
    targets = []
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in {".git", "node_modules", "pagefind"} for p in parts):
            continue
        targets.append(fp)

    total = 0
    files = 0
    for fp in targets:
        n = clean_one(fp)
        if n:
            total += n
            files += 1

    print(f"[ad-slots] cleared {total} placeholder bodies across "
          f"{files} pages (kept empty <div> for future ad slot wiring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
