// Vercel serverless function — proxy GA4 Data API for the dashboard.
// Returns aggregated analytics JSON without exposing the GA4 service-account key
// to the browser. Caches for 1 hour to stay within free tier (5K requests/day).
//
// Required env vars:
//   GA4_PROPERTY_ID            — e.g. "489173824"
//   GA4_SERVICE_ACCOUNT_JSON   — full JSON of GCP service-account key (one-line, no formatting)
//
// Setup:
//   1. Cloud Console → IAM → Create service account → grant "Viewer" on GA4 property
//   2. Generate JSON key, paste entire JSON into GA4_SERVICE_ACCOUNT_JSON env var
//   3. GA4 admin → Property → Property Access Management → add the service-account email as Viewer
//
// Returns:
//   {
//     pageviews_30d: { date: 'YYYY-MM-DD', views: N }[],
//     top_articles: { path: string, views: N, avg_time_sec: N }[],
//     by_country: { country: string, users: N }[],
//     search_terms: { term: string, count: N }[]   // requires custom event "site_search"
//   }

import { GoogleAuth } from 'google-auth-library';

export const config = { runtime: 'nodejs', maxDuration: 10 };

let cache = { data: null, ts: 0 };
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.status(405).json({ error: 'GET only' });
    return;
  }
  // Optional: lock to admin-only via ?token=
  if (process.env.ANALYTICS_TOKEN && req.query.token !== process.env.ANALYTICS_TOKEN) {
    res.status(401).json({ error: 'unauthorized' });
    return;
  }
  const now = Date.now();
  if (cache.data && (now - cache.ts) < CACHE_TTL_MS) {
    res.setHeader('Cache-Control', 'public, max-age=300, stale-while-revalidate=3600');
    res.setHeader('X-Cache', 'HIT');
    res.status(200).json(cache.data);
    return;
  }
  const propertyId = process.env.GA4_PROPERTY_ID;
  const credsJson = process.env.GA4_SERVICE_ACCOUNT_JSON;
  if (!propertyId || !credsJson) {
    res.status(503).json({ error: 'GA4 not configured' });
    return;
  }
  try {
    const credentials = JSON.parse(credsJson);
    const auth = new GoogleAuth({
      credentials,
      scopes: ['https://www.googleapis.com/auth/analytics.readonly'],
    });
    const client = await auth.getClient();
    const baseUrl = `https://analyticsdata.googleapis.com/v1beta/properties/${propertyId}:runReport`;

    async function runReport(body) {
      const resp = await client.request({
        url: baseUrl,
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        data: body,
      });
      return resp.data;
    }

    // 30-day pageview timeline
    const pv = await runReport({
      dateRanges: [{ startDate: '30daysAgo', endDate: 'today' }],
      dimensions: [{ name: 'date' }],
      metrics: [{ name: 'screenPageViews' }],
      orderBys: [{ dimension: { dimensionName: 'date' } }],
    });
    // Top 10 articles by views
    const top = await runReport({
      dateRanges: [{ startDate: '30daysAgo', endDate: 'today' }],
      dimensions: [{ name: 'pagePath' }],
      metrics: [{ name: 'screenPageViews' }, { name: 'averageSessionDuration' }],
      dimensionFilter: { filter: { fieldName: 'pagePath', stringFilter: { matchType: 'BEGINS_WITH', value: '/blog/' } } },
      orderBys: [{ metric: { metricName: 'screenPageViews' }, desc: true }],
      limit: 10,
    });
    // Top countries
    const cn = await runReport({
      dateRanges: [{ startDate: '30daysAgo', endDate: 'today' }],
      dimensions: [{ name: 'country' }],
      metrics: [{ name: 'totalUsers' }],
      orderBys: [{ metric: { metricName: 'totalUsers' }, desc: true }],
      limit: 10,
    });
    // Search terms (requires custom event "site_search")
    const sr = await runReport({
      dateRanges: [{ startDate: '30daysAgo', endDate: 'today' }],
      dimensions: [{ name: 'customEvent:search_term' }],
      metrics: [{ name: 'eventCount' }],
      dimensionFilter: { filter: { fieldName: 'eventName', stringFilter: { value: 'site_search' } } },
      orderBys: [{ metric: { metricName: 'eventCount' }, desc: true }],
      limit: 15,
    }).catch(() => ({ rows: [] }));

    const data = {
      pageviews_30d: (pv.rows || []).map((r) => ({
        date: r.dimensionValues[0].value,
        views: parseInt(r.metricValues[0].value, 10),
      })),
      top_articles: (top.rows || []).map((r) => ({
        path: r.dimensionValues[0].value,
        views: parseInt(r.metricValues[0].value, 10),
        avg_time_sec: parseFloat(r.metricValues[1].value),
      })),
      by_country: (cn.rows || []).map((r) => ({
        country: r.dimensionValues[0].value,
        users: parseInt(r.metricValues[0].value, 10),
      })),
      search_terms: (sr.rows || []).map((r) => ({
        term: r.dimensionValues[0].value,
        count: parseInt(r.metricValues[0].value, 10),
      })),
      generated_at: new Date().toISOString(),
    };
    cache = { data, ts: now };
    res.setHeader('Cache-Control', 'public, max-age=300, stale-while-revalidate=3600');
    res.setHeader('X-Cache', 'MISS');
    res.status(200).json(data);
  } catch (e) {
    res.status(500).json({ error: 'GA4 query failed', detail: e.message });
  }
}
