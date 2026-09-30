#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offer speculative article navigation as a progressive enhancement.

Supported browsers may prefetch or prerender a likely next page on a qualifying
interaction. Browsers can decline the hint, and a navigation can still require
network loading. Prerendering also consumes bandwidth, memory, and CPU; it does
not promise mobile data savings, lower bounce rates, ranking gains, or a fixed
INP improvement. Measure activated navigation latency and wasted requests.
See https://developer.chrome.com/docs/web-platform/prerender-pages

Keep the existing prerender/prefetch rules and exclusions. Skip pages that
already contain speculationrules; mark generated blocks with dn-spec-rules.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent

# Same rule set as index.html — duplicated here so each page is
# self-contained (Chromium reads speculation rules from the navigated
# page, not the referrer).
SPEC_RULES_JSON = (
    '{"prerender":[{"where":{"and":[{"href_matches":"/blog/*"},'
    '{"not":{"href_matches":"/admin*"}},'
    '{"not":{"selector_matches":"[data-no-prerender]"}}]},'
    '"eagerness":"moderate"}],'
    '"prefetch":[{"where":{"href_matches":"/*"},"eagerness":"conservative"}]}'
)

# CODE_REVIEW — validate at module load so a typo in the constant
# above gets caught at build time instead of silently breaking Chrome
# prerender at runtime (Chrome ignores malformed speculation rules
# without console output).
try:
    json.loads(SPEC_RULES_JSON)
except json.JSONDecodeError as _exc:  # pragma: no cover — module init
    raise SystemExit(
        f"SPEC_RULES_JSON is not valid JSON: {_exc}. "
        "Fix the constant before re-running the build."
    )

BLOCK = (
    "\n<!-- dn-spec-rules -->\n"
    '<script type="speculationrules">' + SPEC_RULES_JSON + '</script>'
)

# Strip any prior injection (idempotent re-runs).
EXISTING_RE = re.compile(
    r"\s*<!-- dn-spec-rules -->\s*"
    r'<script type="speculationrules">[\s\S]*?</script>',
    re.IGNORECASE,
)

# Detect existing native speculation rules (e.g., the homepage's
# hand-written block) so we don't double-inject.
NATIVE_RE = re.compile(
    r'<script type="speculationrules">',
    re.IGNORECASE,
)

SKIP_NAMES = {"404.html", "offline.html", "reset-sw.html", "admin.html"}
SKIP_DIRS = {".git", "node_modules", "pagefind", "admin"}


def inject_one(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    # Strip any prior dn-spec-rules block (idempotent)
    cleaned = EXISTING_RE.sub("", src)
    # If a native (non-dn) speculation rules block already exists, leave it.
    if NATIVE_RE.search(cleaned):
        if cleaned != src:
            path.write_text(cleaned, encoding="utf-8")
            return True
        return False
    # Insert right before </body> so it's the last block in the page.
    body_close = cleaned.rfind("</body>")
    if body_close == -1:
        return False
    # Normalize the separator: removing an old block leaves its trailing newline.
    # Without rstrip each generator pass adds another blank line.
    new = cleaned[:body_close].rstrip() + BLOCK + "\n" + cleaned[body_close:]
    if new == src:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    targets: list[Path] = []
    for fp in sorted(ROOT.rglob("*.html")):
        parts = fp.relative_to(ROOT).parts
        if any(p in SKIP_DIRS for p in parts):
            continue
        if fp.name in SKIP_NAMES:
            continue
        targets.append(fp)
    changed = 0
    for fp in targets:
        try:
            if inject_one(fp):
                changed += 1
        except Exception as exc:
            print(f"[!] {fp.relative_to(ROOT)} failed: {exc}")
    print(f"Injected dn-spec-rules into {changed} of {len(targets)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
