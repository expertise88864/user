// Native disclosures/anchors and the actual runtime; no collectors or credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

async function activateFragmentLink(page, link, expected) {
  // Observe the native navigation event; click completion alone need not mean
  // the browser has committed a same-document fragment navigation.
  await Promise.all([
    page.waitForURL(url => decodeURIComponent(url.hash.slice(1)) === expected, {waitUntil:'commit'}),
    link.click(),
  ]);
  assert.equal(decodeURIComponent(new URL(page.url()).hash.slice(1)),expected);
}

module.exports = async function checkReadingNavigation(browser, {readingSource, generated = true} = {}) {
  const source = readingSource || fs.readFileSync('blog/blog-article-reading.min.js', 'utf8');
  const headings = '<h2 id="first">First</h2><p>Authored paragraph.</p><h2 id="second">Second</h2><h2 id="third">Third</h2>';
  const fixtures = [
    {name:'root', body:'<article class="prose"><h1>Guide</h1>' + headings + '</article>', ids:['first','second','third']},
    {name:'collisions', body:'<aside id="overview"></aside><article class="prose"><h2>Overview</h2><h2>Overview</h2><h2 id="overview-2">Author</h2></article>', ids:['overview-3','overview-4','overview-2']},
    {name:'english', body:'<article><div id="proseZh"><h2 id="zh-one">原文一</h2><h2 id="zh-two">原文二</h2><h2 id="zh-three">原文三</h2></div><div id="proseEn">' + headings + '</div></article>', ids:['first','second','third']},
    {name:'empty-english', body:'<article><div id="proseEn"><!-- empty --></div><div id="proseZh">' + headings + '</div></article>', ids:['first','second','third']},
    {name:'nested', body:'<article><section class="prose">' + headings + '</section></article>', ids:['first','second','third']},
    {name:'root-with-inner-prose', body:'<article class="prose"><h2 id="first">First</h2><section class="prose"><p>Inner example</p></section><h2 id="second">Second</h2><h2 id="third">Third</h2></article>', ids:['first','second','third']},
    {name:'static', body:'<article class="prose"><h1>Guide</h1><details id="dn-inline-toc"><summary>In this article</summary><ol><li><a href="#first" data-toc-inline="first">First</a></li><li><a href="#second" data-toc-inline="second">Second</a></li><li><a href="#third" data-toc-inline="third">Third</a></li></ol></details>' + headings + '</article>', ids:['first','second','third']},
    {name:'inert', body:'<article class="prose"><h2 id="first">First</h2><h2 id="second">Second</h2><template><h2>Not rendered</h2></template><!-- <h2>Example</h2> --></article>', ids:[]},
  ];
  const results = [];
  for (const width of [390,800,1440]) {
    const context = await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    try {
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://reading-navigation.test' || route.request().method() !== 'GET') return route.abort();
        if (url.pathname === '/runtime.js') return route.fulfill({contentType:'text/javascript',body:source});
        const fixture = fixtures.find(row => url.pathname === '/' + row.name);
        if (!fixture) return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:'text/html; charset=utf-8',body:'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Isolated outline</title><style>article{max-width:768px;margin:auto}h2{margin-top:400px}</style></head><body>' + fixture.body + '<footer>End</footer><script src="/runtime.js"></script></body></html>'});
      });
      for (const fixture of fixtures) {
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('https://reading-navigation.test/' + fixture.name);
        await page.evaluate(() => {
          window.TOC_EVENTS = [];
          window.gtag = (...args) => TOC_EVENTS.push(args);
          for (let i=0;i<3;i++) { DN.addInlineTOC(); DN.addFloatingTOC(); }
        });
        const links = page.locator('#dn-inline-toc a[data-toc-inline]');
        assert.deepEqual(await links.evaluateAll(nodes => nodes.map(node => node.dataset.tocInline)),fixture.ids,fixture.name + ' must target the selected body');
        assert.equal(await page.locator('#dn-inline-toc').count(),fixture.ids.length ? 1 : 0);
        assert.equal(await page.locator('#dn-toc-float').count(),width === 1440 && fixture.ids.length ? 1 : 0);
        if (fixture.ids.length) {
          const ids = await page.locator('[id]').evaluateAll(nodes => nodes.map(node => node.id));
          assert.equal(new Set(ids).size,ids.length,'New fragments must not collide with authored IDs');
          const details = page.locator('#dn-inline-toc');
          if (!await details.evaluate(node => node.open)) {
            await details.locator('summary').focus();
            await details.locator('summary').press('Enter');
          }
          assert.ok(await details.evaluate(node => node.open),'Keyboard must open the native disclosure');
          assert.doesNotMatch(await details.locator('summary').textContent(),/[一-鿿]/,'English outline controls must be English before other bundles initialize');
          await activateFragmentLink(page,links.last(),fixture.ids.at(-1));
          assert.equal(await page.evaluate(() => TOC_EVENTS.filter(row => row[1] === 'toc_click').length),1,'Repeated initialization must not duplicate click telemetry');
          // A blocked collector must not break the native reader action.
          await page.evaluate(() => { window.gtag = () => { throw Error('blocked collector'); }; });
          await activateFragmentLink(page,links.first(),fixture.ids[0]);
        }
        assert.deepEqual(errors,[],fixture.name + ' reading controls must not throw');
        results.push({width,fixture:fixture.name,runtime:true});
        await page.close();
      }
    } finally { await context.close(); }
    if (!generated) continue;
    const staticContext = await browser.newContext({viewport:{width,height:900},javaScriptEnabled:false,serviceWorkers:'block'});
    try {
      await staticContext.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://reading-navigation.test' || route.request().method() !== 'GET') return route.abort();
        const root = process.cwd();
        let file = path.resolve(root, '.' + url.pathname);
        if (!path.extname(file) && !fs.existsSync(file)) file += '.html';
        if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream',body:fs.readFileSync(file)});
      });
      for (const route of ['/en/blog/psoriasis-overview','/en/blog/atopic-dermatitis-overview','/en/blog/photodynamic-therapy-overview','/blog/dupilumab-long-term-maintenance']) {
        const page = await staticContext.newPage();
        await page.goto('https://reading-navigation.test' + route);
        const toc = page.locator('#dn-inline-toc');
        assert.equal(await toc.count(),1,route + ' must contain a generated outline without JavaScript');
        assert.equal(await toc.evaluate(node => node.open),false,'Static outline must start collapsed');
        const links = toc.locator('a[data-toc-inline]');
        assert.ok(await links.count() >= 3);
        assert.ok(await links.evaluateAll(nodes => nodes.every(node => document.getElementById(node.dataset.tocInline)?.tagName === 'H2')));
        await toc.locator('summary').focus(); await toc.locator('summary').press('Enter');
        assert.ok(await toc.evaluate(node => node.open),'Keyboard must open the real native disclosure');
        const expected = await links.last().getAttribute('data-toc-inline');
        await activateFragmentLink(page,links.last(),expected);
        if (route.includes('psoriasis-overview')) assert.deepEqual(await links.evaluateAll(nodes => nodes.map(node => node.dataset.tocInline)),['what-is-psoriasis','six-clinical-subtypes','severity-assessment','triggers','diagnosis','bottom-line']);
        if (route.includes('photodynamic-therapy-overview')) {
          const fragments = await links.evaluateAll(nodes => nodes.map(node => node.dataset.tocInline));
          assert.equal(fragments[0],'why-does-dermatology-use-light-a-brief-1','The reproduced PDT page must retain its previous English fragment');
          const sourceMap = JSON.parse(await page.locator('[data-dn-zh-fragments]').getAttribute('data-dn-zh-fragments'));
          const origins = await links.evaluateAll(nodes => Object.fromEntries(nodes.map(node => [node.dataset.tocInline, document.getElementById(node.dataset.tocInline).dataset.dnHeadingId])));
          assert.deepEqual(sourceMap,origins,'Every generated English PDT fragment must return to its exact Chinese source');
        }
        results.push({width,route,javaScript:false});
        await page.close();
      }
    } finally { await staticContext.close(); }
  }
  return {cases:results.length,results};
};
