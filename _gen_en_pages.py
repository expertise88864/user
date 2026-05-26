#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate /en/ mirrors with English server-rendered fallbacks.

The legacy site stores bilingual copy in data-zh / data-en attributes and
switches language in the browser. Search crawlers, social scrapers, and JSON-LD
validators see the raw HTML, so English mirrors must also be rendered in English
at build time.
"""

from __future__ import annotations

import json
import os
import re
import sys
import html as html_lib
from html.parser import HTMLParser
from pathlib import Path

# CODE_REVIEW — Windows cp950 console crashes on print() with CJK
# unless stdout is reconfigured to UTF-8. Guard with hasattr because
# `.reconfigure()` only exists in Python 3.7+.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = os.path.dirname(os.path.abspath(__file__))
DOMAIN = 'https://chendermatologist.com'

SKIP = {'404.html', 'offline.html', 'admin.html', 'dashboard.html', 'notes.html', 'reset-sw.html'}

EN_OG_OVERRIDES = {
    'index.html': {
        'title': 'Dr. Yi-Jia Chen | Dermatology Patient Education (Taiwan)',
        'desc': 'Plain-language dermatology articles by Dr. Chen: acne, sunscreen, eczema, melasma, hair loss, biologics, isotretinoin, and topical steroids.',
    },
    'about.html': {
        'title': 'About Dr. Yi-Jia Chen | Dermatology Resident Physician',
        'desc': 'Background of Dr. Chen, Yi-Jia, M.D.: KMU medical school, KMUH PGY, dermatology residency, and personal patient-education work.',
    },
    'tools.html': {
        'title': 'Dermatology Calculators | PASI, DLQI, SCORAD, SALT',
        'desc': 'Free clinical scoring calculators for dermatology, including PASI, DLQI, SCORAD, SALT, EASI, IGA, NRS, and more.',
    },
    'glossary.html': {
        'title': 'Dermatology Glossary in Plain Mandarin and English',
        'desc': 'Plain-language glossary mapping dermatology terms such as biologics, JAK inhibitors, phototherapy, and topical steroids.',
    },
    'blog/index.html': {
        'title': 'Dermatology Articles Index | Dr. Yi-Jia Chen',
        'desc': 'Index of dermatology articles: acne, sunscreen, eczema, melasma, isotretinoin, topical acids, steroids, biologics, hair loss, and mpox.',
    },
    'blog/acne-myths.html': {
        'title': '8 Acne Myths | Dermatologist Patient Education',
        'desc': 'Clear answers to common acne myths: popping pimples, toothpaste spot treatment, dry skin acne, washing frequency, supplements, scars, and when to see a dermatologist.',
    },
    'blog/sunscreen-myths.html': {
        'title': '8 Sunscreen Myths | SPF, UVA, Indoor Light, Mineral vs Chemical',
        'desc': 'A dermatologist explains sunscreen myths about indoor light, cloudy days, SPF numbers, UVA and PA ratings, mineral versus chemical filters, acne-prone skin, and melasma.',
    },
    'blog/isotretinoin-clinical.html': {
        'title': 'Oral Isotretinoin Clinical Guide | Dermatology Notes',
        'desc': 'Resident-level isotretinoin notes covering pharmacology, mechanisms, indications, dosing, adverse effects, drug interactions, monitoring, and acne guideline integration.',
    },
    'blog/perioral-dermatitis-guide.html': {
        'title': 'Periorificial (Perioral) Dermatitis: Complete Patient Guide',
        'desc': 'Patient-friendly dermatology guide to periorificial / perioral dermatitis: how to tell it apart from acne, rosacea, and eczema; the corticosteroid trap; gentle skincare; topical metronidazole / tacrolimus / pimecrolimus / ivermectin; oral doxycycline; Taiwan NHI status and brand names. Integrates Acevedo-Fontanez 2026 JAAD review.',
    },
    'blog/toenail-mechanical-disorders.html': {
        # SEO_AUDIT B1 — shortened from 76 → 63 chars so SERP doesn't truncate.
        'title': 'Toenail Mechanical Disorders — 12-Type Atlas & Diabetic Foot',
        'desc': 'Over 90% of toenail dystrophy is mechanical, not fungal. Patient-friendly guide to the 12 most common types (onycholysis, subungual heloma, Beau lines, retronychia, pincer nail, onychocryptosis, etc.), 4 foot deformities (Morton toe, hallux valgus, flat foot, splayfoot), diabetic nail care, and Taiwan NHI coverage. Integrates Ricardo 2026 JAAD review.',
    },
    'blog/dermatologic-oral-examination.html': {
        # SEO_AUDIT B1 — shortened from 83 → 56 chars.
        'title': 'Oral Mucosa: Dermatologist vs Dentist — Exam & Biopsy',
        'desc': 'An ulcer not healing in 2 weeks, white lacy oral patches, or peeling gums often belong to dermatology, not dentistry. Patient-friendly guide to 6 oral mucosal conditions (oral lichen planus, recurrent aphthous stomatitis, leukoplakia, mucous membrane pemphigoid, actinic cheilitis, oral pigmented lesions), Taiwan-specific epidemiology (betel-related leukoplakia, OLP prevalence trends), dermatologic oral exam steps, biopsy timing and technique, and AHA 2021 antibiotic prophylaxis. Integrates Klein & Aristizabal 2026 JAAD CME.',
    },
    'blog/severe-scabies-treatment.html': {
        'title': 'Severe Scabies: Complete Oral Ivermectin + 5% Permethrin Treatment Guide',
        'desc': 'Severe scabies (profuse or crusted, with hundreds to thousands of mites) does not respond to single-dose treatment. Patient-friendly guide based on the May 2026 NEJM GALE CRUSTED randomized trial: standard regimen is ivermectin 200 μg/kg on Days 0, 7, 14 plus 5% permethrin head-to-toe on Days 0 and 7 plus daily emollient — Day 28 cure rate around 82%. Covers life cycle, household co-treatment, environmental cleaning, long-term care outbreak protocols, infant/pregnancy safety, and Taiwan drug availability.',
    },
    'blog/dupilumab-long-term-maintenance.html': {
        'title': 'Dupilumab Long-Term Maintenance: JAAD 2026 Real-World Study (Tapering Relapses Earlier than Stopping)',
        'desc': 'Real-world 79-patient retrospective from Xinjiang, China, published in May 2026 JAAD, comparing three dupilumab maintenance strategies in moderate-to-severe atopic dermatitis: continuous q2w, interval extension (tapering), and abrupt stop. Continuous q2w yielded the longest relapse-free duration (mean 159.55 days, some >300 days); paradoxically, the tapering group relapsed earlier than the abrupt-stop group, possibly due to sub-therapeutic drug levels or selection bias. Relapse predictors: higher baseline IgE, longer disease duration, non-classic AD phenotype. Includes a first-reported optic-nerve-atrophy case (1 year post-discontinuation, causality unconfirmed) and Taiwan NHI Article 13.17.1 reimbursement criteria.',
    },
    'blog/ai-dermatology-roles.html': {
        'title': 'AI in Dermatology Today: Dermoscopy Heat Maps, Explainability, and Education',
        'desc': 'Resident-level research review integrating 2026 JAAD Reviews and the JAAD eye-tracking study comparing dermatologist gaze maps with DEXI dermoscopy AI heat maps. Covers diagnostic support, explainable AI, generative AI for education, and why AI cannot yet replace clinical judgment.',
    },
    # SEO_AUDIT B1 — 4 articles whose auto-derived titles ran >70 chars.
    # Each rewritten ≤65 chars so Google SERP doesn't ellipsize.
    'blog/skin-biopsy-excision.html': {
        'title': 'Skin biopsy & tumor excision — guide & post-op care',
        'desc': 'Patient-friendly dermatology guide to skin biopsy and tumor excision: indications, technique, post-op wound care, scar care, and follow-up. Integrates AAD biopsy guideline.',
    },
    'blog/psoriasis-special-populations.html': {
        'title': 'Psoriasis comorbidities — PsA, CV, pregnancy, pediatric',
        'desc': 'Psoriasis comorbidities and special populations: psoriatic arthritis screening, cardiovascular risk, pregnancy / breastfeeding biologic safety, pediatric considerations, and Taiwan NHI coverage notes.',
    },
    'blog/warts-myths.html': {
        'title': 'Warts myths — banana peel, single laser, self-resolution?',
        'desc': 'Common warts (HPV) myth-busting: does banana peel work, can one laser session cure, will warts self-resolve, when to see a dermatologist. Treatment ladder included.',
    },
    'blog/rosacea-myths.html': {
        'title': 'Rosacea myths — phenotypes, treatment ladder, Demodex',
        'desc': 'Rosacea myth-busting: subtype identification, ETR vs PPR vs phymatous vs ocular, treatment ladder (topical metronidazole / ivermectin / brimonidine, oral doxycycline, laser), Demodex correlation.',
    },
}

EN_BANNER = '''<div id="dn-en-banner" style="background:linear-gradient(180deg,#ecfeff,#cffafe);border-bottom:1px solid #67e8f9;padding:9px 18px;text-align:center;font-size:12.5px;color:#0c5159;font-family:Inter,system-ui,sans-serif;line-height:1.5;font-weight:600">
  English version. Prefer Traditional Chinese?
  <a href="#" id="dn-en-banner-zh" style="margin-left:8px;color:#083a40;font-weight:800;text-decoration:underline">Switch to Chinese</a>
</div>'''

EN_LANG_BOOTSTRAP = '''<script>
try {
  localStorage.setItem('dn_lang', 'en');
  document.cookie = 'dn_lang=en;path=/;max-age=31536000;samesite=lax';
} catch (e) {}
document.addEventListener('DOMContentLoaded', function () {
  var sw = document.getElementById('dn-en-banner-zh');
  if (sw) sw.href = location.pathname.replace(/^\\/en\\//, '/').replace(/^\\/en$/, '/');
});
</script>'''

FALLBACK_EN_DESC = (
    'Plain-language dermatology patient education by Dr. Yi-Jia Chen, '
    'summarized from medical literature and clinical guidelines.'
)


class DataEnRenderer(HTMLParser):
    """Render elements carrying data-en with that value as their inner HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.active: dict[str, object] | None = None

    def _emit(self, text: str) -> None:
        if self.active is None:
            self.out.append(text)

    def handle_starttag(self, tag, attrs):
        start = self.get_starttag_text()
        data_en = next((value or '' for name, value in attrs if name == 'data-en'), None)
        if self.active is not None:
            if tag == self.active['tag']:
                self.active['depth'] = int(self.active['depth']) + 1
            return
        if data_en is not None:
            self.active = {'tag': tag, 'depth': 1, 'start': start, 'en': data_en}
            return
        self.out.append(start)

    def handle_startendtag(self, tag, attrs):
        self._emit(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.active is not None:
            if tag == self.active['tag']:
                self.active['depth'] = int(self.active['depth']) - 1
                if self.active['depth'] == 0:
                    self.out.append(str(self.active['start']))
                    # Python's HTMLParser already decodes HTML entities in
                    # attribute values, so '&lt; 2 yr' arrives here as '< 2 yr'.
                    # Re-escape lone '<' that doesn't start an HTML tag so the
                    # html5validator does not flag "Bad character ' ' after '<'".
                    en_text = str(self.active['en'])
                    en_text = re.sub(r'<(?![a-zA-Z!/?])', '&lt;', en_text)
                    self.out.append(en_text)
                    self.out.append(f'</{tag}>')
                    self.active = None
            return
        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        self._emit(data)

    def handle_entityref(self, name):
        self._emit(f'&{name};')

    def handle_charref(self, name):
        self._emit(f'&#{name};')

    def handle_comment(self, data):
        self._emit(f'<!--{data}-->')

    def handle_decl(self, decl):
        self._emit(f'<!{decl}>')

    def handle_pi(self, data):
        self._emit(f'<?{data}>')

    def render(self, src: str) -> str:
        self.feed(src)
        self.close()
        return ''.join(self.out)


def _translate_svg_text(svg_block: str) -> str:
    """Translate <text> and <title> elements inside an SVG that carry data-en.

    The main `apply_data_en` STASHES SVG blocks to keep their bytes intact
    (HTMLParser would lowercase tags like linearGradient). But that means
    `<text data-en="...">Chinese</text>` and `<title data-en="...">Chinese
    </title>` inside SVG never get translated when we want a static EN
    mirror. This helper does a targeted swap on these tags: keeps the
    attrs, swaps inner content with data-en value. SVG-other tags untouched.

    2026-05-25 — extended to <title> as well (was only <text>).
    """
    def repl_text(m: re.Match[str]) -> str:
        attrs = m.group('attrs')
        de = re.search(r'data-en="([^"]*)"', attrs)
        if not de:
            return m.group(0)
        en = de.group(1)
        en = re.sub(r'<(?![a-zA-Z!/?])', '&lt;', en)
        return f'<text{attrs}>{en}</text>'

    def repl_title(m: re.Match[str]) -> str:
        attrs = m.group('attrs')
        de = re.search(r'data-en="([^"]*)"', attrs)
        if not de:
            return m.group(0)
        en = de.group(1)
        en = re.sub(r'<(?![a-zA-Z!/?])', '&lt;', en)
        return f'<title{attrs}>{en}</title>'

    svg_block = re.sub(
        r'<text(?P<attrs>[^>]*\bdata-en="[^"]*"[^>]*)>(?P<inner>[^<]+)</text>',
        repl_text,
        svg_block,
    )
    svg_block = re.sub(
        r'<title(?P<attrs>[^>]*\bdata-en="[^"]*"[^>]*)>(?P<inner>[^<]+)</title>',
        repl_title,
        svg_block,
    )
    return svg_block


def apply_data_en(src: str) -> str:
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        # Pre-translate <text data-en> inside the SVG before stashing.
        block = _translate_svg_text(match.group(0))
        protected.append(block)
        return f'__DN_EN_PROTECTED_BLOCK_{len(protected) - 1}__'

    # HTMLParser lowercases foreign-content end tags such as linearGradient.
    # Keep SVG/script/style bytes intact and only render bilingual HTML around them.
    # 2026-05-24 — but BEFORE stashing SVG, swap any `<text data-en>` inner
    # content with the EN value so EN mirror figures show English labels.
    guarded = re.sub(r'<(svg|script|style)\b[\s\S]*?</\1>', stash, src, flags=re.I)
    rendered = DataEnRenderer().render(guarded)
    for index, block in enumerate(protected):
        rendered = rendered.replace(f'__DN_EN_PROTECTED_BLOCK_{index}__', block)
    return rendered


def prefer_static_english_blocks(src: str) -> str:
    """For /en/ pages, remove hidden Chinese article bodies when proseEn exists.

    Pattern A articles ship a fully-rendered English mirror inside
    `<div id="proseEn">`; we drop the Chinese half so search crawlers see EN.
    Pattern B articles (newer style) keep `proseEn` empty and rely on
    in-place data-zh/data-en swapping inside `proseZh`. For those, KEEP the
    proseZh body — apply_data_en will rewrite each tagged element below.
    Detect via empty-or-whitespace-only proseEn block.

    Accepts both legacy `class="prose"` and bilingual `class="prose-zh"` /
    `class="prose-en"` wrappers (2026-05-24 — older regex missed bilingual
    articles like isotretinoin-patient, leaving 2300+ CJK chars visible on
    the EN mirror's proseZh block while the fully-translated proseEn block
    stayed hidden via display:none).
    """

    # 2026-05-25 — allow HTML comments inside the proseEn block when
    # detecting "empty" (some articles have placeholder `<!-- EN body goes
    # here -->` style markers). Otherwise the script incorrectly classifies
    # them as Pattern A (= keeps both proseZh+proseEn) and doubles CJK.
    proseEn_empty = re.search(
        r'<div\s+id="proseEn"\s+class="prose(?:-en)?"[^>]*>\s*(?:<!--[\s\S]*?-->\s*)*</div>',
        src,
        flags=re.I,
    )
    if not proseEn_empty:
        # Drop entire proseZh block (replace with empty) AND strip the
        # display:none from proseEn so it becomes the visible body. Two-step
        # rewrite, accepting both legacy `prose` and bilingual `prose-zh|en`.
        # Step 1: remove the proseZh content.
        src = re.sub(
            r'<div\s+id="proseZh"\s+class="prose(?:-zh)?">[\s\S]*?(?=<div\s+id="proseEn"\s+class="prose(?:-en)?")',
            '',
            src,
            count=1,
            flags=re.I,
        )
        # Step 2: unhide proseEn (strip the inline display:none if present).
        src = re.sub(
            r'(<div\s+id="proseEn"\s+class="prose(?:-en)?")\s+style="display:none;?"',
            r'\1',
            src,
            count=1,
            flags=re.I,
        )
    src = re.sub(r'(<div\s+class="ad-slot"[^>]*>)廣告位(</div>)', r'\1Ad slot\2', src)
    src = re.sub(r'(<div\s+class="ad-slot"[^>]*>)廣告位 · AdSense(</div>)', r'\1Ad slot · AdSense\2', src)
    src = src.replace('aria-label="主導覽"', 'aria-label="Main navigation"')
    src = src.replace('aria-label="搜尋"', 'aria-label="Search"')
    src = src.replace('title="搜尋文章 (Cmd/Ctrl + K)"', 'title="Search articles (Cmd/Ctrl + K)"')
    src = src.replace('aria-label="贊助本站"', 'aria-label="Support this site"')
    src = src.replace('title="街口轉帳支持作者"', 'title="Support this site"')
    src = src.replace('aria-label="切換暗色模式"', 'aria-label="Toggle dark mode"')
    src = src.replace('title="切換亮 / 暗"', 'title="Toggle light / dark"')
    src = src.replace('aria-label="開啟選單"', 'aria-label="Open menu"')
    src = src.replace('title="語言切換"', 'title="Language"')
    src = src.replace('>跳到主內容</a>', '>Skip to main content</a>')
    return src


EN_PRIVACY_ARTICLE = '''<main id="main-content">
<section class="pt-12 sm:pt-16 pb-6"><div class="max-w-3xl mx-auto px-5 sm:px-8"><div class="text-[11px] uppercase tracking-[.24em] text-teal-700 font-semibold">Site Policy</div><h1 class="font-display font-bold text-[34px] sm:text-[42px] mt-3 leading-tight">Privacy Policy</h1><p class="mt-4 text-[13px] text-ink-500">Last updated: May 11, 2026</p></div></section>
<article class="max-w-3xl mx-auto px-5 sm:px-8 mb-16"><div id="proseEn" class="prose">
<p>Welcome to ChenDermatologist. This policy explains what information may be collected when you use this website, how it is used, and what choices you have.</p>
<h2>1. Information We Collect</h2>
<h3>1-1 Information You Provide</h3>
<p>This website does not require account registration and does not ask you to submit your name, national ID number, medical record, photographs, symptoms, or contact information. If you use an external clinic or hospital booking system, that data is handled by that medical institution under its own privacy policy.</p>
<h3>1-2 Automatically Collected Technical Data</h3>
<p>When you browse this website, the hosting provider may record standard web logs such as partially anonymized IP address, browser type, operating system, pages visited, timestamps, and referrer. These logs are used for traffic statistics, site improvement, and security protection.</p>
<h3>1-3 Cookies</h3>
<p>This website may use a first-party cookie named <code>dn_lang</code> to remember your preferred language. Third-party analytics or advertising services may also use cookies as described below. You can clear or block cookies in your browser settings.</p>
<h2>2. Third-Party Services</h2>
<h3>2-1 Google AdSense</h3>
<p>This website may use Google AdSense to display ads. Google and its partners may use cookies, including advertising cookies, to serve and measure ads. You can manage Google ad personalization in Google Ads Settings.</p>
<h3>2-2 Microsoft Clarity</h3>
<p>This website may use Microsoft Clarity to understand aggregate browsing behavior such as clicks, scroll depth, and time on page. Sensitive input fields are not intentionally collected by this website.</p>
<h3>2-3 Search Console and Webmaster Tools</h3>
<p>Google Search Console and Bing Webmaster Tools are used to verify site ownership, submit sitemaps, and monitor search visibility. They do not require this website to collect personal medical information from visitors.</p>
<h3>2-4 Google Fonts and Local CSS</h3>
<p>Fonts may be loaded from Google Fonts. The main site styling is served from local CSS files and no longer depends on the Tailwind CDN. Google Fonts may receive your IP address when font resources are requested.</p>
<h2>3. What We Do Not Do</h2>
<ul><li>We do not sell, rent, or trade your personal data.</li><li>We do not collect your medical records, symptoms, photographs, or contact information through this public website.</li><li>We do not provide individual medical advice through analytics, ads, or cookies.</li></ul>
<h2>4. Your Choices</h2>
<p>You may clear cookies, block third-party cookies, opt out of personalized advertising through the relevant third-party settings, or contact the site owner through the information on the About page.</p>
<h2>5. Children</h2>
<p>This website is intended for general educational reading. It does not knowingly collect personal information from children under 13.</p>
<h2>6. Updates</h2>
<p>This policy may be updated when services, laws, or technical settings change. Material changes will be reflected on this page.</p>
<h2>7. Medical Disclaimer</h2>
<p>All content is for general medical education only and does not replace an in-person consultation, examination, diagnosis, or prescription. Decisions about medications or treatment should be made with your treating physician.</p>
</div></article></main>'''


def replace_privacy_body(src: str) -> str:
    if '<main id="main-content">' not in src:
        return src
    return re.sub(r'<main id="main-content">[\s\S]*?</main>', EN_PRIVACY_ARTICLE, src, count=1, flags=re.I)


def local_html_exists(path: str) -> bool:
    clean = path.split('?', 1)[0].split('#', 1)[0]
    if clean == '/':
        return os.path.exists(os.path.join(ROOT, 'index.html'))
    if clean.endswith('/'):
        return os.path.exists(os.path.join(ROOT, clean.strip('/'), 'index.html'))
    rel = clean.lstrip('/').replace('/', os.sep)
    return (
        os.path.exists(os.path.join(ROOT, rel + '.html'))
        or os.path.exists(os.path.join(ROOT, rel, 'index.html'))
    )


def en_mirror_exists(path: str) -> bool:
    clean = path.split('?', 1)[0].split('#', 1)[0]
    if clean == '/':
        return True
    if clean.startswith('/en/'):
        return True
    if clean.endswith('/'):
        source = os.path.join(ROOT, clean.strip('/'), 'index.html')
        return os.path.exists(source)

    rel = clean.lstrip('/')
    if rel.endswith('.html'):
        rel = rel[:-5]
    source_file = rel + '.html'
    if '/' not in rel:
        return os.path.exists(os.path.join(ROOT, source_file)) and source_file not in SKIP
    if rel.startswith('blog/'):
        blog_file = rel.split('/', 1)[1] + '.html'
        return os.path.exists(os.path.join(ROOT, 'blog', blog_file))
    return False


def to_en_path(path: str) -> str:
    if path == '/':
        return '/en/'
    if path.startswith('/en/'):
        return path
    if path.endswith('/'):
        return '/en' + path
    return '/en' + path


def rewrite_en_internal_links(src: str) -> str:
    """Keep English pages on the English mirror for local page links."""

    def patch(match: re.Match[str]) -> str:
        prefix, quote, href = match.groups()
        if not href.startswith('/') or href.startswith('//') or href.startswith('/en/'):
            return match.group(0)
        path, suffix = href, ''
        for marker in ('#', '?'):
            if marker in path:
                path, tail = path.split(marker, 1)
                suffix = marker + tail
                break
        if not local_html_exists(path) or not en_mirror_exists(path):
            return match.group(0)
        return prefix + quote + to_en_path(path) + suffix + quote

    return re.sub(r'(<a\b[^>]*\bhref=)(["\'])([^"\']+)\2', patch, src, flags=re.I)


def strip_tags(src: str) -> str:
    src = re.sub(r'<script\b[\s\S]*?</script>', ' ', src, flags=re.I)
    src = re.sub(r'<style\b[\s\S]*?</style>', ' ', src, flags=re.I)
    src = re.sub(r'<svg\b[\s\S]*?</svg>', ' ', src, flags=re.I)
    src = re.sub(r'<[^>]+>', ' ', src)
    return re.sub(r'\s+', ' ', html_lib.unescape(src)).strip()


# 2026-05-17 \u2014 elements with data-en="..." get their textContent swapped
# to English at runtime by DN.applyTextOnly(). For visible_cjk_count
# (used to gate EN-indexable status) we should NOT count text inside
# such elements \u2014 what the EN reader actually sees is the data-en value,
# not the zh fallback baked into HTML.
#
# 2026-05-25 \u2014 the old regex-based _DATA_EN_BLOCK_RE matcher was wrong
# on nested same-tag content (e.g., `<div data-en="..."><div>ZH</div></div>`
# closes at the first inner </div>, leaving the outer wrapper's ZH text
# uncounted-as-stripped). Result: AD-overview and dupilumab-long-term-
# maintenance kept being marked noindex even after all visible CJK was
# translated away. Switch to a DOM-aware counter: parse the HTML and walk
# the tree, skipping descendants of any element with data-en.
class _VisibleCJKCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip_depth = 0
        self.count = 0
        self._cjk_re = re.compile(r'[\u4e00-\u9fff]')

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ('script', 'style', 'svg'):
            self.skip_depth += 1
            return
        has_data_en = any(name == 'data-en' for name, _ in attrs)
        if has_data_en or self.skip_depth:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        self.count += len(self._cjk_re.findall(data))


def visible_cjk_count(src: str) -> int:
    """Count CJK characters that a JS-disabled crawler (e.g., legacy
    GoogleBot, Bingbot Lite) would see in the rendered text. Skips
    script/style/svg blocks AND any element subtree carrying data-en
    (which DN.applyTextOnly swaps to English at runtime).
    """
    counter = _VisibleCJKCounter()
    try:
        counter.feed(src)
        counter.close()
    except Exception:
        # Fall back to the regex-based estimator if parsing breaks
        return len(re.findall(r'[\u4e00-\u9fff]', strip_tags(src)))
    return counter.count


def has_cjk(src: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', src or ''))


def first_text(pattern: str, src: str) -> str:
    m = re.search(pattern, src, re.I | re.S)
    return strip_tags(m.group(1)) if m else ''


def _english_only_from_h1(src: str) -> str:
    """Extract the EN-equivalent text of <h1>.

    The <h1> in source often mixes raw Chinese (first half) + a
    <span data-zh="..." data-en="...">trailing</span>. apply_data_en
    only translates spans with data-en, leaving the first half zh.
    For meta-extraction purposes we want the EN equivalent if it
    can be assembled — concatenate every data-en attr inside h1.
    Falls back to plain stripped text (which may still be hybrid).
    """
    m = re.search(r'<h1\b[^>]*>([\s\S]*?)</h1>', src, re.I)
    if not m:
        return ''
    inner = m.group(1)
    en_parts: list[str] = []
    # If h1 itself has data-en attribute
    h1_open_m = re.match(r'<h1\b([^>]*)>', m.group(0), re.I)
    if h1_open_m:
        de_m = re.search(r'data-en="([^"]*)"', h1_open_m.group(1))
        if de_m and not has_cjk(de_m.group(1)):
            return strip_tags(de_m.group(1)).strip()
    # Otherwise concatenate every nested element's data-en
    for de_m in re.finditer(r'data-en="([^"]*)"', inner):
        v = de_m.group(1)
        if v and not has_cjk(v):
            en_parts.append(strip_tags(v).strip())
    if en_parts:
        return ' — '.join(en_parts)
    return first_text(r'<h1\b[^>]*>([\s\S]*?)</h1>', src)


def derive_meta(src: str, override: dict[str, str] | None) -> tuple[str, str]:
    h1 = _english_only_from_h1(src)
    title = (override or {}).get('title') or (h1 + ' | ChenDermatologist' if h1 else '')
    if not title or has_cjk(title):
        title = 'Dermatology Patient Education | ChenDermatologist'
    if len(title) > 72:
        title = title[:69].rsplit(' ', 1)[0].rstrip(' ,.;:|-') + '...'

    lead = (override or {}).get('desc') or ''
    h1_pos = src.lower().find('</h1>')
    if not lead and h1_pos >= 0:
        # Scan up to the first 3 <p> tags after </h1>. For each:
        # 1) prefer the <p>'s own data-en if present and non-CJK
        # 2) otherwise concatenate every nested data-en non-CJK value
        # 3) otherwise fall through to the raw text (which may be CJK)
        tail = src[h1_pos:]
        for p_m in list(re.finditer(r'<p\b([^>]*)>([\s\S]*?)</p>', tail, re.I))[:3]:
            attrs = p_m.group(1)
            inner = p_m.group(2)
            # Own data-en
            attr_de = re.search(r'data-en="([^"]*)"', attrs)
            if attr_de and not has_cjk(attr_de.group(1)):
                lead = attr_de.group(1)
                break
            # Nested data-en concatenation
            nested = [m.group(1) for m in re.finditer(r'data-en="([^"]*)"', inner) if not has_cjk(m.group(1))]
            if nested:
                candidate = ' '.join(strip_tags(x) for x in nested if x.strip())
                if candidate and not has_cjk(candidate):
                    lead = candidate
                    break
            # Fall through to plain text
            raw = strip_tags(inner)
            if raw and not has_cjk(raw):
                lead = raw
                break
    if not lead or has_cjk(lead):
        lead = (override or {}).get('desc') or FALLBACK_EN_DESC
    desc = re.sub(r'\s+', ' ', lead).strip()
    if len(desc) > 170:
        desc = desc[:167].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    if len(desc) < 80:
        desc = (desc + ' ' + FALLBACK_EN_DESC).strip()
        if len(desc) > 170:
            desc = desc[:167].rsplit(' ', 1)[0].rstrip(' ,.;:') + '...'
    return title, desc


def set_meta(src: str, title: str, desc: str) -> str:
    esc_title = html_lib.escape(title, quote=False)
    esc_desc = html_lib.escape(desc, quote=True)
    src = re.sub(r'<title>[\s\S]*?</title>', f'<title>{esc_title}</title>', src, count=1, flags=re.I)
    # 2026-05-17 — use lambda replacement to bypass backreference parsing.
    # esc_desc / esc_title can contain digits like "8 Acne Myths" which combined
    # with the leading r'\1' became `\18` = invalid group reference 18.
    src = re.sub(r'(<meta\s+name="description"\s+content=")[^"]*(")',
                 lambda m: m.group(1) + esc_desc + m.group(2),
                 src, count=1, flags=re.I)
    for field, value in (
        ('og:title', title),
        ('og:description', desc),
        ('twitter:title', title),
        ('twitter:description', desc),
    ):
        src = re.sub(
            rf'(<meta\s+(?:property|name)="{re.escape(field)}"\s+content=")[^"]*(")',
            lambda m: m.group(1) + html_lib.escape(value, quote=True) + m.group(2),
            src,
            count=1,
            flags=re.I,
        )
    # 2026-05-24 — additional meta fields that previously kept ZH content in
    # the /en/ mirror and showed up as raw CJK to GoogleBot + screen-readers.
    # All replace ALL occurrences (count not capped) because OG/twitter pairs
    # often appear twice (open-graph block + dn-og-extras block).
    EN_AUTHOR = 'Dr. Yi-Jia Chen · ChenDermatologist'
    EN_AUTHOR_NAME = 'Dr. Yi-Jia Chen'
    # author meta — replace ZH "陳翊嘉醫師 · ChenDermatologist" forms.
    src = re.sub(
        r'(<meta\s+name="author"\s+content=")[^"]*(")',
        lambda m: m.group(1) + html_lib.escape(EN_AUTHOR, quote=True) + m.group(2),
        src,
        flags=re.I,
    )
    # twitter:data2 = "Written by" value — canonical EN author name.
    src = re.sub(
        r'(<meta\s+name="twitter:data2"\s+content=")[^"]*(")',
        lambda m: m.group(1) + html_lib.escape(EN_AUTHOR_NAME, quote=True) + m.group(2),
        src,
        flags=re.I,
    )
    # og:image:alt + twitter:image:alt — use article EN title as alt text.
    for field in ('og:image:alt', 'twitter:image:alt'):
        src = re.sub(
            rf'(<meta\s+(?:property|name)="{re.escape(field)}"\s+content=")[^"]*(")',
            lambda m: m.group(1) + html_lib.escape(title, quote=True) + m.group(2),
            src,
            flags=re.I,
        )
    # article:tag — articles typically have TWO `<meta property="article:tag">`
    # entries (ZH + EN). On the EN mirror strip the ZH one (any tag whose
    # content contains CJK characters). Run twice to handle adjacent matches.
    cjk_tag_re = re.compile(
        r'<meta\s+property="article:tag"\s+content="[^"]*[一-鿿][^"]*"\s*/?>\s*',
        re.I,
    )
    for _ in range(3):
        new = cjk_tag_re.sub('', src)
        if new == src:
            break
        src = new
    # name="keywords" — comma-separated list often mixes ZH + EN keywords.
    # Drop the CJK-bearing entries, keep the EN ones. If nothing EN survives,
    # fall back to a minimal generic list (Google ignores meta keywords for
    # ranking, but lint/auditors flag CJK in /en/).
    def _clean_keywords(m: re.Match) -> str:
        content = m.group(2)
        parts = [k.strip() for k in content.split(',')]
        en_parts = [k for k in parts if k and not re.search(r'[一-鿿]', k)]
        if not en_parts:
            en_parts = ['dermatology', 'patient education']
        return m.group(1) + ', '.join(en_parts) + m.group(3)
    src = re.sub(
        r'(<meta\s+name="keywords"\s+content=")([^"]*)(")',
        _clean_keywords,
        src,
        flags=re.I,
    )
    return src


def set_noindex(src: str) -> str:
    # 2026-05-18 — include max-image-preview:large + max-snippet:-1 even
    # on noindex pages. Reason: if the page is later flipped to indexable
    # (e.g. translation backfilled), Google sees the SERP directives
    # immediately on the next crawl. Costs nothing on a noindex page.
    content = 'noindex,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1'
    if re.search(r'<meta\s+name="robots"\s+content="[^"]*"', src, re.I):
        src = re.sub(
            r'(<meta\s+name="robots"\s+content=")[^"]*(")',
            r'\1' + content + r'\2',
            src,
            count=1,
            flags=re.I,
        )
    else:
        src = src.replace('</head>', f'<meta name="robots" content="{content}" /></head>', 1)
    # Strip third-party analytics/ads on noindex pages — _check_third_party.py
    # forbids loading AdSense / GA4 / Clarity on noindex/internal pages. Both
    # the inline late-loader <script> block and the static <meta> / <script src>
    # references need to be removed (substring presence alone fails the audit).
    src = re.sub(
        r'<meta\s+name="google-adsense-account"[^>]*/?>',
        '',
        src,
        flags=re.I,
    )
    # Any <script> block (inline or external) that references the three trackers
    src = re.sub(
        r'<script(?:\s[^>]*)?>(?:(?!</script>).)*?(?:pagead2\.googlesyndication\.com|www\.clarity\.ms|googletagmanager\.com/gtag)(?:(?!</script>).)*?</script>',
        '',
        src,
        flags=re.I | re.S,
    )
    src = re.sub(
        r'<script[^>]*src="[^"]*(?:adsbygoogle\.js|googletagmanager\.com/gtag/js|clarity\.ms/tag)[^"]*"[^>]*>\s*</script>',
        '',
        src,
        flags=re.I,
    )
    return src


def is_noindex(src: str) -> bool:
    m = re.search(r'<meta\s+name="robots"\s+content="([^"]*)"', src, re.I)
    return bool(m and 'noindex' in m.group(1).lower())


def hreflang_cluster(zh_canonical_path: str, en_canonical_path: str | None) -> str:
    lines = [
        f'<link rel="alternate" hreflang="x-default" href="{DOMAIN}{zh_canonical_path}" />',
        f'<link rel="alternate" hreflang="zh-Hant" href="{DOMAIN}{zh_canonical_path}" />',
        f'<link rel="alternate" hreflang="zh-Hant-TW" href="{DOMAIN}{zh_canonical_path}" />',
    ]
    if en_canonical_path:
        lines.append(f'<link rel="alternate" hreflang="en" href="{DOMAIN}{en_canonical_path}" />')
    return '\n'.join(lines)


def replace_hreflang_cluster(src: str, cluster: str | None) -> str:
    pattern = r'(<link\s+rel="alternate"\s+hreflang="[^"]*"\s+href="[^"]*"\s*/?>\s*)+'
    if re.search(pattern, src, re.I):
        return re.sub(pattern, (cluster + '\n') if cluster else '', src, count=1, flags=re.I)
    if cluster:
        return src.replace('</head>', cluster + '\n</head>', 1)
    return src


def extract_faqs(src: str) -> list[dict[str, object]]:
    faqs = []
    for m in re.finditer(r'<details\b[^>]*>([\s\S]*?)</details>', src, re.I):
        body = m.group(1)
        sm = re.search(r'<summary\b[^>]*>([\s\S]*?)</summary>', body, re.I)
        if not sm:
            continue
        q = strip_tags(sm.group(1))
        a = strip_tags(body[:sm.start()] + body[sm.end():])
        if q and a and not has_cjk(q + a) and len(a) > 10:
            faqs.append({
                '@type': 'Question',
                'name': q,
                'acceptedAnswer': {'@type': 'Answer', 'text': a[:5000]},
            })
    return faqs


def localize_jsonld(src: str, title: str, desc: str) -> str:
    faqs = extract_faqs(src)

    def patch_block(match):
        opening_tag = match.group(1)  # full opening tag, e.g. `<script type="..." id="dn-citations">`
        raw = match.group(2)
        try:
            obj = json.loads(raw)
        except Exception:
            return match.group(0)

        if isinstance(obj, dict):
            typ = obj.get('@type')
            if typ == 'FAQPage':
                if not faqs:
                    return ''
                obj['mainEntity'] = faqs
            if typ == 'BreadcrumbList':
                items = obj.get('itemListElement') or []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_url = item.get('item', '')
                    if item.get('position') == 1:
                        item['name'] = 'Home'
                    elif item_url.endswith('/blog/') or item.get('position') == 2:
                        item['name'] = 'Articles'
                    else:
                        item['name'] = title.split('|')[0].strip()
            if 'inLanguage' in obj:
                obj['inLanguage'] = 'en'
            if typ in {'Article', 'BlogPosting', 'MedicalScholarlyArticle', 'MedicalWebPage', 'WebPage'}:
                if 'headline' in obj:
                    obj['headline'] = title
                if 'name' in obj:
                    obj['name'] = title
                if 'description' in obj:
                    obj['description'] = desc

        # Preserve the original opening tag so attributes like
        # id="dn-citations" / id="dn-drug-schema" survive mirroring. Without
        # this, _normalize_citations.py + _normalize_drug_schema.py can't
        # find the existing block on subsequent runs and inject duplicates.
        return opening_tag + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '</script>'

    return re.sub(
        r'(<script\s+type="application/ld\+json"[^>]*>)([\s\S]*?)</script>',
        patch_block, src, flags=re.I,
    )


# 2026-05-24 — aria-label translations for SVG figures and other elements
# whose ZH aria-label would otherwise be announced to EN screen-reader
# users. Only translates aria-label values that exactly match a key here;
# unrecognized ZH aria-labels are left as-is (better than a wrong gloss).
ARIA_LABEL_TRANSLATIONS: dict[str, str] = {
    "手腳病灶 × 甲狀腺疾病 2x2 風險矩陣":
        "2x2 risk matrix: hand/foot lesions × thyroid disease — adjusted hazard ratios for vitiligo relapse",
    "患者篩選流程圖":
        "Patient screening flow diagram for the Chang Gung database vitiligo cohort",
    "PDT 三要素與分子機轉：光敏劑 + 光 + 氧氣 → ROS → 細胞凋亡 / 血管損傷 / 免疫活化":
        "PDT three essential elements and molecular mechanism: photosensitizer + light + oxygen → ROS → apoptosis / vascular damage / immune activation",
    "ALA 與 MAL 經 heme 合成路徑代謝為 PpIX 的示意":
        "Schematic: ALA and MAL metabolism via the heme biosynthesis pathway to PpIX",
    "藍光、綠光、紅光與紅外光在皮膚的穿透深度比較":
        "Comparison of penetration depth in skin: blue light, green light, red light, and near-infrared",
    "PDT 12 適應症按證據等級階梯":
        "PDT 12 indications ranked by evidence level on a tiered ladder",
    "PDT 疼痛管理策略階梯":
        "PDT pain-management strategy ladder",
    "疥蟲生命週期與隧道圖：雌蟲在角質層挖隧道產卵，3-4 天孵化，2-3 週成蟲，整個週期 2-3 週":
        "Scabies mite life cycle and burrow diagram: female mite tunnels in stratum corneum and lays eggs; eggs hatch in 3-4 days; adult in 2-3 weeks; full cycle 2-3 weeks",
    "嚴重疥瘡兩型對照圖：廣泛型 profuse scabies 是疥蟲擴散到頭背等不典型部位的紅斑脫屑；結痂型 crusted scabies 是免疫低下患者皮膚出現像乾癬般厚痂、內含數千隻疥蟲":
        "Comparison of two severe scabies subtypes: profuse scabies (mites spread to atypical sites like head and back with erythematous scaling) versus crusted scabies (hyperkeratotic crusted plaques with thousands of mites)",
    "嚴重疥瘡標準治療時程圖：Day 0 ivermectin 200 μg/kg + permethrin 全身塗抹、Day 7 同上、Day 14 ivermectin、Day 18-21 顯微鏡複查、Day 28 治癒判定":
        "Severe scabies standard treatment schedule: Day 0 ivermectin 200 μg/kg + permethrin head-to-toe; Day 7 repeat; Day 14 ivermectin; daily emollient",
    "三組 EASI / SCORAD / pruritus NRS 在 T0、T1、T2 三時間點的柱狀比較圖：長期組第 52 週下降最多；短期組停藥後維持但不再進步；減量組介於兩者之間":
        "Three side-by-side bar charts (EASI / SCORAD / pruritus NRS) at three time points T0 / T1 / T2: the long-term q2w arm shows the greatest decrease by week 52; the short-term arm maintains effect after stopping but does not improve further.",
    "Kaplan-Meier 風格曲線示意：長期 q2w 組 52 週累積無復發率明顯高於短期與減量兩組，部分長期組病人 300 天以上仍無復發":
        "Kaplan-Meier-style curve: cumulative relapse-free rate at 52 weeks is markedly higher in the long-term q2w arm than in the short-term or tapering arms; some long-term patients remain relapse-free beyond 300 days.",
    "五種異位性皮膚炎表型示意圖：classic 對稱屈側、廣泛苔癬化、廣泛發炎、錢幣狀濕疹樣、痒疹結節樣":
        "Five atopic dermatitis phenotypes: classic symmetric flexural, generalized lichenified, generalized inflammatory, nummular eczema-like, and prurigo nodular-like.",
    "Herrera 2026 JAAD：semaglutide / tirzepatide 各種掉髮新發風險 forest plot":
        "Herrera 2026 JAAD: forest plot of relative risks for various new-onset hair-loss types in semaglutide / tirzepatide users",
    "Hill 2026 JAAD：GLP-1 / GIP 對疤痕性禿髮患者各種治療使用率 forest plot":
        "Hill 2026 JAAD: forest plot of treatment-utilization rates for scarring alopecia patients on GLP-1 / GIP",
    "兩篇研究 2x2 概念圖：族群 × 結果":
        "2x2 concept matrix of the two studies: population × outcome",
    "GLP-1RA 對毛囊的雙路徑機轉假說":
        "GLP-1RA dual-pathway hypothesis on hair follicle",
    "GLP-1RA 使用後新發掉髮 RR 隨時間累積":
        "New-onset hair-loss RR accumulating over time after GLP-1RA initiation",
    "口腔黏膜三類分佈圖：硬顎與牙齦為角化的咀嚼性黏膜（粉紅），頰、舌腹、口底、軟顎為非角化的鬆軟黏膜（米黃），舌背與唇紅為特化黏膜（橘紅）":
        "Oral mucosa zones (3 types): keratinized masticatory mucosa over hard palate and gingiva (pink); non-keratinized lining mucosa over buccal, ventral tongue, floor of mouth, and soft palate (cream); specialized mucosa over dorsal tongue and lip vermilion (orange-red).",
    "6 種口腔黏膜疾病示意圖：口腔扁平苔癬白色蕾絲紋路、復發性口瘡圓形潰瘍、口腔白斑均勻白色斑塊、類天疱瘡牙齦剝離與血皰、光線性唇炎下唇粗糙、口腔黑色素斑":
        "6 oral mucosal diseases at a glance: oral lichen planus (white lacy reticulations), recurrent aphthous stomatitis (round ulcer), oral leukoplakia (uniform white patch), mucous membrane pemphigoid (desquamative gingivitis with blood blisters), actinic cheilitis (rough lower lip), and oral melanotic macule.",
    "口腔症狀分流決策圖：依症狀類型導向牙科、皮膚科或口腔外科／耳鼻喉科":
        "Oral symptom triage decision flow: by symptom type, route to dentistry, dermatology, or oral & maxillofacial surgery / ENT.",
    "口腔切片器械與兩種切片技術示意圖：punch trephine 環形切片與 15 號刀片條狀切片":
        "Oral biopsy instruments and two techniques: punch trephine (circular biopsy) and #15 blade (strip biopsy).",
    "USPSTF 證據評級熱度圖：13 項常見篩檢 × 5 個生物製劑類別。深綠 B = 建議；淺綠 C = 個別考量；橘 D = 不建議；灰 I = 證據不足。TNF-α 在結核（B）與 HBV（C）為主要建議；IL-17 在念珠菌與 IBD（C）為主要建議；IL-12/23、IL-23 p19 幾乎全 D；HIV 全 I":
        "USPSTF evidence-grade summary: 13 routine pre-biologic labs across 5 biologic classes. Green B = recommended; uncolored C = case-by-case; red D = not recommended; gray I = insufficient evidence. TNF-α has the most stringent annual TB + HBV recommendations; IL-17 highlights mucocutaneous fungal infection and IBD considerations; IL-12/23 and IL-23 p19 are mostly D; HIV is I.",
    "慢性 B 肝乾癬病人接受生物製劑的 reactivation 風險柱狀比較：未抗病毒預防約 26%、抗病毒預防（entecavir 或 tenofovir）約 7.7%；secukinumab + 預防、ustekinumab + 預防在現有資料中無復活個案；TNF-α 仍有少數復活個案":
        "Bar chart of biologic-associated HBV reactivation risk in psoriasis patients with chronic HBV carriage: 26% without antiviral prophylaxis; 7.7% with antiviral prophylaxis (entecavir or tenofovir); secukinumab + prophylaxis and ustekinumab + prophylaxis show no reactivation cases in current data; TNF-α inhibitors have the most reactivation events.",
    "生物製劑類別決策樹：拿到哪一支生物製劑、要做哪些篩檢與門診詢問。TNF-α → 結核每年 + B 肝；IL-12/23 與 IL-23 → 依個別風險；IL-17 → 問口腔念珠菌 + 腸道症狀。":
        "Biologic class decision tree: required screening and mechanism-of-action questions before initiating any biologic. TNF-α → strict annual TB + HBV screening; IL-12/23 and IL-23 → individual-risk based; IL-17 → mucocutaneous fungal infection prophylaxis + IBD considerations.",
}


def translate_aria_labels(src: str) -> str:
    """Swap ZH aria-label values for known EN translations."""
    def repl(m: re.Match) -> str:
        label = m.group(1)
        en = ARIA_LABEL_TRANSLATIONS.get(label)
        if en:
            return f'aria-label="{html_lib.escape(en, quote=True)}"'
        return m.group(0)
    return re.sub(r'aria-label="([^"]+)"', repl, src)


# 2026-05-25 — EN hub pages (en/blog/index.html, en/blog/topics.html) had
# Blog / CollectionPage JSON-LD whose `name`/`description`/`url` were still
# ZH, falsely advertising the EN page as Chinese content. Swap to clean
# EN equivalents during the EN mirror generation.
EN_HUB_JSONLD_SWAPS: dict[str, str] = {
    # blog/index.html → en/blog/index.html: Blog @type
    '{"@context":"https://schema.org","@type":"Blog","name":"ChenDermatologist 部落格","url":"https://chendermatologist.com/blog/","description":"陳翊嘉醫師（皮膚科）整理的皮膚科衛教文章。","publisher":{"@type":"Person","name":"陳翊嘉 醫師","url":"https://chendermatologist.com/"}}':
        '{"@context":"https://schema.org","@type":"Blog","name":"ChenDermatologist Blog","url":"https://chendermatologist.com/en/blog","description":"Plain-language dermatology articles by Dr. Yi-Jia Chen.","inLanguage":"en","publisher":{"@type":"Person","name":"Dr. Yi-Jia Chen","url":"https://chendermatologist.com/en/"}}',
    # blog/topics.html → en/blog/topics.html: CollectionPage @type
    # NB: source uses inLanguage zh-TW; swap to en for the mirror.
    '{"@context":"https://schema.org","@type":"CollectionPage","name":"皮膚科主題地圖 | ChenDermatologist","url":"https://chendermatologist.com/blog/topics","description":"所有皮膚科衛教文章按主題整理 — 痘痘、防曬、異膚、肝斑、酸類、A 酸、落髮、香港腳。","inLanguage":"zh-TW","isPartOf":{"@type":"WebSite","name":"ChenDermatologist","url":"https://chendermatologist.com/"},"publisher":{"@type":"Person","name":"陳翊嘉 醫師","url":"https://chendermatologist.com/"}}':
        '{"@context":"https://schema.org","@type":"CollectionPage","name":"Dermatology Topic Map | ChenDermatologist","url":"https://chendermatologist.com/en/blog/topics","description":"All dermatology patient-education articles organized by topic — acne, sunscreen, atopic dermatitis, melasma, acids, retinoids, hair loss, tinea pedis.","inLanguage":"en","isPartOf":{"@type":"WebSite","name":"ChenDermatologist","url":"https://chendermatologist.com/"},"publisher":{"@type":"Person","name":"Dr. Yi-Jia Chen","url":"https://chendermatologist.com/en/"}}',
}


def translate_hub_jsonld(src: str) -> str:
    """Replace ZH Blog/CollectionPage JSON-LD on EN hub pages with EN."""
    for zh, en in EN_HUB_JSONLD_SWAPS.items():
        if zh in src:
            src = src.replace(zh, en)
    return src


def transform(src: str, zh_canonical_path: str, en_canonical_path: str, source_rel: str | None = None) -> str:
    s = apply_data_en(src)
    s = translate_aria_labels(s)
    s = translate_hub_jsonld(s)
    s = prefer_static_english_blocks(s)
    if source_rel == 'privacy.html':
        s = replace_privacy_body(s)
    en_title, en_desc = derive_meta(s, EN_OG_OVERRIDES.get(source_rel or ''))
    uses_generic_meta = (
        en_title == 'Dermatology Patient Education | ChenDermatologist'
        or en_desc == FALLBACK_EN_DESC
    )
    s = set_meta(s, en_title, en_desc)
    s = localize_jsonld(s, en_title, en_desc)
    # 2026-05-17 — user opted in to EN indexing. Default is now INDEXABLE;
    # we only force noindex when the EN page fails a quality guard:
    #   - generic meta (title/desc still has zh fallback)
    #   - too much visible CJK left after applyTextOnly (means data-en
    #     translations are missing for big chunks; that page renders as zh
    #     in English locale → low-quality penalty risk)
    # When a specific slug needs to stay noindex (e.g. an in-progress
    # translation), add it to EN_NOINDEX_BLOCKLIST below.
    #
    # 2026-05-26 — added EN_INDEX_ALLOWLIST for explicitly bilingual reference
    # pages (Mandarin↔English glossary, calculator tools listing the Chinese
    # generic name alongside English term, EN homepage hub). These trip the
    # 500-CJK threshold by design but the title/description/structured data
    # are still pure English — Google's Search Console kept flagging them as
    # "Excluded by noindex tag", which was technically correct but blocked
    # the entire /en/ subtree from earning crawl signal via the EN home hub.
    # The generic-meta guard still applies (a page with fallback title/desc
    # stays noindex even if allowlisted — that's a stronger quality signal).
    EN_NOINDEX_BLOCKLIST: set[str] = set()
    EN_INDEX_ALLOWLIST: set[str] = {
        'index.html',     # EN homepage hub
        'tools.html',     # Clinical calculator landing (PASI/DLQI/SCORAD…)
        'glossary.html',  # Mandarin↔English dermatology glossary
    }
    blocked = (source_rel or '') in EN_NOINDEX_BLOCKLIST
    allow_high_cjk = (source_rel or '') in EN_INDEX_ALLOWLIST
    if blocked or uses_generic_meta or (not allow_high_cjk and visible_cjk_count(s) > 500):
        s = set_noindex(s)

    s = re.sub(r'<html\s+lang="[^"]*"', '<html lang="en"', s, count=1)

    new_canonical = f'{DOMAIN}{en_canonical_path}'
    s = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
        f'<link rel="canonical" href="{new_canonical}" />',
        s,
        count=1,
    )
    s = re.sub(
        r'(<meta\s+property="og:url"\s+content=")[^"]*(")',
        lambda m: m.group(1) + new_canonical + m.group(2),
        s,
        count=1,
        flags=re.I,
    )

    s = replace_hreflang_cluster(s, None if is_noindex(s) else hreflang_cluster(zh_canonical_path, en_canonical_path))

    s = re.sub(
        r'(<script\s+src="/blog/blog-shared(?:\.min)?\.js[^"]*"[^>]*></script>)',
        EN_LANG_BOOTSTRAP + '\n\\1',
        s,
    )
    s = rewrite_en_internal_links(s)

    if '<main id="main-content">' in s:
        s = s.replace('<main id="main-content">', '<main id="main-content">\n' + EN_BANNER, 1)
    else:
        s = re.sub(r'(</header>)', r'\1\n' + EN_BANNER, s, count=1)

    s = re.sub(r'<meta property="og:locale" content="[^"]*" ?/?>', '<meta property="og:locale" content="en_US" />', s, count=1)
    s = re.sub(r'<meta property="og:locale:alternate" content="[^"]*" ?/?>', '<meta property="og:locale:alternate" content="zh_TW" />', s, count=1)
    return s


def sync_source_hreflang(pairs: list[tuple[str, str, str]]) -> int:
    changed = 0
    for source_file, zh_canonical, en_canonical in pairs:
        en_file = os.path.join(ROOT, en_canonical.strip('/').replace('/', os.sep) + '.html')
        if en_canonical == '/en/':
            en_file = os.path.join(ROOT, 'en', 'index.html')
        # CODE_REVIEW — use Path.read_text() context-manager equivalent
        # so file handle is released immediately. Previous open(...).read()
        # leaked handles on long runs (60+ articles per call).
        en_indexable = False
        if os.path.exists(en_file):
            en_indexable = not is_noindex(Path(en_file).read_text(encoding='utf-8'))
        cluster = hreflang_cluster(zh_canonical, en_canonical if en_indexable else None)
        with open(source_file, 'r', encoding='utf-8') as fp:
            src = fp.read()
        next_src = replace_hreflang_cluster(src, cluster)
        if next_src != src:
            with open(source_file, 'w', encoding='utf-8') as fp:
                fp.write(next_src)
            changed += 1
    return changed


def get_unpublished_slugs() -> set[str]:
    """Read blog-shared.js and return slugs that have {unpublished:true} in
    the DN.ARTICLES catalog. Matches _gen_feeds.get_unpublished_slugs."""
    js_path = os.path.join(ROOT, 'blog', 'blog-shared.js')
    try:
        with open(js_path, 'r', encoding='utf-8') as fh:
            src = fh.read()
    except FileNotFoundError:
        return set()
    m = re.search(r"DN\.ARTICLES\s*=\s*\[([\s\S]*?)\];", src)
    if not m:
        return set()
    unpublished: set[str] = set()
    for line in m.group(1).splitlines():
        if not re.search(r"\bunpublished\s*:\s*true\b", line):
            continue
        slug_m = re.search(r"slug:'([^']+)'", line)
        if slug_m:
            unpublished.add(slug_m.group(1))
    return unpublished


def main() -> None:
    n = 0
    pairs: list[tuple[str, str, str]] = []
    en_dir = os.path.join(ROOT, 'en')
    blog_en_dir = os.path.join(en_dir, 'blog')
    os.makedirs(blog_en_dir, exist_ok=True)
    unpublished = get_unpublished_slugs()
    if unpublished:
        print(f'Skipping unpublished slugs from /en/ mirror: {sorted(unpublished)}')

    top_files = [f for f in os.listdir(ROOT) if f.endswith('.html') and f not in SKIP and not f.startswith('_')]
    for f in top_files:
        zh_path = os.path.join(ROOT, f)
        if f == 'index.html':
            zh_canonical = '/'
            en_canonical = '/en/'
        else:
            stem = f[:-5]
            zh_canonical = '/' + stem
            en_canonical = '/en/' + stem
        with open(zh_path, 'r', encoding='utf-8') as fp:
            html = fp.read()
        en_html = transform(html, zh_canonical, en_canonical, source_rel=f)
        with open(os.path.join(en_dir, f), 'w', encoding='utf-8') as fp:
            fp.write(en_html)
        pairs.append((zh_path, zh_canonical, en_canonical))
        n += 1

    blog_dir = os.path.join(ROOT, 'blog')
    blog_files = [f for f in os.listdir(blog_dir) if f.endswith('.html')]
    for f in blog_files:
        # Always regenerate the EN mirror (even for unpublished articles).
        # Unpublished articles still need a /en/ URL because:
        #  (a) the homepage / index static HTML still links to them, and the
        #      internal-link audit would fail if the target page is missing;
        #  (b) admin can still navigate to the article; the runtime banner +
        #      hide-unpublished-cards CSS hide them from public listings.
        zh_path = os.path.join(blog_dir, f)
        if f == 'index.html':
            zh_canonical = '/blog'
            # 2026-05-25 — drop trailing slash to match (a) sitemap.xml
            # entry "/en/blog" (no slash) and (b) ZH canonical style. The
            # inconsistency caused _check_sitemap.py to fail on hreflang
            # vs canonical mismatch.
            en_canonical = '/en/blog'
        else:
            stem = f[:-5]
            zh_canonical = '/blog/' + stem
            en_canonical = '/en/blog/' + stem
        with open(zh_path, 'r', encoding='utf-8') as fp:
            html = fp.read()
        en_html = transform(html, zh_canonical, en_canonical, source_rel='blog/' + f)
        with open(os.path.join(blog_en_dir, f), 'w', encoding='utf-8') as fp:
            fp.write(en_html)
        pairs.append((zh_path, zh_canonical, en_canonical))
        n += 1

    print(f'Generated {n} /en/ pages')
    changed = sync_source_hreflang(pairs)
    if changed:
        print(f'Updated hreflang clusters in {changed} source pages')


if __name__ == '__main__':
    main()
