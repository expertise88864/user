from __future__ import annotations

import re
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


def forbid_pattern(errors: list[str], rel: str, pattern: str, message: str) -> None:
    if re.search(pattern, read(rel)):
        errors.append(f"{rel}: {message}")


def require_no_redirect_follow(errors: list[str], rel: str) -> None:
    """Accept `redirect: 'error'`, or `redirect: 'manual'` with a 3xx refusal."""
    text = read(rel)
    if "redirect: 'error'" in text:
        return
    if ("redirect: 'manual'" in text and "'opaqueredirect'" in text
            and re.search(r"status\s*>=\s*300\s*&&\s*\w*\.?status\s*<\s*400", text)):
        return
    errors.append(f"{rel}: provider redirects must not forward credentials "
                  "(use redirect: 'error', or redirect: 'manual' with an explicit 3xx/opaqueredirect refusal)")


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

    # Provider redirects must never forward credentials. `redirect: 'error'` is
    # equivalent, but server-side admin fetches now use `redirect: 'manual'`
    # plus an explicit 3xx/opaqueredirect refusal: the Vercel Edge runtime
    # turned the former into an unclassifiable fast failure in production, and
    # manual mode still never follows a Location header. Either form passes;
    # manual mode only passes together with its refusal check.
    require_no_redirect_follow(errors, "api/admin/_github-fetch.js")
    for rel in ("api/admin/_github-fetch.js", "api/admin/_session.js",
                "api/admin/article-draft.js", "api/admin/_settings-git.js"):
        # Edge fetch does not support the `cache` request option; freshness
        # is requested with the Cache-Control request header instead.
        forbid_pattern(errors, rel, r"\bcache\s*:\s*'", "server-side fetch must not pass a `cache` option on the Edge runtime")
    require(errors, "api/admin/_github-fetch.js", "'Cache-Control': 'no-cache'", "GitHub requests must ask for fresh data via the request header")
    require(errors, "api/admin/_github-fetch.js", "if (length > maxBytes)", "GitHub responses must remain size-capped")
    require(errors, "api/admin/_github-fetch.js", "setTimeout(() => controller.abort(), timeoutMs)", "GitHub requests must keep a deadline")
    forbid_pattern(errors, "api/admin/_github-fetch.js", r"console\.\w+\([^)]*\b(?:pat|Authorization|headers)\b", "GitHub transport logs must never include the PAT or headers")
    require(errors, "api/admin/article-draft.js", "'https://api.github.com/repos/' + REPO + '/' + path", "article drafts must keep the fixed repository")
    require(errors, "api/admin/_settings-git.js", "'https://api.github.com/repos/' + contract.repository + '/' + path", "settings must keep the fixed repository")
    require(errors, "api/admin/_session.js", "await validateRepositoryAccess(pat);", "login must verify repository access before minting a session")
    forbid(errors, "api/admin/_session.js", "permissions.push", "login repository access must be proven by a read, not permissions metadata")
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
