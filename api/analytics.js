// Vercel serverless function — DISABLED (returns 503).
//
// This endpoint is intentionally disabled until GA4 service-account integration
// is configured. Deployment will succeed without GA4_SERVICE_ACCOUNT_JSON /
// GA4_PROPERTY_ID env vars being set, because this stub doesn't import google-auth-library.
//
// To re-enable:
//   1. Resolve the GCP project owner = GA4 login account match (currently blocked
//      with "電子郵件與 Google 帳戶不符" error in GA4 Property Access Management).
//   2. Restore the original implementation from git history (commit before this stub).
//   3. Set env vars GA4_PROPERTY_ID + GA4_SERVICE_ACCOUNT_JSON in Vercel.
//   4. Redeploy.
//
// In the meantime, view analytics directly at https://analytics.google.com/

export const config = { runtime: 'edge' };

export default function handler() {
  return new Response(
    JSON.stringify({
      error: 'analytics_disabled',
      message: 'GA4 backend not configured. View analytics at https://analytics.google.com/',
    }),
    {
      status: 503,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=3600',
      },
    }
  );
}
