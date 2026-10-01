// Read-only public recommendations. Changes use the version-bound settings
// draft/author request and normal candidate CI/Preview/production delivery.
// Bootstrap retains legacy KV reads until the author explicitly saves picks.
import settingsSource from '../../_site_settings.json';
import settingsCatalog from '../../assets/settings-catalog.json';
import { catalogOf, projectSettings } from './_site-settings.js';

export const config = { runtime: 'edge' };
const KV_KEY = 'dn:popular-picks';

function jsonResp(status, obj, extraHeaders) {
  return new Response(JSON.stringify(obj), {status, headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...(extraHeaders || {}),
  }});
}

async function legacyPicks(articles) {
  const endpoint = process.env.KV_REST_API_URL, token = process.env.KV_REST_API_TOKEN;
  if (!endpoint || !token) return {status: 'unavailable'};
  let origin;
  try {
    origin = new URL(endpoint);
    if (origin.protocol !== 'https:' || origin.username || origin.password || origin.search || origin.hash ||
        origin.pathname !== '/') return {status: 'unavailable'};
  } catch (_) { return {status: 'unavailable'}; }
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${origin.origin}/get/${encodeURIComponent(KV_KEY)}`, {
      method: 'GET', redirect: 'error', cache: 'no-store', signal: controller.signal,
      headers: {Authorization: `Bearer ${token}`},
    });
    if (!response.ok) return {status: 'unavailable'};
    const reader = response.body?.getReader(); if (!reader) return {status: 'unavailable'};
    const chunks = []; let length = 0;
    try {
      for (;;) {
        const {done, value} = await reader.read(); if (done) break;
        length += value.byteLength; if (length > 128000) return {status: 'unavailable'};
        chunks.push(value);
      }
    } finally { await reader.cancel(); }
    const bytes = new Uint8Array(length); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    const payload = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
    if (!payload || !Object.hasOwn(payload, 'result')) return {status: 'unavailable'};
    if (payload.result === null) return {status: 'empty'};
    if (typeof payload.result !== 'string') return {status: 'invalid'};
    let picks; try { picks = JSON.parse(payload.result); } catch (_) { return {status: 'invalid'}; }
    const publicSlugs = new Set(articles.map(item => item.slug));
    if (!Array.isArray(picks) || !picks.length || picks.length > 12 || new Set(picks).size !== picks.length ||
        picks.some(slug => typeof slug !== 'string' || !publicSlugs.has(slug))) return {status: 'invalid'};
    return {status: 'verified', picks};
  } catch (_) { return {status: 'unavailable'}; }
  finally { clearTimeout(timer); }
}

export default async function handler(req) {
  // No authentication can turn this retired endpoint into a direct write.
  if (req.method !== 'GET') return jsonResp(405, {error: 'GET only; use settings drafts for changes'}, { Allow: 'GET' });
  let articles, settings;
  try { articles = catalogOf(settingsCatalog); settings = projectSettings(settingsSource, articles); }
  catch (_) { return jsonResp(503, {error: 'Recommendations configuration unavailable'}); }
  const legacy = settings.legacyPicks ? await legacyPicks(articles) : null;
  const body = legacy ? {picks: legacy.picks || settings.picks, fallback: legacy.status !== 'verified',
    source: legacy.status === 'verified' ? 'legacy' : 'legacy-fallback', legacyStatus: legacy.status} :
    {picks: settings.picks, fallback: false, source: 'site-settings'};
  return jsonResp(200, body, {'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300', 'Access-Control-Allow-Origin': '*'});
}
