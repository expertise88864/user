from __future__ import annotations

import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit


ROOT = Path(__file__).resolve().parent
ID_RE = re.compile(r"\s(?:id|name)=([\"'])(.*?)\1", re.IGNORECASE)
VERCEL_RUNTIME_PREFIXES = ("/_vercel/",)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name.lower() in {"href", "src"} and value:
                self.links.append(value)


def html_files() -> list[Path]:
    ignored_parts = {".git", "node_modules", ".lighthouseci"}
    return [
        path
        for path in ROOT.rglob("*.html")
        if not any(part in ignored_parts for part in path.relative_to(ROOT).parts)
    ]


def page_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel[: -len(".html")]


def page_path(url_path: str) -> Path | None:
    if url_path == "/":
        return ROOT / "index.html"
    clean = url_path.strip("/")
    candidates = [
        ROOT / clean,
        ROOT / f"{clean}.html",
        ROOT / clean / "index.html",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def is_template_or_unsupported(raw: str) -> bool:
    if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:", "blob:")):
        return True
    if raw.startswith(VERCEL_RUNTIME_PREFIXES):
        return True
    if raw.startswith("//"):
        return True
    if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.IGNORECASE):
        return True
    return any(token in raw for token in ("${", "{{", "}}", "`", "\" +", "' +"))


def anchors_for(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        text = path.read_text(encoding="utf-8", errors="replace")
        cache[path] = {unescape(match.group(2)) for match in ID_RE.finditer(text)}
    return cache[path]


def main() -> int:
    errors: list[str] = []
    files = html_files()
    pages = {page_url(path): path for path in files}
    anchor_cache: dict[Path, set[str]] = {}

    for source in files:
        source_url = page_url(source)
        text = source.read_text(encoding="utf-8", errors="replace")
        parser = LinkParser()
        parser.feed(text)
        for link in parser.links:
            raw = unescape(link).strip()
            if is_template_or_unsupported(raw):
                continue

            resolved = urljoin(source_url, raw)
            split = urlsplit(resolved)
            if split.scheme or split.netloc:
                continue
            target_path_raw, fragment = urldefrag(split.path or source_url)
            target_path_raw = "/" + target_path_raw.lstrip("/")
            if target_path_raw != "/" and target_path_raw.endswith("/"):
                target_path_raw = target_path_raw.rstrip("/")

            target_file = None
            if target_path_raw in pages:
                target_file = pages[target_path_raw]
            else:
                target_file = page_path(target_path_raw)

            if target_file is None:
                rel_asset = ROOT / target_path_raw.lstrip("/")
                if rel_asset.exists() and rel_asset.is_file():
                    continue
                errors.append(f"{source.relative_to(ROOT).as_posix()}: broken internal link {raw!r}")
                continue

            if fragment and target_file.suffix == ".html" and fragment not in anchors_for(target_file, anchor_cache):
                errors.append(
                    f"{source.relative_to(ROOT).as_posix()}: missing anchor {raw!r} -> "
                    f"{target_file.relative_to(ROOT).as_posix()}#{fragment}"
                )

    if errors:
        print("[FAIL] Internal link audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print(f"[OK] Internal link audit passed ({len(files)} HTML files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
