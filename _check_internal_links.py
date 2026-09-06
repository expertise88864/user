from __future__ import annotations

import re
import json
import subprocess
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


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
    if not raw or raw.startswith(("mailto:", "tel:", "javascript:", "data:", "blob:")):
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
        class Anchors(HTMLParser):
            def handle_starttag(self, tag, attrs):
                found.update(value for key,value in attrs if (key == 'id' or (tag == 'a' and key == 'name')) and value)
        found: set[str] = set()
        Anchors(convert_charrefs=True).feed(text)
        cache[path] = found
    return cache[path]


def calculator_anchors() -> dict[str, str]:
    """Model only the calculator actually auto-injected on each article.

    No blanket dn-* exemption: derive IDs and the first-choice mapping from
    the production JS. Browser coverage checks these live DOM targets too.
    """
    script = r"""
const fs=require('node:fs'),vm=require('node:vm');
const context={window:{}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context,{timeout:1000});
const dn=context.window.DN, ids={};
const shared=fs.readFileSync(process.argv[2],'utf8');
const registry=shared.match(/var CALC_FN\s*=\s*(\{[\s\S]*?\});/);
if(!registry) throw Error('Missing calculator dispatch registry');
const functions=vm.runInNewContext('('+registry[1]+')',{DN:dn},{timeout:1000});
for(const [name,fn] of Object.entries(functions)) {
  if(typeof fn!=='function') throw Error('Missing calculator '+name);
  const match=String(fn).match(/\bid:\s*'(dn-[a-z0-9-]+)'|\bid="(dn-[a-z0-9-]+)"/);
  if(!match) throw Error('Missing calculator ID '+name);
  ids[name]=match[1]||match[2];
}
const result={'*':ids.DLQI};
for(const [slug,names] of Object.entries(dn.CALC_ORDER)) {
  if(!ids[names[0]]) throw Error('Unknown primary calculator '+names[0]);
  result[slug]=ids[names[0]];
}
process.stdout.write(JSON.stringify(result));
"""
    return json.loads(subprocess.check_output(['node','-e',script,
        str(ROOT / 'blog/blog-calculators.js'), str(ROOT / 'blog/blog-shared.js')], text=True, encoding='utf-8'))


def has_fragment(target: Path, fragment: str, cache: dict, calculators: dict) -> bool:
    if fragment in anchors_for(target, cache):
        return True
    text = target.read_text(encoding='utf-8')
    has_prose = re.search(r'id="proseZh"|class="[^"]*\bprose(?:\s|")', text)
    return bool(target.parent.name == 'blog' and has_prose and 'blog-shared.min.js' in text
                and fragment == calculators.get(target.stem, calculators.get('*')))


def needs_zh_fragment(href: str, cache: dict, calculators: dict) -> bool:
    """A section absent from a courtesy EN mirror must link to its real source."""
    split = urlsplit(href)
    if not split.fragment or split.scheme or split.netloc:
        return False
    zh_path = split.path[3:] if split.path.startswith('/en/') else split.path
    zh, en = page_path(zh_path), page_path('/en' + zh_path)
    fragment = unquote(split.fragment)
    return bool(zh and en and zh.suffix == '.html' and en.suffix == '.html'
                and has_fragment(zh, fragment, cache, calculators)
                and not has_fragment(en, fragment, cache, calculators))


# CODE_REVIEW TD-58 — anti-vacuity floor. The pass line already reported the
# file count, but a parser that stopped extracting hrefs would keep that number
# intact while checking nothing, so the number of links actually resolved is
# reported and floored too.
MIN_LINKS_RESOLVED = 2000


def main() -> int:
    errors: list[str] = []
    files = html_files()
    pages = {page_url(path): path for path in files}
    anchor_cache: dict[Path, set[str]] = {}
    calculators = calculator_anchors()
    resolved_links = 0

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
            resolved_links += 1
            target_path_raw, fragment = split.path or source_url, unquote(split.fragment)
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

            if fragment and target_file.suffix == ".html" and not has_fragment(target_file, fragment, anchor_cache, calculators):
                errors.append(
                    f"{source.relative_to(ROOT).as_posix()}: missing anchor {raw!r} -> "
                    f"{target_file.relative_to(ROOT).as_posix()}#{fragment}"
                )

    if resolved_links < MIN_LINKS_RESOLVED:
        errors.append(
            f"only {resolved_links} internal link(s) resolved (expected >= "
            f"{MIN_LINKS_RESOLVED}) — link extraction is broken, so a pass means nothing"
        )

    if errors:
        print("[FAIL] Internal link audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print(f"[OK] Internal link audit passed "
          f"({len(files)} HTML files, {resolved_links} internal links resolved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
