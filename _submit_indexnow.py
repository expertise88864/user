#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Notify IndexNow of public URLs only after exact-SHA production verification.

IndexNow tells participating search engines that public content has changed.
HTTP 200/202 confirms receipt, not a crawl/index/ranking result or deadline.
Protocol reference: https://www.indexnow.org/documentation

Setup:
  1. Random key file is committed at /KEY.txt (root) so Vercel serves
     it at https://chendermatologist.com/KEY.txt — IndexNow verifies
     ownership by fetching this file.
  2. This script POSTs the URL list to the IndexNow API.

Usage:
  python _submit_indexnow.py --sha FULL_SHA               # current public sitemap
  python _submit_indexnow.py --sha FULL_SHA URL1 URL2      # public sitemap subset
  python _submit_indexnow.py --sha FULL_SHA --since 7      # recently changed URLs
  python _submit_indexnow.py --sha FULL_SHA --wait 600     # bounded evidence wait

Use the clean, exact current main revision. Candidate/failed/stale versions and
URLs with search parameters, fragments, foreign hosts or private paths cannot
notify IndexNow. Existing Actions credentials remain read-only and are never
sent to IndexNow. The protocol allows at most 10,000 URLs per POST.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import _delivery as delivery

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


def public_urls(urls: list[str]) -> list[str]:
    """Keep a stable public sitemap subset; never send arbitrary URL input."""
    published = set(parse_sitemap_urls())
    result = []
    for value in urls:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme != 'https' or parsed.netloc != 'chendermatologist.com'
                or parsed.query or parsed.fragment or value not in published):
            raise ValueError('Only public canonical sitemap URLs without query or fragment are allowed')
        if value not in result:
            result.append(value)
    return result


def production_ready(sha: str, api: delivery.API) -> None:
    """Required formal jobs/steps, trusted deployment and still-current main."""
    delivery.check_sha(sha)
    delivery.clean(sha)
    if api.get('/branches/main')['commit']['sha'] != sha:
        raise delivery.Blocked('IndexNow target is not current production main')
    cfg = delivery.policy()
    if cfg['repository'] != 'expertise88864/user':
        raise delivery.Blocked('Unexpected IndexNow repository')
    # Includes the independently executed exact-SHA Production smoke step.
    delivery.verify(sha, 'main', cfg, api)
    delivery.deployment_url(api, sha, 'production')
    if api.get('/branches/main')['commit']['sha'] != sha:
        raise delivery.Blocked('Production main advanced during IndexNow verification')
    delivery.clean(sha)


def submit(urls: list[str], *, sha: str, wait: int = 0) -> int:
    if not urls:
        print("[indexnow] no URLs to submit")
        return 0
    try:
        delivery.check_sha(sha)
        delivery.clean(sha)
        if type(wait) is not int or not 0 <= wait <= 900:
            raise ValueError('Evidence wait must be between 0 and 900 seconds')
        urls = public_urls(urls)
    except (delivery.Blocked, ValueError, OSError, subprocess.SubprocessError):
        print('[indexnow] blocked: invalid target, workspace or non-public URL input')
        return 2
    api = delivery.API('expertise88864/user')
    deadline = time.monotonic() + wait
    if len(urls) > 10000:
        print(f"[indexnow] truncating from {len(urls)} to 10000 (per-POST limit)")
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
        # Gate errors must never fall into the best-effort upstream-error path.
        # Recheck all mutable evidence immediately before every POST/retry.
        while True:
            try:
                production_ready(sha, api)
                break
            except (delivery.Blocked, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                if time.monotonic() >= deadline:
                    print('[indexnow] blocked: exact current formal CI/deployment evidence unavailable; no notification')
                    return 2
                print('[indexnow] waiting for exact current formal CI/deployment evidence')
                time.sleep(min(30, max(0, deadline - time.monotonic())))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True, help='Full, current production main SHA')
    parser.add_argument('--since', type=int, help='Public URLs modified within N days')
    parser.add_argument('--wait', type=int, default=0, help='Bounded formal evidence wait (0–900 seconds)')
    parser.add_argument('urls', nargs='*', help='Optional public sitemap URL subset')
    args = parser.parse_args(argv)
    if args.since is not None and (args.since < 0 or args.urls):
        parser.error('--since must be non-negative and cannot be combined with explicit URLs')
    if args.since is not None:
        urls = parse_sitemap_urls(max_age_days=args.since)
        print(f"[indexnow] {len(urls)} URLs updated in last {args.since} days")
    elif args.urls:
        urls = args.urls
    else:
        urls = parse_sitemap_urls()
        print(f"[indexnow] {len(urls)} URLs from full sitemap")
    return submit(urls, sha=args.sha, wait=args.wait)


if __name__ == "__main__":
    sys.exit(main())
