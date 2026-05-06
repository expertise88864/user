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

export const config = { runtime: 'nodejs' };

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).setHeader('Allow', 'POST').json({ error: 'POST only' });
    return;
  }
  const auth = req.headers.authorization || '';
  if (!process.env.ADMIN_TOKEN || !auth.endsWith(process.env.ADMIN_TOKEN)) {
    res.status(401).json({ error: 'unauthorized' });
    return;
  }
  const { title, body, url, icon, tag } = req.body || {};
  if (!title || !body) {
    res.status(400).json({ error: 'missing title/body' });
    return;
  }
  webpush.setVapidDetails(
    process.env.VAPID_CONTACT,
    process.env.VAPID_PUBLIC_KEY,
    process.env.VAPID_PRIVATE_KEY
  );

  // Fetch all subscription keys from KV SET
  const kvUrl = process.env.KV_REST_API_URL;
  const kvTok = process.env.KV_REST_API_TOKEN;
  const keysResp = await fetch(`${kvUrl}/smembers/push:subs`, {
    headers: { Authorization: `Bearer ${kvTok}` },
  });
  const keysJson = await keysResp.json();
  const keys = keysJson.result || [];
  const payload = JSON.stringify({ title, body, url: url || '/blog/', icon, tag });

  let sent = 0, dead = 0, err = 0;
  await Promise.all(keys.map(async (key) => {
    try {
      const subResp = await fetch(`${kvUrl}/get/${encodeURIComponent(key)}`, {
        headers: { Authorization: `Bearer ${kvTok}` },
      });
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
  }));
  res.status(200).json({ ok: true, sent, dead, err, total: keys.length });
}
