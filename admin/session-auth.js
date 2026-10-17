/* Shared by the editor and its extensions. PATs remain JS-readable in this tab;
 * the HttpOnly cookie is used only for same-origin admin API requests. */
(function () {
  'use strict';
  const PAT_KEY = 'cd_gh_pat';
  const EXP_KEY = 'cd_gh_pat_exp';
  const PENDING_KEY = 'cd_admin_logout_pending';
  // Reasons returned by /api/admin/login (codes only; never provider text).
  const LOGIN_MESSAGES = {
    github_token_invalid: 'GitHub token 無效或已過期，請清除登入後重新登入（重新產生 PAT）。',
    github_forbidden: '這把 GitHub token 沒有讀取 expertise88864/user 的權限，請確認 PAT 已授權此 repository（Contents 讀寫）。',
    github_not_found: '這把 GitHub token 看不到 expertise88864/user：可能未授權此 repository，請重新產生並勾選該 repository。',
    github_rate_limited: 'GitHub API 使用量已達上限，請稍後再登入。',
    github_redirect: 'GitHub 回應了轉址（repository 可能已改名或移動），基於安全未跟隨，請聯絡維護者。',
    github_upstream_error: 'GitHub 服務暫時異常，請稍後再登入。',
    github_timeout: '連線 GitHub 逾時，請稍後再登入。',
    github_fetch_failed: '伺服器無法連線到 GitHub，請稍後再試；若持續發生請檢查部署設定。',
    github_unexpected_status: 'GitHub 回應了未預期的狀態，請稍後再登入。',
    github_response_invalid: 'GitHub 回應內容無法核對，請稍後再登入。',
    user_not_allowlisted: '這個 GitHub 帳號沒有後台權限。',
    login_rate_limited: '登入嘗試次數過多，請 15 分鐘後再試。',
    login_failed: 'GitHub 登入失敗，請確認 PAT、KV 設定與網路連線。',
  };
  function loginMessage(error) {
    const code = error && error.code;
    return Object.prototype.hasOwnProperty.call(LOGIN_MESSAGES, code) ? LOGIN_MESSAGES[code] : LOGIN_MESSAGES.login_failed;
  }
  let pending = false;
  let generation = 0;
  let queue = Promise.resolve();
  function notify() {
    if (typeof window.dispatchEvent === 'function') window.dispatchEvent(new Event('cd-admin-auth-changed'));
  }
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
        generation++;
        clearLocal();
        markPending(true);
        notify();
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
    notify();
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
      let data = null;
      try { data = await response.json(); } catch (_) { data = null; }
      if (!response.ok || !data || data.ok !== true) {
        const failure = new Error('Admin login failed');
        failure.code = data && typeof data.code === 'string' && Object.prototype.hasOwnProperty.call(LOGIN_MESSAGES, data.code)
          ? data.code : response.status === 429 ? 'login_rate_limited' : 'login_failed';
        throw failure;
      }
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
      notify();
      return true;
    });
  }
  function restoreSession() {
    const token = getPat();
    return token ? setPat(token, true) : Promise.resolve();
  }
  try { localStorage.removeItem(PAT_KEY); } catch (_) {}
  window.cdAdminAuth = { getPat, setPat, clearPat, restoreSession, loginMessage, isLogoutPending: () => pending, getRevision: () => generation };
})();
