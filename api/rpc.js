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
//   articles.bookmark        → { ok }                  (server-side bookmark sync; auth)
//   articles.unbookmark      → { ok }
//   articles.bookmarks       → { slugs: [...] }
//   stats.view               → { ok }                  (increment view count)
//   stats.top                → { items: [...] }        (top viewed)
//
// Auth: methods that mutate state require Authorization: Bearer <SESSION>
//   Sessions are anonymous opaque tokens stored in localStorage.
//   For now: SESSION = sha256(IP + userAgent + 'salt'); KV stores per-session
//   state. No login system yet.

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';

function rpcResp(id, result, error) {
  const body = error
    ? { jsonrpc: '2.0', error, id: id == null ? null : id }
    : { jsonrpc: '2.0', result, id: id == null ? null : id };
  return new Response(JSON.stringify(body), {
    status: error && error.code === -32700 ? 400 : 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
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

function getSession(req) {
  const auth = req.headers.get('authorization') || '';
  const m = auth.match(/^Bearer\s+([A-Za-z0-9_-]{8,128})$/);
  return m ? m[1] : null;
}

function isValidSlug(s) { return typeof s === 'string' && /^[a-z0-9-]{2,80}$/.test(s); }

// ─── Method registry ───
const methods = {
  'site.health': async () => ({
    ok: true,
    time: new Date().toISOString(),
    region: process.env.VERCEL_REGION || 'unknown',
  }),

  'articles.recent': async ({ n }) => {
    const limit = Math.min(20, Math.max(1, n || 8));
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

  'articles.bookmark': async ({ slug }, ctx) => {
    if (!ctx.session) throw { code: -32001, message: 'Unauthorized' };
    if (!isValidSlug(slug)) throw { code: -32602, message: 'Invalid slug' };
    await kvSadd(`bm:${ctx.session}`, slug);
    return { ok: true };
  },

  'articles.unbookmark': async ({ slug }, ctx) => {
    if (!ctx.session) throw { code: -32001, message: 'Unauthorized' };
    if (!isValidSlug(slug)) throw { code: -32602, message: 'Invalid slug' };
    await kvSrem(`bm:${ctx.session}`, slug);
    return { ok: true };
  },

  'articles.bookmarks': async (_p, ctx) => {
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
    const limit = Math.min(20, Math.max(1, n || 10));
    // We'd need a sorted set in production; for now return empty.
    // To enable: replace kvIncr with kvZincrby into a `views:zset` sorted set,
    // then ZRANGE here.
    return { items: [], note: 'sorted-set backend pending' };
  },
};

export default async function handler(req) {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '86400',
      },
    });
  }

  if (req.method !== 'POST') return rpcResp(null, null, { code: -32600, message: 'POST only' });

  let envelope;
  try { envelope = await req.json(); }
  catch { return rpcResp(null, null, { code: -32700, message: 'Parse error' }); }

  // Batch support
  const isBatch = Array.isArray(envelope);
  const calls = isBatch ? envelope : [envelope];
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
      const error = (e && typeof e.code === 'number') ? e : { code: -32603, message: String(e && e.message || e) };
      return { jsonrpc: '2.0', error, id: call.id };
    }
  }));

  const body = isBatch ? results : results[0];
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
    },
  });
}
