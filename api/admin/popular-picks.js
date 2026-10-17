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

// Only fixed fields; never the KV URL, token or request headers.
function logFailure(status, code, error) {
  try {
    console.error('[popular-picks] ' + JSON.stringify({endpoint: 'popular-picks', path: 'get/' + KV_KEY,
      status: Number.isInteger(status) ? status : null, code, errorName: error ? String(error.name).slice(0, 80) : null}));
  } catch (_) { /* Logging never changes the public fallback. */ }
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
    // Edge-safe options: no `cache` field (Cache-Control header instead) and
    // manual redirects that are refused below, so the KV token is never
    // forwarded to another location.
    const response = await fetch(`${origin.origin}/get/${encodeURIComponent(KV_KEY)}`, {
      method: 'GET', redirect: 'manual', signal: controller.signal,
      headers: {Authorization: `Bearer ${token}`, 'Cache-Control': 'no-cache'},
    });
    if (response.type === 'opaqueredirect' || (response.status >= 300 && response.status < 400)) {
      logFailure(response.status, 'kv_redirect');
      return {status: 'unavailable'};
    }
    if (!response.ok) { logFailure(response.status, 'kv_status'); return {status: 'unavailable'}; }
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
  } catch (error) {
    logFailure(null, controller.signal.aborted || error?.name === 'AbortError' ? 'kv_timeout' : 'kv_fetch_failed', error);
    return {status: 'unavailable'};
  }
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
