#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject Speculation Rules into every article so cross-article navigation
feels instant.

The Speculation Rules API tells Chromium-based browsers (~70% of TW
desktop + mobile share) to prerender or prefetch the most-likely-next
page when the user shows intent (hover, focus, conservative engagement
signal). When the user clicks, the page swap is instant — no white
flash, no network wait.

Why this matters for SEO/CTR:
  - Bounce rate drops because the first click feels instant. Engagement
    signals (dwell time, pages-per-session) improve, which Google uses
    as a quality / ranking input.
  - INP (Interaction to Next Paint) — a 2024 Core Web Vital — improves
    dramatically because navigation is pre-prepared.
  - Mobile data savings: prefetch is conservative, so it's only
    triggered when the browser is confident.

We inject the same rule set the homepage already uses:
  - prerender: any /blog/* link (moderate eagerness = on viewport+hover)
  - prefetch:  any /* link (conservative = on stronger signal)

Idempotent via the dn-spec-rules marker comment. Skips pages that
already have a <script type="speculationrules">.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

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
    new = cleaned[:body_close] + BLOCK + "\n" + cleaned[body_close:]
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
