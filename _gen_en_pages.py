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
import html as html_lib
from html.parser import HTMLParser


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
        'title': 'Toenail Mechanical & Structural Disorders: 12-Type Atlas + Diabetic Foot',
        'desc': 'Over 90% of toenail dystrophy is mechanical, not fungal. Patient-friendly guide to the 12 most common types (onycholysis, subungual heloma, Beau lines, retronychia, pincer nail, onychocryptosis, etc.), 4 foot deformities (Morton toe, hallux valgus, flat foot, splayfoot), diabetic nail care, and Taiwan NHI coverage. Integrates Ricardo 2026 JAAD review.',
    },
    'blog/dermatologic-oral-examination.html': {
        'title': 'Oral Mucosa: When to See a Dermatologist Instead of a Dentist | Exam & Biopsy Guide',
        'desc': 'An ulcer not healing in 2 weeks, white lacy oral patches, or peeling gums often belong to dermatology, not dentistry. Patient-friendly guide to 6 oral mucosal conditions (oral lichen planus, recurrent aphthous stomatitis, leukoplakia, mucous membrane pemphigoid, actinic cheilitis, oral pigmented lesions), Taiwan-specific epidemiology (betel-related leukoplakia, OLP prevalence trends), dermatologic oral exam steps, biopsy timing and technique, and AHA 2021 antibiotic prophylaxis. Integrates Klein & Aristizabal 2026 JAAD CME.',
    },
    'blog/severe-scabies-treatment.html': {
        'title': 'Severe Scabies: Complete Oral Ivermectin + 5% Permethrin Treatment Guide',
        'desc': 'Severe scabies (profuse or crusted, with hundreds to thousands of mites) does not respond to single-dose treatment. Patient-friendly guide based on the May 2026 NEJM GALE CRUSTED randomized trial: standard regimen is ivermectin 200 μg/kg on Days 0, 7, 14 plus 5% permethrin head-to-toe on Days 0 and 7 plus daily emollient — Day 28 cure rate around 82%. Covers life cycle, household co-treatment, environmental cleaning, long-term care outbreak protocols, infant/pregnancy safety, and Taiwan drug availability.',
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


def apply_data_en(src: str) -> str:
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f'__DN_EN_PROTECTED_BLOCK_{len(protected) - 1}__'

    # HTMLParser lowercases foreign-content end tags such as linearGradient.
    # Keep SVG/script/style bytes intact and only render bilingual HTML around them.
    guarded = re.sub(r'<(svg|script|style)\b[\s\S]*?</\1>', stash, src, flags=re.I)
    rendered = DataEnRenderer().render(guarded)
    for index, block in enumerate(protected):
        rendered = rendered.replace(f'__DN_EN_PROTECTED_BLOCK_{index}__', block)
    return rendered


def prefer_static_english_blocks(src: str) -> str:
    """For /en/ pages, remove hidden Chinese article bodies when proseEn exists."""

    src = re.sub(
        r'<div\s+id="proseZh"\s+class="prose">[\s\S]*?(<div\s+id="proseEn"\s+class="prose")\s+style="display:none"',
        r'\1',
        src,
        count=1,
        flags=re.I,
    )
    src = re.sub(
        r'<div\s+id="proseZh"\s+class="prose">[\s\S]*?(<div\s+id="proseEn"\s+class="prose")',
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


def visible_cjk_count(src: str) -> int:
    return len(re.findall(r'[\u4e00-\u9fff]', strip_tags(src)))


def has_cjk(src: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', src or ''))


def first_text(pattern: str, src: str) -> str:
    m = re.search(pattern, src, re.I | re.S)
    return strip_tags(m.group(1)) if m else ''


def derive_meta(src: str, override: dict[str, str] | None) -> tuple[str, str]:
    h1 = first_text(r'<h1\b[^>]*>([\s\S]*?)</h1>', src)
    title = (override or {}).get('title') or (h1 + ' | ChenDermatologist' if h1 else '')
    if not title or has_cjk(title):
        title = 'Dermatology Patient Education | ChenDermatologist'
    if len(title) > 72:
        title = title[:69].rsplit(' ', 1)[0].rstrip(' ,.;:|-') + '...'

    lead = (override or {}).get('desc') or ''
    h1_pos = src.lower().find('</h1>')
    if not lead and h1_pos >= 0:
        lead = first_text(r'<p\b[^>]*>([\s\S]*?)</p>', src[h1_pos:])
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
    src = re.sub(r'(<meta\s+name="description"\s+content=")[^"]*(")', r'\1' + esc_desc + r'\2', src, count=1, flags=re.I)
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
    return src


def set_noindex(src: str) -> str:
    content = 'noindex,follow'
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
        raw = match.group(1)
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

        return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '</script>'

    return re.sub(r'<script\s+type="application/ld\+json"[^>]*>([\s\S]*?)</script>', patch_block, src, flags=re.I)


def transform(src: str, zh_canonical_path: str, en_canonical_path: str, source_rel: str | None = None) -> str:
    s = apply_data_en(src)
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
    # AdSense audit period: force noindex on ALL en/ mirrors. They are machine-
    # translated from data-en attrs and risk being scored as low-quality. Once
    # AdSense approves and an article gets a real human translation, opt that
    # specific page out by listing it in EN_INDEX_ALLOWLIST below.
    EN_INDEX_ALLOWLIST: set[str] = set()
    force_noindex = (source_rel or '') not in EN_INDEX_ALLOWLIST
    if force_noindex or uses_generic_meta or visible_cjk_count(s) > 500:
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
        en_indexable = os.path.exists(en_file) and not is_noindex(open(en_file, 'r', encoding='utf-8').read())
        cluster = hreflang_cluster(zh_canonical, en_canonical if en_indexable else None)
        with open(source_file, 'r', encoding='utf-8') as fp:
            src = fp.read()
        next_src = replace_hreflang_cluster(src, cluster)
        if next_src != src:
            with open(source_file, 'w', encoding='utf-8') as fp:
                fp.write(next_src)
            changed += 1
    return changed


def main() -> None:
    n = 0
    pairs: list[tuple[str, str, str]] = []
    en_dir = os.path.join(ROOT, 'en')
    blog_en_dir = os.path.join(en_dir, 'blog')
    os.makedirs(blog_en_dir, exist_ok=True)

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
        zh_path = os.path.join(blog_dir, f)
        if f == 'index.html':
            zh_canonical = '/blog'
            en_canonical = '/en/blog/'
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
