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

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'POST only' }), {
      status: 405,
      headers: { 'Content-Type': 'application/json', 'Allow': 'POST' },
    });
  }
  const ALLOWED_ORIGINS = [
    'https://chendermatologist.com',
    'https://www.chendermatologist.com',
  ];
  const origin = req.headers.get('origin') || '';
  if (!ALLOWED_ORIGINS.includes(origin)) {
    return new Response('Forbidden origin', { status: 403 });
  }
  let sub;
  try {
    sub = await req.json();
  } catch {
    return new Response('Invalid JSON', { status: 400 });
  }
  if (!sub || !sub.endpoint) {
    return new Response('Missing endpoint', { status: 400 });
  }
  // Hash endpoint to use as KV key (avoids logging entire token URL)
  const hash = await sha256(sub.endpoint);
  const key = `push:sub:${hash}`;

  const kvUrl = process.env.KV_REST_API_URL;
  const kvToken = process.env.KV_REST_API_TOKEN;
  if (!kvUrl || !kvToken) {
    return new Response('KV not configured', { status: 503 });
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
    return new Response('KV write failed', { status: 502 });
  }
  // Also push the key into a SET for iteration when broadcasting
  await fetch(`${kvUrl}/sadd/push:subs/${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${kvToken}` },
  });
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin,
    },
  });
}

async function sha256(s) {
  const buf = new TextEncoder().encode(s);
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}
