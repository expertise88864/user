from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", ".next", "out", "dist"}
HTML_RE = re.compile(r"(<footer\b[^>]*class=\"[^\"]*\bmag-footer\b[^\"]*\"[^>]*>)(.*?)(</footer>)", re.S)
ARTICLE_CARD_RE = re.compile(
    r"(<a\b(?=[^>]*\barticle-list-item\b)[^>]*>)(.*?)(</a>)",
    re.S,
)


def iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return files


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
    if "class=" in attrs:
        return re.sub(
            r'class="([^"]*)"',
            lambda match: f'class="{match.group(1)} {class_name}"',
            attrs,
            count=1,
        )
    return f' class="{class_name}"{attrs}'


def normalize_content_headings(html: str) -> str:
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
    html = re.sub(r"</h3>(<p (?:class=\"topic-desc\"|style=))", r"</h2>\1", html)
    html = re.sub(r'(<div class="tool-toc"[^>]*>)<h3\b', r"\1<h2", html)
    html = html.replace("</h3><ul><li><a href=\"#scorad\"", "</h2><ul><li><a href=\"#scorad\"")

    html = re.sub(
        r"<h4\b([^>]*\bid=\"lt[^>]*>)(.*?)</h4>",
        r"<h3\1\2</h3>",
        html,
        flags=re.S,
    )
    html = re.sub(
        r"<h4\b([^>]*)>",
        lambda match: f"<div{with_added_class(match.group(1), 'visual-heading')}>",
        html,
    )
    html = html.replace("</h4>", "</div>")
    html = re.sub(
        r"<h5\b([^>]*)>",
        lambda match: f"<div{with_added_class(match.group(1), 'visual-heading')}>",
        html,
    )
    html = html.replace("</h5>", "</div>")

    html = html.replace('class="visual-heading" data-zh=', 'class="infographic-title" data-zh=')
    html = html.replace('class="visual-heading" style=', 'class="visual-heading" style=')
    return html


def main() -> None:
    changed = 0
    for path in iter_html_files():
        before = path.read_text(encoding="utf-8")
        after = normalize_content_headings(normalize_footer_headings(before))
        if after != before:
            path.write_text(after, encoding="utf-8", newline="")
            changed += 1
    print(f"Normalized footer heading structure in {changed} HTML files.")


if __name__ == "__main__":
    main()
