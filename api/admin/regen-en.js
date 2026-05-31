// /api/admin/regen-en — trigger /en/ mirror regeneration for one slug.
//
// How it works:
//   - Browser sends POST { slug: "epidermoid-cyst" }
//   - We fetch the source HTML from GitHub raw, generate the EN-only mirror via
//     the same logic as _gen_en_pages.py (replace data-zh→data-en, hide untranslated, etc.),
//     and commit the result to /en/blog/<slug>.html.
//   - Returns the path written + commit URL.
//
// This avoids the need to push from local Python — admin can refresh /en/ on demand.
//
// Auth: PREFERRED is HttpOnly cookie session set by /api/admin/login (the
// PAT is stored in KV server-side; browser never sees it again). LEGACY
// fallback accepts Authorization: token ghp_... header (for back-compat
// during the admin UI Phase 2 migration). Both paths are validated against
// the same REPO_OWNER_ALLOWLIST in _session.js.

import { resolveAuth, jsonResp as _jsonResp } from './_session.js';

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';
const PAT_AUTH_RE = /^token\s+(?:gh[pousr]_[A-Za-z0-9_]{20,255}|github_pat_[A-Za-z0-9_]{20,255})$/;

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

// Convert ZH HTML → EN HTML using the same rules as _gen_en_pages.py
function zhToEn(html) {
  // 1. Set <html lang="en">
  html = html.replace(/<html\s+lang="zh-Hant-TW"/, '<html lang="en"');

  // 2. Add canonical / hreflang for /en/ mirror
  html = html.replace(/<link\s+rel="canonical"\s+href="([^"]+)"\s*\/?>/, (m, h) => {
    const enHref = h.replace('chendermatologist.com/', 'chendermatologist.com/en/');
    return `<link rel="canonical" href="${enHref}" />`;
  });

  // 3. Replace text in elements that have data-en attribute
  // <tag ... data-zh="..." data-en="EN" ...>ZH</tag>  →  <tag ...>EN</tag>
  html = html.replace(
    /(<(?:h[1-6]|p|li|strong|em|span|small|th|td|figcaption|summary|a|button|div)\b[^>]*?\bdata-en="([^"]*)"[^>]*>)([^<]*)(<\/(?:h[1-6]|p|li|strong|em|span|small|th|td|figcaption|summary|a|button|div)>)/g,
    (m, openTag, en, _zhInside, closeTag) => {
      if (!en) return m;
      // decode &quot; back to "
      const enDecoded = en.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
      return openTag + enDecoded + closeTag;
    }
  );

  // 4. Add a banner indicating this is an auto-generated EN mirror
  if (!html.includes('en-mirror-banner')) {
    html = html.replace(
      /<body([^>]*)>/,
      `<body$1><div class="en-mirror-banner" style="background:#fef3c7;color:#854d0e;padding:6px 16px;font-size:12.5px;text-align:center;border-bottom:1px solid #fcd34d">Note: This page was auto-translated from the original Chinese article. <a href="javascript:history.back()" style="color:#0c5159;font-weight:600">Read original</a></div>`
    );
  }

  return html;
}

async function ghGet(path, auth) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`, {
    headers: { Authorization: auth, Accept: 'application/vnd.github+json' },
  });
  if (!r.ok) return null;
  return r.json();
}

async function ghPut(path, auth, content, message, sha) {
  const body = { message, content, branch: BRANCH };
  if (sha) body.sha = sha;
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}`, {
    method: 'PUT',
    headers: {
      Authorization: auth,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return { ok: r.ok, status: r.status, data: await r.json() };
}

export default async function handler(req) {
  if (req.method !== 'POST') return jsonResp(405, { error: 'POST only' }, { Allow: 'POST' });

  const resolved = await resolveAuth(req);
  if (!resolved) {
    return jsonResp(401, { error: 'Login required (POST /api/admin/login or Authorization header)' });
  }
  const auth = resolved.auth;
  // Defensive — should never trip post-resolveAuth, but keeps the original
  // shape guard so a malformed legacy header bounces here too and the
  // CI security audit (_check_api_security.py) still sees the call.
  if (!PAT_AUTH_RE.test(auth)) {
    return jsonResp(401, { error: 'Malformed Authorization (need "token ghp_…")' });
  }

  let body;
  try { body = await req.json(); }
  catch { return jsonResp(400, { error: 'Body must be JSON' }); }

  let { slug, isRoot } = body || {};
  if (!slug) return jsonResp(400, { error: 'Missing slug' });
  // Sanitize: only allow safe slug chars
  if (!/^[a-z0-9-]+$/.test(slug)) return jsonResp(400, { error: 'Invalid slug (use a-z 0-9 -)' });

  const sourcePath = isRoot ? `${slug}.html` : `blog/${slug}.html`;
  const targetPath = isRoot ? `en/${slug}.html` : `en/blog/${slug}.html`;

  // 1. Fetch source HTML
  const src = await ghGet(sourcePath, auth);
  if (!src) return jsonResp(404, { error: `Source not found: ${sourcePath}` });
  // GitHub Contents API omits `content` for files >1 MB (and returns an array
  // for directories), so src.content can be undefined → atob(undefined) throws
  // an opaque 500. Articles with large inline SVGs can exceed 1 MB. Guard it.
  if (typeof src.content !== 'string') {
    return jsonResp(422, { error: 'Source too large (>1 MB) or not a single file' });
  }
  const decoded = atob(src.content.replace(/\n/g, ''));
  const utf8 = new TextDecoder().decode(Uint8Array.from(decoded, c => c.charCodeAt(0)));

  // 2. Transform to EN
  const enHtml = zhToEn(utf8);

  // 3. Encode back to base64
  const enBytes = new TextEncoder().encode(enHtml);
  let bin = '';
  for (let i = 0; i < enBytes.length; i++) bin += String.fromCharCode(enBytes[i]);
  const enBase64 = btoa(bin);

  // 4. Check if target exists for sha
  const existing = await ghGet(targetPath, auth);

  const result = await ghPut(
    targetPath,
    auth,
    enBase64,
    `admin: regen /en/ for ${slug}`,
    existing && existing.sha
  );

  if (!result.ok) return jsonResp(result.status, { error: 'GitHub PUT failed' });

  return jsonResp(200, {
    path: targetPath,
    url: `/${targetPath}`,
    commit: result.data.commit && result.data.commit.html_url,
  });
}
