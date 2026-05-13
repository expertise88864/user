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


def main() -> int:
    errors: list[str] = []

    require(errors, "api/auth.js", "if (req.method !== 'GET')", "OAuth endpoint should explicitly allow GET only")
    require(errors, "api/auth.js", "process.env.OAUTH_CLIENT_ID || !process.env.OAUTH_CLIENT_SECRET", "OAuth env vars should be checked before redirect/callback")
    require(errors, "api/auth.js", "'Cache-Control': 'no-store'", "OAuth responses should disable caching")
    require(errors, "api/auth.js", "var targetOrigin = ${JSON.stringify(targetOrigin)};", "OAuth popup should postMessage only to the current site origin")
    require(errors, "api/auth.js", "if (e.origin !== targetOrigin) return;", "OAuth popup should ignore messages from other origins")
    forbid(errors, "api/auth.js", "postMessage('authorization:github:' + status + ':' + JSON.stringify(content), '*')", "OAuth token should not be posted to wildcard origins")
    forbid(errors, "api/auth.js", "OAuth failed: ${JSON.stringify(data)}", "OAuth errors should not echo provider payloads")

    require(errors, "api/push-send.js", "auth !== `Bearer ${process.env.ADMIN_TOKEN}`", "admin broadcast auth should use exact bearer-token comparison")
    require(errors, "api/push-send.js", "if (!kvUrl || !kvTok)", "admin broadcast should fail closed when KV env vars are missing")
    require(errors, "api/push-send.js", "res.setHeader('Cache-Control', 'no-store');", "admin broadcast responses should not be cached")
    forbid(errors, "api/push-send.js", "auth.endsWith(process.env.ADMIN_TOKEN)", "admin broadcast should not use suffix token matching")

    require(errors, "api/push-subscribe.js", "if (req.method === 'OPTIONS')", "push subscription endpoint should support CORS preflight")
    require(errors, "api/push-subscribe.js", "Vary: 'Origin'", "push subscription CORS responses should vary by Origin")
    require(errors, "api/push-subscribe.js", "sub.endpoint.startsWith('https://')", "push subscription endpoint should require HTTPS")
    require(errors, "api/push-subscribe.js", "typeof sub.keys.p256dh === 'string'", "push subscription should validate p256dh key")
    require(errors, "api/push-subscribe.js", "typeof sub.keys.auth === 'string'", "push subscription should validate auth key")

    require(errors, "api/rpc.js", "const MAX_BATCH = 20;", "RPC endpoint should cap JSON-RPC batch size")
    require(errors, "api/rpc.js", "if (origin && !ALLOWED_ORIGINS.has(origin))", "RPC endpoint should reject disallowed browser origins")
    require(errors, "api/rpc.js", "Vary: 'Origin'", "RPC CORS responses should vary by Origin")
    require(errors, "api/rpc.js", "calls.length === 0 || calls.length > MAX_BATCH", "RPC endpoint should reject empty or oversized batches")
    require(errors, "api/rpc.js", "function parseLimit(value, fallback = 8)", "RPC endpoint should parse numeric limits with a bounded helper")
    require(errors, "api/rpc.js", "function rpcError(e)", "RPC endpoint should centralize safe error serialization")
    require(errors, "api/rpc.js", "return { code: -32603, message: 'Internal error' };", "RPC endpoint should not expose unknown exception messages")
    forbid(errors, "api/rpc.js", "'Access-Control-Allow-Origin': '*'", "RPC endpoint should not allow wildcard CORS")
    forbid(errors, "api/rpc.js", "String(e && e.message || e)", "RPC endpoint should not echo unknown exception messages")

    require(errors, "api/articles-recent.js", "if (req.method !== 'GET')", "recent articles endpoint should explicitly allow GET only")
    require(errors, "api/articles-recent.js", "headers: {\n        Allow: 'GET',", "recent articles 405 response should declare Allow: GET")
    require(errors, "api/articles-recent.js", "function parseLimit(value)", "recent articles endpoint should parse n with a reusable bounded helper")
    require(errors, "api/articles-recent.js", "if (!Number.isFinite(parsed)) return DEFAULT_LIMIT;", "recent articles endpoint should fall back when n is not numeric")
    forbid(errors, "api/articles-recent.js", "Math.min(20, Math.max(1, parseInt", "recent articles endpoint should not let parseInt NaN leak into slice limits")

    require(errors, "api/og.js", "if (req.method !== 'GET')", "OG image endpoint should explicitly allow GET only")
    require(errors, "api/og.js", "Allow: 'GET'", "OG image 405 response should declare Allow: GET")
    require(errors, "api/analytics.js", "if (req.method !== 'GET')", "analytics stub should explicitly allow GET only")
    require(errors, "api/analytics.js", "'Cache-Control': 'no-store'", "analytics disabled responses should not be cached")

    require(errors, "api/admin/upload.js", "const ALLOWED_FOLDERS = new Set(['assets/uploads', 'blog']);", "upload endpoint should restrict writable folders")
    require(errors, "api/admin/upload.js", "Unsupported image type; use PNG, JPEG, WebP, AVIF, or GIF", "upload endpoint should reject unsupported image types")
    forbid(errors, "api/admin/upload.js", "m === 'image/svg+xml' || ext === 'svg'", "same-origin SVG uploads should remain disabled")

    admin_pat_files = [
        "api/admin/upload.js",
        "api/admin/summarize.js",
        "api/admin/regen-en.js",
        "api/admin/popular-picks.js",
    ]
    for rel in admin_pat_files:
        require(errors, rel, "const PAT_AUTH_RE = /^token\\s+(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/;", "admin PAT auth regex should be anchored and support classic/fine-grained tokens")
        require(errors, rel, "PAT_AUTH_RE.test(auth)", "admin endpoint should use the shared anchored PAT auth regex")
        forbid(errors, rel, "/^token\\s+gh[poas]_[A-Za-z0-9_]+/.test(auth)", "admin endpoint should not use unanchored PAT auth regex")

    for rel in ["api/admin/upload.js", "api/admin/summarize.js", "api/admin/regen-en.js"]:
        require(errors, rel, "'Cache-Control': 'no-store'", "admin write endpoint responses should not be cached")
        require(errors, rel, "{ Allow: 'POST' }", "admin write endpoint 405 response should declare Allow: POST")
    forbid(errors, "api/admin/upload.js", "detail: result", "admin upload should not expose GitHub provider payloads")
    forbid(errors, "api/admin/regen-en.js", "detail: result.data", "admin regen-en should not expose GitHub provider payloads")
    forbid(errors, "api/admin/summarize.js", "detail: e.slice", "admin summarize should not expose provider error payloads")
    forbid(errors, "api/admin/summarize.js", "raw: raw.slice", "admin summarize should not expose raw AI output on parse failure")
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
