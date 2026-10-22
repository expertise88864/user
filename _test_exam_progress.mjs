// exam/exam.js progress bookkeeping on the real generated pages: each chapter
// row on the hub counts only answers given on that chapter's own page, while
// the overall summary, year papers and the wrong notebook stay site-wide.
// The pages are parsed with parse5 into a small DOM; exam.js runs unmodified
// in a vm context with an in-memory localStorage. No network, no browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { parse } from 'parse5';

const SOURCE = fs.readFileSync('exam/exam.js', 'utf8');
const pageCache = new Map();
function pageTree(file) {
  if (!pageCache.has(file)) pageCache.set(file, parse(fs.readFileSync(file, 'utf8')));
  return pageCache.get(file);
}

// ------------------------------------------------------------ minimal DOM
function matchCompound(el, c) {
  if (c.tag && c.tag !== '*' && el.tagName.toLowerCase() !== c.tag) return false;
  if (c.id !== undefined && el.getAttribute('id') !== c.id) return false;
  for (const cls of c.classes) if (!el.classList.contains(cls)) return false;
  for (const [name, value] of c.attrs) {
    if (!el.hasAttribute(name)) return false;
    if (value !== undefined && el.getAttribute(name) !== value) return false;
  }
  for (const p of c.pseudo) {
    if (p === 'checked' && !el.checked) return false;
    if (p === 'not-disabled' && el.disabled) return false;
    if (p === 'hover') return false;
  }
  return true;
}
function parseCompound(text) {
  const c = { tag: null, classes: [], attrs: [], pseudo: [] };
  const re = /^(?:([a-zA-Z][\w-]*|\*)|#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=(?:"([^"]*)"|([^\]]*)))?\]|:not\(:disabled\)|:(checked|hover))/;
  let rest = text;
  while (rest) {
    const m = re.exec(rest);
    if (!m) throw new Error('unsupported selector: ' + text);
    if (m[1]) c.tag = m[1].toLowerCase();
    else if (m[2]) c.id = m[2];
    else if (m[3]) c.classes.push(m[3]);
    else if (m[4]) c.attrs.push([m[4], m[5] !== undefined ? m[5] : m[6]]);
    else if (m[0] === ':not(:disabled)') c.pseudo.push('not-disabled');
    else c.pseudo.push(m[7]);
    rest = rest.slice(m[0].length);
  }
  return c;
}
const selectorCache = new Map();
function compile(selector) {
  if (!selectorCache.has(selector)) {
    selectorCache.set(selector, selector.split(',').map(part => part.trim().split(/\s+/).map(parseCompound)));
  }
  return selectorCache.get(selector);
}
function matches(el, selector) {
  return compile(selector).some(chain => {
    if (!matchCompound(el, chain[chain.length - 1])) return false;
    let i = chain.length - 2;
    for (let p = el.parentNode; p && i >= 0; p = p.parentNode) {
      if (p.nodeType === 1 && matchCompound(p, chain[i])) i -= 1;
    }
    return i < 0;
  });
}

class Node {
  constructor(doc) { this.ownerDocument = doc; this.parentNode = null; this.childNodes = []; }
  get firstChild() { return this.childNodes[0] || null; }
  get nextSibling() {
    if (!this.parentNode) return null;
    const list = this.parentNode.childNodes;
    return list[list.indexOf(this) + 1] || null;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
}
class Text extends Node {
  constructor(doc, data) { super(doc); this.nodeType = 3; this.data = String(data); }
  get textContent() { return this.data; }
  set textContent(v) { this.data = String(v); }
}
class Element extends Node {
  constructor(doc, tag) {
    super(doc);
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.attributes = new Map();
    this.listeners = {};
    this._checked = undefined;
    this.style = {};
    const self = this;
    this.classList = {
      contains: c => self.className.split(/\s+/).includes(c),
      add: c => { if (!self.classList.contains(c)) self.className = (self.className + ' ' + c).trim(); },
      remove: c => { self.className = self.className.split(/\s+/).filter(x => x && x !== c).join(' '); },
      toggle: (c, force) => {
        const on = force === undefined ? !self.classList.contains(c) : !!force;
        if (on) self.classList.add(c); else self.classList.remove(c);
        return on;
      },
    };
  }
  getAttribute(n) { return this.attributes.has(n) ? this.attributes.get(n) : null; }
  setAttribute(n, v) { this.attributes.set(n, String(v)); }
  removeAttribute(n) { this.attributes.delete(n); }
  hasAttribute(n) { return this.attributes.has(n); }
  get id() { return this.getAttribute('id') || ''; }
  set id(v) { this.setAttribute('id', v); }
  get className() { return this.getAttribute('class') || ''; }
  set className(v) { this.setAttribute('class', v); }
  get href() { return this.getAttribute('href') || ''; }
  set href(v) { this.setAttribute('href', v); }
  get type() { return this.getAttribute('type') || ''; }
  set type(v) { this.setAttribute('type', v); }
  get value() {
    if (this.tagName === 'SELECT') {
      const opts = this.querySelectorAll('option');
      const sel = opts.find(o => o.hasAttribute('selected')) || opts[0];
      return sel ? sel.value : '';
    }
    return this.getAttribute('value') || '';
  }
  set value(v) { this.setAttribute('value', v); }
  get checked() { return this._checked === undefined ? this.hasAttribute('checked') : this._checked; }
  set checked(v) { this._checked = !!v; }
  get disabled() { return this.hasAttribute('disabled'); }
  set disabled(v) { if (v) this.setAttribute('disabled', ''); else this.removeAttribute('disabled'); }
  get hidden() { return this.hasAttribute('hidden'); }
  set hidden(v) { if (v) this.setAttribute('hidden', ''); else this.removeAttribute('hidden'); }
  get textContent() { return this.childNodes.map(n => n.textContent).join(''); }
  set textContent(v) {
    this.childNodes.forEach(n => { n.parentNode = null; });
    this.childNodes = [];
    if (String(v) !== '') this.appendChild(new Text(this.ownerDocument, v));
  }
  get tBodies() { return this.childNodes.filter(n => n.tagName === 'TBODY'); }
  get rows() { return this.querySelectorAll('tr'); }
  appendChild(child) { return this.insertBefore(child, null); }
  insertBefore(child, ref) {
    if (child.parentNode) child.parentNode.removeChild(child);
    const at = ref ? this.childNodes.indexOf(ref) : -1;
    if (at < 0) this.childNodes.push(child); else this.childNodes.splice(at, 0, child);
    child.parentNode = this;
    return child;
  }
  removeChild(child) {
    const at = this.childNodes.indexOf(child);
    if (at >= 0) this.childNodes.splice(at, 1);
    child.parentNode = null;
    return child;
  }
  contains(node) { for (let n = node; n; n = n.parentNode) if (n === this) return true; return false; }
  *descendants() {
    for (const c of this.childNodes) if (c.nodeType === 1) { yield c; yield* c.descendants(); }
  }
  querySelectorAll(sel) { return [...this.descendants()].filter(el => matches(el, sel)); }
  querySelector(sel) { for (const el of this.descendants()) if (matches(el, sel)) return el; return null; }
  matches(sel) { return matches(this, sel); }
  closest(sel) { for (let n = this; n && n.nodeType === 1; n = n.parentNode) if (matches(n, sel)) return n; return null; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener() {}
  dispatch(type) { (this.listeners[type] || []).forEach(fn => fn({ type, target: this, preventDefault() {} })); }
  click() { this.dispatch('click'); }
  getClientRects() { return [1]; }
  getBoundingClientRect() { return { top: 1000, height: 10 }; }
  scrollIntoView() {}
  focus() {}
}

function buildDocument(tree) {
  const doc = {
    readyState: 'complete', visibilityState: 'visible', listeners: {},
    createElement: tag => new Element(doc, tag),
    createTextNode: text => new Text(doc, text),
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener() {},
  };
  const convert = node => {
    if (node.nodeName === '#text') return new Text(doc, node.value);
    if (!node.tagName) return null;
    const el = new Element(doc, node.tagName);
    for (const a of node.attrs) el.setAttribute(a.name, a.value);
    for (const c of node.childNodes || []) { const k = convert(c); if (k) el.appendChild(k); }
    return el;
  };
  const html = tree.childNodes.find(n => n.tagName === 'html');
  doc.documentElement = convert(html);
  doc.body = doc.documentElement.querySelector('body');
  doc.querySelector = sel => doc.documentElement.querySelector(sel);
  doc.querySelectorAll = sel => doc.documentElement.querySelectorAll(sel);
  doc.getElementById = id => doc.documentElement.querySelector('#' + id);
  Object.defineProperty(doc, 'activeElement', { get: () => doc.body });
  return doc;
}

class FakeStorage {
  constructor(data = {}) { this.data = new Map(Object.entries(data)); this.broken = false; }
  getItem(k) { if (this.broken) throw new Error('denied'); return this.data.has(k) ? this.data.get(k) : null; }
  setItem(k, v) { if (this.broken) throw new Error('denied'); this.data.set(k, String(v)); }
  removeItem(k) { if (this.broken) throw new Error('denied'); this.data.delete(k); }
  json(k) { return JSON.parse(this.data.get(k)); }
}

// Open a page: a fresh window + document over the shared storage, exam.js run.
function open(storage, path, { confirm = () => true, fetch } = {}) {
  const file = path === '/exam' ? 'exam/index.html' : path.slice(1) + '.html';
  const document = buildDocument(pageTree(file));
  const confirms = [];
  const window = {
    document, localStorage: storage, location: { pathname: path, hash: '' },
    history: {}, pageYOffset: 0, listeners: {},
    addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    removeEventListener() {},
    confirm: message => { confirms.push(message); return confirm(message); },
    scrollTo() {}, requestAnimationFrame() { return 0; },
    setTimeout() { return 0; }, clearTimeout() {}, setInterval() { return 0; }, clearInterval() {},
    Date, JSON, Math, Object, Array, String, Number, RegExp, Error, fetch,
  };
  window.window = window;
  vm.runInNewContext(SOURCE, window, { filename: 'exam/exam.js' });
  return { document, window, confirms };
}

function answer(page, qid, key) {
  const card = page.document.getElementById('q-' + qid);
  assert.ok(card, 'question ' + qid + ' is on the page');
  card.querySelectorAll('input[type=radio]').forEach(input => { input.checked = input.value === key; });
  card.querySelector('.ex-submit').click();
  return card.getAttribute('data-graded');
}
function graded(page, qid) {
  return page.document.getElementById('q-' + qid).getAttribute('data-graded');
}
function hubRows(storage) {
  const hub = open(storage, '/exam');
  const rows = {};
  hub.document.querySelectorAll('.ex-progress tbody tr').forEach(row => {
    rows[row.getAttribute('data-ch')] = {
      done: row.getAttribute('data-done'),
      shown: row.querySelector('.ex-pg-done').textContent,
      acc: row.querySelector('.ex-pg-acc').textContent,
      date: row.querySelector('.ex-pg-date').textContent,
    };
  });
  return { rows, summary: hub.document.getElementById('ex-progress-summary').textContent };
}
function doneChapters(rows) {
  return Object.keys(rows).filter(ch => rows[ch].done !== '0');
}

// 108-44 sits in Ch.1, 42, 44, 52, 121 and 134; 105-35 in Ch.1, 35, 52, ...
const SHARED = '108-44';
const SHARED_KEY = 'C';
const OTHER = '105-35';

test('fixture: the shared questions really belong to several chapters', () => {
  const html = fs.readFileSync('exam/index.html', 'utf8');
  for (const [ch, qid] of [['1', SHARED], ['52', SHARED], ['1', OTHER], ['52', OTHER]]) {
    const row = new RegExp('<tr data-ch="' + ch + '" [^>]*data-qids="([^"]*)"').exec(html);
    assert.ok(row && row[1].split(',').includes(qid), 'Ch.' + ch + ' lists ' + qid);
  }
  assert.match(html, /章節統計只計算在該章頁面作答的題目/);
});

test('an answer in chapter A does not mark chapter B (which shares the question) as done', () => {
  const storage = new FakeStorage();
  const ch1 = open(storage, '/exam/fitz-1');
  assert.equal(answer(ch1, SHARED, SHARED_KEY), 'right');

  const { rows, summary } = hubRows(storage);
  assert.deepEqual(doneChapters(rows), ['1']);
  assert.match(rows['1'].shown, /^1 \/ \d+$/);
  assert.equal(rows['1'].acc, '100%');
  assert.notEqual(rows['1'].date, '—');
  assert.equal(rows['52'].acc, '—');
  assert.equal(rows['52'].date, '—');
  assert.match(rows['52'].shown, /^0 \/ \d+$/);
  // The site-wide summary still counts every answer.
  assert.match(summary, /^已作答 1 \/ \d+ 題，正確率 100%/);

  assert.deepEqual(Object.keys(storage.json('dnExamChapterProgress')), ['fitz-1']);
  assert.ok(Array.isArray(storage.json('dnExamProgress')[SHARED]));
  // Reopened: Ch.1 shows its answer, Ch.52 shows the question unanswered.
  assert.equal(graded(open(storage, '/exam/fitz-1'), SHARED), 'right');
  assert.equal(graded(open(storage, '/exam/fitz-52'), SHARED), null);
});

test('year paper answers count site-wide but in no chapter', () => {
  const storage = new FakeStorage();
  const year = open(storage, '/exam/year-108');
  assert.equal(answer(year, SHARED, 'A'), 'wrong');

  const { rows, summary } = hubRows(storage);
  assert.deepEqual(doneChapters(rows), []);
  assert.match(summary, /^已作答 1 \/ \d+ 題，正確率 0%/);
  assert.equal(storage.getItem('dnExamChapterProgress'), null);
  assert.deepEqual(storage.json('dnExamWrong'), [SHARED]);
  // The year paper reopens with the answer; the chapter page does not.
  assert.equal(graded(open(storage, '/exam/year-108'), SHARED), 'wrong');
  assert.equal(graded(open(storage, '/exam/fitz-1'), SHARED), null);
});

test('清除本章作答 clears this chapter only, and overall records only while they are this answer', () => {
  const storage = new FakeStorage();
  assert.equal(answer(open(storage, '/exam/fitz-52'), SHARED, 'A'), 'wrong');
  const ch1 = open(storage, '/exam/fitz-1');
  answer(ch1, SHARED, SHARED_KEY);
  answer(ch1, OTHER, 'A');
  // OTHER answered again later on its year paper: that overall record stays.
  answer(open(storage, '/exam/year-105'), OTHER, 'B');
  const otherOverall = storage.json('dnExamProgress')[OTHER];
  const notebook = storage.getItem('dnExamWrong');

  const page = open(storage, '/exam/fitz-1');
  assert.equal(graded(page, SHARED), 'right');
  const clear = page.document.querySelector('.ex-clear-answers');
  assert.equal(clear.textContent, '清除本章作答紀錄');
  assert.equal(clear.disabled, false);
  clear.click();
  assert.equal(page.confirms.length, 1);
  assert.match(page.confirms[0], /^清除本章已作答的 2 題紀錄並重新作答？/);
  assert.match(page.confirms[0], /其他章節的統計不受影響/);
  assert.match(page.confirms[0], /錯題本保留/);
  assert.equal(graded(page, SHARED), null);
  assert.equal(graded(page, OTHER), null);
  assert.equal(clear.disabled, true);

  const chapters = storage.json('dnExamChapterProgress');
  assert.deepEqual(Object.keys(chapters), ['fitz-52']);
  assert.ok(Array.isArray(chapters['fitz-52'][SHARED]));
  const overall = storage.json('dnExamProgress');
  assert.equal(overall[SHARED], undefined, 'latest overall answer was given in Ch.1');
  assert.deepEqual(overall[OTHER], otherOverall, 'a later answer elsewhere is kept');
  // The wrong notebook is never cleared here.
  assert.equal(storage.getItem('dnExamWrong'), notebook);

  const { rows } = hubRows(storage);
  assert.deepEqual(doneChapters(rows), ['52']);
  assert.equal(graded(open(storage, '/exam/fitz-52'), SHARED), 'wrong');
});

test('a cancelled clear changes nothing', () => {
  const storage = new FakeStorage();
  answer(open(storage, '/exam/fitz-1'), SHARED, SHARED_KEY);
  const before = [...storage.data.entries()];
  const page = open(storage, '/exam/fitz-1', { confirm: () => false });
  page.document.querySelector('.ex-clear-answers').click();
  assert.deepEqual([...storage.data.entries()], before);
  assert.equal(graded(page, SHARED), 'right');
});

test('clearing a year paper keeps chapter statistics', () => {
  const storage = new FakeStorage();
  answer(open(storage, '/exam/fitz-1'), SHARED, SHARED_KEY);
  const year = open(storage, '/exam/year-108');
  assert.equal(graded(year, SHARED), 'right', 'year paper shows the latest overall answer');
  year.document.querySelector('.ex-clear-answers').click();
  assert.match(year.confirms[0], /各章節的統計只計算在章節頁作答的題目，不受影響/);
  assert.equal(storage.json('dnExamProgress')[SHARED], undefined);
  assert.deepEqual(doneChapters(hubRows(storage).rows), ['1']);
});

const MALFORMED = [
  'not json', '[1,2]', '"text"', '7', 'null', '{"fitz-1":[1,2]}', '{"fitz-1":"x"}', '{"fitz-1":null}',
  '{"fitz-1":{"108-44":"bad","105-35":{"0":1}}}', '{"fitz-1":{"108-44":[1,"yesterday","C"]}}',
];
for (const raw of MALFORMED) {
  test('malformed dnExamChapterProgress is ignored and replaced on the next answer: ' + raw, () => {
    const storage = new FakeStorage({ dnExamChapterProgress: raw, dnExamProgress: raw });
    const { rows, summary } = hubRows(storage);
    const done = doneChapters(rows);
    if (raw.includes('yesterday')) {
      // A record with an unreadable time still counts, without a bogus date.
      assert.deepEqual(done, ['1']);
      assert.equal(rows['1'].date, '—');
    } else {
      assert.deepEqual(done, []);
    }
    assert.match(summary, /^已作答 \d+ \/ \d+ 題/);
    const page = open(storage, '/exam/fitz-1');
    assert.equal(answer(page, OTHER, 'A') !== null, true);
    const chapters = storage.json('dnExamChapterProgress');
    assert.ok(chapters && typeof chapters === 'object' && !Array.isArray(chapters));
    assert.ok(Array.isArray(chapters['fitz-1'][OTHER]));
    assert.ok(Array.isArray(storage.json('dnExamProgress')[OTHER]));
  });
}

test('storage that throws never breaks a page', () => {
  const storage = new FakeStorage();
  storage.broken = true;
  const page = open(storage, '/exam/fitz-1');
  assert.equal(answer(page, SHARED, SHARED_KEY), 'right');
  const hub = open(storage, '/exam');
  assert.match(hub.document.getElementById('ex-progress-summary').textContent, /無法儲存資料/);
});

test('a corrected official answer fixes the chapter record; the notebook follows the overall record', () => {
  const t = Date.UTC(2026, 9, 1);
  // Recorded as right with pick A, but the official answer is C.
  const storage = new FakeStorage({
    dnExamChapterProgress: JSON.stringify({ 'fitz-1': { [SHARED]: [1, t, 'A'] } }),
    dnExamProgress: JSON.stringify({ [SHARED]: [1, t, 'A'] }),
    dnExamWrong: '[]',
  });
  const page = open(storage, '/exam/fitz-1');
  assert.equal(graded(page, SHARED), 'wrong');
  assert.deepEqual(storage.json('dnExamChapterProgress')['fitz-1'][SHARED], [0, t, 'A']);
  assert.deepEqual(storage.json('dnExamProgress')[SHARED], [0, t, 'A']);
  assert.deepEqual(storage.json('dnExamWrong'), [SHARED]);
  assert.equal(hubRows(storage).rows['1'].acc, '0%');

  // Only a chapter record: it is fixed, the notebook is left as it was.
  const alone = new FakeStorage({
    dnExamChapterProgress: JSON.stringify({ 'fitz-1': { [SHARED]: [0, t, SHARED_KEY] } }),
    dnExamWrong: JSON.stringify([SHARED]),
  });
  assert.equal(graded(open(alone, '/exam/fitz-1'), SHARED), 'right');
  assert.deepEqual(alone.json('dnExamChapterProgress')['fitz-1'][SHARED], [1, t, SHARED_KEY]);
  assert.deepEqual(alone.json('dnExamWrong'), [SHARED]);
  assert.equal(alone.getItem('dnExamProgress'), null);
});

test('old overall records are not assigned to any chapter', () => {
  const t = Date.UTC(2026, 9, 1);
  const storage = new FakeStorage({ dnExamProgress: JSON.stringify({ [SHARED]: [1, t, SHARED_KEY], [OTHER]: [0, t] }) });
  const { rows, summary } = hubRows(storage);
  assert.deepEqual(doneChapters(rows), []);
  assert.match(summary, /^已作答 2 \/ \d+ 題，正確率 50%/);
  assert.equal(graded(open(storage, '/exam/fitz-1'), SHARED), null);
  assert.equal(graded(open(storage, '/exam/year-108'), SHARED), 'right');
  assert.deepEqual(JSON.parse(storage.getItem('dnExamProgress'))[SHARED], [1, t, SHARED_KEY], 'kept as is');
});

// 「考試當年 vs 現行觀念」 on the client-rendered wrong notebook: the same block as
// the static pages, last inside .ex-reveal (hidden with the answer in quiz mode).
test('the wrong notebook renders the time machine box inside the reveal', async () => {
  const data = JSON.parse(fs.readFileSync('exam/exam-data.json', 'utf8'));
  const fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(data) });
  const storage = new FakeStorage({ dnExamWrong: JSON.stringify(['101-04', '108-44']) });
  const page = open(storage, '/exam/review', { fetch });
  await new Promise(resolve => setImmediate(resolve));
  const card = page.document.getElementById('q-101-04');
  assert.ok(card, 'the wrong question is rendered');
  const boxes = card.querySelectorAll('.ex-reveal .ex-tm');
  assert.equal(boxes.length, 1);
  const box = boxes[0];
  assert.equal(box.parentNode.className, 'ex-reveal');
  assert.equal(box.parentNode.childNodes[box.parentNode.childNodes.length - 1], box, 'last in the reveal');
  assert.deepEqual(box.querySelectorAll('dt').map(dt => dt.textContent), ['考試當年', '現行觀念', '何時改變', '對答案的影響']);
  const tm = data.questions.find(q => q.id === '101-04').tm;
  const dd = box.querySelectorAll('dd').map(n => n.textContent);
  assert.deepEqual(dd.slice(0, 3), [tm.then, tm.now, tm.changed]);
  assert.equal(dd[3], tm.answer_impact.level + tm.answer_impact.note);
  assert.ok(box.querySelector('.ex-tm-level.ex-tm-diff'));
  const links = box.querySelectorAll('.ex-sources a');
  assert.equal(links.length, tm.sources.length);
  for (const a of links) {
    assert.equal(a.target, '_blank');
    assert.equal(a.rel, 'noopener noreferrer');
  }
  // A question without an entry has no box.
  assert.equal(page.document.getElementById('q-108-44').querySelectorAll('.ex-tm').length, 0);
});

// 模擬考 on the practice page: the paper comes from exam/mock-data.json, every
// card says it is a mock question, and answers go to their own key only —
// never to the official records, chapter progress or the wrong notebook.
test('a mock paper is labelled and kept out of every official record', async () => {
  const exam = JSON.parse(fs.readFileSync('exam/exam-data.json', 'utf8'));
  const mock = JSON.parse(fs.readFileSync('exam/mock-data.json', 'utf8'));
  const fetch = url => Promise.resolve({
    ok: true, json: () => Promise.resolve(String(url).startsWith('/exam/mock-data.json') ? mock : exam),
  });
  const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
  const storage = new FakeStorage();
  const page = open(storage, '/exam/practice', { fetch });
  const form = page.document.querySelector('[data-practice-form]');
  const box = form.querySelector('input[name=ex-mock]');
  assert.ok(box, 'the practice page offers 模擬考');
  assert.match(box.closest('label').textContent, new RegExp('模擬考（題庫 ' + mock.questions.length + ' 題）'));
  box.checked = true;
  box.dispatch('change');
  assert.ok(form.querySelector('.ex-year-set').disabled, 'years do not apply to a mock paper');
  form.querySelector('.ex-build').click();
  await flush();
  const cards = page.document.querySelectorAll('#ex-practice-list .ex-q');
  assert.equal(cards.length, Math.min(50, mock.questions.length));
  assert.ok(cards.every(card => card.hasAttribute('data-mock') && /^M-\d+$/.test(card.getAttribute('data-qid'))));
  assert.ok(cards.every(card => card.querySelector('.ex-mock-tag').textContent === '模擬題，非官方考題'));
  assert.match(page.document.querySelector('.ex-mock-notice').textContent, /模擬題，非官方考題/);
  const first = cards[0];
  const qid = first.getAttribute('data-qid');
  const wrongKey = Object.keys(mock.questions.find(q => q.id === qid).options)
    .find(k => k !== first.getAttribute('data-answer'));
  assert.equal(answer(page, qid, wrongKey), 'wrong');
  assert.equal(storage.json('dnExamMockProgress')[qid][0], 0);
  for (const key of ['dnExamProgress', 'dnExamWrong', 'dnExamChapterProgress']) {
    assert.equal(storage.getItem(key), null, key + ' is untouched');
  }
  assert.equal(storage.json('dnExamPaper').practice.mock, true);
  // Reopened: the mock paper continues, with the answer and the 模擬考 choice.
  const again = open(storage, '/exam/practice', { fetch });
  await flush();
  assert.equal(graded(again, qid), 'wrong');
  assert.ok(again.document.querySelector('input[name=ex-mock]').checked);
  assert.ok(again.document.getElementById('q-' + qid).hasAttribute('data-mock'));
});

// The two banks load independently: a paper asked for earlier whose bank
// arrives later must not replace the newer paper (or its saved answers).
test('a slower earlier build never replaces a newer paper', async () => {
  const exam = JSON.parse(fs.readFileSync('exam/exam-data.json', 'utf8'));
  const mock = JSON.parse(fs.readFileSync('exam/mock-data.json', 'utf8'));
  const pending = {};
  const fetch = url => new Promise(resolve => {
    const which = String(url).startsWith('/exam/mock-data.json') ? 'mock' : 'exam';
    pending[which] = () => resolve({ ok: true, json: () => Promise.resolve(which === 'mock' ? mock : exam) });
  });
  const flush = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
  const storage = new FakeStorage();
  const page = open(storage, '/exam/practice', { fetch });
  const form = page.document.querySelector('[data-practice-form]');
  form.querySelector('.ex-build').click();          // official paper, bank still loading
  const box = form.querySelector('input[name=ex-mock]');
  box.checked = true;
  box.dispatch('change');
  form.querySelector('.ex-build').click();          // then a mock paper
  pending.mock();
  await flush();
  const first = page.document.querySelector('#ex-practice-list .ex-q');
  const qid = first.getAttribute('data-qid');
  assert.ok(first.hasAttribute('data-mock'));
  const key = first.getAttribute('data-answer');
  assert.equal(answer(page, qid, key), 'right');
  pending.exam();                                   // the earlier official bank arrives last
  await flush();
  const cards = page.document.querySelectorAll('#ex-practice-list .ex-q');
  assert.ok(cards.length && cards.every(card => card.hasAttribute('data-mock')), 'the mock paper stays');
  assert.equal(graded(page, qid), 'right');
  const saved = storage.json('dnExamPaper').practice;
  assert.equal(saved.mock, true);
  assert.equal(saved.done[qid], key);
  assert.equal(storage.getItem('dnExamProgress'), null);
});

// Reading progress on the hub (the real browser behaviour, dwell time and the
// chapter page are covered by _test_exam_reading_browser.cjs).
test('the hub shows reading rounds, a summary and the continue-reading card from storage', () => {
  const html = fs.readFileSync('exam/index.html', 'utf8');
  const noted = [...html.matchAll(/<tr data-ch="(\d+)" [^>]*data-notes="1"/g)].map(m => m[1]);
  assert.ok(noted.length >= 3);
  const [a, b, c] = noted;
  const now = Date.now();
  const storage = new FakeStorage({
    dnExamReading: JSON.stringify({
      ['fitz-' + a]: { r: 2, seen: {}, pct: 10, t: 1, done: [1, 2] },
      ['fitz-' + b]: { r: 1, seen: {}, pct: 55, t: 1, done: [1] },
      ['fitz-' + c]: { r: -1, seen: {}, pct: 5, t: 1, done: [] },  // malformed: dropped
    }),
    dnExamPos: JSON.stringify({
      ['fitz-' + b]: { id: 'x', dy: 0, t: now - 7200000, h: '段落標題' },
      ['fitz-' + a]: { id: 'x', dy: 0, t: now - 86400000 * 2 },
      'fitz-99999': { id: 'x', dy: 0, t: now },
    }),
  });
  const hub = open(storage, '/exam');
  const row = ch => hub.document.querySelector('.ex-progress tbody tr[data-ch="' + ch + '"]');
  assert.match(row(a).querySelector('.ex-pg-reading').textContent, /^✓210%$/);
  assert.match(row(b).querySelector('.ex-pg-reading').textContent, /^✓155%$/);
  assert.equal(row(c).querySelector('.ex-pg-reading').textContent, '0%');
  assert.equal(row(b).querySelector('.ex-rd-badge').getAttribute('aria-label'), '讀完 1 次');
  assert.equal(row(b).querySelector('.ex-rd-fill').style.width, '55%');
  // Every chapter has notes now; check a chapter without notes only while one exists.
  const plainRow = hub.document.querySelectorAll('.ex-progress tbody tr').find(r => !r.hasAttribute('data-notes'));
  if (plainRow) assert.equal(plainRow.querySelector('.ex-pg-reading').textContent, '—');
  assert.match(hub.document.getElementById('ex-progress-summary').textContent,
    new RegExp('，重點已讀完 2／' + noted.length + ' 章（其中 1 章 2 次以上）$'));

  const card = hub.document.querySelector('.ex-continue');
  assert.equal(card.hidden, false);
  assert.match(card.querySelector('.ex-continue-main').textContent, new RegExp('^Ch\.' + b + ' .+ 〈段落標題〉$'));
  assert.equal(card.querySelector('.ex-continue-sub').textContent, '2 小時前 · 本章重點已讀 55%');
  assert.equal(card.querySelector('a.ex-cta').getAttribute('href'), '/exam/fitz-' + b);
  assert.deepEqual(card.querySelectorAll('.ex-continue-more a').map(x => x.getAttribute('href')), ['/exam/fitz-' + a]);

  // nothing stored: the card stays hidden
  const empty = open(new FakeStorage(), '/exam');
  assert.equal(empty.document.querySelector('.ex-continue').hidden, true);
  // storage that throws: still hidden, placeholders kept
  const broken = new FakeStorage();
  broken.broken = true;
  assert.equal(open(broken, '/exam').document.querySelector('.ex-continue').hidden, true);
});
