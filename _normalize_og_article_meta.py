#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject rich OpenGraph + Twitter card metadata into every blog article.

This is one of the biggest single-action wins for off-Google CTR:

  - Facebook / LinkedIn / Discord / Slack render every shared link as
    a richer card when article:* properties are present (author byline,
    published / modified dates, section, tag chips).
  - Twitter renders custom label fields (label1/data1, label2/data2)
    underneath the title — perfect for "Reading time: X min" or
    "Author: Dr. Chen".
  - Google Discover requires og:image:width + og:image:height to
    classify the image as eligible for the large card variant.

Reads DN.ARTICLES (slug -> date, cat, tag, tag_en) and JSON-LD
(timeRequired, dateModified) to populate every field automatically.

Idempotent: replaces existing dn-og-extras block on re-run.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

sys.path.insert(0, str(ROOT))
from _normalize_social_images import image_size  # noqa: E402
AUTHOR_URL = f"{DOMAIN}/about"
# CODE_REVIEW TD-72 — this was a third spelling of the same person ("陳翊嘉醫師",
# no space) sitting in twitter:data2 while the JSON-LD graph carried two others.
# Imported rather than re-typed so there is one place the author's name exists.
from _normalize_schema import PHYSICIAN_NAME as AUTHOR_NAME  # noqa: E402

# Map cat -> human-readable section label (mirrors _normalize_schema.py).
CAT_TO_SECTION = {
    "rx": "Treatment & Therapy",
    "myth": "Myths & Facts",
    "note": "Clinical Notes",
    "research": "Research Summary",
    "product": "Products & Drugs",
}


def parse_articles() -> dict[str, dict[str, str]]:
    src = (ROOT / "blog" / "blog-shared.js").read_text(encoding="utf-8")
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return {}
    out: dict[str, dict[str, str]] = {}
    for entry_m in re.finditer(r"\{[^{}]*?slug:'([a-z0-9-]+)'[^{}]*?\}", m.group(1)):
        e = entry_m.group(0)
        slug = entry_m.group(1)

        def field(name: str) -> str:
            mm = re.search(rf"\b{name}:'([^']*)'", e)
            return mm.group(1) if mm else ""

        out[slug] = {
            "date": field("date"),
            "cat": field("cat"),
            "tag": field("tag"),
            "tag_en": field("tag_en"),
            "title": field("title"),
        }
    return out


def extract_jsonld_value(src: str, field: str) -> str:
    m = re.search(rf'"{field}":"([^"]+)"', src)
    return m.group(1) if m else ""


def build_meta_block(slug: str, meta_record: dict[str, str], src: str) -> str:
    """Build the OG / Twitter / article:* meta block for one article."""
    published = meta_record.get("date") or extract_jsonld_value(src, "datePublished")
    # ISO 8601 with timezone — Facebook prefers full ISO. Day precision is fine.
    if published and "T" not in published:
        published_iso = f"{published}T00:00:00+08:00"
    else:
        published_iso = published or ""

    modified_raw = extract_jsonld_value(src, "dateModified") or published
    if modified_raw and "T" not in modified_raw:
        modified_iso = f"{modified_raw}T00:00:00+08:00"
    else:
        modified_iso = modified_raw or published_iso

    section_label = CAT_TO_SECTION.get(meta_record.get("cat", ""), "")
    tag_zh = meta_record.get("tag", "")
    tag_en = meta_record.get("tag_en", "")

    # Read time from existing JSON-LD (set by _normalize_schema.compute_metrics).
    time_m = re.search(r'"timeRequired":"PT(\d+)M"', src)
    minutes = int(time_m.group(1)) if time_m else 0

    # OG image dimensions — all api/og + assets/og are 1200x630 (standard).
    # CODE_REVIEW SEO-4 — these were hardcoded "1200"/"630", which happened to
    # be right only because every card is that size. Read from the file the
    # page actually points at, so a differently-sized share image cannot ship
    # with dimensions that quietly lie about it.
    og_url = ""
    og_m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', src, re.I)
    if og_m:
        og_url = og_m.group(1)
    size = None
    if og_url.startswith(DOMAIN + "/"):
        size = image_size(ROOT / og_url[len(DOMAIN) + 1:].split("?")[0])
    img_w, img_h = (str(size[0]), str(size[1])) if size else ("1200", "630")

    # OG image alt: same as title (already cleaned upstream).
    title = meta_record.get("title", "").strip()
    # If no title from DN.ARTICLES (shouldn't happen), fall back to <title>.
    if not title:
        t_m = re.search(r"<title>([^<]+)</title>", src)
        if t_m:
            title = t_m.group(1).split("|")[0].strip()
    img_alt = title or slug

    lines = ['<!-- dn-og-extras:start -->']
    if published_iso:
        lines.append(f'<meta property="article:published_time" content="{published_iso}" />')
    if modified_iso:
        lines.append(f'<meta property="article:modified_time" content="{modified_iso}" />')
    lines.append(f'<meta property="article:author" content="{AUTHOR_URL}" />')
    if section_label:
        lines.append(f'<meta property="article:section" content="{section_label}" />')
    if tag_zh:
        lines.append(f'<meta property="article:tag" content="{tag_zh}" />')
    if tag_en and tag_en != tag_zh:
        lines.append(f'<meta property="article:tag" content="{tag_en}" />')
    lines.append(f'<meta property="og:image:width" content="{img_w}" />')
    lines.append(f'<meta property="og:image:height" content="{img_h}" />')
    lines.append(f'<meta property="og:image:alt" content="{_attr_escape(img_alt)}" />')
    # Twitter label1/data1 = reading time, label2/data2 = author byline.
    # Renders as two compact rows under the card title on x.com / share previews.
    if minutes:
        lines.append('<meta name="twitter:label1" content="Reading time" />')
        lines.append(f'<meta name="twitter:data1" content="{minutes} min" />')
    lines.append('<meta name="twitter:label2" content="Written by" />')
    lines.append(f'<meta name="twitter:data2" content="{AUTHOR_NAME}" />')
    lines.append(f'<meta name="twitter:image:alt" content="{_attr_escape(img_alt)}" />')
    # CODE_REVIEW SEO-4 — twitter:image belongs in this block, not next to
    # og:image. 13 articles had none, and inserting it after og:image did not
    # stick: ORPHAN_RE below strips any article:/og:image:/twitter: meta that
    # follows the end marker, so each build removed what the previous one had
    # added and the two normalizers oscillated. The tag that owns the
    # twitter:* family for articles is this one.
    if og_url:
        lines.append(f'<meta name="twitter:image" content="{_attr_escape(og_url)}" />')
    lines.append('<!-- dn-og-extras:end -->')
    return "".join(lines)


def _attr_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace('"', "&quot;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


BLOCK_RE = re.compile(
    r"<!-- dn-og-extras:start -->[\s\S]*?<!-- dn-og-extras:end -->",
    re.IGNORECASE,
)
# 2026-05-25 — also strip ORPHAN duplicate <meta property="article:|og:|name=
# "twitter:"> tags that appear right after dn-og-extras:end. A prior version
# of this injector (or a different script) appended a second meta block
# without start/end markers, so BLOCK_RE alone couldn't catch the dup. This
# regex strips a contiguous run of orphan metas immediately following the
# end-marker so re-runs converge to a single block.
# CODE_REVIEW TD-51 — the `[^"]+` suffix used to sit INSIDE the alternation,
# attached to `twitter:` only. So `article:` and `og:image:` each had to be
# followed immediately by the closing quote, which no real tag is
# (`article:tag`, `og:image:width`, …) — two of the three branches could never
# match, and the dedup this regex was added for only ever worked for
# `twitter:*`. Hoisted out so all three branches take a suffix.
ORPHAN_RUN_RE = re.compile(
    r'(<!-- dn-og-extras:end -->)'
    r'(\s*(?:<meta\s+(?:property|name)="(?:article:|og:image:|twitter:)[^"]+"\s+content="[^"]*"\s*/?>)+)',
    re.IGNORECASE,
)
TWITTER_IMAGE_TAG_RE = re.compile(
    r'\s*<meta\s+name="twitter:image"\s+content="[^"]*"\s*/?>',
    re.IGNORECASE,
)
OG_IMAGE_TAG_RE = re.compile(
    r'<meta\s+property="og:image"\s+content="[^"]*"\s*/?>',
    re.IGNORECASE,
)


def inject(path: Path, catalog: dict[str, dict[str, str]]) -> bool:
    original = path.read_text(encoding="utf-8")
    slug = path.stem
    # CODE_REVIEW TD-51 — DN.ARTICLES membership is a BLOG-LISTING decision,
    # not an "is this an article" test. isotretinoin-clinical and
    # topical-acids-clinical (plus their EN mirrors) are indexable, sitemapped
    # and internally linked, yet sat outside the catalog and so silently lost
    # every article:* / og:image:width|height tag — exactly the Discover
    # large-card eligibility this normalizer exists to grant. build_meta_block
    # already falls back to JSON-LD datePublished/dateModified and <title>, and
    # emits section/tag lines only when it has them, so an empty record is safe.
    record = catalog.get(slug, {})
    block = build_meta_block(slug, record, original)

    # Strip orphan duplicate metas that follow end-marker (legacy artifacts).
    src = ORPHAN_RUN_RE.sub(r'\1', original)
    # Strip any prior injection (current-format block).
    cleaned = BLOCK_RE.sub("", src)
    # CODE_REVIEW SEO-5 round 3 — this block now emits twitter:image, and 44
    # articles already carried a standalone one elsewhere in <head>, so they
    # ended up with TWO. They agree today, which is exactly why it would go
    # unnoticed until they stopped agreeing and a crawler picked the stale one.
    # ORPHAN_RUN_RE only reaches tags immediately after the end marker, so the
    # standalone copies are removed here — the block below is the single owner.
    cleaned = TWITTER_IMAGE_TAG_RE.sub("", cleaned)
    # Insert right after the existing og:image meta tag for visual grouping.
    og_m = OG_IMAGE_TAG_RE.search(cleaned)
    if not og_m:
        return False
    new = cleaned[:og_m.end()] + block + cleaned[og_m.end():]
    # CODE_REVIEW TD-51 — compare against the ORIGINAL bytes, not the
    # orphan-stripped copy. `src` was reassigned above, so when the current
    # block was already correct the comparison came out equal and the orphan
    # removal was thrown away unwritten — i.e. the 2026-05-25 dedup fix could
    # only ever take effect on a run that ALSO had to rewrite the block.
    if new == original:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    catalog = parse_articles()
    if not catalog:
        print("[og-extras] DN.ARTICLES catalog empty — skipping")
        return 0
    changed = 0
    targets: list[Path] = []
    for d in (ROOT / "blog", ROOT / "en" / "blog"):
        if d.exists():
            for fp in sorted(d.glob("*.html")):
                if fp.name in {"index.html", "topics.html"}:
                    continue
                targets.append(fp)
    for fp in targets:
        try:
            if inject(fp, catalog):
                changed += 1
        except Exception as exc:
            print(f"[!] {fp.relative_to(ROOT)} failed: {exc}")
    print(f"Injected dn-og-extras into {changed} of {len(targets)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
