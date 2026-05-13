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

    admin_index = ROOT / "admin" / "index.html"
    if admin_index.exists():
        admin_html = admin_index.read_text(encoding="utf-8", errors="replace")
        if "decap-cms@^" in admin_html or "decap-cms@latest" in admin_html:
            errors.append("admin/index.html: Decap CMS CDN version should be pinned exactly")
        if "</main></main>" in admin_html:
            errors.append("admin/index.html: duplicate </main> closing tag should be removed")
    else:
        errors.append("admin/index.html: missing admin shell")

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
            "img-src": ["'self'", "data:", "https:", "blob:"],
            "font-src": ["'self'", "data:", "https://fonts.gstatic.com"],
            "connect-src": [
                "'self'",
                "https://www.google-analytics.com",
                "https://*.clarity.ms",
                "https://stats.g.doubleclick.net",
                "https://eutils.ncbi.nlm.nih.gov",
                "https://api.github.com",
                "https://uploads.github.com",
                "https://raw.githubusercontent.com",
                "https://api.languagetool.org",
            ],
            "frame-src": ["https://www.google.com", "https://googleads.g.doubleclick.net", "https://www.youtube.com"],
        }
        for name, sources in required_sources.items():
            for source in sources:
                require_csp_source(errors, directives, name, source)
        forbid_csp_source(errors, directives, "script-src", "https://fonts.googleapis.com")

    if errors:
        print("[FAIL] Deployment config audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] Deployment config audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
