#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate llms-full.txt — concatenated clean text of every published article
for AI / LLM crawlers (Perplexity, ChatGPT, Claude, Anthropic, etc.).

The /llms.txt manifest (RFC-ish convention, Anthropic-proposed) tells AI
crawlers WHAT the site has. /llms-full.txt is the optional companion
that provides the full content in a single fetchable document — perfect
for retrieval-augmented generation and citation grounding.

Layout (markdown, UTF-8):

    # ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記
    Generated YYYY-MM-DD · NN articles

    For each article:
        ---
        ## <title>
        URL: <canonical>
        Updated: <dateModified>
        Section: <articleSection>
        Reading time: <PT##M>
        Tags: <tag, tag_en>

        <clean text from #proseZh, no markup>

Cap: each article body truncated to 6000 chars (keeps file < 1MB even
with 50+ articles). LLMs that need more depth can fetch the canonical URL.

Skips unpublished + EN mirrors (LLMs follow the canonical URL anyway).
"""
from __future__ import annotations

import datetime as dt
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
ARTICLE_BODY_CAP = 6000  # chars; keeps full file under ~1 MB

CAT_LABEL = {
    "rx": "Treatment & Therapy",
    "myth": "Myths & Facts",
    "note": "Clinical Notes",
    "research": "Research Summary",
    "product": "Products & Drugs",
}


def parse_articles() -> list[dict[str, str]]:
    src = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return []
    out: list[dict[str, str]] = []
    for entry_m in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}",
                                m.group(1)):
        e = entry_m.group(0)
        if re.search(r"\bunpublished\s*:\s*true\b", e):
            continue

        def field(name: str) -> str:
            mm = re.search(rf"\b{name}:'([^']*)'", e)
            return mm.group(1) if mm else ""

        out.append({
            "slug": entry_m.group(1),
            "title": field("title"),
            "date": field("date"),
            "cat": field("cat"),
            "tag": field("tag"),
            "tag_en": field("tag_en"),
        })
    # Sort newest first — better for LLM context windows
    return sorted(out, key=lambda a: a["date"] or "", reverse=True)


def extract_clean_body(html: str) -> str:
    """Pull text from #proseZh container (where DN.addReadingMeta also reads).

    Strips: scripts, styles, SVGs, JSON-LD, all HTML tags.
    Collapses whitespace and dedupes blank lines.
    """
    # Find proseZh with balanced-div extraction (same approach as
    # _normalize_schema._extract_prose_container).
    open_m = re.search(r'<div\b[^>]*\bid="proseZh"[^>]*>', html, re.I)
    if not open_m:
        # Fallback to <article>
        a_m = re.search(r"<article\b[^>]*>([\s\S]*?)</article>", html, re.I)
        body_html = a_m.group(1) if a_m else html
    else:
        pos = open_m.end()
        depth = 1
        div_re = re.compile(r'<(/?)div\b[^>]*>', re.I)
        end = None
        while depth > 0:
            m = div_re.search(html, pos)
            if not m:
                break
            depth += -1 if m.group(1) == '/' else 1
            pos = m.end()
            if depth == 0:
                end = m.start()
                break
        body_html = html[open_m.end():end] if end else html[open_m.end():]

    # Strip non-text elements
    body_html = re.sub(r'<script\b[\s\S]*?</script>', ' ', body_html, flags=re.I)
    body_html = re.sub(r'<style\b[\s\S]*?</style>', ' ', body_html, flags=re.I)
    body_html = re.sub(r'<svg\b[\s\S]*?</svg>', ' ', body_html, flags=re.I)
    body_html = re.sub(r'<noscript\b[\s\S]*?</noscript>', ' ', body_html, flags=re.I)
    # Replace block-level closes with newlines so paragraphs survive
    body_html = re.sub(r'</(h[1-6]|p|li|tr|td|th|details|summary|blockquote)>',
                       '\n', body_html, flags=re.I)
    # Drop remaining tags
    body_html = re.sub(r'<[^>]+>', '', body_html)
    # HTML entities
    import html as html_lib
    text = html_lib.unescape(body_html)
    # Collapse multi-space + dedupe blank lines
    lines = [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines()]
    out_lines: list[str] = []
    prev_blank = False
    for ln in lines:
        if not ln:
            if not prev_blank:
                out_lines.append('')
            prev_blank = True
        else:
            out_lines.append(ln)
            prev_blank = False
    return '\n'.join(out_lines).strip()


def extract_meta_from_html(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    m = re.search(r'"dateModified"\s*:\s*"([^"]+)"', html)
    if m:
        out["dateModified"] = m.group(1)
    m = re.search(r'"timeRequired"\s*:\s*"(PT\d+M)"', html)
    if m:
        out["timeRequired"] = m.group(1)
    return out


def build_article_section(meta: dict[str, str], path: Path) -> str:
    html = path.read_text(encoding="utf-8", errors="replace")
    extra = extract_meta_from_html(html)
    body = extract_clean_body(html)
    if len(body) > ARTICLE_BODY_CAP:
        body = body[:ARTICLE_BODY_CAP].rsplit('\n', 1)[0] + \
               '\n\n[... truncated; fetch canonical URL for full text ...]'
    lines = [
        '---',
        f'## {meta["title"]}',
        f'URL: {DOMAIN}/blog/{meta["slug"]}',
    ]
    if extra.get("dateModified"):
        lines.append(f'Updated: {extra["dateModified"]}')
    else:
        lines.append(f'Updated: {meta.get("date", "")}')
    if meta.get("cat"):
        lines.append(f'Section: {CAT_LABEL.get(meta["cat"], meta["cat"])}')
    if extra.get("timeRequired"):
        lines.append(f'Reading time: {extra["timeRequired"]}')
    tags = ", ".join(t for t in (meta.get("tag", ""), meta.get("tag_en", "")) if t)
    if tags:
        lines.append(f'Tags: {tags}')
    lines.append('')
    lines.append(body)
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    catalog = parse_articles()
    if not catalog:
        print("[llms-full] no articles found")
        return 1
    today = dt.date.today().isoformat()
    header = (
        f"# ChenDermatologist · 陳翊嘉醫師 · 皮膚科衛教筆記\n"
        f"\n"
        f"Generated {today} · {len(catalog)} articles · "
        f"by Dr. Chen Yi-Jia (R2 Dermatology, China Medical University Hospital, Taiwan)\n"
        f"\n"
        f"Bilingual zh-Hant / en. ZH source is authoritative; EN mirror is "
        f"machine-translated and provided for accessibility only.\n"
        f"\n"
        f"For citation rules and structural metadata, see "
        f"{DOMAIN}/llms.txt and individual article JSON-LD.\n"
        f"\n"
    )

    sections: list[str] = [header]
    skipped = 0
    for meta in catalog:
        fp = ROOT / "blog" / f"{meta['slug']}.html"
        if not fp.exists():
            skipped += 1
            continue
        sections.append(build_article_section(meta, fp))

    out = "\n".join(sections)
    out_path = ROOT / "llms-full.txt"
    out_path.write_text(out, encoding="utf-8")
    size_kb = len(out.encode("utf-8")) / 1024
    print(f"Wrote llms-full.txt: {len(catalog) - skipped} articles, "
          f"{size_kb:.1f} KB")
    if skipped:
        print(f"  ({skipped} skipped — file missing)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
