// /api/admin/login — exchange a GitHub PAT for an HttpOnly session cookie.
//
// Browser POSTs { pat: "ghp_..." } once. Server validates the PAT with
// GitHub /user, confirms the user is in REPO_OWNER_ALLOWLIST, stores the
// PAT in Vercel KV keyed by a random session token, and returns Set-Cookie
// with the session token (HttpOnly Secure SameSite=Strict, 24h TTL).
//
// After this, same-origin admin API calls send the cookie automatically
// and use _session.js to retrieve the PAT server-side. The WYSIWYG keeps
// a separate tab-scoped copy only for its direct GitHub API operations.
//
// Method:
//   POST { pat: "ghp_..." } → 200 { ok: true, login: "expertise88864" }
//                              + Set-Cookie: dn_admin_session=...
//   anything else            → 400/401/405
//
// Security rationale: localStorage and sessionStorage are JS-accessible,
// so an XSS or compromised 3rd-party script can exfiltrate the PAT.
// HttpOnly cookies are not accessible to JS — even XSS can't read them.
// Cookie-authenticated endpoints should not resend the tab-scoped PAT.

import { createSession, jsonResp } from './_session.js';

export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method !== 'POST') {
    return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });
  }
  let body;
  try { body = await req.json(); } catch { return jsonResp(400, { error: 'JSON body required' }); }
  const pat = body && body.pat;
  if (!pat || typeof pat !== 'string') {
    return jsonResp(400, { error: 'pat string required' });
  }
  // Basic shape check before round-tripping to GitHub
  if (!/^(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/.test(pat)) {
    return jsonResp(400, { error: 'pat does not match GitHub PAT shape' });
  }
  try {
    const { login, setCookieHeader } = await createSession(pat);
    return jsonResp(200, { ok: true, login }, { 'Set-Cookie': setCookieHeader });
  } catch (e) {
    const msg = String(e && e.message || e);
    if (msg.includes('not allowlisted')) {
      return jsonResp(403, { error: 'User not allowlisted' });
    }
    if (msg.includes('GitHub')) {
      return jsonResp(401, { error: msg });
    }
    return jsonResp(500, { error: 'Login failed' });
  }
}
