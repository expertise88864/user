// Actual runtime on native DOMs; synthetic clock/visibility, isolated storage and collector.
const assert = require('node:assert/strict');
const fs = require('node:fs');

module.exports = async function checkReadingEngagement(browser, {readingSource, sharedSource} = {}) {
  const reading = readingSource || fs.readFileSync('blog/blog-article-reading.min.js', 'utf8');
  const shared = sharedSource || fs.readFileSync('blog/blog-shared.min.js', 'utf8');
  const stylesheet = fs.readFileSync('assets/tw-mini.css', 'utf8');
  const results = [];
  for (const width of [390,800,1440]) for (const lang of ['zh-Hant','en']) {
    const context = await browser.newContext({viewport:{width,height:800},serviceWorkers:'block'});
    try {
      await context.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== 'https://reading-engagement.test' || route.request().method() !== 'GET') return route.abort();
        const root = url.pathname === '/root';
        const body = '<h1>Fixture guide</h1><p>Fixture introduction</p><details id="dn-secondary-meta"><summary>Details</summary></details><h2 id="first">Fixture section</h2><p>' + 'Fixture word. '.repeat(600) + '</p>';
        return route.fulfill({contentType:'text/html; charset=utf-8',body:'<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><title>Isolated reading</title><style>article{min-height:3000px}body{margin:0}footer{height:2000px}</style></head><body><article class="max-w-3xl '+(root?'prose':'')+'">'+(root?body:'<div class="prose">'+body+'</div>')+'</article><footer>End</footer></body></html>'});
      });
      for (const layout of ['root','nested']) {
        const page = await context.newPage(), errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('https://reading-engagement.test/'+layout);
        await page.addStyleTag({content:stylesheet});
        await page.evaluate(() => {
          const aside = document.createElement('aside');
          aside.id = 'color-fixture';
          aside.style.cssText = '--muted:rgb(90,80,70);--teal-deep:rgb(12,81,89);--ink-2:rgb(94,87,78);color:rgb(1,2,3);font-size:18px';
          for (const value of ['var(--muted)','var(--teal-deep)','var(--ink-2)','14px']) {
            const span = document.createElement('span');
            span.className = 'text-['+value+']'; span.textContent = 'Fixture color'; aside.appendChild(span);
          }
          document.body.prepend(aside);
        });
        const colors = await page.locator('#color-fixture span').evaluateAll(nodes => nodes.map(node => ({color:getComputedStyle(node).color,size:getComputedStyle(node).fontSize})));
        assert.deepEqual(colors.map(row=>row.color),['rgb(90, 80, 70)','rgb(12, 81, 89)','rgb(94, 87, 78)','rgb(1, 2, 3)']);
        assert.deepEqual(colors.map(row=>row.size),['18px','18px','18px','14px']);
        await page.addScriptTag({content:shared});
        await page.addScriptTag({content:reading});
        await page.evaluate(() => {
          localStorage.clear();
          window.READING_TEST = {now:0,hidden:false,intervals:[],events:[]};
          // Exercise the real foreground-time algorithm without waiting 30s
          // or confusing this fixture with a physical background-tab trial.
          Object.defineProperty(performance,'now',{value:()=>READING_TEST.now});
          Object.defineProperty(document,'hidden',{get:()=>READING_TEST.hidden});
          window.setInterval = fn => { READING_TEST.intervals.push(fn); return READING_TEST.intervals.length; };
          window.clearInterval = () => {};
          window.gtag = (...args) => READING_TEST.events.push(args);
          DN.currentSlug = () => 'engagement-fixture';
          DN.ARTICLES.push({slug:'engagement-fixture',title:'Fixture guide',date:'2026-01-01',published:true});
          DN.addReadingMeta(); DN.addReadingMeta();
          DN.bindScrollMemory(); DN.bindGAEvents(); DN.bindGAEvents();
        });
        assert.equal(await page.locator('#dn-reading-meta').count(),1,layout+' must show one reading-information bar');
        assert.match(await page.locator('#dn-reading-meta [data-dn-wordcount]').textContent(),/1,20\d words/);
        async function tick(now, pct, hidden) {
          return page.evaluate(async ({now,pct,hidden}) => {
            READING_TEST.now = now;
            if (hidden !== undefined) {
              READING_TEST.hidden = hidden;
              document.dispatchEvent(new Event('visibilitychange'));
            }
            const article = document.querySelector('article');
            const top = article.getBoundingClientRect().top + scrollY;
            scrollTo(0,Math.round(top + article.scrollHeight*pct - innerHeight));
            dispatchEvent(new Event('scroll'));
            await new Promise(resolve => requestAnimationFrame(resolve));
            READING_TEST.intervals.forEach(fn => fn());
            return DN.getReadSlugs();
          },{now,pct,hidden});
        }
        assert.deepEqual(await tick(0,0.85),[],'Progress alone must not mark an article read');
        assert.deepEqual(await tick(29999,0.85),[],'Foreground dwell below 30s must not mark read');
        assert.deepEqual(await tick(29999,0.85,true),[]);
        assert.deepEqual(await tick(119999,0.85),[],'Hidden time must not satisfy the dwell threshold');
        assert.deepEqual(await tick(119999,0.85,false),[]);
        assert.deepEqual(await tick(120000,0.69),[],'30s foreground with less than 70% progress must not mark read');
        assert.deepEqual(await tick(120000,0.85),['engagement-fixture']);
        assert.deepEqual(await tick(180000,0.85),['engagement-fixture']);
        await page.evaluate(() => dispatchEvent(new Event('beforeunload')));
        const memory = await page.evaluate(() => JSON.parse(localStorage.getItem('dn:scroll:engagement-fixture')));
        assert.ok(memory && memory.y > 0,layout+' must save a meaningful reading position');
        // The 75% proxy uses whole-document depth, separately from article
        // engagement. Large article fonts must not make this fixture's footer
        // a fixed percentage of the document.
        await page.evaluate(async () => {
          scrollTo(0,Math.round(document.documentElement.scrollHeight*0.8-innerHeight));
          dispatchEvent(new Event('scroll')); dispatchEvent(new Event('scroll'));
          await new Promise(resolve=>requestAnimationFrame(resolve));
        });
        const outcome = await page.evaluate(() => ({
          readEvents:READING_TEST.events.filter(row=>row[1]==='article_read_threshold').length,
          depthEvents:READING_TEST.events.filter(row=>row[1]==='article_75pct').length,
        }));
        assert.equal(outcome.readEvents,1,'Repeated checks must emit one engaged-reading event');
        assert.equal(outcome.depthEvents,1,'Repeated initialization/scroll must emit one depth proxy');
        assert.deepEqual(errors,[]);
        results.push({width,lang,layout,metadata:true,foregroundThreshold:true,progressThreshold:true,readingMemory:true,eventsOnce:true,actualColorUtilities:true});
        await page.close();
      }
    } finally { await context.close(); }
  }
  return {cases:results.length,results,realVendorEgress:false,syntheticClockAndVisibility:true};
};
