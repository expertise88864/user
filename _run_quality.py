from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


PY = sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"

REGEN_STEPS: list[list[str]] = [
    [PY, "_sync_article_navigation.py"],
    [PY, "_gen_site_settings.py"],
    # Board-exam section (/exam/**), first pass: makes the page set exist so
    # _gen_feeds (sitemap) and the normalizers see every exam page. The final
    # pass at the end of this list re-renders on the finished notes.html shell.
    [PY, "_gen_exam.py"],
    # Complete static hub links from the public catalog before EN generation.
    [PY, "_sync_hub_catalog.py"],
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
    # Freeze source-generated heading identities before copying the source to
    # EN. Mirrors derive their own legacy fragments from explicit provenance.
    [PY, "_normalize_reading_shell.py"],
    # Resolve content-ledger dates before generating EN mirrors, feeds,
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
    [PY, "_normalize_reading_shell.py"],
    # Preserve native full-document navigation and the legacy a11y styles.
    [PY, "_normalize_native_navigation.py"],
    [PY, "_gen_feeds.py"],
    [PY, "_normalize_robots.py"],
    # Permit larger image previews and let Google choose snippet length.
    # Neither guarantees search appearance or CTR growth. Preserve noindex;
    # there is no universal 155-character snippet limit.
    [PY, "_normalize_robots_meta.py"],
    # Describe article sharing metadata and image dimensions.
    # Each platform decides presentation; no guaranteed chips or CTR gain.
    # Image dimensions alone do not establish Discover eligibility.
    [PY, "_normalize_og_article_meta.py"],
    # Offer speculative navigation in supported browsers.
    # Measure activated navigation benefit and resource waste; do not promise
    # ranking gains, mobile data savings, or a fixed INP improvement.
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
    # Extract print rules to shared media="print" CSS.
    # Browsers may fetch it before printing at lower priority; it does not
    # block screen rendering. Saves repeated inline bytes, not all requests.
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
    # Preserve curated topic-neighbor metadata; no ranking or crawl-budget
    # improvement is established by rel=prev/next alone.
    [PY, "_inject_cluster_nav.py"],
    # Add diagnosis-code metadata after schema normalization.
    # No dedicated Google Medical Q&A feature or ranking gain is promised.
    # Existing clinical mappings still require editorial validation.
    [PY, "_normalize_medical_codes.py"],
    # Remove historical standalone Drug JSON-LD blocks (cleanup mode).
    # Current main() does not generate the retained legacy Drug mappings.
    # Do not promise a medication rich card or invent offers/reviews.
    [PY, "_normalize_drug_schema.py"],
    # Describe visible references with a citation graph.
    # PMID/DOI links retain the bibliography without automatic E-E-A-T
    # certification or a promised Sources search-result feature.
    [PY, "_normalize_citations.py"],
    # 2026-05-21 — Final pass over MedicalWebPage / MedicalScholarlyArticle
    # JSON-LD: inject `keywords` (from homepage data-tag-en + alternateName),
    # lastReviewed from the author ledger (or retain existing), and differentiate
    # `audience.audienceType` (Patient default, Patient+Clinician for
    # clinical-depth slugs). Must run LAST so previously-injected fields
    # like `about` are stable when we harvest alternateName from them.
    [PY, "_normalize_article_metadata.py"],
    # Describe visible glossary definitions and canonical anchors.
    # DefinedTermSet is not a dedicated Google definition rich-result type;
    # no automatic scroll-to-text, impressions, or CTR gain is promised.
    [PY, "_normalize_glossary_schema.py"],
    # Describe visible calculators with WebApplication metadata.
    # applicationCategory alone does not establish software-app eligibility.
    # Do not invent ratings or offers. Preserve existing calculator anchors.
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
    # links explicit as metadata, without automatic E-E-A-T or trust scoring.
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
    # 2026-10-18 - make every /en JSON-LD block English (citation/isBasedOn
    # names via the zh reference list's data-en, related-article titles,
    # author/keywords/glossary @id) and rebuild /en isBasedOn from the final zh
    # citation graph so ONE regeneration settles it (isBasedOn used to need two
    # runs because _normalize_is_based_on.py runs after _gen_en_pages.py).
    # Must stay after every step that writes /en JSON-LD and before
    # _gen_ai_faq.py, which aggregates the /en FAQPage blocks.
    [PY, "_localize_en_jsonld.py"],
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
    # Board-exam section, final pass: exam/** copies the notes.html shell, so
    # it must run after every step above that edits notes.html (e.g. the
    # ASSET_VERSION ?v= rewrite) or a version bump needs two builds to settle.
    [PY, "_gen_exam.py"],
]

BUILD_GENERATED_STEPS: list[list[str]] = [
    [PY, "_gen_search_index.py"],
    # 2026-05-17 — Pagefind CJK-aware full-text search index. Runs AFTER all
    # HTML is generated (REGEN_STEPS) so it crawls the final on-disk file
    # tree. Missing npx fails generation; do not publish a partial index.
    [PY, "_run_pagefind.py"],
    # CODE_REVIEW TD-28 — _minify is a GENERATOR (it writes blog/*.min.js), so
    # it belongs in the generate phase, not after the checks. Moved here from
    # POST_BUILD_STEPS so that (a) `_check_min_sync.py` in CHECK_STEPS sees a
    # freshly-minified tree during `build`, and (b) `_check_performance_budget`
    # / `_check_js_syntax` audit the min files this build actually produced
    # instead of the previous build's. Kept after pagefind to preserve the
    # existing pagefind→minify relative order.
    ["node", "_build_editor.mjs"],
    [PY, "_minify.py"],
    [PY, "_gen_asset_release.py", "--write"],
    # CODE_REVIEW TD-04 — must run AFTER _minify: minification rewrites inline
    # script bodies, and a CSP hash has to be of the bytes that actually ship.
    # _check_deployment.py (CHECK_STEPS) then asserts the CSP covers every
    # inline script in the built HTML, so an edit without a rebuild fails the
    # gate instead of silently losing that script in production.
    [PY, "_gen_csp_hashes.py"],
]

CHECK_STEPS: list[list[str]] = [
    [PY, "_gen_site_settings.py", "--check"],
    [PY, "_gen_exam.py", "--check"],
    # exam.js progress: per-chapter statistics vs. site-wide records, on the
    # real generated pages (parse5 DOM + in-memory localStorage).
    ["node", "--test", "_test_exam_progress.mjs"],
    # 「考試當年 vs 現行觀念」 data rules (qid, sources with urls, impact level,
    # no simplified characters) and placement inside the answer reveal.
    [PY, "-m", "unittest", "_test_exam_timemachine"],
    [PY, "_test_site_settings_data.py"],
    [PY, "-m", "unittest", "_test_site_settings_render"],
    [PY, "-m", "unittest", "_test_site_settings_delivery"],
    [PY, "-m", "unittest", "_test_site_settings_preparation"],
    [PY, "-m", "unittest", "_test_site_settings_retirement"],
    ["node", "--test", "_test_site_settings_delivery.cjs"],
    ["node", "--test", "_test_settings_delivery_integration.cjs"],
    ["node", "--test", "_test_site_settings.cjs", "_test_site_settings_client.cjs", "_test_popular_picks.cjs"],
    [PY, "_test_native_navigation.py"],
    ["node", "_build_editor.mjs", "--check"],
    ["node", "--test", "_test_word_editor_source.mjs"],
    ["node", "--test", "_test_editor_artifacts.mjs"],
    ["node", "--test", "_test_article_publication.cjs"],
    [PY, "_test_asset_release.py"],
    [PY, "_test_csp_source_scope.py"],
    [PY, "_test_heading_source_scope.py"],
    [PY, "_test_performance_migrations.py"],
    [PY, "_test_css_background_alpha.py"],
    [PY, "_gen_asset_release.py", "--check"],
    [PY, "_test_release.py"],
    [PY, "_test_translation_failures.py"],
    [PY, "_test_link_fragments.py"],
    [PY, "_test_article_candidate.py"],
    [PY, "_test_article_request.py"],
    [PY, "_test_article_visibility.py"],
    [PY, "_test_cms_delivery.py"],
    [PY, "_test_cms_generated_package.py"],
    [PY, "_test_cms_patient_package.py"],
    [PY, "_test_cms_patient_review.py"],
    [PY, "_test_cms_patient_rebuild.py"],
    [PY, "_test_patient_review_preparation.py"],
    [PY, "_test_patient_release_preparation.py"],
    [PY, "_test_patient_request_discovery.py"],
    [PY, "_test_generation_clock.py"],
    [PY, "_test_quality_runner.py"],
    [PY, "_test_cms_retirement.py"],
    [PY, "_test_patient_review_retirement.py"],
    ["node", "--test", "_test_cms_delivery.cjs", "_test_vercel_gate.cjs"],
    [PY, "_test_scheduled_candidate.py"],
    [PY, "-m", "unittest", "_test_indexnow_delivery"],
    ["node", "--test", "_test_serve.mjs", "_test_runtime_edges.mjs", "_test_reset_cache.mjs", "_test_article_prefetch.mjs", "_test_admin_skeleton.mjs", "_test_admin_sessions.cjs", "_test_admin_persistence.cjs", "_test_article_draft.cjs", "_test_article_draft_client.cjs", "_test_navigation.cjs", "_test_search_integrity.cjs", "_test_analytics.cjs", "_test_font_loader.cjs"],
    [PY, "_test_navigation_generation.py"],
    [PY, "_test_search_scope.py"],
    [PY, "_test_search_index_visibility.py"],
    [PY, "_test_og_card_sources.py"],
    [PY, "_gen_og_cards.py", "--check"],
    [PY, "_test_review_fixes.py"],
    [PY, "-m", "unittest", "_test_codex_review_identity"],
    [PY, "_test_legacy_maintenance.py"],
    [PY, "_test_dashboard.py"],
    [PY, "_test_reading_metrics.py"],
    [PY, "_check_meta.py", "--fast"],
    [PY, "_check_metadata_uniqueness.py"],
    [PY, "_check_robots.py"],
    [PY, "_check_sitemap.py"],
    [PY, "_check_internal_links.py"],
    [PY, "_check_index_boundaries.py"],
    [PY, "-m", "unittest", "_test_static_a11y_ids"],
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
    # Production serves only the staged public site (dist/), never the repository.
    [PY, "-m", "unittest", "_test_site_publish"],
    [PY, "_check_deploy_exposure.py"],
    [PY, "_check_api_security.py"],
    [PY, "_check_frontend_security.py"],
    # CODE_REVIEW TD-31 — broad-scan companion to the two above. They are
    # string-contract regression locks over a fixed file list, so a NEW
    # api/admin/frontend file is unaudited and a new sink shape slips past. This
    # globs the whole security surface, hard-forbids eval/new Function/
    # document.write/outerHTML, and requires innerHTML to live only in files on
    # a reviewed allowlist.
    [PY, "_test_dangerous_sinks.py"],
    [PY, "_check_dangerous_sinks.py"],
    [PY, "_check_secrets.py"],
    [PY, "_check_supply_chain.py"],
    [PY, "_check_js_syntax.py"],
    # CODE_REVIEW TD-28 — _check_js_syntax only proves the min files are valid
    # JS, not that they still match their sources. Without this, editing a
    # bundle and running only `check` (the push gate) would happily ship a stale
    # .min.js. Asserts js_minify(source) == committed min for every bundle.
    [PY, "_check_min_sync.py"],
    # Preserve bilingual and search metadata contracts.
    # Consistency checks do not prove each field raises rankings or enables
    # a rich result. Measure actual impressions, clicks, and reading behavior.
    [PY, "_check_bilingual_attrs.py"],
    [PY, "_check_hant_only.py"],
    # 2026-10-17 — the retired _fix_proseen_cjk.py once str.replace'd visible
    # Chinese into English on 53 zh articles; English belongs in data-en only.
    [PY, "_test_zh_english_prose.py"],
    [PY, "_check_zh_english_prose.py"],
    # 2026-10-18 — /en structured data must be English (alternateName exempt);
    # the visible-text en-leak scan never looked at <head>.
    [PY, "_test_en_jsonld_cjk.py"],
    [PY, "_check_en_jsonld_cjk.py"],
    [PY, "_check_seo_signals.py"],
    # 2026-05-19 — Tier 2D guard: every blog article's H1 + lead
    # paragraph must render from raw HTML (not be JS-injected).
    # Googlebot's first pass + AI/LLM crawlers don't always run JS.
    [PY, "_check_no_js_render_dependency.py"],
    [PY, "_sync_hub_catalog.py", "--check"],
    [PY, "_test_hub_catalog.py"],
    [PY, "_test_articles_desc.py"],
    [PY, "_test_related_articles.py"],
]

# Check scheduling (2026-10-16). CHECK_STEPS keeps every check, its arguments
# and its order; only the wall-clock schedule changes. `check` and `build` run
# them in a bounded pool (min(4, CPUs); DN_QUALITY_JOBS=1 restores the serial
# runner). Each check's stdout+stderr is buffered and printed in list order
# under its usual "+ command" line. The first failing check in LIST order
# fails the build with the same "[FAIL] <command> exited with <code>" line and
# exit code as before; checks after it are not started (queued ones are
# cancelled, running ones are awaited) and their output is not printed.
#
# Classification: every CHECK_STEPS entry is currently PARALLEL (read-only).
# Each one was run alone and every checkout file and this worktree's git
# metadata (size + mtime) compared before/after: none writes. Tests write only
# inside their own tempfile directories or fixture clones, child servers bind
# port 0, and every generator here runs in its --check mode, which compares
# without writing (_gen_site_settings, _gen_exam, _build_editor, _gen_asset_
# release, _gen_og_cards, _sync_hub_catalog). No check consumes another
# check's output; generators stay serial in REGEN/BUILD_GENERATED_STEPS.
# A future check that writes to the checkout, depends on an earlier check's
# effects or must not share the machine belongs in SERIAL_CHECK_STEPS: it then
# runs alone at its list position, after every earlier check has finished and
# before any later check starts, with live output.
SERIAL_CHECK_STEPS: list[list[str]] = []

POST_BUILD_STEPS: list[list[str]] = [
    # _minify.py moved to BUILD_GENERATED_STEPS (see TD-28 note there).
    [NPM, "run", "check-js"],
    [NPM, "run", "check-smoke"],
]


def label(command: Sequence[str]) -> str:
    return " ".join(command)


def check_jobs() -> int:
    """Concurrent check processes: min(4, CPUs); DN_QUALITY_JOBS=1 forces serial."""
    raw = os.environ.get("DN_QUALITY_JOBS", "").strip()
    if not raw:
        return max(1, min(4, os.cpu_count() or 1))
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError("DN_QUALITY_JOBS must be a positive integer")
    return int(raw)


def _run_captured(command: Sequence[str]) -> tuple[int, bytes]:
    # Output goes to a pipe instead of the console, so pin Python children to
    # UTF-8 (a Windows locale codec cannot encode every CJK message). Linux
    # builds already use UTF-8; nothing else about the environment changes.
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    return result.returncode, result.stdout


def _emit(output: bytes) -> None:
    text = output.decode("utf-8", errors="replace")
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))
    sys.stdout.flush()


def _run_concurrently(steps: Sequence[Sequence[str]], jobs: int) -> None:
    serial = [list(command) for command in SERIAL_CHECK_STEPS]
    pool = ThreadPoolExecutor(max_workers=jobs)
    try:
        index = 0
        while index < len(steps):
            if list(steps[index]) in serial:
                # Barrier: every earlier check has finished; none later started.
                print(f"+ {label(steps[index])}", flush=True)
                subprocess.run(steps[index], check=True)
                index += 1
                continue
            stop = index
            while stop < len(steps) and list(steps[stop]) not in serial:
                stop += 1
            batch = list(steps[index:stop])
            futures = [pool.submit(_run_captured, command) for command in batch]
            for position, (command, future) in enumerate(zip(batch, futures)):
                code, output = future.result()
                print(f"+ {label(command)}", flush=True)
                _emit(output)
                if code != 0:
                    for pending in futures[position + 1:]:
                        pending.cancel()
                    raise subprocess.CalledProcessError(code, command)
            index = stop
    finally:
        # Never leave a running check behind; queued ones were cancelled above.
        pool.shutdown(wait=True, cancel_futures=True)


def run_steps(name: str, steps: Sequence[Sequence[str]], *, parallel: bool = False) -> None:
    print(f"\n== {name} ==", flush=True)
    jobs = check_jobs() if parallel else 1
    if jobs > 1:
        print(f"(read-only checks run {jobs} at a time; output is shown in list order)", flush=True)
        _run_concurrently(steps, jobs)
        return
    for command in steps:
        print(f"+ {label(command)}", flush=True)
        subprocess.run(command, check=True)


@contextlib.contextmanager
def fixed_point_scope() -> Iterator[None]:
    """Let the twice-run normalizers skip text this regeneration proved unchanged."""
    from _regen_fixed_points import ENV

    previous = os.environ.get(ENV)
    with tempfile.TemporaryDirectory(prefix="dn-regen-") as directory:
        os.environ[ENV] = directory
        try:
            yield
        finally:
            if previous is None:
                os.environ.pop(ENV, None)
            else:
                os.environ[ENV] = previous


def regeneration_steps(content_date: str | None = None) -> list[list[str]]:
    """Bind the content clock without changing the shared pipeline recipe."""
    steps = [list(command) for command in REGEN_STEPS]
    if content_date is None:
        return steps
    from _normalize_date_modified import content_date_argument

    frozen_date = content_date_argument(content_date)
    target = [PY, "_normalize_date_modified.py"]
    matches = [command for command in steps if command == target]
    if len(matches) != 1:
        raise ValueError("expected exactly one content-date generation step")
    matches[0].extend(["--content-date", frozen_date])
    return steps


def main(argv: Sequence[str] | None = None) -> int:
    from _normalize_date_modified import content_date_argument

    parser = argparse.ArgumentParser(description="Generate and validate the complete site.")
    parser.add_argument("mode", nargs="?", default="build", choices=("regen", "check", "build"))
    parser.add_argument("--content-date", type=content_date_argument,
                        help="freeze the date for new or changed prose during generation")
    args = parser.parse_args(argv)
    if args.mode == "check" and args.content_date is not None:
        parser.error("--content-date requires regen or build; check does not generate files")
    mode = args.mode
    if mode in {'regen', 'build'}:
        from _cms_patient_review import frozen_content_date
        approved_date = frozen_content_date(Path(__file__).resolve().parent)
        if approved_date is not None:
            if args.content_date is not None and args.content_date != approved_date:
                raise ValueError('Generation date differs from the recorded patient package')
            args.content_date = approved_date
    try:
        if mode == "regen":
            with fixed_point_scope():
                run_steps("Regenerate generated site files", regeneration_steps(args.content_date))
        elif mode == "check":
            run_steps("Run quality checks", CHECK_STEPS, parallel=True)
        elif mode == "build":
            with fixed_point_scope():
                run_steps("Regenerate generated site files", regeneration_steps(args.content_date))
            run_steps("Generate build artifacts", BUILD_GENERATED_STEPS)
            run_steps("Run quality checks", CHECK_STEPS, parallel=True)
            run_steps("Finalize and smoke-test build", POST_BUILD_STEPS)
    except subprocess.CalledProcessError as exc:
        print(f"\n[FAIL] {label(exc.cmd)} exited with {exc.returncode}")
        return exc.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
