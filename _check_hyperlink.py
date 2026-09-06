"""Run hyperlink against the deployed routing model, with real failure exits."""
from __future__ import annotations

import json
import re
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urljoin, urlsplit, urlunsplit

from _check_internal_links import ROOT, calculator_anchors, has_fragment, page_url, page_path


def routed_html(text: str, source: Path) -> str:
    """Resolve real clean URLs in HTML attributes; preserve every fragment."""
    edits = []
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    class Routes(HTMLParser):
        def handle_starttag(self, tag, attrs):
            raw = self.get_starttag_text()
            line, column = self.getpos()
            start = offsets[line - 1] + column
            for match in re.finditer(r'\b(?:href|src)\s*=\s*([\"\'])(.*?)\1', raw, re.I | re.S):
                link = unescape(match[2])
                parsed = urlsplit(urljoin(page_url(source), link))
                if parsed.scheme or parsed.netloc:
                    continue
                target = page_path(parsed.path)
                if target is not None and target.suffix == '.html':
                    mapped = urlunsplit(('', '', '/' + target.relative_to(ROOT).as_posix(), parsed.query, parsed.fragment))
                    edits.append((start + match.start(2), start + match.end(2), escape(mapped, quote=True)))

    Routes(convert_charrefs=True).feed(text)
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text


def stage(destination: Path) -> None:
    # Only versioned source belongs in this mirror, never review logs or secrets.
    files = subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    calculators = calculator_anchors()
    redirects = []
    for name in filter(None, files):
        source = ROOT / name
        if not source.is_file():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if source.suffix != '.html':
            continue
        route = page_url(source)
        if route != '/' and route != '/' + name:
            redirects.append(f'{route.rstrip("/")} /{name}')
        # The calculator is mounted by blog-shared.js. Model only its exact
        # primary ID derived from production dispatch, never arbitrary dn-* IDs.
        text = routed_html(target.read_text(encoding='utf-8'), source)
        primary = calculators.get(source.stem, calculators.get('*'))
        if primary and has_fragment(source, primary, {}, calculators):
            text += f'\n<div id="{primary}"></div>\n'
        target.write_text(text, encoding='utf-8')
    config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
    for item in config.get('redirects', []):
        if ':' not in item['source'] and '*' not in item['source']:
            redirects.append(f"{item['source']} {item['destination']}")
    (destination / '_redirects').write_text('\n'.join(redirects) + '\n', encoding='utf-8')
    # This single asset is supplied by Vercel Speed Insights, outside Git.
    runtime = destination / '_vercel/speed-insights/script.js'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text('// Vercel-managed Speed Insights endpoint\n', encoding='utf-8')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='dermnotes-hyperlink-') as directory:
        destination = Path(directory)
        stage(destination)
        return subprocess.run(['hyperlink', str(destination), '--check-anchors'], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
