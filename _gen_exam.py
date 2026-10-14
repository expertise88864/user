"""Generate the board-exam review section (/exam/**) from data/exam/.

Sources (hand-maintained):
  data/exam/questions.json     750 MCQs, built by _exam_import.py
  data/exam/tags.json          question id -> Fitzpatrick chapters / McKee / Kantor
  data/exam/explanations.json  per-question explanations with Fitzpatrick page refs
  data/exam/notes/fitz-<n>.frag  chapter study notes (trusted HTML fragments)
  data/exam/fitz_chapters.json chapter titles and printed page ranges

Outputs (generated, never hand-edit):
  exam/index.html, exam/fitz-<n>.html, exam/year-<y>.html, exam/mckee.html,
  exam/kantor.html, exam/review.html, exam/exam-data.json

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
HUB_TITLE = "皮膚科專科醫師考試重點及歷屆考古題"
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
    return {"questions": questions, "tags": tags, "explanations": explanations,
            "chapters": chapters, "notes": notes}


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
    f'<a href="{SOURCE_URL}" target="_blank" rel="noopener noreferrer">{SOURCE_LABEL}歷屆試題</a>'
    "，答案為學會公告的標準答案；重點與詳解依 Fitzpatrick's Dermatology 9th edition 自行整理</div>"
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


def ref_html(ref, current_chapter: int | None, chapters: dict) -> str:
    chap, pages = ref
    label = f"Fitzpatrick 9e ch.{chap} p.{pages}"
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
        flags = "".join(f'<p class="ex-warn">⚠ {rich(f)}</p>' for f in expl.get("flags", []))
        expl_html = f'<p class="ex-summary">{rich(expl["summary"])}</p><ul class="ex-items">{items}</ul>{flags}'
    else:
        homes = [f'<a href="/exam/fitz-{c}">Ch.{c}</a>' for c in tag["fitz"]]
        where = f'（相關章節：{"、".join(homes)}）' if homes else ""
        expl_html = f'<p class="ex-pending">詳解尚未整理{where}。</p>'
    return (
        f'<article class="ex-q" id="q-{qid}" data-qid="{qid}" data-answer="{"".join(sorted(answer))}">'
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


def expand_hits(fragment: str, chapter: int, on_page: set[str]) -> str:
    def repl(m: re.Match) -> str:
        ids = [i.strip() for i in m.group(1).split(",") if i.strip()]
        links = []
        for qid in ids:
            year = qid.split("-")[0]
            href = f"#q-{qid}" if qid in on_page else f"/exam/year-{year}#q-{qid}"
            links.append(f'<a href="{href}">{esc(qid)}</a>')
        return f'<span class="ex-hit">歷屆考過 {len(ids)} 題：{"、".join(links)}</span>'
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
    items.append(f'<li class="ex-toc-qs"><a href="#qs-h">歷屆考題（{qs_count} 題）</a></li>')
    cls, state, label = (("ex-toc ex-toc-mobile", "", "本章目錄（展開式）") if mobile
                         else ("ex-toc ex-toc-side", " open", "本章目錄"))
    return (f'<details class="{cls}"{state}><summary>本章目錄</summary>'
            f'<nav aria-label="{label}"><ol>{"".join(items)}</ol></nav></details>')


NOTES_TOOLS = (
    '<div class="ex-notes-tools">'
    '<span class="ex-legend"><mark class="ex-key">螢光</mark>＝歷屆考過（後附題號）'
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
                      f'{NOTES_TOOLS}{expand_marks(expand_hits(note, n, on_page), on_page)}</section>')
    else:
        notes_html = '<section class="ex-notes"><h2 class="ex-h2">重點整理</h2><p class="ex-pending">這一章的重點尚未整理。</p></section>'
    year_text = "、".join(f"{y} 年 {c} 題" for y, c in sorted(years.items()))
    body = (
        f'<p class="ex-kicker">Fitzpatrick 9e · {esc(chapter["part"].title() if chapter["part"] else "")}</p>'
        f'<h1 class="ex-h1">Ch.{n} {esc(chapter["title"])}</h1>'
        f'<p class="ex-meta">原書 p.{chapter["pageStart"]}–{chapter["pageEnd"]} · 歷屆共 {len(qs)} 題'
        f'（已有詳解 {explained} 題）</p>'
        f'<p class="ex-meta">{esc(year_text)}</p>{NOTICE}{toc_html(note, len(qs), mobile=True)}{notes_html}'
        f'<section aria-labelledby="qs-h"><h2 id="qs-h" class="ex-h2">歷屆考題</h2>{MODE_BAR}'
        + "".join(question_html(q, data, current_chapter=n) for q in qs)
        + "</section>"
    )
    title = f"Fitzpatrick Ch.{n} {chapter['title']} 重點與歷屆考題"
    desc = (f"皮膚科專科醫師考試讀書筆記：Fitzpatrick's Dermatology 9e 第 {n} 章 {chapter['title']}"
            f"，整理 101–115 年歷屆考題 {len(qs)} 題" + ("與重點整理" if note else "") + "。")
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
        f'<p class="ex-meta">主要考 {esc(name)} 內容的歷屆題，共 {len(qs)} 題。'
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
        '<p class="ex-pending">選好年份、題數與順序後按「產生試卷」。這個功能需要啟用 JavaScript；'
        '也可以直接到首頁選擇單一年度的考古卷。</p></div>'
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
    desc = "皮膚科專科醫師考試讀書筆記的錯題本：集中重練作答模式答錯的歷屆題，並可匯出 Anki 卡片。"
    return page(shell, path="/exam/review", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[("錯題本", "/exam/review")],
                jsonld_type="WebPage", body=body, page_kind="review")


def hub_page(shell, data, by_chapter, by_year, by_book) -> str:
    chapters = data["chapters"]
    total = len(data["questions"])
    explained = len(data["explanations"])
    ranked = sorted(by_chapter.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    top = ranked[:25]
    peak = len(top[0][1]) if top else 1
    rows = "".join(
        f'<tr><td><a href="/exam/fitz-{n}">Ch.{n} {esc(chapters[n]["title"])}</a>'
        f'{" <span class=\"ex-badge\">有重點</span>" if n in data["notes"] else ""}</td>'
        f'<td class="ex-num">{len(qs)}</td>'
        f'<td class="ex-bar-cell"><span class="ex-bar" style="width:{round(100 * len(qs) / peak)}%"></span></td></tr>'
        for n, qs in top
    )
    parts = defaultdict(list)
    for n, ch in sorted(chapters.items()):
        parts[ch["part"]].append(n)
    part_html = []
    for part, nums in parts.items():
        items = "".join(
            f'<li><a href="/exam/fitz-{n}">Ch.{n} {esc(chapters[n]["title"])}</a>'
            f' <span class="ex-count">{len(by_chapter[n])} 題</span>'
            f'{" <span class=\"ex-badge\">有重點</span>" if n in data["notes"] else ""}</li>'
            if n in by_chapter else
            f'<li class="ex-none">Ch.{n} {esc(chapters[n]["title"])} <span class="ex-count">0 題</span></li>'
            for n in nums
        )
        count = sum(len(by_chapter.get(n, [])) for n in nums)
        part_html.append(
            f'<details class="ex-part"><summary>{esc((part or "").title())} <span class="ex-count">{count} 題次</span></summary>'
            f'<ul class="ex-chapter-list">{items}</ul></details>'
        )
    years = "".join(f'<li><a href="/exam/year-{y}">{y} 年</a></li>' for y in sorted(by_year))
    books = "".join(
        f'<li><a href="/exam/{b}">{esc(OTHER_BOOKS[b][1])}題（{esc(OTHER_BOOKS[b][0])}）</a> <span class="ex-count">{len(qs)} 題</span></li>'
        for b, qs in sorted(by_book.items())
    )
    refs = "".join(f"<li>{esc(book)}</li>" for book in REFERENCE_BOOKS)
    body = (
        f'<h1 class="ex-h1">{HUB_TITLE}</h1>'
        '<p class="ex-lead">目前整理 101–115 年歷屆選擇題以及各章節重點整理（陸續更新中）</p>'
        '<h2 class="ex-h2 ex-h2-sm">目前甄審筆試出題參考範圍</h2>'
        f'<ol class="ex-refs">{refs}</ol>{NOTICE}'
        '<h2 class="ex-h2">出題頻率：最常考的 25 章</h2>'
        '<p class="ex-meta">一題可能計入多章，所以加總會超過題數。</p>'
        '<table class="ex-rank"><thead><tr><th scope="col">章節</th><th scope="col">題數</th><th scope="col"><span class="ex-sr">比例</span></th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        '<h2 class="ex-h2">考古卷</h2>'
        '<p class="ex-meta"><a class="ex-cta" href="/exam/practice">自選年份／隨機出題</a></p>'
        '<p class="ex-meta">或依年度照原卷順序作答，可計時並交卷計分：</p>'
        f'<ul class="ex-years">{years}</ul>'
        '<h2 class="ex-h2">依章節瀏覽</h2>' + "".join(part_html)
        + '<h2 class="ex-h2">其他參考書與工具</h2>'
        f'<ul class="ex-chapter-list">{books}<li><a href="/exam/review">錯題本與 Anki 匯出</a></li></ul>'
    )
    title = HUB_TITLE
    desc = (f"皮膚科專科醫師甄審筆試 101–115 年歷屆選擇題 {total} 題，依 Fitzpatrick 9e 章節整理重點，"
            "附出題頻率統計、自選年份或隨機出題的考古卷、錯題本與 Anki 匯出。")
    return page(shell, path="/exam", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=HUB_TITLE, crumbs=[],
                jsonld_type="CollectionPage", body=body, page_kind="hub")


def client_data(data) -> dict:
    """Compact data for the review page and Anki export."""
    out = []
    for q in data["questions"]:
        row = {k: q[k] for k in ("id", "year", "number", "stem", "options", "answer")}
        if q.get("statements"):
            row["statements"] = q["statements"]
        row["fitz"] = data["tags"][q["id"]]["fitz"]
        expl = data["explanations"].get(q["id"])
        if expl:
            row["expl"] = {"summary": expl["summary"], "items": [
                {"key": it["key"], "label": it["label"], "text": it["text"],
                 "refs": [f"ch.{c} p.{p}" for c, p in it["refs"]]} for it in expl["items"]]}
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
    for qid in data["explanations"]:
        if not data["tags"][qid]["fitz"]:
            raise SystemExit(f"{qid} has an explanation but no Fitzpatrick chapter")
    CHAPTER_PAGES.clear()
    CHAPTER_PAGES.update(by_chapter)
    client = json.dumps(client_data(data), ensure_ascii=False, separators=(",", ":")) + "\n"
    DATA_VERSION[0] = hashlib.sha256(client.encode("utf-8")).hexdigest()[:10]
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
.ex-chapter-list a,.ex-years a{color:var(--teal-deep)}
.ex-none{color:var(--muted)}
.ex-years{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}
.ex-years a{display:inline-block;border:1px solid var(--border);border-radius:9999px;padding:4px 14px;background:#fff;text-decoration:none;font-weight:600}
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
.ex-pending{font-size:13px;color:var(--muted)}
body.ex-quiz .ex-actions{display:flex}
body.ex-quiz .ex-q:not(.ex-done) .ex-reveal{display:none}
.ex-q.ex-done .ex-opt[data-correct]{border-color:#16a34a;background:#f0fdf4}
.ex-q.ex-done .ex-opt.ex-picked:not([data-correct]){border-color:#dc2626;background:#fef2f2}
body:not(.ex-quiz) .ex-opt[data-correct]{border-color:#16a34a;background:#f0fdf4}
body:not(.ex-quiz) .ex-opt input{display:none}
:root[data-theme="dark"] .ex-q,:root[data-theme="dark"] .ex-part,:root[data-theme="dark"] .ex-table,:root[data-theme="dark"] .ex-rank,:root[data-theme="dark"] .ex-years a{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-table th,:root[data-theme="dark"] .ex-rank th{background:#3a352c;color:#f5efe6}
:root[data-theme="dark"] .ex-table td,:root[data-theme="dark"] .ex-rank td,:root[data-theme="dark"] .ex-opt,:root[data-theme="dark"] .ex-items li{border-color:#3a352c}
:root[data-theme="dark"] .ex-ref,:root[data-theme="dark"] .ex-chip{background:#3a352c;color:#cfe0d6}
:root[data-theme="dark"] .ex-chip-on{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-chip-book{background:#2e1065;color:#ddd6fe}
:root[data-theme="dark"] .ex-notice{background:#3a2818;color:#fed7aa;border-color:#9a3412}
:root[data-theme="dark"] .ex-notice a{color:#fed7aa}
:root[data-theme="dark"] .ex-hit,:root[data-theme="dark"] .ex-flag,:root[data-theme="dark"] .ex-warn{background:#332a14;color:#fde68a}
:root[data-theme="dark"] .ex-hit a{color:#fde68a}
:root[data-theme="dark"] .ex-badge,:root[data-theme="dark"] .ex-ok .ex-item-label{background:#14532d;color:#dcfce7}
:root[data-theme="dark"] .ex-no .ex-item-label{background:#7f1d1d;color:#fee2e2}
:root[data-theme="dark"] .ex-kicker,:root[data-theme="dark"] .ex-score,:root[data-theme="dark"] .ex-main .crumbs a,:root[data-theme="dark"] .ex-q-no a,:root[data-theme="dark"] .ex-chapter-list a,:root[data-theme="dark"] .ex-years a{color:#a4b5a8}
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
