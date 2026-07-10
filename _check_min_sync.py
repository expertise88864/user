#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assert every blog/*.js bundle's committed .min.js matches a fresh minify.

CODE_REVIEW TD-28 — the push gate is `python _run_quality.py check`, but
`_minify.py` only runs in `build` (POST_BUILD_STEPS), not in CHECK_STEPS. So
editing a bundle's source and running only `check` before pushing could ship a
STALE `.min.js`: `_check_js_syntax.py` only validates that the (old) min is
syntactically valid JS, not that it still corresponds to the source. This guard
re-runs `js_minify()` over each source and compares to the on-disk min, so
`check` alone catches a forgotten re-minify (bug class #14).

Line-ending note (see TD-34): `js_minify()` joins with '\n' and Path.read_text()
decodes CRLF→LF via universal newlines, so both sides are LF — the comparison is
unaffected by a local Windows CRLF checkout.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _minify import JS_BUNDLES, js_minify

ROOT = Path(__file__).resolve().parent


def main() -> int:
    errors: list[str] = []
    checked = 0

    # CODE_REVIEW — a `checked == len(JS_BUNDLES)` test is not a vacuity guard:
    # an empty JS_BUNDLES satisfies it (0 == 0) and the audit passes having
    # verified nothing. Assert the declared set is non-empty, and reconcile it
    # against the committed artifacts in the OTHER direction too, so a
    # `.min.js` whose bundle entry was dropped can't keep shipping unverified.
    if not JS_BUNDLES:
        print("[FAIL] _minify.JS_BUNDLES is empty — this audit would verify nothing")
        return 1
    declared = set(JS_BUNDLES)
    for min_file in sorted((ROOT / "blog").glob("*.min.js")):
        stem = min_file.name[: -len(".min.js")]
        if stem not in declared:
            errors.append(
                f"blog/{min_file.name} is committed but '{stem}' is not declared in "
                f"_minify.JS_BUNDLES — it is never regenerated nor verified"
            )

    for name in JS_BUNDLES:
        src_path = ROOT / "blog" / f"{name}.js"
        min_path = ROOT / "blog" / f"{name}.min.js"
        # CODE_REVIEW — every declared bundle must have BOTH files. Skipping a
        # missing source would let its stale .min.js keep shipping while the
        # audit passed on the remaining bundles.
        if not src_path.exists():
            errors.append(
                f"blog/{name}.js is missing but is declared in _minify.JS_BUNDLES — "
                f"a stale blog/{name}.min.js may still be deployed"
            )
            continue
        if not min_path.exists():
            errors.append(f"blog/{name}.min.js missing though blog/{name}.js exists — run: python _minify.py")
            continue
        expected = js_minify(src_path.read_text(encoding="utf-8"))
        actual = min_path.read_text(encoding="utf-8")  # universal newlines → LF, matching js_minify output
        if expected != actual:
            errors.append(
                f"blog/{name}.min.js is out of sync with blog/{name}.js "
                f"(source edited without re-minifying) — run: python _minify.py"
            )
        checked += 1

    # Vacuity guard: every declared bundle must have actually been compared.
    if not errors and checked != len(JS_BUNDLES):
        errors.append(f"only {checked}/{len(JS_BUNDLES)} declared bundles were compared — audit coverage is incomplete")

    if errors:
        print("[FAIL] minified bundle sync audit:")
        for error in errors:
            print(" - " + error)
        return 1
    print(f"[OK] minified bundle sync audit passed ({checked}/{len(JS_BUNDLES)} bundles)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
