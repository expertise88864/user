#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit robots.txt against sitemap and internal tooling rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROBOTS = ROOT / 'robots.txt'
SITEMAP = ROOT / 'sitemap.xml'

SEARCH_USER_AGENTS = [
    'Googlebot',
    'Bingbot',
    'DuckDuckBot',
    'Mediapartners-Google',
    'AdsBot-Google',
    'ChatGPT-User',
    'OAI-SearchBot',
    'PerplexityBot',
]

INTERNAL_DISALLOWS = [
    'Disallow: /admin',
    'Disallow: /reset-sw',
    'Disallow: /en/reset-sw',
]

# Model-training / aggregation crawlers that MUST be blocked from the article
# tree (they may still fetch llms.txt / sitemap). This guards against a class
# of bug where a bot falls out of the block group — e.g. a duplicate top-level
# BLOCK_UAS assignment in _normalize_robots.py silently shadowing the first —
# and lands in the wildcard Allow group instead.
#
# Deliberately a COMPLETE, INDEPENDENT hardcoded list (the full BLOCK_UAS
# policy set), NOT imported from _normalize_robots.BLOCK_UAS: if it were
# derived from the same source, the very shadowing bug we are guarding against
# would shrink both the generator AND this list in lockstep, and the check
# would pass while bots were silently unblocked.
REQUIRED_BLOCKED = [
    'GPTBot',
    'anthropic-ai',
    'CCBot',
    'Applebot-Extended',
    'cohere-ai',
    'cohere-training-data-crawler',
    'Diffbot',
    'FacebookBot',
    'Amazonbot',
    'Bytespider',
    'omgilibot',
    'omgili',
    'AhrefsBot',
    'SemrushBot',
    'MJ12bot',
    'DotBot',
    'BLEXBot',
    'PetalBot',
]


def parse_robots(src: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    for raw in src.split('\n\n'):
        uas: list[str] = []
        rules: list[tuple[str, str]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('#') or ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            if key == 'user-agent':
                uas.append(value.lower())
            elif key in {'allow', 'disallow'}:
                rules.append((key, value))
        if uas:
            groups.append((uas, rules))
    return groups


def rules_for(user_agent: str, groups: list[tuple[list[str], list[tuple[str, str]]]]) -> list[tuple[str, str]]:
    ua = user_agent.lower()
    for uas, rules in groups:
        if ua in uas:
            return rules
    for uas, rules in groups:
        if '*' in uas:
            return rules
    return []


def disallowed(path: str, rules: list[tuple[str, str]]) -> bool:
    best: tuple[str, str] | None = None
    for kind, pattern in rules:
        if not pattern:
            continue
        prefix = pattern.rstrip('*')
        if path.startswith(prefix) and (best is None or len(prefix) > len(best[1].rstrip('*'))):
            best = (kind, pattern)
    return bool(best and best[0] == 'disallow')


def main() -> None:
    robots = ROBOTS.read_text(encoding='utf-8')
    sitemap = SITEMAP.read_text(encoding='utf-8')
    groups = parse_robots(robots)
    errors: list[str] = []
    seen_uas: set[str] = set()

    for uas, rules in groups:
        for ua in uas:
            if ua in seen_uas:
                errors.append(f'duplicate User-agent group: {ua}')
            seen_uas.add(ua)
        seen_rules: set[tuple[str, str]] = set()
        for rule in rules:
            if rule in seen_rules:
                ua_label = ', '.join(uas) or '?'
                errors.append(f'duplicate robots rule for {ua_label}: {rule[0]} {rule[1]}')
            seen_rules.add(rule)

    for raw in robots.split('\n\n'):
        # Only the open-access group needs internal disallows. We detect
        # it by the literal standalone `Allow: /` line — NOT a substring
        # match (otherwise `Allow: /llms.txt` etc. on the block group
        # would falsely trigger). The block group has `Disallow: /` and
        # narrower Allows, which don't grant tree access.
        lines = [ln.strip() for ln in raw.splitlines()]
        has_open_allow = 'Allow: /' in lines
        if 'User-agent:' in raw and has_open_allow:
            for rule in INTERNAL_DISALLOWS:
                if rule not in raw:
                    first_ua = next((line for line in raw.splitlines() if line.startswith('User-agent:')), 'User-agent: ?')
                    errors.append(f'{first_ua} missing {rule}')

    locs = re.findall(r'<loc>https://chendermatologist\.com([^<]*)</loc>', sitemap)
    if 'Sitemap: https://chendermatologist.com/sitemap.xml' not in robots:
        errors.append('robots.txt missing absolute Sitemap directive')
    for ua in SEARCH_USER_AGENTS:
        rules = rules_for(ua, groups)
        blocked = [loc for loc in locs if disallowed(loc, rules)]
        if blocked:
            errors.append(f'{ua} blocks sitemap URL(s): {", ".join(blocked[:5])}')

    # Training/aggregation crawlers MUST be broadly blocked. If one falls into
    # the wildcard Allow group (e.g. dropped from BLOCK_UAS), it would be free
    # to crawl everything — fail loudly. We require BOTH an effective broad
    # block (a literal `Disallow: /` in the resolved group) AND that every
    # representative path is disallowed, so a future narrow-disallow policy
    # can't slip through a single-path probe.
    probes = ['/blog/acne-myths', '/blog/', '/en/blog/acne-myths', '/glossary', '/tools', '/about']
    for ua in REQUIRED_BLOCKED:
        rules = rules_for(ua, groups)
        has_broad_block = any(kind == 'disallow' and pattern == '/' for kind, pattern in rules)
        crawlable = [p for p in probes if not disallowed(p, rules)]
        if not has_broad_block or crawlable:
            detail = 'no "Disallow: /"' if not has_broad_block else f'crawlable: {", ".join(crawlable)}'
            errors.append(f'training/scraper crawler {ua} is NOT broadly blocked ({detail})')

    if errors:
        print('[FAIL] robots.txt audit')
        for err in errors:
            print(' - ' + err)
        sys.exit(1)

    print('[OK] robots.txt audit passed')


if __name__ == '__main__':
    main()
