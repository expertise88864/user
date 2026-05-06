// F5 — Edge SWR endpoint listing the N most recent articles from GitHub
// Contents API. Lets the homepage refresh "最近更新" without a redeploy.
//
// Caches at the edge for 60s, serves stale up to 5 min while revalidating.
// Public — no auth required (only reads public repo metadata).
//
// Frontend usage (DN.refreshRecentList):
//   fetch('/api/articles-recent?n=8')
//     .then(r => r.json())
//     .then(items => renderList(items));
//
// Returns: [{ slug, title, date, dir }]  — sorted newest first

export const config = { runtime: 'edge' };

const REPO = process.env.ADMIN_REPO || 'expertise88864/user';
const BRANCH = process.env.ADMIN_BRANCH || 'main';

async function ghContents(path) {
  const r = await fetch(
    `https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,
    { headers: { Accept: 'application/vnd.github+json' } }
  );
  if (!r.ok) return null;
  return r.json();
}

async function fetchHead(path) {
  // Fetch raw file from GitHub (faster than contents API for content body)
  const r = await fetch(
    `https://raw.githubusercontent.com/${REPO}/${BRANCH}/${path}`
  );
  if (!r.ok) return null;
  // Only need first 4 KB for title + meta extraction
  const reader = r.body.getReader();
  const chunks = [];
  let total = 0;
  while (total < 4096) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.length;
  }
  reader.cancel();
  const buf = new Uint8Array(total);
  let pos = 0;
  for (const c of chunks) { buf.set(c, pos); pos += c.length; }
  return new TextDecoder().decode(buf);
}

function extractTitle(head) {
  if (!head) return '';
  const m = head.match(/<title>([^<]+)<\/title>/i);
  if (!m) return '';
  // Strip "— ChenDermatologist" suffix if present
  return m[1].replace(/\s*[—|]\s*Chen\s*Dermatologist.*$/i, '').replace(/\s+衛教筆記\s*$/, '').trim();
}

function extractDate(head) {
  if (!head) return null;
  // Look for ISO datePublished in JSON-LD
  const m = head.match(/"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"/);
  if (m) return m[1];
  const m2 = head.match(/"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})"/);
  return m2 ? m2[1] : null;
}

export default async function handler(req) {
  const url = new URL(req.url);
  const n = Math.min(20, Math.max(1, parseInt(url.searchParams.get('n') || '8', 10)));

  const blog = await ghContents('blog');
  if (!blog) {
    return Response.json({ error: 'cannot read blog/' }, {
      status: 502,
      headers: { 'Cache-Control': 'public, max-age=10' },
    });
  }
  // Filter article HTMLs only
  const articles = blog.filter(f =>
    f.type === 'file' && /\.html$/.test(f.name) && !/^index\./.test(f.name)
  );

  // Pull head snippet of each article in parallel (limit concurrency to 8)
  const items = [];
  const limit = 8;
  for (let i = 0; i < articles.length; i += limit) {
    const batch = articles.slice(i, i + limit);
    const heads = await Promise.all(batch.map(a => fetchHead(a.path)));
    for (let j = 0; j < batch.length; j++) {
      const a = batch[j];
      const head = heads[j];
      const title = extractTitle(head);
      const date = extractDate(head);
      if (!title) continue;
      items.push({
        slug: a.name.replace(/\.html$/, ''),
        title,
        date: date || '1970-01-01',
        dir: 'blog/',
      });
    }
  }

  items.sort((a, b) => (b.date || '').localeCompare(a.date || ''));

  return Response.json(items.slice(0, n), {
    headers: {
      'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      'Content-Type': 'application/json; charset=utf-8',
    },
  });
}
