/* Read-only preview acceptance; never submits forms or changes visual baselines. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
// Never attach the preview credential to analytics, images, or redirect hosts.
function previewHeaders(url, origin, secret) {
  return secret && new URL(url).origin === origin
    ? { 'x-vercel-protection-bypass': secret } : {};
}
async function checkHubStatus(page) {
  const status = page.locator('#dn-search-status');
  await status.waitFor();
  await page.waitForFunction(() => document.getElementById('dn-search-status')?.getAttribute('data-en'));
  const english = await page.locator('html').getAttribute('lang').then(lang => lang.startsWith('en'));
  async function assertStatus(pattern) {
    const text = await status.textContent();
    assert.match(text, pattern);
    assert.equal(text, await status.getAttribute(english ? 'data-en' : 'data-zh'));
  }
  await assertStatus(english ? /^\d+ featured articles?$/ : /^\d+ 篇精選文章$/);
  const cards = page.locator('#dn-article-list > .article-list-item');
  const total = await page.evaluate(() => document.querySelectorAll('#dn-article-list > .article-list-item').length +
    (document.getElementById('dn-home-card-rest')?.content.querySelectorAll('.article-list-item').length || 0));
  const limit = Number(await page.locator('#dn-hub').getAttribute('data-show-count'));
  assert.equal(await cards.count(), Math.min(limit,total),
    'The initial homepage must keep remaining cards inert');
  assert.equal(await page.locator('#dn-article-list > .article-list-item:visible').count(), Math.min(limit, total),
    'Homepage must initially display only its configured latest articles');
  const initialOrder = await page.locator('#dn-article-list > .article-list-item:visible').evaluateAll(
    nodes => nodes.map(node => node.getAttribute('href')));
  const input = page.locator('#dn-search-input');
  // Search first: revealing the full catalog beforehand would mask lazy-load failures.
  await input.fill('杜避炎 打多久');
  await assertStatus(english ? /^\d+ results?$/ : /^找到 \d+ 篇文章$/);
  assert.ok(await page.locator('#dn-article-list > a[href$="/dupilumab-long-term-maintenance"]').isVisible());
  await input.fill('');
  await assertStatus(english ? /^\d+ featured articles?$/ : /^\d+ 篇精選文章$/);
  assert.deepEqual(await page.locator('#dn-article-list > .article-list-item:visible').evaluateAll(
    nodes => nodes.map(node => node.getAttribute('href'))), initialOrder,
    'Clearing the first search must restore the initial date order');
  await page.locator('.dn-tag-all').click();
  await assertStatus(english ? /^\d+ articles?$/ : /^\d+ 篇文章$/);
  assert.equal(await page.locator('#dn-article-list > .article-list-item:visible').count(), total,
    'All topics must reveal the complete catalog despite the initial CSS limit');
  const topics = page.locator('.dn-tag-chip:not(.dn-tag-all)');
  for (const topic of await topics.all()) {
    const label = await topic.getAttribute(english ? 'data-en' : 'data-zh');
    assert.ok(label, 'Every topic must have a localized label');
    if (english) assert.doesNotMatch(label, /[\u3400-\u9fff]/, 'English topic label must be translated');
    await topic.click();
    assert.equal(await status.textContent(), english ? 'Articles about ' + label : label + ' 相關文章');
  }
  await input.fill('杜避炎 打多久');
  await assertStatus(english ? /^\d+ results?$/ : /^找到 \d+ 篇文章$/);
  assert.ok(await page.locator('#dn-article-list > a[href$="/dupilumab-long-term-maintenance"]').isVisible(),
    'Search must reveal matching articles outside the initial latest-card limit');
  await input.fill('zzzznomatchingarticlezzzz');
  await assertStatus(english ? /^0 results$/ : /^找到 0 篇文章$/);
  await input.fill('');
  await assertStatus(english ? /^\d+ articles?$/ : /^\d+ 篇文章$/);
  assert.equal(await page.locator('#dn-article-list > .article-list-item:visible').count(), total);
}
async function checkStaticHome(browser, base, secret, width) {
  const context = await browser.newContext({viewport:{width,height:900},javaScriptEnabled:false});
  try {
    await authenticatePreview(context, base, secret);
    for (const route of ['/', '/en']) {
      const page = await context.newPage();
      await page.goto(new URL(route, base).href, {waitUntil:'load'});
      const cards = page.locator('#dn-article-list > .article-list-item');
      const total = await page.evaluate(() => document.querySelectorAll('#dn-article-list > .article-list-item').length +
        (document.getElementById('dn-home-card-rest')?.content.querySelectorAll('.article-list-item').length || 0));
      const limit = Number(await page.locator('#dn-hub').getAttribute('data-show-count'));
      assert.ok(total > limit, 'Static home must retain the complete catalog');
      assert.equal(await cards.count(), limit, 'Only initial cards may be live DOM nodes');
      assert.equal(await page.locator('#dn-article-list > .article-list-item:visible').count(), limit,
        'The initial card limit must apply even when JavaScript is unavailable');
      const target = route === '/en' ? '/en/blog' : '/blog';
      const link = page.locator('#articles a[href="' + target + '"]').first();
      await Promise.all([page.waitForURL(base.origin + target),link.click()]);
      // The pinned board-exam card (zh only) sits outside the article list.
      assert.equal(await page.locator('.article-list-item:not([data-dn-pinned]):visible').count(), total,
        'Native All articles navigation must expose every article without JavaScript');
      assert.equal(await page.locator('a[data-dn-pinned][href="/exam"]:visible').count(), route === '/en' ? 0 : 1,
        'The board-exam card is pinned on the Chinese article index only');
      await page.close();
    }
  } finally { await context.close(); }
}
async function authenticatePreview(context, base, secret) {
  if (!secret) return;
  // Bootstrap a host-only Vercel session without forwarding the secret on redirects.
  // Native browser requests then retain normal service-worker/cache behavior.
  let response;
  try {
    response = await context.request.get(base.origin + '/', {
      headers: { ...previewHeaders(base.href, base.origin, secret), 'x-vercel-set-bypass-cookie': 'true' },
      maxRedirects: 0,
    });
  } catch (_) {
    // Playwright request errors can contain request headers: keep credentials out of logs.
    throw new Error('Preview authentication request failed');
  }
  assert.ok([200, 301, 302, 303, 307, 308].includes(response.status()), 'Preview authentication failed');
  const redirect = response.headers().location;
  if (response.status() !== 200) {
    let redirectOrigin;
    try { redirectOrigin = redirect && new URL(redirect, base).origin; } catch (_) {}
    assert.ok(redirectOrigin === base.origin,
      'Preview authentication redirect must stay on the verified origin');
  }
  const cookies = await context.cookies();
  assert.ok(cookies.length > 0 && cookies.every(cookie =>
    cookie.domain === base.hostname && cookie.secure && cookie.httpOnly),
    'Preview authentication requires secure, HttpOnly, exact-host cookies');
}
async function checkHomeNavigation(page, base, route) {
  await page.evaluate(() => navigator.serviceWorker.ready.then(() => true));
  await page.reload({waitUntil: 'load'});
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  const target = route === '/en' ? '/en/blog' : '/blog';
  const link = page.locator('a.dn-show-more');
  assert.equal(await link.getAttribute('href'), target);
  await Promise.all([
    page.waitForURL(base.origin + target),
    link.click(),
  ]);
  await page.locator('.article-list-item').first().waitFor();
  // Exercise the old bookmarked route too, with the service worker active.
  const response = await page.goto(base.origin + target + '/', {waitUntil: 'load'});
  assert.equal(response.status(), 200);
  assert.equal(new URL(page.url()).pathname, target);
  await page.locator('.article-list-item').first().waitFor();
}
// The deployment serves the staged public site (dist/), never the repository.
// The authoritative file census comes from the Vercel API: the exact-SHA
// deployment's own output tree must equal the public selection (every public
// file present, no internal file, nothing else but the generated search bundle).
// The CDN then only answers a small sample, so the check costs a few dozen
// requests instead of one HEAD per checkout file.
const ADMIN_SHELL = /^admin(?:\.html$|\/)/;  // middleware.js matcher: /admin.html, /admin/*
const VERCEL_API = 'https://api.vercel.com';
const VERCEL_PROJECT = 'chendermatologist';
const VERCEL_TEAM_SLUG = 'expertise88864s-projects';
const GENERATED = /^pagefind\//;  // built by `npm run build`, absent from the checkout manifest
const MAX_TREE_ENTRIES = 50000;

// The token is only ever placed in the Authorization header. Errors carry fixed
// labels and the HTTP status, never the request, the response body or the token.
async function vercelApi(path, label, token, request = fetch) {
  if (typeof token !== 'string' || !/^[\x21-\x7e]{8,512}$/.test(token)) {
    throw new Error('VERCEL_FILES_TOKEN is missing or malformed: the deployed file set cannot be verified');
  }
  let response;
  try {
    response = await request(VERCEL_API + path, {
      headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' },
      redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(30000),
    });
  } catch (_) {
    throw new Error('Vercel API ' + label + ' request failed (network)');
  }
  if (!response || !response.ok) {
    throw new Error('Vercel API ' + label + ' request failed: HTTP ' + (response ? response.status : 'none'));
  }
  let text;
  try { text = await response.text(); } catch (_) { throw new Error('Vercel API ' + label + ' response unreadable'); }
  if (text.length > 64 * 1024 * 1024) throw new Error('Vercel API ' + label + ' response is too large');
  try { return JSON.parse(text); } catch (_) { throw new Error('Vercel API ' + label + ' response is not JSON'); }
}

// Same binding as `_delivery.py preview`: the preview URL comes from the GitHub
// deployment Vercel created for this exact SHA; the API must confirm that very
// deployment (same URL, project and commit, ready, not production).
async function vercelDeployment(base, sha, token, request = fetch) {
  assert.match(sha || '', /^[0-9a-f]{40}$/, 'A full commit SHA is required to verify deployed files');
  const host = base.hostname;
  assert.match(host, /^[a-z0-9-]+\.vercel\.app$/, 'Preview host must be a vercel.app deployment');
  const data = await vercelApi('/v13/deployments/' + encodeURIComponent(host) + '?slug=' + VERCEL_TEAM_SLUG,
    'deployment', token, request);
  assert.ok(data && typeof data === 'object' && !Array.isArray(data), 'Vercel API deployment response is malformed');
  assert.equal(data.url, host, 'Vercel API returned a different deployment');
  assert.ok(typeof data.id === 'string' && /^dpl_[A-Za-z0-9]+$/.test(data.id), 'Vercel deployment id is malformed');
  assert.equal(data.name, VERCEL_PROJECT, 'Vercel deployment belongs to another project');
  assert.equal(data.readyState, 'READY', 'Vercel deployment is not ready');
  assert.ok(data.target !== 'production', 'A production deployment is never Preview evidence');
  assert.equal(data.meta && data.meta.githubCommitSha, sha, 'Vercel deployment is not bound to this exact commit');
  return data.id;
}

function flattenTree(nodes, prefix, out, depth) {
  assert.ok(Array.isArray(nodes) && depth < 40, 'Vercel file tree is malformed');
  for (const node of nodes) {
    const name = node && node.name;
    assert.ok(typeof name === 'string' && name && name !== '.' && name !== '..' && !/[/\\\0]/.test(name),
      'Vercel file tree has an invalid entry name');
    const full = prefix + name;
    if (node.type === 'directory') {
      assert.ok(Array.isArray(node.children), 'Vercel file tree omitted a directory listing: ' + full);
      flattenTree(node.children, full + '/', out, depth + 1);
    } else if (node.type === 'file') {
      out.files.push(full);
    } else if (node.type === 'lambda' || node.type === 'middleware') {
      out.functions.push(full);
    } else {
      throw new Error('Unexpected Vercel file tree entry (' + String(node.type).slice(0, 20) + '): ' + full);
    }
    assert.ok(out.files.length + out.functions.length <= MAX_TREE_ENTRIES, 'Vercel file tree exceeds its bound');
  }
  return out;
}

// Build output: Git deployments list it under `out/`; a tree without one is
// taken as the output itself (a source tree then fails the comparison).
function outputEntries(tree) {
  assert.ok(Array.isArray(tree) && tree.length > 0, 'Vercel file tree is empty or malformed');
  const out = tree.filter(node => node && node.type === 'directory' && node.name === 'out');
  assert.ok(out.length <= 1, 'Vercel file tree has several output roots');
  assert.ok(!out.length || Array.isArray(out[0].children), 'Vercel file tree omitted a directory listing: out');
  return flattenTree(out.length ? out[0].children : tree, '', { files: [], functions: [] }, 0);
}

function shape(tree) {
  // Structure only (types and names of the top level) for diagnosing API changes.
  return (Array.isArray(tree) ? tree : []).slice(0, 12)
    .map(node => String(node && node.type) + ':' + String(node && node.name)).join(', ');
}

function compareDeployedFiles(manifest, entries) {
  // api/ is deployed as functions from the project root, never as static source files.
  const internal = manifest.private.filter(name => !name.startsWith('api/'));
  assert.ok(manifest.published.includes('index.html') && internal.includes('_delivery.py'), 'Incomplete file manifest');
  const deployed = new Set(entries.files);
  assert.equal(deployed.size, entries.files.length, 'Vercel file tree lists a file twice');
  const published = new Set(manifest.published), hidden = new Set(internal);
  const failures = [];
  for (const name of [...manifest.published, 'pagefind/pagefind.js']) {
    if (!deployed.has(name)) failures.push(name + ': public file missing from the deployment');
  }
  for (const name of entries.files) {
    if (hidden.has(name)) failures.push(name + ': internal file deployed');
    else if (!published.has(name) && !GENERATED.test(name)) failures.push(name + ': unexpected file deployed');
  }
  assert.deepEqual(failures.sort().slice(0, 40), [], 'Deployed file set differs from the public site selection');
  return { published: manifest.published.length, generated: entries.files.filter(name => GENERATED.test(name)).length,
    private: internal.length, functions: entries.functions.length };
}

// A few files of every type (first and last by name), the generated search bundle
// and representative internal paths: proves the CDN really answers as the census says.
function cdnSample(manifest) {
  const byType = new Map();
  for (const name of [...manifest.published].sort()) {
    const type = (name.match(/\.[A-Za-z0-9]+$/) || ['(none)'])[0].toLowerCase();
    if (!byType.has(type)) byType.set(type, []);
    byType.get(type).push(name);
  }
  const jobs = [];
  for (const names of byType.values()) {
    for (const name of new Set([names[0], names[names.length - 1]])) jobs.push([name, 200]);
  }
  jobs.push(['pagefind/pagefind.js', 200]);
  const internal = manifest.private.filter(name => !name.startsWith('api/'));
  const probes = new Set(['_delivery.py', internal.find(name => name.endsWith('.md')),
    internal.find(name => name.startsWith('.github/')), '__pycache__/_run_quality.cpython-312.pyc']);
  for (const name of probes) if (name) jobs.push([name, 404]);
  return jobs;
}

async function checkDeployedFiles(context, base, manifest, { sha, token, request = fetch } = {}) {
  const id = await vercelDeployment(base, sha, token, request);
  const tree = await vercelApi('/v6/deployments/' + encodeURIComponent(id) + '/files?slug=' + VERCEL_TEAM_SLUG,
    'deployment files', token, request);
  let counts;
  try { counts = compareDeployedFiles(manifest, outputEntries(tree)); }
  catch (error) { error.message += ' [Vercel tree top level: ' + shape(tree) + ']'; throw error; }
  const encode = name => '/' + name.split('/').map(encodeURIComponent).join('/');
  const jobs = cdnSample(manifest), failures = [];
  let next = 0, gated = 0;
  async function worker() {
    while (next < jobs.length) {
      const [name, expected] = jobs[next++];
      let response;
      try { response = await context.request.head(base.origin + encode(name), { maxRedirects: 5 }); } catch (_) {}
      const status = response ? response.status() : 'request failed';
      // middleware.js may put the admin shell behind Basic Auth (ADMIN_BASIC_USER/PASS).
      // Its challenge proves the gate, not the file, which the API census already proved.
      if (expected === 200 && status === 401 && ADMIN_SHELL.test(name) &&
          (response.headers()['www-authenticate'] || '').startsWith('Basic realm="ChenDermatologist Admin"')) {
        gated++;
        continue;
      }
      if (status !== expected) failures.push(name + ': HTTP ' + status + ', expected ' + expected);
    }
  }
  await Promise.all(Array.from({ length: 4 }, worker));
  // Functions still deploy from the project root, not from the static output.
  let og;
  try { og = await context.request.get(base.origin + '/api/og?title=DermNotes', { maxRedirects: 0 }); } catch (_) {}
  if (!og || og.status() !== 200 || !/^image\/svg\+xml/.test(og.headers()['content-type'] || '')) {
    failures.push('api/og: serverless function did not answer');
  }
  assert.deepEqual(failures.sort().slice(0, 40), [], 'Deployed file set differs from the public site selection');
  return { deployment: id, ...counts, adminBasicAuth: gated, cdnRequests: jobs.length + 1, apiRequests: 2 };
}

// Every request a browser context sends to the Preview origin over the network
// (service-worker cache hits excluded): the Vercel cost of these checks.
function countPreviewRequests(context, base, counter) {
  const own = request => { try { return new URL(request.url()).origin === base.origin; } catch (_) { return false; } };
  context.on('requestfinished', request => {
    if (!own(request)) return;
    request.response().then(response => { if (!response || !response.fromServiceWorker()) counter.browser++; },
      () => { counter.browser++; });
  });
  context.on('requestfailed', request => { if (own(request)) counter.browser++; });
}

module.exports = { previewHeaders, checkHubStatus, authenticatePreview, checkStaticHome, checkDeployedFiles,
  vercelDeployment, outputEntries, compareDeployedFiles, cdnSample };

if (require.main === module) (async () => {
  const { chromium } = require('playwright');
  const base = new URL(process.env.PW_BASE_URL);
  assert.equal(base.protocol, 'https:');
  assert.ok(base.hostname.endsWith('.vercel.app'));
  const policy = JSON.parse(fs.readFileSync('_delivery_policy.json', 'utf8'));
  fs.mkdirSync('delivery-preview', { recursive: true });
  const secret = process.env.VERCEL_AUTOMATION_BYPASS_SECRET;
  const counter = { browser: 0, authentication: 0 };
  const browser = await chromium.launch();
  // Same browser, every context counted; authenticatePreview sends one request per context.
  const contexts = {
    newContext: async options => {
      const context = await browser.newContext(options);
      countPreviewRequests(context, base, counter);
      if (secret) counter.authentication++;
      return context;
    },
  };
  let files;
  try {
    const manifest = JSON.parse(require('node:child_process').execFileSync('python', ['_site_publish.py', '--manifest'],
      { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }));
    const filesContext = await contexts.newContext();
    try {
      await authenticatePreview(filesContext, base, secret);
      files = await checkDeployedFiles(filesContext, base, manifest,
        { sha: process.env.GITHUB_SHA, token: process.env.VERCEL_FILES_TOKEN });
      fs.writeFileSync('delivery-preview/deployed-files.json', JSON.stringify(files) + '\n');
      console.log('Deployed files (Vercel API census of ' + files.deployment + '): ' + files.published + ' public + ' +
        files.generated + ' generated files present, ' + files.private + ' internal files absent, ' +
        files.functions + ' functions; CDN sample ' + files.cdnRequests + ' requests, ' +
        files.adminBasicAuth + ' admin files behind Basic Auth');
    } finally { await filesContext.close(); }
    for (const width of [390, 800, 1440]) {
      // Every width starts from fresh contexts: no cookies, caches or service worker carry over.
      await checkStaticHome(contexts, base, secret, width);
      const context = await contexts.newContext({ viewport: { width, height: 900 }, locale: 'zh-TW' });
      try {
        await authenticatePreview(context, base, secret);
        for (const [index, route] of policy.preview_paths.entries()) {
          const page = await context.newPage();
          const errors = [];
          page.on('pageerror', e => errors.push(e.message));
          try {
            const response = await page.goto(new URL(route, base).href, { waitUntil: 'load' });
            assert.ok(response && response.status() === 200, route + ' must return HTTP 200');
            assert.equal(new URL(page.url()).hostname, base.hostname, 'Preview must not redirect to production/login');
            assert.ok((await page.title()).trim().length > 0, 'Document title missing');
            assert.ok(await page.locator('main').count() > 0, 'Main content missing');
            const nav = page.locator('nav.dn-nav');
            if (await nav.count()) {
              // 2026-10-17: calculators, glossary and the support (coffee) icon
              // left the header; the pages themselves stay reachable elsewhere.
              assert.equal(await page.locator('#dn-nav-support, #dn-bmc-header').count(), 0,
                'Header must not carry a support icon');
              assert.equal(await nav.locator('a[href$="/tools"], a[href$="/glossary"]').count(), 0,
                'Header must not link calculators or glossary');
              const burger = page.locator('#dn-nav-burger');
              const search = page.locator('#dn-nav-search');
              if (width <= 899) {
                assert.ok(await burger.isVisible(), 'Mobile/tablet menu control missing');
                assert.equal(await nav.isVisible(), false, 'Mobile/tablet menu must start collapsed');
                await burger.click();
                assert.ok(await nav.isVisible(), 'Mobile/tablet menu did not open');
                assert.ok(await search.evaluate(el => el.getBoundingClientRect().width > 100
                  && getComputedStyle(el, '::after').display !== 'none'), 'Menu labels must have room');
                for (const id of ['dn-nav-search', 'dn-nav-theme']) {
                  assert.ok(await page.locator('#' + id).evaluate(el =>
                    getComputedStyle(el, '::after').content === JSON.stringify(el.getAttribute('aria-label'))),
                    'Visible menu label must match the current page language: ' + id);
                }
                await burger.click();
                assert.equal(await nav.isVisible(), false, 'Mobile/tablet menu did not close');
              } else {
                assert.ok(await nav.isVisible(), 'Desktop navigation missing');
                assert.equal(await burger.isVisible(), false, 'Desktop hamburger should be hidden');
                assert.equal(await search.evaluate(el => getComputedStyle(el, '::after').display),
                  'none', 'Desktop icon labels must not overflow compact buttons');
              }
            }
            await page.screenshot({ path: 'delivery-preview/' + width + '-' + index + '.png', fullPage: true });
            if (route === '/' || route === '/en') {
              await checkHubStatus(page);
              await checkHomeNavigation(page, base, route);
            }
            assert.deepEqual(errors, [], 'Page JavaScript errors');
          } catch (error) {
            // Diagnostics only (the failure still fails): where the page was when a check failed.
            let where = 'unknown';
            try { where = new URL(page.url()).pathname + ' "' + (await page.title()).slice(0, 80) + '"'; } catch (_) {}
            console.error('Failed at ' + width + 'px ' + route + '; page at ' + where);
            await page.screenshot({ path: 'delivery-preview/failure-' + width + '-' + index + '.png', fullPage: true })
              .catch(() => {});
            throw error;
          }
          await page.close();
        }
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
    const requests = { browser: counter.browser, authentication: counter.authentication,
      cdnSample: files ? files.cdnRequests : 0, vercelApi: files ? files.apiRequests : 0 };
    requests.previewTotal = requests.browser + requests.authentication + requests.cdnSample;
    fs.writeFileSync('delivery-preview/vercel-requests.json', JSON.stringify(requests) + '\n');
    console.log('Vercel requests this attempt: ' + requests.previewTotal + ' to the Preview deployment (browser ' +
      requests.browser + ', authentication ' + requests.authentication + ', CDN sample ' + requests.cdnSample +
      ') + ' + requests.vercelApi + ' Vercel API');
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
