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
  for (const missingIO of [false,true]) for (const width of [390,800,1440]) {
    const context = await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});
    try {
      if (missingIO) await context.addInitScript(() => { delete window.IntersectionObserver; });
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://reading-navigation.test' || route.request().method() !== 'GET') return route.abort();
        if (url.pathname === '/runtime.js') return route.fulfill({contentType:'text/javascript',body:source});
        const fixture = fixtures.find(row => url.pathname === '/' + row.name);
        if (!fixture) return route.fulfill({status:404,body:''});
        return route.fulfill({contentType:'text/html; charset=utf-8',body:'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Isolated outline</title><style>article{max-width:768px;margin:auto}h2{margin-top:400px}</style></head><body>' + fixture.body + '<footer style="min-height:1100px">End</footer><script src="/runtime.js"></script></body></html>'});
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
        if (width === 1440 && fixture.name === 'root') {
          const outline = page.locator('#dn-toc-float');
          // Exercise actual scroll geometry, active-heading updates and footer
          // hide/restore through the native browser, including the no-IO path.
          await page.evaluate(() => {
            const heading = document.getElementById('second');
            window.scrollTo(0, heading.getBoundingClientRect().top + window.scrollY - innerHeight * 0.4);
          });
          if (missingIO) await page.waitForFunction(() => document.querySelector('#dn-toc-float a[data-toc="second"]').style.fontWeight === '700');
          await page.evaluate(() => window.scrollTo(0, document.querySelector('footer').offsetTop));
          await page.waitForFunction(() => getComputedStyle(document.getElementById('dn-toc-float')).visibility === 'hidden');
          assert.equal(await outline.evaluate(node => node.style.pointerEvents), 'none');
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.waitForFunction(() => getComputedStyle(document.getElementById('dn-toc-float')).visibility === 'visible');
          assert.notEqual(await outline.evaluate(node => node.style.pointerEvents), 'none');
        }
        assert.deepEqual(errors,[],fixture.name + ' reading controls must not throw');
        results.push({width,fixture:fixture.name,missingIO,runtime:true});
        await page.close();
      }
    } finally { await context.close(); }
    if (!generated || missingIO) continue;
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
          const ports=page.locator('article .dn-table-scroll');
          assert.equal(await ports.count(),3,'PDT comparison tables need static scrollports without JavaScript');
          assert(await page.locator('html').evaluate(el=>el.scrollWidth<=innerWidth),'Tables must not widen the mobile document');
          assert.deepEqual(await ports.evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label'))),Array(3).fill('Comparison table; scroll horizontally'));
          if(width===390){
            const wide=ports.filter({has:page.locator('table')}).first();
            await wide.focus();
            assert(await wide.evaluate(el=>el.scrollWidth>el.clientWidth),'The full comparison remains available inside its scrollport');
            await wide.press('ArrowRight');
            // In a no-JS page, an animation-frame poll can stall after native
            // scrolling. Observe from the test process while preserving the
            // actual keyboard event and focused scrollport requirement.
            const deadline=Date.now()+5000;
            while(!await wide.evaluate(el=>el===document.activeElement&&el.scrollLeft>0)){
              assert(Date.now()<deadline,'ArrowRight must scroll the focused comparison table');
              await new Promise(resolve=>setTimeout(resolve,50));
            }
          }

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
  if (generated) results.push(...await checkLanguageFragments(browser));
  return {cases:results.length,results,topicEntries:generated ? await checkPublishedTopicEntry(browser) : {cases:0,results:[]}};
};

async function checkLanguageFragments(browser) {
  const journeys = [
    {slug:'skin-biopsy-excision',zh:'postop',en:'postop-en'},
    {slug:'perioral-dermatitis-guide',zh:'dx',en:'en-dx'},
    {slug:'photodynamic-therapy-overview',zh:'pdt-\u4e09\u8981\u7d20\u8207\u5206\u5b50\u5c64\u7d1a\u6a5f\u8f49',en:'the-three-pillars-of-pdt-and-molecular-m'},
  ];
  const origin = 'https://reading-locale.test', results = [];
  async function selectLanguage(page, lang, pathname) {
    const toggle = page.locator('#langToggle');
    if (!await toggle.isVisible()) {
      await page.locator('#dn-nav-burger').click();
      await toggle.waitFor({state:'visible'});
    }
    await Promise.all([
      page.waitForURL(url => url.pathname === pathname, {waitUntil:'load'}),
      toggle.selectOption(lang),
    ]);
  }
  async function atHeading(page, id) {
    await page.waitForFunction(id => {
      const target = document.getElementById(id);
      if (!target || !target.getClientRects().length) return false;
      const top = target.getBoundingClientRect().top;
      return window.scrollY > 100 && top >= -5 && top < 220;
    }, id, {timeout:5000});
  }
  for (const width of [390,800,1440]) {
    for (const javaScriptEnabled of [true,false]) {
      const context = await browser.newContext({viewport:{width,height:900},javaScriptEnabled,serviceWorkers:'block'});
      try {
        await context.route('**/*', route => {
          const url = new URL(route.request().url());
          if (url.origin !== origin || route.request().method() !== 'GET') return route.abort();
          const root = process.cwd();
          let file = path.resolve(root, '.' + url.pathname);
          if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file,'index.html');
          else if (!path.extname(file)) file += '.html';
          if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status:404,body:''});
          const extension = path.extname(file);
          const contentType = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.json':'application/json'}[extension] || 'application/octet-stream';
          return route.fulfill({contentType,body:fs.readFileSync(file)});
        });
        for (const journey of journeys) {
          const page = await context.newPage(), errors = [];
          page.on('pageerror', error => errors.push(error.message));
          const zhPath = '/blog/' + journey.slug, enPath = '/en' + zhPath;
          if (javaScriptEnabled) {
            await page.goto(origin + zhPath + '?source=journey#' + encodeURIComponent(journey.zh));
            await atHeading(page, journey.zh);
            await selectLanguage(page, 'en', enPath);
            assert.equal(new URL(page.url()).search,'?source=journey');
            assert.equal(decodeURIComponent(new URL(page.url()).hash.slice(1)),journey.zh);
            await atHeading(page,journey.en);
            // Exercise an authored English fragment, rather than returning
            // through the new Chinese alias and hiding the reverse defect.
            await page.goto(origin + enPath + '?source=journey#' + encodeURIComponent(journey.en));
            await atHeading(page,journey.en);
            await selectLanguage(page, 'zh', zhPath);
            assert.equal(new URL(page.url()).search,'?source=journey');
            assert.equal(decodeURIComponent(new URL(page.url()).hash.slice(1)),journey.zh);
            await atHeading(page,journey.zh);
          } else {
            await page.goto(origin + enPath + '#' + encodeURIComponent(journey.zh));
            await atHeading(page,journey.en);
            await atHeading(page,journey.zh);
          }
          assert.deepEqual(errors,[],journey.slug + ' locale navigation must not throw');
          results.push({width,journey:journey.slug,javaScriptEnabled,localeFragments:true});
          await page.close();
        }
      } finally { await context.close(); }
    }
  }
  return results;
}

module.exports.checkLanguageFragments = checkLanguageFragments;

async function checkPublishedTopicEntry(browser) {
  const origin = 'https://published-topic-entry.test', results = [];
  for (const width of [390,800,1440]) for (const javaScriptEnabled of [true,false]) {
    const context = await browser.newContext({viewport:{width,height:900},javaScriptEnabled,serviceWorkers:'block'});
    try {
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== origin || route.request().method() !== 'GET') return route.abort();
        if (url.pathname === '/api/admin/popular-picks') return route.fulfill({contentType:'application/json',body:JSON.stringify({picks:[],fallback:true})});
        const root = process.cwd();
        let file = path.resolve(root, '.' + url.pathname);
        if (fs.existsSync(file) && fs.statSync(file).isDirectory()) file = path.join(file,'index.html');
        else if (!path.extname(file)) file += '.html';
        if (!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.fulfill({status:404,body:''});
        const types = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.json':'application/json','.svg':'image/svg+xml','.webp':'image/webp','.png':'image/png','.woff2':'font/woff2'};
        return route.fulfill({contentType:types[path.extname(file)] || 'application/octet-stream',body:fs.readFileSync(file)});
      });
      for (const locale of ['zh','en']) {
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const prefix = locale === 'en' ? '/en' : '';
        await page.goto(origin + prefix + '/blog/topics');
        if (javaScriptEnabled) await page.waitForFunction(() => typeof window.DN === 'object');
        const pathname = prefix + '/blog/topical-steroids-guide';
        const link = page.locator('main a[href="' + pathname + '"]');
        assert.equal(await link.count(),1,'A published guide needs one visible topic entry');
        assert.ok(await link.isVisible(),'A published guide must not remain hidden as coming soon');
        assert.equal(await link.textContent(),locale === 'en' ? 'Topical steroid full-use guide' : '類固醇藥膏完整使用指南','Preserve the existing authored guide name');
        assert.equal(await page.locator('a[data-en="Topical steroid full-use guide (coming)"]').count(),0);
        await link.focus();
        await Promise.all([page.waitForURL(url => url.pathname === pathname,{waitUntil:'load'}),page.keyboard.press('Enter')]);
        assert.equal(new URL(page.url()).pathname,pathname,'The focused topic link must open its published article');
        assert.equal(await page.locator('main h1').count(),1,'The native route must render the actual published guide header');
        assert.deepEqual(errors,[],'Topic navigation must work without runtime exceptions');
        results.push({width,javaScriptEnabled,locale,publishedTopicEntry:true,nativeKeyboardNavigation:true});
        await page.close();
      }
    } finally { await context.close(); }
  }
  return {cases:results.length,results};
}
