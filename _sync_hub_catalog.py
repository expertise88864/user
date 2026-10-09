"""Keep public article cards in raw HTML; JavaScript only enhances navigation.

Preserve artwork and explicit editorial overrides while reconciling metadata
with the catalog. Remove unpublished cards from hubs.
Run before EN generation. --check verifies both language mirrors without writes.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent
HUBS = {"index.html": "dn-article-list", "blog/index.html": "articleList"}
OVERRIDE_FIELDS = {"title", "title_en", "tag", "tag_en"}


def load_overrides(catalog: list[dict], root: Path = ROOT) -> dict:
    overrides = json.loads((root / "_hub_card_overrides.json").read_text(encoding="utf-8"))
    slugs = {item["slug"] for item in catalog}
    if not isinstance(overrides, dict) or set(overrides) - set(HUBS):
        raise ValueError("Invalid card override hubs")
    for hub, cards in overrides.items():
        if not isinstance(cards, dict) or set(cards) - slugs:
            raise ValueError(f"Unknown card override slug: {hub}")
        for slug, fields in cards.items():
            if not isinstance(fields, dict) or set(fields) - OVERRIDE_FIELDS:
                raise ValueError(f"Invalid card override fields: {hub}/{slug}")
            if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                raise ValueError(f"Empty card override: {hub}/{slug}")
    return overrides


def set_attribute(tag: str, name: str, value: str) -> str:
    value = html.escape(value, quote=True)
    pattern = rf'''\s+{re.escape(name)}\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)'''
    tag = re.sub(pattern, "", tag, flags=re.I)
    return tag[:-1] + f' {name}="{value}">'


def sync_card(card: str, item: dict, overrides: dict, language: str = "zh") -> str:
    metadata = {**item, **overrides}
    opening = re.match(r"<a\b[^>]*>", card, flags=re.I)
    if not opening:
        raise ValueError(f"Missing card anchor: {item['slug']}")
    tag = set_attribute(opening[0], "data-cat", item.get("cat") or "note")
    tag = set_attribute(tag, "data-tag-en", metadata.get("tag_en") or "")
    card = tag + card[opening.end():]

    def title(match):
        tag = set_attribute(match[1], "data-zh", metadata["title"])
        tag = set_attribute(tag, "data-en", metadata["title_en"])
        tag = set_attribute(tag, "data-dn-text-only", "")
        return tag + html.escape(metadata["title_en" if language == "en" else "title"]) + match[3]

    card, count = re.subn(r"(<h[23]\b[^>]*>)([\s\S]*?)(</h[23]>)", title, card, count=1, flags=re.I)
    if count != 1:
        raise ValueError(f"Missing card title: {item['slug']}")
    if metadata.get("tag"):
        def topic(match):
            tag = set_attribute(match[1], "data-zh", metadata["tag"])
            tag = set_attribute(tag, "data-en", metadata.get("tag_en") or metadata["tag"])
            tag = set_attribute(tag, "data-dn-text-only", "")
            display = (metadata.get("tag_en") or metadata["tag"]) if language == "en" else metadata["tag"]
            return tag + html.escape(display) + match[3]
        card = re.sub(r'(<span\b[^>]*class="chip tag"[^>]*>)([\s\S]*?)(</span>)', topic, card, count=1)
    return card


def load_catalog(root: Path = ROOT) -> list[dict]:
    # Parse the trusted repository's JS literal with JS string semantics, so
    # escaped apostrophes and Unicode are not truncated by a regex field parser.
    script = """
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(process.argv[1], 'utf8');
const match = source.match(/DN\\.ARTICLES\\s*=\\s*(\\[[\\s\\S]*?\\]);/);
if (!match) throw Error('Missing DN.ARTICLES');
process.stdout.write(JSON.stringify(vm.runInNewContext('(' + match[1] + ')', {}, {timeout: 1000})));
"""
    # The reader needs only the system toolchain and locale. Inherited Node
    # preloads can execute before our VM/script, including early CMS planning
    # that runs before the disposable rebuild's separate environment exists.
    allowed = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'LANG', 'LC_ALL'}
    env = {key.upper(): value for key, value in os.environ.items() if key.upper() in allowed}
    result = subprocess.run(
        ["node", "-e", script, str(root / "blog/blog-shared.js")],
        check=True, capture_output=True, encoding="utf-8", timeout=10, env=env,
    )
    catalog = json.loads(result.stdout)
    if not isinstance(catalog, list) or not catalog:
        raise ValueError("Empty or invalid article catalog")
    seen = set()
    for item in catalog:
        slug = item.get("slug", "")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate catalog slug: {slug}")
        seen.add(slug)
        if not item.get("title") or not item.get("title_en"):
            raise ValueError(f"Missing bilingual title: {slug}")
    return catalog


class CardList(HTMLParser):
    """Locate the actual list and its direct card children, preserving bytes."""

    def __init__(self, source: str, element_id: str):
        super().__init__(convert_charrefs=True)
        self.source = source
        self.element_id = element_id
        self.lines = [0]
        for match in re.finditer("\n", source):
            self.lines.append(match.end())
        self.depth = 0
        self.start = self.end = None
        self.open_start = None
        self.card_start = None
        self.cards = []
        self.dates = {}
        self.time_text = None
        self.in_time = False
        self.feed(source)
        if self.start is None or self.end is None or self.card_start is not None:
            raise ValueError(f"Missing or malformed article list: {element_id}")

    def source_offset(self):
        row, col = self.getpos()
        return self.lines[row - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if attrs.get("id") == self.element_id:
                if self.start is not None:
                    raise ValueError(f"Duplicate list: {self.element_id}")
                self.start = self.source_offset() + len(self.get_starttag_text())
                self.open_start = self.source_offset()
                self.depth = 1
            elif self.depth:
                self.depth += 1
        if tag == "a" and self.depth == 1:
            if self.card_start is not None:
                raise ValueError("Nested article card")
            if "article-list-item" not in attrs.get("class", "").split():
                raise ValueError("Unexpected link inside article list")
            match = re.fullmatch(r"/(?:en/)?blog/([a-z0-9-]+)", attrs.get("href", ""))
            if not match:
                raise ValueError("Noncanonical article card URL")
            self.card_start = self.source_offset()
            self.slug = match[1]
            self.time_text = None
            self.in_time = False
        if tag == "time" and self.card_start is not None and self.time_text is None:
            self.time_text = []
            self.in_time = True

    def handle_data(self, data):
        if self.in_time:
            self.time_text.append(data)

    def handle_endtag(self, tag):
        if tag == "time":
            self.in_time = False
        if tag == "a" and self.card_start is not None:
            end = self.source_offset() + len("</a>")
            self.cards.append((self.slug, self.card_start, end))
            self.dates[self.slug] = "".join(self.time_text or []).strip()
            self.in_time = False
            self.card_start = None
        if tag == "div" and self.depth:
            self.depth -= 1
            if not self.depth:
                self.end = self.source_offset()


def public_catalog(catalog: list[dict], root: Path) -> list[dict]:
    published = []
    for item in catalog:
        if item.get("unpublished"):
            continue
        path = root / "blog" / (item["slug"] + ".html")
        source = path.read_text(encoding="utf-8")
        # Use parsed attributes; noindex may be beyond the first 5 KB.
        class Robots(HTMLParser):
            CDATA_CONTENT_ELEMENTS = ('script', 'style', 'textarea', 'title')

            def __init__(self):
                super().__init__()
                self.noindex = False
                self.template_depth = 0

            def handle_starttag(self, tag, attributes):
                if tag == 'template':
                    self.template_depth += 1
                if self.template_depth:
                    return
                attrs = dict(attributes)
                names = [(value or '').lower() for key, value in attributes if key == 'name']
                if tag == "meta" and set(names) & {"robots", "googlebot"}:
                    # Match search indexing: ambiguous visibility must not become public.
                    if len(names) != 1 or sum(key == 'content' for key, _ in attributes) != 1:
                        self.noindex = True
                    directives = set(re.split(r"[\s,]+", (attrs.get("content") or "").lower()))
                    self.noindex |= bool(directives & {'noindex', 'none'})

            def handle_endtag(self, tag):
                if tag == 'template' and self.template_depth:
                    self.template_depth -= 1

        robots = Robots()
        robots.feed(source)
        if not robots.noindex:
            published.append(item)
    if not published:
        raise ValueError("No public articles; refusing to empty hubs")
    return published


def render_card(item: dict) -> str:
    slug, title, english = (html.escape(item[key], quote=True) for key in ("slug", "title", "title_en"))
    category = html.escape(item.get("cat") or "note", quote=True)
    tag_en = html.escape(item.get("tag_en") or "", quote=True)
    date = html.escape(item.get("date") or "", quote=True)
    return (
        f'<a href="/blog/{slug}" class="article-list-item" data-cat="{category}" data-tag-en="{tag_en}">'
        f'<div class="al-body"><div class="al-meta"><time datetime="{date}">{date}</time></div>'
        f'<h2 data-zh="{title}" data-en="{english}" data-dn-text-only="">{title}</h2></div>'
        '<div class="al-arrow" aria-hidden="true">→</div></a>'
    )


def sync_homepage_limit(source: str) -> str:
    """Match the enhanced hub's initial limit before its deferred JS runs.

    Keep every card's markup and artwork in the HTML. Only the initial cards
    are live DOM nodes; the rest stay in an inert template until interaction.
    The full index and native All articles link remain usable without JS.

    Keep the hero rendered. The lower-section size hint reduces initial layout
    before first paint in the local diagnostic; auto remembers actual heights
    once rendered. This rule is homepage-only and must not target :first-child:
    main also contains inline style elements before its first section.
    """
    class HomeConfig(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.hubs = []
            self.head_ends = []
            self.lines = [0] + [match.end() for match in re.finditer("\n", source)]

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('id') == 'dn-hub':
                self.hubs.append(attrs)

        def handle_endtag(self, tag):
            if tag == 'head':
                row, col = self.getpos()
                self.head_ends.append(self.lines[row - 1] + col)

    config = HomeConfig()
    config.feed(source)
    if len(config.hubs) > 1:
        raise ValueError('Duplicate homepage hub')
    existing = list(re.finditer(r'<style data-home-card-limit>[\s\S]*?</style>', source))
    if len(existing) > 1:
        raise ValueError('Duplicate homepage card limit')
    templates = list(re.finditer(r'<template id="dn-home-card-rest">([\s\S]*?)</template>', source))
    if len(templates) > 1:
        raise ValueError('Duplicate remaining-home-card template')
    if templates:
        match = templates[0]
        parsed = CardList(source, 'dn-article-list')
        if not parsed.start <= match.start() < match.end() <= parsed.end:
            raise ValueError('Remaining home cards must be inside their list')
        source = source[:match.start()] + match[1] + source[match.end():]
    if not config.hubs or config.hubs[0].get('data-hub-mode') != 'homepage':
        return re.sub(r'<style data-home-card-limit>[\s\S]*?</style>', '', source)
    count = config.hubs[0].get('data-show-count', '6')
    if not re.fullmatch(r'[1-9][0-9]{0,3}', count) or len(config.head_ends) != 1:
        raise ValueError('Missing head or invalid homepage card limit')
    parsed = CardList(source, 'dn-article-list')
    if len(parsed.cards) > int(count):
        start, end = parsed.cards[int(count)][1], parsed.cards[-1][2]
        source = (source[:start] + '<template id="dn-home-card-rest">' + source[start:end] +
                  '</template>' + source[end:])
    # Retire the old fixed-six rule; the authored hub count is authoritative.
    source = re.sub(r'#dn-article-list\s*>\s*\.article-list-item:nth-child\(n\+7\)\s*\{\s*display:\s*none;\s*\}', '', source)
    config = HomeConfig()
    config.feed(source)
    existing = list(re.finditer(r'<style data-home-card-limit>[\s\S]*?</style>', source))
    rule = (f'<style data-home-card-limit>#dn-article-list>.article-list-item:'
            f'nth-of-type(n+{int(count) + 1}){{display:none}}'
            'main>section:not(.mag-hero){content-visibility:auto;contain-intrinsic-size:auto 1000px}</style>')
    if existing:
        match = existing[0]
        if match.end() > config.head_ends[0]:
            raise ValueError('Homepage card limit must be in the head')
        return source[:match.start()] + rule + source[match.end():]
    offset = config.head_ends[0]
    return source[:offset] + rule + source[offset:]


def sync_source(source: str, element_id: str, articles: list[dict], overrides: dict | None = None,
                *, order: list[str] | None = None) -> str:
    parsed = CardList(source, element_id)
    existing = set()
    wanted = {item["slug"] for item in articles}
    if order is not None and not isinstance(order, list):
        raise ValueError('Invalid public article order')
    if order and (len(order) != len(wanted) or set(order) != wanted):
        raise ValueError('Incomplete public article order')
    catalog = {item["slug"]: item for item in articles}
    overrides = overrides or {}
    removals = []
    for slug, start, end in parsed.cards:
        # Legacy hubs can contain a second minimal card for the same article.
        # Keep the first editorial card; --check still rejects duplicate output.
        if slug not in wanted or slug in existing:
            removals.append((start, end))
        else:
            existing.add(slug)
    # Reconcile metadata while retaining artwork, dates, descriptions and layout.
    replacements = [(start, end, "") for start, end in removals]
    for slug, start, end in parsed.cards:
        if (start, end) not in removals:
            card = sync_card(source[start:end], catalog[slug], overrides.get(slug, {}))
            replacements.append((start, end, card))
    additions = "".join(render_card({**item, **overrides.get(item["slug"], {})})
                        for item in articles if item["slug"] not in existing)
    updated = source[:parsed.end] + additions + source[parsed.end:]
    for start, end, card in sorted(replacements, reverse=True):
        updated = updated[:start] + card + updated[end:]
    if order or element_id == 'dn-article-list':
        # Homepage previously moved every card at parse time. Emit that order
        # directly; catalog position breaks date ties without oscillating on
        # repeated builds or relying on the previously generated DOM order.
        parsed = CardList(updated, element_id)
        # Authored cards may display dates different from the catalog. Preserve
        # their visible date ordering without rewriting published content.
        rank = {item['slug']: (parsed.dates[item['slug']] or item.get('date') or '', i)
                for i, item in enumerate(articles)}
        cards = parsed.cards
        if order:
            positions = {slug: index for index, slug in enumerate(order)}
            ordered = sorted(cards, key=lambda card: positions[card[0]])
        else:
            ordered = sorted(cards, key=lambda card: rank[card[0]], reverse=True)
        markup = [updated[start:end] for _, start, end in ordered]
        for (_, start, end), card_html in reversed(list(zip(cards, markup))):
            updated = updated[:start] + card_html + updated[end:]
    parsed = CardList(updated, element_id)
    opening = updated[parsed.open_start:parsed.start]
    opening = re.sub(r'''\s+data-dn-settings-order\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''', '', opening, flags=re.I)
    if order:
        opening = set_attribute(opening, 'data-dn-settings-order', 'custom')
    updated = updated[:parsed.open_start] + opening + updated[parsed.start:]
    if element_id == 'dn-article-list':
        updated = sync_homepage_limit(updated)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    catalog = load_catalog()
    articles = public_catalog(catalog, ROOT)
    overrides = load_overrides(catalog)
    from _site_settings_data import load_settings
    settings, _ = load_settings(ROOT)
    expected = {item["slug"] for item in articles}
    pending = []
    for relative, element_id in HUBS.items():
        path = ROOT / relative
        with path.open(encoding="utf-8", newline="") as stream:
            source = stream.read()
        updated = sync_source(source, element_id, articles, overrides.get(relative), order=settings['order'])
        pending.append((path, updated, source != updated))
        if args.check:
            if source != updated:
                raise ValueError(f"{relative}: stale public card metadata; regenerate hubs")
            for target in (path, ROOT / "en" / relative):
                target_source = target.read_text(encoding="utf-8")
                if element_id == 'dn-article-list' and sync_homepage_limit(target_source) != target_source:
                    raise ValueError(f"{target.relative_to(ROOT)}: stale homepage card limit")
                parsed = CardList(target_source, element_id)
                slugs = [slug for slug, _, _ in parsed.cards]
                if set(slugs) != expected or len(slugs) != len(expected):
                    raise ValueError(f"{target.relative_to(ROOT)}: stale public article cards")
                if 'en' in target.relative_to(ROOT).parts:
                    english_source = target.read_text(encoding="utf-8")
                    by_slug = {item["slug"]: item for item in articles}
                    for slug, start, end in parsed.cards:
                        card = english_source[start:end]
                        normalized = sync_card(card, by_slug[slug], overrides.get(relative, {}).get(slug, {}), "en")
                        # The EN generator may serialize a text '&' literally.
                        # Compare decoded markup, not equivalent entity spellings.
                        if html.unescape(card) != html.unescape(normalized):
                            raise ValueError(f"{target.relative_to(ROOT)}: stale card metadata: {slug}")
    # Validate every target before writing any of them.
    if not args.check:
        for path, updated, changed in pending:
            if changed:
                with path.open("w", encoding="utf-8", newline="") as stream:
                    stream.write(updated)
    print(f"[OK] Public hub cards: {len(expected)} articles, {'verified ZH + EN' if args.check else 'synced ZH'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
