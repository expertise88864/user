from __future__ import annotations

import re
from html import escape, unescape
from pathlib import Path
from _html_scan import iter_tags, tag_name, attributes, attribute_spans, blank_script_style, mask_inert_regions
from _site_html import site_html_files

# CODE_REVIEW TD-53 — no forced newline on write. This repo runs
# core.autocrlf=true with no .gitattributes, so every other worktree file is
# CRLF; forcing LF here left the generated file permanently reported as
# modified after every build (measured: 6 files, byte-identical content).
# git still normalises to LF in the blob, so the DEPLOYED bytes are unchanged.
# Same decision already documented in _gen_llms_full.py.


ROOT = Path(__file__).resolve().parent
HTML_RE = re.compile(r"(<footer\b[^>]*class=\"[^\"]*\bmag-footer\b[^\"]*\"[^>]*>)(.*?)(</footer>)", re.S)
ARTICLE_CARD_RE = re.compile(
    r"(<a\b(?=[^>]*\barticle-list-item\b)[^>]*>)(.*?)(</a>)",
    re.S,
)


def iter_html_files() -> list[Path]:
    return site_html_files(ROOT)


def normalize_footer_headings(html: str) -> str:
    html = html.replace(".mag-foot-brand h3{", ".mag-foot-brand .mag-foot-brand-title{")
    html = html.replace(".mag-foot-cols h5{", ".mag-foot-cols .mag-foot-heading{")

    def repl(match: re.Match[str]) -> str:
        open_tag, body, close_tag = match.groups()
        body = re.sub(
            r"<h3\b([^>]*\bclass=\"[^\"]*\bmag-foot-brand-title\b[^\"]*\"[^>]*)>",
            r"<div\1>",
            body,
        )
        body = body.replace("</h3><p", "</div><p")
        body = re.sub(
            r"<h5\b([^>]*)>",
            r'<div class="mag-foot-heading"\1>',
            body,
        )
        body = body.replace("</h5>", "</div>")
        return f"{open_tag}{body}{close_tag}"

    return HTML_RE.sub(repl, html)


def with_added_class(attrs: str, class_name: str) -> str:
    prefix = '<x'
    span = attribute_spans(prefix + attrs + '>').get('class')
    if span is None:
        return f' class="{class_name}"{attrs}'
    start, end, raw_value, _ = span
    value = unescape(raw_value)
    if class_name in re.split(r'[\t\n\f\r ]+', value):
        return attrs
    replacement = 'class="' + escape((value + ' ' + class_name).strip(' \t\n\f\r'), quote=True) + '"'
    return attrs[:start - len(prefix)] + replacement + attrs[end - len(prefix):]


def normalize_content_headings(html: str) -> str:
    tags = list(iter_tags(mask_inert_regions(blank_script_style(html))))
    if any(tag_name(tag) == 'article' and not tag.startswith('</') for _, tag in tags):
        for offset, tag in tags:
            if tag_name(tag) != 'h1' or tag.startswith('</') or not tag.endswith('>'):
                continue
            if 'dn-article-title' not in re.split(r'[\t\n\f\r ]+', unescape(attributes(tag).get('class', ''))):
                attrs = tag[len('<h1'):-1]
                replacement = '<h1' + with_added_class(attrs, 'dn-article-title') + '>'
                html = html[:offset] + replacement + html[offset + len(tag):]
            break
    replacements = {
        ".infographic h4{": ".infographic .infographic-title{",
        ".toc h4{": ".toc .toc-title{",
        ".compare-cell h5{": ".compare-cell .compare-title{",
        ".compare-cell.bad h5{": ".compare-cell.bad .compare-title{",
        ".compare-cell.good h5{": ".compare-cell.good .compare-title{",
        ".type-cell h5{": ".type-cell .type-title{",
        ".article-list-item h3{": ".article-list-item h2{",
        ".al-body h3{": ".al-body h2{",
        ".article-list-item .al-body h3{": ".article-list-item .al-body h2{",
        ".mag-card-body h3{": ".mag-card-body h2{",
        ".topic-card h3{": ".topic-card h2{",
        ".tool-toc h3{": ".tool-toc h2{",
    }
    for before, after in replacements.items():
        html = html.replace(before, after)

    def article_card_repl(match: re.Match[str]) -> str:
        open_tag, body, close_tag = match.groups()
        body = re.sub(r"<h3\b([^>]*)>", r"<h2\1>", body)
        body = body.replace("</h3>", "</h2>")
        return f"{open_tag}{body}{close_tag}"

    html = ARTICLE_CARD_RE.sub(article_card_repl, html)

    html = re.sub(r'(<div class="mag-card-body"[^>]*>.*?)<h3\b', r"\1<h2", html, flags=re.S)
    html = html.replace("</h3><div class=\"mag-card-meta\"", "</h2><div class=\"mag-card-meta\"")
    html = re.sub(r'(<div class="topic-card"[^>]*>)<h3\b', r"\1<h2", html)
    # Only match topic-desc paragraph; the previous |style= alternative was
    # too broad and mangled regular articles (e.g. laser-dermatology had
    # <h3>痣(melanocytic nevus)</h3><p style="..."> rewritten to </h2>,
    # leaving a <h3>...</h2> mismatch the HTML validator failed on).
    html = re.sub(r'</h3>(<p class="topic-desc")', r"</h2>\1", html)
    html = re.sub(r'(<div class="tool-toc"[^>]*>)<h3\b', r"\1<h2", html)
    html = html.replace("</h3><ul><li><a href=\"#scorad\"", "</h2><ul><li><a href=\"#scorad\"")

    # Pair real heading tags without rewriting quoted or inert HTML examples.
    open_headings = {'h4': [], 'h5': []}
    edits = []
    for offset, tag in iter_tags(mask_inert_regions(blank_script_style(html))):
        name = tag_name(tag)
        if name not in open_headings or not tag.endswith('>'):
            continue
        if tag.startswith('</'):
            if not open_headings[name]:
                continue
            replacement = '</' + open_headings[name].pop() + '>'
        else:
            attrs = tag[3:-1]
            target = 'h3' if name == 'h4' and attributes(tag).get('id', '').startswith('lt') else 'div'
            if target == 'div':
                attrs = with_added_class(attrs, 'visual-heading')
            replacement = '<' + target + attrs + '>'
            open_headings[name].append(target)
        edits.append((offset, offset + len(tag), replacement))
    for start, stop, replacement in reversed(edits):
        html = html[:start] + replacement + html[stop:]

    html = html.replace('class="visual-heading" data-zh=', 'class="infographic-title" data-zh=')
    # CODE_REVIEW TD-59 — a second replace() here mapped
    # 'class="visual-heading" style=' onto itself: a literal no-op. Removed.
    return html


def main() -> None:
    changed = 0
    for path in iter_html_files():
        before = path.read_text(encoding="utf-8")
        after = normalize_content_headings(normalize_footer_headings(before))
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed += 1
    print(f"Normalized footer heading structure in {changed} HTML files.")


if __name__ == "__main__":
    main()
