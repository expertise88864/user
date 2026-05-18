// G1 — JSON-RPC 2.0 base endpoint.
//
// Single endpoint for all future "small backend" features (vote, comment,
// bookmark sync, member-area, etc.). Cleaner than minting a new /api/<name>
// per feature.
//
// Spec: https://www.jsonrpc.org/specification
//
// POST /api/rpc
// Body: { jsonrpc: "2.0", method: "ns.action", params: {...}, id: 1 }
// Resp: { jsonrpc: "2.0", result: {...}, id: 1 }
//        or { jsonrpc: "2.0", error: { code, message }, id: 1 }
//
// Currently registered methods:
//   site.health              → { ok, time, region }    (public)
//   articles.recent          → { items: [...] }        (public; ≤ 20 items)
//   articles.bookmark        → { ok }                  (DISABLED — see C6 below)
//   articles.unbookmark      → { ok }                  (DISABLED)
//   articles.bookmarks       → { slugs: [...] }        (DISABLED)
//   stats.view               → { ok }                  (increment view count)
//   stats.top                → { items: [...] }        (top viewed)
//
// Auth (planned, not implemented):
//   The bookmark methods require Authorization: Bearer <SESSION> but
//   no session-issuance layer exists yet. Per CODE_REVIEW C6 the
//   previous implementation accepted any 8-128 char string as a valid
//   session — anyone could read/write any other user's bookmarks by
//   guessing or sniffing the string. To re-enable:
//     1. Add `session.create` method that issues 32-byte tokens bound
//        to a fingerprint (IP+UA hash with SESSION_SALT), stores
//        them in KV as `session:<token>` with a 30-day TTL.
//     2. Update getSession() to validate against KV (look up the
//        token, return null if missing/expired).
//     3. Set env var BOOKMARKS_BACKEND=enabled.

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';
const MAX_BATCH = 20;
// Single allowed origin — `www.` 301-redirects to apex so the
// post-redirect browser-sent Origin is already canonical. Including
// `www.` would widen the allowlist if the 301 ever breaks. (CODE_REVIEW)
const ALLOWED_ORIGINS = new Set([
  'https://chendermatologist.com',
]);

function parseLimit(value, fallback = 8) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(20, Math.max(1, parsed));
}

function corsHeaders(origin) {
  const headers = {
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
  if (origin) headers['Access-Control-Allow-Origin'] = origin;
  return headers;
}

function rpcResp(id, result, error, extraHeaders = {}) {
  const body = error
    ? { jsonrpc: '2.0', error, id: id == null ? null : id }
    : { jsonrpc: '2.0', result, id: id == null ? null : id };
  return new Response(JSON.stringify(body), {
    status: error && error.code === -32700 ? 400 : 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...extraHeaders,
    },
  });
}

async function kvGet(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  const r = await fetch(`${url}/get/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return null;
  const j = await r.json();
  return j.result || null;
}

async function kvSet(key, value, ttlSeconds) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  const path = ttlSeconds
    ? `${url}/set/${encodeURIComponent(key)}?EX=${ttlSeconds}`
    : `${url}/set/${encodeURIComponent(key)}`;
  return fetch(path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(value),
  });
}

async function kvIncr(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return null;
  const r = await fetch(`${url}/incr/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return null;
  const j = await r.json();
  return j.result;
}

async function kvSadd(key, member) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  return fetch(`${url}/sadd/${encodeURIComponent(key)}/${encodeURIComponent(member)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

async function kvSrem(key, member) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  return fetch(`${url}/srem/${encodeURIComponent(key)}/${encodeURIComponent(member)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

async function kvSmembers(key) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) return [];
  const r = await fetch(`${url}/smembers/${encodeURIComponent(key)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) return [];
  const j = await r.json();
  return j.result || [];
}

// CODE_REVIEW C6 — bookmark feature gated until a real session layer
// exists. Previous getSession() accepted any client-asserted Bearer
// string with no KV-side issuance, so anyone could read/write any
// other user's bookmarks by guessing or sniffing the string.
//
// Until a server-side session.create method is implemented (issues
// random tokens bound to IP+UA fingerprint, stored in KV with TTL),
// the bookmark methods return -32004 Unavailable. Set env var
// `BOOKMARKS_BACKEND=enabled` ONLY after the issuance layer is wired.
const BOOKMARKS_BACKEND_ENABLED = process.env.BOOKMARKS_BACKEND === 'enabled';

function getSession(req) {
  if (!BOOKMARKS_BACKEND_ENABLED) return null;
  const auth = req.headers.get('authorization') || '';
  const m = auth.match(/^Bearer\s+([A-Za-z0-9_-]{8,128})$/);
  return m ? m[1] : null;
}

function isValidSlug(s) { return typeof s === 'string' && /^[a-z0-9-]{2,80}$/.test(s); }

function rpcError(e) {
  if (e && typeof e.code === 'number' && typeof e.message === 'string') {
    return { code: e.code, message: e.message };
  }
  return { code: -32603, message: 'Internal error' };
}

// ─── Method registry ───
const methods = {
  'site.health': async () => ({
    ok: true,
    time: new Date().toISOString(),
    region: process.env.VERCEL_REGION || 'unknown',
  }),

  'articles.recent': async ({ n }) => {
    const limit = parseLimit(n, 8);
    // Reuse /api/articles-recent logic via internal call
    const r = await fetch(`https://api.github.com/repos/${REPO}/contents/blog?ref=${BRANCH}`, {
      headers: { Accept: 'application/vnd.github+json' },
    });
    if (!r.ok) throw { code: -32000, message: 'Cannot read blog directory' };
    const files = await r.json();
    return {
      items: (Array.isArray(files) ? files : [])
        .filter(f => f.type === 'file' && /\.html$/.test(f.name) && !/^index/.test(f.name))
        .slice(0, limit)
        .map(f => ({ slug: f.name.replace(/\.html$/, '') })),
    };
  },

  // CODE_REVIEW C6 — bookmark methods return -32004 Unavailable
  // until a real session-issuance layer exists. Set env
  // BOOKMARKS_BACKEND=enabled to re-enable AFTER wiring up
  // server-side session.create with KV-stored tokens.
  'articles.bookmark': async ({ slug }, ctx) => {
    if (!BOOKMARKS_BACKEND_ENABLED) {
      throw { code: -32004, message: 'Bookmark backend not available' };
    }
    if (!ctx.session) throw { code: -32001, message: 'Unauthorized' };
    if (!isValidSlug(slug)) throw { code: -32602, message: 'Invalid slug' };
    await kvSadd(`bm:${ctx.session}`, slug);
    return { ok: true };
  },

  'articles.unbookmark': async ({ slug }, ctx) => {
    if (!BOOKMARKS_BACKEND_ENABLED) {
      throw { code: -32004, message: 'Bookmark backend not available' };
    }
    if (!ctx.session) throw { code: -32001, message: 'Unauthorized' };
    if (!isValidSlug(slug)) throw { code: -32602, message: 'Invalid slug' };
    await kvSrem(`bm:${ctx.session}`, slug);
    return { ok: true };
  },

  'articles.bookmarks': async (_p, ctx) => {
    if (!BOOKMARKS_BACKEND_ENABLED) {
      throw { code: -32004, message: 'Bookmark backend not available' };
    }
    if (!ctx.session) throw { code: -32001, message: 'Unauthorized' };
    const slugs = await kvSmembers(`bm:${ctx.session}`);
    return { slugs };
  },

  'stats.view': async ({ slug }) => {
    if (!isValidSlug(slug)) throw { code: -32602, message: 'Invalid slug' };
    const count = await kvIncr(`view:${slug}`);
    return { ok: true, count };
  },

  'stats.top': async ({ n }) => {
    const limit = parseLimit(n, 10);
    // We'd need a sorted set in production; for now return empty.
    // To enable: replace kvIncr with kvZincrby into a `views:zset` sorted set,
    // then ZRANGE here.
    return { items: [], note: 'sorted-set backend pending' };
  },
};

export default async function handler(req) {
  const origin = req.headers.get('origin') || '';
  if (origin && !ALLOWED_ORIGINS.has(origin)) {
    return new Response(JSON.stringify({ error: 'Forbidden origin' }), {
      status: 403,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        Vary: 'Origin',
      },
    });
  }
  const cors = corsHeaders(origin);

  // CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: cors,
    });
  }

  if (req.method !== 'POST') return rpcResp(null, null, { code: -32600, message: 'POST only' }, cors);

  let envelope;
  try { envelope = await req.json(); }
  catch { return rpcResp(null, null, { code: -32700, message: 'Parse error' }, cors); }

  // Batch support
  const isBatch = Array.isArray(envelope);
  const calls = isBatch ? envelope : [envelope];
  if (isBatch && (calls.length === 0 || calls.length > MAX_BATCH)) {
    return rpcResp(null, null, { code: -32600, message: `Batch size must be 1..${MAX_BATCH}` }, cors);
  }
  const ctx = { session: getSession(req) };

  const results = await Promise.all(calls.map(async (call) => {
    if (!call || call.jsonrpc !== '2.0' || typeof call.method !== 'string') {
      return { jsonrpc: '2.0', error: { code: -32600, message: 'Invalid Request' }, id: call && call.id != null ? call.id : null };
    }
    const fn = methods[call.method];
    if (!fn) {
      return { jsonrpc: '2.0', error: { code: -32601, message: 'Method not found: ' + call.method }, id: call.id };
    }
    try {
      const result = await fn(call.params || {}, ctx);
      return { jsonrpc: '2.0', result, id: call.id };
    } catch (e) {
      return { jsonrpc: '2.0', error: rpcError(e), id: call.id };
    }
  }));

  const body = isBatch ? results : results[0];
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      ...cors,
    },
  });
}
