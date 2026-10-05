#!/usr/bin/env node
import { createServer } from 'node:http';
import { createServer as createSecureServer } from 'node:https';
import { createReadStream, readFileSync } from 'node:fs';
import { realpath, stat } from 'node:fs/promises';
import { createGzip } from 'node:zlib';
import { pipeline } from 'node:stream/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const args = new Map();
for (let i = 2; i < process.argv.length; i += 1) {
  if (process.argv[i].startsWith('--')) {
    args.set(process.argv[i].slice(2), process.argv[i + 1] || '');
    i += 1;
  }
}

const port = Number(args.get('port') || process.env.PORT || 8080);
const host = args.get('host') || process.env.HOST || '127.0.0.1';
const certPath = args.get('tls-cert');
const keyPath = args.get('tls-key');
if (Boolean(certPath) !== Boolean(keyPath)) {
  throw new Error('Provide both --tls-cert and --tls-key');
}
const makeServer = certPath
  ? handler => createSecureServer({cert: readFileSync(certPath), key: readFileSync(keyPath)}, handler)
  : createServer;

const TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.js', 'application/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml; charset=utf-8'],
  ['.txt', 'text/plain; charset=utf-8'],
  ['.webp', 'image/webp'],
  ['.xml', 'application/xml; charset=utf-8'],
  ['.jpg', 'image/jpeg'],
  ['.jpeg', 'image/jpeg'],
]);

const COMPRESSIBLE = new Set(['.css', '.html', '.js', '.json', '.svg', '.txt', '.xml']);
const PUBLIC_DIRECTORIES = new Set(['admin', 'ai', 'assets', 'blog', 'en', 'pagefind', '.well-known']);
const PUBLIC_ROOT_FILES = new Set([
  '404.html', 'about.html', 'admin.html', 'dashboard.html', 'glossary.html', 'index.html',
  'notes.html', 'offline.html', 'privacy.html', 'reset-sw.html', 'support.html', 'tools.html',
  'ads.txt', 'humans.txt', 'llms.txt', 'llms-full.txt', 'robots.txt', 'sitemap.xml',
  'manifest.json', 'opensearch.xml', 'sw.js', 'favicon.ico', 'apple-touch-icon.png', 'icon.svg',
  'icon-16.png', 'icon-32.png', 'icon-48.png', 'icon-64.png', 'icon-96.png', 'icon-128.png',
  'icon-180.png', 'icon-192.png', 'icon-256.png', 'icon-512.png', 'logo-512.png',
]);
const PUBLIC_ROOT_ROUTES = new Set([...PUBLIC_ROOT_FILES].filter(name => name.endsWith('.html')).map(name => name.slice(0, -5)));
const VERIFICATION_FILE = /^[A-Za-z0-9-]{8,128}\.txt$/;

function encodingQuality(header) {
  const weights = new Map();
  for (const entry of String(header || '').split(',')) {
    const [coding, ...parameters] = entry.trim().toLowerCase().split(';');
    const name = coding.trim();
    if (!name) continue;
    let quality = 1;
    for (const parameter of parameters) {
      if (!parameter.trim().startsWith('q')) continue;
      const match = parameter.match(/^\s*q\s*=\s*(0(?:\.\d{0,3})?|1(?:\.0{0,3})?)\s*$/);
      quality = match ? Number(match[1]) : 0;
    }
    weights.set(name, Math.min(weights.get(name) ?? 1, quality));
  }
  return {
    gzip: weights.get('gzip') ?? weights.get('*') ?? 0,
    identity: weights.get('identity') ?? (weights.get('*') === 0 ? 0 : 1),
  };
}

function send(res, status, body, type = 'text/plain; charset=utf-8') {
  res.writeHead(status, {
    'content-type': type,
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(body);
}

function safePath(urlPath) {
  let decoded;
  try { decoded = decodeURIComponent(urlPath.split('?')[0]); }
  catch { return null; }
  const normalized = path.normalize(decoded).replace(/^(\.\.[/\\])+/, '');
  const relative = normalized.replace(/^[/\\]+/, '');
  const absolute = path.resolve(ROOT, relative);
  return publicFilePath(absolute) ? absolute : null;
}

function publicFilePath(absolute, isFile = false) {
  const fromRoot = path.relative(ROOT, absolute);
  if (fromRoot === '..' || fromRoot.startsWith('..' + path.sep) || path.isAbsolute(fromRoot)) return false;
  const parts = fromRoot.split(/[/\\]+/).filter(Boolean);
  // Only known site roots are public. The popular-picks fixture is handled
  // before resolution; API source, project docs/config and tooling stay private.
  if (parts.some(part => /\.(?:pem|key|pyc)$/i.test(part) ||
    /(?:service-account|credentials|firebase-adminsdk|gcloud-key|positive-guild-).*\.json$/i.test(part))) return false;
  if (parts.some((part, index) => part.startsWith('_') ||
    (part.startsWith('.') && !(index === 0 && part.toLowerCase() === '.well-known')))) return false;
  const first = parts[0]?.toLowerCase();
  if (parts.length > 1) return PUBLIC_DIRECTORIES.has(first);
  return PUBLIC_ROOT_FILES.has(first) || VERIFICATION_FILE.test(parts[0] || '') ||
    (!isFile && (PUBLIC_DIRECTORIES.has(first) || PUBLIC_ROOT_ROUTES.has(first)));
}

async function resolveFile(urlPath) {
  const direct = safePath(urlPath === '/' ? '/index.html' : urlPath);
  if (!direct) return null;

  const candidates = [direct];
  if (!path.extname(direct)) {
    candidates.push(`${direct}.html`);
    candidates.push(path.join(direct, 'index.html'));
  }

  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) {
        const resolved = await realpath(candidate);
        if (!publicFilePath(resolved, true)) continue;
        const relative = path.relative(ROOT, resolved);
        if (!relative.includes(path.sep) && !PUBLIC_ROOT_FILES.has(relative.toLowerCase())) {
          // IndexNow root verification files contain only their public key.
          // A plausible filename alone must not expose arbitrary text files.
          if (info.size > 130 || readFileSync(resolved, 'utf8').trim() !== relative.slice(0, -4)) continue;
        }
        return resolved;
      }
    } catch {
      // try next candidate
    }
  }
  return null;
}

const server = makeServer(async (req, res) => {
  try {
    const url = new URL(req.url || '/', `http://${req.headers.host || `${host}:${port}`}`);
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      send(res, 405, 'Method Not Allowed');
      return;
    }

    if (url.pathname === '/api/admin/popular-picks') {
      send(res, 200, JSON.stringify({ picks: [] }), 'application/json; charset=utf-8');
      return;
    }

    const file = await resolveFile(url.pathname);
    if (!file) {
      send(res, 404, 'File not found');
      return;
    }

    const ext = path.extname(file).toLowerCase();
    const quality = encodingQuality(req.headers['accept-encoding']);
    const compressible = COMPRESSIBLE.has(ext);
    const size = (await stat(file)).size;
    const gzip = compressible && quality.gzip > 0 && quality.gzip >= quality.identity &&
      (size >= 1024 || quality.identity === 0);
    if (compressible) res.setHeader('vary', 'Accept-Encoding');
    if (!gzip && quality.identity === 0) {
      send(res, 406, 'No acceptable content encoding');
      return;
    }
    res.writeHead(200, {
      'content-type': TYPES.get(ext) || 'application/octet-stream',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
      ...(gzip ? {'content-encoding': 'gzip'} : {}),
    });
    if (req.method === 'HEAD') {
      res.end();
      return;
    }
    // Match production compression without changing the decoded source bytes.
    // Await the stream so disconnect/read/compression failures are handled too.
    if (gzip) await pipeline(createReadStream(file), createGzip(), res);
    else await pipeline(createReadStream(file), res);
  } catch (error) {
    if (res.headersSent) res.destroy();
    else send(res, 500, String(error && error.stack ? error.stack : error));
  }
});

server.listen(port, host, () => {
  console.log(`DermNotes dev server: ${certPath ? 'https' : 'http'}://${host}:${server.address().port}/`);
});
