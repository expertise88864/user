const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const loader = fs.readFileSync('assets/inline/analytics-loader.js', 'utf8');
const shared = fs.readFileSync('blog/blog-shared.js', 'utf8');

// No browser or network collector: only the documented dataLayer command queue.
function fixture({hostname = 'chendermatologist.com', protocol = 'https:', userAgent = 'Firefox', referrer = ''} = {}) {
  const handlers = {}, scripts = [], idle = [], timers = [], metricCallbacks = {};
  const location = new URL(`${protocol}//${hostname}/blog/example?q=private#medical`);
  const document = {referrer,
    head: {appendChild: node => { if (node.tagName === 'SCRIPT') scripts.push(node); }},
    createElement: tag => ({tagName: tag.toUpperCase()}),
    getElementsByTagName: () => [{parentNode: {insertBefore: script => scripts.push(script)}}],
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: (name, fn) => (handlers[name] ||= []).push(fn),
  };
  const context = {document, location, navigator: {userAgent}, URL,
    localStorage: {getItem: () => null, setItem() {}, removeItem() {}},
    requestIdleCallback: fn => idle.push(fn), setTimeout: fn => timers.push(fn),
    addEventListener: (name, fn) => (handlers[name] ||= []).push(fn),
  };
  context.window = context;
  context.webVitals = Object.fromEntries(['LCP', 'CLS', 'INP', 'FCP', 'TTFB'].map(name =>
    ['on' + name, fn => (metricCallbacks[name] ||= []).push(fn)]));
  vm.createContext(context);
  vm.runInContext(loader, context);
  vm.runInContext(shared, context);
  const commands = () => Array.from(context.dataLayer || [], args => Array.from(args));
  return {context, document, handlers, scripts, idle, timers, metricCallbacks, commands};
}

test('events bind before idle, replay once, and vitals initialize once', () => {
  const f = fixture();
  f.context.DN.bindGAEvents();
  f.context.DN.bindGAEvents();
  f.context.DN.bindWebVitals();
  f.context.DN.bindWebVitals();
  assert.equal(f.handlers.click.length, 2); // loader navigation + shared outbound
  assert.equal(f.metricCallbacks.LCP.length, 1);
  f.context.gtag('event', 'article_read_threshold', {slug: 'example'});
  f.metricCallbacks.LCP[0]({name: 'LCP', value: 2400, delta: 2400, id: 'metric-1'});
  assert.equal(f.scripts.length, 0);
  f.idle[0]();
  assert.equal(f.commands().filter(c => c[1] === 'article_read_threshold').length, 1);
  assert.equal(f.commands().filter(c => c[1] === 'LCP').length, 1);
  vm.runInContext(loader, f.context);
  f.idle[0]();
  assert.equal(f.commands().filter(c => c[1] === 'page_view').length, 1);
  assert.equal(f.scripts.length, 2);
});

test('search text and query/fragment URLs never enter the command queue', () => {
  const f = fixture({referrer: 'https://example.org/search?q=sensitive#note'});
  f.context.gtag('event', 'search_result_click', {
    search_term: 'sensitive medical text', result_url: '/blog/result?q=private#dx', result_position: 2,
  });
  f.idle[0]();
  const view = f.commands().find(c => c[1] === 'page_view')[2];
  assert.equal(view.page_location, 'https://chendermatologist.com/blog/example');
  assert.equal(view.page_referrer, 'https://example.org/search');
  const search = f.commands().find(c => c[1] === 'search_result_click')[2];
  assert.equal(search.search_term, undefined);
  assert.equal(search.result_position, 2);
  assert.equal(search.result_url, 'https://chendermatologist.com/blog/result');
  assert.doesNotMatch(JSON.stringify(f.commands()), /sensitive|private|#dx|#medical/);
});

test('absent referrer stays absent and malformed event commands are ignored', () => {
  const f = fixture();
  f.context.gtag('config', 'another-id', {});
  f.context.gtag('event', 'invalid name', {});
  f.idle[0]();
  assert.equal(f.commands().find(c => c[1] === 'page_view')[2].page_referrer, '');
  assert.equal(f.commands().length, 3);
});

test('blocked GA has bounded retention; loaded GA can accept subsequent events', () => {
  const f = fixture();
  for (let i = 0; i < 1000; i++) f.context.gtag('event', 'article_read_threshold', {slug: 'example'});
  f.idle[0]();
  for (let i = 0; i < 1000; i++) f.context.gtag('event', 'toc_click', {target: 'dx'});
  assert.equal(f.commands().length, 100);
  f.scripts.find(s => s.src.includes('googletagmanager')).onload();
  f.context.gtag('event', 'toc_click', {target: 'dx'});
  assert.equal(f.commands().length, 101);
});

for (const options of [{hostname: 'localhost'}, {hostname: '127.0.0.1'}, {userAgent: 'Googlebot'}]) {
  test(`local/bot events never collect: ${JSON.stringify(options)}`, () => {
    const f = fixture(options);
    f.context.DN.bindGAEvents();
    f.context.DN.bindWebVitals();
    f.context.gtag('event', 'article_read_threshold', {slug: 'example'});
    f.idle[0]();
    assert.equal(f.commands().length, 0);
    assert.equal(f.scripts.length, 0);
  });
}

for (const options of [
  {hostname: 'chendermatologist-clpruakvg-expertise88864s-projects.vercel.app'},
  {hostname: 'chendermatologist.com.attacker.test'},
  {hostname: 'www.chendermatologist.com'},
  {hostname: 'chendermatologist.com:444'},
  {hostname: '[::1]'},
  {hostname: 'staging.example.test'},
  {protocol: 'http:'},
]) {
  test(`non-production origin cannot collect initial or later events: ${JSON.stringify(options)}`, () => {
    const f = fixture(options);
    f.context.DN.bindGAEvents();
    f.context.DN.bindWebVitals();
    f.context.gtag('event', 'article_read_threshold', {slug: 'example'});
    f.idle[0]();
    f.context.gtag('event', 'toc_click', {target: 'dx'});
    for (const callback of f.metricCallbacks.LCP || []) callback({name: 'LCP', value: 2000, delta: 2000, id: 'fixture'});
    assert.equal(f.commands().length, 0);
    assert.equal(f.scripts.length, 0);
    assert.equal(f.context.clarity, undefined);
  });
}

test('explicit default HTTPS port normalizes to the canonical production origin', () => {
  const f = fixture({hostname: 'chendermatologist.com:443'});
  f.idle[0]();
  assert.equal(f.commands().filter(c => c[1] === 'page_view').length, 1);
  assert.equal(f.scripts.length, 2);
});

test('canonical navigation emits one contextual event without legacy duplicates', () => {
  const f = fixture();
  f.context.DN.bindGAEvents();
  f.context.DN.bindGAEvents();
  const area = {id: 'dn-related-static'};
  const link = {getAttribute: () => '/en/blog/result#dx', closest: () => area};
  const target = {closest: selector => selector === 'a[href]' ? link : null};
  for (const click of f.handlers.click) click({target});
  f.idle[0]();
  const events = f.commands().filter(c => c[0] === 'event' && c[1] !== 'page_view');
  assert.equal(events.length, 1);
  assert.equal(events[0][1], 'select_content');
  assert.equal(events[0][2].navigation_area, 'dn-related-static');
});

test('outbound clicks preserve the external origin while removing private URL values', () => {
  const f = fixture();
  f.context.DN.bindGAEvents();
  const link = {getAttribute: () => 'https://example.org/reference?q=private#medical'};
  const target = {closest: selector => selector === 'a[href]' ? link : null};
  for (const click of f.handlers.click) click({target});
  f.idle[0]();
  const events = f.commands().filter(c => c[1] === 'outbound_click');
  assert.equal(events.length, 1);
  assert.equal(events[0][2].destination, 'https://example.org/reference');
  assert.equal(events[0][2].host, 'example.org');
  assert.doesNotMatch(JSON.stringify(events), /private|medical/);
});
