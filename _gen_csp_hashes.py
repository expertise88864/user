#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Replace `script-src 'unsafe-inline'` with sha256 hashes of the real scripts.

CODE_REVIEW TD-04 — the site's CSP allowed ANY inline script on every page,
which is the allowance that makes a CSP largely decorative against injected
markup. TECH_DEBT framed the fix as "nonce-ing or externalising the inline
scripts — a project-level refactor". A static site has a third option that is
strictly better than either: hash every inline script that actually ships and
list those hashes. No server-side nonce generation, no runtime cost, and the
gate can verify the list matches the deployed HTML exactly.

Measured on this site: 456 distinct inline script bodies, but only **25** need
hashing — 23 executable blocks plus 2 `type="speculationrules"` variants. The
other 431 are `type="application/ld+json"`, which browsers never execute, so
`script-src` does not govern them.

That was confirmed in a browser, not assumed. Two local servers were run with
the same CSP minus 'unsafe-inline', one with the 25 hashes and one with none:

    inline <script> injected at runtime   blocked on BOTH   (CSP is enforced)
    dn_lang set by a hashed inline script  "en" WITH hashes / null WITHOUT

so the hashes are what let the real scripts run, they match the browser's own
digest byte for byte, and the unhashed JSON-LD blocks caused no violation.

Runs after _minify.py, because minification rewrites inline script bodies and
the hash must be of the bytes that actually ship. _check_deployment.py then
asserts the CSP covers every inline script found in the built HTML — so a page
whose script changes without a rebuild fails the gate instead of silently
losing that script in production.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import iter_inline_scripts  # noqa: E402

VERCEL = ROOT / "vercel.json"
SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}

# Script types the browser EXECUTES, so `script-src` applies. An empty type is
# classic JavaScript. `speculationrules` is included deliberately: the
# Speculation Rules spec routes inline rule sets through script-src too.
# `application/ld+json` is absent on purpose — it is a data block.
HASHED_TYPES = {"", "text/javascript", "module", "speculationrules"}

# Anti-vacuity floor. If the scan stops finding inline scripts, this generator
# would happily write a CSP with no hashes and every inline script on the site
# would die in production. Refuse instead.
MIN_HASHES = 20

# CODE_REVIEW TD-04 — which CSP rule governs which pages. The admin scopes get
# ONLY the hashes their own pages need, not the site-wide union.
# Why it matters: with the union, every public inline body was executable on
# /admin. `en/reset-sw.html`'s script unregisters service workers and clears
# localStorage / sessionStorage / IndexedDB — which is where admin.html keeps
# the GitHub PAT and autosaved drafts. Under the union, any markup injection
# reaching /admin could replay that exact allowed body as a ready-made gadget.
# Measured: admin pages need 3 hashes, public pages 22, with zero overlap.
# This split is safe under EITHER Vercel semantics — if the admin rule
# overrides, admin gets its own subset; if both headers are sent, the browser
# enforces global ∩ admin = the admin subset. Admin scripts run either way.
# Scope is derived from each rule's own `source` pattern rather than a
# hardcoded list, so the three admin rules get what they ACTUALLY govern:
# /admin.html and /admin cover admin.html, /admin/(.*) covers admin/edit.html.
# _check_deployment.py derives the same thing independently and fails loudly if
# the two ever disagree — which is exactly how the first, too-coarse version of
# this split (one shared admin set for all three rules) was caught.

# The precondition for HTML's script "double escaped" state: a body containing
# `<!--` and then `<script`. Inside it the tokenizer treats a `</script>` as
# script data rather than the end tag, so a scanner that does not model those
# transitions can hash a truncated body — and both the generator and the
# checker share this scanner, so they would agree on the wrong hash. Rather
# than implement the full state machine for a case no page uses (measured: 0),
# refuse and say so.
DOUBLE_ESCAPE_MARKERS = ("<!--", "<script")


# CODE_REVIEW TD-04 — documents that can be served under ANY path, so their
# hashes belong in EVERY CSP rule, not just the one matching their own URL.
# 404.html is Vercel's custom error document: a request to a nonexistent
# /admin/* URL matches the /admin/(.*) header rule but is answered with
# 404.html, whose bootstrap would otherwise be blocked. offline.html is served
# by the service worker as the navigation fallback for any URL.
ANY_PATH_DOCUMENTS = {"404.html", "offline.html"}


def rule_governs(source: str, rel: str) -> bool:
    """Does a vercel.json header `source` pattern govern this HTML file?"""
    if rel in ANY_PATH_DOCUMENTS:
        return True
    clean = rel[: -len(".html")] if rel.endswith(".html") else rel
    if source == "/(.*)":
        return True
    if source.endswith("/(.*)"):
        return rel.startswith(source[1:-len("(.*)")])
    return source.lstrip("/") in (rel, clean)


def sha256_source(body: str) -> str:
    digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
    return f"'sha256-{digest}'"


def collect_hashes() -> tuple[dict[str, set[str]], int, int, list[str]]:
    """(hashes per HTML file, files, scripts, refusals)."""
    per_file: dict[str, set[str]] = {}
    files = 0
    scripts = 0
    refusals: list[str] = []
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files += 1
        rel = path.relative_to(ROOT).as_posix()
        for attrs, body in iter_inline_scripts(path.read_text(encoding="utf-8")):
            if not body.strip():
                continue
            if attrs.get("type", "").strip().lower() not in HASHED_TYPES:
                continue
            lowered = body.lower()
            if all(marker in lowered for marker in DOUBLE_ESCAPE_MARKERS):
                refusals.append(rel)
                continue
            scripts += 1
            per_file.setdefault(rel, set()).add(sha256_source(body))
    return per_file, files, scripts, refusals


def rewrite_script_src(csp: str, hashes: list[str]) -> str:
    """Drop 'unsafe-inline' and any stale hashes, then append the current set."""
    out = []
    for directive in csp.split(";"):
        stripped = directive.strip()
        if stripped.startswith("script-src"):
            tokens = [
                t for t in stripped.split()
                if t != "'unsafe-inline'" and not t.startswith("'sha256-")
            ]
            stripped = " ".join(tokens + hashes)
        if stripped:
            out.append(stripped)
    return "; ".join(out)


def main() -> int:
    per_file, files, scripts, refusals = collect_hashes()
    all_hashes = set().union(*per_file.values()) if per_file else set()
    if refusals:
        print(f"[csp-hashes] REFUSING to write: {len(refusals)} inline script(s) contain both "
              f"'<!--' and '<script', the precondition for HTML's script double-escaped state, "
              f"which this scanner does not model — hashing them could truncate the body and "
              f"block the script in production. Files: {', '.join(sorted(set(refusals))[:5])}")
        return 1
    if len(all_hashes) < MIN_HASHES:
        print(f"[csp-hashes] REFUSING to write: only {len(all_hashes)} inline script "
              f"hash(es) found across {files} file(s) (expected >= {MIN_HASHES}). Writing this "
              f"CSP would kill every inline script on the site.")
        return 1

    config = json.loads(VERCEL.read_text(encoding="utf-8"))
    touched = 0
    for rule in config.get("headers", []):
        source = rule.get("source", "")
        wanted = sorted(
            h
            for rel, hs in per_file.items()
            if rule_governs(source, rel)
            for h in hs
        )
        wanted = sorted(set(wanted))
        for kv in rule.get("headers", []):
            if kv["key"].lower() != "content-security-policy":
                continue
            new = rewrite_script_src(kv["value"], wanted)
            if new != kv["value"]:
                kv["value"] = new
                touched += 1

    rendered = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    if rendered != VERCEL.read_text(encoding="utf-8"):
        VERCEL.write_text(rendered, encoding="utf-8")
        print(f"[csp-hashes] vercel.json updated — {len(all_hashes)} hashes across "
              f"{len(per_file)} page(s); {touched} CSP rule(s) changed")
    else:
        print(f"[csp-hashes] vercel.json already current — {len(all_hashes)} hashes")
    print(f"  scanned {files} HTML file(s), {scripts} executable inline script(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
