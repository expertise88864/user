// Vercel serverless function — admin-only push broadcast.
// Iterate over all stored subscriptions and send a Web Push notification.
//
// SECURITY:  Protected by ADMIN_TOKEN env var. Send via:
//   curl -X POST https://chendermatologist.com/api/push-send \
//     -H "Authorization: Bearer $ADMIN_TOKEN" \
//     -H "Content-Type: application/json" \
//     -d '{"title":"新文章","body":"...","url":"/blog/foo"}'
//
// Required env vars:
//   ADMIN_TOKEN          — random secret for admin auth (generate with: openssl rand -hex 32)
//   VAPID_PUBLIC_KEY     — from `npx web-push generate-vapid-keys`
//   VAPID_PRIVATE_KEY    — same; KEEP SECRET
//   VAPID_CONTACT        — mailto:expertise88864@gmail.com
//   KV_REST_API_URL      — Vercel KV
//   KV_REST_API_TOKEN    — Vercel KV
//
// Auto-cleans dead subscriptions (410 Gone, 404 Not Found).

import webpush from 'web-push';
import { Buffer } from 'node:buffer';
import { timingSafeEqual } from 'node:crypto';

export const config = { runtime: 'nodejs' };

// CODE_REVIEW — payload caps so a hostile admin token (or compromised
// admin device) can't broadcast a 1 MB blob to every subscriber.
const MAX_TITLE = 100;
const MAX_BODY = 500;
const MAX_URL = 500;
const MAX_ICON = 500;
const MAX_TAG = 64;
const BROADCAST_CONCURRENCY = 20;

function isSafeSiteUrl(value) {
  if (typeof value !== 'string') return false;
  try {
    return new URL(value, 'https://chendermatologist.com').origin === 'https://chendermatologist.com';
  } catch {
    return false;
  }
}

function timingSafeBearerEqual(headerValue, expectedToken) {
  if (!expectedToken) return false;
  const expected = `Bearer ${expectedToken}`;
  const got = String(headerValue || '');
  if (got.length !== expected.length) {
    // Length mismatch — do a constant-time compare against a same-length
    // dummy to keep timing uniform, then return false.
    const dummy = Buffer.alloc(expected.length, 0);
    try { timingSafeEqual(Buffer.alloc(expected.length, 0), dummy); } catch {}
    return false;
  }
  return timingSafeEqual(Buffer.from(got), Buffer.from(expected));
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') {
    res.status(405).setHeader('Allow', 'POST').json({ error: 'POST only' });
    return;
  }
  // Timing-safe comparison so attackers can't measure response latency
  // to probe ADMIN_TOKEN byte-by-byte. (CODE_REVIEW)
  if (!timingSafeBearerEqual(req.headers.authorization, process.env.ADMIN_TOKEN)) {
    res.status(401).json({ error: 'unauthorized' });
    return;
  }
  const { title, body, url, icon, tag } = req.body || {};
  if (!title || !body) {
    res.status(400).json({ error: 'missing title/body' });
    return;
  }
  // Length caps prevent runaway broadcast payloads. Web Push spec
  // limits typical bodies to ~4 KB encrypted; these caps stay well
  // under that and keep notification text readable. (CODE_REVIEW)
  if (typeof title !== 'string' || title.length > MAX_TITLE) {
    res.status(400).json({ error: `title must be ≤ ${MAX_TITLE} chars` });
    return;
  }
  if (typeof body !== 'string' || body.length > MAX_BODY) {
    res.status(400).json({ error: `body must be ≤ ${MAX_BODY} chars` });
    return;
  }
  if (url !== undefined && (url.length > MAX_URL || !isSafeSiteUrl(url))) {
    res.status(400).json({ error: 'url must be relative or under chendermatologist.com' });
    return;
  }
  if (icon !== undefined && (icon.length > MAX_ICON || !isSafeSiteUrl(icon))) {
    res.status(400).json({ error: 'icon must be relative or under chendermatologist.com' });
    return;
  }
  if (tag !== undefined && (typeof tag !== 'string' || tag.length > MAX_TAG)) {
    res.status(400).json({ error: `tag must be ≤ ${MAX_TAG} chars` });
    return;
  }
  const vapidContact = process.env.VAPID_CONTACT;
  const vapidPublicKey = process.env.VAPID_PUBLIC_KEY;
  const vapidPrivateKey = process.env.VAPID_PRIVATE_KEY;
  if (!vapidContact || !vapidPublicKey || !vapidPrivateKey) {
    res.status(503).json({ error: 'VAPID not configured' });
    return;
  }
  try {
    webpush.setVapidDetails(vapidContact, vapidPublicKey, vapidPrivateKey);
  } catch {
    res.status(503).json({ error: 'VAPID configuration invalid' });
    return;
  }

  // Fetch all subscription keys from KV SET
  const kvUrl = process.env.KV_REST_API_URL;
  const kvTok = process.env.KV_REST_API_TOKEN;
  if (!kvUrl || !kvTok) {
    res.status(503).json({ error: 'KV not configured' });
    return;
  }
  const keysResp = await fetch(`${kvUrl}/smembers/push:subs`, {
    headers: { Authorization: `Bearer ${kvTok}` },
  });
  if (!keysResp.ok) {
    res.status(502).json({ error: 'KV subscription index read failed' });
    return;
  }
  const keysJson = await keysResp.json();
  const keys = Array.isArray(keysJson.result) ? keysJson.result : [];
  const payload = JSON.stringify({ title, body, url: url || '/blog/', icon, tag });

  let sent = 0, dead = 0, err = 0;
  async function sendToKey(key) {
    try {
      const subResp = await fetch(`${kvUrl}/get/${encodeURIComponent(key)}`, {
        headers: { Authorization: `Bearer ${kvTok}` },
      });
      if (!subResp.ok) {
        err++;
        return;
      }
      const subJson = await subResp.json();
      const sub = JSON.parse(subJson.result || 'null');
      if (!sub) return;
      try {
        await webpush.sendNotification(sub, payload, { TTL: 86400 });
        sent++;
      } catch (e) {
        if (e.statusCode === 410 || e.statusCode === 404) {
          // Dead subscription — purge from KV
          await fetch(`${kvUrl}/del/${encodeURIComponent(key)}`, {
            method: 'POST', headers: { Authorization: `Bearer ${kvTok}` },
          });
          await fetch(`${kvUrl}/srem/push:subs/${encodeURIComponent(key)}`, {
            method: 'POST', headers: { Authorization: `Bearer ${kvTok}` },
          });
          dead++;
        } else { err++; }
      }
    } catch { err++; }
  }
  for (let i = 0; i < keys.length; i += BROADCAST_CONCURRENCY) {
    await Promise.all(keys.slice(i, i + BROADCAST_CONCURRENCY).map(sendToKey));
  }
  res.status(200).json({ ok: true, sent, dead, err, total: keys.length });
}
