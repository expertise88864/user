"""Generate the board-exam review section (/exam/**) from data/exam/.

Sources (hand-maintained):
  data/exam/questions.json     750 MCQs, built by _exam_import.py
  data/exam/tags.json          question id -> Fitzpatrick chapters / McKee / Kantor
  data/exam/explanations.json  per-question explanations with Fitzpatrick page refs
  data/exam/notes/fitz-<n>.frag  chapter study notes (trusted HTML fragments)
  data/exam/fitz_chapters.json chapter titles and printed page ranges
  data/exam/links.json         chapter DermNet / PathologyOutlines links
  data/exam/search_aliases.json  chapter -> standard abbreviations for the hub search

Outputs (generated, never hand-edit):
  exam/index.html, exam/fitz-<n>.html, exam/year-<y>.html, exam/mckee.html,
  exam/kantor.html, exam/review.html, exam/exam-data.json, exam/search-index.json

Pages reuse the normalized notes.html shell (head, header, footer), and the
output is already in its final normalized form. REGEN_STEPS runs it twice:
early (so the sitemap and normalizers see every page) and last (after every
step that edits notes.html); `--check` in CHECK_STEPS proves the committed
exam/** matches. It rewrites every output from scratch.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "exam"
OUT = ROOT / "exam"
DOMAIN = "https://chendermatologist.com"
TEMPLATE = ROOT / "notes.html"
SOURCE_LABEL = "臺灣皮膚科醫學會專科醫師甄審筆試"
SOURCE_URL = "https://www.derma.org.tw/specialist/download.php?id=9"
HUB_TITLE = "皮膚科專科醫師考試重點及考題"
REFERENCE_BOOKS = [
    "McKee's Pathology of the Skin, 6th Edition (2026/7/21)",
    "Fitzpatrick's Dermatology in General Medicine, 9th Edition (2019/3/19)",
    "Dermatologic Surgery (by Jonathan Kantor) 1st Edition (2018/6/9)",
]
OTHER_BOOKS = {
    "mckee": ("McKee's Pathology of the Skin", "病理"),
    "kantor": ("Dermatologic Surgery (Kantor)", "皮膚外科"),
}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


ITALIC = re.compile(r"\[i\](.+?)\[/i\]")


def rich(text: str) -> str:
    """Escape explanation text; [i]Genus species[/i] becomes <em> (organism names)."""
    return ITALIC.sub(r"<em>\1</em>", esc(text))


def esc_lines(text: str) -> str:
    return "<br>".join(esc(line) for line in text.split("\n"))


def load() -> dict:
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    tags = json.loads((DATA / "tags.json").read_text(encoding="utf-8"))
    explanations = json.loads((DATA / "explanations.json").read_text(encoding="utf-8"))
    chapters = {c["chapter"]: c for c in json.loads((DATA / "fitz_chapters.json").read_text(encoding="utf-8"))}
    missing = [q["id"] for q in questions if q["id"] not in tags]
    if missing:
        raise SystemExit(f"tags.json is missing {len(missing)} questions, e.g. {missing[:5]}")
    unknown = [k for k in explanations if k not in {q['id'] for q in questions}]
    if unknown:
        raise SystemExit(f"explanations.json has unknown ids {unknown}")
    notes = {}
    # Notes are trusted HTML fragments, kept as .frag so page audits do not
    # mistake them for standalone pages.
    for path in sorted((DATA / "notes").glob("fitz-*.frag")):
        notes[int(path.stem.split("-")[1])] = path.read_text(encoding="utf-8")
    links_path = DATA / "links.json"
    links = {int(k): v for k, v in json.loads(links_path.read_text(encoding="utf-8")).items()} if links_path.exists() else {}
    aliases_path = DATA / "search_aliases.json"
    aliases = ({int(k): v for k, v in json.loads(aliases_path.read_text(encoding="utf-8")).items()}
               if aliases_path.exists() else {})
    bad = [k for k in aliases if k not in chapters]
    if bad:
        raise SystemExit(f"search_aliases.json has unknown chapters {bad}")
    return {"questions": questions, "tags": tags, "explanations": explanations,
            "chapters": chapters, "notes": notes, "links": links, "aliases": aliases}


# ---------------------------------------------------------------- page shell

def split_template() -> tuple[str, str, str]:
    src = TEMPLATE.read_text(encoding="utf-8")
    head_end = src.index("</head>")
    main_start = src.index('<main id="main-content">')
    main_end = src.index("</main>") + len("</main>")
    return src[:head_end], src[head_end:main_start], src[main_end:]


def set_head(head: str, *, title: str, description: str, path: str, og_title: str,
             jsonld: list[dict]) -> str:
    url = DOMAIN + path
    subs = [
        (r"<title>.*?</title>", f"<title>{esc(title)}</title>"),
        (r'<meta name="robots" content="[^"]*" />',
         '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1" />'),
        (r'<meta name="description" content="[^"]*" />', f'<meta name="description" content="{esc(description)}" />'),
        (r'<link rel="canonical" href="[^"]*" />', f'<link rel="canonical" href="{url}" />'),
        (r'<meta property="og:url" content="[^"]*" />', f'<meta property="og:url" content="{url}" />'),
        (r'<meta property="og:title" content="[^"]*" />', f'<meta property="og:title" content="{esc(og_title)}" />'),
        (r'<meta property="og:description" content="[^"]*" />', f'<meta property="og:description" content="{esc(description)}" />'),
        (r'<meta name="twitter:title" content="[^"]*" />', f'<meta name="twitter:title" content="{esc(og_title)}" />'),
    ]
    for pattern, repl in subs:
        head, n = re.subn(pattern, lambda _m, r=repl: r, head, count=1, flags=re.S)
        if n != 1:
            raise SystemExit(f"notes.html template is missing {pattern}")
    blocks = "".join(
        '<script type="application/ld+json">'
        + json.dumps(block, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        + "</script>\n"
        for block in jsonld
    )
    head, n = re.subn(r'(?:<script type="application/ld\+json">.*?</script>\s*)+', lambda _m: blocks, head, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("notes.html template has no JSON-LD block")
    head = head.replace("</head>", "")
    # _inject_nav_critical keeps its <style id="dn-nav-critical"> as the last
    # thing in <head>; inserting before it makes the raw output identical to
    # the normalized page, so this generator is order-independent and --check works.
    nav = head.rfind('<style id="dn-nav-critical"')
    if nav < 0:
        return head + EXAM_STYLE
    return head[:nav] + EXAM_STYLE + head[nav:]


def breadcrumb(items: list[tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": DOMAIN + path}
            for i, (name, path) in enumerate(items)
        ],
    }


def crumbs_html(items: list[tuple[str, str]]) -> str:
    parts = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            parts.append(f"<span>{esc(name)}</span>")
        else:
            parts.append(f'<a href="{path}">{esc(name)}</a>')
    sep = '<span class="ex-sep" aria-hidden="true">/</span>'
    return f'<nav class="crumbs" aria-label="麵包屑">{sep.join(parts)}</nav>'


DATA_VERSION = [""]  # content hash of exam-data.json, set by build() before any page renders


def script_version() -> str:
    """Content hash of exam/exam.js so browsers refetch it whenever it changes."""
    raw = (OUT / "exam.js").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:10]


def page(shell, *, path, title, description, og_title, crumbs, jsonld_type, body, page_kind, toc="") -> str:
    head, mid, tail = shell
    crumb_items = [("首頁", "/"), ("專科考試", "/exam")] + crumbs
    if path == "/exam":
        crumb_items = [("首頁", "/"), ("專科考試", "/exam")]
    jsonld = [
        {"@context": "https://schema.org", "@type": jsonld_type, "name": og_title,
         "description": description, "url": DOMAIN + path, "inLanguage": "zh-Hant-TW",
         "author": {"@type": "Person", "name": "陳翊嘉 醫師"},
         "audience": {"@type": "Audience", "audienceType": "皮膚科住院醫師"}},
        breadcrumb(crumb_items),
    ]
    out = set_head(head, title=title, description=description, path=path, og_title=og_title, jsonld=jsonld)
    content = f"{crumbs_html(crumb_items)}{body}"
    if toc:
        inner = f'<div class="ex-layout">{toc}<div class="ex-content">{content}</div></div>'
    else:
        inner = f'<div class="max-w-3xl mx-auto px-5 sm:px-8 pt-12 sm:pt-14 pb-16">{content}</div>'
    main = (f'<main id="main-content" class="ex-main" data-exam-page="{page_kind}" '
            f'data-exam-data="/exam/exam-data.json?v={DATA_VERSION[0]}">{inner}</main>')
    tail = tail.replace("</body>", f'<script src="/exam/exam.js?v={script_version()}" defer></script>\n</body>', 1)
    return out + mid + main + tail


NOTICE = (
    '<div class="ex-notice">題目取自'
    f'<a href="{SOURCE_URL}" target="_blank" rel="noopener noreferrer">{SOURCE_LABEL}試題</a>'
    "，答案為學會公告的標準答案；重點與詳解依據 Fitzpatrick's Dermatology, 9th Edition 與 "
    "McKee's Pathology of the Skin, 5th Edition 整理</div>"
)

MODE_BAR = (
    '<div class="ex-toolbar" role="group" aria-label="作答模式">'
    '<button type="button" class="ex-mode" data-mode="quiz" aria-pressed="false">作答模式</button>'
    '<button type="button" class="ex-mode" data-mode="browse" aria-pressed="true">瀏覽模式</button>'
    '<span class="ex-toolbar-hint">作答模式：選完送出才顯示詳解。瀏覽模式：直接顯示答案與詳解。</span>'
    "</div>"
)


# ---------------------------------------------------------------- questions

def chapter_title(ch: dict) -> str:
    return f"Ch.{ch['chapter']} {ch['title']}"


CHAPTER_PAGES: set[int] = set()  # chapters that get an exam/fitz-<n>.html page; set by build()


def ref_label(ref) -> str:
    chap, pages = ref
    return f"McKee 5e p.{pages}" if chap == "M" else f"Fitzpatrick 9e ch.{chap} p.{pages}"


def ref_html(ref, current_chapter: int | None, chapters: dict) -> str:
    chap, pages = ref
    label = ref_label(ref)
    if chap == "M":
        return f'<span class="ex-ref ex-ref-mckee">{esc(label)}</span>'
    if chap == current_chapter or chap not in CHAPTER_PAGES:
        return f'<span class="ex-ref">{esc(label)}</span>'
    return f'<a class="ex-ref" href="/exam/fitz-{chap}">{esc(label)}</a>'


def question_html(q: dict, data: dict, *, current_chapter: int | None = None, show_year=True) -> str:
    chapters = data["chapters"]
    tag = data["tags"][q["id"]]
    expl = data["explanations"].get(q["id"])
    qid = q["id"]
    chips = []
    for chap in tag["fitz"]:
        if chap == current_chapter:
            chips.append(f'<span class="ex-chip ex-chip-on">Ch.{chap}</span>')
        else:
            chips.append(f'<a class="ex-chip" href="/exam/fitz-{chap}#q-{qid}">Ch.{chap}</a>')
    for book in tag.get("other", []):
        name, short = OTHER_BOOKS[book]
        chips.append(f'<a class="ex-chip ex-chip-book" href="/exam/{book}#q-{qid}" title="{esc(name)}">{esc(short)}</a>')
    year_label = f'<a href="/exam/year-{q["year"]}#q-{qid}">{q["year"]} 年第 {q["number"]} 題</a>' if show_year else f'第 {q["number"]} 題'
    statements = ""
    if q.get("statements"):
        statements = '<ul class="ex-stmts">' + "".join(
            f'<li><span class="ex-stmt-id">{esc(s["id"])}</span>{esc_lines(s["text"])}</li>' for s in q["statements"]
        ) + "</ul>"
    answer = set(q["answer"])
    opts = "".join(
        f'<label class="ex-opt" data-key="{k}"{" data-correct" if k in answer else ""}>'
        f'<input type="radio" name="ans-{qid}" value="{k}" aria-labelledby="o-{qid}-{k} t-{qid}-{k}">'
        f'<span class="ex-opt-key" id="o-{qid}-{k}">{k}</span>'
        f'<span class="ex-opt-text" id="t-{qid}-{k}">{esc_lines(v)}</span></label>'
        for k, v in q["options"].items()
    )
    note = f'<span class="ex-flag">{esc(q["note"])}</span>' if q.get("note") else ""
    answer_html = f'<p class="ex-answer">官方答案：<strong>{esc("、".join(q["answer"]))}</strong>{note}</p>'
    if expl:
        items = "".join(
            f'<li class="{"ex-ok" if it["ok"] else "ex-no"}"><span class="ex-item-key">{esc(it["key"])}</span>'
            f'<span class="ex-item-label">{esc(it["label"])}</span>'
            f'<span class="ex-item-text">{rich(it["text"])}</span>'
            f'<span class="ex-item-refs">{"；".join(ref_html(r, current_chapter, chapters) for r in it["refs"])}</span></li>'
            for it in expl["items"]
        )
        flags = "".join(f'<p class="ex-flag-note"><span class="ex-flag-tag">附註</span>{rich(f)}</p>' for f in expl.get("flags", []))
        expl_html = (f'<p class="ex-summary">{rich(expl["summary"])}</p><ul class="ex-items">{items}</ul>'
                     f'{flags}{dispute_html(expl.get("dispute"))}')
    else:
        homes = [f'<a href="/exam/fitz-{c}">Ch.{c}</a>' for c in tag["fitz"]]
        where = f'（相關章節：{"、".join(homes)}）' if homes else ""
        expl_html = f'<p class="ex-pending">詳解尚未整理{where}。</p>'
    return (
        f'<article class="ex-q" id="q-{qid}" data-qid="{qid}" data-answer="{"".join(sorted(answer))}"'
        f'{" data-free" if q.get("free") else ""}>'
        f'<header class="ex-q-head"><span class="ex-q-no">{year_label}</span>'
        f'<span class="ex-chips">{"".join(chips)}</span></header>'
        # Verbatim official exam text: the YMYL claim audit skips this block
        # (the society's wording is quoted, not the site's own claim).
        f'<div class="ex-quote" data-ymyl="quoted-exam"><p class="ex-stem">{esc_lines(q["stem"])}</p>{statements}'
        f'<fieldset class="ex-opts"><legend class="ex-sr">選項</legend>{opts}</fieldset></div>'
        '<div class="ex-actions"><button type="button" class="ex-submit">送出答案</button>'
        '<button type="button" class="ex-reset">重新作答</button>'
        '<span class="ex-result" aria-live="polite"></span></div>'
        f'<div class="ex-reveal">{answer_html}<div class="ex-expl">{expl_html}</div></div>'
        "</article>"
    )


DISPUTE_KINDS = {
    "old": "舊版觀念", "missing": "課本未提及", "conflict": "說法矛盾",
    "ambiguous": "選項模稜兩可", "typo": "題目誤植", "figure": "缺圖或缺表",
}


def labelled(text: str) -> str:
    """'考試答案：…' -> bold label + text (the label is part of the data)."""
    head, sep, body = text.partition("：")
    if sep and len(head) <= 6:
        return f"<strong>{esc(head)}</strong>：{rich(body)}"
    return rich(text)


def source_html(src: dict) -> str:
    year = f"（{src['year']}）" if src.get("year") else ""
    pmid = f" PMID {esc(str(src['pmid']))}" if src.get("pmid") else ""
    return (f'<li><a href="{esc(src["url"])}" target="_blank" rel="noopener noreferrer">{rich(src["title"])}</a>'
            f'{esc(year)}{pmid}</li>')


def dispute_html(dispute: dict | None) -> str:
    if not dispute:
        return ""
    kind = DISPUTE_KINDS.get(dispute.get("kind"), "疑義")
    parts = [f'<p class="ex-dispute-h">⚠ 疑義題 · {esc(kind)}</p>', f'<p>{labelled(dispute["exam"])}</p>']
    if dispute.get("current"):
        parts.append(f'<p>{labelled(dispute["current"])}</p>')
    if dispute.get("sources"):
        parts.append('<ul class="ex-sources">' + "".join(source_html(s) for s in dispute["sources"]) + "</ul>")
    return f'<div class="ex-dispute">{"".join(parts)}</div>'


def links_html(links: dict | None) -> str:
    """Chapter image/reference links (DermNet, PathologyOutlines), verified by hand."""
    if not links:
        return ""
    groups = []
    for key, name in (("dermnet", "DermNet（臨床照片與疾病介紹）"), ("pathologyoutlines", "PathologyOutlines（病理圖片）")):
        items = links.get(key) or []
        if items:
            lis = "".join(f'<li><a href="{esc(i["url"])}" target="_blank" rel="noopener noreferrer">{esc(i["label"])}</a></li>'
                          for i in items)
            groups.append(f'<div class="ex-links-group"><p class="ex-links-name">{esc(name)}</p><ul>{lis}</ul></div>')
    if not groups:
        return ""
    return ('<section class="ex-links" aria-labelledby="links-h"><h2 id="links-h" class="ex-h2 ex-h2-sm">圖片與延伸閱讀</h2>'
            '<p class="ex-meta">課本圖片有版權，請到以下網站看臨床與病理照片（外部網站，另開新分頁）。</p>'
            f'{"".join(groups)}</section>')


def wrap_tables(fragment: str) -> str:
    """Note tables scroll inside their own box so a wide table never widens the page."""
    return re.sub(r'(<table\b[^>]*>.*?</table>)', r'<div class="ex-table-wrap">\1</div>', fragment, flags=re.S)


def expand_hits(fragment: str, chapter: int, on_page: set[str]) -> str:
    def repl(m: re.Match) -> str:
        ids = [i.strip() for i in m.group(1).split(",") if i.strip()]
        links = []
        for qid in ids:
            year = qid.split("-")[0]
            href = f"#q-{qid}" if qid in on_page else f"/exam/year-{year}#q-{qid}"
            links.append(f'<a href="{href}">{esc(qid)}</a>')
        return f'<span class="ex-hit">考過 {len(ids)} 題：{"、".join(links)}</span>'
    out = re.sub(r"\{\{hit:([0-9,\- ]+)\}\}", repl, fragment)
    if "{{" in out:
        raise SystemExit(f"fitz-{chapter} notes: unexpanded placeholder")
    return out


MARK = re.compile(r'<mark data-q="([0-9,\- ]+)">(.*?)</mark>', re.S)
SECTION = re.compile(r'<section class="ex-note" id="([a-z0-9-]+)">\s*<h2>(.*?)</h2>', re.S)


def expand_marks(fragment: str, on_page: set[str]) -> str:
    """<mark data-q="102-42,105-21">fact</mark> -> highlighted fact + links to the questions."""
    def repl(m: re.Match) -> str:
        links = []
        for qid in [i.strip() for i in m.group(1).split(",") if i.strip()]:
            href = f"#q-{qid}" if qid in on_page else f"/exam/year-{qid.split('-')[0]}#q-{qid}"
            links.append(f'<a href="{href}">{esc(qid)}</a>')
        return f'<mark class="ex-key">{m.group(2)}</mark><span class="ex-qref">{" ".join(links)}</span>'
    return MARK.sub(repl, fragment)


def toc_html(note: str | None, qs_count: int, *, mobile: bool = False) -> str:
    items = [f'<li><a href="#{sid}">{title}</a></li>' for sid, title in SECTION.findall(note or "")]
    items.append(f'<li class="ex-toc-qs"><a href="#qs-h">考題（{qs_count} 題）</a></li>')
    cls, state, label = (("ex-toc ex-toc-mobile", "", "本章目錄（展開式）") if mobile
                         else ("ex-toc ex-toc-side", " open", "本章目錄"))
    return (f'<details class="{cls}"{state}><summary>本章目錄</summary>'
            f'<nav aria-label="{label}"><ol>{"".join(items)}</ol></nav></details>')


NOTES_TOOLS = (
    '<div class="ex-notes-tools">'
    '<span class="ex-legend"><mark class="ex-key">螢光</mark>＝考過（後附題號）'
    '<span class="ex-legend-trap">紅框</span>＝易錯陷阱'
    '<strong class="ex-n">粗體數字</strong>＝門檻值</span></div>'
)


# ---------------------------------------------------------------- pages

def chapter_page(shell, data, chapter: dict, qs: list[dict]) -> str:
    n = chapter["chapter"]
    years = Counter(q["year"] for q in qs)
    on_page = {q["id"] for q in qs}
    note = data["notes"].get(n)
    explained = sum(1 for q in qs if q["id"] in data["explanations"])
    if note:
        notes_html = (f'<section class="ex-notes" aria-labelledby="notes-h"><h2 id="notes-h" class="ex-h2">重點整理</h2>'
                      f'{NOTES_TOOLS}{wrap_tables(expand_marks(expand_hits(note, n, on_page), on_page))}</section>')
    else:
        notes_html = '<section class="ex-notes"><h2 class="ex-h2">重點整理</h2><p class="ex-pending">這一章的重點尚未整理。</p></section>'
    year_text = "、".join(f"{y} 年 {c} 題" for y, c in sorted(years.items()))
    body = (
        f'<p class="ex-kicker">Fitzpatrick 9e · {esc(chapter["part"].title() if chapter["part"] else "")}</p>'
        f'<h1 class="ex-h1">Ch.{n} {esc(chapter["title"])}</h1>'
        f'<p class="ex-meta">原書 p.{chapter["pageStart"]}–{chapter["pageEnd"]} · 考題共 {len(qs)} 題'
        f'（已有詳解 {explained} 題）</p>'
        f'<p class="ex-meta">{esc(year_text)}</p>{NOTICE}{links_html(data["links"].get(n))}'
        f'{toc_html(note, len(qs), mobile=True)}{notes_html}'
        f'<section aria-labelledby="qs-h"><h2 id="qs-h" class="ex-h2">考題</h2>{MODE_BAR}'
        + "".join(question_html(q, data, current_chapter=n) for q in qs)
        + "</section>"
    )
    title = f"Fitzpatrick Ch.{n} {chapter['title']} 重點與考題"
    desc = (f"皮膚科專科醫師考試讀書筆記：Fitzpatrick's Dermatology 9e 第 {n} 章 {chapter['title']}"
            f"，整理 101–115 年考題 {len(qs)} 題" + ("與重點整理" if note else "") + "。")
    return page(shell, path=f"/exam/fitz-{n}", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[(f"Ch.{n}", f"/exam/fitz-{n}")],
                jsonld_type="WebPage", body=body, page_kind="chapter", toc=toc_html(note, len(qs)))


def year_page(shell, data, year: int, qs: list[dict]) -> str:
    body = (
        f'<p class="ex-kicker">年度考古卷</p><h1 class="ex-h1">{year} 年度皮膚科專科醫師甄審筆試 · 選擇題</h1>'
        f'<p class="ex-meta">共 {len(qs)} 題 · 已有詳解 {sum(1 for q in qs if q["id"] in data["explanations"])} 題</p>{NOTICE}'
        '<div class="ex-exam-bar" data-exam-bar>'
        '<button type="button" class="ex-start">開始計時作答</button>'
        '<span class="ex-timer" aria-live="off">00:00</span>'
        '<button type="button" class="ex-finish">交卷並計分</button>'
        '<span class="ex-score" aria-live="polite"></span></div>'
        f"{MODE_BAR}"
        + "".join(question_html(q, data, show_year=False) for q in qs)
    )
    title = f"{year} 年皮膚科專科醫師甄審筆試選擇題（考古卷）"
    desc = f"{year} 年度皮膚科專科醫師甄審筆試選擇題 {len(qs)} 題，可計時作答、交卷計分，並對照官方答案與 Fitzpatrick 詳解。"
    return page(shell, path=f"/exam/year-{year}", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[(f"{year} 年", f"/exam/year-{year}")],
                jsonld_type="WebPage", body=body, page_kind="year")


def book_page(shell, data, book: str, qs: list[dict]) -> str:
    name, short = OTHER_BOOKS[book]
    body = (
        f'<p class="ex-kicker">其他參考書</p><h1 class="ex-h1">{esc(short)}題 · {esc(name)}</h1>'
        f'<p class="ex-meta">主要考 {esc(name)} 內容的考題，共 {len(qs)} 題。'
        "這些題目的詳解需要該書內容，目前只列出官方答案；若 Fitzpatrick 也有涵蓋，題目旁會標出章節。</p>"
        f"{NOTICE}{MODE_BAR}" + "".join(question_html(q, data) for q in qs)
    )
    title = f"皮膚科專科考試 {short}題（{name}）"
    desc = f"皮膚科專科醫師甄審筆試 101–115 年中以 {name} 為主的{short}題，共 {len(qs)} 題，附官方答案。"
    return page(shell, path=f"/exam/{book}", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[(f"{short}題", f"/exam/{book}")],
                jsonld_type="WebPage", body=body, page_kind="book")


def practice_page(shell, by_year) -> str:
    years = "".join(
        f'<label class="ex-check"><input type="checkbox" name="ex-year" value="{y}" checked aria-label="{y} 年"> {y} 年</label>'
        for y in sorted(by_year)
    )
    year_links = "".join(f'<li><a href="/exam/year-{y}">{y} 年</a></li>' for y in sorted(by_year))
    body = (
        '<p class="ex-kicker">考古卷</p><h1 class="ex-h1">自選年份／隨機出題</h1>'
        f"{NOTICE}"
        '<form class="ex-practice-form" data-practice-form>'
        '<fieldset class="ex-fieldset"><legend>出題年份</legend>'
        f'<div class="ex-checks">{years}</div>'
        '<div class="ex-toolbar"><button type="button" class="ex-years-all">全選</button>'
        '<button type="button" class="ex-years-none">全不選</button></div></fieldset>'
        '<fieldset class="ex-fieldset"><legend>題數</legend><select name="ex-count" class="ex-select" aria-label="題數">'
        '<option value="10">10 題</option><option value="25">25 題</option><option value="50" selected>50 題</option>'
        '<option value="100">100 題</option><option value="0">全部</option></select></fieldset>'
        '<fieldset class="ex-fieldset"><legend>出題順序</legend>'
        '<label class="ex-check"><input type="radio" name="ex-order" value="random" aria-label="隨機" checked> 隨機</label>'
        '<label class="ex-check"><input type="radio" name="ex-order" value="year" aria-label="依年份與題號"> 依年份與題號</label></fieldset>'
        '<div class="ex-toolbar"><button type="button" class="ex-build">產生試卷並開始計時</button>'
        '<span class="ex-build-note" aria-live="polite"></span></div></form>'
        '<div class="ex-exam-bar" data-exam-bar hidden>'
        '<span class="ex-timer" aria-live="off">00:00</span>'
        '<button type="button" class="ex-finish">交卷並計分</button>'
        '<span class="ex-score" aria-live="polite"></span></div>'
        '<div id="ex-practice-list" class="ex-review-list">'
        '<p class="ex-pending">選好年份、題數與順序後按「產生試卷」。</p></div>'
        '<noscript><p class="ex-meta">這個功能需要啟用 JavaScript。未啟用時，可以直接開啟單一年度的考古卷：</p>'
        f'<ul class="ex-year-links">{year_links}</ul></noscript>'
    )
    title = "皮膚科專科醫師考試考古卷：自選年份與隨機出題"
    desc = "從 101–115 年皮膚科專科醫師甄審筆試選擇題中自選年份、題數，隨機或依序出題，計時作答並交卷計分。"
    return page(shell, path="/exam/practice", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[("自選／隨機出題", "/exam/practice")],
                jsonld_type="WebPage", body=body, page_kind="practice")


def review_page(shell) -> str:
    body = (
        '<p class="ex-kicker">複習工具</p><h1 class="ex-h1">錯題本與 Anki 匯出</h1>'
        f"{NOTICE}"
        '<p class="ex-meta">在作答模式答錯的題目會自動記在這台裝置的瀏覽器裡（不同電腦或手機不會同步）。'
        "答對後可以把題目移出錯題本。</p>"
        '<div class="ex-toolbar"><button type="button" class="ex-anki" data-scope="wrong">錯題匯出 Anki（CSV）</button>'
        '<button type="button" class="ex-anki" data-scope="all">全部題目匯出 Anki（CSV）</button>'
        '<button type="button" class="ex-clear-wrong">清空錯題本</button></div>'
        '<p class="ex-meta">Anki 匯入方式：檔案 → 匯入，欄位分隔選逗號，第一欄為正面、第二欄為背面，並勾選「允許在欄位中使用 HTML」。</p>'
        f"{MODE_BAR}"
        '<div id="ex-review-list" class="ex-review-list"><p class="ex-pending">目前沒有錯題，或瀏覽器停用了 JavaScript。</p></div>'
    )
    title = "皮膚科專科考試錯題本"
    desc = "皮膚科專科醫師考試讀書筆記的錯題本：集中重練作答模式答錯的考題，並可匯出 Anki 卡片。"
    return page(shell, path="/exam/review", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[("錯題本", "/exam/review")],
                jsonld_type="WebPage", body=body, page_kind="review")


SEARCH_VERSION = [""]  # content hash of search-index.json, set by build()

# Hidden until exam.js loads the index, so a page without JS shows no dead box.
SEARCH_BOX = (
    '<div class="ex-search" data-exam-search="{index}" hidden>'
    '<label class="ex-search-label" for="ex-search-input">搜尋疾病或主題（全名、縮寫或中文）</label>'
    '<input id="ex-search-input" class="ex-search-input" type="text" role="combobox" '
    'aria-autocomplete="list" aria-expanded="false" aria-controls="ex-search-results" '
    'aria-describedby="ex-search-hint" autocomplete="off" autocapitalize="off" spellcheck="false" '
    'enterkeyhint="search" placeholder="例如 HES、pemphigus、梅毒">'
    '<p id="ex-search-hint" class="ex-search-hint">結果依章節分組，點選後直接跳到該章的段落；可用上下鍵選擇、Enter 開啟。</p>'
    '<p id="ex-search-status" class="ex-search-status" role="status" aria-live="polite"></p>'
    '<div id="ex-search-results" class="ex-search-results" role="listbox" aria-label="搜尋結果" hidden></div>'
    "</div>"
)


def hub_page(shell, data, by_chapter, by_year, by_book) -> str:
    chapters = data["chapters"]
    total = len(data["questions"])
    explained = len(data["explanations"])
    # Every chapter with questions is listed; exam.js shows data-rank-page rows
    # at a time behind a 「載入更多」 button, and without JS the whole table shows.
    ranked = sorted(by_chapter.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    peak = len(ranked[0][1]) if ranked else 1
    rows = "".join(
        f'<tr><td><a href="/exam/fitz-{n}">Ch.{n} {esc(chapters[n]["title"])}</a>'
        f'{" <span class=\"ex-badge\">有重點</span>" if n in data["notes"] else ""}</td>'
        f'<td class="ex-num">{len(qs)}</td>'
        f'<td class="ex-bar-cell"><span class="ex-bar" style="width:{round(100 * len(qs) / peak)}%"></span></td></tr>'
        for n, qs in ranked
    )
    parts = defaultdict(list)
    for n, ch in sorted(chapters.items()):
        parts[ch["part"]].append(n)
    part_html = []
    for part, nums in parts.items():
        prog_rows = []
        for idx, n in enumerate(nums):
            qs = by_chapter.get(n, [])
            title = esc(chapters[n]["title"])
            name = (f'<a href="/exam/fitz-{n}">Ch.{n} {title}</a>' if qs else f'Ch.{n} {title}')
            badge = ' <span class="ex-badge">有重點</span>' if n in data["notes"] else ""
            # Progress cells start as "—" and are filled from this browser's
            # localStorage by exam.js; data-qids lists the chapter's questions,
            # counted from the answers given on /exam/fitz-<data-ch> only.
            prog_rows.append(
                f'<tr data-ch="{n}" data-order="{idx}" data-qids="{",".join(q["id"] for q in qs)}"'
                f'{" class=\"ex-none\"" if not qs else ""}>'
                f'<th scope="row">{name}{badge}</th><td class="ex-num">{len(qs)}</td>'
                '<td class="ex-num ex-pg-done">—</td><td class="ex-num ex-pg-acc">—</td><td class="ex-pg-date">—</td>'
                f'<td class="ex-pg-readcell"><input type="checkbox" class="ex-pg-read" data-ch="{n}" '
                f'aria-label="Ch.{n} 課本已讀完" disabled></td></tr>'
            )
        count = sum(len(by_chapter.get(n, [])) for n in nums)
        part_html.append(
            f'<details class="ex-part"><summary>{esc((part or "").title())} <span class="ex-count">{count} 題次</span></summary>'
            '<div class="ex-table-wrap"><table class="ex-progress"><thead><tr><th scope="col">章節</th>'
            '<th scope="col">題數</th><th scope="col">已做</th><th scope="col">正確率</th>'
            '<th scope="col">最後作答</th><th scope="col">課本已讀完</th></tr></thead>'
            f'<tbody>{"".join(prog_rows)}</tbody></table></div></details>'
        )
    books = "".join(
        f'<li><a href="/exam/{b}">{esc(OTHER_BOOKS[b][1])}題（{esc(OTHER_BOOKS[b][0])}）</a> <span class="ex-count">{len(qs)} 題</span></li>'
        for b, qs in sorted(by_book.items())
    )
    refs = "".join(f"<li>{esc(book)}</li>" for book in REFERENCE_BOOKS)
    body = (
        f'<h1 class="ex-h1">{HUB_TITLE}</h1>'
        '<p class="ex-lead">目前整理 101–115 年考題以及各章節重點整理（陸續更新中）</p>'
        f'{SEARCH_BOX.format(index=f"/exam/search-index.json?v={SEARCH_VERSION[0]}")}'
        '<h2 class="ex-h2 ex-h2-sm">目前甄審筆試出題參考範圍</h2>'
        f'<ol class="ex-refs">{refs}</ol>{NOTICE}'
        '<h2 class="ex-h2">考古卷</h2>'
        '<p class="ex-meta"><a class="ex-cta" href="/exam/practice">自選年份／隨機出題</a></p>'
        '<h2 class="ex-h2">依章節瀏覽與讀書進度</h2>'
        '<p class="ex-meta">已做題數、正確率（以每題最近一次作答計算）與「課本已讀完」只存在這台裝置的瀏覽器，'
        '不同電腦或手機不會同步。正確率低於 60% 以紅字標示。</p>'
        '<p class="ex-meta">章節統計只計算在該章頁面作答的題目。</p>'
        f'<div class="ex-toolbar ex-progress-bar" data-exam-total="{total}"><span id="ex-progress-summary" class="ex-meta" aria-live="polite"></span>'
        '<label class="ex-check">排序 <select class="ex-select ex-progress-sort" aria-label="章節排序" disabled>'
        '<option value="order">章節順序</option><option value="todo">尚未作答優先</option>'
        '<option value="low">正確率低優先</option></select></label></div>' + "".join(part_html)
        + '<h2 class="ex-h2" id="rank-h">出題頻率：最常考的章節</h2>'
        f'<p class="ex-meta">有考題的 {len(ranked)} 章依題數排序。一題可能計入多章，所以加總會超過題數。</p>'
        '<table class="ex-rank" id="ex-rank" aria-labelledby="rank-h" data-rank-page="25"><thead><tr><th scope="col">章節</th>'
        '<th scope="col">題數</th><th scope="col"><span class="ex-sr">比例</span></th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        '<div class="ex-more-wrap" hidden><button type="button" class="ex-more" aria-controls="ex-rank">載入更多</button></div>'
        + '<h2 class="ex-h2">其他參考書與工具</h2>'
        f'<ul class="ex-chapter-list">{books}<li><a href="/exam/review">錯題本與 Anki 匯出</a></li></ul>'
    )
    title = HUB_TITLE
    desc = (f"皮膚科專科醫師甄審筆試 101–115 年考題 {total} 題，依 Fitzpatrick 9e 章節整理重點，"
            "附出題頻率統計、自選年份或隨機出題的考古卷、錯題本與 Anki 匯出。")
    return page(shell, path="/exam", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=HUB_TITLE, crumbs=[],
                jsonld_type="CollectionPage", body=body, page_kind="hub")


# ---------------------------------------------------------------- search index
# The hub's disease search (exam.js) reads exam/search-index.json. Every note
# section contributes the names a reader would type: its h2/h3 headings, the
# first cell of each table row, <strong> terms (not the ex-n threshold numbers
# or the 易錯 label) and <em> organism names. "Full name（ABBR）",
# "ABBR（full name）" and "English（中文）" are split so the full name, the
# abbreviation and the Chinese name all find the same section.

TAG = re.compile(r"<[^>]+>")
CJK = re.compile(r"[\u3400-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
SECTION_BLOCK = re.compile(r'<section class="ex-note" id="([a-z0-9-]+)">(.*?)</section>', re.S)
PAREN = re.compile(r"[（(]([^（）()]*)[）)]")
NAME_SOURCES = (
    re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S),
    re.compile(r"<tbody>.*?</tbody>", re.S),  # expanded to first cells below
    re.compile(r"<strong>(.*?)</strong>", re.S),  # bare <strong> only: class="ex-n" are numbers
    re.compile(r"<em>(.*?)</em>", re.S),
)
FIRST_CELL = re.compile(r"<tr>\s*<t[dh][^>]*>(.*?)</t[dh]>", re.S)
SKIP_NAMES = {"易錯", "mckee 補充"}


def plain(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG.sub("", fragment))).strip()


def is_abbr(text: str) -> bool:
    """SJS, HES, IgA, MBP-1, CD35 — short tokens that are mostly capitals."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{1,9}", text):
        return False
    letters = [c for c in text if c.isalpha()]
    caps = sum(c.isupper() for c in letters)
    return caps >= 2 and caps * 2 >= len(letters)


def long_form(abbr: str, before: str) -> str | None:
    """Schwartz-Hearst: the shortest run of words before '（ABBR）' whose letters spell ABBR."""
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", re.split(r"[^A-Za-z0-9'\- ]", before)[-1])
    letters = [c.lower() for c in abbr if c.isalnum()]
    if not words or not letters:
        return None
    words = words[-min(len(letters) + 5, len(letters) * 2):]
    text = " ".join(words)
    si, li = len(text) - 1, len(letters) - 1
    while li >= 0:
        ch = letters[li]
        while si >= 0 and (text[si].lower() != ch or (li == 0 and si > 0 and text[si - 1].isalnum())):
            si -= 1
        if si < 0:
            return None
        si -= 1
        li -= 1
    found = text[text.rfind(" ", 0, si + 1) + 1:]
    if found.lower() == abbr.lower() or len(found) <= len(abbr):
        return None
    return found


def split_name(raw: str) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """'7. Hypereosinophilic Syndromes（嗜酸性球增多症候群，HES）' ->
    names [Hypereosinophilic Syndromes, 嗜酸性球增多症候群], abbrs [HES],
    pairs [(full, HES), (full, 嗜酸性球增多症候群)] (a full English name with its
    abbreviation or its Chinese name)."""
    text = re.sub(r"^\s*\d+[.)、]\s*", "", raw).strip(" ：:;；，,。")
    base = PAREN.sub(" ", text)
    base = re.sub(r"\s+", " ", base).strip(" ：:;；，,")
    parts = [base] + [p for group in PAREN.findall(text) for p in re.split(r"[，,、；;/]", group)]
    names, abbrs, pairs = [], [], []
    for part in parts:
        part = part.strip()
        if (len(part) < 2 or len(part) > 80 or part.lower() in SKIP_NAMES
                or re.fullmatch(r"(?:p\.|Table|Fig).*|[\d\s.,\-–+%≥≤<>=/]+", part)):
            continue
        if is_abbr(part):
            abbrs.append(part)
        elif LATIN.search(part) or CJK.search(part):
            names.append(part)
    if base and not is_abbr(base) and LATIN.search(base):
        pairs.extend((base, a) for a in abbrs if long_form(a, base))
        pairs.extend((base, n) for n in names[1:] if CJK.search(n) and not LATIN.search(n))
    return names, abbrs, pairs


def prose_pairs(text: str) -> list[tuple[str, str]]:
    """'Bowenoid papulosis（BP）' anywhere in a section -> (Bowenoid papulosis, BP)."""
    pairs = []
    for m in PAREN.finditer(text):
        inner = re.split(r"[，,]", m.group(1))[-1].strip()
        if is_abbr(inner):
            full = long_form(inner, text[max(0, m.start() - 120):m.start()])
            if full:
                pairs.append((full, inner))
    return pairs


def name_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\-‐–—_/]", " ", text.lower())).strip()


def gloss_key(text: str) -> str:
    """name_key without plural -s, so 'Hypereosinophilic Syndromes' and '... syndrome' meet."""
    return re.sub(r"(?<=[a-z]{3})s\b", "", name_key(text))


class Terms:
    """Names and abbreviations of one index entry, de-duplicated in first-seen order."""

    def __init__(self) -> None:
        self.names: list[str] = []
        self.abbrs: list[str] = []
        self.seen: set[str] = set()

    def add(self, names=(), abbrs=()) -> None:
        for target, items in ((self.names, names), (self.abbrs, abbrs)):
            for item in items:
                key = name_key(item)
                if key and key not in self.seen:
                    self.seen.add(key)
                    target.append(item)


def search_index(data, by_chapter) -> dict:
    """Entries are [chapter, section id ("" = chapter page), section title, names,
    abbreviations, n primary names, n primary abbreviations]; primary terms come
    from the section's own h2 (or the chapter title and its listed aliases) and
    rank above terms that merely occur inside the section."""
    chapters = data["chapters"]
    glossary: dict[str, set[str]] = defaultdict(set)  # gloss_key(full name) -> abbreviations
    chinese: dict[str, list[str]] = defaultdict(list)  # gloss_key(English name) -> Chinese names
    sections = []
    for n in sorted(data["notes"]):
        if n not in by_chapter:
            continue  # no chapter page to link to
        for sid, body in SECTION_BLOCK.findall(data["notes"][n]):
            heading = plain(re.search(r"<h2>(.*?)</h2>", body, re.S).group(1))
            terms = Terms()
            names, abbrs, pairs = split_name(heading)
            terms.add(names, abbrs)
            primary = (len(terms.names), len(terms.abbrs))
            raw_names = []
            for pattern in NAME_SOURCES:
                for m in pattern.finditer(body):
                    if m.group(0).startswith("<tbody>"):
                        raw_names.extend(plain(c) for c in FIRST_CELL.findall(m.group(0)))
                    elif not m.group(0).startswith("<h2"):
                        raw_names.append(plain(m.group(1)))
            for raw in raw_names:
                got_names, got_abbrs, got_pairs = split_name(raw)
                terms.add(got_names, got_abbrs)
                pairs += got_pairs
            for full, other in pairs + prose_pairs(plain(body)):
                if CJK.search(other):
                    if other not in chinese[gloss_key(full)]:
                        chinese[gloss_key(full)].append(other)
                    continue
                glossary[gloss_key(full)].add(other)
                terms.add([full], [other])
            sections.append((n, sid, re.sub(r"^\s*\d+[.)、]\s*", "", heading), terms, primary))
    fulls = sorted((f for f in glossary if len(f) >= 6), key=lambda f: (-len(f), f))
    known = (re.compile(r"(?<![a-z0-9])(?:" + "|".join(map(re.escape, fulls)) + r")(?![a-z0-9])")
             if fulls else None)

    def glossary_abbrs(texts) -> list[str]:
        """An abbreviation defined anywhere also finds names that only spell it out."""
        found = []
        for text in texts:
            for m in (known.finditer(gloss_key(text)) if known else ()):
                found.extend(sorted(glossary[m.group(0)]))
        return found

    def chinese_names(texts) -> list[str]:
        """Chinese names the notes give for exactly this English name: 'Syphilis（梅毒）'."""
        return [zh for text in texts for zh in chinese.get(gloss_key(text), [])]

    entries = []
    for n in sorted(by_chapter):
        title = chapters[n]["title"]
        terms = Terms()
        names, abbrs, _ = split_name(title)
        terms.add([title] + names, abbrs + data["aliases"].get(n, []))
        terms.add(chinese_names([title] + names), glossary_abbrs([title]))
        primary = (len(terms.names), len(terms.abbrs))
        for group in ("dermnet", "pathologyoutlines"):
            for item in (data["links"].get(n) or {}).get(group, []):
                label = re.sub(r"\s+(?:images|\(overview\))$", "", item["label"], flags=re.I)
                got_names, got_abbrs, _ = split_name(label)
                terms.add(got_names, got_abbrs)
        terms.add(chinese_names(terms.names[primary[0]:]), glossary_abbrs(terms.names[primary[0]:]))
        entries.append([n, "", "", terms.names, terms.abbrs, *primary])
    for n, sid, heading, terms, primary in sections:
        head_abbrs = glossary_abbrs(terms.names[:primary[0]])
        terms.add(abbrs=head_abbrs)
        if len(terms.abbrs) > primary[1] and head_abbrs:
            # glossary abbreviations of the heading itself are primary too
            moved = [a for a in terms.abbrs[primary[1]:] if a in head_abbrs]
            terms.abbrs = terms.abbrs[:primary[1]] + moved + [a for a in terms.abbrs[primary[1]:] if a not in moved]
            primary = (primary[0], primary[1] + len(moved))
        terms.add(abbrs=glossary_abbrs(terms.names[primary[0]:]))
        entries.append([n, sid, heading, terms.names, terms.abbrs, *primary])
    return {
        "chapters": {str(n): chapters[n]["title"] for n in sorted(by_chapter)},
        "notes": sorted(n for n in data["notes"] if n in by_chapter),
        "entries": entries,
    }


def client_data(data) -> dict:
    """Compact data for the review page and Anki export."""
    out = []
    for q in data["questions"]:
        row = {k: q[k] for k in ("id", "year", "number", "stem", "options", "answer")}
        if q.get("statements"):
            row["statements"] = q["statements"]
        if q.get("free"):
            row["free"] = True
            row["note"] = q.get("note", "")
        row["fitz"] = data["tags"][q["id"]]["fitz"]
        expl = data["explanations"].get(q["id"])
        if expl:
            row["expl"] = {"summary": expl["summary"], "items": [
                {"key": it["key"], "label": it["label"], "ok": it["ok"], "text": it["text"],
                 "refs": [ref_label([c, p]) for c, p in it["refs"]]} for it in expl["items"]]}
            if expl.get("flags"):
                row["expl"]["flags"] = expl["flags"]
            if expl.get("dispute"):
                row["expl"]["dispute"] = expl["dispute"]
        out.append(row)
    return {"questions": out}


def build() -> dict[str, str]:
    data = load()
    shell = split_template()
    by_chapter: dict[int, list] = defaultdict(list)
    by_year: dict[int, list] = defaultdict(list)
    by_book: dict[str, list] = defaultdict(list)
    for q in data["questions"]:
        by_year[q["year"]].append(q)
        tag = data["tags"][q["id"]]
        for chap in tag["fitz"]:
            if chap not in data["chapters"]:
                raise SystemExit(f"{q['id']}: unknown chapter {chap}")
            by_chapter[chap].append(q)
        for book in tag.get("other", []):
            if book not in OTHER_BOOKS:
                raise SystemExit(f"{q['id']}: unknown book {book}")
            by_book[book].append(q)
    # Chapter and book pages list the newest exam first (user request
    # 2026-10-16); within a year the original question order is kept.
    for group in (*by_chapter.values(), *by_book.values()):
        group.sort(key=lambda q: (-q["year"], q["number"]))
    for qid in data["explanations"]:
        if not data["tags"][qid]["fitz"]:
            raise SystemExit(f"{qid} has an explanation but no Fitzpatrick chapter")
    CHAPTER_PAGES.clear()
    CHAPTER_PAGES.update(by_chapter)
    client = json.dumps(client_data(data), ensure_ascii=False, separators=(",", ":")) + "\n"
    DATA_VERSION[0] = hashlib.sha256(client.encode("utf-8")).hexdigest()[:10]
    index = json.dumps(search_index(data, by_chapter), ensure_ascii=False, separators=(",", ":")) + "\n"
    SEARCH_VERSION[0] = hashlib.sha256(index.encode("utf-8")).hexdigest()[:10]
    files: dict[str, str] = {}
    files["index.html"] = hub_page(shell, data, by_chapter, by_year, by_book)
    for n, qs in sorted(by_chapter.items()):
        files[f"fitz-{n}.html"] = chapter_page(shell, data, data["chapters"][n], qs)
    for y, qs in sorted(by_year.items()):
        files[f"year-{y}.html"] = year_page(shell, data, y, qs)
    for b, qs in sorted(by_book.items()):
        files[f"{b}.html"] = book_page(shell, data, b, qs)
    files["practice.html"] = practice_page(shell, by_year)
    files["review.html"] = review_page(shell)
    files["exam-data.json"] = client
    files["search-index.json"] = index
    return files


EXAM_STYLE = """<style data-exam-style>
.ex-main .crumbs{font-size:12.5px;color:var(--muted);margin-bottom:18px}
.ex-main .crumbs a{color:var(--teal-deep);font-weight:600;text-decoration:none}
.ex-sep{margin:0 6px;opacity:.5}
.ex-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.ex-kicker{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#0c5159;font-weight:700;margin:0 0 8px}
.ex-h1{font-family:'Noto Serif TC',Georgia,serif;font-weight:700;font-size:28px;line-height:1.3;margin:0 0 12px}
.ex-h2{font-family:'Noto Serif TC',Georgia,serif;font-weight:700;font-size:21px;margin:36px 0 14px}
.ex-main h3{font-weight:700;font-size:16px;margin:18px 0 8px}
.ex-lead{font-size:15.5px;line-height:1.9;color:var(--ink-2)}
.ex-meta{font-size:13px;color:var(--ink-2);line-height:1.8;margin:4px 0}
.ex-notice{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:12px 16px;margin:18px 0;font-size:13px;color:#7c2d12;line-height:1.8}
.ex-notice a{color:#7c2d12;text-decoration:underline}
.ex-note{border-top:1px solid var(--line);padding-top:6px;margin-top:10px}
.ex-note h2{font-size:18px;font-weight:700;margin:18px 0 10px}
.ex-note p,.ex-note li{font-size:14.5px;line-height:1.85}
.ex-note ul{padding-left:20px;margin:6px 0}
.ex-ref{font-size:11.5px;color:#4d6358;background:#f1ece4;border-radius:6px;padding:1px 6px;margin-left:4px;white-space:nowrap;text-decoration:none}
.ex-cite{font-size:12px;color:var(--muted);margin:4px 0 12px}
.ex-table,.ex-rank{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0;background:#fff}
.ex-table th,.ex-table td,.ex-rank th,.ex-rank td{border:1px solid var(--border);padding:6px 9px;text-align:left;vertical-align:top}
.ex-table th,.ex-rank th{background:#f1ece4}
.ex-num{text-align:right;width:3.5em}
.ex-bar-cell{width:30%}
.ex-bar{display:block;height:9px;border-radius:9px;background:#7a9285}
.ex-hit{display:inline-block;font-size:11.5px;font-weight:600;color:#854d0e;background:#fef3c7;border-radius:9999px;padding:2px 10px;margin-left:6px;vertical-align:middle}
.ex-hit a{color:#854d0e}
.ex-badge{font-size:10.5px;font-weight:700;color:#14532d;background:#dcfce7;border-radius:9999px;padding:1px 7px}
.ex-count{font-size:12px;color:var(--muted)}
.ex-part{border:1px solid var(--border);border-radius:12px;background:#fff;margin:8px 0;padding:8px 14px}
.ex-part summary{cursor:pointer;font-weight:700;font-size:14px}
.ex-chapter-list{list-style:none;padding:0;margin:8px 0;font-size:14px;line-height:1.9}
.ex-chapter-list a{color:var(--teal-deep)}
.ex-year-links{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}
.ex-year-links a{display:inline-block;border:1px solid var(--border);border-radius:9999px;padding:4px 14px;text-decoration:none;font-weight:600;color:var(--teal-deep)}
.ex-none{color:var(--muted)}
.ex-toolbar,.ex-exam-bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:14px 0}
.ex-exam-bar[hidden]{display:none}
.ex-toolbar button,.ex-exam-bar button,.ex-actions button{border:1px solid #4d6358;border-radius:9999px;padding:6px 14px;font-size:13px;font-weight:600;background:#fff;color:#4d6358;cursor:pointer}
.ex-mode[aria-pressed="true"]{background:#4d6358;color:#fff}
.ex-toolbar-hint{font-size:12px;color:var(--muted)}
.ex-timer{font-family:Inter,ui-monospace,monospace;font-size:15px;font-weight:700;min-width:4.5em}
.ex-score{font-weight:700;color:#0c5159}
.ex-q{background:#fff;border:1px solid var(--border);border-radius:14px;padding:16px 18px;margin:14px 0}
.ex-q-head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px;font-size:12px;color:var(--muted);margin-bottom:8px}
.ex-q-no a{color:var(--teal-deep);font-weight:700}
.ex-chips{display:flex;flex-wrap:wrap;gap:4px}
.ex-chip{font-size:11px;font-weight:600;border-radius:9999px;padding:1px 8px;background:#f1ece4;color:#4d6358;text-decoration:none}
.ex-chip-on{background:#4d6358;color:#fff}
.ex-chip-book{background:#ede9fe;color:#5b21b6}
.ex-stem{font-size:15px;line-height:1.85;font-weight:600;margin:0 0 8px}
.ex-stmts{list-style:none;padding:0;margin:0 0 8px;font-size:14px;line-height:1.8}
.ex-stmt-id{font-weight:700;margin-right:6px}
.ex-opts{border:0;padding:0;margin:0}
.ex-opt{display:flex;gap:8px;align-items:flex-start;border:1px solid var(--line);border-radius:10px;padding:7px 10px;margin:5px 0;font-size:14px;line-height:1.7;cursor:pointer}
.ex-opt input{margin-top:6px}
.ex-opt-key{font-weight:700;min-width:1.2em}
.ex-actions{display:none;align-items:center;gap:8px;margin-top:10px}
.ex-result{font-weight:700}
.ex-reveal{margin-top:12px;border-top:1px dashed var(--border);padding-top:10px}
.ex-answer{font-size:14px;margin:0 0 6px}
.ex-flag{margin-left:8px;font-size:12px;color:#854d0e;background:#fef3c7;border-radius:6px;padding:1px 6px}
.ex-summary{font-size:14px;font-weight:600;margin:6px 0}
.ex-items{list-style:none;padding:0;margin:0}
.ex-items li{display:grid;grid-template-columns:2em auto 1fr;gap:4px 8px;font-size:13.5px;line-height:1.75;padding:6px 0;border-bottom:1px solid var(--line)}
.ex-item-key{font-weight:700}
.ex-item-label{font-size:11.5px;font-weight:700;border-radius:6px;padding:1px 6px;height:fit-content}
.ex-ok .ex-item-label{background:#dcfce7;color:#14532d}
.ex-no .ex-item-label{background:#fee2e2;color:#7f1d1d}
.ex-item-text{grid-column:3}
.ex-item-refs{grid-column:3;font-size:11.5px}
.ex-warn{font-size:12.5px;color:#854d0e;background:#fffbeb;border-radius:8px;padding:6px 10px;margin:8px 0 0}
.ex-flag-note{font-size:12.5px;color:#475569;background:#f8fafc;border-radius:8px;padding:6px 10px;margin:8px 0 0}
.ex-flag-tag{display:inline-block;font-size:11px;font-weight:700;color:#0c5159;margin-right:6px}
.ex-dispute{border:1px solid #f0c27b;border-left:4px solid #d97706;background:#fffbeb;border-radius:8px;padding:8px 12px;margin:10px 0 0;font-size:13.5px;line-height:1.75}
.ex-dispute p{margin:4px 0}.ex-dispute-h{font-weight:700;color:#92400e}
.ex-sources{margin:4px 0 0;padding-left:20px;font-size:12.5px}.ex-sources a{color:#0c5159}
.ex-ref-mckee{background:#f3e8ff;color:#5b21b6}
.ex-links{border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin:14px 0;background:#fff}
.ex-links ul{margin:4px 0 8px;padding-left:20px;font-size:14px;line-height:1.8}.ex-links a{color:var(--teal-deep);text-decoration:underline;text-underline-offset:2px}.ex-links-name{font-weight:700;font-size:13.5px;margin:8px 0 0}
.ex-progress-bar{flex-wrap:wrap;gap:10px;align-items:center}
.ex-table-wrap{overflow-x:auto}
.ex-progress{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0;background:#fff;min-width:560px}
.ex-progress th,.ex-progress td{border:1px solid var(--border);padding:6px 8px;text-align:left;vertical-align:middle}
.ex-progress thead th{background:#f1ece4;font-size:12.5px;white-space:nowrap}
.ex-progress tbody th{font-weight:500}.ex-progress tbody th a{color:var(--teal-deep)}
.ex-progress .ex-num,.ex-pg-date,.ex-pg-readcell{white-space:nowrap;text-align:center}
.ex-progress tr.ex-none th{color:var(--muted)}
.ex-pg-low{color:#b91c1c;font-weight:700}
.ex-pending{font-size:13px;color:var(--muted)}
body.ex-quiz .ex-actions{display:flex}
body.ex-quiz .ex-q:not(.ex-done) .ex-reveal{display:none}
.ex-q.ex-done .ex-opt[data-correct]{border-color:#16a34a;background:#f0fdf4}
.ex-q.ex-done .ex-opt.ex-picked:not([data-correct]){border-color:#dc2626;background:#fef2f2}
body:not(.ex-quiz) .ex-opt[data-correct]{border-color:#16a34a;background:#f0fdf4}
body:not(.ex-quiz) .ex-opt input{display:none}
:root[data-theme="dark"] .ex-q,:root[data-theme="dark"] .ex-part,:root[data-theme="dark"] .ex-table,:root[data-theme="dark"] .ex-rank{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-table th,:root[data-theme="dark"] .ex-rank th{background:#3a352c;color:#f5efe6}
:root[data-theme="dark"] .ex-table td,:root[data-theme="dark"] .ex-rank td,:root[data-theme="dark"] .ex-opt,:root[data-theme="dark"] .ex-items li{border-color:#3a352c}
:root[data-theme="dark"] .ex-ref,:root[data-theme="dark"] .ex-chip{background:#3a352c;color:#cfe0d6}
:root[data-theme="dark"] .ex-chip-on{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-chip-book{background:#2e1065;color:#ddd6fe}
:root[data-theme="dark"] .ex-notice{background:#3a2818;color:#fed7aa;border-color:#9a3412}
:root[data-theme="dark"] .ex-notice a{color:#fed7aa}
:root[data-theme="dark"] .ex-hit,:root[data-theme="dark"] .ex-flag,:root[data-theme="dark"] .ex-warn{background:#332a14;color:#fde68a}
:root[data-theme="dark"] .ex-dispute{background:#332a14;border-color:#92400e;color:#fde68a}
:root[data-theme="dark"] .ex-dispute-h{color:#fcd34d}:root[data-theme="dark"] .ex-sources a{color:#fde68a}
:root[data-theme="dark"] .ex-flag-note{background:#24211c;color:#d6d3cd}:root[data-theme="dark"] .ex-flag-tag{color:#a4d4c4}
:root[data-theme="dark"] .ex-ref-mckee{background:#2e1065;color:#ddd6fe}
:root[data-theme="dark"] .ex-links,:root[data-theme="dark"] .ex-progress{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-progress th,:root[data-theme="dark"] .ex-progress td{border-color:#3a352c}
:root[data-theme="dark"] .ex-progress thead th{background:#3a352c;color:#f5efe6}
:root[data-theme="dark"] .ex-pg-low{color:#fca5a5}
:root[data-theme="dark"] .ex-hit a{color:#fde68a}
:root[data-theme="dark"] .ex-badge,:root[data-theme="dark"] .ex-ok .ex-item-label{background:#14532d;color:#dcfce7}
:root[data-theme="dark"] .ex-no .ex-item-label{background:#7f1d1d;color:#fee2e2}
:root[data-theme="dark"] .ex-kicker,:root[data-theme="dark"] .ex-score,:root[data-theme="dark"] .ex-main .crumbs a,:root[data-theme="dark"] .ex-q-no a,:root[data-theme="dark"] .ex-chapter-list a{color:#a4b5a8}
:root[data-theme="dark"] .ex-toolbar button,:root[data-theme="dark"] .ex-exam-bar button,:root[data-theme="dark"] .ex-actions button{background:transparent;color:#a4b5a8;border-color:#a4b5a8}
:root[data-theme="dark"] .ex-mode[aria-pressed="true"]{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-bar{background:#a4b5a8}
:root[data-theme="dark"] .ex-q.ex-done .ex-opt[data-correct],:root[data-theme="dark"] body:not(.ex-quiz) .ex-opt[data-correct]{background:#12301d;border-color:#16a34a}
:root[data-theme="dark"] .ex-q.ex-done .ex-opt.ex-picked:not([data-correct]){background:#3a1a1a;border-color:#dc2626}
.ex-h2-sm{font-size:17px;margin:20px 0 6px}
.ex-refs{font-size:14px;line-height:1.9;padding-left:22px;margin:0 0 8px}
.ex-cta{display:inline-block;border-radius:9999px;padding:6px 16px;background:#4d6358;color:#fff;font-weight:700;text-decoration:none}
.ex-fieldset{border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin:10px 0}
.ex-fieldset legend{font-weight:700;font-size:14px;padding:0 4px}
.ex-checks{display:flex;flex-wrap:wrap;gap:6px 14px}
.ex-check{font-size:14px;display:inline-flex;align-items:center;gap:4px;margin-right:12px}
.ex-select{border:1px solid var(--border);border-radius:8px;padding:4px 8px;font-size:14px;background:#fff;color:inherit}
:root[data-theme="dark"] .ex-cta{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-select{background:#24211c;border-color:#3a352c}
.ex-layout{max-width:48rem;margin:0 auto;padding:3rem 1.25rem 4rem}
.ex-content{min-width:0}
.ex-toc-side{display:none}
@media (min-width:1100px){.ex-layout{max-width:76rem;display:grid;grid-template-columns:230px minmax(0,48rem);gap:44px;justify-content:center}.ex-toc-side{display:block;position:sticky;top:84px;align-self:start;max-height:calc(100vh - 110px);overflow:auto}.ex-toc-mobile{display:none}}
.ex-toc{border:1px solid var(--border);border-radius:12px;background:#fff;padding:10px 14px;margin-bottom:16px;font-size:13px}
.ex-toc summary{font-weight:700;cursor:pointer}
.ex-toc ol{margin:8px 0 0;padding-left:0;line-height:1.9;list-style:none}
.ex-toc a{color:var(--teal-deep);text-decoration:none}
.ex-toc-qs{font-weight:700;margin-top:6px;border-top:1px solid var(--line);padding-top:6px}
.ex-note ul{list-style:disc;padding-left:22px}
.ex-note li{margin:4px 0}
mark.ex-key{background:linear-gradient(transparent 42%,#fde9a8 42%);color:inherit;padding:0 1px}
.ex-qref{font-size:10.5px;margin-left:2px;vertical-align:super;white-space:nowrap}
.ex-qref a{color:#b45309;text-decoration:none;font-weight:600;margin-left:2px}
.ex-trap{border-left:4px solid #f87171;background:#fef5f5;border-radius:8px;padding:8px 12px;margin:10px 0;font-size:14px;line-height:1.8}
.ex-trap>strong:first-child{display:inline-block;background:#ef5350;color:#fff;border-radius:6px;font-size:11px;padding:0 7px;margin-right:8px}
.ex-n{font-family:Inter,ui-monospace,monospace;font-weight:700;color:#0c5159;white-space:nowrap}
.ex-notes-tools{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:6px 0 14px;font-size:12px;color:var(--muted)}
.ex-legend{display:inline-flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
.ex-legend-trap{border-left:3px solid #f87171;background:#fef5f5;padding:0 6px;border-radius:4px}
:root[data-theme="dark"] .ex-toc{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-toc a{color:#a4b5a8}
:root[data-theme="dark"] mark.ex-key{background:linear-gradient(transparent 42%,rgba(234,179,8,.32) 42%)}
:root[data-theme="dark"] .ex-qref a{color:#f2c14e}
:root[data-theme="dark"] .ex-trap,:root[data-theme="dark"] .ex-legend-trap{background:rgba(127,29,29,.3);border-left-color:#b45454;color:inherit}
:root[data-theme="dark"] .ex-trap>strong:first-child{background:#c24141;color:#fff}
:root[data-theme="dark"] .ex-n{color:#a4b5a8}
.ex-note{scroll-margin-top:80px}
.ex-note:target{animation:ex-flash 2.6s ease-out 1}
@keyframes ex-flash{0%,35%{background:#fef3c7;box-shadow:0 0 0 8px #fef3c7}100%{background:transparent;box-shadow:0 0 0 8px transparent}}
:root[data-theme="dark"] .ex-note:target{animation-name:ex-flash-dark}
@keyframes ex-flash-dark{0%,35%{background:#332a14;box-shadow:0 0 0 8px #332a14}100%{background:transparent;box-shadow:0 0 0 8px transparent}}
@media (prefers-reduced-motion:reduce){.ex-note:target{animation:none}}
.ex-search{margin:20px 0 6px}
.ex-search[hidden],.ex-search-results[hidden],.ex-more-wrap[hidden],.ex-rank tr[hidden]{display:none}
.ex-search-label{display:block;font-weight:700;font-size:14.5px;margin:0 0 6px}
.ex-search-input{display:block;width:100%;box-sizing:border-box;border:1.5px solid #4d6358;border-radius:12px;padding:10px 14px;font-size:16px;line-height:1.4;background:#fff;color:inherit}
.ex-search-input:focus{outline:2px solid #0c5159;outline-offset:2px}
.ex-search-hint{font-size:12px;color:var(--muted);margin:6px 0 0;line-height:1.7}
.ex-search-status{font-size:13px;color:var(--ink-2);margin:4px 0 0}
.ex-search-status:empty{display:none}
.ex-search-results{border:1px solid var(--border);border-radius:12px;background:#fff;margin-top:8px;max-height:min(62vh,560px);overflow:auto;overscroll-behavior:contain}
.ex-s-group+.ex-s-group{border-top:1px solid var(--line)}
.ex-s-ch{font-size:12.5px;font-weight:700;color:#0c5159;padding:8px 14px 2px;margin:0}
.ex-s-opt{display:block;position:relative;padding:6px 14px 7px;text-decoration:none;color:inherit;font-size:14px;line-height:1.6}
.ex-s-opt:hover,.ex-s-opt[aria-selected="true"]{background:#f1ece4}
.ex-s-opt[aria-selected="true"]{box-shadow:inset 3px 0 0 #4d6358}
.ex-s-sec{font-weight:600;color:var(--teal-deep)}
.ex-s-hit{display:block;font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.ex-s-more{font-size:12px;color:var(--muted);padding:0 14px 8px;margin:0}
.ex-more-wrap{display:flex;justify-content:flex-end;margin:-4px 0 12px}
.ex-more{border:1px solid #4d6358;border-radius:9999px;padding:6px 16px;font-size:13px;font-weight:600;background:#fff;color:#4d6358;cursor:pointer}
:root[data-theme="dark"] .ex-search-input{background:#24211c;border-color:#a4b5a8}
:root[data-theme="dark"] .ex-search-input:focus{outline-color:#a4b5a8}
:root[data-theme="dark"] .ex-search-results{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-s-group+.ex-s-group{border-color:#3a352c}
:root[data-theme="dark"] .ex-s-ch,:root[data-theme="dark"] .ex-s-sec{color:#a4b5a8}
:root[data-theme="dark"] .ex-s-opt:hover,:root[data-theme="dark"] .ex-s-opt[aria-selected="true"]{background:#3a352c}
:root[data-theme="dark"] .ex-s-opt[aria-selected="true"]{box-shadow:inset 3px 0 0 #a4b5a8}
:root[data-theme="dark"] .ex-more{background:transparent;color:#a4b5a8;border-color:#a4b5a8}
.ex-q{scroll-margin-top:80px}
.ex-answer-bar{display:none;flex-wrap:wrap;align-items:center;gap:8px;margin:2px 0 14px;padding:8px 12px;border:1px dashed var(--border);border-radius:12px;font-size:13px}
body.ex-quiz .ex-answer-bar:not([hidden]){display:flex}
.ex-answer-count{font-weight:700;color:#0c5159;margin-right:4px}
.ex-answer-bar button{border:1px solid #4d6358;border-radius:9999px;padding:4px 12px;font-size:12.5px;font-weight:600;background:#fff;color:#4d6358;cursor:pointer}
.ex-answer-bar button[aria-pressed="true"]{background:#4d6358;color:#fff}
.ex-answer-bar button:disabled{opacity:.45;cursor:default}
body.ex-quiz .ex-q.ex-hide{display:none}
.ex-resume{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:40;display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;width:max-content;max-width:calc(100% - 32px);box-sizing:border-box;background:#2f3b35;color:#fff;border-radius:12px;padding:8px 8px 8px 14px;font-size:13px;line-height:1.5;box-shadow:0 6px 20px rgba(0,0,0,.18)}
.ex-resume button{border:0;background:transparent;color:#fde9a8;font:inherit;font-weight:700;cursor:pointer;padding:4px 6px;text-decoration:underline;text-underline-offset:2px}
.ex-resume .ex-resume-close{text-decoration:none;font-size:18px;line-height:1;color:#fff}
@media (max-width:767px){.ex-resume{left:16px;right:72px;transform:none;width:auto;max-width:none}body.dn-has-sticky-cta .ex-resume{bottom:70px}}
:root[data-theme="dark"] .ex-answer-count{color:#a4b5a8}
:root[data-theme="dark"] .ex-answer-bar{border-color:#3a352c}
:root[data-theme="dark"] .ex-answer-bar button{background:transparent;color:#a4b5a8;border-color:#a4b5a8}
:root[data-theme="dark"] .ex-answer-bar button[aria-pressed="true"]{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-resume{background:#e8e2d6;color:#16140f}
:root[data-theme="dark"] .ex-resume button{color:#0c5159}
:root[data-theme="dark"] .ex-resume .ex-resume-close{color:#16140f}
</style>
"""


def main() -> int:
    check = "--check" in sys.argv
    files = build()
    stale = []
    for name, content in files.items():
        path = OUT / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    if check:
        if stale:
            print(f"exam pages out of date: {stale[:5]} (run python _gen_exam.py)")
            return 1
        return 0
    expected = set(files) | {"exam.js"}
    for path in OUT.iterdir():
        if path.is_file() and path.name not in expected:
            path.unlink()
    print(f"wrote {len(files)} exam files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
