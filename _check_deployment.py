from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def header_map(entry: dict) -> dict[str, str]:
    return {item.get("key", "").lower(): item.get("value", "") for item in entry.get("headers", [])}


def find_header_entry(config: dict, source: str) -> dict | None:
    for entry in config.get("headers", []):
        if entry.get("source") == source:
            return entry
    return None


def require_header(errors: list[str], config: dict, source: str, key: str, contains: str | None = None) -> None:
    entry = find_header_entry(config, source)
    if not entry:
        errors.append(f"vercel.json: missing headers entry for {source}")
        return
    headers = header_map(entry)
    value = headers.get(key.lower())
    if not value:
        errors.append(f"vercel.json: {source} missing {key}")
        return
    if contains and contains not in value:
        errors.append(f"vercel.json: {source} {key} should include {contains!r}")


def parse_csp(csp: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for part in csp.split(";"):
        tokens = part.strip().split()
        if tokens:
            directives[tokens[0]] = tokens[1:]
    return directives


def require_csp_source(errors: list[str], directives: dict[str, list[str]], name: str, source: str) -> None:
    sources = set(directives.get(name, []))
    if source not in sources:
        errors.append(f"vercel.json: CSP {name} missing {source}")


def forbid_csp_source(errors: list[str], directives: dict[str, list[str]], name: str, source: str) -> None:
    sources = set(directives.get(name, []))
    if source in sources:
        errors.append(f"vercel.json: CSP {name} should not include {source}")


def main() -> int:
    errors: list[str] = []
    config_path = ROOT / "vercel.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[FAIL] Could not parse vercel.json: {exc}")
        return 1

    if config.get("cleanUrls") is not True:
        errors.append("vercel.json: cleanUrls should stay true for canonical clean URLs")
    if config.get("trailingSlash") is not False:
        errors.append("vercel.json: trailingSlash should stay false to match canonical URLs")

    require_header(errors, config, "/blog/blog-:bundle.min.js", "Content-Type", "application/javascript")
    require_header(errors, config, "/blog/blog-:bundle.min.js", "Cache-Control", "stale-while-revalidate")
    require_header(errors, config, "/blog/blog-:bundle.js", "Content-Type", "application/javascript")
    require_header(errors, config, "/assets/search-index.json", "Content-Type", "application/json")
    require_header(errors, config, "/assets/search-index.json", "Cache-Control", "stale-while-revalidate")
    require_header(errors, config, "/sw.js", "Service-Worker-Allowed", "/")
    require_header(errors, config, "/sitemap.xml", "Content-Type", "application/xml")
    require_header(errors, config, "/robots.txt", "Content-Type", "text/plain")
    require_header(errors, config, "/admin.html", "Cache-Control", "no-store")
    require_header(errors, config, "/admin.html", "X-Robots-Tag", "noindex")
    require_header(errors, config, "/admin.html", "X-Frame-Options", "DENY")
    require_header(errors, config, "/admin.html", "Content-Security-Policy", "frame-ancestors 'none'")
    require_header(errors, config, "/admin", "Cache-Control", "no-store")
    require_header(errors, config, "/admin", "X-Robots-Tag", "noindex")
    require_header(errors, config, "/admin", "X-Frame-Options", "DENY")
    require_header(errors, config, "/admin", "Content-Security-Policy", "frame-ancestors 'none'")
    require_header(errors, config, "/admin/(.*)", "X-Frame-Options", "DENY")
    require_header(errors, config, "/admin/(.*)", "Content-Security-Policy", "frame-ancestors 'none'")
    # CODE_REVIEW TD-32 — the admin editor is the ONLY caller of these three
    # hosts (GitHub contents API for save/upload, LanguageTool for the spell
    # check, PubMed esummary for the citation button). They were removed from
    # the global CSP; the /admin* rules must therefore keep them or the doctor
    # silently loses save / spell-check / citation. Vercel applies matching
    # header rules in declaration order and a later duplicate key overrides the
    # earlier one, so these admin rules override the global CSP.
    #
    # Parse each admin CSP and check the connect-src directive specifically — a
    # plain substring test would pass if a host were moved to, say, img-src,
    # while the fetch stayed blocked.
    for admin_path in ("/admin.html", "/admin", "/admin/(.*)"):
        admin_entry = find_header_entry(config, admin_path)
        if not admin_entry:
            errors.append(f"vercel.json: missing headers entry for {admin_path}")
            continue
        admin_csp = header_map(admin_entry).get("content-security-policy")
        if not admin_csp:
            errors.append(f"vercel.json: {admin_path} missing Content-Security-Policy")
            continue
        admin_connect = set(parse_csp(admin_csp).get("connect-src", []))
        for admin_host in (
            "https://api.github.com",
            "https://api.languagetool.org",
            "https://eutils.ncbi.nlm.nih.gov",
        ):
            if admin_host not in admin_connect:
                errors.append(f"vercel.json: {admin_path} CSP connect-src missing {admin_host}")
    for admin_source in ("/admin.html", "/admin", "/admin/(.*)"):
        admin_entry = find_header_entry(config, admin_source)
        if admin_entry:
            admin_csp = header_map(admin_entry).get("content-security-policy", "")
            for directive in [
                "default-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "connect-src 'self'",
                "upgrade-insecure-requests",
            ]:
                if directive not in admin_csp:
                    errors.append(f"vercel.json: {admin_source} CSP missing {directive}")
    header_sources = [entry.get("source") for entry in config.get("headers", [])]
    broad_indices = [
        header_sources.index(source)
        for source in ("/(.*).html", "/(.*)")
        if source in header_sources
    ]
    if broad_indices:
        last_broad_index = max(broad_indices)
        for admin_source in ("/admin.html", "/admin", "/admin/(.*)"):
            if admin_source in header_sources and header_sources.index(admin_source) <= last_broad_index:
                errors.append(
                    f"vercel.json: {admin_source} must follow broad header rules "
                    "so its strict CSP and DENY frame policy win"
                )

    for retired in ("admin/index.html", "admin/cms.html", "admin/config.yml"):
        if (ROOT / retired).exists():
            errors.append(f"{retired}: retired or unreachable admin shell should remain removed")

    scheduled_path = ROOT / ".github" / "workflows" / "scheduled-publish.yml"
    if not scheduled_path.exists():
        errors.append(".github/workflows/scheduled-publish.yml: missing scheduled publish workflow")
    else:
        scheduled = scheduled_path.read_text(encoding="utf-8", errors="replace")
        push_main = "subprocess.check_call(['git', 'push', 'origin', 'main'])"
        delete_branch = "subprocess.check_call(['git', 'push', 'origin', '--delete', branch])"
        if push_main not in scheduled or delete_branch not in scheduled:
            errors.append("scheduled-publish.yml: expected main push and draft cleanup commands")
        elif scheduled.index(delete_branch) < scheduled.index(push_main):
            errors.append("scheduled-publish.yml: draft branches must be deleted only after main is pushed")
        if "remaining.append(item)" not in scheduled:
            errors.append("scheduled-publish.yml: failed or missing drafts should remain queued for recovery")
        if "group: scheduled-publish-main" not in scheduled:
            errors.append("scheduled-publish.yml: scheduled runs should be serialized")
        if "if r.returncode != 0:" not in scheduled or "raise subprocess.CalledProcessError" not in scheduled:
            errors.append("scheduled-publish.yml: remote branch lookup failures should fail visibly")
        for guard in [
            "SLUG_RE.fullmatch(slug)",
            "branch != f'drafts/{slug}'",
            "file_path != f'blog/{slug}.html'",
            "if at.tzinfo is None:",
        ]:
            if guard not in scheduled:
                errors.append(f"scheduled-publish.yml: missing queue safety guard {guard}")

    quality_path = ROOT / ".github" / "workflows" / "quality.yml"
    if not quality_path.exists():
        errors.append(".github/workflows/quality.yml: missing quality workflow")
    else:
        quality = quality_path.read_text(encoding="utf-8", errors="replace")
        for command in [
            "python _run_quality.py regen",
            "python _gen_search_index.py",
            "python _minify.py",
            "python _run_quality.py check",
            "git add -A",
            "git commit --amend --no-edit",
        ]:
            if command not in quality:
                errors.append(f"quality.yml: canonical auto-regen missing {command}")

    runner = (ROOT / "_run_quality.py").read_text(encoding="utf-8", errors="replace")
    date_step = '[PY, "_normalize_date_modified.py"]'
    if runner.count(date_step) != 1:
        errors.append("_run_quality.py: dateModified normalizer should appear exactly once")
    else:
        date_index = runner.index(date_step)
        for dependent_step in (
            '[PY, "_gen_en_pages.py"]',
            '[PY, "_gen_feeds.py"]',
            '[PY, "_gen_llms_full.py"]',
        ):
            if dependent_step not in runner or date_index > runner.index(dependent_step):
                errors.append(
                    f"_run_quality.py: {date_step} must run before {dependent_step} "
                    "to keep generated freshness metadata consistent"
                )

    graph_generator = (ROOT / "_gen_site_graph.py").read_text(encoding="utf-8", errors="replace")
    if "return sorted(edges)" not in graph_generator:
        errors.append("_gen_site_graph.py: graph edges should be sorted for deterministic builds")
    if 'sorted(parse_articles(), key=lambda article: article["slug"])' not in graph_generator:
        errors.append("_gen_site_graph.py: graph nodes should be sorted for deterministic builds")

    for date_script in ("_normalize_date_modified.py", "_normalize_article_metadata.py"):
        date_source = (ROOT / date_script).read_text(encoding="utf-8", errors="replace")
        if "--invert-grep" not in date_source or "AUTO_REGEN_SUBJECT_RE" not in date_source:
            errors.append(f"{date_script}: git-derived freshness dates should ignore auto-regen commits")

    global_entry = find_header_entry(config, "/(.*)")
    if not global_entry:
        errors.append("vercel.json: missing global security headers entry")
    else:
        headers = header_map(global_entry)
        required_global = [
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy",
            "x-frame-options",
            "strict-transport-security",
            "content-security-policy",
            "cross-origin-opener-policy",
        ]
        for key in required_global:
            if key not in headers:
                errors.append(f"vercel.json: global headers missing {key}")
        csp = headers.get("content-security-policy", "")
        for directive in [
            "default-src 'self'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self' mailto:",
            "frame-ancestors 'self'",
            "manifest-src 'self'",
            "worker-src 'self'",
            "upgrade-insecure-requests",
        ]:
            if directive not in csp:
                errors.append(f"vercel.json: CSP missing {directive}")
        directives = parse_csp(csp)
        required_sources = {
            "script-src": [
                "'self'",
                "'unsafe-inline'",
                "https://www.googletagmanager.com",
                "https://pagead2.googlesyndication.com",
                "https://www.clarity.ms",
                "https://*.clarity.ms",
                "https://unpkg.com",
            ],
            "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
            # 2026-05-25 — img-src tightened: was `'self' data: https: blob:`
            # (wildcard https: = any host could serve images, real
            # exfiltration vector via injected <img>). Now explicit allow-
            # list: 'self' + data: + blob: + GA/Clarity/AdSense/doubleclick
            # tracking pixels + Giscus avatars. Wildcard `https:` is FORBIDDEN.
            "img-src": [
                "'self'",
                "data:",
                "blob:",
                "https://www.google-analytics.com",
                "https://www.googletagmanager.com",
                "https://pagead2.googlesyndication.com",
                "https://googleads.g.doubleclick.net",
                "https://stats.g.doubleclick.net",
                "https://www.clarity.ms",
                "https://*.clarity.ms",
                "https://avatars.githubusercontent.com",
            ],
            "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
            # CODE_REVIEW TD-32 — the GLOBAL connect-src carries only 'self' plus
            # the analytics endpoints the public pages actually call. GitHub /
            # LanguageTool are fetched exclusively by the admin editor and now
            # live only in the /admin* CSP rules; eutils.ncbi + raw.githubusercontent
            # were dead allowances (nothing in the repo ever fetched them — public
            # pages only <a href> to pubmed, which connect-src does not govern).
            "connect-src": [
                "'self'",
                "https://www.google-analytics.com",
                "https://*.clarity.ms",
                "https://stats.g.doubleclick.net",
            ],
            "frame-src": ["https://www.google.com", "https://googleads.g.doubleclick.net", "https://www.youtube.com"],
        }
        for name, sources in required_sources.items():
            for source in sources:
                require_csp_source(errors, directives, name, source)
        # CODE_REVIEW TD-32 — keep admin-only + dead endpoints out of the GLOBAL
        # connect-src. They belong to the /admin* CSP rules only; if one creeps
        # back here every public page regains permission to call it.
        for admin_only in (
            "https://api.github.com",
            "https://uploads.github.com",
            "https://raw.githubusercontent.com",
            "https://api.languagetool.org",
            "https://eutils.ncbi.nlm.nih.gov",
        ):
            forbid_csp_source(errors, directives, "connect-src", admin_only)
        forbid_csp_source(errors, directives, "script-src", "https://fonts.googleapis.com")
        # 2026-05-25 — block the wildcard https: from sneaking back into img-src.
        forbid_csp_source(errors, directives, "img-src", "https:")

    if errors:
        print("[FAIL] Deployment config audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] Deployment config audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
