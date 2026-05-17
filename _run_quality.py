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
    [PY, "_gen_en_pages.py"],
    [PY, "_normalize_schema.py", "--include-en"],
    [PY, "_normalize_social_urls.py"],
    [PY, "_normalize_third_party.py"],
    [PY, "_normalize_external_links.py"],
    [PY, "_normalize_button_types.py"],
    [PY, "_normalize_css_links.py"],
    [PY, "_normalize_heading_structure.py"],
    [PY, "_gen_feeds.py"],
    [PY, "_normalize_robots.py"],
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
