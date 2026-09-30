import assert from 'node:assert/strict';
import {test} from 'node:test';
import {articleRegion} from './admin/word-source.js';

test('source offsets preserve article shell, English, scripts and non-BMP text', () => {
  const shell = '<!doctype html><html><head><script>"immutable"</script></head><body>😀<section id="proseZh"><p>原稿</p></section><div id="proseEn">English</div><footer>Keep</footer></body></html>';
  const region = articleRegion(shell);
  assert.equal(region.inner, '<p>原稿</p>');
  assert.equal(region.assemble(region.inner), shell);
  assert.equal(region.assemble('<h2>新文字 😀</h2>'), shell.replace('<p>原稿</p>', '<h2>新文字 😀</h2>'));
});
test('ambiguous, incomplete or inert regions fail without a fallback body edit', () => {
  for (const source of ['<body>legacy</body>', '<div id="proseZh">Missing closing tag',
    '<div id="proseZh"></div><section id="proseZh"></section>',
    '<template><div id="proseZh">inert</div></template>', '<p id="proseZh">inline</p>']) {
    assert.throws(() => articleRegion(source));
  }
});
test('UTF-8 byte limit applies to the full assembled article', () => {
  const region = articleRegion('<div id="proseZh">Keep</div>');
  assert.throws(() => region.assemble('中'.repeat(500_001)));
  assert.throws(() => region.assemble(null));
  assert.throws(() => articleRegion('中'.repeat(500_001)));
});
test('explicit legacy article stays bounded to the authored container', () => {
  const source = '<main><nav>Keep</nav><article class="prose prose-lg" data-slug="legacy"><h1>Title</h1><p>Text</p></article><aside>Keep</aside></main>';
  const region = articleRegion(source);
  assert.equal(region.kind, 'legacy-article');
  assert.equal(region.assemble(region.inner), source);
  assert.throws(() => articleRegion(source + source));
  assert.throws(() => articleRegion(source.replace('data-slug="legacy"', 'data-slug="../bad"')));
  assert.throws(() => articleRegion(source.replace('class="prose prose-lg"', 'class="layout"')));
});
