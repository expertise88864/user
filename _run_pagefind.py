#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the exact Pagefind native package installed from package-lock.json.

Install with npm ci --ignore-scripts before building. Generation does not use
npx, registry resolution, user script shells or executable-path overrides.

Pagefind crawls the static HTML on disk and writes /pagefind/ (UI bundle
+ chunked search index, total ~3 MB but loaded only on search-button
click). Supports CJK out-of-the-box with BM25 ranking — replaces the
substring-match self-built search.

Runs as part of _run_quality.py BUILD_GENERATED_STEPS, after all HTML
generators but before any check that might reference the pagefind paths.

Usage:
    python _run_pagefind.py             # full build (default)
    # Every invocation rebuilds: old fragments must not survive a new crawl.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import re
import json
import platform
import stat
import hashlib
from pathlib import Path

from _gen_search_index import VisibleTextExtractor
from _sync_hub_catalog import load_catalog

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
PAGEFIND_DIR = ROOT / "pagefind"
PUBLIC_HTML_GLOB = "{*.html,blog/*.html,en/*.html,en/blog/*.html}"
PAGEFIND_VERSION = '1.5.2'
# Derived from each complete npm tarball only after its SHA512 matched the
# committed lockfile. An upgrade must update both identities together. All
# seven 1.5.2 platform packages ship the extended/CJK binary exclusively.
PAGEFIND_NATIVE = {
    '@pagefind/darwin-arm64': {
        'integrity': 'sha512-MXpI+7HsAdPkvJ0gk9xj9g541BCqBZOBbdwj9g6lB5LCj6kSV6nqDSjzcAJwvOsfu0fjwvC8hQU+ecfhp+MpiQ==',
        'size': 57617264, 'sha256': '111c39d20165385df77736c80ddace6593d01d46d0758d541f5d3bafff0cddd2'},
    '@pagefind/darwin-x64': {
        'integrity': 'sha512-IojxFWMEJe0RQ7PQ3KXQsPIImNsbpPYpoZ+QUDrL8fAl/O27IX+LVLs74/UzEZy5uA2LD8Nz1AiwKr72vrkZQw==',
        'size': 57441084, 'sha256': 'a8ca52c505ccd223136d19193c56824191268b045036c25828322c7bba4008c3'},
    '@pagefind/freebsd-x64': {
        'integrity': 'sha512-7EVzo9+0w+2cbe671BtMj10UlNo83I+HrLVLfRxO731svHRJKUfJ/mo05gU14pe9PCfpKNQT8FS3Xc/oDN6pOA==',
        'size': 58286848, 'sha256': '547baa255c19c54193280c45cc1ae71aafd0d248a31ea1fd208549cd9a6332a5'},
    '@pagefind/linux-arm64': {
        'integrity': 'sha512-Ovt9+K35sqzn8H3ZMXGwls4TD/wMJuvRtShHIsmUQREmaxjrDEX7gHckRCrwYJ4XE1H1p6HkLz3wukrAnsfXQw==',
        'size': 57547816, 'sha256': 'f317d9624087db37e875e1f606aaf09e935a9fce9cf5122b989d7579cc669a8c'},
    '@pagefind/linux-x64': {
        'integrity': 'sha512-V+tFqHKXhQKq/WqPBD67AFy7scn1/aZID00ws4fSDd+1daSi5UHR9VVlRrOUYKxn3VuFQYRD7lYXdZK1WED1YA==',
        'size': 58802000, 'sha256': '70cb6d23d6508bb18e77fd5403e99d7ede0ae9d2eef1ab9f049411e0c12ec380'},
    '@pagefind/windows-arm64': {
        'integrity': 'sha512-hN9Nh90fNW61nNRCW9ZyQrAj/mD0eRvmJ8NlTUzkbuW8kIzGJUi3cxjFkEcMZ5h/8FsKWD/VcouZl4yo1F7B6g==',
        'size': 57802752, 'sha256': '5f2ce0af09c782728743fb3aae3ac4fdc974c068cf67a32cb4e7a9024b100732'},
    '@pagefind/windows-x64': {
        'integrity': 'sha512-Fa2Iyw7kaDRzGMfNYNUXNW2zbL5FQVDgSOcbDHdzBrDEdpqOqg8TcZ68F22ol6NJ9IGzvUdmeyZypLW5dyhqsg==',
        'size': 58413056, 'sha256': 'ea67f8e3757e756263df57244ba894807a9bed8501b02d15daf1ab00a8a98734'},
}


def locked_binary(tool_root: Path | None = None) -> Path:
    """Resolve only this checkout's integrity-pinned platform package."""
    root = (tool_root if tool_root is not None else Path(__file__).resolve().parent).resolve()
    system = 'windows' if sys.platform == 'win32' else 'freebsd' if sys.platform.startswith('freebsd') else sys.platform
    cpu = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine().lower())
    if system not in {'windows', 'linux', 'darwin', 'freebsd'} or cpu is None:
        raise ValueError('Unsupported locked Pagefind platform')
    name = '@pagefind/' + system + '-' + cpu
    pin = PAGEFIND_NATIVE.get(name)
    if pin is None:
        raise ValueError('Unsupported locked Pagefind platform')
    def metadata(path: Path) -> dict:
        info = path.lstat()
        if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > 1_500_000):
            raise ValueError('Pagefind metadata must be a bounded ordinary local file')
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict):
            raise ValueError('Invalid Pagefind package metadata')
        return value
    manifest = metadata(root / 'package.json')
    lock = metadata(root / 'package-lock.json')
    if (manifest.get('dependencies', {}).get('pagefind') != PAGEFIND_VERSION or
            lock.get('packages', {}).get('', {}).get('dependencies', {}).get('pagefind') != PAGEFIND_VERSION):
        raise ValueError('Pagefind requires an exact root dependency')
    for key in ('pagefind', name):
        entry = lock.get('packages', {}).get('node_modules/' + key, {})
        installed = metadata(root / 'node_modules' / key / 'package.json')
        if (entry.get('version') != PAGEFIND_VERSION or installed.get('version') != PAGEFIND_VERSION or
                installed.get('name') != key or not re.fullmatch(r'sha512-[A-Za-z0-9+/]+={0,2}', entry.get('integrity', ''))):
            raise ValueError('Pagefind installed packages differ from their locked identity')
    if lock['packages']['node_modules/' + name]['integrity'] != pin['integrity']:
        raise ValueError('Pagefind native package differs from its pinned tarball')
    binary = root / 'node_modules' / name / 'bin' / ('pagefind_extended.exe' if system == 'windows' else 'pagefind_extended')
    info = binary.lstat()
    if (binary.resolve() != binary or not stat.S_ISREG(info.st_mode) or
            # The locked Windows extended/CJK executable is 58,413,056 bytes;
            # this tool bound is distinct from patient-asset archive limits.
            not 0 < info.st_size <= 128_000_000 or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400):
        raise ValueError('Locked Pagefind executable is not an ordinary local file')
    def identity(value):
        # Python's deprecated Windows ctime differs between stat and fstat.
        # Creation time agrees there; Unix retains the change timestamp.
        clock = value.st_birthtime_ns if os.name == 'nt' else value.st_ctime_ns
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, clock)
    if info.st_size != pin['size']:
        raise ValueError('Pagefind executable differs from its pinned bytes')
    with binary.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(info):
            raise ValueError('Pagefind executable changed while opening')
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if (identity(os.fstat(stream.fileno())) != identity(info) or
                identity(binary.lstat()) != identity(info) or digest != pin['sha256']):
            raise ValueError('Pagefind executable differs from its pinned bytes')
    return binary


def indexable_glob(root: Path) -> str:
    """Limit the crawler to current public visibility, including EN mirrors.

    Pagefind does not apply robots/noindex or the author catalog by itself.
    Inspect every candidate before clearing old output; malformed/missing
    visibility data must fail the build rather than index every HTML file.
    """
    unpublished = {item['slug'] for item in load_catalog(root) if item.get('unpublished')}
    paths = []
    for folder in (root, root / 'blog', root / 'en', root / 'en/blog'):
        for target in sorted(folder.glob('*.html')):
            relative = target.relative_to(root).as_posix()
            if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('Refuse indexing an HTML source outside the site root')
            if not re.fullmatch(r'(?:en/)?(?:blog/)?[a-z0-9-]+\.html', relative):
                raise ValueError('Unsupported public HTML path: ' + relative)
            if target.parent.name == 'blog' and target.stem in unpublished:
                continue
            parser = VisibleTextExtractor()
            parser.feed(target.read_text(encoding='utf-8'))
            parser.close()
            if not parser.noindex:
                paths.append(relative)
    if not paths:
        raise ValueError('No indexable public HTML sources')
    return paths[0] if len(paths) == 1 else '{' + ','.join(paths) + '}'


def main() -> int:
    # Never reuse an existing directory: it may contain fragments of private
    # files indexed by an older, broader crawl. Only this generated child is removed.
    if PAGEFIND_DIR.is_symlink() or PAGEFIND_DIR.resolve() != ROOT.resolve() / "pagefind":
        raise ValueError("Refuse clearing a Pagefind output outside the site root")
    public_glob = indexable_glob(ROOT)
    try:
        binary = locked_binary()
    except (ValueError, OSError) as error:
        print(f'[pagefind] locked tool unavailable: {error}. Run npm ci --ignore-scripts.')
        return 1
    if PAGEFIND_DIR.exists():
        shutil.rmtree(PAGEFIND_DIR)

    args = [
        str(binary),
        "--site", str(ROOT),
        "--output-path", str(PAGEFIND_DIR),
        "--root-selector", "main",
    ]
    # Use the native executable with no script shell. Keep the exact validated
    # visibility list in its supported environment option, overriding only the
    # child's inherited glob without changing the parent environment.
    env = os.environ.copy()
    env['PAGEFIND_GLOB'] = public_glob
    print(f"[pagefind] {' '.join(args[:5])} ...")
    try:
        result = subprocess.run(args, cwd=str(ROOT), check=False, text=True,
                                encoding="utf-8", errors="replace",
                                capture_output=True, timeout=180, env=env)
    except subprocess.TimeoutExpired:
        print("[pagefind] timed out after 180s — build failed")
        return 1
    except Exception as exc:
        print(f"[pagefind] failed to invoke locked executable: {exc}")
        return 1

    # Keep successful builds concise, but retain actionable failure diagnostics
    # (the CLI emits lowercase 'error:', which the old summary filter hid).
    out_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
    for line in out_lines[-60:] if result.returncode != 0 else out_lines:
        if result.returncode != 0 or any(kw in line for kw in ["Indexed", "Finished", "language", "Warning", "Error"]):
            print(f"  {line}")

    if result.returncode != 0:
        print(f"[pagefind] exited with code {result.returncode} (build failed)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
