// Vercel serverless function — accept push subscription from browser,
// store it in Vercel KV (Upstash Redis under the hood). Free tier covers
// thousands of subscriptions for a solo blog.
//
// Requires env vars:
//   KV_REST_API_URL      — from Vercel KV dashboard
//   KV_REST_API_TOKEN    — from Vercel KV dashboard
//
// Cost: $0 (free tier: 10K commands/day, 256MB storage). One subscriber
// = ~1 KB. 10K subs = 10 MB. You'll hit free tier limit around 250K subs.

export const config = { runtime: 'edge' };

// Single allowed origin — `www.` 301s to apex so post-redirect
// Origin is canonical. (CODE_REVIEW)
const ALLOWED_ORIGINS = [
  'https://chendermatologist.com',
];
const MAX_ENDPOINT_LENGTH = 2048;
const MAX_P256DH_LENGTH = 256;
const MAX_AUTH_LENGTH = 128;

function corsHeaders(origin) {
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
}

function jsonResp(status, obj, origin) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...(origin ? corsHeaders(origin) : { Vary: 'Origin' }),
    },
  });
}

function isValidSubscription(sub) {
  return Boolean(
    sub &&
    typeof sub.endpoint === 'string' &&
    sub.endpoint.startsWith('https://') &&
    sub.endpoint.length <= MAX_ENDPOINT_LENGTH &&
    sub.keys &&
    typeof sub.keys.p256dh === 'string' &&
    sub.keys.p256dh.length > 0 &&
    sub.keys.p256dh.length <= MAX_P256DH_LENGTH &&
    typeof sub.keys.auth === 'string' &&
    sub.keys.auth.length > 0 &&
    sub.keys.auth.length <= MAX_AUTH_LENGTH
  );
}

export default async function handler(req) {
  const origin = req.headers.get('origin') || '';
  if (!ALLOWED_ORIGINS.includes(origin)) {
    return jsonResp(403, { error: 'Forbidden origin' });
  }
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: corsHeaders(origin),
    });
  }
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST only' }), {
      status: 405,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        Allow: 'POST, OPTIONS',
        ...corsHeaders(origin),
      },
    });
  }
  let sub;
  try {
    sub = await req.json();
  } catch {
    return jsonResp(400, { error: 'Invalid JSON' }, origin);
  }
  if (!isValidSubscription(sub)) {
    return jsonResp(400, { error: 'Invalid push subscription' }, origin);
  }
  // Hash endpoint to use as KV key (avoids logging entire token URL)
  const hash = await sha256(sub.endpoint);
  const key = `push:sub:${hash}`;

  const kvUrl = process.env.KV_REST_API_URL;
  const kvToken = process.env.KV_REST_API_TOKEN;
  if (!kvUrl || !kvToken) {
    return jsonResp(503, { error: 'KV not configured' }, origin);
  }
  // SET key value EX 31536000  (1-year expiry; client re-subscribes on visit)
  const r = await fetch(`${kvUrl}/set/${encodeURIComponent(key)}?EX=31536000`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${kvToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(sub),
  });
  if (!r.ok) {
    return jsonResp(502, { error: 'KV write failed' }, origin);
  }
  // Also push the key into a SET for iteration when broadcasting
  const setResp = await fetch(`${kvUrl}/sadd/push:subs/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${kvToken}` },
  });
  if (!setResp.ok) {
    // Avoid an unreachable orphan value when the membership write fails.
    await fetch(`${kvUrl}/del/${encodeURIComponent(key)}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${kvToken}` },
    }).catch(() => {});
    return jsonResp(502, { error: 'KV index write failed' }, origin);
  }
  return jsonResp(200, { ok: true }, origin);
}

async function sha256(s) {
  const buf = new TextEncoder().encode(s);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}
