#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Push URL list to IndexNow for fast Bing / Yandex / Seznam re-crawl.

IndexNow lets us proactively notify search engines that content has
changed, so they re-crawl within hours instead of the usual days-to-
weeks polling cycle. Supported by Bing, Yandex, Seznam, Naver — NOT
Google directly (Google uses its own GSC URL Inspection API).

Setup:
  1. Random key file is committed at /KEY.txt (root) so Vercel serves
     it at https://chendermatologist.com/KEY.txt — IndexNow verifies
     ownership by fetching this file.
  2. This script POSTs the URL list to the IndexNow API.

Usage:
  python _submit_indexnow.py                 # submit all URLs from sitemap.xml
  python _submit_indexnow.py URL1 URL2 ...   # submit specific URLs
  python _submit_indexnow.py --since 7       # only URLs with lastmod within last N days

Idempotent + safe to re-run; IndexNow rate-limits to 10,000 URLs/day
per host. Sitemap has ~100 URLs so we're nowhere near the limit.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"
KEY = "088dd3112f7c0dbe01fed932957d952a6efcb29285bec9ae3df29f174d9e1c10"
KEY_LOCATION = f"{DOMAIN}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/IndexNow"


def parse_sitemap_urls(max_age_days: int | None = None) -> list[str]:
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    cutoff = None
    if max_age_days is not None:
        cutoff = dt.date.today() - dt.timedelta(days=max_age_days)
    urls: list[str] = []
    for url_block in re.findall(r"<url>([\s\S]*?)</url>", sm):
        loc_m = re.search(r"<loc>([^<]+)</loc>", url_block)
        if not loc_m:
            continue
        loc = loc_m.group(1).strip()
        if cutoff:
            lm_m = re.search(r"<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>", url_block)
            if not lm_m:
                continue
            try:
                lm = dt.date.fromisoformat(lm_m.group(1))
            except ValueError:
                continue
            if lm < cutoff:
                continue
        urls.append(loc)
    return urls


def submit(urls: list[str]) -> int:
    if not urls:
        print("[indexnow] no URLs to submit")
        return 0
    if len(urls) > 10000:
        print(f"[indexnow] truncating from {len(urls)} to 10000 (per-host daily cap)")
        urls = urls[:10000]
    payload = {
        "host": DOMAIN.removeprefix("https://").removeprefix("http://"),
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Host": "api.indexnow.org",
            "User-Agent": "DermNotes-IndexNow-Submitter/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body_text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        status = exc.code
    except Exception as exc:
        print(f"[indexnow] network error: {exc}")
        return 1
    # IndexNow returns:
    #   200 OK / 202 Accepted — submitted successfully
    #   400 — bad request (malformed JSON)
    #   403 — key file unreachable (verify host KEY.txt is live)
    #   422 — URLs not under host or invalid
    #   429 — rate limited
    print(f"[indexnow] submitted {len(urls)} URLs -> HTTP {status}")
    if status not in (200, 202):
        print(f"[indexnow]   response body: {body_text[:300]}")
        return 1
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--since" in args:
        i = args.index("--since")
        try:
            days = int(args[i + 1])
        except (IndexError, ValueError):
            print("Usage: --since N (days)")
            return 2
        urls = parse_sitemap_urls(max_age_days=days)
        print(f"[indexnow] {len(urls)} URLs updated in last {days} days")
    elif args:
        urls = [a for a in args if a.startswith("http")]
    else:
        urls = parse_sitemap_urls()
        print(f"[indexnow] {len(urls)} URLs from full sitemap")
    return submit(urls)


if __name__ == "__main__":
    sys.exit(main())
