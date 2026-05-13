#!/usr/bin/env node
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
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

function send(res, status, body, type = 'text/plain; charset=utf-8') {
  res.writeHead(status, {
    'content-type': type,
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(body);
}

function safePath(urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const normalized = path.normalize(decoded).replace(/^(\.\.[/\\])+/, '');
  const relative = normalized.replace(/^[/\\]+/, '');
  const absolute = path.resolve(ROOT, relative);
  return absolute.startsWith(ROOT) ? absolute : null;
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

const server = createServer(async (req, res) => {
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
    res.writeHead(200, {
      'content-type': TYPES.get(ext) || 'application/octet-stream',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    });
    if (req.method === 'HEAD') {
      res.end();
      return;
    }
    createReadStream(file).pipe(res);
  } catch (error) {
    send(res, 500, String(error && error.stack ? error.stack : error));
  }
});

server.listen(port, host, () => {
  console.log(`DermNotes dev server: http://${host}:${port}/`);
});
