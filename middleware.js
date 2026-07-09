// Optional edge Basic-Auth gate for the admin HTML shell (defense-in-depth for
// TD-03). The admin WRITE paths are already protected by an HttpOnly session
// cookie (api/admin/_session.js) + a tab-scoped PAT; this only stops the static
// admin UI from *loading* for anyone who doesn't know a shared secret.
//
// ── INERT BY DEFAULT ────────────────────────────────────────────────────────
// Does nothing unless BOTH ADMIN_BASIC_USER and ADMIN_BASIC_PASS are set in the
// Vercel project environment. Until then every request passes straight through,
// so merging/deploying this file changes NOTHING about current behaviour.
//
// To enable: set ADMIN_BASIC_USER + ADMIN_BASIC_PASS in Vercel → redeploy →
// visiting /admin now prompts for those credentials. Test on a preview URL
// first. To disable again, unset either variable.
//
// Scope: ONLY /admin, /admin.html, and /admin/* (the UI + its JS bundle). It
// does NOT touch /api/* (those keep their own session auth) or any public page.

export const config = {
  matcher: ['/admin', '/admin.html', '/admin/:path*'],
};

// Constant-time string compare so a wrong password can't be inferred by timing.
function safeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) {
    return false;
  }
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}

export default function middleware(request) {
  const user = process.env.ADMIN_BASIC_USER;
  const pass = process.env.ADMIN_BASIC_PASS;

  // Not configured → completely inert (continue to the origin).
  if (!user || !pass) return undefined;

  const header = request.headers.get('authorization') || '';
  if (header.startsWith('Basic ')) {
    let decoded = '';
    try {
      decoded = atob(header.slice(6));
    } catch (_) {
      decoded = '';
    }
    const sep = decoded.indexOf(':');
    if (sep >= 0) {
      const u = decoded.slice(0, sep);
      const p = decoded.slice(sep + 1);
      if (safeEqual(u, user) && safeEqual(p, pass)) {
        return undefined; // authenticated → continue to the admin UI
      }
    }
  }

  return new Response('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="ChenDermatologist Admin", charset="UTF-8"',
      'Cache-Control': 'no-store',
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Robots-Tag': 'noindex',
    },
  });
}
