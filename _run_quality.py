from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence


PY = sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"

REGEN_STEPS: list[list[str]] = [
    # CODE_REVIEW TD-46 — _normalize_bilingual_attrs.py was removed from
    # this list on 2026-08-01. It was a one-shot migration carrying
    # hardcoded copies of four blocks and rewriting pages back to them;
    # the migration finished long ago (it changes 0 files today) but
    # while it stayed here, rewording any of those blocks would have been
    # silently reverted by the next build. _check_bilingual_attrs.py in
    # CHECK_STEPS guards the same contract structurally instead.
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
    # Resolve git-derived freshness before generating EN mirrors, feeds,
    # LLM corpora, and search artifacts. Running this after llms-full used
    # to leave aggregate freshness metadata one build behind.
    [PY, "_normalize_date_modified.py"],
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
    # 2026-05-21 — Emit a DefinedTermSet JSON-LD block with all 64
    # /glossary terms (SCORAD/PASI/EASI/DLQI/IL-17/JAK/etc.) so each
    # surfaces a SERP definition rich-card on its own. Major impressions
    # win for medical-term queries that currently miss the long-form
    # article cards. Deep-link via #anchor URL to scroll-to-text.
    [PY, "_normalize_glossary_schema.py"],
    # 2026-05-21 — Emit a WebApplication @graph for /tools' 10 calculators
    # (SCORAD/PASI/DLQI/SALT/UAS7/GAGS/MASI/Hurley/Norwood/Fitzpatrick).
    # applicationCategory=MedicalApplication + isAccessibleForFree=true
    # qualifies the entries for Google's "free interactive tool" rich-card.
    # Deep-link URL points to the calculator anchor inside the host article.
    [PY, "_normalize_tools_schema.py"],
    # 2026-05-21 — Stitch each article's body to the glossary schema graph:
    # scan body text for DefinedTerm names + acronyms + ASCII drug-name
    # prefixes, rank by occurrence count, emit a `mentions` array on the
    # MedicalWebPage with DefinedTerm @id refs (cap 10/article). Tells
    # Google + LLM crawlers which canonical definitions this article
    # references. Must run AFTER _normalize_glossary_schema.py so term
    # @ids are stable. ~217 mentions across 48 articles.
    [PY, "_normalize_mentions.py"],
    # 2026-05-22 — Auto-derive `isBasedOn` from the citation @graph:
    # filter ScholarlyArticles by authority-guideline keywords (AAD /
    # EADV / ETFAD / S3 / Consensus / "guidelines of care") and emit
    # top 5 as isBasedOn on MedicalWebPage. Makes the article→authority
    # chain explicit for Google's E-E-A-T scoring + LLM crawler trust.
    # Must run AFTER _normalize_citations.py so #dn-citations exists.
    [PY, "_normalize_is_based_on.py"],
    # 2026-05-26 — Inline the critical sticky-nav CSS (.dn-nav family) into
    # every page's <head> as <style id="dn-nav-critical">. The nav is the
    # most above-the-fold element on every page but its CSS otherwise lives
    # only in the separately-versioned assets/dn-below-fold.css; twice the
    # homepage nav rendered as an unstyled run-together blob because a
    # cached copy of that CSS predated its dn-nav rules (content edited
    # without a ?v= bump → cache-first SW never re-fetched). Inlining makes
    # the nav markup + its critical styling atomic (same document, same
    # cache entry) so they can never desync. Runs LAST in REGEN, after
    # _normalize_critical_css.py, so the block is never disturbed.
    [PY, "_inject_nav_critical.py"],
    # 2026-05-31 - add scope=col to every <thead> <th> (WCAG 1.3.1). Runs last
    # in REGEN so it also covers freshly-generated EN mirrors. Idempotent.
    [PY, "_normalize_th_scope.py"],
    # 2026-05-31 - emit FAQPage JSON-LD for articles whose FAQ uses the
    # .qa pattern (newer research articles) instead of <details><summary>.
    # Runs after _gen_en_pages so EN mirrors (English visible text) get an
    # English FAQPage too. Idempotent; skips hand-authored FAQPage blocks.
    [PY, "_gen_faq_from_qa.py"],
    # 2026-05-31 - label the breadcrumb <nav> (WCAG 1.3.6: articles have two
    # nav landmarks - breadcrumb + related-articles - and each needs a unique
    # accessible name). Idempotent, additive. Runs after EN gen.
    [PY, "_normalize_breadcrumb_aria.py"],
    # 2026-06-23 - aggregate every article's data-faq-auto FAQPage Q&A into a
    # single static /ai/faq.json for AI answer engines + RAG. Runs LAST so all
    # FAQPage blocks (zh + EN mirror) already exist. Deterministic (date from
    # newest article), so it never churns git on unchanged content.
    [PY, "_gen_ai_faq.py"],
    # 2026-06-23 - emit /ai/service.json, a machine-readable service descriptor
    # (who/what/tracks/endpoints/AI-policy) — the 4th AI-discovery surface
    # alongside ai.txt + summary.json + faq.json. Deterministic.
    [PY, "_gen_ai_service.py"],
    # 2026-06-23 - refresh the 3 stale counts inside the hand-curated llms.txt
    # (article/EN-mirror counts, corpus entry count, corpus KB) from on-disk
    # truth. Runs after _gen_llms_full.py so the size/entries are current.
    [PY, "_normalize_llms_counts.py"],
]

BUILD_GENERATED_STEPS: list[list[str]] = [
    [PY, "_gen_search_index.py"],
    # 2026-05-17 — Pagefind CJK-aware full-text search index. Runs AFTER all
    # HTML is generated (REGEN_STEPS) so it crawls the final on-disk file
    # tree. Non-fatal: skips gracefully if npx unavailable.
    [PY, "_run_pagefind.py"],
    # CODE_REVIEW TD-28 — _minify is a GENERATOR (it writes blog/*.min.js), so
    # it belongs in the generate phase, not after the checks. Moved here from
    # POST_BUILD_STEPS so that (a) `_check_min_sync.py` in CHECK_STEPS sees a
    # freshly-minified tree during `build`, and (b) `_check_performance_budget`
    # / `_check_js_syntax` audit the min files this build actually produced
    # instead of the previous build's. Kept after pagefind to preserve the
    # existing pagefind→minify relative order.
    [PY, "_minify.py"],
    # CODE_REVIEW TD-04 — must run AFTER _minify: minification rewrites inline
    # script bodies, and a CSP hash has to be of the bytes that actually ship.
    # _check_deployment.py (CHECK_STEPS) then asserts the CSP covers every
    # inline script in the built HTML, so an edit without a rebuild fails the
    # gate instead of silently losing that script in production.
    [PY, "_gen_csp_hashes.py"],
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
    # 2026-05-26 — guard the inline sticky-nav critical CSS (see
    # _inject_nav_critical.py); fails loudly if a dn-nav page ever loses its
    # <style id="dn-nav-critical"> block (e.g. via a REGEN reorder).
    [PY, "_check_nav_critical.py"],
    [PY, "_check_performance_budget.py"],
    [PY, "_check_text_integrity.py"],
    # CODE_REVIEW TD-64 — absolute-cure / sponsorship claims. The repo marked
    # these `level: error` in styles/DermNotes/BannedYMYL.yml, but the only
    # thing that ran them was vale.yml on `pull_request`, and this repo has
    # never had a PR. Negation-aware, because the corpus's one match is the
    # responsible sentence "現有療法皆無法保證根治".
    [PY, "_check_ymyl_claims.py"],
    [PY, "_check_en_internal_links.py"],
    [PY, "_check_third_party.py"],
    [PY, "_check_external_links.py"],
    [PY, "_check_button_types.py"],
    [PY, "_check_html_escape.py"],
    [PY, "_check_html_balance.py"],
    [PY, "_check_article_runtime.py"],
    [PY, "_check_deployment.py"],
    [PY, "_check_api_security.py"],
    [PY, "_check_frontend_security.py"],
    # CODE_REVIEW TD-31 — broad-scan companion to the two above. They are
    # string-contract regression locks over a fixed file list, so a NEW
    # api/admin/frontend file is unaudited and a new sink shape slips past. This
    # globs the whole security surface, hard-forbids eval/new Function/
    # document.write/outerHTML, and requires innerHTML to live only in files on
    # a reviewed allowlist.
    [PY, "_check_dangerous_sinks.py"],
    [PY, "_check_secrets.py"],
    [PY, "_check_supply_chain.py"],
    [PY, "_check_js_syntax.py"],
    # CODE_REVIEW TD-28 — _check_js_syntax only proves the min files are valid
    # JS, not that they still match their sources. Without this, editing a
    # bundle and running only `check` (the push gate) would happily ship a stale
    # .min.js. Asserts js_minify(source) == committed min for every bundle.
    [PY, "_check_min_sync.py"],
    # 2026-05-18 — Lock in SERP CTR/impressions signals shipped in
    # batches 12-17 (robots SERP directives, JSON-LD enrichment,
    # OG article:* on every blog article, Organization+logo on
    # homepage, sitemap encoding). Each missing signal directly
    # reduces SERP visibility or rich-card eligibility.
    [PY, "_check_bilingual_attrs.py"],
    [PY, "_check_seo_signals.py"],
    # 2026-05-19 — Tier 2D guard: every blog article's H1 + lead
    # paragraph must render from raw HTML (not be JS-injected).
    # Googlebot's first pass + AI/LLM crawlers don't always run JS.
    [PY, "_check_no_js_render_dependency.py"],
]

POST_BUILD_STEPS: list[list[str]] = [
    # _minify.py moved to BUILD_GENERATED_STEPS (see TD-28 note there).
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
