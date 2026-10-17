// Edge-safe GitHub REST transport shared by the cookie-authenticated admin APIs.
//
// Request options are limited to what the Vercel Edge fetch accepts:
//   - no `cache` option; freshness comes from the `Cache-Control: no-cache`
//     request header that every call sends;
//   - `redirect: 'manual'` instead of `redirect: 'error'`. A 3xx (or an
//     opaque redirect) is never followed, so the Authorization header cannot be
//     forwarded to another location, and it is reported as `github_redirect`
//     instead of an indistinguishable network TypeError.
// The repository is fixed by the caller, responses are size-capped and every
// request (including reading its body) has a deadline. Failures are classified
// so the author sees why GitHub could not be read. Logs never include the
// credential or any request header.

export class GitHubRequestError extends Error {
  constructor(code, upstreamStatus = null) {
    super(code);
    this.name = 'GitHubRequestError';
    this.code = code;
    this.upstreamStatus = upstreamStatus;
    this.conflict = upstreamStatus === 409 || upstreamStatus === 422;
  }
}

export const GITHUB_ERROR_CODES = Object.freeze([
  'github_token_invalid', 'github_rate_limited', 'github_forbidden', 'github_not_found',
  'github_redirect', 'github_upstream_error', 'github_timeout', 'github_fetch_failed',
  'github_unexpected_status', 'github_response_invalid',
]);

export function githubStatusCode(response) {
  const status = response.status;
  if (response.type === 'opaqueredirect' || (status >= 300 && status < 400)) return 'github_redirect';
  if (status === 401) return 'github_token_invalid';
  if (status === 403) return response.headers.get('x-ratelimit-remaining') === '0' ? 'github_rate_limited' : 'github_forbidden';
  if (status === 429) return 'github_rate_limited';
  if (status === 404) return 'github_not_found';
  if (status >= 500) return 'github_upstream_error';
  return 'github_unexpected_status';
}

export function githubExceptionCode(error, signal) {
  if (error instanceof GitHubRequestError) return error.code;
  if ((error && (error.name === 'AbortError' || error.name === 'TimeoutError')) || (signal && signal.aborted)) return 'github_timeout';
  return 'github_fetch_failed';
}

const CREDENTIAL = /\b(?:gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,})\b|\b(?:Bearer|token|Basic)\s+[^\s"',;]+/gi;
export function redact(text, secret) {
  let value = String(text == null ? '' : text);
  if (typeof secret === 'string' && secret.length >= 4) value = value.split(secret).join('[redacted]');
  return value.replace(CREDENTIAL, '[redacted]').slice(0, 300);
}

// Only fixed, non-secret fields. `path` is the repository-relative API path
// without its query string; the credential is never part of a path or query.
export function logGitHubFailure(endpoint, path, details, secret) {
  try {
    console.error('[admin-github] ' + JSON.stringify({
      endpoint: String(endpoint || 'unknown'),
      path: redact(String(path || '').split('?')[0], secret),
      status: Number.isInteger(details.status) ? details.status : null,
      code: details.code,
      errorName: details.error ? redact(details.error.name, secret) : null,
      errorMessage: details.error ? redact(details.error.message, secret) : null,
    }));
  } catch (_) { /* Logging must never change the API outcome. */ }
}

async function boundedJson(response, maxBytes) {
  if (!response.body) throw new GitHubRequestError('github_response_invalid', response.status);
  const reader = response.body.getReader(), chunks = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > maxBytes) throw new GitHubRequestError('github_response_invalid', response.status);
      chunks.push(value);
    }
  } finally { try { await reader.cancel(); } catch (_) { /* Already closed. */ } }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try { return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); }
  catch (_) { throw new GitHubRequestError('github_response_invalid', response.status); }
}

// Returns parsed JSON, or null for an optional 404. Throws GitHubRequestError
// for every other outcome; 409/422 are flagged `conflict` for the caller's own
// compare-and-swap error and are not logged as transport failures.
export async function githubRequest({ endpoint, url, path, method = 'GET', pat, accept, userAgent,
  body, timeoutMs, maxBytes, optional = false }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let status = null;
  try {
    const response = await fetch(url, {
      method, redirect: 'manual', signal: controller.signal,
      headers: { Authorization: 'Bearer ' + pat, Accept: accept, 'Content-Type': 'application/json',
        'User-Agent': userAgent, 'Cache-Control': 'no-cache', 'X-GitHub-Api-Version': '2022-11-28' },
      ...(body === undefined ? {} : { body }),
    });
    status = response.status;
    if (optional && status === 404) return null;
    if (status === 409 || status === 422) throw new GitHubRequestError('github_conflict', status);
    if (response.type === 'opaqueredirect' || !response.ok) throw new GitHubRequestError(githubStatusCode(response), status);
    return await boundedJson(response, maxBytes);
  } catch (error) {
    const code = githubExceptionCode(error, controller.signal);
    const failure = error instanceof GitHubRequestError ? error : new GitHubRequestError(code, status);
    if (!failure.conflict) logGitHubFailure(endpoint, path, { status, code, error: error instanceof GitHubRequestError ? null : error }, pat);
    throw failure;
  } finally { clearTimeout(timer); }
}
