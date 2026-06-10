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
    ]
    for rel in retired_endpoints:
        require_absent(errors, rel, "retired or unwired endpoint should remain removed")

    require(errors, "api/admin/popular-picks.js", "import { getSession } from './_session.js';", "admin popular-picks should use the shared cookie session")
    require(errors, "api/admin/popular-picks.js", "const session = await getSession(req);", "admin popular-picks writes should require the cookie session")
    require(errors, "api/admin/popular-picks.js", "'Cache-Control': 'no-store'", "admin popular-picks write and error responses should not be cached by default")
    require(errors, "api/admin/popular-picks.js", "{ Allow: 'GET, POST' }", "admin popular-picks 405 response should declare allowed methods")
    require(errors, "api/admin/popular-picks.js", "new Set(cleaned).size !== cleaned.length", "admin popular-picks should reject duplicate slugs server-side")
    forbid(errors, "api/admin/popular-picks.js", "req.headers.get('authorization')", "admin popular-picks should not accept PAT headers")
    forbid(errors, "api/admin/popular-picks.js", "const REPO =", "admin popular-picks should not keep unused REPO constants")
    forbid(errors, "api/admin/popular-picks.js", "error: e.message", "admin popular-picks should not expose raw KV error messages")

    if errors:
        print("[FAIL] API security audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] API security audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
