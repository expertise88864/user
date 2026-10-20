/* Browser fixture suite (CI job "Browser fixtures").
 * Every check serves its own documents through context.route on a fixture
 * origin, so the suite needs no Preview deployment, no credentials and sends
 * no request to Vercel. It runs on the runner itself; the Preview browser job
 * keeps only the checks that need the exact-SHA deployment.
 */
const fs = require('node:fs');

const FIXTURES = [
  '_test_analytics_origin_browser.cjs',
  '_test_nav_search_browser.cjs',
  '_test_article_prefetch_browser.cjs',
  '_test_settings_public_browser.cjs',
  '_test_admin_editing_browser.cjs',
  '_test_file_groups_browser.cjs',
  '_test_exam_editor_browser.cjs',
  '_test_exam_reading_browser.cjs',
  '_test_settings_panel_browser.cjs',
  '_test_dictionary_undo_browser.cjs',
  '_test_font_loader_browser.cjs',
  '_test_diagram_loading_browser.cjs',
  '_test_diagram_viewer_browser.cjs',
  '_test_reading_meta_browser.cjs',
  '_test_reading_engagement_browser.cjs',
  '_test_recovery_pages_browser.cjs',
  '_test_reading_navigation_browser.cjs',
  '_test_reader_controls_browser.cjs',
  '_test_patient_journeys_browser.cjs',
  '_test_en_locale_browser.cjs',
  '_test_draft_media_browser.cjs',
  '_test_editor_drafts_browser.cjs',
  '_test_editor_version_browser.cjs',
  '_test_calculators_browser.cjs',
  '_test_article_publication_browser.cjs',
  '_test_generated_approval_browser.cjs',
  '_test_word_editor_browser.cjs',
  '_test_word_security_browser.cjs',
  '_test_word_admin_browser.cjs',
  '_test_word_ime_browser.cjs',
  '_test_hover_stability_browser.cjs',
];

function options(name) {
  if (name === '_test_reader_controls_browser.cjs') {
    return { readingSource: fs.readFileSync('blog/blog-article-reading.min.js', 'utf8') };
  }
  return undefined;
}

async function runFixtures(browser) {
  for (const name of FIXTURES) await require('./' + name)(browser, options(name));
  return FIXTURES.length;
}

module.exports = { FIXTURES, runFixtures };

if (require.main === module) (async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  try {
    console.log('Browser fixtures passed: ' + await runFixtures(browser) + ' suites');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
