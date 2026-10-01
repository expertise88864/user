#!/usr/bin/env node
import { createServer } from 'node:http';
import { createServer as createSecureServer } from 'node:https';
import { createReadStream, readFileSync } from 'node:fs';
import { stat } from 'node:fs/promises';
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
  const fromRoot = path.relative(ROOT, absolute);
  return fromRoot === '..' || fromRoot.startsWith('..' + path.sep) || path.isAbsolute(fromRoot)
    ? null : absolute;
}

async function resolveFile(urlPath) {
  if (urlPath === '/') return path.join(ROOT, 'index.html');
  const direct = safePath(urlPath);
  if (!direct) return null;

  const candidates = [direct];
  if (!path.extname(direct)) {
    candidates.push(`${direct}.html`);
    candidates.push(path.join(direct, 'index.html'));
  }

  for (const candidate of candidates) {
    try {
      const info = await stat(candidate);
      if (info.isFile()) return candidate;
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
