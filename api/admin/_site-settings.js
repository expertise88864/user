// Shared, data-only settings contract. Never accepts CSS, scripts or paths.
import contract from '../../_site_settings_contract.json';
export { contract };
export class SettingsError extends Error {
  constructor(status, code) { super(code); this.status = status; this.code = code; }
}
export function fail(status, code) { throw new SettingsError(status, code); }
export const SHA = /^(?!0{40}$)[a-f0-9]{40}$/;
export function revision(value, nullable = false) {
  if (nullable && value === null) return value;
  if (typeof value !== 'string' || !SHA.test(value)) fail(400, 'invalid_settings_revision');
  return value;
}
export function exact(value, keys, status = 400, code = 'invalid_settings') {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))) fail(status, code);
}
export function parseJson(source, status = 400, code = 'invalid_settings_json') {
  let value;
  try { value = JSON.parse(source); } catch (_) { fail(status, code); }
  // JSON.parse silently keeps the last repeated key. Version/approval inputs
  // must have one meaning in the browser, API and candidate validators.
  const tokens = source.match(/"(?:\\.|[^"\\])*"|[{}\[\]:,]/g) || [];
  const stack = [];
  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i];
    if (token === '{') stack.push(new Set());
    else if (token === '[') stack.push(null);
    else if (token === '}' || token === ']') stack.pop();
    else if (token.charAt(0) === '"' && tokens[i + 1] === ':' && stack[stack.length - 1]) {
      const key = JSON.parse(token), keys = stack[stack.length - 1];
      if (keys.has(key)) fail(status, code);
      keys.add(key);
    }
  }
  return value;
}
export function catalogOf(value) {
  exact(value, ['version', 'articles'], 502, 'invalid_settings_catalog');
  if (value.version !== 1 || !Array.isArray(value.articles) || !value.articles.length ||
      value.articles.length > contract.maxArticles) fail(502, 'invalid_settings_catalog');
  const seen = new Set();
  return value.articles.map(item => {
    exact(item, ['slug', 'title', 'title_en'], 502, 'invalid_settings_catalog');
    if (typeof item.slug !== 'string' || item.slug.length > 100 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item.slug) || seen.has(item.slug) ||
        ['title', 'title_en'].some(key => typeof item[key] !== 'string' || !item[key].trim() || item[key].length > 500 ||
          /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?:^|[^\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(item[key]))) fail(502, 'invalid_settings_catalog');
    seen.add(item.slug);
    return { slug: item.slug, title: item.title, title_en: item.title_en };
  });
}
export function settingsRecord(value) {
  // Homepage recommendations (熱門推薦) were retired 2026-10-17.
  exact(value, ['version', 'font', 'order']);
  if (value.version !== 1) fail(400, 'invalid_settings');
  exact(value.font, Object.keys(contract.fonts));
  for (const [field, options] of Object.entries(contract.fonts)) {
    if (typeof value.font[field] !== 'string' || !options.includes(value.font[field])) fail(400, 'invalid_settings_font');
  }
  const list = value.order;
  if (!Array.isArray(list) || list.length > contract.maxArticles || new Set(list).size !== list.length ||
      list.some(slug => typeof slug !== 'string' || slug.length > 100 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))) fail(400, 'invalid_settings_order');
  return { version: 1, font: { ...value.font }, order: [...value.order] };
}

// New author input remains strict. Stored data may outlive its original
// catalogue (see conflict handling); it cannot authorise a new private selection.
export function settingsOf(value, articles) {
  const result = settingsRecord(value), slugs = new Set(articles.map(item => item.slug));
  if (result.order.some(slug => !slugs.has(slug))) fail(400, 'invalid_settings_order');
  if (result.order.length && result.order.length !== articles.length) fail(400, 'invalid_settings_selection');
  return result;
}

// Cloud drafts saved before 熱門推薦 was retired still carry exactly these two
// fields. Only reading such an already stored draft may drop them (font and
// order are kept); every new author input above stays strict.
const RETIRED_DRAFT_FIELDS = ['picks', 'legacyPicks'];
export function storedDraftOf(value, articles) {
  const retired = !!value && typeof value === 'object' && !Array.isArray(value) &&
    RETIRED_DRAFT_FIELDS.some(key => Object.hasOwn(value, key));
  if (!retired) return { settings: settingsOf(value, articles), retired: false };
  exact(value, ['version', 'font', 'order', ...RETIRED_DRAFT_FIELDS]);
  const [list, flag] = RETIRED_DRAFT_FIELDS.map(key => value[key]);
  if (typeof flag !== 'boolean' || !Array.isArray(list) || !list.length || list.length > 12 || new Set(list).size !== list.length ||
      list.some(slug => typeof slug !== 'string' || slug.length > 100 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))) fail(400, 'invalid_settings');
  return { settings: settingsOf({ version: value.version, font: value.font, order: value.order }, articles), retired: true };
}
