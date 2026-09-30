// Isolated raster polyglot fixture. Uploaded bytes must stay image resources
// when embedded, opened as a document, or requested as a script.
const assert = require('node:assert/strict');
const fs = require('node:fs');
module.exports = async function checkDraftMedia(browser) {
  const config = JSON.parse(fs.readFileSync('vercel.json', 'utf8'));
  const global = config.headers.find(rule => rule.source === '/(.*)');
  const nosniff = global.headers.find(header => header.key.toLowerCase() === 'x-content-type-options');
  assert.equal(nosniff.value, 'nosniff');
  // A valid one-pixel GIF plus appended HTML retains a functioning image.
  const gif = Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64');
  const polyglot = Buffer.concat([gif, Buffer.from('<script>parent.__executed.push("unsafe")</script>')]);
  const context = await browser.newContext({ serviceWorkers: 'block' });
  try {
    const page = await context.newPage();
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== 'https://media.test' || request.method() !== 'GET') return route.abort();
      if (url.pathname === '/fixture') return route.fulfill({ status: 200, contentType: 'text/html', body:
        '<!doctype html><html><body><script>window.__executed=[]</script>' +
        '<img id="image" src="/blog/images/example/fixture.gif" alt="fixture">' +
        '<iframe id="document" src="/blog/images/example/fixture.gif"></iframe>' +
        '<script src="/blog/images/example/fixture.gif"></script></body></html>' });
      if (url.pathname === '/blog/images/example/fixture.gif') return route.fulfill({ status: 200,
        headers: { 'Content-Type': 'image/gif', 'X-Content-Type-Options': nosniff.value }, body: polyglot });
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('https://media.test/fixture', { waitUntil: 'load' });
    assert.equal(await page.locator('#image').evaluate(img => img.naturalWidth), 1, 'image content remains intact');
    assert.deepEqual(await page.evaluate(() => window.__executed), [], 'appended payload must never execute');
    assert.equal(await page.frameLocator('#document').locator('script').count(), 0, 'direct image navigation must not turn into an HTML document');
  } finally { await context.close(); }
};
