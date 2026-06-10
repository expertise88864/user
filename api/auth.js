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
// CODE_REVIEW C5: Decap CMS only needs repo content access. Drop `user`
// (was leaking email + profile). Use `public_repo` since the content
// repo (expertise88864/user) is public — narrower blast radius if the
// token is ever exposed via XSS or popup interception.
const SCOPES = 'public_repo';
// Cookie name. `__Host-` prefix locks the cookie to:
//   - exact origin (no Domain attribute allowed)
//   - HTTPS only (Secure required)
//   - Path=/ required
// This makes it impossible for a subdomain or downgrade attack to read.
const STATE_COOKIE = '__Host-oauth_state';

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
        // __Host- prefix requires Path=/ and forbids Domain attribute.
        'Set-Cookie': `${STATE_COOKIE}=${state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`,
        'Cache-Control': 'no-store',
      },
    });
  }

  // Step 2: callback — exchange code for token
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const cookie = req.headers.get('cookie') || '';
  const cookieRe = new RegExp(`${STATE_COOKIE.replace(/[-]/g, '\\$&')}=([^;]+)`);
  const expected = (cookie.match(cookieRe) || [])[1];
  if (!code || !state || state !== expected) {
    return new Response('OAuth state mismatch', {
      status: 400,
      headers: {
        'Cache-Control': 'no-store',
        // Burn the state cookie on mismatch to prevent reuse.
        'Set-Cookie': `${STATE_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
      },
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
      headers: {
        'Cache-Control': 'no-store',
        'Set-Cookie': `${STATE_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
      },
    });
  }
  // Decap CMS protocol: popup sends 'authorizing:github' → opener
  // echoes 'authorizing:github' → popup responds with
  // 'authorization:github:success:...{token}'.
  //
  // OAuth state was already verified above against the HttpOnly __Host-
  // cookie. Keep this handshake byte-compatible with Decap CMS 3.5.0 and
  // accept the echo only from the exact opener WindowProxy.
  const targetOrigin = url.origin;
  const html = `<!doctype html><html><body><script>
    (function () {
      var targetOrigin = ${JSON.stringify(targetOrigin)};
      var openerWindow = window.opener;
      var settled = false;
      function send (status, content) {
        if (settled || !openerWindow) return;
        settled = true;
        openerWindow.postMessage('authorization:github:' + status + ':' + JSON.stringify(content), targetOrigin);
      }
      window.addEventListener('message', function (e) {
        if (e.origin !== targetOrigin) return;
        if (e.source !== openerWindow) return;
        if (e.data === 'authorizing:github') {
          send('success', { token: ${JSON.stringify(token)}, provider: 'github' });
        }
      }, false);
      if (openerWindow) {
        openerWindow.postMessage('authorizing:github', targetOrigin);
      }
      // Auto-cleanup after 60s if opener never responds (e.g., window
      // closed, opener navigated away). Token stays only in memory.
      setTimeout(function () { window.close(); }, 60000);
    })();
  </script><p>Authentication complete. You may close this tab.</p></body></html>`;
  return new Response(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      // Single-use: burn the state cookie now that the flow is complete.
      'Set-Cookie': `${STATE_COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`,
    },
  });
}
