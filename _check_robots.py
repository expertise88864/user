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
        if 'User-agent:' in raw and 'Allow: /' in raw:
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

    if errors:
        print('[FAIL] robots.txt audit')
        for err in errors:
            print(' - ' + err)
        sys.exit(1)

    print('[OK] robots.txt audit passed')


if __name__ == '__main__':
    main()
