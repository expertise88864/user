from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def require(errors: list[str], rel: str, needle: str, message: str) -> None:
    if needle not in read(rel):
        errors.append(f"{rel}: {message}")


def forbid(errors: list[str], rel: str, needle: str, message: str) -> None:
    if needle in read(rel):
        errors.append(f"{rel}: {message}")


def require_absent(errors: list[str], rel: str, message: str) -> None:
    if (ROOT / rel).exists():
        errors.append(f"{rel}: {message}")


def main() -> int:
    errors: list[str] = []

    require(errors, "api/og.js", "if (req.method !== 'GET')", "OG image endpoint should explicitly allow GET only")
    require(errors, "api/og.js", "Allow: 'GET'", "OG image 405 response should declare Allow: GET")
    require(errors, "api/og.js", "function sanitizeXmlText(value, maxChars)", "OG image text should strip invalid XML controls")
    require(errors, "api/og.js", "\"default-src 'none'; style-src 'unsafe-inline'; sandbox\"", "OG SVG responses should carry a restrictive CSP")
    require(errors, "api/og.js", "'X-Content-Type-Options': 'nosniff'", "OG SVG responses should disable MIME sniffing")

    require(errors, "api/admin/_session.js", "throw new Error('Secure random generator unavailable');", "admin sessions should fail closed without a CSPRNG")
    require(errors, "api/admin/_session.js", "catch (_) {\n      // Ignore malformed cookie values", "malformed cookies should not crash admin authentication")
    forbid(errors, "api/admin/_session.js", "Math.random()", "admin session tokens should never use Math.random")
    forbid(errors, "api/admin/_session.js", "resolveAuth", "legacy Authorization-header fallback should remain removed")
    forbid(errors, "api/admin/_session.js", "PAT_AUTH_RE_INTERNAL", "legacy PAT header parsing should remain removed")

    retired_endpoints = [
        "api/auth.js",
        "api/rpc.js",
        "api/articles-recent.js",
        "api/analytics.js",
        "api/push-send.js",
        "api/push-subscribe.js",
        "api/admin/upload.js",
        "api/admin/summarize.js",
        "api/admin/regen-en.js",
        "api/admin/popular-picks.js",
    ]
    for rel in retired_endpoints:
        require_absent(errors, rel, "retired or unwired endpoint should remain removed")

    # Homepage recommendations (熱門推薦) were retired 2026-10-17 by user
    # decision: no public KV read, no settings field and no admin save kind.
    forbid(errors, "api/admin/_site-settings.js", "contract.maxPicks", "Retired homepage recommendations must not return to the settings grammar")
    forbid(errors, "api/admin/_site-settings.js", "legacyPicks: value.legacyPicks", "Retired homepage recommendations must not be returned as a settings field")
    require(errors, "api/admin/_site-settings.js", "if (!retired) return { settings: settingsOf(value, articles), retired: false };", "Only stored drafts may drop the retired fields; author input stays strict")
    forbid(errors, "api/admin/site-settings.js", "picks", "Retired homepage recommendations must not return as a settings save kind")
    forbid(errors, "_site_settings_contract.json", "maxPicks", "Retired homepage recommendations must not keep a settings limit")

    if errors:
        print("[FAIL] API security audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] API security audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
