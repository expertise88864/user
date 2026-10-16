#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Production must serve the site, not the repository.

Before 2026-10-16 vercel.json published the repository root, so production
returned 200 for build/review scripts (/_delivery.py, /tools/pr_review.py),
internal documents (/AGENTS.md, /TECH_DEBT.md), CI and hook configuration,
build data (/data/exam/questions.json, /_pdf_extracts/*) and even the build's
/__pycache__/*.pyc. _site_publish.py now stages only the public site into
dist/. This audit keeps that true:

  * vercel.json serves dist/ and the build ends by staging it;
  * every tracked top-level directory and root file is explicitly classified,
    so a new site directory or file type cannot vanish from production and a
    new internal directory cannot be published by accident;
  * representative internal paths stay private and site entry points public;
  * every local URL that the published pages, styles, scripts, feeds, the
    service worker, vercel.json, middleware or functions reference, and that
    exists in the checkout, is also in the published set.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from _site_publish import (OUTPUT, PRIVATE_PARTS, PRIVATE_SUFFIXES, PUBLIC_DIRS, PUBLIC_ROOT_FILES, ROOT,
                           is_published, published_files)


BUILD_COMMAND = ('node _vercel_gate.cjs --build && npm run build && node _vercel_gate.cjs --build --post-build'
                 f' && python _site_publish.py --stage {OUTPUT}')
# Tracked top-level directories that are never static files. api/ holds the
# serverless functions, which Vercel deploys from the project root.
INTERNAL_DIRS = frozenset({'.claude', '.githooks', '.github', '_pdf_extracts', 'api', 'astro-rewrite',
                           'data', 'styles', 'tools'})
INTERNAL_ROOT_FILES = frozenset({'vercel.json', 'middleware.js', 'package.json', 'package-lock.json'})
# Each of these returned HTTP 200 from production on 2026-10-15/16.
MUST_STAY_PRIVATE = (
    '_delivery.py', '_delivery_policy.json', '_run_ci.py', '_test_delivery.py', '_vercel_gate.cjs',
    '_cms_delivery.cjs', '_serve.mjs', '_site_settings.json', '_knowledge_graph.json',
    '.cms-delivery.json', '.site-settings-delivery.json', '.gitignore', '.vale.ini',
    'AGENTS.md', 'CLAUDE.md', 'README.md', 'DECISIONS.md', 'TECH_DEBT.md', 'CODE_REVIEW.md',
    'REMOTE_CI_DELIVERY.md', 'vercel.json', 'middleware.js', 'deploy.ps1', 'deploy.bat', 'set-domain.ps1',
    'new-article.ps1', '_setup_pagefind.bat', 'tools/pr_review.py', 'tools/codex_review.sh',
    '.github/workflows/delivery.yml', '.github/tools/html-validator/check.py', '.githooks/pre-push',
    '.claude/launch.json', 'data/exam/questions.json', 'data/nhi/derm_2026-09-22.md',
    '_pdf_extracts/AK JAAD.txt', 'astro-rewrite/package.json', 'styles/DermNotes/BannedYMYL.yml',
)
UNTRACKED_PRIVATE = ('__pycache__/_delivery.cpython-312.pyc', 'blog/__pycache__/x.pyc',
                     'node_modules/parse5/package.json', '.git/HEAD', '.vercel/project.json', '.env',
                     '_scratch.txt', 'assets/.DS_Store', 'blog/.well-known/x', 'dist/index.html')
MUST_STAY_PUBLIC = (
    'index.html', '404.html', 'offline.html', 'reset-sw.html', 'robots.txt', 'sitemap.xml', 'llms.txt',
    'llms-full.txt', 'ads.txt', 'humans.txt', 'opensearch.xml', 'manifest.json', 'sw.js', 'favicon.ico',
    'icon.svg', 'icon-192.png', 'apple-touch-icon.png', '.well-known/security.txt', '.well-known/ai.txt',
    'ai/summary.json', 'blog/feed.xml', 'blog/atom.xml', 'assets/search-index.json',
    'pagefind/pagefind.js', 'admin/word-editor.js', 'exam/index.html', 'en/index.html',
    '088dd3112f7c0dbe01fed932957d952a6efcb29285bec9ae3df29f174d9e1c10.txt',
    'c481b9a4f6410883e67a02647a4715ed.txt',
)

SITE_HOSTS = {'chendermatologist.com', 'www.chendermatologist.com'}
SCANNED_SUFFIXES = {'.html', '.css', '.js', '.json', '.xml', '.txt', '.svg', '.webmanifest'}
ATTR_RE = re.compile(r'''\b(?:src|href|poster|content|action|srcset|imagesrcset|data-[\w-]+)\s*=\s*(["'])(.*?)\1''',
                     re.IGNORECASE | re.DOTALL)
CSS_URL_RE = re.compile(r'''url\(\s*(["']?)([^"')\s]+)\1\s*\)''', re.IGNORECASE)
LITERAL_RE = re.compile(r'''(["'`])((?:https?://(?:www\.)?chendermatologist\.com)?/[^"'`\s<>\\]*)\1''')
ABSOLUTE_RE = re.compile(r'''https?://(?:www\.)?chendermatologist\.com(/[^\s"'`<>)\]\\]*)''')
SKIP_SCHEMES = ('data:', 'mailto:', 'tel:', 'javascript:', 'blob:', 'about:', 'sms:')
SKIP_WALK = frozenset({'.git', OUTPUT, '.lighthouseci', '.codex-review', '.claude-review', 'delivery-preview'})


def tracked_files() -> list[str]:
    out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, check=True, capture_output=True).stdout
    return sorted(name for name in out.decode('utf-8').split('\0') if name)


def classification_errors(tracked: list[str]) -> list[str]:
    errors = []
    tracked_set = set(tracked)
    for name in tracked:
        parts = PurePosixPath(name).parts
        if len(parts) > 1:
            top = parts[0]
            if top in PUBLIC_DIRS:
                if not is_published(name):
                    errors.append(f'{name}: tracked file in a public directory is not deployed')
            elif top not in INTERNAL_DIRS:
                errors.append(f'{top}/: unclassified top-level directory; add it to PUBLIC_DIRS '
                              f'(_site_publish.py) or INTERNAL_DIRS (_check_deploy_exposure.py)')
            elif is_published(name):
                errors.append(f'{name}: internal directory is deployed')
        elif not is_published(name):
            suffix = PurePosixPath(name).suffix.lower()
            if not (name.startswith(('_', '.')) or suffix in PRIVATE_SUFFIXES or name in INTERNAL_ROOT_FILES):
                errors.append(f'{name}: unclassified root file; list it in PUBLIC_ROOT_FILES '
                              f'(_site_publish.py and _serve.mjs) or INTERNAL_ROOT_FILES')
    for name in MUST_STAY_PRIVATE:
        if name not in tracked_set:
            errors.append(f'{name}: private probe is no longer tracked; update MUST_STAY_PRIVATE')
        elif is_published(name):
            errors.append(f'{name}: internal file would be deployed')
    for name in UNTRACKED_PRIVATE:
        if is_published(name):
            errors.append(f'{name}: local/build artefact would be deployed')
    for name in MUST_STAY_PUBLIC:
        if not is_published(name):
            errors.append(f'{name}: site file would not be deployed')
    return errors


def config_errors() -> list[str]:
    config = json.loads((ROOT / 'vercel.json').read_text(encoding='utf-8'))
    errors = []
    if config.get('outputDirectory') != OUTPUT:
        errors.append(f'vercel.json: outputDirectory must be {OUTPUT!r} (the staged public site), '
                      f'not {config.get("outputDirectory")!r}')
    if config.get('buildCommand') != BUILD_COMMAND:
        errors.append('vercel.json: buildCommand must end by staging the public site: ' + BUILD_COMMAND)
    # The local server and production must expose the same site.
    serve = (ROOT / '_serve.mjs').read_text(encoding='utf-8')
    for name, expected in (('PUBLIC_DIRECTORIES', PUBLIC_DIRS), ('PUBLIC_ROOT_FILES', PUBLIC_ROOT_FILES)):
        match = re.search(r'const ' + name + r' = new Set\(\[(.*?)\]\);', serve, re.DOTALL)
        if not match or set(re.findall(r"'([^']+)'", match.group(1))) != set(expected):
            errors.append(f'_serve.mjs: {name} differs from the deployed site selection in _site_publish.py')
    gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines()
    if f'{OUTPUT}/' not in gitignore:
        errors.append(f'.gitignore: {OUTPUT}/ (the staged site) must stay untracked')
    return errors


def source_files() -> set[str]:
    found = set()
    for directory, dirnames, filenames in os.walk(ROOT):
        here = Path(directory)
        dirnames[:] = [name for name in dirnames
                       if name not in PRIVATE_PARTS and not (here == ROOT and name in SKIP_WALK)]
        for name in filenames:
            found.add((here / name).relative_to(ROOT).as_posix())
    return found


def served_url(relative: str) -> str:
    return '/' + relative


def resolve(url_path: str, files: set[str]) -> str | None:
    path = unquote(url_path).lstrip('/')
    if path == '' or path.endswith('/'):
        candidates = [path + 'index.html']
    else:
        candidates = [path, path + '.html', path + '/index.html']
    return next((candidate for candidate in candidates if candidate in files), None)


def local_path(raw: str, base: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.startswith(('#', '//')) or raw.lower().startswith(SKIP_SCHEMES):
        return None
    if '${' in raw or '{{' in raw or '\n' in raw:
        return None
    parts = urlsplit(urljoin('https://chendermatologist.com' + base, raw))
    if parts.scheme not in {'http', 'https'} or parts.hostname not in SITE_HOSTS:
        return None
    return parts.path or '/'


def references(relative: str, text: str) -> set[str]:
    base = served_url(relative)
    raw: list[str] = []
    for match in ATTR_RE.finditer(text):
        value = match.group(2)
        if 'srcset' in match.group(0).lower().split('=', 1)[0]:
            raw.extend(item.strip().split(' ')[0] for item in value.split(','))
        else:
            raw.append(value)
    raw.extend(match.group(2) for match in CSS_URL_RE.finditer(text))
    raw.extend(match.group(2) for match in LITERAL_RE.finditer(text))
    raw.extend(match.group(1) for match in ABSOLUTE_RE.finditer(text))
    return {path for path in (local_path(value, base) for value in raw) if path}


def reference_errors(published: list[str]) -> tuple[list[str], int]:
    source = source_files()
    served = set(published)
    scanned = [name for name in published if PurePosixPath(name).suffix.lower() in SCANNED_SUFFIXES]
    # Request-time code is not static output, but what it points at must still be served.
    scanned += ['vercel.json', 'middleware.js'] + sorted(name for name in source
                                                         if name.startswith('api/') and name.endswith('.js'))
    errors, checked = [], 0
    for name in scanned:
        text = (ROOT / name).read_text(encoding='utf-8', errors='replace')
        for path in sorted(references(name, text)):
            target = resolve(path, source)
            if target is None:
                continue  # dynamic or function route, or not in the checkout at all
            checked += 1
            if resolve(path, served) is None:
                errors.append(f'{name}: references {path} ({target}), which would not be deployed')
    return errors, checked


def main() -> int:
    tracked = tracked_files()
    published = published_files(ROOT)
    errors = config_errors() + classification_errors(tracked)
    ref_errors, checked = reference_errors(published)
    errors += ref_errors
    if errors:
        print(f'[FAIL] Deployment exposure audit: {len(errors)} problem(s)')
        for error in errors[:200]:
            print('  - ' + error)
        return 1
    private = sum(1 for name in tracked if not is_published(name))
    print(f'[OK] Deployment exposure audit passed: {len(published)} public files staged, '
          f'{private} tracked internal files withheld, {checked} local references resolved')
    return 0


if __name__ == '__main__':
    sys.exit(main())
