import {parse} from 'parse5';

/** Keep the authored Chinese region separate from the immutable article shell.
 * Source offsets are JavaScript string offsets, including non-BMP characters.
 * Unsupported/ambiguous legacy layouts stay in the existing source editor.
 */
export function articleRegion(source) {
  if (typeof source !== 'string' || new TextEncoder().encode(source).length > 1_500_000) {
    throw Error('文章來源過大或格式不符，請保留原稿並使用原始碼模式。');
  }
  const found = [], legacy = [];
  const document = parse(source, {sourceCodeLocationInfo: true});
  function visit(node, inert = false) {
    if ((node.attrs || []).some(attr => attr.name === 'id' && attr.value === 'proseZh')) {
      found.push({node, inert});
    }
    // One older article has an explicitly authored article.prose[data-slug]
    // instead of a language wrapper. Never widen this to main or body.
    const attrs = Object.fromEntries((node.attrs || []).map(attr => [attr.name, attr.value]));
    if (node.tagName === 'article' && (attrs.class || '').split(/\s+/).includes('prose') &&
        /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(attrs['data-slug'] || '') && attrs['data-slug'].length <= 100) {
      legacy.push({node, inert});
    }
    for (const child of node.childNodes || []) visit(child, inert);
    if (node.content) visit(node.content, true);
  }
  visit(document);
  const region = found.length === 1 ? found[0] : found.length === 0 && legacy.length === 1 ? legacy[0] : null;
  const location = region && region.node.sourceCodeLocation;
  if (!region || region.inert || !['div', 'section', 'article'].includes(region.node.tagName) ||
      !location?.startTag || !location.endTag || location.startTag.endOffset > location.endTag.startOffset) {
    throw Error('找不到唯一且完整的中文文章區塊，請使用原始碼模式；原稿未變更。');
  }
  const start = location.startTag.endOffset, end = location.endTag.startOffset;
  const before = source.slice(0, start), after = source.slice(end);
  return Object.freeze({
    kind: found.length ? 'chinese-region' : 'legacy-article',
    inner: source.slice(start, end),
    assemble(inner) {
      if (typeof inner !== 'string') throw Error('編輯內容格式不符，原稿未變更。');
      const assembled = before + inner + after;
      if (new TextEncoder().encode(assembled).length > 1_500_000) throw Error('文章超過草稿上限，請先保留原稿。');
      return assembled;
    }
  });
}
