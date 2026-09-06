import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const source = readFileSync(new URL('./admin.html', import.meta.url), 'utf8');
const start = source.indexOf('function generateNewArticleSkeleton(opts){');
const end = source.indexOf('// ───', start);
const context = vm.createContext({});
vm.runInContext(source.slice(start, end), context);
const opts = {slug:'new-article', date:'2026-09-06', title:'A "quote" & <tag>',
  sub:'A subtitle', tag:'Example', desc:'A backslash \\ and </script> in prose'};

for (const type of ['myth','rx','overview','note','research']) {
  test(`article skeleton: ${type}`, () => {
    const html = context.generateNewArticleSkeleton({...opts,type});
    const json = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1];
    const schema = JSON.parse(json);
    assert.equal(schema['@type'], type === 'research' ? 'MedicalScholarlyArticle' : 'MedicalWebPage');
    assert.equal(schema.description, opts.desc);
    assert.equal(schema.headline, opts.title + ' — ' + opts.sub);
    assert.equal((html.match(/id="refs"/g) || []).length, 1);
    assert.ok(html.includes('A &quot;quote&quot; &amp; &lt;tag&gt;'));
    const image = html.match(/property="og:image" content="([^"]+)"/)[1];
    assert.ok(image.endsWith('.png'));
    assert.ok(readFileSync(new URL('.' + new URL(image).pathname, import.meta.url)).length > 0);
    assert.ok(html.includes('name="twitter:image" content="' + image + '"'));
  });
}
test('unsafe slug rejected before constructing markup', () => {
  assert.throws(() => context.generateNewArticleSkeleton({...opts,slug:'../"bad'}));
});
