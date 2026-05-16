from __future__ import annotations

import io
import re
import sys
from pathlib import Path

# Force UTF-8 stdout so error messages containing non-cp950 chars (≥, →,
# CJK garbled bytes from broken HTML attrs, etc.) print without crashing
# on Windows CI runners that default to cp950.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", ".next", "out", "dist"}


SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
ID_RE = re.compile(r'\bid="([^"]+)"')
HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>([\s\S]*?)</h\1>", re.I)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
BUTTON_RE = re.compile(r"<button\b([^>]*)>([\s\S]*?)</button>", re.I)
FORM_CONTROL_RE = re.compile(r"<(input|select|textarea)\b[^>]*>", re.I)
LABEL_FOR_RE = re.compile(r'<label\b[^>]*\bfor="([^"]+)"', re.I)
TARGET_BLANK_RE = re.compile(r"<a\b[^>]*target=\"_blank\"[^>]*>", re.I)
SKIP_LINK_RE = re.compile(r'<a\b[^>]*class="[^"]*\bskip-to-main\b[^"]*"[^>]*href="#([^"]+)"', re.I)
BAD_BILINGUAL_ATTR_RE = re.compile(r'data-(?:zh|en)="[^"]*<(?:span|strong)[^>]*(?:data-zh|data-en)="', re.I)
BROKEN_SVG_CASE_RE = re.compile(r"</(?:lineargradient|radialgradient|clippath)>")
PRELOAD_BLOG_SHARED_RE = re.compile(r'<link\s+rel="(?:modulepreload|preload)"(?:\s+as="script")?\s+href="[^"]*blog-shared(?:\.min)?\.js', re.I)


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html)).strip()


def has_attr(tag: str, name: str) -> bool:
    return re.search(rf"\b{name}\s*=", tag, re.I) is not None


def main() -> int:
    errors: list[str] = []

    for path in iter_html_files():
        rel = path.relative_to(ROOT).as_posix()
        raw = path.read_text(encoding="utf-8")
        dom = SCRIPT_STYLE_RE.sub("", raw)

        for bad in BAD_BILINGUAL_ATTR_RE.finditer(dom):
            snippet = re.sub(r"\s+", " ", dom[bad.start():bad.start() + 160])
            errors.append(f"{rel}: nested data-zh/data-en inside bilingual attr breaks HTML parsing: {snippet}")

        for bad in BROKEN_SVG_CASE_RE.finditer(dom):
            errors.append(f"{rel}: SVG tag casing was rewritten by HTML parsing: {bad.group(0)}")

        if PRELOAD_BLOG_SHARED_RE.search(dom):
            errors.append(f"{rel}: large deferred blog-shared.js should not be head-preloaded before first paint")

        ids = ID_RE.findall(dom)
        seen: set[str] = set()
        dupes: set[str] = set()
        for item in ids:
            if item in seen:
                dupes.add(item)
            seen.add(item)
        for item in sorted(dupes):
            errors.append(f"{rel}: duplicate id #{item}")

        for skip in SKIP_LINK_RE.finditer(dom):
            target = skip.group(1)
            if target not in seen:
                errors.append(f"{rel}: skip link target #{target} is missing")

        prev_level = 0
        for heading in HEADING_RE.finditer(dom):
            level = int(heading.group(1))
            text = plain_text(heading.group(2))[:80]
            if prev_level and level > prev_level + 1:
                errors.append(f"{rel}: heading jump h{prev_level}->h{level}: {text}")
            prev_level = level

        for image in IMG_RE.finditer(dom):
            tag = image.group(0)
            if not has_attr(tag, "width") or not has_attr(tag, "height"):
                errors.append(f"{rel}: image missing width/height: {tag[:140]}")
            if 'loading="eager"' in tag and 'fetchpriority="high"' not in tag:
                errors.append(f"{rel}: eager image missing fetchpriority=high: {tag[:140]}")

        for button in BUTTON_RE.finditer(dom):
            attrs, body = button.groups()
            name = plain_text(body)
            if not name and not re.search(r"\b(aria-label|aria-labelledby|title)\s*=", attrs, re.I):
                errors.append(f"{rel}: button has no accessible name: <button{attrs[:120]}>")

        labels = set(LABEL_FOR_RE.findall(dom))
        for control in FORM_CONTROL_RE.finditer(dom):
            tag = control.group(0)
            if re.search(r'\btype="(?:hidden|file|color)"', tag, re.I):
                continue
            if re.search(r"\b(aria-label|aria-labelledby|title)\s*=", tag, re.I):
                continue
            id_match = re.search(r'\bid="([^"]+)"', tag, re.I)
            if id_match and id_match.group(1) in labels:
                continue
            errors.append(f"{rel}: form control has no accessible name: {tag[:140]}")

        for anchor in TARGET_BLANK_RE.finditer(dom):
            tag = anchor.group(0)
            if not re.search(r'rel="[^"]*\bnoopener\b', tag, re.I):
                errors.append(f"{rel}: target=_blank missing rel=noopener: {tag[:140]}")

    if errors:
        print("[FAIL] Static accessibility audit found issues:")
        for error in errors[:200]:
            print(" - " + error)
        if len(errors) > 200:
            print(f" ... {len(errors) - 200} more")
        return 1

    print("[OK] Static accessibility audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
