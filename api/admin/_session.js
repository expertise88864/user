// _session.js — shared helper for HttpOnly cookie-based admin sessions.
//
// 2026-05-25 — replaces "send PAT in Authorization header from browser" pattern,
// which kept the PAT in localStorage/sessionStorage and exposed it to any XSS.
// New pattern:
//   1. POST /api/admin/login {pat:"ghp_..."} → validates with GitHub /user,
//      stores {pat, login, exp} in Vercel KV keyed by random session token,
//      Set-Cookie: dn_admin_session=<token> HttpOnly Secure SameSite=Strict.
//   2. Subsequent calls send the cookie (browser does this automatically).
//   3. Admin API endpoints call `getSession(req)` here to retrieve {pat, login}.
//   4. PAT never lives in JS-accessible storage; an XSS on the origin cannot
//      read it because of HttpOnly + (under modern browsers) Site-isolation.
//
// Note: needs env vars KV_REST_API_URL + KV_REST_API_TOKEN configured.
// Falls back to ADMIN_REPO env var; defaults to "expertise88864/user".

const COOKIE_NAME = 'dn_admin_session';
const SESSION_TTL_SECONDS = 86400; // 24 h — match the sessionStorage PAT TTL
const KV_KEY_PREFIX = 'admin:session:';
const REPO_OWNER_ALLOWLIST = new Set(['expertise88864']);

function jsonResp(status, obj, extraHeaders) {
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    ...(extraHeaders || {}),
  };
  return new Response(JSON.stringify(obj), { status, headers });
}

async function kvGet(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  try {
    const r = await fetch(`${url}/get/${encodeURIComponent(key)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!r.ok) return null;
    const j = await r.json();
    return j.result ? JSON.parse(j.result) : null;
  } catch (_) {
    return null;
  }
}

async function kvSetEx(key, value, ttlSeconds) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  // Upstash REST: PUT /set/<key>?EX=<seconds>
  const r = await fetch(
    `${url}/set/${encodeURIComponent(key)}?EX=${encodeURIComponent(ttlSeconds)}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(value),
    },
  );
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`KV set failed: ${r.status} ${t}`);
  }
}

async function kvDel(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return;
  try {
    await fetch(`${url}/del/${encodeURIComponent(key)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (_) { /* ignore */ }
}

function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (k) out[k] = decodeURIComponent(v);
  }
  return out;
}

function sessionTokenFromReq(req) {
  const cookies = parseCookies(req.headers.get('cookie'));
  return cookies[COOKIE_NAME] || '';
}

function buildSetCookie(token, opts) {
  const ttl = (opts && opts.ttlSeconds) ?? SESSION_TTL_SECONDS;
  const maxAge = opts && opts.clear ? 0 : ttl;
  const value = opts && opts.clear ? '' : encodeURIComponent(token);
  // Path=/api/admin — cookie only sent to admin endpoints (not e.g. /api/popular-picks public read)
  // SameSite=Strict — no cross-site requests
  // HttpOnly — JS can't read
  // Secure — HTTPS only
  return [
    `${COOKIE_NAME}=${value}`,
    'Path=/api/admin',
    'HttpOnly',
    'Secure',
    'SameSite=Strict',
    `Max-Age=${maxAge}`,
  ].join('; ');
}

/**
 * Read the admin session from the incoming request.
 * Returns {token, pat, login} on hit, null on miss/expired.
 */
async function getSession(req) {
  const token = sessionTokenFromReq(req);
  if (!token) return null;
  const data = await kvGet(KV_KEY_PREFIX + token);
  if (!data) return null;
  if (data.exp && Date.now() / 1000 > data.exp) {
    await kvDel(KV_KEY_PREFIX + token);
    return null;
  }
  if (!REPO_OWNER_ALLOWLIST.has(data.login)) {
    // Defensive: if allowlist was tightened since the session was issued
    await kvDel(KV_KEY_PREFIX + token);
    return null;
  }
  return { token, pat: data.pat, login: data.login };
}

/**
 * Validate the PAT against GitHub and (on success) mint a new session.
 * Returns { token, login, setCookieHeader } on success, throws on failure.
 */
async function createSession(pat) {
  if (!pat || typeof pat !== 'string') throw new Error('Missing PAT');
  // Round-trip to GitHub /user to confirm the token is valid + owner is allowed.
  let userLogin = null;
  try {
    const r = await fetch('https://api.github.com/user', {
      headers: {
        Authorization: `token ${pat}`,
        'User-Agent': 'ChenDermatologist-Admin/1.0',
        Accept: 'application/vnd.github+json',
      },
    });
    if (!r.ok) throw new Error('GitHub rejected token');
    const u = await r.json();
    userLogin = u && u.login;
  } catch (_) {
    throw new Error('GitHub validation failed');
  }
  if (!userLogin || !REPO_OWNER_ALLOWLIST.has(userLogin)) {
    throw new Error('User not allowlisted');
  }
  // Mint a 32-byte session token. crypto.randomUUID() is good enough here
  // (122 bits of entropy, plenty for a 24h-lifetime session ID).
  const token = (globalThis.crypto && globalThis.crypto.randomUUID)
    ? globalThis.crypto.randomUUID()
    : Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
  const exp = Math.floor(Date.now() / 1000) + SESSION_TTL_SECONDS;
  await kvSetEx(KV_KEY_PREFIX + token, { pat, login: userLogin, exp }, SESSION_TTL_SECONDS);
  return {
    token,
    login: userLogin,
    setCookieHeader: buildSetCookie(token, { ttlSeconds: SESSION_TTL_SECONDS }),
  };
}

/**
 * Destroy the session: clear KV + tell browser to drop cookie.
 * Returns the clear-cookie Set-Cookie header.
 */
async function destroySession(req) {
  const token = sessionTokenFromReq(req);
  if (token) await kvDel(KV_KEY_PREFIX + token);
  return buildSetCookie('', { clear: true });
}

/**
 * Resolve the GitHub auth header value for an admin API call.
 * Tries cookie session first (PREFERRED — PAT never touched the browser);
 * falls back to legacy `Authorization: token ghp_...` header (the older
 * admin UI sends this; gradually being phased out in Phase 2).
 *
 * Returns { auth, login, source } on hit, null on miss.
 *   - auth: string "token ghp_..." ready to forward to api.github.com
 *   - login: GitHub username (only set in cookie path; null in legacy)
 *   - source: 'cookie' | 'header'
 */
const PAT_AUTH_RE_INTERNAL = /^token\s+(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/;

async function resolveAuth(req) {
  const session = await getSession(req);
  if (session) {
    return { auth: `token ${session.pat}`, login: session.login, source: 'cookie' };
  }
  const header = req.headers.get('authorization') || '';
  if (PAT_AUTH_RE_INTERNAL.test(header)) {
    return { auth: header, login: null, source: 'header' };
  }
  return null;
}

export {
  COOKIE_NAME,
  SESSION_TTL_SECONDS,
  REPO_OWNER_ALLOWLIST,
  jsonResp,
  getSession,
  createSession,
  destroySession,
  resolveAuth,
};
