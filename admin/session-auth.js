/* Shared by the editor and its extensions. PATs remain JS-readable in this tab;
 * the HttpOnly cookie is used only for same-origin admin API requests. */
(function () {
  'use strict';
  const PAT_KEY = 'cd_gh_pat';
  const EXP_KEY = 'cd_gh_pat_exp';
  const PENDING_KEY = 'cd_admin_logout_pending';
  let pending = false;
  let generation = 0;
  let queue = Promise.resolve();
  try { pending = sessionStorage.getItem(PENDING_KEY) === '1'; } catch (_) {}

  function serialize(operation) {
    const result = queue.then(operation);
    queue = result.catch(() => {});
    return result;
  }
  function clearLocal() {
    for (const key of [PAT_KEY, EXP_KEY]) {
      try { sessionStorage.removeItem(key); } catch (_) {}
    }
    try { localStorage.removeItem(PAT_KEY); } catch (_) {}
  }
  function markPending(value) {
    pending = value;
    try {
      if (value) sessionStorage.setItem(PENDING_KEY, '1');
      else sessionStorage.removeItem(PENDING_KEY);
    } catch (_) {}
  }
  function getPat() {
    if (pending) return '';
    try {
      const token = sessionStorage.getItem(PAT_KEY) || '';
      const expiry = Number(sessionStorage.getItem(EXP_KEY));
      if (token && (!Number.isFinite(expiry) || expiry <= Date.now())) {
        clearLocal();
        markPending(true);
        return '';
      }
      return token;
    } catch (_) { return ''; }
  }
  async function revoke() {
    const response = await fetch('/api/admin/logout', {
      method: 'POST', credentials: 'same-origin', keepalive: true,
    });
    if (!response.ok || (await response.json()).ok !== true) {
      throw new Error('Logout not confirmed');
    }
    markPending(false);
  }
  function clearPat() {
    generation++;
    clearLocal();
    markPending(true);
    // An earlier login may still set a cookie. Revoke only after it settles.
    return serialize(revoke);
  }
  function setPat(token, preserveExpiry = false) {
    const started = generation;
    return serialize(async () => {
      if (!token || pending || started !== generation) throw new Error('Login unavailable');
      const expiry = preserveExpiry ? Number(sessionStorage.getItem(EXP_KEY)) : Date.now() + 86400000;
      if (!Number.isFinite(expiry) || expiry <= Date.now()) throw new Error('Session expired');
      const response = await fetch('/api/admin/login', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pat: token }),
      });
      if (!response.ok || (await response.json()).ok !== true) throw new Error('Admin login failed');
      if (started !== generation) throw new Error('Login cancelled');
      try {
        sessionStorage.setItem(PAT_KEY, token);
        sessionStorage.setItem(EXP_KEY, String(expiry));
      } catch (_) {
        clearLocal();
        markPending(true);
        await revoke();
        throw new Error('Session storage unavailable');
      }
      return true;
    });
  }
  function restoreSession() {
    const token = getPat();
    return token ? setPat(token, true) : Promise.resolve();
  }
  try { localStorage.removeItem(PAT_KEY); } catch (_) {}
  window.cdAdminAuth = { getPat, setPat, clearPat, restoreSession, isLogoutPending: () => pending };
})();
