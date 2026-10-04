const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const loader = fs.readFileSync('assets/inline/analytics-loader.js', 'utf8');
const shared = fs.readFileSync('blog/blog-shared.js', 'utf8');

// No browser or network collector: only the documented dataLayer command queue.
function fixture({hostname = 'chendermatologist.com', protocol = 'https:', userAgent = 'Firefox', referrer = '', search = '?q=private#medical', storedInternal = false} = {}) {
  const handlers = {}, scripts = [], idle = [], timers = [], metricCallbacks = {};
  const location = new URL(`${protocol}//${hostname}/blog/example${search}`);
  const storage = new Map(storedInternal ? [['dn-ga-internal', '1']] : []);
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
    localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
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

test('internal traffic changes only for the exact parameter and supported values', () => {
  for (const entry of [
    {search: '?ga_internal=1', storedInternal: false, expected: 'internal'},
    {search: '?ga_internal=0', storedInternal: true, expected: null},
    {search: '?ga_internal=%31', storedInternal: false, expected: 'internal'},
    {search: '?ga_internal=10', storedInternal: false, expected: null},
    {search: '?not_ga_internal=1', storedInternal: false, expected: null},
    {search: '?redirect=ga_internal=1', storedInternal: false, expected: null},
    {search: '?not_ga_internal=0', storedInternal: true, expected: 'internal'},
    {search: '?redirect=ga_internal=0', storedInternal: true, expected: 'internal'},
    {search: '?ga_internal=01', storedInternal: true, expected: 'internal'},
  ]) {
    const f = fixture(entry);
    f.idle[0]();
    const config = f.commands().find(command => command[0] === 'config')[2];
    assert.equal(config.traffic_type || null, entry.expected, entry.search);
    assert.equal(f.context.localStorage.getItem('dn-ga-internal'), entry.expected ? '1' : null, entry.search);
  }
});

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
  assert.equal(f.scripts.length, 1);
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
  assert.equal(f.scripts.length, 1);
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

test('public content groups remain measurable without search or attribution identifiers', () => {
  const f = fixture();
  f.context.gtag('event', 'article_read_threshold', {
    slug: 'published-example', category: 'public-topic', visible_seconds: 30,
    email: 'reader@example.test', search_query: 'private-input',
    lcp_element: '#private-input', lcp_url: '/image?email=reader@example.test',
    cls_target: '.private-input', inp_target: '#private-input',
  });
  f.idle[0]();
  const event = f.commands().find(c => c[1] === 'article_read_threshold')[2];
  assert.equal(event.slug, 'published-example');
  assert.equal(event.category, 'public-topic');
  assert.equal(event.visible_seconds, 30);
  assert.doesNotMatch(JSON.stringify(f.commands()), /private-input|reader@example/);
});

test('late contact, newsletter and feed links use one delegated event contract', () => {
  const f = fixture();
  f.context.DN.bindGAEvents();
  f.context.DN.bindGAEvents();
  // These anchors were absent at initialization, as in the deferred footer.
  for (const [href, subscribe] of [['mailto:owner@example.test', false], ['mailto:owner@example.test', true], ['/feed.xml', false]]) {
    const link = {getAttribute: () => href, hasAttribute: key => subscribe && key === 'data-subscribe-link'};
    const target = {closest: selector => selector === 'a[href]' ? link : null};
    for (const click of f.handlers.click) click({target});
  }
  f.idle[0]();
  const events = f.commands().filter(c => c[0] === 'event');
  assert.equal(events.filter(c => c[1] === 'email_click').length, 2);
  assert.equal(events.filter(c => c[1] === 'newsletter_subscribe_click').length, 1);
  assert.equal(events.filter(c => c[1] === 'rss_subscribe_click').length, 1);
  assert.equal(events.find(c => c[1] === 'rss_subscribe_click')[2].feed, 'https://chendermatologist.com/feed.xml');
  assert.doesNotMatch(JSON.stringify(events), /owner@example/);
});

test('Web Vitals preserve timings without forwarding dynamic selectors or resource URLs', () => {
  const f = fixture();
  f.context.DN.bindWebVitals();
  const attribution = {
    element: '#private-input', url: 'https://example.test/private-input',
    largestShiftTarget: '.private-input', interactionTarget: '#private-input',
    interactionType: 'private-input', timeToFirstByte: 123, elementRenderDelay: 456,
    largestShiftTime: 789, inputDelay: 12, processingDuration: 34, presentationDelay: 56,
  };
  for (const name of ['LCP', 'CLS', 'INP']) f.metricCallbacks[name][0]({name, value: 100, delta: 100, id: 'metric-1', attribution});
  f.idle[0]();
  const metrics = f.commands().filter(c => ['LCP', 'CLS', 'INP'].includes(c[1]));
  assert.equal(metrics.length, 3);
  assert.equal(metrics.find(c => c[1] === 'LCP')[2].lcp_ttfb, 123);
  assert.equal(metrics.find(c => c[1] === 'CLS')[2].cls_time, 789);
  assert.equal(metrics.find(c => c[1] === 'INP')[2].inp_processing, 34);
  assert.equal(metrics.find(c => c[1] === 'INP')[2].inp_type, undefined);
  assert.doesNotMatch(JSON.stringify(metrics), /private-input|example\.test/);
});

for (const cancelSignal of [null, 'wheel', 'touchmove', 'keydown', 'pointerdown', 'hashchange', 'pagehide']) {
  test(`late calculator fragment respects reader intent: ${cancelSignal || 'uninterrupted request'}`, () => {
    const f = fixture({search: '#dn-test-score'}), frames = [], moves = [];
    let target = null;
    f.document.getElementById = () => target;
    f.context.scrollY = 0;
    f.context.requestAnimationFrame = callback => frames.push(callback);
    f.context.removeEventListener = (name, fn) => {
      f.handlers[name] = (f.handlers[name] || []).filter(callback => callback !== fn);
    };
    f.context.scrollTo = options => moves.push(options);
    const signals = ['wheel', 'touchmove', 'keydown', 'pointerdown', 'hashchange', 'pagehide', 'scroll'];
    const originalHandlers = Object.fromEntries(signals.map(signal => [signal, [...(f.handlers[signal] || [])]]));
    let expiry, timerActive = false;
    f.context.setTimeout = (callback, delay) => {
      assert.equal(delay, 2000, 'Initial fragment alignment must have a bounded lifetime');
      expiry = callback; timerActive = true; return 1;
    };
    f.context.clearTimeout = () => { timerActive = false; };
    const finish = f.context.DN.prepareRequestedCalculatorScroll();
    if (cancelSignal) for (const handler of [...f.handlers[cancelSignal]]) handler({});
    target = {classList: {contains: name => name === 'dn-calc'}, getBoundingClientRect: () => ({top: 900})};
    finish(true); finish(true);
    while (frames.length) frames.shift()();
    assert.equal(moves.length, cancelSignal ? 0 : 1);
    if (!cancelSignal) assert.equal(moves[0].top, 820);
    if (!cancelSignal) {
      assert.equal(timerActive, true, 'Native fragment/layout settling remains bounded');
      expiry();
    }
    assert.equal(timerActive, false, 'Cancellation or expiry releases the timer');
    for (const signal of signals) {
      assert.deepEqual(f.handlers[signal] || [], originalHandlers[signal],
        'Temporary interaction handlers must be released without removing unrelated handlers');
    }
  });
}

test('replay cannot collect search or personal URLs while public groups remain measurable', () => {
  const f = fixture({search: '?q=private-input&email=reader@example.test#private-note',
    referrer: 'https://example.test/search?q=private-input&email=reader@example.test'});
  f.context.gtag('event', 'article_read_threshold', {slug: 'published-example', category: 'public-topic'});
  f.idle[0]();
  assert.deepEqual(f.scripts.map(script => new URL(script.src).hostname), ['www.googletagmanager.com']);
  assert.equal(f.context.clarity, undefined);
  assert.equal(f.commands().find(command => command[1] === 'article_read_threshold')[2].category, 'public-topic');
  assert.doesNotMatch(JSON.stringify(f.commands()), /private-input|reader@example|private-note/);
});
