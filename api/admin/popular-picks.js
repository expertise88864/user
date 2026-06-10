// Public read and authenticated admin write for DN.POPULAR_PICKS.
//
// GET is cached at the edge and lets blog-shared.js refresh the hard-coded
// fallback without a redeploy. POST requires the HttpOnly admin session set
// by /api/admin/login.

import { getSession } from './_session.js';

export const config = { runtime: 'edge' };

const KV_KEY = 'dn:popular-picks';
const MAX_PICKS = 12;
const FALLBACK = [
  'acne-myths',
  'sunscreen-myths',
  'atopic-dermatitis-overview',
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
    const response = await fetch(`${url}/get/${encodeURIComponent(key)}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    const payload = await response.json();
    return payload.result ? JSON.parse(payload.result) : null;
  } catch (_) {
    return null;
  }
}

async function kvSet(key, value) {
  const url = process.env.KV_REST_API_URL;
  const token = process.env.KV_REST_API_TOKEN;
  if (!url || !token) throw new Error('KV not configured');
  const response = await fetch(`${url}/set/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(value),
  });
  if (!response.ok) throw new Error('KV write failed');
}

export default async function handler(req) {
  if (req.method === 'GET') {
    const stored = await kvGet(KV_KEY);
    return jsonResp(200, { picks: stored || FALLBACK, fallback: !stored }, {
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      'Access-Control-Allow-Origin': '*',
    });
  }

  if (req.method === 'POST') {
    const session = await getSession(req);
    if (!session) {
      return jsonResp(401, { error: 'Login required' });
    }

    let body;
    try {
      body = await req.json();
    } catch {
      return jsonResp(400, { error: 'JSON body required' });
    }

    const picks = body && body.picks;
    if (!Array.isArray(picks)) {
      return jsonResp(400, { error: 'picks must be an array' });
    }
    if (picks.length === 0 || picks.length > MAX_PICKS) {
      return jsonResp(400, { error: `picks length must be 1..${MAX_PICKS}` });
    }

    const cleaned = picks
      .filter(slug => typeof slug === 'string')
      .map(slug => slug.trim())
      .filter(slug => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug));
    if (cleaned.length !== picks.length) {
      return jsonResp(400, { error: 'invalid slug format' });
    }
    if (new Set(cleaned).size !== cleaned.length) {
      return jsonResp(400, { error: 'duplicate slugs are not allowed' });
    }

    try {
      await kvSet(KV_KEY, cleaned);
    } catch (_) {
      return jsonResp(503, { error: 'Popular picks update failed' });
    }
    return jsonResp(200, { ok: true, picks: cleaned });
  }

  return jsonResp(405, { error: 'GET or POST only' }, { Allow: 'GET, POST' });
}
