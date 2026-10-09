"""Regression tests for manual maintenance tools; no image decoder or real writes."""
from contextlib import redirect_stdout
import ast
import html
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisibleEnglishCounterTests(unittest.TestCase):
    def setUp(self):
        self.generator = load_script('_gen_en_pages')

    def test_void_elements_do_not_hide_later_untranslated_text(self):
        for tag in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                    'link', 'meta', 'param', 'source', 'track', 'wbr'):
            for ending in ('>', '/>'):
                with self.subTest(tag=tag, ending=ending):
                    source = '<div data-en="Translated"><' + tag + ending + '</div><p>中文</p>'
                    self.assertEqual(self.generator.visible_cjk_count(source), 2)

    def test_nested_translated_subtree_does_not_hide_following_text(self):
        source = '<div data-en="English"><section><br><span>隱藏</span></section></div><p>中文</p>'
        self.assertEqual(self.generator.visible_cjk_count(source), 2)

    def test_unrelated_end_tag_does_not_release_translated_scope(self):
        source = '<div data-en="English">隱藏</unused>隱藏</div><p>中文</p>'
        self.assertEqual(self.generator.visible_cjk_count(source), 2)

    def test_inert_and_self_closing_scopes_are_balanced(self):
        source = '<script>中文</script><style>中文</style><svg><text>中文</text></svg><svg/><p>中文</p>'
        self.assertEqual(self.generator.visible_cjk_count(source), 2)

    def test_translated_void_attribute_does_not_hide_following_text(self):
        self.assertEqual(self.generator.visible_cjk_count('<img data-en="English"><p>中文</p>'), 2)

    def test_quality_threshold_sees_untranslated_text_after_void(self):
        source = '<div data-en="English"><img></div><p>' + '中' * 501 + '</p>'
        self.assertGreater(self.generator.visible_cjk_count(source), 500)


class SupportSecurityScopeTests(unittest.TestCase):
    def test_split_support_module_keeps_style_and_handler_security_checks(self):
        audit = load_script('_check_frontend_security')
        original_read = audit.read
        support = original_read('blog/blog-support.js')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(), 0)
        mutations = [
            (support.replace('dn-bmc-header-css', 'missing-header-css'), 'hover/focus'),
            (support.replace("a.className = 'dn-bmc-header-link';", ''), 'use a class'),
            (support + '\na.onmouseover = unsafeHandler;', 'mouseover handlers'),
            (support + '\na.onmouseout = unsafeHandler;', 'mouseout handlers'),
        ]
        for source, expected in mutations:
            with self.subTest(expected=expected):
                output = io.StringIO()
                with patch.object(audit, 'read', side_effect=lambda name: source if name == 'blog/blog-support.js' else original_read(name)), redirect_stdout(output):
                    self.assertEqual(audit.main(), 1)
                self.assertIn('blog/blog-support.js:', output.getvalue())
                self.assertIn(expected, output.getvalue())


class AutomaticHTMLScopeTests(unittest.TestCase):
    def setUp(self):
        self.css=load_script('_normalize_css_links')
        self.schema=load_script('_normalize_schema')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def write(self,name,body):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(body,encoding='utf8');return p

    def test_css_batch_leaves_private_generated_nested_and_backup_html_bytes_intact(self):
        body='<head><script src="/assets/inline/nonmedical-ui.js?v=1"></script></head>'
        public=['index.html','blog/new.html','admin/edit.html','en/index.html','en/blog/new.html']
        excluded=['.codex-review/evidence.html','node_modules/package/page.html','pagefind/page.html',
                  'backups/previous.html','blog/backup/previous.html','en/blog/backup/previous.html',
                  '.venv/lib/page.html','fixtures/previous.html','assets/example.html']
        for name in public+excluded:self.write(name,body)
        originals={n:(self.root/n).read_bytes() for n in excluded}
        with patch.object(self.css,'ROOT',str(self.root)),redirect_stdout(io.StringIO()):
            self.css.main()
            self.assertEqual({Path(p).relative_to(self.root).as_posix() for p in self.css.html_files()},set(public))
            once={n:(self.root/n).read_bytes() for n in public}
            self.css.main()
        self.assertEqual({n:(self.root/n).read_bytes() for n in excluded},originals)
        self.assertTrue(all(b'v=1"' not in value for value in once.values()))
        self.assertEqual({n:(self.root/n).read_bytes() for n in public},once)

    def test_schema_identity_only_rewrite_is_persisted_and_then_idempotent(self):
        for legacy in (self.schema.DOMAIN + '/#person', self.schema.DOMAIN + '/about#person'):
            with self.subTest(legacy=legacy):
                # No article or JSON-LD normalization can cause an incidental
                # write: the physician reference is the only difference.
                before = '<head></head><body><a href="' + legacy + '">Nonmedical author reference</a></body>'
                page = self.write('index.html', before)
                self.assertTrue(self.schema.normalize_file(page))
                expected = before.replace(legacy, self.schema.PHYSICIAN_ID)
                self.assertEqual(page.read_text(encoding='utf8'), expected)
                once = page.read_bytes()
                self.assertFalse(self.schema.normalize_file(page))
                self.assertEqual(page.read_bytes(), once)

    def test_schema_batch_respects_include_en_and_existing_utility_exclusions(self):
        body='<head><title>Nonmedical UI fixture</title><script type="application/ld+json">{"@type":"MedicalWebPage","name":"Old fixture"}</script></head>'
        public=['index.html','blog/new.html','admin/edit.html']
        english=['en/index.html','en/blog/new.html']
        excluded=['404.html','offline.html','admin.html','reset-sw.html','en/reset-sw.html',
                  '.codex-review/evidence.html','blog/backup/previous.html','fixtures/previous.html',
                  '.git/private.html','node_modules/page.html','pagefind/page.html']
        for name in public+english+excluded:self.write(name,body)
        originals={n:(self.root/n).read_bytes() for n in english+excluded}
        with patch.object(self.schema,'ROOT',self.root),patch.object(sys,'argv',['_normalize_schema.py']),redirect_stdout(io.StringIO()):
            self.schema.main()
        self.assertEqual({n:(self.root/n).read_bytes() for n in english+excluded},originals)
        self.assertTrue(all((self.root/n).read_bytes()!=body.encode() for n in public))
        with patch.object(self.schema,'ROOT',self.root),patch.object(sys,'argv',['_normalize_schema.py','--include-en']),redirect_stdout(io.StringIO()):
            self.schema.main()
            once={n:(self.root/n).read_bytes() for n in public+english}
            self.schema.main()
        self.assertTrue(all((self.root/n).read_bytes()!=body.encode() for n in english))
        self.assertEqual({n:(self.root/n).read_bytes() for n in excluded},{n:originals[n] for n in excluded})
        self.assertEqual({n:(self.root/n).read_bytes() for n in public+english},once)

    def test_schema_batch_accepts_a_lexical_root_with_parent_segments(self):
        (self.root / 'alias').mkdir()
        body = '<head><script type="application/ld+json">{"@type":"MedicalWebPage","name":"Old fixture"}</script></head>'
        page = self.write('index.html', body)
        with patch.object(self.schema, 'ROOT', self.root / 'alias' / '..'), \
                patch.object(sys, 'argv', ['_normalize_schema.py']), redirect_stdout(io.StringIO()):
            self.schema.main()
        self.assertNotEqual(page.read_text(encoding='utf8'), body)

    def test_both_batch_writers_preflight_all_html_before_linked_source_failure(self):
        from _site_html import site_html_files
        css_body='<head><script src="/assets/inline/nonmedical-ui.js?v=1"></script></head>'
        schema_body='<head><script type="application/ld+json">{"@type":"MedicalWebPage","name":"Old nonmedical fixture"}</script></head>'
        for script,body,root_value in [(self.css,css_body,str(self.root)),(self.schema,schema_body,self.root)]:
            for kind in ['file','directory']:
                with self.subTest(writer=script.__name__,kind=kind):
                    first=self.write('index.html',body)
                    linked=self.write('blog/zz.html',body)
                    blocked=linked if kind=='file' else linked.parent
                    with patch('_site_html._linked',side_effect=lambda p:p==blocked),patch.object(script,'ROOT',root_value),patch.object(sys,'argv',[script.__name__]),redirect_stdout(io.StringIO()):
                        with self.assertRaisesRegex(ValueError,'[Ll]inked|ordinary file'):
                            script.main()
                    self.assertEqual(first.read_bytes(),body.encode())
                    self.assertEqual(linked.read_bytes(),body.encode())
        self.assertEqual(site_html_files(self.root),sorted(site_html_files(self.root),key=lambda p:p.relative_to(self.root).as_posix()))

    def test_shared_inventory_handles_optional_en_and_rejects_nonfile_html(self):
        from _site_html import site_html_files
        self.write('blog/new.html','Nonmedical UI')
        self.write('en/blog/new.html','Nonmedical UI')
        self.assertEqual([p.relative_to(self.root).as_posix() for p in site_html_files(self.root,include_en=False)],['blog/new.html'])
        self.assertEqual([p.relative_to(self.root).as_posix() for p in site_html_files(self.root)],['blog/new.html','en/blog/new.html'])
        (self.root/'blog/not-a-file.html').mkdir()
        with self.assertRaisesRegex(ValueError,'ordinary file'):
            site_html_files(self.root)
        with self.assertRaisesRegex(ValueError,'not a directory'):
            site_html_files(self.root/'blog/new.html')

    def test_junction_detector_and_all_tracked_deployed_html_coverage(self):
        from _site_html import _linked,site_html_files
        p=self.write('blog/new.html','Nonmedical UI')
        with patch.object(Path,'is_junction',return_value=True,create=True):
            self.assertTrue(_linked(p))
        tracked=set(subprocess.check_output(['git','ls-files','*.html'],cwd=ROOT).decode('utf8').splitlines())
        seen={p.relative_to(ROOT).as_posix() for p in site_html_files(ROOT)}
        self.assertTrue(tracked)
        self.assertEqual(seen,tracked)

    def test_minifier_never_rewrites_private_or_nested_backup_documents(self):
        # Run the actual CLI in a fixture checkout, including its stdout setup.
        for name in ['_minify.py', '_site_html.py']:
            (self.root/name).write_bytes((ROOT/name).read_bytes())
        body='<!doctype html>\n<html>\n'+('    <!-- Nonmedical fixture spacing -->\n    <p>Visible UI</p>\n'*30)+'</html>\n'
        public=['index.html','blog/new.html','admin/edit.html','en/index.html','en/blog/new.html']
        excluded=['.codex-review/evidence.html','backups/previous.html','blog/backup/previous.html',
                  'node_modules/package/page.html','pagefind/page.html','fixtures/previous.html']
        for name in public+excluded:self.write(name,body)
        originals={n:(self.root/n).read_bytes() for n in excluded}
        run=subprocess.run([sys.executable,str(self.root/'_minify.py')],cwd=self.root,capture_output=True)
        self.assertEqual(run.returncode,0,run.stdout.decode('utf8',errors='replace')+run.stderr.decode('utf8',errors='replace'))
        self.assertTrue(all((self.root/n).read_bytes()!=body.encode() for n in public))
        self.assertEqual({n:(self.root/n).read_bytes() for n in excluded},originals)

    def test_print_extraction_never_uses_private_rules_or_rewrites_private_documents(self):
        script=load_script('_normalize_critical_css')
        body='<head><style>@media print { body { color:black } }</style></head>'
        private='<head><style>@media print { body { color:hotpink } }</style></head>'
        public=['index.html','blog/new.html','en/index.html','en/blog/new.html']
        excluded=['.codex-review/evidence.html','backups/previous.html','blog/backup/previous.html',
                  'fixtures/previous.html','node_modules/page.html','admin/edit.html','404.html']
        for name in public:self.write(name,body)
        for name in excluded:self.write(name,private)
        with patch.object(script,'ROOT',self.root),patch.object(script,'PRINT_CSS_PATH',self.root/'assets/dn-print.css'),patch.object(script,'BELOW_FOLD_CSS_PATH',self.root/'assets/dn-below-fold.css'),redirect_stdout(io.StringIO()):
            self.assertEqual(script.main(),0)
        self.assertTrue(all((self.root/n).read_bytes()!=body.encode() for n in public))
        self.assertEqual({n:(self.root/n).read_bytes() for n in excluded},{n:private.encode() for n in excluded})
        css=(self.root/'assets/dn-print.css').read_text(encoding='utf8')
        self.assertIn('color:black',css)
        self.assertNotIn('hotpink',css)

    def test_performance_discovery_covers_all_source_roots_without_private_output(self):
        script=load_script('_check_performance_budget')
        public=['index.html','blog/new.html','admin/edit.html','en/index.html','en/blog/new.html']
        excluded=['.codex-review/evidence.html','blog/backups/new.html','node_modules/page.html','pagefind/page.html']
        for name in public+excluded:self.write(name,'Nonmedical UI')
        with patch.object(script,'ROOT',self.root):
            self.assertEqual({p.relative_to(self.root).as_posix() for p in script.iter_html_files()},set(public))

    def test_head_extras_version_update_preserves_tag_position_and_is_idempotent(self):
        script=load_script('_normalize_head_extras')
        old=script.VITALS_TAG.replace('?v='+script._ASSET_VERSION,'?v=1')
        before='<head>'+script.SEARCH_LINK+old+'<style id="nonmedical-fixture">p{color:black}</style><meta name="x" content="y"></head><body>Nonmedical UI</body>'
        page=self.write('index.html',before)
        self.assertTrue(script.inject_one(page))
        self.assertEqual(page.read_text(encoding='utf8'),before.replace(old,script.VITALS_TAG))
        self.assertFalse(script.inject_one(page))

    def test_head_extras_batch_preserves_private_html_and_existing_utility_exclusions(self):
        script=load_script('_normalize_head_extras')
        body='<head></head><body>Nonmedical UI</body>'
        public=['index.html','blog/new.html','en/index.html','en/blog/new.html']
        excluded=['.codex-review/evidence.html','blog/backups/new.html','node_modules/page.html','pagefind/page.html','admin/edit.html','404.html']
        for name in public+excluded:self.write(name,body)
        with patch.object(script,'ROOT',self.root),redirect_stdout(io.StringIO()):
            self.assertEqual(script.main(),0)
        self.assertTrue(all((self.root/n).read_text(encoding='utf8')!=body for n in public))
        self.assertTrue(all((self.root/n).read_text(encoding='utf8')==body for n in excluded))


class AnalyticsMaintenanceScopeTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_normalize_analytics')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def run_apply(self):
        with patch.object(self.script, 'HERE', str(self.root)), patch.object(self.script, 'APPLY', True), redirect_stdout(io.StringIO()):
            self.script.main()

    def test_only_deployed_sources_change_and_utility_pages_remain_uninstrumented(self):
        body = b'<head></head><body>Nonmedical fixture</body>'
        public = ['index.html', 'blog/article.html', 'en/index.html', 'en/blog/article.html']
        excluded = ['.codex-review/evidence.html', 'backups/old.html', 'fixtures/paste.html',
                    'blog/backup/old.html', 'assets/private.html', 'node_modules/page.html', 'pagefind/page.html']
        utilities = ['admin.html', 'admin/edit.html', 'admin/new-private-tool.html',
                     'reset-sw.html', 'en/reset-sw.html', 'offline.html', 'en/admin.html', 'en/offline.html']
        for name in public + excluded + utilities:
            self.write(name, body)
        self.run_apply()
        self.assertTrue(all(b'analytics-loader.js' in (self.root / name).read_bytes() for name in public))
        self.assertEqual({name: (self.root / name).read_bytes() for name in excluded + utilities},
                         {name: body for name in excluded + utilities})
        once = {name: (self.root / name).read_bytes() for name in public}
        self.run_apply()
        self.assertEqual({name: (self.root / name).read_bytes() for name in public}, once)

    def test_invalid_utf8_aborts_before_rewriting_an_earlier_source(self):
        first = self.write('blog/first.html', b'<head></head>Nonmedical valid fixture')
        invalid = self.write('en/index.html', b'<head></head>Nonmedical invalid \xff fixture')
        originals = [first.read_bytes(), invalid.read_bytes()]
        with self.assertRaises(UnicodeDecodeError):
            self.run_apply()
        self.assertEqual([first.read_bytes(), invalid.read_bytes()], originals)

    def test_optional_private_utilities_strip_existing_current_and_legacy_loaders(self):
        body = ('<head>' + self.script.KEEPER + self.script.LEGACY_TAGS[0] +
                '<script>gtag("config", "G-XFF3L5QD10");</script></head><body>Private fixture</body>').encode()
        utilities = ['en/admin.html', 'en/offline.html', 'admin/new-private-tool.html']
        for name in utilities:
            self.write(name, body)
        self.run_apply()
        expected = b'<head></head><body>Private fixture</body>'
        self.assertEqual({name: (self.root / name).read_bytes() for name in utilities},
                         {name: expected for name in utilities})
        self.run_apply()
        self.assertEqual({name: (self.root / name).read_bytes() for name in utilities},
                         {name: expected for name in utilities})

    def test_linked_source_aborts_before_any_source_or_target_write(self):
        first = self.write('index.html', b'<head></head>Nonmedical fixture')
        target = self.write('fixtures/original.html', b'<head></head>Protected fixture')
        linked = self.root / 'blog/linked.html'
        linked.parent.mkdir()
        try:
            linked.symlink_to(target)
        except OSError as exc:
            self.skipTest(f'Filesystem does not permit symlinks: {exc}')
        originals = [first.read_bytes(), target.read_bytes()]
        with self.assertRaisesRegex(ValueError, 'ordinary file'):
            self.run_apply()
        self.assertEqual([first.read_bytes(), target.read_bytes()], originals)


    def test_versioned_bootstrap_attribute_ga_and_clarity_are_removed(self):
        snippets = [
            '<script defer src="/assets/inline/gtag-bootstrap.js?v=old"></script>',
            '<script type="text/javascript">gtag("config", "G-XFF3L5QD10");</script>',
            '<script async src="https://www.clarity.ms/tag/fixture-id"></script>',
            '<script>(function(c,l){var t=l.createElement("script");t.src="https://www.clarity.ms/tag/fixture-id";})(window,document);</script>',
        ]
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                src = '<head>' + snippet + '</head><main>Untouched</main>'
                cleaned, _, _ = self.script.normalize(src)
                self.assertEqual(cleaned, '<head></head><main>Untouched</main>')
                self.assertEqual(self.script.normalize(cleaned)[0], cleaned)

    def test_inert_json_comments_and_nontracking_scripts_stay_exact(self):
        snippets = [
            '<!-- <script>gtag("config", "G-XFF3L5QD10");</script> -->',
            '<script type="application/ld+json">{"name":"G-XFF3L5QD10","note":"clarity.ms/tag/"}</script>',
            '<script>window.fixture = "G-XFF3L5QD10";</script>',
            '<script src="/assets/inline/other.js?v=old"></script>',
        ]
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                self.assertEqual(self.script.normalize(snippet)[0], snippet)

    def test_malformed_later_script_aborts_before_any_write(self):
        first = self.write('blog/first.html', b'<head></head><main>First</main>')
        later = self.write('en/index.html', b'<head><script>gtag("config", "G-XFF3L5QD10");')
        originals = [first.read_bytes(), later.read_bytes()]
        with self.assertRaisesRegex(ValueError, 'Unclosed script'):
            self.run_apply()
        self.assertEqual([first.read_bytes(), later.read_bytes()], originals)


    def test_actual_loaders_ignore_commented_examples_when_deduplicating(self):
        example = '<!-- ' + self.script.KEEPER + ' -->'
        inert = '<script type="application/json" src="/assets/inline/analytics-loader.js?v=example"></script>'
        index = self.write('index.html', ('<head>' + example + inert + '</head>').encode())
        private = self.write('offline.html', ('<head>' + example + self.script.KEEPER + '</head>').encode())
        self.run_apply()
        self.assertEqual(index.read_text(), '<head>' + example + inert + self.script.KEEPER + '</head>')
        self.assertEqual(private.read_text(), '<head>' + example + '</head>')
        once = [index.read_bytes(), private.read_bytes()]
        self.run_apply()
        self.assertEqual([index.read_bytes(), private.read_bytes()], once)

    def test_self_closing_later_script_aborts_before_any_write(self):
        first = self.write('index.html', b'<head></head>First')
        later = self.write('en/index.html', b'<head><script src="/assets/inline/gtag-bootstrap.js" /></head>')
        originals = [first.read_bytes(), later.read_bytes()]
        with self.assertRaisesRegex(ValueError, 'Self-closing script'):
            self.run_apply()
        self.assertEqual([first.read_bytes(), later.read_bytes()], originals)


    def test_nested_inert_containers_keep_script_examples_exact(self):
        for wrapper in ['template', 'noscript']:
            snippet = ('<' + wrapper + '><template><script src="/assets/inline/gtag-bootstrap.js?v=example"></script>'
                       '<script>gtag("config", "G-XFF3L5QD10");</script></template></' + wrapper + '>')
            with self.subTest(wrapper=wrapper):
                self.assertEqual(self.script.normalize(snippet)[0], snippet)


class CacheStampMaintenanceScopeTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_bump_v')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def run_apply(self, stamp='202610040250'):
        with patch.object(self.script, 'ROOT', self.root), redirect_stdout(io.StringIO()):
            return self.script.main([stamp])

    def test_visible_exports_and_backups_remain_unchanged_and_newlines_survive(self):
        raw = b'<head>\r\n<script src="/ui.js?v=202609010000"></script></head>\r\n'
        public = ['index.html', 'blog/article.html', 'admin/edit.html', 'en/index.html', 'en/blog/article.html']
        excluded = ['exports/author-draft.html', 'backups/site-copy.html', 'blog/backups/old.html',
                    'en/blog/backups/old.html', '.codex-review/evidence.html', 'pagefind/private.html',
                    'node_modules/private.html', 'fixtures/paste.html']
        for name in public + excluded:
            self.write(name, raw)
        self.assertEqual(self.run_apply(), 0)
        expected = raw.replace(b'202609010000', b'202610040250')
        self.assertEqual({name: (self.root / name).read_bytes() for name in public},
                         {name: expected for name in public})
        self.assertEqual({name: (self.root / name).read_bytes() for name in excluded},
                         {name: raw for name in excluded})
        with patch.object(Path, 'write_bytes', side_effect=AssertionError('Unchanged source was rewritten')):
            self.assertEqual(self.run_apply(), 0)

    def test_invalid_later_source_aborts_before_any_write(self):
        first = self.write('index.html', b'<script src="/ui.js?v=202609010000"></script>')
        last = self.write('en/index.html', b'Invalid \xff fixture')
        originals = [first.read_bytes(), last.read_bytes()]
        with self.assertRaises(UnicodeDecodeError):
            self.run_apply()
        self.assertEqual([first.read_bytes(), last.read_bytes()], originals)

    def test_linked_source_roots_and_files_abort_before_any_write(self):
        first = self.write('index.html', b'<script src="/ui.js?v=202609010000"></script>')
        last = self.write('en/blog/last.html', b'<script src="/ui.js?v=202609010000"></script>')
        originals = [first.read_bytes(), last.read_bytes()]
        for blocked in [last, last.parent]:
            with self.subTest(blocked=blocked), patch('_site_html._linked', side_effect=lambda p: p == blocked):
                with self.assertRaisesRegex(ValueError, '[Ll]inked|ordinary file'):
                    self.run_apply()
            self.assertEqual([first.read_bytes(), last.read_bytes()], originals)

    def test_invalid_stamp_cannot_inject_into_or_rewrite_html(self):
        first = self.write('index.html', b'<script src="/ui.js?v=202609010000"></script>')
        for stamp in ['x', '12345', '1' * 15, '202610040250"><script>', '１２３４５６']:
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ValueError, 'ASCII digits'):
                self.run_apply(stamp)
        self.assertEqual(first.read_bytes(), b'<script src="/ui.js?v=202609010000"></script>')

    def test_private_invalid_utf8_is_never_read(self):
        public = self.write('index.html', b'<script src="/ui.js?v=202609010000"></script>')
        private = self.write('exports/author-draft.html', b'Protected \xff fixture')
        self.assertEqual(self.run_apply(), 0)
        self.assertIn(b'202610040250', public.read_bytes())
        self.assertEqual(private.read_bytes(), b'Protected \xff fixture')


class SpeedInsightsMaintenanceScopeTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_apply_vercel_insights')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path

    def run_apply(self):
        with patch.object(self.script, 'ROOT', self.root), redirect_stdout(io.StringIO()):
            return self.script.main()

    def test_deployed_content_only_and_repeat_preserves_bytes(self):
        body = b'<head>\r\n</head><body>Nonmedical fixture</body>\r\n'
        public = ['index.html', 'blog/article.html', 'en/index.html', 'en/blog/article.html', '404.html']
        excluded = ['.codex-review/evidence.html', 'backups/old.html', 'blog/backups/old.html',
                    'fixtures/paste.html', 'assets/private.html', 'node_modules/page.html', 'pagefind/page.html',
                    'admin.html', 'admin/edit.html', 'admin/cms.html', 'reset-sw.html', 'offline.html',
                    'en/admin.html', 'en/offline.html', 'en/reset-sw.html']
        for name in public + excluded:
            self.write(name, body)
        self.assertEqual(self.run_apply(), 0)
        expected = body.replace(b'</head>', self.script.TAG.encode() + b'</head>', 1)
        self.assertEqual({name: (self.root / name).read_bytes() for name in public},
                         {name: expected for name in public})
        self.assertEqual({name: (self.root / name).read_bytes() for name in excluded},
                         {name: body for name in excluded})
        self.assertEqual(self.run_apply(), 0)
        self.assertEqual({name: (self.root / name).read_bytes() for name in public},
                         {name: expected for name in public})

    def test_invalid_later_source_aborts_before_any_write(self):
        first = self.write('blog/first.html', b'<head></head>Valid nonmedical fixture')
        invalid = self.write('en/index.html', b'<head></head>Invalid \xff fixture')
        originals = [first.read_bytes(), invalid.read_bytes()]
        with self.assertRaises(UnicodeDecodeError):
            self.run_apply()
        self.assertEqual([first.read_bytes(), invalid.read_bytes()], originals)

    def test_linked_file_and_directory_abort_before_any_write(self):
        first = self.write('index.html', b'<head></head>Nonmedical fixture')
        linked = self.write('blog/zz.html', b'<head></head>Protected fixture')
        originals = [first.read_bytes(), linked.read_bytes()]
        for blocked in (linked, linked.parent):
            with self.subTest(blocked=blocked), patch('_site_html._linked', side_effect=lambda p: p == blocked):
                with self.assertRaisesRegex(ValueError, '[Ll]inked|ordinary file'):
                    self.run_apply()
            self.assertEqual([first.read_bytes(), linked.read_bytes()], originals)

    def test_private_invalid_utf8_is_never_read(self):
        public = self.write('index.html', b'<head></head>Nonmedical fixture')
        private = self.write('.codex-review/evidence.html', b'Protected \xff fixture')
        self.assertEqual(self.run_apply(), 0)
        self.assertIn(self.script.TAG.encode(), public.read_bytes())
        self.assertEqual(private.read_bytes(), b'Protected \xff fixture')

    def test_existing_script_and_headless_content_remain_unchanged(self):
        existing = self.write('index.html', b'<head>' + self.script.TAG.encode() + b'</head>')
        headless = self.write('blog/headless.html', b'<body>Nonmedical fragment</body>')
        originals = [existing.read_bytes(), headless.read_bytes()]
        self.assertEqual(self.run_apply(), 0)
        self.assertEqual([existing.read_bytes(), headless.read_bytes()], originals)


class MaintenanceImportTests(unittest.TestCase):
    def test_import_does_not_touch_navigation_stdout_or_load_codecs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            originals = {}
            for name in ('_clean_dead_slugs', '_convert_images', '_dump_aria', '_wrap_citations', '_html_scan',
                         '_apply_vercel_insights', '_site_html', '_bump_v'):
                (root / f'{name}.py').write_bytes((ROOT / f'{name}.py').read_bytes())
            for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                originals[name] = b'<li><a href="/blog/eczema-myths">Keep on import</a></li>'
                path.write_bytes(originals[name])
            # A fresh interpreter verifies imports even when codecs are unavailable.
            command = """
import importlib.abc, sys
class NoCodecs(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'PIL', 'pillow_avif'}:
            raise AssertionError('Codec imported during helper import')
sys.meta_path.insert(0, NoCodecs())
original = sys.stdout
import _clean_dead_slugs, _convert_images, _dump_aria, _wrap_citations, _apply_vercel_insights, _bump_v
assert sys.stdout is original
print('import-safe')
"""
            run = subprocess.run([sys.executable, '-c', command], cwd=root,
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), 'import-safe')
            self.assertEqual({n: (root / n).read_bytes() for n in originals}, originals)


class SVGLabelExtractionTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_dump_aria')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.page = self.root / 'fixture.html'

    def labels(self, source):
        self.page.write_text(source, encoding='utf8')
        with patch.object(self.script, 'ROOT', self.root):
            return self.script.extract_zh_arias('fixture.html')

    def test_quoted_greater_than_single_quotes_and_entities_do_not_lose_labels(self):
        source = '<SVG data-note="1 > 0" aria-label=\'甲 &amp; 乙\'></SVG><svg aria-label="丙"></svg>'
        self.assertEqual(self.labels(source), ['甲 & 乙', '丙'])

    def test_non_svg_and_inert_examples_do_not_shift_translation_order(self):
        source = '<button aria-label="導航"></button><!-- <svg aria-label="註解"></svg> -->'
        for tag in ('script', 'style', 'template', 'noscript', 'textarea', 'title'):
            source += f'<{tag}><svg aria-label="範例"></svg></{tag}>'
        source += '<svg aria-label="實際圖"></svg><svg aria-label="English only"/>'
        self.assertEqual(self.labels(source), ['實際圖'])

    def test_translation_count_mismatch_fails_before_appending_output(self):
        self.labels('<svg aria-label="甲"></svg><svg aria-label="乙"></svg>')
        for translations in ([], ['One'], ['One', 'Two', 'Three']):
            with self.subTest(translations=translations), patch.object(self.script, 'ROOT', self.root):
                lines = ['Previous output']
                with self.assertRaisesRegex(ValueError, 'fixture.html'):
                    self.script.dump('fixture.html', translations, lines)
                self.assertEqual(lines, ['Previous output'])

    def test_matching_labels_preserve_exact_order_and_escape_quotes(self):
        self.labels('<svg aria-label="甲 &quot;引文&quot;"></svg><svg aria-label="乙"></svg>')
        lines = []
        with patch.object(self.script, 'ROOT', self.root):
            self.script.dump('fixture.html', ['First "quote"', 'Second'], lines)
        self.assertEqual(len(lines), 5)
        self.assertIn('甲 ' + chr(92) + '"引文' + chr(92) + '"', lines[1])
        self.assertIn('First ' + chr(92) + '"quote' + chr(92) + '"', lines[2])
        self.assertIn('Second', lines[4])


class CitationWrappingTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_wrap_citations')

    def test_only_visible_text_changes_preserving_attributes_and_surrounding_bytes(self):
        source = '<p title="(Hill 2014)" data-zh="(Hill 2014)" data-en="(Hill 2014)">\n原文 (Hill 2014) 結尾 &amp;\n</p>'
        expected = source.replace('原文 (Hill 2014)', '原文 (<span class="cite">Hill 2014</span>)')
        result, count = self.script.wrap(source)
        self.assertEqual((result, count), (expected, 1))
        self.assertEqual(self.script.wrap(result), (result, 0))

    def test_inert_foreign_preformatted_and_existing_citations_are_preserved(self):
        for tag in ('script', 'style', 'template', 'noscript', 'textarea', 'title', 'pre', 'code', 'kbd', 'svg', 'math'):
            source = f'<{tag}>(Hill 2014)</{tag}>'
            with self.subTest(tag=tag):
                self.assertEqual(self.script.wrap(source), (source, 0))
        for source in ('<!-- (Hill 2014) -->', '<span class="cite other">(Hill 2014)</span>'):
            with self.subTest(source=source):
                self.assertEqual(self.script.wrap(source), (source, 0))

    def test_visible_citation_after_skipped_block_is_wrapped_and_rate_like_numbers_ignored(self):
        source = '<template><p>(Hill 2014)</p></template><p>(Hill 2014) (Fraxel 1550) (Hill 2044)</p>'
        expected = '<template><p>(Hill 2014)</p></template><p>(<span class="cite">Hill 2014</span>) (Fraxel 1550) (Hill 2044)</p>'
        self.assertEqual(self.script.wrap(source), (expected, 1))

    def test_raw_text_fake_tags_cannot_corrupt_following_real_text(self):
        for tag in ('textarea', 'title'):
            source = f'<div><{tag}><script></div>(Hill 2014)</{tag}><p>(Hill 2014)</p></div>'
            expected = source.replace('<p>(Hill 2014)</p>', '<p>(<span class="cite">Hill 2014</span>)</p>')
            with self.subTest(tag=tag):
                self.assertEqual(self.script.wrap(source), (expected, 1))

    def test_manual_main_targets_script_root_and_rerun_does_not_write_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / 'blog/fixture.html'
            page.parent.mkdir()
            page.write_text('<p>(Hill 2014)</p>', encoding='utf8')
            with patch.object(self.script, 'ROOT', root), redirect_stdout(io.StringIO()):
                self.script.main()
                once = page.read_bytes()
                self.script.main()
            self.assertEqual(page.read_bytes(), once)
            self.assertEqual(once, b'<p>(<span class="cite">Hill 2014</span>)</p>')


class SVGTranslationConsumerTests(unittest.TestCase):
    def test_extracted_entity_label_works_with_real_generator_lookup_and_legacy_keys(self):
        # Execute the actual pure consumer function without importing the whole
        # generator or its stdout configuration. Use nonmedical UI fixture text.
        tree = ast.parse((ROOT / '_gen_en_pages.py').read_text(encoding='utf8'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'translate_aria_labels']
        self.assertEqual(len(functions), 1)
        import re
        context = {'re': re, 'html_lib': html, 'ARIA_LABEL_TRANSLATIONS': {}}
        exec(compile(ast.Module(body=functions, type_ignores=[]), '_gen_en_pages.py', 'exec'), context)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = '<svg aria-label="卡片 &amp; 排版" data-note="原屬性"></svg>'
            (root / 'fixture.html').write_text(source, encoding='utf8')
            helper = load_script('_dump_aria')
            with patch.object(helper, 'ROOT', root):
                labels = helper.extract_zh_arias('fixture.html')
            context['ARIA_LABEL_TRANSLATIONS'][labels[0]] = 'Card & layout'
            expected = source.replace('卡片 &amp; 排版', 'Card &amp; layout')
            self.assertEqual(context['translate_aria_labels'](source), expected)
            # Existing raw-entity dictionary keys remain preferred and supported.
            context['ARIA_LABEL_TRANSLATIONS']['卡片 &amp; 排版'] = 'Legacy card'
            self.assertEqual(context['translate_aria_labels'](source), source.replace('卡片 &amp; 排版', 'Legacy card'))


class DeletedNavigationTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_clean_dead_slugs')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_existing_chinese_or_english_source_preserves_links(self):
        slugs = ('atopic-dermatitis-topical', 'atopic-dermatitis-systemic')
        for prefix, slug in zip(('blog', 'en/blog'), slugs):
            source = self.root / prefix / f'{slug}.html'
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('Article exists', encoding='utf8')
        for prefix in ('/blog/', '/en/blog/'):
            for slug in slugs:
                for markup in (f'<a href="{prefix}{slug}" class="article-list-item"><h2>保留</h2></a>',
                               f'<li><a href="{prefix}{slug}">保留</a></li>'):
                    with self.subTest(prefix=prefix, slug=slug, markup=markup):
                        navigation = self.root / 'fixture.html'
                        navigation.write_text(markup, encoding='utf8')
                        self.assertFalse(self.script.clean(navigation, self.root))
                        self.assertEqual(navigation.read_text(encoding='utf8'), markup)

    def test_missing_candidate_removed_idempotently_and_other_links_preserved(self):
        original = ('<main><a href="/blog/eczema-myths" class="article-list-item">Deleted</a>'
                    '<li><a href="/en/blog/atopic-dermatitis-comorbidity">Deleted</a></li>'
                    '<a href="/blog/other" class="article-list-item">保留</a></main>')
        navigation = self.root / 'fixture.html'
        navigation.write_text(original, encoding='utf8')
        self.assertTrue(self.script.clean(navigation, self.root))
        expected = '<main><a href="/blog/other" class="article-list-item">保留</a></main>'
        self.assertEqual(navigation.read_text(encoding='utf8'), expected)
        self.assertFalse(self.script.clean(navigation, self.root))

    def test_main_targets_script_root_independent_of_working_directory(self):
        live = self.root / 'blog/atopic-dermatitis-topical.html'
        live.parent.mkdir(parents=True)
        live.write_text('Existing source', encoding='utf8')
        keep = '<li><a href="/blog/atopic-dermatitis-topical">Keep</a></li>'
        for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('<li><a href="/blog/eczema-myths">Deleted</a></li>' + keep, encoding='utf8')
        with patch.object(self.script, 'ROOT', self.root), redirect_stdout(io.StringIO()):
            # main() uses ROOT for both paths and existence checks.
            self.script.main()
        self.assertTrue(all((self.root / name).read_text(encoding='utf8') == keep
                            for name in ('blog/index.html', 'blog/topics.html', 'en/blog/index.html', 'en/blog/topics.html')))


class PictureRewriteTests(unittest.TestCase):
    def setUp(self):
        self.script = load_script('_convert_images')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'assets/photo.jpg'
        self.source.parent.mkdir()
        self.source.write_bytes(b'file-existence fixture; not an image')
        self.source.with_suffix('.webp').write_bytes(b'file-existence fixture')
        self.page = self.root / 'blog/article.html'
        self.page.parent.mkdir()

    def rewrite(self, value, images=None):
        with patch.object(self.script, 'ROOT', str(self.root)):
            return self.script.rewrite_html_imgs(value, {self.source} if images is None else images, self.page)

    def test_original_tag_and_surrounding_text_preserved_on_first_and_second_pass(self):
        image = '<IMG alt="臨床圖 > 說明" src=\'/assets/photo.jpg\' width="20" loading="lazy" />'
        original = f'<main>原文\n{image}\n<img src="/assets/photo.jpg" alt="二">結尾</main>'
        once = self.rewrite(original)
        self.assertEqual(once.count('<picture>'), 2)
        self.assertEqual(once.count(image), 1)
        self.assertEqual(once.replace('<picture><source srcset="/assets/photo.webp" type="image/webp">', '').replace('</picture>', ''), original)
        self.assertEqual(self.rewrite(once), once)

    def test_existing_picture_and_inert_or_foreign_markup_unchanged(self):
        image = '<img src="/assets/photo.jpg">'
        fixtures = [f'<{tag}>{image}</{tag}>' for tag in
                    ('picture', 'script', 'style', 'template', 'noscript', 'textarea', 'title', 'svg', 'math')]
        fixtures += [f'<!-- {image} -->', f'<picture><source srcset="custom.webp">{image}</picture>']
        for original in fixtures:
            with self.subTest(original=original):
                self.assertEqual(self.rewrite(original), original)
                # A separate eligible image following the excluded block still wraps.
                after = self.rewrite(original + image)
                self.assertTrue(after.startswith(original))
                self.assertEqual(after[len(original):].count('<picture>'), 1)

    def test_opt_out_and_responsive_choices_preserved(self):
        for attrs in ('data-no-picture', 'data-no-picture="false"', 'srcset="custom.webp 2x"', 'sizes="100vw"', 'src="/assets/other.jpg"'):
            original = f'<img src="/assets/photo.jpg" {attrs}>'
            with self.subTest(attrs=attrs):
                self.assertEqual(self.rewrite(original), original)

    def test_only_local_listed_images_with_existing_siblings_wrap(self):
        for src in ('https://example.com/assets/photo.jpg', '//example.com/assets/photo.jpg',
                    '../../photo.jpg', '/assets/photo.svg', '/assets/missing.jpg', '/assets\\photo.jpg',
                    '/assets/ph%00oto.jpg', '/assets/%5cphoto.jpg', '/assets/photo%2Ejpg'):
            original = f'<img src="{src}">'
            with self.subTest(src=src):
                self.assertEqual(self.rewrite(original), original)
        original = '<img src="/assets/photo.jpg">'
        self.assertEqual(self.rewrite(original, set()), original)
        self.source.with_suffix('.webp').unlink()
        self.assertEqual(self.rewrite(original), original)

    def test_relative_path_avif_precedence_and_escaped_query_preserved(self):
        self.source.with_suffix('.avif').write_bytes(b'file-existence fixture')
        original = '<img src="../assets/photo.jpg?v=1&amp;x=2#figure" alt="Original">'
        result = self.rewrite(original)
        self.assertEqual(result, '<picture><source srcset="../assets/photo.avif?v=1&amp;x=2#figure" type="image/avif"><source srcset="../assets/photo.webp?v=1&amp;x=2#figure" type="image/webp">' + original + '</picture>')

    def test_image_discovery_excludes_private_and_generated_directories(self):
        for name in ('.codex-review', 'node_modules', '.git', 'en', 'pagefind', '.claude-review',
                     '.lighthouseci', 'delivery-preview', 'backups', 'exports', 'fixtures', '.venv'):
            directory = self.root / name / 'nested'
            directory.mkdir(parents=True)
            (directory / 'private.jpg').write_bytes(b'not an image')
        self.assertEqual(self.script.find_images(self.root), [str(self.source)])

    def test_main_only_rewrites_public_html_and_preflights_before_conversion(self):
        body = '<img src="/assets/photo.jpg">'
        self.page.write_text(body, encoding='utf8')
        private = self.root / '.claude-review' / 'proof.html'
        private.parent.mkdir()
        private.write_text(body, encoding='utf8')
        with patch.object(self.script, 'ROOT', str(self.root)), \
                patch.object(self.script, 'load_image_backend'), \
                patch.object(self.script, 'convert_image', return_value=(False, False)), redirect_stdout(io.StringIO()):
            self.script.main()
        self.assertIn('<picture>', self.page.read_text(encoding='utf8'))
        self.assertEqual(private.read_text(encoding='utf8'), body)
        with patch.object(self.script, 'site_html_files', side_effect=ValueError('linked source')), \
                patch.object(self.script, 'convert_image') as convert, self.assertRaises(ValueError):
            self.script.main()
        convert.assert_not_called()

    def test_stale_outputs_are_not_advertised(self):
        os.utime(self.source.with_suffix('.webp'), (1, 1))
        body = '<img src="/assets/photo.jpg">'
        self.assertEqual(self.rewrite(body), body)

    def test_failed_encoding_preserves_previous_bytes_and_removes_partial_temp(self):
        target = self.source.with_suffix('.webp')
        old = target.read_bytes()
        os.utime(target, (1, 1))
        backend = MagicMock()
        def fail(path, *args, **kwargs):
            Path(path).write_bytes(b'partial codec output')
            raise OSError('synthetic codec failure')
        backend.open.return_value.__enter__.return_value.save.side_effect = fail
        with patch.object(self.script, 'Image', backend), self.assertRaisesRegex(OSError, 'codec failure'):
            self.script.convert_image(self.source)
        self.assertEqual(target.read_bytes(), old)
        self.assertFalse(list(self.source.parent.glob('.image-convert-*')))

    def test_stale_avif_without_encoder_fails_before_html_rewrite(self):
        self.source.with_suffix('.avif').write_bytes(b'old figure')
        os.utime(self.source.with_suffix('.avif'), (1, 1))
        backend = MagicMock()
        backend.open.return_value.__enter__.return_value.format = 'WEBP'
        with patch.object(self.script, 'Image', backend), patch.object(self.script, 'HAS_AVIF', False), \
                self.assertRaisesRegex(ValueError, 'stale AVIF'):
            self.script.convert_image(self.source)


class MetadataPublicScopeTests(unittest.TestCase):
    def setUp(self):
        self.audit=load_script('_check_metadata_uniqueness')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def page(self,name,title='Authored page',description='Original public summary',noindex=False):
        source=('<html><head><title>'+title+'</title><meta name="description" content="'+description+'">'
                '<meta property="og:title" content="'+title+'"><meta property="og:description" content="'+description+'">'
                '<meta property="og:url" content="https://example.test/guide"><link rel="canonical" href="https://example.test/guide">'
                + ('<meta name="robots" content="noindex">' if noindex else '') + '</head><body>Fixture</body></html>')
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source,encoding='utf8')

    def result(self):
        output=io.StringIO()
        with patch.object(self.audit,'ROOT',self.root),redirect_stdout(output):
            code=self.audit.main()
        return code,output.getvalue()

    def test_root_local_evidence_copies_are_not_published_pages(self):
        self.page('index.html')
        for directory in ['.codex-review','.claude-review','.lighthouseci','delivery-preview']:
            self.page(directory+'/nested/old.html')
        self.assertEqual(self.result()[0],0)
        with patch.object(self.audit,'ROOT',self.root):
            self.assertEqual([p.relative_to(self.root).as_posix() for p in self.audit.iter_html()],['index.html'])

    def test_two_genuine_public_pages_keep_every_duplicate_gate(self):
        self.page('index.html');self.page('blog/new.html')
        code,output=self.result();self.assertEqual(code,1)
        for field in ['title','description','og:title','og:description','canonical','og:url']:
            self.assertIn('duplicate '+field,output)
        self.assertIn('2 indexable pages',output)

    def test_similar_root_names_and_nested_audit_names_remain_checked(self):
        self.page('index.html')
        for name in ['.codex-review-public/new.html','blog/.codex-review/new.html','blog/delivery-preview/new.html']:
            with self.subTest(name=name):
                self.page(name)
                code,output=self.result();self.assertEqual(code,1)
                self.assertIn(name,output)
                (self.root/name).unlink()

    def test_english_canonical_exception_retains_english_metadata_checks(self):
        self.page('index.html',title='中文頁面',description='中文摘要')
        self.page('en/index.html',title='English page',description='English summary')
        self.assertEqual(self.result()[0],0)
        self.page('en/another.html',title='English page',description='English summary')
        code,output=self.result();self.assertEqual(code,1)
        self.assertIn('duplicate title on 2 indexable pages',output)
        self.assertIn('duplicate description on 2 indexable pages',output)

    def test_existing_noindex_admin_and_recovery_controls_remain_excluded(self):
        self.page('index.html')
        self.page('notes.html',noindex=True)
        for name in ['admin/source.html','404.html','offline.html','reset-sw.html']:
            self.page(name)
        self.assertEqual(self.result()[0],0)


class TextIntegrityPublishedScopeTests(unittest.TestCase):
    def setUp(self):
        self.audit=load_script('_check_text_integrity')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for number in range(self.audit.MIN_FILES_SCANNED):
            (self.root/f'public-{number}.txt').write_text('Author supplied content',encoding='utf8')

    def write(self,name,raw):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
        return path

    def result(self):
        output=io.StringIO()
        with patch.object(self.audit,'ROOT',self.root),redirect_stdout(output):
            code=self.audit.main()
        return code,output.getvalue()

    def test_exact_root_private_evidence_is_not_site_text(self):
        for name in ['.codex-review','.claude-review','.lighthouseci','delivery-preview']:
            self.write(name+'/failed-evidence.txt',b'\xff\xfeprivate historical output')
        code,output=self.result()
        self.assertEqual(code,0,output)
        with patch.object(self.audit,'ROOT',self.root):
            self.assertEqual(len(self.audit.iter_files()),self.audit.MIN_FILES_SCANNED)

    def test_actual_public_text_preserves_all_character_and_title_gates(self):
        for raw,label in [
            (b'\xff\xfeinvalid public bytes','not valid UTF-8'),
            (chr(0xfffd).encode('utf8'),'Unicode replacement character'),
            ((chr(0xc3)+'X').encode('utf8'),'likely mojibake text'),
            (('<title>Author '+chr(0xb7)+' '+chr(0xb7)+' ChenDermatologist</title>').encode('utf8'),'duplicated title separator'),
            (b'<title>Author '+bytes([63])+b' ChenDermatologist</title>','likely corrupted title separator'),
        ]:
            with self.subTest(label=label):
                path=self.write('blog/public-guide.svg',raw)
                code,output=self.result()
                self.assertEqual(code,1)
                self.assertIn('blog/public-guide.svg:',output)
                self.assertIn(label,output)
                path.unlink()

    def test_similar_and_nested_evidence_names_remain_audited(self):
        for name in ['.codex-review-public/guide.html','blog/.codex-review/guide.html','blog/delivery-preview/guide.html']:
            with self.subTest(name=name):
                path=self.write(name,chr(0xfffd).encode('utf8'))
                code,output=self.result()
                self.assertEqual(code,1)
                self.assertIn(name+':',output)
                path.unlink()

    def test_private_evidence_cannot_satisfy_public_anti_vacuity_floor(self):
        for path in self.root.glob('public-*.txt'):
            path.unlink()
        for number in range(self.audit.MIN_FILES_SCANNED):
            self.write(f'.codex-review/evidence-{number}.txt',b'Historical evidence')
        code,output=self.result()
        self.assertEqual(code,1)
        self.assertIn('only 0 file(s) scanned',output)

class SEOPublishedScopeTests(unittest.TestCase):
    def setUp(self):
        fake=io.TextIOWrapper(io.BytesIO(),encoding='utf8')
        with patch.object(sys,'stdout',fake):
            self.audit=load_script('_check_seo_signals')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.good='<meta name="robots" content="max-image-preview:large,max-snippet:-1"><link rel="canonical" href="https://example.test/guide">'
        self.bad='<span data-zh="???">Fixture</span><div class="ad-slot">AdSense</div>'
        self.checks=['check_robots_serp_directives','check_canonical_coverage','check_no_mojibake_in_data_attrs','check_no_ad_placeholder_text']

    def write(self,name,source):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(source,encoding='utf8')
        return path

    def errors(self,method):
        self.audit.errors.clear()
        with patch.object(self.audit,'ROOT',self.root),redirect_stdout(io.StringIO()):
            getattr(self.audit,method)()
        return list(self.audit.errors)

    def test_exact_root_private_evidence_is_not_public_seo_content(self):
        self.write('index.html',self.good)
        for prefix in ['.codex-review','.claude-review','.lighthouseci','delivery-preview']:
            self.write(prefix+'/failed.html',self.bad)
        for method in self.checks:
            with self.subTest(method=method):
                self.assertEqual(self.errors(method),[])

    def test_real_public_robots_canonical_mojibake_and_placeholder_fail(self):
        self.write('blog/new.html',self.bad)
        for method in self.checks:
            with self.subTest(method=method):
                errors=self.errors(method)
                self.assertTrue(errors)
                self.assertTrue(any('[blog/new.html]' in row for row in errors))

    def test_similar_root_and_nested_evidence_names_remain_checked(self):
        for name in ['.codex-review-public/guide.html','blog/.codex-review/guide.html','blog/delivery-preview/guide.html']:
            path=self.write(name,self.bad)
            for method in self.checks:
                with self.subTest(name=name,method=method):
                    self.assertTrue(any('['+name+']' in row for row in self.errors(method)))
            path.unlink()

if __name__ == '__main__':
    unittest.main()
