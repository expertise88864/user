#!/usr/bin/env python
"""Replace each article page's short pastel footer with the canonical
homepage mag-footer (dark ink background). Skips files that already use
mag-footer.
"""
import re, sys, io, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(ROOT, 'index.html'), 'r', encoding='utf-8') as f:
    home = f.read()
m = re.search(r'<style>\.mag-footer\{.*?</footer>', home, re.DOTALL)
if not m:
    print('NO mag-footer in index.html')
    sys.exit(1)
canonical = m.group(0)
print(f'Canonical mag-footer length: {len(canonical):,} chars')

SHORT_FOOTER_PAT = re.compile(
    r'<footer class="border-t border-\[var\(--border\)\] bg-mint-50/60">.*?</footer>',
    re.DOTALL,
)

files_changed = 0
for sub in ['', 'blog', 'en', os.path.join('en', 'blog')]:
    for path in glob.glob(os.path.join(ROOT, sub, '*.html')):
        norm = path.replace(os.sep, '/').lower()
        # Skip homepage (already canonical) — both root and en/
        if norm.endswith('/index.html'):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        if 'class="mag-footer"' in src:
            continue
        if 'class="border-t border-[var(--border)] bg-mint-50/60"' not in src:
            continue
        new = SHORT_FOOTER_PAT.sub(canonical, src)
        if new != src:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
            files_changed += 1
            print(f'  {os.path.relpath(path, ROOT)}: footer swapped')
print(f'\nUpdated {files_changed} files.')
