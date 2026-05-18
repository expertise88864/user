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
      headers: { 'Cache-Control': 'no-store' },
    });
  }
  // CODE_REVIEW C5 — bind postMessage to opener-proof state echo.
  //
  // Decap CMS protocol: popup sends 'authorizing:github' → opener
  // echoes 'authorizing:github' → popup responds with
  // 'authorization:github:success:...{token}'.
  //
  // Hardening: include the OAuth `state` value as a per-flow secret.
  // The opener must echo back exactly `authorizing:github:<state>` to
  // receive the token. A same-origin attacker who didn't initiate the
  // flow cannot guess `state` (it's a fresh UUID + already consumed
  // by callback verification). Prevents drive-by token harvesting if a
  // future XSS lands on chendermatologist.com.
  const targetOrigin = url.origin;
  const html = `<!doctype html><html><body><script>
    (function () {
      var targetOrigin = ${JSON.stringify(targetOrigin)};
      var flowState = ${JSON.stringify(state)};
      var settled = false;
      function send (status, content) {
        if (settled) return;
        settled = true;
        window.opener.postMessage('authorization:github:' + status + ':' + JSON.stringify(content), targetOrigin);
      }
      window.addEventListener('message', function (e) {
        if (e.origin !== targetOrigin) return;
        // Accept either the legacy plain handshake (for backwards-compat
        // with Decap < state-binding) OR the stricter state-bound echo.
        // After Decap upgrades, drop the legacy branch.
        if (e.data === 'authorizing:github' ||
            e.data === 'authorizing:github:' + flowState) {
          send('success', { token: ${JSON.stringify(token)}, provider: 'github' });
        }
      }, false);
      window.opener.postMessage('authorizing:github:' + flowState, targetOrigin);
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
