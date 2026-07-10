#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Broad-scan companion to _check_api_security.py / _check_frontend_security.py.

CODE_REVIEW TD-31 — those two checkers are string-contract regression locks over
a FIXED file list: they assert specific strings are (or aren't) present in files
they know about. Two gaps follow:
  1. A newly added `api/admin/*.js` or frontend page is not audited at all.
  2. They forbid `innerHTML` only via specific old variable names; a new sink
     (different identifier, `insertAdjacentHTML`, `document.write`) slips past.

This checker closes both by globbing the whole security-relevant surface and
asserting:
  A. Hard-forbidden constructs appear NOWHERE (baseline: zero occurrences).
  B. `innerHTML` / `insertAdjacentHTML` appear only in files on an explicit
     reviewed allowlist. A new file using them fails until a human audits it
     and adds it here — which is the point.
  C. An `Authorization` header never embeds a literal credential (all current
     call sites interpolate a variable).

False-positive control: comments are stripped before matching. This is not
cosmetic — `api/admin/login.js` has a comment mentioning `localStorage`, and
`admin/edit.html` + `blog-shared.js` mention `javascript:` inside URL-rejection
guards. A naive grep flags all three. We reuse `_minify.js_minify()`, which is
string- and regex-literal-aware, so `'https://…'` is never mistaken for a `//`
comment.

DESIGN CHOICE — bias toward false positives, never false negatives. The scan
runs on comment-stripped code with STRING LITERALS INTACT. That is deliberate:
a bracket-notation sink writes the property name as a string literal
(`el['innerHTML'] = x`, `document['write'](...)`), so blanking string bodies to
suppress "sink-shaped text inside a string" would erase the very token that
makes those a sink — trading a harmless false positive for a dangerous false
negative. We keep strings so every real sink is caught.

KNOWN LIMITS (documented, not silently ignored):
 - False positive: a string/template literal whose TEXT contains a sink spelling
   (`const w = "please don't call eval("`) is reported. It fails safe — the
   message names the file and line so it's trivial to refactor or allowlist —
   and no file in the current tree trips it.
 - False negative only via deliberate obfuscation (`el['inner' + 'HTML'] = x`,
   `Reflect.set(el, 'innerHTML', x)`). This is a lexical scan; its job is to
   stop accidental regressions and unaudited new files, not a hostile committer
   who already holds push access.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _minify import js_minify

ROOT = Path(__file__).resolve().parent

# Security-relevant surface. Globs so NEW files are picked up automatically —
# that is the whole point of this checker.
SCAN_GLOBS = (
    "api/*.js",
    "api/**/*.js",
    "admin/*.js",
    "admin/*.html",
    "middleware.js",
    "sw.js",
    "assets/inline/*.js",
    "blog/*.js",
    # CODE_REVIEW — frontend HTML carries inline <script> blocks too (index.html
    # has an innerHTML sink). Scanning only admin*.html left those unaudited.
    "*.html",
    "blog/*.html",
    "en/*.html",
    "en/blog/*.html",
)

# Files reviewed and permitted to build HTML strings. Adding a file here is a
# deliberate act: audit that every interpolated value is escaped first.
INNERHTML_ALLOWLIST = frozenset({
    "admin.html",
    "dashboard.html",
    "index.html",
    "en/index.html",
    # Private, noindex, robots-disallowed service-worker reset utility (declared
    # as an expected private page by _check_index_boundaries.py). Its sinks
    # interpolate a registration count and a browser Error message, not user
    # input. See TECH_DEBT TD-36: could use textContent instead.
    "en/reset-sw.html",
    "admin/admin-extras.js",
    "admin/edit.html",
    "blog/blog-shared.js",
    "blog/blog-hub.js",
    "blog/blog-calculators.js",
    "blog/blog-article-reading.js",
    "blog/blog-article-footer.js",
    "blog/blog-article-visuals.js",
    "blog/pagefind-search.js",
})

# If a glob silently stops matching, the audit would go vacuously green. Two
# independent guards:
#   1. every SCAN_GLOBS pattern must match at least one file — this is what
#      catches a whole omitted category; a scanned-file COUNT cannot, because
#      the other globs still make up a plausible total, and
#   2. these representative files must actually have been scanned.
REQUIRED_SCANNED = (
    "api/og.js",
    "api/admin/_session.js",
    "admin.html",
    "admin/admin-extras.js",
    "admin/edit.html",
    "dashboard.html",
    "index.html",
    "middleware.js",
    "sw.js",
    "blog/blog-shared.js",
    "assets/inline/analytics-loader.js",
)

# Quote characters. MUST include the backtick: both ``el[`innerHTML`]`` and
# ``Authorization: `Basic …` `` are valid JS, and omitting it silently drops
# template-literal coverage.
_Q = r"""['"`]"""
# Assignment forms: `=`, `+=`, and the logical-assignment operators
# (`||=`, `&&=`, `??=`). The `(?!=)` is essential — without it `el.innerHTML
# === x` (a comparison) is reported as an assignment.
_ASSIGN = r"\s*(?:\+|\|\||&&|\?\?)?=(?!=)"

FORBIDDEN = (
    (re.compile(r"\beval\s*\("), "eval()"),
    # `new Function(...)` and the bare `Function(...)` constructor call.
    (re.compile(r"\bFunction\s*\("), "Function() constructor"),
    # NB: `write(?:ln)?` — NOT `writeln?`, which parses as `writel` + optional
    # `n` and therefore never matches plain `document.write(`.
    (re.compile(rf"\bdocument\s*(?:\.\s*write(?:ln)?|\[\s*{_Q}write(?:ln)?{_Q}\s*\])\s*\("), "document.write()"),
    (re.compile(rf"(?:\.\s*outerHTML|\[\s*{_Q}outerHTML{_Q}\s*\]){_ASSIGN}"), "outerHTML assignment"),
)

INNERHTML_RE = re.compile(
    rf"(?:\.\s*innerHTML|\[\s*{_Q}innerHTML{_Q}\s*\]){_ASSIGN}"
    rf"|(?:\.\s*insertAdjacentHTML|\[\s*{_Q}insertAdjacentHTML{_Q}\s*\])\s*\("
)

# ``Authorization: `Bearer ${token}` `` is fine (`${…}` is not [A-Za-z0-9_-]).
# `Authorization: 'token ghp_abc12345'` / ``Authorization: `Basic Zm9vOmJhcg==` ``
# are not. `[\s\S]{0,40}?` (NOT `[^\n]`) so a value formatted onto the next line
# — `Authorization:\n  'Basic …'` — is still caught, bounded to 40 chars so it
# cannot run away.
AUTH_LITERAL_RE = re.compile(
    rf"""Authorization[\s\S]{{0,40}}?{_Q}\s*(?:Bearer|token|Basic)\s+[A-Za-z0-9_\-+/=]{{8,}}""",
    re.IGNORECASE,
)

HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
SCRIPT_RE = re.compile(r"<script\b[^>]*>([\s\S]*?)</script>", re.IGNORECASE)


def iter_files() -> tuple[list[Path], dict[str, int]]:
    """Return (files, per-pattern match counts). The counts let main() prove
    every declared category actually contributed files."""
    seen: dict[str, Path] = {}
    per_pattern: dict[str, int] = {}
    for pattern in SCAN_GLOBS:
        matched = 0
        for path in ROOT.glob(pattern):
            if not path.is_file():
                continue
            if path.name.endswith(".min.js"):
                continue  # generated artifact; its source is scanned instead
            seen[path.relative_to(ROOT).as_posix()] = path
            matched += 1
        per_pattern[pattern] = matched
    return [seen[key] for key in sorted(seen)], per_pattern


def code_of(path: Path) -> str:
    """Return the file's executable JS with comments stripped (strings intact).

    Strings are intentionally KEPT: a bracket-notation sink writes the property
    name AS a string literal (`el['innerHTML'] = x`, `document['write'](...)`),
    so blanking string bodies would erase the very thing that makes those a
    sink — a false negative, which is unacceptable for a security check. The
    cost is the documented false-positive noted in the module docstring.
    """
    src = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".js":
        return js_minify(src)
    # HTML: drop markup comments, then keep only <script> bodies (all the sinks
    # we care about live in JS), each run through the comment-aware minifier.
    src = HTML_COMMENT_RE.sub(" ", src)
    return "\n".join(js_minify(m.group(1)) for m in SCRIPT_RE.finditer(src))


def main() -> int:
    errors: list[str] = []
    scanned: set[str] = set()
    innerhtml_sites = 0

    files, per_pattern = iter_files()
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            code = code_of(path)
        except Exception as exc:  # noqa: BLE001 — surface, never silently skip
            errors.append(f"{rel}: could not extract code for scanning ({exc})")
            continue
        scanned.add(rel)

        for pattern, label in FORBIDDEN:
            if pattern.search(code):
                errors.append(f"{rel}: forbidden construct {label} — never allowed on the security surface")

        hits = len(INNERHTML_RE.findall(code))
        if hits:
            if rel not in INNERHTML_ALLOWLIST:
                errors.append(
                    f"{rel}: {hits} innerHTML/insertAdjacentHTML site(s) in a file that is NOT on the "
                    f"reviewed allowlist. Audit that every interpolated value is escaped, then add the "
                    f"file to INNERHTML_ALLOWLIST in {Path(__file__).name}."
                )
            else:
                innerhtml_sites += hits

        if AUTH_LITERAL_RE.search(code):
            errors.append(f"{rel}: Authorization header appears to embed a literal credential")

    # Guard against a broken glob silently scanning nothing (vacuous green).
    for pattern, matched in per_pattern.items():
        if matched == 0:
            errors.append(f"SCAN_GLOBS pattern {pattern!r} matched no files — that whole category is unaudited")
    for required in REQUIRED_SCANNED:
        if required not in scanned:
            errors.append(f"{required} was not scanned — SCAN_GLOBS is broken, audit coverage is not what it claims")

    if errors:
        print("[FAIL] Dangerous-sink audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1

    print(
        f"[OK] Dangerous-sink audit passed "
        f"({len(scanned)} files scanned; 0 eval/Function/document.write/outerHTML; "
        f"{innerhtml_sites} innerHTML sites, all in allowlisted files)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
