#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Inject <link rel="prev"> + <link rel="next"> hreflang-style cluster
navigation hints for article series.

SEO_AUDIT C4 — strengthens topic-cluster signal for series like
the 5-article atopic-dermatitis cluster. Google previously used
rel=prev/next as a strong signal (now treated as a discovery hint
rather than ranking factor since 2019, but still parsed and
helpful for crawl budget allocation).

Each cluster is a hand-curated ordered list. The first article gets
only rel="next"; the last gets only rel="prev"; middle ones get
both. Cluster membership is independent of TAG_CATEGORIES grouping
(which is for related-card scoring) — this is for SEQUENTIAL reading.

Idempotent via dn-cluster-nav marker.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
DOMAIN = "https://chendermatologist.com"

# Hand-curated reading order per cluster. Order matters — first to last
# is the recommended reading sequence. Slugs must exist in blog/ AND
# be indexable; unpublished or noindex articles get filtered out
# automatically.
CLUSTERS: list[list[str]] = [
    # Atopic dermatitis pillar: overview → topical → systemic → special pops → pediatric
    [
        "atopic-dermatitis-overview",
        "atopic-dermatitis-topical",
        "atopic-dermatitis-systemic",
        "atopic-dermatitis-special-populations",
        "pediatric-eczema",
    ],
    # Psoriasis pillar
    [
        "psoriasis-overview",
        "psoriasis-topical",
        "psoriasis-systemic",
        "psoriasis-special-populations",
        "psoriasis-myths",
        "psoriasis-biologic-monitoring",
    ],
    # Acne + isotretinoin: myth → scars → patient-level → clinical-level
    [
        "acne-myths",
        "acne-scar-treatment",
        "isotretinoin-patient",
        "isotretinoin-clinical",
    ],
    # Topical acids + steroids: patient → clinical → steroid guide
    [
        "topical-acids-patient",
        "topical-acids-clinical",
        "topical-steroids-guide",
    ],
    # Hair-loss pair
    [
        "hairloss-myths",
        "alopecia-areata",
    ],
    # Skin procedures: biopsy → laser → oral exam
    [
        "skin-biopsy-excision",
        "laser-dermatology",
        "dermatologic-oral-examination",
    ],
    # Viral skin infections
    [
        "warts-myths",
        "shingles-myths",
        "mpox-care",
    ],
    # Skin cancer / AK
    [
        "actinic-keratosis-scc",
        "cutaneous-t-cell-lymphoma",
        "targeted-therapy-skin",
    ],
]

MARKER_RE = re.compile(
    r'\s*<!-- dn-cluster-nav -->[\s\S]*?<!-- /dn-cluster-nav -->',
    re.IGNORECASE,
)


def is_indexable(html: str) -> bool:
    """True if no noindex robots meta."""
    return not re.search(r'<meta[^>]+name="robots"[^>]+content="[^"]*noindex',
                          html, re.I)


def inject_one(article_dir: Path, slug: str,
               prev_slug: str | None, next_slug: str | None,
               url_prefix: str) -> bool:
    fp = article_dir / f"{slug}.html"
    if not fp.exists():
        return False
    src = fp.read_text(encoding="utf-8")
    # Strip any prior dn-cluster-nav block
    cleaned = MARKER_RE.sub("", src)

    parts = ["\n<!-- dn-cluster-nav -->"]
    if prev_slug:
        parts.append(
            f'<link rel="prev" href="{DOMAIN}{url_prefix}{prev_slug}" />'
        )
    if next_slug:
        parts.append(
            f'<link rel="next" href="{DOMAIN}{url_prefix}{next_slug}" />'
        )
    parts.append("<!-- /dn-cluster-nav -->")
    block = "\n".join(parts)

    head_close = cleaned.find("</head>")
    if head_close == -1:
        return False
    new_src = cleaned[:head_close] + block + cleaned[head_close:]
    if new_src == src:
        return False
    fp.write_text(new_src, encoding="utf-8")
    return True


def main() -> int:
    zh_blog = ROOT / "blog"
    en_blog = ROOT / "en" / "blog"

    total_changed = 0

    for cluster in CLUSTERS:
        # Filter out slugs whose ZH article is noindex (cluster only
        # links between INDEXABLE articles to avoid dead-end signals).
        live_slugs = []
        for s in cluster:
            fp = zh_blog / f"{s}.html"
            if fp.exists() and is_indexable(fp.read_text(encoding="utf-8")):
                live_slugs.append(s)

        for i, slug in enumerate(live_slugs):
            prev_slug = live_slugs[i - 1] if i > 0 else None
            next_slug = live_slugs[i + 1] if i < len(live_slugs) - 1 else None
            # ZH side
            if inject_one(zh_blog, slug, prev_slug, next_slug, "/blog/"):
                total_changed += 1
            # EN side — only if EN file exists AND is indexable (else prev/next
            # would point to a dead-end noindex page)
            en_fp = en_blog / f"{slug}.html"
            if en_fp.exists() and is_indexable(en_fp.read_text(encoding="utf-8")):
                # Build EN cluster from EN-indexable subset
                en_live = [s for s in live_slugs
                           if (en_blog / f"{s}.html").exists()
                           and is_indexable((en_blog / f"{s}.html").read_text(encoding="utf-8"))]
                if slug in en_live:
                    idx = en_live.index(slug)
                    en_prev = en_live[idx - 1] if idx > 0 else None
                    en_next = en_live[idx + 1] if idx < len(en_live) - 1 else None
                    if inject_one(en_blog, slug, en_prev, en_next, "/en/blog/"):
                        total_changed += 1

    print(f"[cluster-nav] injected rel=prev/next links into "
          f"{total_changed} article files across {len(CLUSTERS)} clusters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
