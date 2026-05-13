// GitHub OAuth proxy for Decap CMS — runs as Vercel serverless function.
// Decap admin loads /admin/, clicks "Login with GitHub", we redirect through here.
//
// Setup:
//   1. https://github.com/settings/developers → New OAuth App
//      - Homepage URL: https://chendermatologist.com
//      - Callback URL: https://chendermatologist.com/api/auth/callback
//   2. Copy Client ID + Secret to Vercel env vars:
//      - OAUTH_CLIENT_ID
//      - OAUTH_CLIENT_SECRET
//
// Routes:
//   GET /api/auth         — start OAuth flow, redirect to GitHub
//   GET /api/auth/callback — GitHub returns code, we exchange for token + post to opener
//
// Reference: https://decapcms.org/docs/external-oauth-clients/

export const config = { runtime: 'edge' };

const GITHUB_AUTHORIZE = 'https://github.com/login/oauth/authorize';
const GITHUB_TOKEN = 'https://github.com/login/oauth/access_token';
const SCOPES = 'repo,user';

export default async function handler(req) {
  if (req.method !== 'GET') {
    return new Response('GET only', {
      status: 405,
      headers: { Allow: 'GET', 'Cache-Control': 'no-store' },
    });
  }
  if (!process.env.OAUTH_CLIENT_ID || !process.env.OAUTH_CLIENT_SECRET) {
    return new Response('OAuth is not configured', {
      status: 503,
      headers: { 'Cache-Control': 'no-store' },
    });
  }
  const url = new URL(req.url);
  const isCallback = url.pathname.endsWith('/callback');

  if (!isCallback) {
    // Step 1: redirect to GitHub authorize
    const state = crypto.randomUUID();
    const params = new URLSearchParams({
      client_id: process.env.OAUTH_CLIENT_ID || '',
      redirect_uri: `${url.origin}/api/auth/callback`,
      scope: SCOPES,
      state,
    });
    return new Response(null, {
      status: 302,
      headers: {
        Location: `${GITHUB_AUTHORIZE}?${params}`,
        'Set-Cookie': `oauth_state=${state}; Path=/api/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
        'Cache-Control': 'no-store',
      },
    });
  }

  // Step 2: callback — exchange code for token
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const cookie = req.headers.get('cookie') || '';
  const expected = (cookie.match(/oauth_state=([^;]+)/) || [])[1];
  if (!code || !state || state !== expected) {
    return new Response('OAuth state mismatch', {
      status: 400,
      headers: { 'Cache-Control': 'no-store' },
    });
  }
  const tokenResp = await fetch(GITHUB_TOKEN, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: process.env.OAUTH_CLIENT_ID,
      client_secret: process.env.OAUTH_CLIENT_SECRET,
      code,
    }),
  });
  const data = await tokenResp.json();
  const token = data.access_token;
  if (!token) {
    return new Response('OAuth failed', {
      status: 400,
      headers: { 'Cache-Control': 'no-store' },
    });
  }
  // Decap expects the popup to postMessage back with auth result
  const targetOrigin = url.origin;
  const html = `<!doctype html><html><body><script>
    (function () {
      var targetOrigin = ${JSON.stringify(targetOrigin)};
      function send (status, content) {
        window.opener.postMessage('authorization:github:' + status + ':' + JSON.stringify(content), targetOrigin);
      }
      window.addEventListener('message', function (e) {
        if (e.origin !== targetOrigin) return;
        if (e.data === 'authorizing:github') {
          send('success', { token: ${JSON.stringify(token)}, provider: 'github' });
        }
      }, false);
      window.opener.postMessage('authorizing:github', targetOrigin);
    })();
  </script><p>Authentication complete. You may close this tab.</p></body></html>`;
  return new Response(html, {
    status: 200,
    headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
  });
}
