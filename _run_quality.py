from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence


PY = sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"

REGEN_STEPS: list[list[str]] = [
    [PY, "_normalize_bilingual_attrs.py"],
    [PY, "_normalize_schema.py"],
    [PY, "_normalize_social_images.py"],
    [PY, "_normalize_css_links.py"],
    [PY, "_normalize_heading_structure.py"],
    # 2026-05-17 — SSG-render related-articles cards BEFORE _gen_en_pages
    # so the EN mirror inherits them. Each blog/*.html gets 4 internal
    # links injected pre-</main>; runtime DN.addRelatedArticles bails
    # early when it sees #dn-related-static. ~174 internal links added,
    # all crawlable by Googlebot without JS.
    [PY, "_inject_related.py"],
    # Refresh 404.html "popular articles" with 6 newest from DN.ARTICLES
    # so the list doesn't drift as new content lands.
    [PY, "_inject_404.py"],
    [PY, "_gen_en_pages.py"],
    [PY, "_normalize_schema.py", "--include-en"],
    # 2026-05-18 — Inject visible reading-time badge under each H1
    # using the timeRequired + wordCount values that _normalize_schema
    # just wrote into JSON-LD. Runs after --include-en so EN articles
    # use EN-specific reading times (smaller body, lower minute count).
    [PY, "_inject_reading_time.py"],
    [PY, "_normalize_social_urls.py"],
    [PY, "_normalize_third_party.py"],
    [PY, "_normalize_external_links.py"],
    [PY, "_normalize_button_types.py"],
    [PY, "_normalize_css_links.py"],
    [PY, "_normalize_heading_structure.py"],
    [PY, "_gen_feeds.py"],
    [PY, "_normalize_robots.py"],
    # 2026-05-18 — Inject max-image-preview:large + max-snippet:-1 into
    # every page's <meta name="robots">. Largest single-action CTR uplift:
    # unlocks LARGE image previews (vs tiny default thumbs) and FULL
    # snippet length (vs 155-char truncation) in Google SERPs. Safe to
    # apply site-wide; preserves any existing noindex.
    [PY, "_normalize_robots_meta.py"],
    # 2026-05-18 — Inject OpenGraph article:* + Twitter custom labels +
    # og:image dimensions into every article. Major off-Google CTR uplift:
    # Facebook / LinkedIn / Discord / Slack render shared cards with
    # author + date + section + tag chips; Twitter shows reading time
    # underneath the title; Google Discover requires width/height to
    # classify image for the large card variant.
    [PY, "_normalize_og_article_meta.py"],
    # 2026-05-18 — Inject Speculation Rules so cross-article navigation
    # prerenders on hover. Drops bounce + improves INP (Core Web Vital)
    # + improves engagement signals Google uses for ranking. Each page
    # gets the same prerender(/blog/*) + prefetch(/*) rule set; pages
    # with a native (homepage) speculationrules block are left alone.
    [PY, "_inject_speculation_rules.py"],
    # 2026-05-18 — Regenerate llms-full.txt (concatenated clean article
    # text for AI/LLM crawlers like Perplexity, ChatGPT, Claude). Runs
    # AFTER schema/og normalization so the metadata embedded in each
    # article section reflects the latest dateModified + timeRequired.
    [PY, "_gen_llms_full.py"],
    # 2026-05-18 — Inject <link rel="search"> pointing at opensearch.xml
    # so Firefox/Edge/Brave readers see "Add Search Engine" prompt and
    # can search the site from their browser URL bar (recurring visits).
    [PY, "_normalize_head_extras.py"],
    # 2026-05-19 — Sync `desc` + `desc_en` fields in DN.ARTICLES from
    # each article's <meta name="description"> tag. Powers the subtitle
    # <p> on /blog/ dynamic article-list cards (blog-hub.js renderer).
    # Must run AFTER everything that touches each article's meta
    # description (notably _normalize_schema.py).
    [PY, "_normalize_articles_desc.py"],
    # 2026-05-19 — Tier 2D from OPEN_SOURCE_INTEGRATIONS.md:
    # emit /.well-known/ai.txt + /ai/summary.json so emerging AI bot
    # standards and machine-readable site-summary consumers have a
    # canonical surface (parallel to robots.txt / llms.txt).
    [PY, "_normalize_ai_well_known.py"],
    # 2026-05-20 — Round 2-H from OPEN_SOURCE_INTEGRATIONS.md:
    # extract @media print rules from inline <style> blocks to a
    # shared external CSS loaded with media="print" so browsers
    # only fetch when printing. ~1 KB savings per page × 114 pages
    # = ~110 KB redundant inline weight removed site-wide.
    [PY, "_normalize_critical_css.py"],
    # 2026-05-20 — Round 2-K visualization: regenerate the
    # internal-link force-directed SVG after every catalog change.
    [PY, "_gen_site_graph.py"],
    # 2026-05-20 — Auto-bump JSON-LD dateModified + OG article:
    # modified_time to each article's last git-touched date. Fixes
    # GSC "Crawled — currently not indexed" caused by stale freshness
    # signal (dateModified never moved despite ~22 batches of SEO
    # + schema upgrades). Must run AFTER every other normalizer so
    # the date reflects the FINAL post-build state.
    [PY, "_normalize_date_modified.py"],
    # 2026-05-21 — SEO_AUDIT A2: strip '廣告位 · AdSense' placeholder
    # text from ad-slot divs so Googlebot stops indexing the empty-
    # ad-inventory signal. CSS rule .ad-slot{display:none!important}
    # already hides them visually; this clears Googlebot's read.
    [PY, "_normalize_ad_slots.py"],
    # 2026-05-21 — SEO_AUDIT C4: inject <link rel="prev/next"> for
    # 8 curated article clusters (atopic-dermatitis, psoriasis, etc.).
    # Strengthens topic-cluster signal + crawl-budget allocation hint
    # for Googlebot.
    [PY, "_inject_cluster_nav.py"],
    # 2026-05-21 — Inject ICD-10/SNOMED/MeSH codes into MedicalCondition
    # `about` fields. Eligible for Google Medical Q&A rich results;
    # discoverable via medical-professional diagnosis-code search.
    # Must run AFTER _normalize_schema (which sets the about field
    # baseline) and AFTER any --include-en pass so EN mirrors get codes too.
    [PY, "_normalize_medical_codes.py"],
    # 2026-05-21 — Inject Drug JSON-LD blocks for drug-focused articles
    # (isotretinoin, dupilumab, biologics, topical retinoids/steroids/acids).
    # Eligible for Google "About this medication" rich-card. ATC codes +
    # Wikidata + DrugBank cross-references for Knowledge Graph linkage.
    [PY, "_normalize_drug_schema.py"],
    # 2026-05-21 — Parse <ol class="references"> Vancouver citations and
    # emit a ScholarlyArticle @graph as #dn-citations JSON-LD. Powers
    # E-E-A-T (peer-reviewed source trail), SERP "Sources: N publications",
    # and AI-crawler trust signals (Perplexity / ChatGPT / Claude). PMID
    # + DOI identifiers cross-link to PubMed + Crossref.
    [PY, "_normalize_citations.py"],
    # 2026-05-21 — Final pass over MedicalWebPage / MedicalScholarlyArticle
    # JSON-LD: inject `keywords` (from homepage data-tag-en + alternateName),
    # `lastReviewed` (git last-modified date), and differentiate
    # `audience.audienceType` (Patient default, Patient+Clinician for
    # clinical-depth slugs). Must run LAST so previously-injected fields
    # like `about` are stable when we harvest alternateName from them.
    [PY, "_normalize_article_metadata.py"],
]

BUILD_GENERATED_STEPS: list[list[str]] = [
    [PY, "_gen_search_index.py"],
    # 2026-05-17 — Pagefind CJK-aware full-text search index. Runs AFTER all
    # HTML is generated (REGEN_STEPS) so it crawls the final on-disk file
    # tree. Non-fatal: skips gracefully if npx unavailable.
    [PY, "_run_pagefind.py"],
]

CHECK_STEPS: list[list[str]] = [
    [PY, "_check_meta.py", "--fast"],
    [PY, "_check_metadata_uniqueness.py"],
    [PY, "_check_robots.py"],
    [PY, "_check_sitemap.py"],
    [PY, "_check_internal_links.py"],
    [PY, "_check_index_boundaries.py"],
    [PY, "_check_static_a11y.py"],
    [PY, "_check_inline_events.py"],
    [PY, "_audit_jsonld.py"],
    [PY, "_check_pwa.py"],
    [PY, "_check_performance_budget.py"],
    [PY, "_check_text_integrity.py"],
    [PY, "_check_en_internal_links.py"],
    [PY, "_check_third_party.py"],
    [PY, "_check_external_links.py"],
    [PY, "_check_button_types.py"],
    [PY, "_check_deployment.py"],
    [PY, "_check_api_security.py"],
    [PY, "_check_frontend_security.py"],
    [PY, "_check_secrets.py"],
    [PY, "_check_supply_chain.py"],
    [PY, "_check_js_syntax.py"],
    # 2026-05-18 — Lock in SERP CTR/impressions signals shipped in
    # batches 12-17 (robots SERP directives, JSON-LD enrichment,
    # OG article:* on every blog article, Organization+logo on
    # homepage, sitemap encoding). Each missing signal directly
    # reduces SERP visibility or rich-card eligibility.
    [PY, "_check_seo_signals.py"],
    # 2026-05-19 — Tier 2D guard: every blog article's H1 + lead
    # paragraph must render from raw HTML (not be JS-injected).
    # Googlebot's first pass + AI/LLM crawlers don't always run JS.
    [PY, "_check_no_js_render_dependency.py"],
]

POST_BUILD_STEPS: list[list[str]] = [
    [PY, "_minify.py"],
    [NPM, "run", "check-js"],
    [NPM, "run", "check-smoke"],
]


def label(command: Sequence[str]) -> str:
    return " ".join(command)


def run_steps(name: str, steps: Sequence[Sequence[str]]) -> None:
    print(f"\n== {name} ==", flush=True)
    for command in steps:
        print(f"+ {label(command)}", flush=True)
        subprocess.run(command, check=True)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "build"
    try:
        if mode == "regen":
            run_steps("Regenerate generated site files", REGEN_STEPS)
        elif mode == "check":
            run_steps("Run quality checks", CHECK_STEPS)
        elif mode == "build":
            run_steps("Regenerate generated site files", REGEN_STEPS)
            run_steps("Generate build artifacts", BUILD_GENERATED_STEPS)
            run_steps("Run quality checks", CHECK_STEPS)
            run_steps("Finalize and smoke-test build", POST_BUILD_STEPS)
        else:
            print("Usage: python _run_quality.py [regen|check|build]")
            return 2
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] {label(exc.cmd)} exited with {exc.returncode}")
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
