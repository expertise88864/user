// /api/admin/logout — destroy the admin session.
//
// Clears the KV entry for the current session token + tells the browser
// to drop the dn_admin_session cookie (Max-Age=0 form).
//
// Method:
//   POST → 200 { ok: true } + Set-Cookie: dn_admin_session=; Max-Age=0
//   Unconfirmed deletion → 503 { ok: false }, cookie retained for retry.
//   anything else → 405
//
// Safe to call without an active session (idempotent).

import { destroySession, jsonResp } from './_session.js';

export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method !== 'POST') {
    return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });
  }
  try {
    const setCookieHeader = await destroySession(req);
    return jsonResp(200, { ok: true }, { 'Set-Cookie': setCookieHeader });
  } catch (_) {
    // Retain the cookie so a retry can revoke the same server session.
    return jsonResp(503, { ok: false, error: 'Logout not confirmed; retry' });
  }
}
