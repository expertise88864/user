// /api/admin/logout — destroy the admin session.
//
// Clears the KV entry for the current session token + tells the browser
// to drop the dn_admin_session cookie (Max-Age=0 form).
//
// Method:
//   POST → 200 { ok: true } + Set-Cookie: dn_admin_session=; Max-Age=0
//   anything else → 405
//
// Safe to call without an active session (idempotent).

import { destroySession, jsonResp } from './_session.js';

export const config = { runtime: 'edge' };

export default async function handler(req) {
  if (req.method !== 'POST') {
    return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });
  }
  const setCookieHeader = await destroySession(req);
  return jsonResp(200, { ok: true }, { 'Set-Cookie': setCookieHeader });
}
