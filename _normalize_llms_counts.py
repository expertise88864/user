#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Refresh the (only) stale numbers inside the hand-curated llms.txt.

llms.txt is hand-written (curated "authoritative pages" + "latest research"
lists worth keeping). The only parts that drift are three counts:
  - "<zh> published articles + <en> EN mirrors"
  - "all <N> published articles concatenated"   (entries actually in llms-full)
  - "(~<KB> KB)"                                 (llms-full.txt size)
This normalizer rewrites just those numbers from the on-disk truth, leaving
all curated prose untouched. Idempotent. Runs AFTER _gen_llms_full.py so the
corpus size + entry count are current.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
# Generation-independent article marker: every article (and its EN mirror)
# carries a MedicalWebPage JSON-LD node; hubs/index pages do not. (The older
# id="proseZh" marker missed EN mirrors built by an earlier generator.)
MARKER = '"@type":"MedicalWebPage"'
DATE_RE = re.compile(r'"dateModified":"(\d{4}-\d{2}-\d{2})"')


def count_articles(glob_pat: str) -> int:
    n = 0
    for p in ROOT.glob(glob_pat):
        try:
            if MARKER in p.read_text(encoding="utf-8"):
                n += 1
        except OSError:
            continue
    return n


def newest_date() -> str:
    newest = ""
    for p in ROOT.glob("blog/*.html"):
        try:
            m = DATE_RE.search(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        if m and m.group(1) > newest:
            newest = m.group(1)
    return newest


def main() -> int:
    llms = ROOT / "llms.txt"
    full = ROOT / "llms-full.txt"
    if not llms.exists():
        print("llms.txt missing; skipped")
        return 0

    zh = count_articles("blog/*.html")
    en = count_articles("en/blog/*.html")
    # CODE_REVIEW TD-44 — measure the DEPLOYED (LF) size, not raw on-disk bytes.
    # git stores LF and Vercel serves LF, but a Windows checkout has llms-full.txt
    # in CRLF, which is ~11 KB larger. With stat().st_size every local build wrote
    # "~589 KB" and every CI build wrote "~578 KB", so the two ping-ponged forever
    # in git history — and the figure advertised to AI crawlers did not match the
    # file they actually fetch. Same class as TD-34.
    kb = round(len(full.read_bytes().replace(b"\r\n", b"\n")) / 1024) if full.exists() else 0
    entries = 0
    if full.exists():
        entries = len(set(re.findall(r"chendermatologist\.com/blog/([a-z0-9-]+)", full.read_text(encoding="utf-8"))))

    newest = newest_date()

    s = llms.read_text(encoding="utf-8")
    orig = s
    s = re.sub(r"\d+ published articles \+ \d+ EN mirrors", f"{zh} published articles + {en} EN mirrors", s)
    if entries:
        s = re.sub(r"all \d+ published articles concatenated", f"all {entries} published articles concatenated", s)
        s = re.sub(r"with all \d+ articles \+ metadata", f"with all {entries} articles + metadata", s)
    if kb:
        s = re.sub(r"~\d+ KB", f"~{kb} KB", s)
    if newest:
        s = re.sub(r"Last updated: \d{4}-\d{2}-\d{2}", f"Last updated: {newest}", s)

    if s != orig:
        llms.write_text(s, encoding="utf-8", newline="\n")
        print(f"Refreshed llms.txt counts — {zh} zh / {en} EN / {entries} in corpus / ~{kb} KB")
    else:
        print("llms.txt counts already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
