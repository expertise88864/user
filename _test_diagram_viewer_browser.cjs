'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

module.exports = async function checkDiagramViewer(browser) {
  const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
  const sources = ['blog/blog-diagrams.js', 'blog/blog-article-reading.js'].map(read);
  let cases = 0;
  for (const width of [390, 800, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' });
    try {
      const page = await context.newPage();
      await page.route('**/*', route => route.abort());
      await page.setContent('<!doctype html><html lang="zh-Hant"><head></head><body><button id="outside">Outside</button>' +
        '<article class="max-w-3xl"><div id="proseZh"></div></article></body></html>');
      await page.addStyleTag({ content: read('assets/tw-mini.css') });
      await page.evaluate(() => {
        delete window.IntersectionObserver;
        window.DN = { currentSlug: () => 'viewer-fixture' };
      });
      for (const source of sources) await page.addScriptTag({ content: source });
      const keys = await page.evaluate(() => Object.keys(DN.medDiagrams));
      for (const [index, key] of keys.entries()) {
        const english = index % 2 === 1;
        await page.evaluate(({ key, english }) => {
          document.documentElement.lang = english ? 'en' : 'zh-Hant';
          document.getElementById('proseZh').innerHTML = '<h2 id="authored-heading">Existing heading</h2><p>Existing paragraph</p>';
          DN.MED_DIAGRAM_MAP['viewer-fixture'] = [{ key, after: 0 }];
          DN.injectMedDiagrams();
          DN.injectMedDiagrams();
        }, { key, english });
        const figure = page.locator('.dn-med-fig');
        const button = figure.locator('.dn-med-enlarge');
        assert.equal(await button.count(), 1, 'Repeat initialization keeps a single button');
        assert.equal(await button.textContent(), english ? 'Enlarge diagram' : '放大圖解');
        const before = await figure.locator('svg').evaluate(el => el.outerHTML);
        if (key === 'laser-wavelength' || key === 'dermatome-map') {
          const clipped = await figure.locator('svg').evaluate(svg => {
            const bounds = svg.getBoundingClientRect();
            return [...svg.querySelectorAll('text')].filter(text => {
              const box = text.getBoundingClientRect();
              return box.left < bounds.left - 1 || box.top < bounds.top - 1 || box.right > bounds.right + 1 || box.bottom > bounds.bottom + 1;
            }).map(text => text.textContent);
          });
          assert.deepEqual(clipped, [], key + ': all existing labels fit the SVG viewport');
        }
        await button.focus();
        await page.keyboard.press('Enter');
        const dialog = page.locator('dialog.dn-med-viewer');
        await page.waitForFunction(() => document.querySelector('dialog.dn-med-viewer').open);
        assert.equal(await dialog.locator('svg').count(), 1);
        assert.equal(await dialog.locator('.dn-med-close').textContent(), english ? 'Close' : '關閉');
        assert.equal(await dialog.locator('.dn-med-close').evaluate(el => document.activeElement === el), true);
        const clone = await dialog.locator('svg').evaluate(el => {
          const original = document.querySelector('.dn-med-fig svg');
          const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
          const refs = [...el.querySelectorAll('*'), el].flatMap(node => [...node.attributes].flatMap(attr => {
            if (/^aria-(labelledby|describedby)$/.test(attr.name)) return attr.value.split(/\s+/);
            if (attr.localName === 'href' && attr.value.startsWith('#')) return [attr.value.slice(1)];
            return [...attr.value.matchAll(/url\(\s*['"]?#([^)'"\s]+)/g)].map(match => match[1]);
          }));
          return {
            duplicateIds: ids.filter((id, i) => ids.indexOf(id) !== i),
            allReferencesInternal: refs.every(id => [...el.querySelectorAll('[id]'), el].some(node => node.id === id)),
            textPreserved: [...el.querySelectorAll('text,title,desc')].map(node => node.textContent).join('\n') ===
              [...original.querySelectorAll('text,title,desc')].map(node => node.textContent).join('\n'),
            viewBoxPreserved: el.getAttribute('viewBox') === original.getAttribute('viewBox'),
            accessibleTitle: document.getElementById(el.getAttribute('aria-labelledby')).textContent === original.querySelector('title').textContent,
          };
        });
        assert.deepEqual(clone.duplicateIds, []);
        assert.equal(clone.allReferencesInternal, true, key + ': internal SVG references stay with the clone');
        assert.equal(clone.textPreserved, true);
        assert.equal(clone.viewBoxPreserved, true);
        assert.equal(clone.accessibleTitle, true);
        // Native modal focus must stay inside, including wrapping in both directions.
        for (const direction of ['Tab', 'Tab', 'Shift+Tab', 'Shift+Tab']) {
          await page.keyboard.press(direction);
          assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true);
        }
        // Inert outside content cannot steal focus while the dialog is open.
        await page.locator('#outside').evaluate(el => el.focus());
        assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true);
        const viewport = dialog.locator('.dn-med-viewer-scroll');
        if (width === 390) {
          await viewport.focus();
          await page.keyboard.press('End');
          await viewport.evaluate(el => { el.scrollLeft = el.scrollWidth; });
          assert.ok(await viewport.evaluate(el => el.scrollLeft) > 0, 'Large diagram can be panned on mobile');
        }
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => !document.querySelector('dialog.dn-med-viewer').open && !document.querySelector('dialog.dn-med-viewer svg'));
        assert.equal(await button.evaluate(el => document.activeElement === el), true);
        assert.equal(await figure.locator('svg').evaluate(el => el.outerHTML), before);
        // Reopen and close using the visible button too; no stale clone/listener.
        await button.press('Enter');
        await dialog.locator('.dn-med-close').click();
        await page.waitForFunction(() => !document.querySelector('dialog.dn-med-viewer svg'));
        assert.equal(await button.evaluate(el => document.activeElement === el), true);
        assert.equal(await page.locator('dialog.dn-med-viewer').count(), 1);
        cases++;
      }
      // Browsers without native modal support retain a keyboard-scrollable figure.
      await page.evaluate(() => {
        HTMLDialogElement.prototype.showModal = undefined;
        document.getElementById('proseZh').innerHTML = '<h2>Existing heading</h2>';
        DN.injectMedDiagrams();
      });
      assert.equal(await page.locator('.dn-med-enlarge').count(), 0);
      assert.equal(await page.locator('.dn-med-fig').getAttribute('tabindex'), '0');
      assert.equal(await page.locator('.dn-med-fig svg').count(), 1);
      cases++;
    } finally { await context.close(); }
    // Exercise the original article HTML, styles, bundles and native lazy
    // initialization as well as the catalogue fixtures above.
    for (const [slug, key, after] of [['laser-dermatology', 'laser-wavelength', 0], ['shingles-myths', 'dermatome-map', 1]]) {
      const articleContext = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' });
      try {
        const page = await articleContext.newPage();
        const origin = 'https://diagram-article.invalid';
        await page.route('**/*', route => {
          const url = new URL(route.request().url());
          if (url.origin !== origin || !/^\/(?:blog|assets)\//.test(url.pathname)) return route.abort();
          let name = url.pathname.slice(1);
          if (!path.extname(name)) name += '.html';
          const file = path.resolve(__dirname, name);
          if (!file.startsWith(__dirname + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return route.abort();
          const type = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' }[path.extname(file)] || 'application/octet-stream';
          return route.fulfill({ status: 200, body: fs.readFileSync(file), contentType: type });
        });
        await page.goto(origin + '/blog/' + slug, { waitUntil: 'load' });
        await page.locator('#proseZh h2').nth(after).scrollIntoViewIfNeeded();
        const figure = page.locator('.dn-med-fig[data-diagram-key="' + key + '"]');
        await figure.locator('svg').waitFor();
        const geometry = await figure.locator('svg').evaluate(svg => {
          const bounds = svg.getBoundingClientRect();
          const original = document.createElement('div');
          original.innerHTML = DN.medDiagrams[svg.parentElement.dataset.diagramKey]();
          return {
            clipped: [...svg.querySelectorAll('text')].filter(text => {
              const box = text.getBoundingClientRect();
              return box.left < bounds.left - 1 || box.top < bounds.top - 1 || box.right > bounds.right + 1 || box.bottom > bounds.bottom + 1;
            }).map(text => text.textContent),
            svgPreserved: svg.outerHTML === original.querySelector('svg').outerHTML,
            pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          };
        });
        assert.deepEqual(geometry.clipped, [], slug + ': original article labels are not clipped');
        assert.equal(geometry.svgPreserved, true);
        assert.equal(geometry.pageOverflow, false, 'Diagram scrolling must stay inside its figure');
        await figure.locator('.dn-med-enlarge').press('Enter');
        await page.waitForFunction(() => document.querySelector('dialog.dn-med-viewer').open);
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => !document.querySelector('dialog.dn-med-viewer svg'));
        assert.equal(await figure.locator('.dn-med-enlarge').evaluate(el => el === document.activeElement), true);
        cases++;
      } finally { await articleContext.close(); }
    }
  }
  return { cases, scope: 'All original diagram definitions, native modal keyboard/inert/focus/close/reopen and internal SVG references, Chinese/English labels, three viewport widths, unsupported-modal fallback; isolated public-source fixtures, no physical-device or medical approval.' };
};
