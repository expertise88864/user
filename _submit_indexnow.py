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
import time
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

    def attempt() -> tuple[int | None, str]:
        """Return (http_status, body_text). status is None on network failure."""
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
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return exc.code, (exc.read().decode("utf-8", errors="replace") if exc.fp else "")
        except Exception as exc:  # noqa: BLE001 — network timeout / DNS / reset
            return None, str(exc)

    # IndexNow responses:
    #   200 OK / 202 Accepted — submitted successfully
    #   400 — bad request (malformed JSON)        ← OUR bug → fail
    #   403 — key file unreachable (KEY.txt down)  ← OUR bug → fail
    #   422 — URLs not under host / invalid        ← OUR bug → fail
    #   429 — rate limited                         ← transient → retry, then pass
    #   5xx / network timeout                      ← THEIR outage → retry, then pass
    #
    # 2026-05-26 — IndexNow is a best-effort "please recrawl faster" ping to
    # Bing/Yandex/Seznam; it does NOT affect Google. An api.indexnow.org
    # outage (we observed sustained HTTP 502s + read timeouts) must NOT fail
    # the CI workflow and spam failure emails. So transient upstream errors
    # (5xx / 429 / network) are retried a few times and then treated as a
    # non-fatal warning (exit 0). Only genuine client errors that indicate a
    # real problem on our side (400 / 403 / 422) fail the run so we get alerted.
    TRANSIENT_HTTP = {429, 500, 502, 503, 504}
    max_attempts = 3
    status: int | None = None
    body_text = ""
    for i in range(max_attempts):
        status, body_text = attempt()
        if status in (200, 202):
            print(f"[indexnow] submitted {len(urls)} URLs -> HTTP {status}")
            return 0
        transient = status is None or status in TRANSIENT_HTTP
        label = "network error" if status is None else f"HTTP {status}"
        if transient and i < max_attempts - 1:
            wait = 5 * (i + 1)
            print(f"[indexnow] {label} (attempt {i + 1}/{max_attempts}) — retrying in {wait}s")
            time.sleep(wait)
            continue
        break

    if status is not None and status not in (200, 202) and status not in TRANSIENT_HTTP:
        # Any non-success status that is NOT a known-transient upstream code is a
        # real problem on our side that needs fixing — bad/rotated key (401),
        # endpoint moved (404), malformed payload (400), key file unreachable
        # (403), URLs not under host (422), payload too large (413), etc. Fail
        # so the CI email is actionable. (Previously only an explicit
        # {400,403,422} allowlist failed, so 401/404/413/… leaked through as a
        # silent "non-fatal" pass — defeating the alerting this script exists for.)
        print(f"[indexnow] submit FAILED -> HTTP {status} (client/unexpected error — needs a fix)")
        print(f"[indexnow]   response body: {body_text[:300]}")
        return 1

    # Transient upstream outage (5xx / 429 / network) — non-fatal.
    where = "network unreachable" if status is None else f"HTTP {status}"
    print(f"[indexnow] upstream issue after {max_attempts} attempts -> {where}")
    print("[indexnow] treating as NON-FATAL (IndexNow is best-effort; does not affect Google).")
    if body_text:
        print(f"[indexnow]   detail: {body_text[:200]}")
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
