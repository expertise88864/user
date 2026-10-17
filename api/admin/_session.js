// _session.js — shared helper for HttpOnly cookie-based admin sessions.
//
// Cookie-session path for same-origin admin APIs:
//   1. POST /api/admin/login {pat:"ghp_..."} → validates with GitHub /user,
//      stores {pat, login, exp} in Vercel KV keyed by random session token,
//      Set-Cookie: dn_admin_session=<token> HttpOnly Secure SameSite=Strict.
//   2. Subsequent calls send the cookie (browser does this automatically).
//   3. Admin API endpoints call `getSession(req)` here to retrieve {pat, login}.
// The custom WYSIWYG still keeps a tab-scoped PAT for direct GitHub calls;
// endpoints using this helper should rely on the cookie and avoid resending it.
//
// Note: needs env vars KV_REST_API_URL + KV_REST_API_TOKEN configured.
// Before a session is minted, the same PAT must read the fixed admin
// repository through the Edge-safe transport the admin APIs use, so a token
// without repository access fails at login with a specific reason.
import { githubRequest, GitHubRequestError, githubStatusCode } from './_github-fetch.js';

const COOKIE_NAME = 'dn_admin_session';
const ADMIN_REPOSITORY = 'expertise88864/user';
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
  if (!r.ok) throw new Error('KV set failed');
  const result = await r.json();
  if (!result || result.error || result.result !== 'OK') throw new Error('KV set failed');
}

async function kvDel(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${url}/del/${encodeURIComponent(key)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error('KV deletion failed');
    const result = await response.json();
    if (!result || result.error || ![0, 1].includes(result.result)) {
      throw new Error('KV deletion failed');
    }
  } finally {
    clearTimeout(timer);
  }
}

function parseCookies(cookieHeader) {
  const out = {};
  if (!cookieHeader) return out;
  for (const part of cookieHeader.split(';')) {
    const i = part.indexOf('=');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    const v = part.slice(i + 1).trim();
    if (!k) continue;
    try {
      out[k] = decodeURIComponent(v);
    } catch (_) {
      // Ignore malformed cookie values instead of turning auth misses into 500s.
    }
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
    try { await kvDel(KV_KEY_PREFIX + token); } catch (_) { /* Still deny expired sessions. */ }
    return null;
  }
  if (!REPO_OWNER_ALLOWLIST.has(data.login)) {
    // Defensive: if allowlist was tightened since the session was issued
    try { await kvDel(KV_KEY_PREFIX + token); } catch (_) { /* Still deny disallowed users. */ }
    return null;
  }
  return { token, pat: data.pat, login: data.login };
}

function loginError(message, code) {
  const error = new Error(message);
  error.code = code;
  return error;
}

async function validateGitHubIdentity(auth) {
  let response;
  try {
    response = await fetch('https://api.github.com/user', {
      headers: {
        Authorization: auth,
        'User-Agent': 'ChenDermatologist-Admin/1.0',
        Accept: 'application/vnd.github+json',
      },
    });
  } catch (_) {
    throw loginError('GitHub validation failed', 'github_fetch_failed');
  }
  if (!response.ok) throw loginError('GitHub rejected token', githubStatusCode(response));

  let user;
  try {
    user = await response.json();
  } catch (_) {
    throw loginError('GitHub validation failed', 'github_response_invalid');
  }
  const login = user && user.login;
  if (!login || !REPO_OWNER_ALLOWLIST.has(login)) {
    throw new Error('User not allowlisted');
  }
  return login;
}

// Read the fixed repository with the PAT itself (the permissions metadata in
// the response is not interpreted): a session is only useful when this read
// succeeds.
async function validateRepositoryAccess(pat) {
  let data;
  try {
    data = await githubRequest({ endpoint: 'login', url: 'https://api.github.com/repos/' + ADMIN_REPOSITORY,
      path: 'repos/' + ADMIN_REPOSITORY, method: 'GET', pat, accept: 'application/vnd.github+json',
      userAgent: 'ChenDermatologist-Admin/1.0', timeoutMs: 10_000, maxBytes: 1_000_000 });
  } catch (error) {
    const code = error instanceof GitHubRequestError && !error.conflict ? error.code : 'github_unexpected_status';
    throw loginError('GitHub repository access failed', code);
  }
  if (!data || typeof data.full_name !== 'string' || data.full_name.toLowerCase() !== ADMIN_REPOSITORY) {
    throw loginError('GitHub repository access failed', 'github_response_invalid');
  }
}

function createSessionToken() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
    return globalThis.crypto.randomUUID();
  }
  if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(32);
    globalThis.crypto.getRandomValues(bytes);
    return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  }
  throw new Error('Secure random generator unavailable');
}

/**
 * Validate the PAT against GitHub and (on success) mint a new session.
 * Returns { token, login, setCookieHeader } on success, throws on failure.
 */
async function createSession(pat) {
  if (!pat || typeof pat !== 'string') throw new Error('Missing PAT');
  const userLogin = await validateGitHubIdentity(`token ${pat}`);
  await validateRepositoryAccess(pat);
  // Mint an unguessable session token. UUID gives 122 random bits; the
  // getRandomValues fallback gives 256 bits.
  const token = createSessionToken();
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

export {
  COOKIE_NAME,
  SESSION_TTL_SECONDS,
  REPO_OWNER_ALLOWLIST,
  jsonResp,
  getSession,
  createSession,
  destroySession,
};
