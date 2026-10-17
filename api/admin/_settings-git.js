// Fixed-repository immutable Git reads and bounded requests for site settings.
import { contract, SHA, fail } from './_site-settings.js';
import { githubRequest, GitHubRequestError, logGitHubFailure } from './_github-fetch.js';
const encoder = new TextEncoder();
export function settingsGit(pat) {
  const trees = new Map();
  const commits = new Map();
  const deadline = Date.now() + 22_000;
  async function api(method, path, body, optional = false) {
    if (typeof path !== 'string' || path.startsWith('/') || path.includes('://') || path.includes('..')) fail(502, 'invalid_settings_repository');
    const left = deadline - Date.now();
    if (left <= 0) {
      logGitHubFailure('site-settings', path, { status: null, code: 'github_timeout', error: null }, pat);
      fail(502, 'github_timeout');
    }
    try {
      return await githubRequest({ endpoint: 'site-settings', url: 'https://api.github.com/repos/' + contract.repository + '/' + path, path,
        method, pat, body: body === undefined ? undefined : JSON.stringify(body), timeoutMs: Math.min(left, 12_000), maxBytes: 3_000_000,
        optional, accept: path.startsWith('contents/') ? 'application/vnd.github.object+json' : 'application/vnd.github+json',
        userAgent: 'ChenDermatologist-Settings/1.0' });
    } catch (error) {
      if (error instanceof GitHubRequestError) fail(error.conflict ? 409 : 502, error.conflict ? 'settings_conflict' : error.code);
      fail(502, 'github_fetch_failed');
    }
  }
  async function ref(branch) {
    const data = await api('GET', 'git/ref/heads/' + encodeURIComponent(branch), undefined, true);
    if (data === null) return null;
    if (data.ref !== 'refs/heads/' + branch || data.object?.type !== 'commit' || !SHA.test(data.object.sha || '')) fail(502, 'invalid_settings_repository');
    return data.object.sha;
  }
  function commit(head) {
    if (!SHA.test(head || '')) fail(502, 'invalid_settings_repository');
    if (!commits.has(head)) commits.set(head, (async () => {
      const data = await api('GET', 'git/commits/' + head);
      if (data.sha !== head || !SHA.test(data.tree?.sha || '') || !Array.isArray(data.parents) ||
          data.parents.length > 2 || data.parents.some(parent => !SHA.test(parent?.sha || ''))) fail(502, 'invalid_settings_repository');
      return data;
    })());
    return commits.get(head);
  }
  function tree(head) {
    if (!SHA.test(head || '')) fail(502, 'invalid_settings_repository');
    if (!trees.has(head)) trees.set(head, (async () => {
      const record = await commit(head);
      const data = await api('GET', 'git/trees/' + record.tree.sha + '?recursive=1');
      if (data.sha !== record.tree.sha || data.truncated !== false || !Array.isArray(data.tree) || data.tree.length > 10000) fail(502, 'invalid_settings_repository');
      const entries = new Map();
      for (const entry of data.tree) {
        if (typeof entry.path !== 'string' || entries.has(entry.path)) fail(502, 'invalid_settings_repository');
        entries.set(entry.path, entry);
      }
      return { sha: record.tree.sha, entries };
    })());
    return trees.get(head);
  }
  async function file(path, head, optional = false) {
    const entry = (await tree(head)).entries.get(path);
    if (!entry && optional) return null;
    if (!entry || entry.type !== 'blob' || entry.mode !== '100644' || !SHA.test(entry.sha || '')) fail(502, 'invalid_settings_repository');
    const data = await api('GET', 'contents/' + path + '?ref=' + head);
    const limit = path === contract.catalog ? 200_000 : 32_000;
    if (data.type !== 'file' || data.sha !== entry.sha || data.encoding !== 'base64' || !Number.isInteger(data.size) || data.size < 0 || data.size > limit || typeof data.content !== 'string') fail(502, 'invalid_settings_repository');
    const encoded = data.content.replace(/\s/g, '');
    if (encoded.length !== Math.ceil(data.size / 3) * 4 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded)) fail(502, 'invalid_settings_repository');
    let bytes;
    try { bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0)); } catch (_) { fail(502, 'invalid_settings_repository'); }
    if (bytes.byteLength !== data.size) fail(502, 'invalid_settings_repository');
    const header = encoder.encode('blob ' + bytes.byteLength + '\0'), object = new Uint8Array(header.length + bytes.byteLength);
    object.set(header); object.set(bytes, header.length);
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-1', object))].map(byte => byte.toString(16).padStart(2, '0')).join('');
    if (digest !== data.sha) fail(502, 'invalid_settings_repository');
    try { return { sha: data.sha, content: new TextDecoder('utf-8', { fatal: true }).decode(bytes) }; } catch (_) { fail(502, 'invalid_settings_repository'); }
  }
  return { api, ref, commit, tree, file };
}
