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

    # CODE_REVIEW — auth check upgraded from `auth !== \`Bearer ${TOKEN}\``
    # (timing-leaky string compare) to constant-time timingSafeEqual.
    require(errors, "api/push-send.js", "timingSafeBearerEqual(req.headers.authorization, process.env.ADMIN_TOKEN)", "admin broadcast auth should use constant-time bearer-token comparison")
    require(errors, "api/push-send.js", "timingSafeEqual", "admin broadcast must import timingSafeEqual from node:crypto")
    require(errors, "api/push-send.js", "if (!kvUrl || !kvTok)", "admin broadcast should fail closed when KV env vars are missing")
    require(errors, "api/push-send.js", "res.setHeader('Cache-Control', 'no-store');", "admin broadcast responses should not be cached")
    require(errors, "api/push-send.js", "const MAX_TITLE = 100;", "admin broadcast should cap title length")
    require(errors, "api/push-send.js", "const MAX_BODY = 500;", "admin broadcast should cap body length")
    require(errors, "api/push-send.js", "const MAX_ICON = 500;", "admin broadcast should cap icon URL length")
    require(errors, "api/push-send.js", "const MAX_TAG = 64;", "admin broadcast should cap notification tag length")
    require(errors, "api/push-send.js", "function isSafeSiteUrl(value)", "admin broadcast should validate notification URLs centrally")
    require(errors, "api/push-send.js", "new URL(value, 'https://chendermatologist.com')", "admin broadcast should parse relative and absolute URLs against the canonical origin")
    require(errors, "api/push-send.js", "if (!vapidContact || !vapidPublicKey || !vapidPrivateKey)", "admin broadcast should fail closed when VAPID env vars are missing")
    require(errors, "api/push-send.js", "error: 'VAPID configuration invalid'", "admin broadcast should handle malformed VAPID configuration")
    require(errors, "api/push-send.js", "const BROADCAST_CONCURRENCY = 20;", "admin broadcast should use bounded concurrency")
    require(errors, "api/push-send.js", "keys.slice(i, i + BROADCAST_CONCURRENCY)", "admin broadcast should process subscriptions in bounded batches")
    require(errors, "api/push-send.js", "if (!keysResp.ok)", "admin broadcast should handle KV index read failures")
    forbid(errors, "api/push-send.js", "auth.endsWith(process.env.ADMIN_TOKEN)", "admin broadcast should not use suffix token matching")
    forbid(errors, "api/push-send.js", "auth !== `Bearer ${process.env.ADMIN_TOKEN}`", "admin broadcast should not use timing-unsafe string compare")
    forbid(errors, "api/push-send.js", "Promise.all(keys.map", "admin broadcast should not fan out to every subscriber at once")

    require(errors, "api/push-subscribe.js", "if (req.method === 'OPTIONS')", "push subscription endpoint should support CORS preflight")
    require(errors, "api/push-subscribe.js", "Vary: 'Origin'", "push subscription CORS responses should vary by Origin")
    require(errors, "api/push-subscribe.js", "sub.endpoint.startsWith('https://')", "push subscription endpoint should require HTTPS")
    require(errors, "api/push-subscribe.js", "typeof sub.keys.p256dh === 'string'", "push subscription should validate p256dh key")
    require(errors, "api/push-subscribe.js", "typeof sub.keys.auth === 'string'", "push subscription should validate auth key")
    require(errors, "api/push-subscribe.js", "const MAX_ENDPOINT_LENGTH = 2048;", "push subscription should cap endpoint length")
    require(errors, "api/push-subscribe.js", "if (!setResp.ok)", "push subscription should verify the KV membership write")
    require(errors, "api/push-subscribe.js", "/del/${encodeURIComponent(key)}", "push subscription should roll back orphan values after membership failure")

    require(errors, "api/og.js", "if (req.method !== 'GET')", "OG image endpoint should explicitly allow GET only")
    require(errors, "api/og.js", "Allow: 'GET'", "OG image 405 response should declare Allow: GET")

    require(errors, "api/admin/_session.js", "const login = await validateGitHubIdentity(header);", "legacy PAT fallback should validate GitHub identity and allowlist")
    require(errors, "api/admin/_session.js", "throw new Error('Secure random generator unavailable');", "admin sessions should fail closed without a CSPRNG")
    require(errors, "api/admin/_session.js", "catch (_) {\n      // Ignore malformed cookie values", "malformed cookies should not crash admin authentication")
    forbid(errors, "api/admin/_session.js", "Math.random()", "admin session tokens should never use Math.random")

    retired_endpoints = [
        "api/auth.js",
        "api/rpc.js",
        "api/articles-recent.js",
        "api/analytics.js",
        "api/admin/upload.js",
        "api/admin/summarize.js",
        "api/admin/regen-en.js",
    ]
    for rel in retired_endpoints:
        require_absent(errors, rel, "retired/unwired endpoint should remain removed")
    require(errors, "api/admin/popular-picks.js", "import { resolveAuth } from './_session.js';", "admin popular-picks should use shared authentication")
    require(errors, "api/admin/popular-picks.js", "const resolved = await resolveAuth(req);", "admin popular-picks should validate cookie and legacy PAT through the shared helper")

    require(errors, "api/admin/popular-picks.js", "'Cache-Control': 'no-store'", "admin popular-picks write/error responses should not be cached by default")
    require(errors, "api/admin/popular-picks.js", "{ Allow: 'GET, POST' }", "admin popular-picks 405 response should declare allowed methods")
    require(errors, "api/admin/popular-picks.js", "new Set(cleaned).size !== cleaned.length", "admin popular-picks should reject duplicate slugs server-side")
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
