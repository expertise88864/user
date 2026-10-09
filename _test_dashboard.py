"""Operational dashboard regressions on isolated synthetic article sources."""
from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
import _dashboard as dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dermnotes-dashboard-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "blog").mkdir()
        (self.root / "en/blog").mkdir(parents=True)
        self.entries = []
        self.patch = patch.object(dashboard, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def article(self, slug, *, unpublished=False, robots="", pretty=False, graph=False,
                extra="", metrics=True, english_robots=None):
        self.entries.append({"slug": slug, "title": "Reader's fixture", "title_en": "Reader's fixture",
                             "date": "2026-01-01", "cat": "note", "unpublished": unpublished})
        (self.root / "blog/blog-shared.js").write_text(
            "DN.ARTICLES=" + json.dumps(self.entries) + ";", encoding="utf-8")
        node = {"@context": "https://schema.org", "@type": "MedicalWebPage",
                "url": "https://chendermatologist.com/blog/" + slug,
                "articleSection": "Fixture"}
        if metrics:
            node.update(wordCount=1200, timeRequired="PT6M", dateModified="2026-01-01")
        value = {"@graph": [{"@type": "Person", "wordCount": 999999}, node]} if graph else node
        data = json.dumps(value, indent=2) if pretty else json.dumps(value, separators=(",", ":"))
        body = "<!doctype html><html><head>" + robots + (
            '<meta property="article:published_time" content="2026-01-01">'
            '<meta name="twitter:label1" content="Fixture">'
            '<script type="application/ld+json">' + data + '</script></head><body><article>'
            '<h1>Fixture</h1><p>Fixture body.</p>' + extra + '</article></body></html>')
        (self.root / "blog" / (slug + ".html")).write_text(body, encoding="utf-8")
        if english_robots is not None:
            (self.root / "en/blog" / (slug + ".html")).write_text(
                "<html><head>" + english_robots + "</head><body>Fixture</body></html>", encoding="utf-8")

    def test_trusted_catalogue_preserves_json_and_escaped_titles(self):
        self.article("public-guide")
        self.article("hidden-guide", unpublished=True)
        entries = dashboard.parse_articles()
        self.assertEqual([row["slug"] for row in entries], ["public-guide", "hidden-guide"])
        self.assertEqual(entries[0]["title"], "Reader's fixture")
        self.assertTrue(entries[1]["unpublished"])

    def test_pretty_and_graph_metadata_are_read_without_text_lookalikes(self):
        for slug, pretty, graph in [("compact-guide", False, False),
                                    ("pretty-guide", True, False), ("graph-guide", True, True)]:
            self.article(slug, pretty=pretty, graph=graph,
                         extra='<p>Example: "wordCount":888888</p>')
            with self.subTest(slug=slug):
                data = dashboard.article_metrics(slug)
                self.assertEqual((data["wordCount"], data["minutes"], data["dateModified"]),
                                 (1200, 6, "2026-01-01"))

    def test_missing_or_invalid_metadata_remains_unknown(self):
        self.article("missing-guide", metrics=False, extra=(
            '<p>Example: "wordCount":888888,"timeRequired":"PT99M"</p>'
            '<script type="application/ld+json">invalid JSON</script>'))
        metrics = dashboard.article_metrics("missing-guide")
        self.assertIsNone(metrics["wordCount"])
        self.assertIsNone(metrics["minutes"])
        self.assertEqual(metrics["dateModified"], "")

    def test_only_real_exact_internal_anchors_from_public_sources_count(self):
        self.article("target")
        self.article("lookalikes", extra=(
            '<p>/blog/target and /blog/target-tools</p>'
            '<script type="application/ld+json">{"url":"/blog/target"}</script>'
            '<a href="/blog/target-tools">Different page</a>'
            '<a href="https://elsewhere.test/blog/target">Foreign host</a>'))
        self.article("source", extra=(
            '<a href="target.html#section">Relative</a>'
            '<a href="/blog/target?view=read#section">Repeated same source</a>'))
        self.article("private", unpublished=True, extra='<a href="/blog/target">Private</a>')
        self.article("noindex", robots="<meta name='robots' content='noindex'>",
                     extra='<a href="/blog/target">Excluded</a>')
        public = dashboard.public_catalog(dashboard.parse_articles(), self.root)
        slugs = [row["slug"] for row in public]
        self.assertEqual(dashboard.incoming_link_counts(self.root / "blog", slugs)["target"], 1)

    def test_link_inventory_parses_each_public_source_once(self):
        self.article("first", extra='<a href="/blog/second">Next</a>')
        self.article("second", extra='<a href="/blog/first">Back</a>')
        self.article("third", extra='<a href="/blog/first">Related</a>')
        with patch.object(dashboard, "PageMetadata", wraps=dashboard.PageMetadata) as parser:
            self.assertEqual(dashboard.incoming_link_counts(self.root / "blog", ["first", "second", "third"]),
                             {"first": 2, "second": 1, "third": 0})
        self.assertEqual(parser.call_count, 3)

    def test_inert_examples_do_not_become_public_links_or_metadata(self):
        self.article('target')
        fake = ('<a href="/blog/target">Example</a>'
                '<meta name="robots" content="noindex">'
                '<script type="application/ld+json">{"wordCount":999}</script>')
        for opener, closer in [('textarea', 'textarea'), ('title', 'title'),
                               ('template', 'template')]:
            with self.subTest(element=opener):
                page = dashboard.PageMetadata()
                page.feed('<'+opener+'>'+fake+'</'+closer+'><a href="/blog/real">Real</a>')
                self.assertEqual(page.links, ['/blog/real'])
                self.assertFalse(page.noindex)
                self.assertEqual(page.schemas, [])
        page = dashboard.PageMetadata()
        page.feed('<template><template>'+fake+'</template>'+fake+'</template>'
                  '<a href="/blog/real">Real</a>')
        self.assertEqual(page.links, ['/blog/real'])
        self.assertFalse(page.noindex)

    def test_malformed_external_url_does_not_abort_public_link_inventory(self):
        self.article('target')
        self.article('source', extra=(
            '<a href="https://[broken">Broken external URL</a>'
            '<a href="/blog/target">Working internal link</a>'))
        self.assertEqual(dashboard.incoming_link_counts(self.root / 'blog', ['target', 'source']),
                         {'target': 1, 'source': 0})

    def test_inert_robots_examples_remain_public_through_report_generation(self):
        self.article('target')
        fake = '<meta name="robots" content="noindex">'
        for element in ('template', 'textarea', 'title', 'script', 'style'):
            self.article(element + '-example', extra=(
                '<' + element + '>' + fake + '</' + element + '>'
                '<a href="/blog/target">Real link</a>'))
        self.article('nested-example', extra=(
            '<template><template>' + fake + '</template>' + fake + '</template>'
            '<meta name><meta name="robots" content>'
            '<a href="/blog/target">Real link</a>'))
        public = dashboard.public_catalog(dashboard.parse_articles(), self.root)
        self.assertEqual([row['slug'] for row in public], [row['slug'] for row in self.entries])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(dashboard.main(), 0)
        report = (self.root / '_dashboard.md').read_text(encoding='utf-8')
        self.assertIn('**Published articles:** 7', report)
        self.assertIn('| target | Clinical Notes | 1200 | 6 | 6 |', report)
        for entry in self.entries:
            self.assertIn('| ' + entry['slug'] + ' |', report)
        self.assertNotIn('### noindex articles', report)

    def test_live_robots_after_inert_examples_still_exclude_articles(self):
        example = ('<template><template><meta name="robots" content="noindex">'
                   '</template></template>')
        self.article('excluded', extra=example + '<meta name="googlebot" content="NOINDEX, follow">')
        self.article('visible', extra=example)
        public = dashboard.public_catalog(dashboard.parse_articles(), self.root)
        self.assertEqual([row['slug'] for row in public], ['visible'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(dashboard.main(), 0)
        report = (self.root / '_dashboard.md').read_text(encoding='utf-8')
        self.assertIn('**Published articles:** 1', report)
        self.assertIn('### noindex articles', report)
        self.assertIn('- `excluded`', report)
        self.assertNotIn('| excluded |', report)
        self.assertIn('| visible |', report)

    def test_robots_none_and_ambiguous_attributes_fail_closed(self):
        directives = [
            '<meta name="robots" content="none">',
            '<meta name="googlebot" content="NONE, follow">',
            '<meta name="robots" content="noindex" content="index">',
            '<meta name="robots" content="index" content="noindex">',
            '<meta name="robots" name="description" content="index">',
            '<meta name="description" name="googlebot" content="index">',
            '<meta name="robots">',
        ]
        self.article('visible', robots='<meta name="robots" content="index, follow">')
        for index, directive in enumerate(directives):
            self.article('excluded-' + str(index), robots=directive, english_robots=directive)
            with self.subTest(directive=directive):
                page = dashboard.PageMetadata()
                page.feed(directive)
                self.assertTrue(page.noindex)
        public = dashboard.public_catalog(dashboard.parse_articles(), self.root)
        self.assertEqual([row['slug'] for row in public], ['visible'])
        self.assertEqual(dashboard.en_indexable_count([row['slug'] for row in self.entries]), 0)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(dashboard.main(), 0)
        report = (self.root / '_dashboard.md').read_text(encoding='utf-8')
        self.assertIn('**Published articles:** 1', report)
        self.assertIn('### noindex articles', report)
        for index in range(len(directives)):
            self.assertIn('- `excluded-' + str(index) + '`', report)
            self.assertNotIn('| excluded-' + str(index) + ' |', report)

    def test_english_count_uses_public_catalogue_and_parsed_directives(self):
        self.article("visible", english_robots="")
        self.article("excluded", english_robots=(
            "<!--" + "padding" * 1000 + "--><META CONTENT='NOINDEX, follow' NAME='googlebot'>"))
        self.article("private", unpublished=True, english_robots="")
        (self.root / "en/blog/unregistered.html").write_text("<html>Fixture</html>", encoding="utf-8")
        self.assertEqual(dashboard.en_indexable_count(["visible", "excluded"]), 1)

    def test_report_is_descriptive_and_preserves_source_bytes(self):
        self.article("visible", pretty=True)
        self.article("unknown", metrics=False)
        self.article("private", unpublished=True)
        self.article("excluded", robots=(
            "<!--" + "padding" * 1000 + "--><META CONTENT='NOINDEX, follow' NAME='robots'>"))
        files = {q.relative_to(self.root): q.read_bytes() for q in self.root.rglob("*") if q.is_file()}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(dashboard.main(), 0)
        text = (self.root / "_dashboard.md").read_text(encoding="utf-8")
        self.assertIn("**Published articles:** 2", text)
        self.assertIn("| visible | Clinical Notes | 1200 | 6 |", text)
        self.assertIn("| unknown | Clinical Notes | — | — |", text)
        self.assertIn("### noindex articles — 1", text)
        self.assertIn("- `excluded`", text)
        self.assertNotIn("| private |", text)
        self.assertNotIn("| excluded |", text)
        self.assertIn("Google has no preferred word count", text)
        self.assertIn("do not change dates to imply freshness", text)
        self.assertNotIn("ranking signal Google reads", text)
        self.assertNotIn("Short content underperforms", text)
        self.assertNotIn("missing speakable", text)
        self.assertIn("## Interpretation references", text)
        self.assertEqual(files, {name: (self.root / name).read_bytes() for name in files})
        self.assertEqual(set(q.relative_to(self.root) for q in self.root.rglob("*") if q.is_file()),
                         set(files) | {Path("_dashboard.md")})

    def test_actual_cli_in_isolated_site(self):
        self.article("visible", pretty=True)
        for name in ("_dashboard.py", "_sync_hub_catalog.py"):
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        run = subprocess.run([sys.executable, "-X", "utf8", "_dashboard.py"], cwd=self.root,
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("1 articles scored", run.stdout)
        self.assertIn("| visible | Clinical Notes | 1200 | 6 |",
                      (self.root / "_dashboard.md").read_text(encoding="utf-8"))

    def test_import_does_not_replace_callers_stdout(self):
        before = sys.stdout
        importlib.reload(dashboard)
        self.assertIs(sys.stdout, before)
        # Reload restores ROOT; keep subsequent fixture callers isolated.
        dashboard.ROOT = self.root


if __name__ == "__main__":
    unittest.main()
