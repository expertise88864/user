// Native DOM regression coverage. Collectors and all network access are blocked.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const crypto = require('node:crypto');
const cases = [
  ['SCORAD', 'atopic-dermatitis-overview', 'dn-scorad'], ['SALT', 'alopecia-areata', 'dn-salt'],
  ['UAS7', 'urticaria-myths', 'dn-uas7'], ['PASI', 'psoriasis-myths', 'dn-pasi'],
  ['DLQI', 'atopic-dermatitis-overview', 'dn-dlqi'], ['Hurley', 'hidradenitis-suppurativa', 'dn-hurley'],
  ['HairScale', 'hairloss-myths', 'dn-hair-scale'], ['Fitzpatrick', 'sunscreen-myths', 'dn-fitzpatrick'],
  ['GAGS', 'acne-myths', 'dn-gags'], ['MASI', 'melasma-myths', 'dn-masi'],
  ['POEM', 'atopic-dermatitis-overview', 'dn-poem'], ['IHS4', 'hidradenitis-suppurativa', 'dn-ihs4'],
  ['NAPSI', 'psoriasis-myths', 'dn-napsi'], ['VASPruritus', 'prurigo-nodularis', 'dn-vas-itch'],
  ['IGA', 'atopic-dermatitis-overview', 'dn-iga'], ['ASIS', 'acne-myths', 'dn-asis'],
  ['VASI', 'vitiligo', 'dn-vasi'], ['EASI', 'atopic-dermatitis-overview', 'dn-easi'],
];
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
async function mount(page, source, [name, slug, id]) {
  await page.setContent('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"></head><body><article class="max-w-3xl mx-auto">Isolated calculator fixture</article></body></html>');
  await page.addStyleTag({ content: fs.readFileSync('assets/tw-mini.css', 'utf8') });
  await page.evaluate(slug => { window.DN = { currentSlug: () => slug }; window.fixtureEvents = []; window.gtag = (...args) => fixtureEvents.push(args); }, slug);
  await page.addScriptTag({ content: source });
  await page.evaluate(name => DN['inject' + name](), name);
  await page.locator('#' + id).waitFor();
}
async function profile(page, id, mode) {
  await page.locator('#' + id).evaluate((box, mode) => {
    const controls = [...box.querySelectorAll('input[type="number"],select')];
    controls.forEach((input, index) => {
      if (input.tagName === 'SELECT') {
        input.selectedIndex = mode === 'min' ? 0 : mode === 'max' ? input.options.length - 1 : Math.floor(input.options.length / 2);
      } else {
        const min = Number(input.min), max = Number(input.max), step = Number(input.step || 1);
        input.value = String(mode === 'min' ? min : mode === 'max' ? max : min + Math.floor((max - min) / step / 2) * step);
      }
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }, mode);
}
async function clinicalHash(page, id) {
  const value = await page.locator('#' + id).evaluate(box => ({
    title: box.querySelector('.dn-calc-title').textContent,
    subtitle: box.querySelector('.dn-calc-sub').innerHTML,
    labels: [...box.querySelectorAll('label')].map(label => label.innerHTML),
    score: box.querySelector('.dn-calc-score').textContent, band: box.querySelector('.dn-calc-band').textContent,
    interpretation: box.querySelector('.dn-calc-interp').innerHTML,
    disclaimer: box.querySelector('.dn-calc-disclaimer').innerHTML,
    links: [...box.querySelectorAll('a')].map(link => [link.getAttribute('href'), link.innerHTML]),
  }));
  return hash(JSON.stringify(value));
}
async function captureContract(browser, source) {
  const context = await browser.newContext({ serviceWorkers: 'block' });
  await context.route('**/*', route => route.abort());
  try {
    const page = await context.newPage(), snapshots = {};
    for (const item of cases) {
      await mount(page, source, item);
      const values = { initial: await clinicalHash(page, item[2]) };
      for (const mode of ['min', 'max', 'middle']) { await profile(page, item[2], mode); values[mode] = await clinicalHash(page, item[2]); }
      snapshots[item[0]] = values;
    }
    return { scope: 'Existing valid UI output identity, not approval of medical correctness', snapshots };
  } finally { await context.close(); }
}
async function checkCalculators(browser) {
  const source = fs.readFileSync('blog/blog-calculators.min.js', 'utf8');
  const expected = JSON.parse(fs.readFileSync('_test_calculator_contract.json', 'utf8'));
  const context = await browser.newContext({ serviceWorkers: 'block' });
  await context.route('**/*', route => route.abort());
  let invalidCases = 0;
  try {
    const page = await context.newPage();
    const shared = fs.readFileSync('blog/blog-shared.js', 'utf8');
    const start = shared.indexOf('  DN.injectCalculatorByName = function');
    const end = shared.indexOf('  // Homepage spotlight', start);
    assert.ok(start >= 0 && end > start, 'actual production dispatcher is present');
    await mount(page, source, ['DLQI', 'atopic-dermatitis-overview', 'dn-dlqi']);
    await page.locator('#dn-dlqi').evaluate(node => node.parentElement.remove());
    await page.addScriptTag({ content: '(function(){var DN=window.DN;' + shared.slice(start, end) + '})();' });
    await page.evaluate(() => { DN.currentSlug = () => 'dermatology-faq'; DN.autoInjectCalculators('dermatology-faq'); });
    await page.locator('#dn-dlqi').waitFor();
    assert.equal(await page.locator('#dn-dlqi select').count(), 10, 'existing tools DLQI link reaches the configured widget');
    assert.equal(await page.evaluate(() => DN._forceInject), false, 'dispatcher releases its temporary override');
    for (const width of [390, 800, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const item of cases) {
        const [name, , id] = item;
        await mount(page, source, item);
        assert.equal(await clinicalHash(page, id), expected.snapshots[name].initial, name + ' initial');
        const box = page.locator('#' + id);
        assert.equal(await box.locator('input,select').evaluateAll(inputs => inputs.filter(input => !input.labels.length && !input.getAttribute('aria-label') && !input.getAttribute('aria-labelledby')).length), 0, name + ' labels');
        for (const mode of ['min', 'max', 'middle']) {
          await profile(page, id, mode);
          assert.equal(await clinicalHash(page, id), expected.snapshots[name][mode], name + ' valid ' + mode);
          assert.equal(await box.locator('[aria-invalid="true"]').count(), 0);
        }
        const before = await clinicalHash(page, id);
        const results = await box.evaluate(box => {
          const results = [];
          for (const input of box.querySelectorAll('input[type="number"]')) {
            const saved = input.value;
            for (const value of ['', String(Number(input.min) - 1), String(Number(input.max) + 1), String(Number(input.min) + Number(input.step || 1) / 2)]) {
              input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }));
              const notice = box.querySelector('.dn-calc-input-notice');
              results.push({ value: input.value, expected: value, invalid: input.getAttribute('aria-invalid'),
                score: box.querySelector('.dn-calc-score').textContent, band: box.querySelector('.dn-calc-band').textContent,
                interpretation: box.querySelector('.dn-calc-interp').textContent, visible: notice && !notice.hidden,
                linked: notice && (input.getAttribute('aria-describedby') || '').split(/\s+/).includes(notice.id), role: notice && notice.getAttribute('role') });
              input.value = saved; input.dispatchEvent(new Event('input', { bubbles: true }));
            }
          }
          return results;
        });
        for (const result of results) {
          assert.equal(result.value, result.expected, name + ' does not clamp'); assert.equal(result.invalid, 'true');
          assert.equal(result.score, '—'); assert.equal(result.band, ''); assert.equal(result.interpretation, '');
          assert.equal(result.visible, true); assert.equal(result.linked, true); assert.equal(result.role, 'status');
        }
        invalidCases += results.length;
        assert.equal(await clinicalHash(page, id), before, name + ' recovery');
        const first = box.locator('input[type="number"]').first();
        if (await first.count()) {
          const saved = await first.inputValue(); await first.fill('');
          assert.equal(await box.locator('.dn-calc-score').textContent(), '—');
          await page.evaluate(() => { document.documentElement.lang = 'en'; });
          await first.fill('-1'); assert.match(await box.locator('.dn-calc-input-notice').textContent(), /Complete all fields/);
          await first.fill(saved); await first.focus(); await first.press('ArrowUp');
          assert.equal(await first.getAttribute('aria-invalid'), 'false', name + ' keyboard');
          assert.equal(await box.locator('.dn-calc-score').locator('..').getAttribute('aria-live'), 'polite');
        }
        const geometry = await box.boundingBox(); assert.ok(geometry && geometry.x >= 0 && geometry.x + geometry.width <= width + 1, name + ' width');
        const events = await page.evaluate(() => fixtureEvents);
        assert.ok(events.every(event => event[0] === 'event' && event[1] === 'calculator_view' && Object.keys(event[2]).sort().join(',') === 'page_path,tool'), 'no input/result telemetry');
      }
    }
    console.log('Calculator UI passed: 18 components, 390/800/1440, preserved valid medical text/results, ' + invalidCases + ' invalid input cases, correction/keyboard/labels, isolated collectors');
  } finally { await context.close(); }
}
module.exports = checkCalculators;
module.exports.captureContract = captureContract;
