// G4 — Dynamic Open Graph image generator.
//
// Renders a 1200×630 social-share card on demand. Uses pure SVG → PNG path
// instead of @vercel/og (no React dependency, no extra package). The
// resulting card has the article title, kicker tag, gradient teal bg, and
// the ChenDermatologist logo.
//
// Usage in HTML:
//   <meta property="og:image" content="https://chendermatologist.com/api/og?title=異位性皮膚炎概論&tag=異膚&date=2026-05-14">
//
// Cached at the edge for 24 hours per unique query string. SVG is ~3 KB vs
// PNG ~30 KB, so we serve SVG (Twitter, Facebook, LINE all accept image/svg+xml
// in og:image). For maximum compatibility a `?png=1` query forces PNG fallback
// (NOT yet implemented — would require a rasterization step).
//
// Query params:
//   title  (required, ≤ 80 chars)
//   tag    (optional, kicker eyebrow)
//   date   (optional, ISO date)
//   subtitle (optional)

export const config = { runtime: 'edge' };

function sanitizeXmlText(value, maxChars) {
  const cleaned = String(value || '')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]/g, '');
  return Number.isInteger(maxChars)
    ? Array.from(cleaned).slice(0, maxChars).join('')
    : cleaned;
}

function escapeXml(s) {
  return sanitizeXmlText(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function wrapText(text, maxCharsPerLine, maxLines) {
  // Greedy CJK-aware word-wrap. CJK chars count as 2 width, ASCII as 1.
  const lines = [];
  let cur = '';
  let curWidth = 0;
  for (const ch of text) {
    const w = ch.charCodeAt(0) > 127 ? 2 : 1;
    if (curWidth + w > maxCharsPerLine) {
      lines.push(cur);
      cur = ch;
      curWidth = w;
      if (lines.length >= maxLines) break;
    } else {
      cur += ch;
      curWidth += w;
    }
  }
  if (cur && lines.length < maxLines) lines.push(cur);
  // If text was longer than fits, add ellipsis.
  // CODE_REVIEW — was `last.replace(/.{2}$/, '…')` which counts UTF-16
  // code units, not codepoints. A 4-byte emoji (surrogate pair) at
  // string end would get mangled (high surrogate dropped, leaving
  // an unpaired low surrogate). Iterate codepoints via Array.from.
  if (lines.length === maxLines && text.length > lines.join('').length) {
    const chars = Array.from(lines[lines.length - 1]);
    lines[lines.length - 1] = chars.slice(0, -2).join('') + '…';
  }
  return lines;
}

function buildSvg(title, tag, date, subtitle) {
  const W = 1200, H = 630;
  const titleLines = wrapText(title || 'ChenDermatologist', 38, 3);
  const titleY0 = H / 2 - (titleLines.length - 1) * 38 + 10;
  const subtitleSafe = subtitle ? escapeXml(subtitle) : '';
  // Uppercase the RAW eyebrow text, THEN escape — escaping first and
  // upper-casing after would mangle XML entities (e.g. `&amp;` → `&AMP;`,
  // which is not a valid entity). CJK has no case so this is a no-op there.
  const tagSafe = escapeXml((tag || '皮膚科衛教').toUpperCase());
  const dateSafe = date ? escapeXml(date) : '';

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
<defs>
<linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
  <stop offset="0%" stop-color="#0c5159"/>
  <stop offset="55%" stop-color="#4d6358"/>
  <stop offset="100%" stop-color="#7a9285"/>
</linearGradient>
<radialGradient id="glow" cx="80%" cy="20%" r="60%">
  <stop offset="0%" stop-color="#a4b5a8" stop-opacity="0.45"/>
  <stop offset="100%" stop-color="#a4b5a8" stop-opacity="0"/>
</radialGradient>
<linearGradient id="line" x1="0%" y1="0%" x2="100%" y2="0%">
  <stop offset="0%" stop-color="#fff" stop-opacity="0"/>
  <stop offset="50%" stop-color="#fff" stop-opacity="0.65"/>
  <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
</linearGradient>
</defs>
<rect width="${W}" height="${H}" fill="url(#bg)"/>
<rect width="${W}" height="${H}" fill="url(#glow)"/>
<g font-family="-apple-system, BlinkMacSystemFont, 'Noto Sans TC', sans-serif" fill="#fff">
  <!-- top eyebrow / tag -->
  <text x="80" y="120" font-size="22" font-weight="700" letter-spacing="0.2em" fill="#a4b5a8" text-transform="uppercase">${tagSafe}</text>
  <line x1="80" y1="146" x2="240" y2="146" stroke="url(#line)" stroke-width="2"/>

  <!-- title (up to 3 lines) -->
  ${titleLines.map((line, i) =>
    `<text x="80" y="${titleY0 + i * 76}" font-size="62" font-weight="700" font-family="'Noto Serif TC', Georgia, serif">${escapeXml(line)}</text>`
  ).join('')}

  ${subtitleSafe ? `<text x="80" y="${titleY0 + titleLines.length * 76 + 20}" font-size="26" fill="#dcd9d1" font-weight="500">${subtitleSafe}</text>` : ''}

  <!-- bottom row: brand + date -->
  <g transform="translate(80, 540)">
    <circle cx="22" cy="22" r="22" fill="#a4b5a8" opacity="0.95"/>
    <text x="20" y="29" font-size="22" font-weight="800" fill="#0c5159" text-anchor="middle">陳</text>
    <text x="62" y="22" font-size="22" font-weight="700" fill="#fff">陳翊嘉醫師 · ChenDermatologist</text>
    <text x="62" y="46" font-size="16" fill="#dcd9d1">chendermatologist.com</text>
  </g>
  ${dateSafe ? `<text x="${W - 80}" y="568" font-size="18" fill="#dcd9d1" text-anchor="end">${dateSafe}</text>` : ''}
</g>
</svg>`;
}

export default async function handler(req) {
  if (req.method !== 'GET') {
    return Response.json({ error: 'GET only' }, {
      status: 405,
      headers: {
        Allow: 'GET',
        'Cache-Control': 'no-store',
      },
    });
  }

  const url = new URL(req.url);
  const title = sanitizeXmlText(url.searchParams.get('title'), 120);
  const tag = sanitizeXmlText(url.searchParams.get('tag'), 30);
  const date = sanitizeXmlText(url.searchParams.get('date'), 30);
  const subtitle = sanitizeXmlText(url.searchParams.get('subtitle'), 80);

  const svg = buildSvg(title, tag, date, subtitle);

  return new Response(svg, {
    status: 200,
    headers: {
      'Content-Type': 'image/svg+xml; charset=utf-8',
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox",
      'Content-Disposition': 'inline',
      'X-Content-Type-Options': 'nosniff',
      // Aggressive edge cache: same query string returns same image
      'Cache-Control': 'public, max-age=86400, s-maxage=2592000, stale-while-revalidate=2592000, immutable',
      // CODE_REVIEW — was `Access-Control-Allow-Origin: *`. SVG can
      // carry script; if any cross-origin consumer ever drops the
      // response into `<object>` or fetch+innerHTML, wildcard CORS
      // would let them read it. OG image scrapers (Facebook, Twitter,
      // etc.) don't honor CORS anyway — they fetch server-to-server.
      // No legitimate browser-side consumer needs cross-origin SVG.
    },
  });
}
