// Content rules for the admin exam editor (api/admin/exam-draft.js).
// Pure functions only: no network, no secrets. Everything here fails closed —
// a note or explanation that does not match today's real data shape is
// rejected with a reason, never silently rewritten.
import { parse, parseFragment } from 'parse5';

export class ExamContentError extends Error {
  constructor(code, reason) { super(code); this.code = code; this.reason = reason; }
}
function reject(code, reason) { throw new ExamContentError(code, reason); }

export const QUESTION_ID = /^\d{3}-\d{2}$/;
export const MAX_NOTE_BYTES = 400_000;
const encoder = new TextEncoder();

// ---------------------------------------------------------------- notes
// data/exam/notes/fitz-<N>.frag is inserted verbatim into every chapter page
// by _gen_exam.py, which also reads it with regexes (SECTION, SECTION_BLOCK,
// expand_marks, wrap_tables). So the allowlist is on the parsed tree AND on
// the raw source: every element is explicitly opened and closed, start tags
// are in the canonical `<tag name="value">` form those regexes expect, and
// no stray end tag can close page markup around the fragment.
const VOID = new Set(['br']);
const TAGS = new Set(['section', 'h2', 'h3', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'span', 'mark',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'aside', 'br']);
// Exact class attribute values in use (measured over all 50 fragments).
const CLASSES = {
  section: new Set(['ex-note']), aside: new Set(['ex-trap']), p: new Set(['ex-cite']),
  span: new Set(['ex-ref', 'ex-ref ex-ref-mckee']), strong: new Set(['ex-n']), table: new Set(['ex-table']),
};
const REQUIRED_CLASS = new Set(['section', 'aside', 'span', 'table']);
const SECTION_ID = /^[a-z0-9-]+$/;
const DATA_Q = /^\d{3}-\d{2}(?:, ?\d{3}-\d{2})*$/;
const SAFE_VALUE = /^[^"<>&\x00-\x1f]*$/;
let context = null;
function divContext() {
  if (!context) context = parse('<div></div>').childNodes.find(n => n.nodeName === 'html')
    .childNodes.find(n => n.nodeName === 'body').childNodes[0];
  return context;
}

export function validateNote(content) {
  if (typeof content !== 'string') reject('invalid_note', '內容必須是文字');
  const source = content.replace(/\r\n?/g, '\n');
  if (!source.trim()) reject('invalid_note', '內容是空的');
  if (encoder.encode(source).length > MAX_NOTE_BYTES) reject('too_large', '內容超過 400 KB');
  if (/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(source)) reject('invalid_note', '含有控制字元');
  if (source.includes('{{')) reject('invalid_note', '不可使用 {{ … }} 標記');
  if (/<[!?]/.test(source)) reject('invalid_note', '不可使用 HTML 註解、<!DOCTYPE> 或 <? … > 宣告');
  const fragment = parseFragment(divContext(), source, { sourceCodeLocationInfo: true });
  const ids = new Set();
  let endTags = 0, startTags = 0;
  function where(node) {
    const at = node.sourceCodeLocation && node.sourceCodeLocation.startLine;
    return at ? `（第 ${at} 行）` : '';
  }
  // Every node must sit inside its parent's source span, after its previous
  // sibling: the parser moves misplaced content (e.g. text or <p> directly in
  // a <table> is foster-parented before it), so the rendered order would
  // differ from what was written.
  function span(node) {
    const at = node.sourceCodeLocation;
    if (!at || !Number.isInteger(at.startOffset) || !Number.isInteger(at.endOffset)) reject('invalid_note', '標籤順序錯亂' + where(node));
    return at;
  }
  function inner(node) {
    if (node === fragment) return [0, source.length];
    const at = span(node);
    return [at.startTag.endOffset, at.endTag ? at.endTag.startOffset : at.startTag.endOffset];
  }
  function checkOrder(parent) {
    const [from, to] = inner(parent);
    let cursor = from;
    for (const child of parent.childNodes || []) {
      const at = span(child);
      if (at.startOffset < cursor || at.endOffset > to) reject('invalid_note', '內容被移到不該在的位置（例如表格內直接放文字或段落）' + where(child));
      cursor = at.endOffset;
    }
  }
  function visit(node, parent, insideTable) {
    if (node.nodeName === '#text') return;
    if (node.nodeName === '#comment') reject('invalid_note', '不可使用 HTML 註解或 <! … > 宣告' + where(node));
    const tag = node.tagName;
    if (!tag || !TAGS.has(tag) || node.namespaceURI !== 'http://www.w3.org/1999/xhtml') {
      reject('invalid_note', `不允許的標籤 <${tag || node.nodeName}>` + where(node));
    }
    const location = node.sourceCodeLocation;
    if (!location || !location.startTag) reject('invalid_note', `<${tag}> 缺少開始標籤（標籤順序錯亂）` + where(parent));
    if (!VOID.has(tag) && !location.endTag) reject('invalid_note', `<${tag}> 沒有對應的結束標籤` + where(node));
    if (!VOID.has(tag)) {
      endTags++;
      // _gen_exam.py matches literal closing tags (e.g. "</h2>"), so the
      // spelling must be canonical too, not just parse-equivalent.
      const closing = source.slice(location.endTag.startOffset, location.endTag.endOffset);
      if (closing !== '</' + tag + '>') reject('invalid_note', `結束標籤需寫成 </${tag}>，實際為 ${closing.slice(0, 40)}` + where(node));
    }
    startTags++;
    // Canonical start tag: what the generator's regexes and wrappers expect.
    const raw = source.slice(location.startTag.startOffset, location.startTag.endOffset);
    const canonical = '<' + tag + node.attrs.map(a => ` ${a.name}="${a.value}"`).join('') + '>';
    if (raw !== canonical || node.attrs.some(a => !SAFE_VALUE.test(a.value))) {
      reject('invalid_note', `開始標籤格式需為 ${canonical.length > 80 ? '<' + tag + ' 屬性="值">' : canonical}，實際為 ${raw.slice(0, 80)}` + where(node));
    }
    const names = node.attrs.map(a => a.name);
    const allowed = new Set(CLASSES[tag] ? ['class'] : []);
    if (tag === 'section') allowed.add('id');
    if (tag === 'mark') allowed.add('data-q');
    if (tag === 'th') allowed.add('scope');
    for (const name of names) if (!allowed.has(name)) reject('invalid_note', `<${tag}> 不允許屬性 ${name}` + where(node));
    const attr = name => (node.attrs.find(a => a.name === name) || {}).value;
    if (names.includes('class') && !CLASSES[tag].has(attr('class'))) reject('invalid_note', `<${tag}> 不允許 class="${attr('class')}"` + where(node));
    if (REQUIRED_CLASS.has(tag) && !names.includes('class')) reject('invalid_note', `<${tag}> 需要 class` + where(node));
    if (tag === 'section') {
      if (parent !== fragment) reject('invalid_note', '<section> 只能放在最外層' + where(node));
      const id = attr('id');
      if (!id || !SECTION_ID.test(id) || names.join(',') !== 'class,id') reject('invalid_note', '<section> 需寫成 <section class="ex-note" id="小寫英數-連字號">' + where(node));
      if (ids.has(id)) reject('invalid_note', `段落 id 重複：${id}` + where(node));
      ids.add(id);
      const first = node.childNodes.find(c => c.nodeName !== '#text' || c.value.trim());
      if (!first || first.tagName !== 'h2') reject('invalid_note', '每個 <section> 必須以 <h2> 開頭' + where(node));
    } else if (parent === fragment) {
      reject('invalid_note', `最外層只能是 <section class="ex-note">，不能是 <${tag}>` + where(node));
    }
    if (tag === 'mark' && !DATA_Q.test(attr('data-q') || '')) reject('invalid_note', '<mark> 需要 data-q="年度-題號"（例如 108-13）' + where(node));
    if (tag === 'th' && names.includes('scope') && !['col', 'row'].includes(attr('scope'))) reject('invalid_note', 'scope 只能是 col 或 row' + where(node));
    if (tag === 'table' && insideTable) reject('invalid_note', '表格不可巢狀' + where(node));
    checkOrder(node);
    for (const child of node.childNodes || []) visit(child, node, insideTable || tag === 'table');
  }
  checkOrder(fragment);
  for (const child of fragment.childNodes) {
    if (child.nodeName === '#text') {
      if (child.value.trim()) reject('invalid_note', '最外層只能是 <section class="ex-note">，不能直接放文字');
      continue;
    }
    visit(child, fragment, false);
  }
  if (!ids.size) reject('invalid_note', '至少要有一個 <section class="ex-note">');
  // A stray end tag is dropped by the parser here but would close page markup
  // around the fragment on the real page. Text never holds a raw "</x".
  const declared = (source.match(/<\/[A-Za-z]/g) || []).length;
  if (declared !== endTags) reject('invalid_note', '有多餘或錯置的結束標籤');
  // Likewise a start tag the fragment parser discards (<html>, <body>, <head>
  // in this context) leaves no node but would reach the generated page.
  const opened = (source.match(/<[A-Za-z]/g) || []).length;
  if (opened !== startTags) reject('invalid_note', '有被忽略的開始標籤（例如 <html>、<body>、<head>）');
  return source;
}

// ---------------------------------------------------------- explanations
// data/exam/explanations.json is written exactly like
// json.dumps(data, indent=1, ensure_ascii=False) (no trailing newline), which
// JSON.stringify(data, null, 1) reproduces for this data. Writers verify that
// identity on the stored file before changing anything.
const DISPUTE_KINDS = new Set(['old', 'missing', 'conflict', 'ambiguous', 'typo', 'figure']);
const CONTROL = /[\x00-\x1f\x7f\u2028\u2029]/;
function isPlainObject(value) { return !!value && typeof value === 'object' && !Array.isArray(value); }
function exactKeys(value, required, optional, path) {
  if (!isPlainObject(value)) reject('invalid_entry', `${path} 必須是物件`);
  for (const key of Object.keys(value)) if (!required.includes(key) && !optional.includes(key)) reject('invalid_entry', `${path} 不允許欄位 ${key}`);
  for (const key of required) if (!(key in value)) reject('invalid_entry', `${path} 缺少欄位 ${key}`);
}
function text(value, path, max, allowEmpty = false) {
  if (typeof value !== 'string') reject('invalid_entry', `${path} 必須是文字`);
  const trimmed = value.trim();
  if (!allowEmpty && !trimmed) reject('invalid_entry', `${path} 不可空白`);
  if (value.length > max) reject('invalid_entry', `${path} 超過 ${max} 字`);
  if (CONTROL.test(value)) reject('invalid_entry', `${path} 含有換行或控制字元`);
  return trimmed;
}

// Returns a new entry in the file's canonical key order. `previous` is the
// stored entry: option keys and their order cannot change from the editor.
export function validateEntry(input, previous) {
  exactKeys(input, ['summary', 'items'], ['flags', 'dispute'], 'entry');
  const entry = { summary: text(input.summary, 'summary', 2000) };
  if (!Array.isArray(input.items) || input.items.length !== previous.items.length) reject('invalid_entry', 'items 數量不可變更');
  entry.items = input.items.map((item, index) => {
    const path = `items[${index}]`;
    exactKeys(item, ['key', 'label', 'ok', 'text', 'refs'], [], path);
    if (item.key !== previous.items[index].key) reject('invalid_entry', `${path}.key 不可變更`);
    if (typeof item.ok !== 'boolean') reject('invalid_entry', `${path}.ok 必須是 true/false`);
    if (!Array.isArray(item.refs) || item.refs.length > 20) reject('invalid_entry', `${path}.refs 必須是陣列（最多 20 筆）`);
    const refs = item.refs.map((ref, r) => {
      if (!Array.isArray(ref) || ref.length !== 2) reject('invalid_entry', `${path}.refs[${r}] 必須是 [章, 頁]`);
      const [chapter, pages] = ref;
      if (!(chapter === 'M' || (Number.isInteger(chapter) && chapter >= 1 && chapter <= 300))) reject('invalid_entry', `${path}.refs[${r}] 章節須為 1–300 或 "M"`);
      if (typeof pages !== 'string' || !/^\d{1,5}(?:-\d{1,5})?$/.test(pages)) reject('invalid_entry', `${path}.refs[${r}] 頁碼須為 266 或 266-267`);
      return [chapter, pages];
    });
    return { key: item.key, label: text(item.label, `${path}.label`, 300), ok: item.ok,
      text: text(item.text, `${path}.text`, 4000), refs };
  });
  // Some disputed questions have no correct option (e.g. 104-48), so ok may be all false.
  if ('flags' in input) {
    if (!Array.isArray(input.flags) || input.flags.length > 10) reject('invalid_entry', 'flags 必須是陣列（最多 10 筆）');
    const flags = input.flags.map((flag, f) => text(flag, `flags[${f}]`, 1000));
    if (flags.length) entry.flags = flags;
  }
  if ('dispute' in input && input.dispute !== null) {
    const d = input.dispute;
    exactKeys(d, ['kind', 'exam'], ['current', 'sources'], 'dispute');
    if (!DISPUTE_KINDS.has(d.kind)) reject('invalid_entry', 'dispute.kind 不在允許清單');
    const dispute = { kind: d.kind, exam: text(d.exam, 'dispute.exam', 2000) };
    if ('current' in d) dispute.current = text(d.current, 'dispute.current', 2000);
    if ('sources' in d) {
      if (!Array.isArray(d.sources) || !d.sources.length || d.sources.length > 10) reject('invalid_entry', 'dispute.sources 必須是 1–10 筆');
      dispute.sources = d.sources.map((s, i) => {
        const path = `dispute.sources[${i}]`;
        exactKeys(s, ['title', 'url', 'year'], ['pmid'], path);
        const title = text(s.title, path + '.title', 500);
        const url = text(s.url, path + '.url', 500);
        let parsed;
        try { parsed = new URL(url); } catch (_) { reject('invalid_entry', `${path}.url 不是有效網址`); }
        if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.href !== url) reject('invalid_entry', `${path}.url 必須是完整的 https 網址`);
        if (!Number.isInteger(s.year) || s.year < 1900 || s.year > 2100) reject('invalid_entry', `${path}.year 必須是西元年`);
        if ('pmid' in s) {
          if (typeof s.pmid !== 'string' || !/^\d{1,9}$/.test(s.pmid)) reject('invalid_entry', `${path}.pmid 必須是數字字串`);
          return { pmid: s.pmid, title, year: s.year, url };
        }
        return { url, title, year: s.year };
      });
    }
    entry.dispute = dispute;
  }
  return entry;
}

export function serializeExplanations(data) { return JSON.stringify(data, null, 1); }

// Replace one existing question's entry. Fails closed unless the stored text
// re-serializes byte-for-byte, so the commit can only change that entry.
export function replaceExplanation(storedText, id, input) {
  if (!QUESTION_ID.test(id || '')) reject('invalid_id', '題號格式須為 108-13');
  let data;
  try { data = JSON.parse(storedText); } catch (_) { reject('format_mismatch', '雲端檔案不是有效 JSON'); }
  if (!isPlainObject(data) || serializeExplanations(data) !== storedText) reject('format_mismatch', '雲端檔案格式與產生器不一致，未寫入');
  if (!Object.prototype.hasOwnProperty.call(data, id)) reject('unknown_question', `沒有題號 ${id}`);
  const entry = validateEntry(input, data[id]);
  data[id] = entry; // existing non-index key: insertion order is preserved
  return { text: serializeExplanations(data), entry };
}

// Current main plus every drafted entry: drafted ids come from the draft copy,
// all other entries from main, so a stale branch copy never reverts newer main
// text. Both stored files must re-serialize byte-for-byte.
export function composeExplanations(mainText, draftText, draftedIds) {
  const parseStored = text => {
    let data;
    try { data = JSON.parse(text); } catch (_) { reject('format_mismatch', '雲端檔案不是有效 JSON'); }
    if (!isPlainObject(data) || serializeExplanations(data) !== text) reject('format_mismatch', '雲端檔案格式與產生器不一致，未寫入');
    return data;
  };
  const data = parseStored(mainText);
  if (!draftedIds.length) return mainText;
  const draft = parseStored(draftText);
  for (const id of draftedIds) {
    if (!Object.prototype.hasOwnProperty.call(draft, id) || !Object.prototype.hasOwnProperty.call(data, id)) reject('format_mismatch', `草稿與 main 的題號 ${id} 對不上`);
    data[id] = draft[id];
  }
  return serializeExplanations(data);
}

export function readExplanation(storedText, id) {
  if (!QUESTION_ID.test(id || '')) reject('invalid_id', '題號格式須為 108-13');
  let data;
  try { data = JSON.parse(storedText); } catch (_) { reject('format_mismatch', '雲端檔案不是有效 JSON'); }
  if (!isPlainObject(data) || !Object.prototype.hasOwnProperty.call(data, id)) reject('unknown_question', `沒有題號 ${id}`);
  return data[id];
}
