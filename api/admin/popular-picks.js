// G2 — Admin endpoint to read/write DN.POPULAR_PICKS via Vercel KV.
//
// Why: previously POPULAR_PICKS was hard-coded in blog-shared.js. Updating it
// required a code commit + redeploy. With this endpoint, the admin UI can
// change "熱門推薦" instantly without git push.
//
// On the public side, blog-shared.js fetches /api/popular-picks (no auth) at
// runtime and falls back to its hard-coded default if KV is empty.
//
// Methods:
//   GET  → returns { picks: [...] }                 (public, KV-backed)
//   POST → updates picks. Body: { picks: ["slug1", ...] }   (PAT required)
//
// KV keys:
//   dn:popular-picks  → JSON array of slugs

export const config = { runtime: 'edge' };

const KV_KEY = 'dn:popular-picks';
const MAX_PICKS = 12;
const PAT_AUTH_RE = /^token\s+(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/;

const FALLBACK = [
  'acne-myths',
  'sunscreen-myths',
  'eczema-myths',
  'topical-steroids-guide',
  'hairloss-myths',
];

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

async function kvSet(key, value) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  const r = await fetch(`${url}/set/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(value),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`KV set failed: ${r.status} ${t}`);
  }
}

export default async function handler(req) {
  // Public read
  if (req.method === 'GET') {
    const stored = await kvGet(KV_KEY);
    return jsonResp(200, { picks: stored || FALLBACK, fallback: !stored }, {
      // Edge cache 60s, stale-while-revalidate 5 min
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      'Access-Control-Allow-Origin': '*',
    });
  }

  // Admin write
  if (req.method === 'POST') {
    const auth = req.headers.get('authorization') || '';
    if (!PAT_AUTH_RE.test(auth)) {
      return jsonResp(401, { error: 'Missing Authorization (PAT)' });
    }
    // 2026-05-25 — actually validate the bearer against GitHub. Previously
    // the endpoint only regex-checked the token's shape, so any random
    // string of the right pattern could mutate KV. Now we round-trip to
    // GitHub's /user endpoint and require (a) HTTP 200, (b) the
    // authenticated login is in REPO_OWNER_ALLOWLIST.
    const REPO_OWNER_ALLOWLIST = new Set(['expertise88864']);
    let userLogin = null;
    try {
      const ghResp = await fetch('https://api.github.com/user', {
        headers: {
          Authorization: auth, // pass through "token gh..."
          'User-Agent': 'ChenDermatologist-Admin/1.0',
          Accept: 'application/vnd.github+json',
        },
      });
      if (!ghResp.ok) {
        return jsonResp(401, { error: 'GitHub rejected the token' });
      }
      const u = await ghResp.json();
      userLogin = u && u.login;
    } catch (_) {
      return jsonResp(502, { error: 'GitHub validation failed' });
    }
    if (!userLogin || !REPO_OWNER_ALLOWLIST.has(userLogin)) {
      return jsonResp(403, { error: 'Token user not allowlisted' });
    }
    let body;
    try { body = await req.json(); } catch { return jsonResp(400, { error: 'JSON body required' }); }
    const picks = body && body.picks;
    if (!Array.isArray(picks)) return jsonResp(400, { error: 'picks must be an array' });
    if (picks.length === 0 || picks.length > MAX_PICKS) {
      return jsonResp(400, { error: `picks length must be 1..${MAX_PICKS}` });
    }
    const cleaned = picks
      .filter(s => typeof s === 'string')
      .map(s => s.trim())
      .filter(s => /^[a-z0-9-]+$/.test(s));
    if (cleaned.length !== picks.length) {
      return jsonResp(400, { error: 'invalid slug format (only a-z 0-9 -)' });
    }
    if (new Set(cleaned).size !== cleaned.length) {
      return jsonResp(400, { error: 'duplicate slugs are not allowed' });
    }
    try {
      await kvSet(KV_KEY, cleaned);
    } catch (e) {
      return jsonResp(503, { error: 'Popular picks update failed' });
    }
    return jsonResp(200, { ok: true, picks: cleaned });
  }

  return jsonResp(405, { error: 'GET or POST only' }, { Allow: 'GET, POST' });
}
