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
  exact(value, ['version', 'font', 'order', 'picks', 'legacyPicks']);
  if (value.version !== 1 || typeof value.legacyPicks !== 'boolean') fail(400, 'invalid_settings');
  exact(value.font, Object.keys(contract.fonts));
  for (const [field, options] of Object.entries(contract.fonts)) {
    if (typeof value.font[field] !== 'string' || !options.includes(value.font[field])) fail(400, 'invalid_settings_font');
  }
  for (const field of ['order', 'picks']) {
    const list = value[field], max = field === 'order' ? contract.maxArticles : contract.maxPicks;
    if (!Array.isArray(list) || list.length > max || new Set(list).size !== list.length ||
        list.some(slug => typeof slug !== 'string' || slug.length > 100 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))) fail(400, 'invalid_settings_' + field);
  }
  if (!value.picks.length) fail(400, 'invalid_settings_selection');
  return { version: 1, legacyPicks: value.legacyPicks, font: { ...value.font }, order: [...value.order], picks: [...value.picks] };
}

// New author input remains strict. Only projection of already stored data can
// outlive its original catalogue; it cannot authorise a new private selection.
export function settingsOf(value, articles) {
  const result = settingsRecord(value), slugs = new Set(articles.map(item => item.slug));
  for (const field of ['order', 'picks']) {
    if (result[field].some(slug => !slugs.has(slug))) fail(400, 'invalid_settings_' + field);
  }
  if (result.order.length && result.order.length !== articles.length) fail(400, 'invalid_settings_selection');
  return result;
}
export function projectSettings(value, articles) {
  const result = settingsRecord(value), current = articles.map(item => item.slug), visible = new Set(current);
  if (result.order.length) {
    const retained = result.order.filter(slug => visible.has(slug)), selected = new Set(retained);
    result.order = retained.concat(current.filter(slug => !selected.has(slug)));
  }
  result.picks = result.picks.filter(slug => visible.has(slug));
  return result;
}
