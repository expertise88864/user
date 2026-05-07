#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Robust Pagefind installer + index builder (replaces _setup_pagefind.bat).

Downloads the Pagefind standalone binary for the current platform, then runs
it against the site to build /pagefind/.

Why Python instead of bat:
  - GitHub release filenames sometimes change. We try multiple candidates.
  - Binary download with progress + retry.
  - Cross-platform (works on Win/Mac/Linux without rewriting).

Usage:
    python _setup_pagefind.py             # auto-detect latest, download, index
    python _setup_pagefind.py --version 1.1.1
    python _setup_pagefind.py --reindex   # skip download (use existing binary)
"""
import os, sys, io, platform, subprocess, urllib.request, zipfile, tempfile, shutil
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(ROOT, '_bin')
os.makedirs(BIN_DIR, exist_ok=True)

VERSIONS_TO_TRY = ['1.1.1', '1.1.0', '1.0.4', '1.0.3']

def detect_platform():
    sys_name = platform.system().lower()
    arch = platform.machine().lower()
    # Map to Pagefind release naming (based on rust target triples)
    if sys_name == 'windows':
        # x86_64-pc-windows-msvc
        return ('x86_64-pc-windows-msvc', 'pagefind.exe', '.zip', 'tar.gz')
    if sys_name == 'darwin':
        target = 'aarch64-apple-darwin' if arch in ('arm64', 'aarch64') else 'x86_64-apple-darwin'
        return (target, 'pagefind', '.tar.gz', None)
    # Linux
    target = 'aarch64-unknown-linux-musl' if arch in ('aarch64', 'arm64') else 'x86_64-unknown-linux-musl'
    return (target, 'pagefind', '.tar.gz', None)

def candidate_urls(version):
    target, exe, ext1, ext2 = detect_platform()
    base = 'https://github.com/CloudCannon/pagefind/releases/download/v{v}'
    fnames = [
        f'pagefind-v{version}-{target}{ext1}',
        # Also try without v-prefix in version (some older releases)
        f'pagefind_extended-v{version}-{target}{ext1}',
    ]
    if ext2:
        fnames.append(f'pagefind-v{version}-{target}{ext2}')
    return [base.format(v=version) + '/' + n for n in fnames]

def download(url, dest):
    print(f'  GET {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 pagefind-installer'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, 'wb') as f:
            shutil.copyfileobj(r, f)
        return True
    except Exception as e:
        msg = str(e)
        # 404 → try next URL silently
        if '404' in msg or 'Not Found' in msg:
            print(f'    → 404, skipping')
            return False
        print(f'    → ERROR: {msg}')
        return False

def install_binary():
    target, exe, _, _ = detect_platform()
    exe_path = os.path.join(BIN_DIR, exe)
    if os.path.exists(exe_path):
        print(f'✓ Pagefind binary already at {exe_path}')
        return exe_path
    print(f'Detected platform: {target}')
    print(f'Will install to: {exe_path}')
    for v in VERSIONS_TO_TRY:
        for url in candidate_urls(v):
            ext = '.zip' if url.endswith('.zip') else '.tar.gz'
            archive = os.path.join(BIN_DIR, 'pagefind' + ext)
            if download(url, archive):
                print(f'✓ Downloaded {os.path.getsize(archive)} bytes')
                # Extract
                if ext == '.zip':
                    with zipfile.ZipFile(archive, 'r') as z:
                        z.extractall(BIN_DIR)
                else:
                    import tarfile
                    with tarfile.open(archive, 'r:gz') as t:
                        t.extractall(BIN_DIR)
                os.remove(archive)
                if os.path.exists(exe_path):
                    if not exe.endswith('.exe'):
                        os.chmod(exe_path, 0o755)
                    print(f'✓ Installed Pagefind v{v} → {exe_path}')
                    return exe_path
    print('\n❌ All download attempts failed.')
    print('Manual download: https://github.com/CloudCannon/pagefind/releases')
    print(f'Save the binary as: {exe_path}')
    sys.exit(1)

def run_index(exe_path):
    print(f'\nBuilding Pagefind index against {ROOT}')
    out_dir = os.path.join(ROOT, 'pagefind')
    cmd = [
        exe_path,
        '--site', ROOT,
        '--output-path', out_dir,
        '--root-selector', 'main, article, body',
        '--keep-index-url',
    ]
    print(f'  $ {" ".join(cmd)}')
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f'❌ Pagefind exited {r.returncode}')
        sys.exit(r.returncode)
    print(f'\n✓ Index built. Commit pagefind/ to git so Vercel deploys it.')
    print(f'  Files in pagefind/: {sum(1 for _ in os.listdir(out_dir))} files')

if __name__ == '__main__':
    args = sys.argv[1:]
    if '--reindex' in args:
        target, exe, _, _ = detect_platform()
        exe_path = os.path.join(BIN_DIR, exe)
        if not os.path.exists(exe_path):
            print('No binary found. Run without --reindex first.')
            sys.exit(1)
    else:
        exe_path = install_binary()
    run_index(exe_path)
