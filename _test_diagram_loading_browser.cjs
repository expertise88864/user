'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkDiagramLoading(browser) {
  const sources = ['blog/blog-diagrams.js', 'blog/blog-article-reading.js']
    .map(name => fs.readFileSync(path.join(__dirname, name), 'utf8'));
  let cases = 0;
  for (const width of [390, 800, 1440]) {
    for (const mode of ['eager', 'controlled-lazy', 'native-lazy']) {
      for (const slug of ['acne-myths', 'laser-dermatology']) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' });
        try {
          const page = await context.newPage();
          await page.route('**/*', route => route.abort());
          await page.setContent('<!doctype html><html><head></head><body><article class="max-w-3xl"><div id="proseZh">' +
            Array.from({ length: 8 }, (_, i) => `<h2 id="section-${i}">Existing heading ${i}</h2><p>Existing fixture paragraph ${i}</p>`).join('') +
            '</div></article></body></html>');
          await page.evaluate(({ mode, slug }) => {
            window.DN = { currentSlug: () => slug };
            if (mode === 'eager') delete window.IntersectionObserver;
            if (mode === 'controlled-lazy') {
              window.diagramObservers = [];
              window.IntersectionObserver = class {
                constructor(callback) { this.callback = callback; this.targets = new Set(); window.diagramObservers.push(this); }
                observe(target) { this.targets.add(target); }
                unobserve(target) { this.targets.delete(target); }
                disconnect() { this.targets.clear(); }
              };
            }
          }, { mode, slug });
          for (const source of sources) await page.addScriptTag({ content: source });
          const expected = await page.evaluate(() => DN.MED_DIAGRAM_MAP[DN.currentSlug()].map(item => item.key));
          const authoredBefore = await page.locator('#proseZh > h2, #proseZh > p').evaluateAll(nodes => nodes.map(el => el.outerHTML));
          await page.evaluate(() => { DN.injectMedDiagrams(); DN.injectMedDiagrams(); });
          assert.equal(await page.locator('.dn-med-fig').count(), expected.length, `${mode}/${slug}: repeat before paint must not duplicate figures`);
          if (mode === 'controlled-lazy') await page.evaluate(() => {
            for (const observer of diagramObservers)
              observer.callback([...observer.targets].map(target => ({ target, isIntersecting: true })));
          });
          if (mode === 'native-lazy') {
            // The lazy placeholder is intentionally replaced. Scroll to its
            // stable authored heading rather than holding a detached figure.
            const anchors = await page.evaluate(() => DN.MED_DIAGRAM_MAP[DN.currentSlug()]
              .map(item => document.querySelectorAll('#proseZh h2')[item.after].id));
            for (const id of anchors) await page.locator('#' + id).scrollIntoViewIfNeeded();
            await page.waitForFunction(() => !document.querySelector('.dn-med-fig-placeholder'));
          }
          await page.evaluate(() => DN.injectMedDiagrams());
          assert.equal(await page.locator('.dn-med-fig').count(), expected.length, `${mode}/${slug}: rendered figures must stay unique`);
          const observed = await page.evaluate(() => {
            const figures = [...document.querySelectorAll('.dn-med-fig')];
            const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
            return {
              keys: figures.map(el => el.dataset.diagramKey).sort(),
              duplicateIds: ids.filter((id, i) => ids.indexOf(id) !== i),
              renderedContentPreserved: figures.every(figure => {
                const fixture = document.createElement('div');
                fixture.innerHTML = DN.medDiagrams[figure.dataset.diagramKey]();
                const original = fixture.firstElementChild;
                return original.querySelector('svg').outerHTML === figure.querySelector('svg').outerHTML &&
                  original.querySelector('figcaption').outerHTML === figure.querySelector('figcaption').outerHTML &&
                  figure.querySelectorAll('.dn-med-enlarge').length === 1;
              }),
            };
          });
          assert.deepEqual(observed.keys, [...expected].sort());
          assert.deepEqual(observed.duplicateIds, []);
          assert.equal(observed.renderedContentPreserved, true, 'Existing diagram text, SVG and caption must be preserved');
          assert.deepEqual(await page.locator('#proseZh > h2, #proseZh > p').evaluateAll(nodes => nodes.map(el => el.outerHTML)), authoredBefore);
          cases++;
        } finally { await context.close(); }
      }
    }
  }
  return { cases, scope: 'Actual diagram/reading modules, repeated eager/controlled/native lazy initialization, three viewport widths; isolated fixtures, no clinical correctness or physical-device approval.' };
};
