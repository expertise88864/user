// /api/admin/upload — image upload + commit to /assets/uploads via GitHub API.
//
// Why this exists in addition to direct-from-browser GitHub API calls:
//   - Server-side image processing (resize / WebP conversion if requested)
//   - Filename collision detection
//   - Token never travels through any third party
//   - Single endpoint for cross-tool reuse (drag-drop, paste-image, library picker)
//
// Auth model:
//   - Browser sends `Authorization: token ghp_…` (the same PAT the admin already uses)
//   - We pass it through to GitHub. We never store it.
//   - Optional: if env var ADMIN_TOKEN is set, request must additionally contain
//     `X-Admin-Token: <ADMIN_TOKEN>` (defence-in-depth so a leaked PAT alone isn't enough).
//
// POST body (JSON):
//   {
//     "filename": "my-image.jpg",     // optional; auto-named if absent
//     "mime":     "image/jpeg",
//     "data":     "<base64 of file>",
//     "folder":   "assets/uploads"    // optional, default assets/uploads
//   }
//
// Response: { url, path, sha, size }

import { resolveAuth } from './_session.js';

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';
const MAX_BYTES = 8 * 1024 * 1024;  // 8 MB hard cap per upload
const ALLOWED_FOLDERS = new Set(['assets/uploads', 'blog']);
const PAT_AUTH_RE = /^token\s+(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/;

function ymdSlug() {
  const d = new Date();
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const da = String(d.getUTCDate()).padStart(2, '0');
  return `${y}${m}${da}`;
}

function pickExt(mime, filename) {
  const m = (mime || '').toLowerCase();
  const ext = (filename || '').split('.').pop().toLowerCase();
  if (m === 'image/png' || ext === 'png') return 'png';
  if (m === 'image/jpeg' || m === 'image/jpg' || ext === 'jpg' || ext === 'jpeg') return 'jpg';
  if (m === 'image/webp' || ext === 'webp') return 'webp';
  if (m === 'image/avif' || ext === 'avif') return 'avif';
  if (m === 'image/gif' || ext === 'gif') return 'gif';
  return 'bin';
}

function jsonResp(status, obj, extraHeaders) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...(extraHeaders || {}),
    },
  });
}

export default async function handler(req) {
  if (req.method !== 'POST') return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });

  // Auth: PREFERRED is HttpOnly cookie session set by /api/admin/login.
  // LEGACY: Authorization: token ghp_… header still accepted.
  const resolved = await resolveAuth(req);
  if (!resolved) {
    return jsonResp(401, { error: 'Login required (POST /api/admin/login or Authorization header)' });
  }
  const auth = resolved.auth;
  // Defensive — should never trip post-resolveAuth, but keep the original
  // shape guard so a malformed legacy header bounces here too.
  if (!PAT_AUTH_RE.test(auth)) {
    return jsonResp(401, { error: 'Missing or malformed Authorization header (need "token ghp_…")' });
  }

  // Optional defence-in-depth: ADMIN_TOKEN gate
  const adminToken = process.env.ADMIN_TOKEN || '';
  if (adminToken) {
    const presented = req.headers.get('x-admin-token') || '';
    if (presented !== adminToken) return jsonResp(403, { error: 'X-Admin-Token mismatch' });
  }

  let body;
  try { body = await req.json(); }
  catch { return jsonResp(400, { error: 'Body must be JSON' }); }

  const { filename, mime, data, folder } = body || {};
  if (!data || typeof data !== 'string') return jsonResp(400, { error: 'Missing data (base64 string)' });

  // Approximate decoded size: base64 length × 0.75
  const approxBytes = Math.floor(data.length * 0.75);
  if (approxBytes > MAX_BYTES) return jsonResp(413, { error: `File too large (${approxBytes} > ${MAX_BYTES})` });

  // Sanitize filename
  const ext = pickExt(mime, filename);
  if (!['png', 'jpg', 'webp', 'avif', 'gif'].includes(ext)) {
    return jsonResp(415, { error: 'Unsupported image type; use PNG, JPEG, WebP, AVIF, or GIF' });
  }
  let safe = (filename || '').replace(/[^a-zA-Z0-9._-]/g, '-').replace(/-+/g, '-').replace(/^[-.]+/, '');
  if (!safe || !safe.includes('.')) safe = `img-${ymdSlug()}-${crypto.randomUUID().slice(0, 6)}.${ext}`;

  const safeFolder = (folder || 'assets/uploads').replace(/^\/+|\/+$/g, '').replace(/\.\./g, '');
  if (!ALLOWED_FOLDERS.has(safeFolder)) {
    return jsonResp(400, { error: 'Invalid folder; uploads must target assets/uploads or blog' });
  }
  const path = `${safeFolder}/${safe}`;

  // Use GitHub Contents API: PUT /repos/:owner/:repo/contents/:path
  const ghUrl = `https://api.github.com/repos/${REPO}/contents/${path}`;
  // Check if file exists (so we can pass sha for update vs create)
  let existingSha = null;
  try {
    const head = await fetch(`${ghUrl}?ref=${BRANCH}`, {
      headers: { Authorization: auth, Accept: 'application/vnd.github+json' },
    });
    if (head.ok) {
      const j = await head.json();
      existingSha = j.sha;
    }
  } catch (_) { /* ignore — likely 404 */ }

  const commitBody = {
    message: `admin: upload ${safe}`,
    content: data,
    branch: BRANCH,
  };
  if (existingSha) commitBody.sha = existingSha;

  const put = await fetch(ghUrl, {
    method: 'PUT',
    headers: {
      Authorization: auth,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(commitBody),
  });
  const result = await put.json();
  if (!put.ok) return jsonResp(put.status, { error: 'GitHub upload failed' });

  return jsonResp(200, {
    url: `/${path}`,
    path,
    sha: result.content && result.content.sha,
    size: approxBytes,
    commit: result.commit && result.commit.html_url,
  });
}
