#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Catch unbalanced HTML tags before CI does.

GH Actions html5validator catches `Unclosed element "section"` / `Stray end
tag "div"` style errors, but it requires a JRE locally. This Python check
uses html.parser to walk every HTML file and verify that block-level tags
(article, section, main, header, footer, nav, aside) are balanced and
properly nested.

False-positive guard: the check skips `<script>` and `<style>` content,
voids tags that don't need closing, and tolerates minor flow content
mismatches (em, span, etc.).
"""
from __future__ import annotations

import io
import sys
from html.parser import HTMLParser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}

# Tags we strictly track — block-level structural tags where mismatch
# definitely breaks the page. Mismatch in <p>/<span>/<em>/<strong>
# rarely shows visually so we skip those.
# CODE_REVIEW TD-54 — `div` was missing even though the failure message told
# the reader to "ensure <section>/<div>/… are balanced", so the single most
# common container in this repo was never checked (an unbalanced <div> passed
# silently; see the negative test). Added together with ul/ol/table, all of
# which have REQUIRED end tags in HTML5. Deliberately still excluded:
# p, li, tr, td, th, tbody, thead — HTML5 lets their end tags be omitted, so
# tracking them would reject valid markup.
TRACKED_TAGS = {"article", "section", "main", "header", "footer",
                "nav", "aside", "html", "body",
                "div", "ul", "ol", "table"}

# Tags that are self-closing / void per HTML5 (don't expect close tag)
VOID_TAGS = {"br", "hr", "img", "input", "link", "meta", "area",
             "base", "col", "embed", "param", "source", "track", "wbr"}


class TagBalanceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack: list[tuple[str, tuple[int, int]]] = []
        self.errors: list[str] = []
        # When True, ignore content (we're inside <script> or <style>)
        self._in_raw = False
        self._raw_tag = None

    def handle_starttag(self, tag, attrs):
        if self._in_raw:
            return
        if tag in ("script", "style"):
            self._in_raw = True
            self._raw_tag = tag
            return
        if tag in VOID_TAGS:
            return
        if tag in TRACKED_TAGS:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if self._in_raw:
            if tag == self._raw_tag:
                self._in_raw = False
                self._raw_tag = None
            return
        if tag not in TRACKED_TAGS:
            return
        if not self.stack:
            line, col = self.getpos()
            self.errors.append(
                f"{line}:{col+1}: stray </{tag}> with no matching open"
            )
            return
        # Find nearest matching open in stack (may close intermediate
        # tracked tags implicitly — which is invalid for our purposes)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if i != len(self.stack) - 1:
                    # Closing a tag while others remain open inside
                    inner_open = self.stack[i+1]
                    line, col = self.getpos()
                    self.errors.append(
                        f"{line}:{col+1}: </{tag}> closes element opened at "
                        f"line {self.stack[i][1][0]} but inner <{inner_open[0]}> "
                        f"(opened at line {inner_open[1][0]}) still open"
                    )
                # Pop everything from i to end (recover)
                self.stack = self.stack[:i]
                return
        # No match found — stray close
        line, col = self.getpos()
        self.errors.append(
            f"{line}:{col+1}: stray </{tag}> with no matching open in stack "
            f"{[t[0] for t in self.stack]}"
        )


def check_file(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    parser = TagBalanceParser()
    try:
        parser.feed(text)
        parser.close()
    except Exception as e:
        return [f"{rel}: parser error: {e}"]
    errs = [f"{rel}:{e}" for e in parser.errors]
    # Anything left in stack after parse = unclosed
    for tag, (line, col) in parser.stack:
        if tag in ("html", "body"):
            continue  # html / body sometimes left open in fragments
        errs.append(f"{rel}:{line}:{col+1}: unclosed <{tag}> never closed")
    return errs


# CODE_REVIEW TD-54 — anti-vacuity floor. The old pass message reported no
# count at all, so if the glob or the skip list ever stopped matching, this
# audit would print exactly the same "[OK]" line while checking nothing.
MIN_FILES_SCANNED = 100


def main() -> int:
    total = 0
    err_files = 0
    scanned = 0
    for path in sorted(ROOT.glob("**/*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        scanned += 1
        errs = check_file(path)
        if errs:
            err_files += 1
            for e in errs:
                print(f"  {e}")
                total += 1
    if scanned < MIN_FILES_SCANNED:
        print(f"  only {scanned} HTML file(s) scanned (expected >= {MIN_FILES_SCANNED}) "
              f"— file discovery is broken, so a pass here would mean nothing")
        total += 1
    if total:
        print(f"\n[FAIL] HTML balance audit: {total} issue(s) in {err_files} file(s).")
        print("Fix: ensure " + "/".join(f"<{t}>" for t in sorted(TRACKED_TAGS))
              + " tags are balanced + properly nested.")
        return 1
    print(f"[OK] HTML balance audit passed "
          f"({scanned} files, {len(TRACKED_TAGS)} tracked block tags balanced)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
