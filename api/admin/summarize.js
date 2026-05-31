// /api/admin/summarize.js — F9 — generate bilingual TL;DR from article body.
//
// POST { slug } → returns { zh, en }
// The admin Save flow can then optionally inject the result into the
// `<div class="dn-tldr">` block of the article.
//
// Auth: PREFERRED is HttpOnly cookie session set by /api/admin/login;
// LEGACY accepts Authorization: token ghp_... header. ANTHROPIC_API_KEY
// env still required for the Claude call.

import { resolveAuth } from './_session.js';

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';
const MODEL = 'claude-3-5-haiku-20241022';
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

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

const SYSTEM_PROMPT = `You are a Taiwan dermatology resident writing TL;DR summaries for patient-facing articles. Return ONLY a valid JSON object with two keys "zh" and "en":

- zh: 1-2 Traditional-Chinese sentences (≤ 100 字), full-width punctuation, NO emoji, NO markdown
- en: 1-2 English sentences (≤ 200 chars), clinical tone, no markdown

Never wrap in code fences. Output only the JSON.`;

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
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return jsonResp(500, { error: 'ANTHROPIC_API_KEY not configured on server' });

  let body;
  try { body = await req.json(); } catch { return jsonResp(400, { error: 'Body must be JSON' }); }
  let { slug, isRoot } = body || {};
  if (!slug || !/^[a-z0-9-]+$/.test(slug)) return jsonResp(400, { error: 'Invalid slug' });

  const path = isRoot ? `${slug}.html` : `blog/${slug}.html`;
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`, {
    headers: { Authorization: auth, Accept: 'application/vnd.github+json' },
  });
  if (!r.ok) return jsonResp(404, { error: 'Article not found' });
  const j = await r.json();
  // GitHub omits `content` for files >1 MB / returns an array for dirs, so
  // j.content can be undefined → atob(undefined) throws an opaque 500. Guard.
  if (typeof j.content !== 'string') {
    return jsonResp(422, { error: 'Article too large (>1 MB) or not a single file' });
  }
  const html = new TextDecoder().decode(Uint8Array.from(atob(j.content.replace(/\n/g, '')), c => c.charCodeAt(0)));

  // Extract main article text (truncate to 4000 chars to keep token cost low)
  const articleMatch = html.match(/<article[\s\S]*?<\/article>/i);
  const text = stripHtml(articleMatch ? articleMatch[0] : html).slice(0, 4000);

  // CODE_REVIEW 2026-05-26 — bound the upstream Claude call with an
  // AbortController so a slow/hung Anthropic response can't hold the edge
  // invocation open until the platform duration limit (wasted compute + a
  // worse 504-style failure for the admin). 25s is comfortably above a
  // normal Haiku TL;DR latency while staying under typical edge limits.
  const aiController = new AbortController();
  const aiTimeout = setTimeout(() => aiController.abort(), 25000);
  let aiResp;
  try {
    aiResp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      signal: aiController.signal,
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 600,
        system: SYSTEM_PROMPT,
        messages: [{ role: 'user', content: 'Article body:\n\n' + text }],
      }),
    });
  } catch (_) {
    return jsonResp(504, { error: 'AI call timed out or failed' });
  } finally {
    clearTimeout(aiTimeout);
  }
  if (!aiResp.ok) {
    return jsonResp(aiResp.status, { error: 'AI call failed' });
  }
  const ai = await aiResp.json();
  let raw = (ai.content && ai.content[0] && ai.content[0].text) || '{}';
  raw = raw.trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '');
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch { return jsonResp(502, { error: 'AI returned non-JSON' }); }

  return jsonResp(200, parsed);
}
