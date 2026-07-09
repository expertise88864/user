// /api/admin/login — exchange a GitHub PAT for an HttpOnly session cookie.
//
// Browser POSTs { pat: "ghp_..." } once. Server validates the PAT with
// GitHub /user, confirms the user is in REPO_OWNER_ALLOWLIST, stores the
// PAT in Vercel KV keyed by a random session token, and returns Set-Cookie
// with the session token (HttpOnly Secure SameSite=Strict, 24h TTL).
//
// After this, same-origin admin API calls send the cookie automatically
// and use _session.js to retrieve the PAT server-side. The WYSIWYG keeps
// a separate tab-scoped copy only for its direct GitHub API operations.
//
// Method:
//   POST { pat: "ghp_..." } → 200 { ok: true, login: "expertise88864" }
//                              + Set-Cookie: dn_admin_session=...
//   anything else            → 400/401/405
//
// Security rationale: localStorage and sessionStorage are JS-accessible,
// so an XSS or compromised 3rd-party script can exfiltrate the PAT.
// HttpOnly cookies are not accessible to JS — even XSS can't read them.
// Cookie-authenticated endpoints should not resend the tab-scoped PAT.

import { createSession, jsonResp } from './_session.js';

export const config = { runtime: 'edge' };

// Brute-force / validity-oracle guard: cap login attempts per client IP in KV.
// FAIL-OPEN — if KV is unavailable we never block a legitimate login.
const RL_WINDOW_SECONDS = 900; // 15-minute sliding window
const RL_MAX_ATTEMPTS = 10; // generous for a single-admin site

function clientIp(req) {
  const xff = req.headers.get('x-forwarded-for') || '';
  return xff.split(',')[0].trim() || req.headers.get('x-real-ip') || 'unknown';
}

// Single Upstash REST command via JSON-array body → { result }.
// Has a hard deadline (AbortController): a *stalled* KV request aborts and
// throws instead of hanging until the function timeout, so the caller's
// try/catch can fail-open promptly rather than blocking a legitimate login.
const KV_TIMEOUT_MS = 2000;

async function kvCmd(url, token, args) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), KV_TIMEOUT_MS);
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(args),
      signal: ctrl.signal,
    });
    if (!r.ok) throw new Error(`KV command failed: ${r.status}`);
    const j = await r.json();
    return j.result;
  } finally {
    clearTimeout(timer);
  }
}

async function loginRateLimited(req) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return false; // fail-open: no KV configured
  const key = `admin:login:rl:${clientIp(req)}`;
  try {
    // Atomically ensure the counter key exists WITH a TTL *before* we increment.
    // `SET key 0 EX <win> NX` creates it (with expiry) only if absent; a
    // subsequent INCR preserves that TTL. This avoids the classic
    // INCR-then-conditional-EXPIRE race where a failed/late EXPIRE would leave
    // a counter that never resets — a permanent 429 (fail-closed) for that IP.
    await kvCmd(url, token, ['SET', key, '0', 'EX', String(RL_WINDOW_SECONDS), 'NX']);
    const count = Number(await kvCmd(url, token, ['INCR', key])) || 0;
    return count > RL_MAX_ATTEMPTS;
  } catch (_) {
    return false; // fail-open on any transient KV error
  }
}

export default async function handler(req) {
  if (req.method !== 'POST') {
    return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });
  }
  if (await loginRateLimited(req)) {
    return jsonResp(
      429,
      { error: 'Too many login attempts; try again later' },
      { 'Retry-After': String(RL_WINDOW_SECONDS) },
    );
  }
  let body;
  try { body = await req.json(); } catch { return jsonResp(400, { error: 'JSON body required' }); }
  const pat = body && body.pat;
  if (!pat || typeof pat !== 'string') {
    return jsonResp(400, { error: 'pat string required' });
  }
  // Basic shape check before round-tripping to GitHub
  if (!/^(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/.test(pat)) {
    return jsonResp(400, { error: 'pat does not match GitHub PAT shape' });
  }
  try {
    const { login, setCookieHeader } = await createSession(pat);
    return jsonResp(200, { ok: true, login }, { 'Set-Cookie': setCookieHeader });
  } catch (e) {
    const msg = String(e && e.message || e);
    if (msg.includes('not allowlisted')) {
      return jsonResp(403, { error: 'User not allowlisted' });
    }
    if (msg.includes('GitHub')) {
      return jsonResp(401, { error: msg });
    }
    return jsonResp(500, { error: 'Login failed' });
  }
}
