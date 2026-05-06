#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit internal cross-links between blog articles.

Output:
  - graph: { from_slug: [linked_slug, ...] }
  - orphans: articles that nothing links TO
  - dead-ends: articles that link to NOTHING
  - hubs: articles with most outbound links

This is a *report*, not an injector. Use to spot articles needing more cross-refs.
"""
import os, re, sys, io, json
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.join(ROOT, 'blog')
SKIP = {'index.html', 'topics.html'}

def main():
    slugs = [f[:-5] for f in os.listdir(BLOG)
             if f.endswith('.html') and f not in SKIP]
    slugs_set = set(slugs)
    out_links = defaultdict(set)
    in_links = defaultdict(set)
    for s in slugs:
        path = os.path.join(BLOG, s + '.html')
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        for m in re.finditer(r'href="/blog/([^"#?/]+)"', html):
            target = m.group(1)
            if target in slugs_set and target != s:
                out_links[s].add(target)
                in_links[target].add(s)
    print(f'Total articles: {len(slugs)}')
    print(f'Total cross-link edges: {sum(len(v) for v in out_links.values())}')

    # Orphans (no inbound)
    orphans = sorted([s for s in slugs if not in_links.get(s)])
    print(f'\n[orphans — nothing links TO them, {len(orphans)}]')
    for s in orphans:
        print(f'  {s}')

    # Dead-ends (no outbound)
    dead = sorted([s for s in slugs if not out_links.get(s)])
    print(f'\n[dead-ends — link to nothing, {len(dead)}]')
    for s in dead:
        print(f'  {s}')

    # Top hubs
    print(f'\n[top hubs — most outbound links]')
    for s, links in sorted(out_links.items(), key=lambda x: -len(x[1]))[:8]:
        print(f'  {s} → {len(links)} outbound')

    # Save graph for further analysis
    out_path = os.path.join(ROOT, '_knowledge_graph.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'edges': {k: sorted(v) for k, v in out_links.items()},
                   'orphans': orphans, 'dead_ends': dead}, f, ensure_ascii=False, indent=2)
    print(f'\nFull graph saved → _knowledge_graph.json')

if __name__ == '__main__':
    main()
