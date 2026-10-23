"""Generate the board-exam review section (/exam/**) from data/exam/.

Sources (hand-maintained):
  data/exam/questions.json     750 MCQs, built by _exam_import.py
  data/exam/tags.json          question id -> Fitzpatrick chapters / McKee / Kantor
  data/exam/explanations.json  per-question explanations with Fitzpatrick page refs
  data/exam/notes/fitz-<n>.frag  chapter study notes (trusted HTML fragments)
  data/exam/fitz_chapters.json chapter titles and printed page ranges
  data/exam/links.json         chapter DermNet / PathologyOutlines links
  data/exam/search_aliases.json  chapter -> standard abbreviations for the hub search
  data/exam/timemachine.json   physician-approved 「考試當年 vs 現行觀念」 notes per question
                               (text is verbatim; validated by validate_timemachine)
  data/exam/concepts/concepts.json  考點 (exam concepts), built by _import_exam_concepts.py
  data/exam/mock.json          模擬題 (newly written practice questions, NOT official exam
                               questions; validated by validate_mock). Used only by the
                               practice page's 模擬考 option, never by chapter/year pages,
                               concepts, the time machine, search or exam-data.json

Outputs (generated, never hand-edit):
  exam/index.html, exam/fitz-<n>.html, exam/year-<y>.html, exam/mckee.html,
  exam/kantor.html, exam/review.html, exam/concepts.html, exam/exam-data.json,
  exam/search-index.json, exam/nav-search.json, exam/mock-data.json

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
    tm_path = DATA / "timemachine.json"
    timemachine = json.loads(tm_path.read_text(encoding="utf-8")) if tm_path.exists() else {}
    errors = validate_timemachine(timemachine, {q["id"] for q in questions})
    if errors:
        raise SystemExit("timemachine.json is invalid:\n  " + "\n  ".join(errors))
    concepts_path = DATA / "concepts" / "concepts.json"
    concept_data = (json.loads(concepts_path.read_text(encoding="utf-8")) if concepts_path.exists()
                    else {"_meta": {"rule": ""}, "concepts": []})
    qids = {q["id"] for q in questions}
    for c in concept_data["concepts"]:
        unknown_q = [h["q"] for h in c["how"] if h["q"] not in qids]
        if unknown_q or any(ch not in chapters for ch in c["chs"]):
            raise SystemExit(f"concepts.json {c['id']}: unknown question/chapter {unknown_q or c['chs']}")
    mock_path = DATA / "mock.json"
    mock = (json.loads(mock_path.read_text(encoding="utf-8")) if mock_path.exists()
            else {"_meta": {"label": MOCK_LABEL}, "questions": []})
    errors = validate_mock(mock, chapters)
    if errors:
        raise SystemExit("mock.json is invalid:\n  " + "\n  ".join(errors))
    return {"questions": questions, "tags": tags, "explanations": explanations,
            "chapters": chapters, "notes": notes, "links": links, "aliases": aliases,
            "timemachine": timemachine, "mock": mock["questions"],
            "concepts": concept_data["concepts"], "concept_rule": concept_data["_meta"]["rule"],
            "qmap": {q["id"]: q for q in questions}}


# ---------------------------------------------------------------- time machine
# 「考試當年 vs 現行觀念」: what the exam assumed in its year, what changed since,
# and whether the official answer still holds. The text is approved by the
# physician (D-01) and rendered verbatim; only escaping and layout are ours.

TM_LEVELS = ("不影響", "依現行觀念答案會不同")
TM_TEXT_FIELDS = ("then", "now", "changed")
# Simplified-only characters (each has a distinct Traditional form the site
# uses). Narrow on purpose: characters valid in both scripts (台、后、里、干…)
# are not listed, so a hit is always a real mistake.
HANS_ONLY = frozenset(
    "这们来时为说对会发过还进见现实问题经应样学没开关长门东车书产业从众优伤价儿写军农剂剧办动劳区医华单卖"
    "卫历压县参双变号吗听员围图国圆场坏块声处备复头夺奋妇宁宝将尔层岁岛带帮广庆张录怀态总恶惊战扩扫报护"
    "拥择换损据数断无旧显术机杀杂权条极构标检残气汉汤沟济测浓湿满灭灯炉点热爱状犹独环疗痒皱盐监盖盘确礼"
    "种积称稳穷简类粮纠红约级纪纤纸线练组细织终结给络统绝续维综绿缓编缩网罗职联肠肤肾肿胀胆胶脑脏脓脱节"
    "药获虽补观规视览觉触计认讨让训议记讲许论设证评识诊词试诚话该详语误请读谁调谈质贫购费资赖赶践转轻较"
    "辅边运远连选适遗释针钙钠钾铁银链销锌镜闭间阳阴际陆随隐难页项须预领频颈颜风饮马验鱼鸟齿龄疮疡癣疯痉"
    "挛螨体"
)


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def validate_timemachine(tm, qids: set[str]) -> list[str]:
    """Every entry: a known question, the three text fields, an allowed impact
    level with a note, at least one source and a http(s) url on every source,
    and no simplified-only characters anywhere."""
    if not isinstance(tm, dict):
        return ["top level must be an object keyed by question id"]
    errors = []
    for qid, entry in tm.items():
        if qid not in qids:
            errors.append(f"{qid}: unknown question id")
        if not isinstance(entry, dict):
            errors.append(f"{qid}: entry must be an object")
            continue
        for field in TM_TEXT_FIELDS:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(f"{qid}: missing text '{field}'")
        impact = entry.get("answer_impact")
        if not isinstance(impact, dict):
            errors.append(f"{qid}: missing answer_impact")
        else:
            if impact.get("level") not in TM_LEVELS:
                errors.append(f"{qid}: answer_impact.level must be one of {list(TM_LEVELS)}, got {impact.get('level')!r}")
            if not isinstance(impact.get("note"), str) or not impact["note"].strip():
                errors.append(f"{qid}: missing answer_impact.note")
        sources = entry.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{qid}: needs at least one source")
        else:
            for i, src in enumerate(sources):
                if not isinstance(src, dict) or not isinstance(src.get("title"), str) or not src["title"].strip():
                    errors.append(f"{qid}: source {i + 1} has no title")
                url = src.get("url") if isinstance(src, dict) else None
                if not isinstance(url, str) or not re.fullmatch(r"https?://\S+", url):
                    errors.append(f"{qid}: source {i + 1} has no url")
        hans = sorted({c for text in _strings(entry) for c in text if c in HANS_ONLY})
        if hans:
            errors.append(f"{qid}: simplified characters {''.join(hans)}")
    return errors


# ---------------------------------------------------------------- mock exam
# 模擬題: questions written for practice from the two textbooks, each checked by
# a separate blind solver and a line-by-line source check before it is added.
# They are never official exam questions, so every place that shows one says so.

MOCK_LABEL = "模擬題，非官方考題"
MOCK_ID = re.compile(r"M-\d{2,3}")
SINGLE_KEYS = ["A", "B", "C", "D"]
COMBO_OPTIONS = {"A": "①③", "B": "②④", "C": "①②③", "D": "④", "E": "①②③④"}
STATEMENT_IDS = ["①", "②", "③", "④"]
MOCK_POLARITY = ("positive", "negative")


def validate_mock(mock, chapters: dict) -> list[str]:
    """Shape of every mock question, its explanation and refs; for combination
    questions the answer must be exactly the true (positive stem) or false
    (negative stem) statements; no simplified-only characters."""
    if not isinstance(mock, dict) or not isinstance(mock.get("questions"), list):
        return ["top level must be {_meta, questions: [...]}"]
    if not isinstance(mock.get("_meta"), dict) or mock["_meta"].get("label") != MOCK_LABEL:
        return [f"_meta.label must be {MOCK_LABEL!r}"]
    errors, seen = [], set()
    for q in mock["questions"]:
        qid = q.get("id") if isinstance(q, dict) else None
        if not isinstance(qid, str) or not MOCK_ID.fullmatch(qid):
            errors.append(f"bad id {qid!r}")
            continue
        if qid in seen:
            errors.append(f"{qid}: duplicate id")
        seen.add(qid)
        for field in ("stem", "topic"):
            if not isinstance(q.get(field), str) or not q[field].strip():
                errors.append(f"{qid}: missing {field}")
        fitz = q.get("fitz")
        if not isinstance(fitz, list) or not fitz or any(c not in chapters for c in fitz):
            errors.append(f"{qid}: fitz must list known chapters, got {fitz!r}")
        answer, options = q.get("answer"), q.get("options")
        if not isinstance(answer, list) or len(answer) != 1 or not isinstance(options, dict) or answer[0] not in options:
            errors.append(f"{qid}: answer must be one option key")
            continue
        expl = q.get("expl")
        items = expl.get("items") if isinstance(expl, dict) else None
        if not isinstance(items, list) or not isinstance(expl.get("summary"), str) or not expl["summary"].strip():
            errors.append(f"{qid}: missing explanation")
            continue
        keys = [it.get("key") if isinstance(it, dict) else None for it in items]
        if q.get("statements") is not None:
            ids = [s.get("id") for s in q["statements"]] if isinstance(q["statements"], list) else None
            if ids != STATEMENT_IDS or options != COMBO_OPTIONS:
                errors.append(f"{qid}: combination questions need statements ①②③④ and options {COMBO_OPTIONS}")
            elif keys != STATEMENT_IDS:
                errors.append(f"{qid}: explanation items must be ①②③④")
            elif q.get("polarity") not in MOCK_POLARITY:
                errors.append(f"{qid}: polarity must be one of {list(MOCK_POLARITY)}")
            else:
                want = q["polarity"] == "positive"
                chosen = "".join(it["key"] for it in items if bool(it.get("ok")) == want)
                if COMBO_OPTIONS[answer[0]] != chosen:
                    errors.append(f"{qid}: answer {answer[0]} does not match statements {chosen or '(none)'}")
        else:
            if list(options) != SINGLE_KEYS:
                errors.append(f"{qid}: single-answer questions need options A-D")
            elif keys != SINGLE_KEYS:
                errors.append(f"{qid}: explanation items must be A-D")
            elif [it["key"] for it in items if it.get("ok")] != answer:
                errors.append(f"{qid}: explanation ok flags do not match the answer")
        for it in items:
            if not isinstance(it, dict):
                continue
            for field in ("label", "text"):
                if not isinstance(it.get(field), str) or not it[field].strip():
                    errors.append(f"{qid} {it.get('key')}: missing {field}")
            refs = it.get("refs")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{qid} {it.get('key')}: needs at least one textbook ref")
                continue
            for ref in refs:
                ok = (isinstance(ref, list) and len(ref) == 2 and (ref[0] == "M" or ref[0] in chapters)
                      and isinstance(ref[1], str) and re.fullmatch(r"\d+(?:[–-]\d+)?", ref[1]))
                if not ok:
                    errors.append(f"{qid} {it.get('key')}: bad ref {ref!r}")
        hans = sorted({c for text in _strings(q) for c in text if c in HANS_ONLY})
        if hans:
            errors.append(f"{qid}: simplified characters {''.join(hans)}")
    return errors


def mock_client_data(data) -> dict:
    """The 模擬考 bank for the practice page (same row shape as exam-data.json)."""
    out = []
    for q in data["mock"]:
        row = {"id": q["id"], "mock": True, "stem": q["stem"], "options": q["options"], "answer": q["answer"],
               "fitz": q["fitz"]}
        if q.get("statements"):
            row["statements"] = q["statements"]
        row["expl"] = {"summary": q["expl"]["summary"], "items": [
            {"key": it["key"], "label": it["label"], "ok": it["ok"], "text": it["text"],
             "refs": [ref_label(r) for r in it["refs"]]} for it in q["expl"]["items"]]}
        out.append(row)
    return {"label": MOCK_LABEL, "questions": out}


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
MOCK_VERSION = [""]  # content hash of mock-data.json, set by build()


def script_version() -> str:
    """Content hash of exam/exam.js so browsers refetch it whenever it changes."""
    raw = (OUT / "exam.js").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()[:10]


def page(shell, *, path, title, description, og_title, crumbs, jsonld_type, body, page_kind, toc="",
         mock_data=False) -> str:
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
    mock_attr = f' data-mock-data="/exam/mock-data.json?v={MOCK_VERSION[0]}"' if mock_data else ""
    main = (f'<main id="main-content" class="ex-main" data-exam-page="{page_kind}" '
            f'data-exam-data="/exam/exam-data.json?v={DATA_VERSION[0]}"{mock_attr}>{inner}</main>')
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
    expl_html += timemachine_html(data["timemachine"].get(qid))
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


def timemachine_html(tm: dict | None) -> str:
    """The 「考試當年 vs 現行觀念」 box, last inside .ex-expl so quiz mode hides it
    together with the answer until the question is graded."""
    if not tm:
        return ""
    impact = tm["answer_impact"]
    level_cls = "ex-tm-diff" if impact["level"] == TM_LEVELS[1] else "ex-tm-same"
    rows = "".join(f"<dt>{label}</dt><dd>{rich(tm[key])}</dd>"
                   for label, key in (("考試當年", "then"), ("現行觀念", "now"), ("何時改變", "changed")))
    rows += (f'<dt>對答案的影響</dt><dd><span class="ex-tm-level {level_cls}">{esc(impact["level"])}</span>'
             f'{rich(impact["note"])}</dd>')
    return ('<div class="ex-tm"><p class="ex-tm-h">考試當年 vs 現行觀念</p>'
            f'<dl class="ex-tm-rows">{rows}</dl><p class="ex-tm-src-h">參考文獻</p>'
            f'<ul class="ex-sources">{"".join(source_html(s) for s in tm["sources"])}</ul></div>')


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


NOTE_SECTION = re.compile(r'<section class="ex-note" id="([a-z0-9-]+)">(.*?)</section>', re.S)


def add_note_weights(rendered: str) -> str:
    """Add data-w="<weight>" to every rendered note section's start tag.

    The weight is the number of non-whitespace characters of the section's
    visible text (at least 1); exam.js uses it to size the time a section must
    stay on screen and to weigh each section in the chapter's reading coverage.
    Done on the rendered HTML, so the .frag sources stay untouched.
    """
    def repl(m: re.Match) -> str:
        text = html.unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        weight = max(1, len(re.sub(r"\s+", "", text)))
        return f'<section class="ex-note" id="{m.group(1)}" data-w="{weight}">{m.group(2)}</section>'
    return NOTE_SECTION.sub(repl, rendered)


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
SECTION = re.compile(r'<section class="ex-note" id="([a-z0-9-]+)"(?: data-w="\d+")?>\s*<h2>(.*?)</h2>', re.S)


def expand_marks(fragment: str, on_page: set[str]) -> str:
    """<mark data-q="102-42,105-21">fact</mark> -> highlighted fact + plain question numbers.

    The superscripts are labels, not links: a mistaken tap must not jump the
    reader away from the notes (user request 2026-10-23).
    """
    def repl(m: re.Match) -> str:
        ids = [esc(i.strip()) for i in m.group(1).split(",") if i.strip()]
        return f'<mark class="ex-key">{m.group(2)}</mark><span class="ex-qref">{" ".join(ids)}</span>'
    return MARK.sub(repl, fragment)


CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
ZH_PAREN = re.compile(r"（[^（）]*）")
TAGS = re.compile(r"<[^>]+>")


def toc_label(title: str) -> tuple[str, str]:
    """(label html, plain full heading) for one 本章目錄 entry.

    Owner decision 2026-10-22: the outline shows English only so entries stay
    short. The label is the heading without its full-width parenthetical(s)
    that hold Chinese (「9. Drug-Induced Lichenoid Eruptions（苔蘚樣藥疹）」 ->
    「9. Drug-Induced Lichenoid Eruptions」); an abbreviation such as （NK） is
    kept. A heading with no English left (Chinese only) keeps its full text.
    The full heading goes to the tooltip and the accessible name."""
    full = re.sub(r"\s+", " ", TAGS.sub("", title)).strip()
    label = ZH_PAREN.sub(lambda m: "" if CJK.search(TAGS.sub("", m.group(0))) else m.group(0), title)
    label = re.sub(r"\s+", " ", label)
    label = re.sub(r"\s+([：；，、])", r"\1", label).strip()
    label = re.sub(r"[\s：；，、:;,]+$", "", label)
    if not re.search(r"[A-Za-z]", re.sub(r"^\d+\.\s*", "", TAGS.sub("", label))):
        label = title.strip()
    return label, full


def toc_item(sid: str, title: str) -> str:
    label, full = toc_label(title)
    name = re.sub(r"\s+", " ", TAGS.sub("", label)).strip()
    extra = f' title="{full}" aria-label="{full}"' if name != full else ""
    return f'<li><a href="#{sid}"{extra}>{label}</a></li>'


def toc_html(note: str | None, qs_count: int, *, mobile: bool = False, concepts: int = 0) -> str:
    items = [toc_item(sid, title) for sid, title in SECTION.findall(note or "")]
    if concepts:  # the 本章考點 block sits between the notes and the questions
        items.append(f'<li class="ex-toc-cx"><a href="#concepts-h">本章考點（{concepts}）</a></li>')
    if qs_count:  # chapters never tested have notes only
        items.append(f'<li class="ex-toc-qs"><a href="#qs-h">考題（{qs_count} 題）</a></li>')
    cls, state, label = (("ex-toc ex-toc-mobile", "", "本章目錄（展開式）") if mobile
                         else ("ex-toc ex-toc-side", " open", "本章目錄"))
    return (f'<details class="{cls}"{state}><summary>本章目錄</summary>'
            f'<nav aria-label="{label}"><ol>{"".join(items)}</ol></nav></details>')


# ---------------------------------------------------------------- concepts (考點)
# data/exam/concepts/concepts.json lists every concept with one 考法 sentence per
# question that tested it and the misconceptions its wrong options relied on
# (counts already filtered by _import_exam_concepts.py). Chapter pages show the
# chapter's own concepts; /exam/concepts lists all of them. Everything is static
# HTML in collapsed <details>; exam.js only adds search, filter and paging.

# Doctor approved the layout 2026-10-18: every chapter page that has study notes
# (data/exam/notes/fitz-<n>.frag) gets a 「本章考點」 block. Chapters without notes
# show none yet; their concepts are still listed on the overview page.
CONCEPT_PAGE_SIZE = 50
FLAG_LABELS = {"official_conflict": "官方答案有疑義"}


def concept_name(c: dict) -> str:
    """Chinese name on its own line, the English name below it in small muted type
    (doctor decision 2026-10-18: no back-to-back brackets such as 「（Dsg1）（PF autoantigen）」)."""
    en = f"<small>{esc(c['en'])}</small>" if c["en"] else ""
    return f'<span class="cx-name">{esc(c["zh"])}{en}</span>'


def qid_href(qid: str, on_page: set[str]) -> str:
    return f"#q-{qid}" if qid in on_page else f"/exam/year-{qid.split('-')[0]}#q-{qid}"


def concept_item(c: dict, data: dict, *, on_page: set[str], current_chapter: int | None,
                 overview: bool) -> str:
    """One concept as a collapsed <details>. The overview repeats this 2,000+ times,
    so the markup is terse: inside .cx-meta / .cx-how / .cx-traps, <b> <i> <em>
    are styled chips (see EXAM_STYLE), not emphasis."""
    qs = data["qmap"]
    n_traps = sum(t["n"] for t in c["traps"])
    meta = f'<b>{len(c["how"])} 題</b>'
    if overview:
        meta += f'<i>Ch.{c["ch"]}</i>'
    if n_traps:
        meta += f"<em>陷阱 {n_traps} 次</em>"
    meta += f'<span>{"・".join(str(y) for y in c["years"])} 年</span>'
    how = []
    for h in sorted(c["how"], key=lambda h: h["q"]):
        q = qs[h["q"]]
        tag = "<em>誘答</em>" if h.get("trap") else ""
        flags = "".join(f'<em class="cx-flag">{esc(FLAG_LABELS.get(f, f))}</em>' for f in h.get("flags", []))
        how.append(f'<li><a href="{qid_href(h["q"], on_page)}">{q["year"]} 年第 {q["number"]} 題</a>'
                   f'<b>{esc("".join(h["k"]))}</b>{tag}{flags}<span>{esc(h["t"])}</span></li>')
    parts = f'<ul class="cx-how" aria-label="考法">{"".join(how)}</ul>'
    if c["traps"]:
        traps = "".join(
            f'<li>{esc(t["desc"])}<b>{t["n"]} 次{"（%d 題）" % t["nq"] if t["nq"] != t["n"] else ""}</b></li>'
            for t in c["traps"])
        parts += f'<p class="cx-h">常被當成陷阱的錯誤觀念</p><ul class="cx-traps">{traps}</ul>'
    chips = []
    for ch in c["chs"]:
        # The overview names only the concept's own chapter in full (the filter lists every title).
        label = esc(f"Ch.{ch} {data['chapters'][ch]['title']}" if ch == c["ch"] or not overview else f"Ch.{ch}")
        if ch == c["ch"]:
            label = f"<strong>{label}</strong>"
        if ch == current_chapter or ch not in CHAPTER_PAGES:
            chips.append(label)
        else:
            chips.append(f'<a href="/exam/fitz-{ch}">{label}</a>')
    parts += f'<p class="cx-chs">牽涉章節：{"、".join(chips)}</p>'
    # data-ch: every chapter involved, the concept's own chapter first.
    chs = [c["ch"]] + [ch for ch in c["chs"] if ch != c["ch"]]
    attrs = f' data-ch="{" ".join(map(str, chs))}"' if overview else ""
    return (f'<li id="c-{c["id"]}"{attrs}><details><summary>{concept_name(c)}'
            f'<span class="cx-meta">{meta}</span></summary><div>{parts}</div></details></li>')


def concept_rule(data: dict) -> str:
    return f'<p class="cx-rule"><strong>統計方式</strong>：{esc(data["concept_rule"])}</p>'


def chapter_concepts_html(data: dict, n: int, on_page: set[str]) -> tuple[str, int]:
    """「本章考點」 block of a chapter page and its concept count (0 = no block)."""
    if n not in data["notes"]:
        return "", 0
    own = [c for c in data["concepts"] if c["ch"] == n]
    if not own:
        return "", 0
    items = "".join(concept_item(c, data, on_page=on_page, current_chapter=n, overview=False) for c in own)
    # Concepts of other chapters that this page's own questions tested.
    also = []
    for c in data["concepts"]:
        if c["ch"] != n:
            here = sum(1 for h in c["how"] if h["q"] in on_page)
            if here:
                also.append((c, here))
    also_html = ""
    if also:
        lis = "".join(
            f'<li><a href="/exam/concepts#c-{c["id"]}">{concept_name(c)}</a>'
            f'<span class="cx-meta"><i>Ch.{c["ch"]}</i><span>本章 {here} 題</span></span></li>'
            for c, here in sorted(also, key=lambda x: (-x[1], x[0]["ch"], x[0]["id"])))
        also_html = (f'<details class="cx-also"><summary>本章考題也考到的其他章考點（{len(also)}）</summary>'
                     f'<ul>{lis}</ul></details>')
    total_q = len({h["q"] for c in own for h in c["how"]})
    html_out = (
        '<section class="cx-block" aria-labelledby="concepts-h">'
        f'<h2 id="concepts-h" class="ex-h2">本章考點</h2>'
        f'<p class="ex-meta">本章 {len(own)} 個考點，出現在 {total_q} 題，依考過的題數排序。'
        '點開考點可看到每一次的考法；題號可直接跳到該題。'
        f'<a href="/exam/concepts?ch={n}">所有章節的考點請見考點總覽</a>。</p>'
        f'{concept_rule(data)}<ol class="cx-list">{items}</ol>{also_html}</section>'
    )
    return html_out, len(own)


def concepts_page(shell, data, by_chapter) -> str:
    concepts = data["concepts"]
    items = "".join(concept_item(c, data, on_page=set(), current_chapter=None, overview=True) for c in concepts)
    per_chapter = Counter(ch for c in concepts for ch in c["chs"])
    options = "".join(
        f'<option value="{ch}">Ch.{ch} {esc(data["chapters"][ch]["title"])}（{per_chapter[ch]}）</option>'
        for ch in sorted(per_chapter))
    n_q = len({h["q"] for c in concepts for h in c["how"]})
    multi = sum(1 for c in concepts if len(c["how"]) >= 2)
    body = (
        '<p class="ex-kicker">考點</p><h1 class="ex-h1">考點總覽</h1>'
        f'<p class="ex-lead">把 101–115 年 {n_q} 題拆成 {len(concepts)} 個考點，其中 {multi} 個考過兩題以上。'
        '預設依考過的題數排序，考得多的排前面；點開考點可看到每一次的考法、牽涉的章節，'
        '以及常被拿來當陷阱的錯誤觀念。</p>'
        f'{NOTICE}{concept_rule(data)}'
        '<div class="cx-tools" data-cx-tools hidden>'
        '<label class="ex-search-label" for="cx-q">搜尋考點（中文、英文或考法）</label>'
        '<input id="cx-q" class="ex-search-input cx-q" type="search" autocomplete="off" autocapitalize="off" '
        'spellcheck="false" enterkeyhint="search" placeholder="例如 pemphigus、Dsg1、光敏感" aria-controls="cx-all">'
        '<div class="cx-filters">'
        '<label class="ex-check">章節 <select class="ex-select cx-ch-select" aria-label="依章節篩選" aria-controls="cx-all">'
        f'<option value="">全部章節</option>{options}</select></label>'
        '<label class="ex-check">排序 <select class="ex-select cx-sort" aria-label="排序方式" aria-controls="cx-all">'
        '<option value="n">考過的題數</option><option value="ch">章節順序</option></select></label></div>'
        '<p class="cx-status" role="status" aria-live="polite"></p></div>'
        f'<ol class="cx-list" id="cx-all" data-cx-page="{CONCEPT_PAGE_SIZE}">{items}</ol>'
        '<p class="ex-pending cx-empty" hidden>沒有符合的考點，請換個關鍵字或章節。</p>'
        '<div class="ex-more-wrap cx-more-wrap" hidden>'
        '<button type="button" class="ex-more" aria-controls="cx-all">載入更多</button></div>'
    )
    title = "皮膚科專科醫師考試考點總覽"
    desc = (f"皮膚科專科醫師甄審筆試 101–115 年考題拆解的 {len(concepts)} 個考點，依出題次數排序，"
            "列出每次的考法、牽涉的 Fitzpatrick 章節與常見陷阱選項。")
    return page(shell, path="/exam/concepts", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[("考點總覽", "/exam/concepts")],
                jsonld_type="CollectionPage", body=body, page_kind="concepts")


NOTES_TOOLS = (
    '<div class="ex-notes-tools">'
    '<span class="ex-legend"><mark class="ex-key">螢光</mark>＝考過（後附題號）'
    '<span class="ex-legend-trap">紅框</span>＝易錯陷阱'
    '<strong class="ex-n">粗體數字</strong>＝門檻值</span></div>'
)


# Filled and unhidden by exam.js (reading coverage of this chapter's notes);
# stays hidden without JS or storage.
READING_STATUS = '<p class="ex-reading" id="ex-reading" hidden></p>'


# ---------------------------------------------------------------- pages

def chapter_page(shell, data, chapter: dict, qs: list[dict]) -> str:
    n = chapter["chapter"]
    years = Counter(q["year"] for q in qs)
    on_page = {q["id"] for q in qs}
    note = data["notes"].get(n)
    explained = sum(1 for q in qs if q["id"] in data["explanations"])
    if note:
        notes_html = (f'<section class="ex-notes" aria-labelledby="notes-h"><h2 id="notes-h" class="ex-h2">重點整理</h2>'
                      f'{NOTES_TOOLS}{READING_STATUS}'
                      f'{add_note_weights(wrap_tables(expand_marks(expand_hits(note, n, on_page), on_page)))}</section>')
    else:
        notes_html = '<section class="ex-notes"><h2 class="ex-h2">重點整理</h2><p class="ex-pending">這一章的重點尚未整理。</p></section>'
    year_text = "、".join(f"{y} 年 {c} 題" for y, c in sorted(years.items()))
    concepts_html, n_concepts = chapter_concepts_html(data, n, on_page)
    body = (
        f'<p class="ex-kicker">Fitzpatrick 9e · {esc(chapter["part"].title() if chapter["part"] else "")}</p>'
        f'<h1 class="ex-h1">Ch.{n} {esc(chapter["title"])}</h1>'
        f'<p class="ex-meta">原書 p.{chapter["pageStart"]}–{chapter["pageEnd"]} · '
        + (f'考題共 {len(qs)} 題（已有詳解 {explained} 題）</p><p class="ex-meta">{esc(year_text)}</p>' if qs
           else '101–115 年歷屆未出題</p>')
        + f'{NOTICE}{links_html(data["links"].get(n))}'
        f'{toc_html(note, len(qs), mobile=True, concepts=n_concepts)}{notes_html}{concepts_html}'
        + (f'<section aria-labelledby="qs-h"><h2 id="qs-h" class="ex-h2">考題</h2>{MODE_BAR}'
           + "".join(question_html(q, data, current_chapter=n) for q in qs) + "</section>" if qs else "")
    )
    title = f"Fitzpatrick Ch.{n} {chapter['title']} 重點與考題"
    desc = (f"皮膚科專科醫師考試讀書筆記：Fitzpatrick's Dermatology 9e 第 {n} 章 {chapter['title']}"
            + (f"，整理 101–115 年考題 {len(qs)} 題" + ("與重點整理" if note else "") if qs
               else "，重點整理（101–115 年歷屆未出題）") + "。")
    return page(shell, path=f"/exam/fitz-{n}", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[(f"Ch.{n}", f"/exam/fitz-{n}")],
                jsonld_type="WebPage", body=body, page_kind="chapter",
                toc=toc_html(note, len(qs), concepts=n_concepts))


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


def practice_page(shell, by_year, n_mock: int) -> str:
    # 模擬考 replaces the year selection with the mock bank; shown only once the bank has questions.
    mock = (
        '<fieldset class="ex-fieldset ex-mock-set"><legend>模擬考</legend>'
        f'<label class="ex-check"><input type="checkbox" name="ex-mock" value="1" aria-label="模擬考（題庫 {n_mock} 題）">'
        f' 模擬考（題庫 {n_mock} 題）</label>'
        f'<p class="ex-mock-note">勾選後改從模擬題出題（{MOCK_LABEL}；年份選擇不適用）。'
        "模擬題依 Fitzpatrick 與 McKee 新撰寫，比照歷屆題型，每題經獨立作答與逐句對照原文核對；"
        "作答紀錄另外保存，不計入考古題的作答統計與錯題本。</p></fieldset>"
    ) if n_mock else ""
    years = "".join(
        f'<label class="ex-check"><input type="checkbox" name="ex-year" value="{y}" checked aria-label="{y} 年"> {y} 年</label>'
        for y in sorted(by_year)
    )
    year_links = "".join(f'<li><a href="/exam/year-{y}">{y} 年</a></li>' for y in sorted(by_year))
    body = (
        '<p class="ex-kicker">考古卷</p><h1 class="ex-h1">自選年份／隨機出題</h1>'
        f"{NOTICE}"
        '<form class="ex-practice-form" data-practice-form>'
        f"{mock}"
        '<fieldset class="ex-fieldset ex-year-set"><legend>出題年份</legend>'
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
    desc = ("從 101–115 年皮膚科專科醫師甄審筆試選擇題中自選年份、題數，隨機或依序出題，計時作答並交卷計分"
            + (f"；也可改做模擬考（{n_mock} 題{MOCK_LABEL}）。" if n_mock else "。"))
    return page(shell, path="/exam/practice", title=f"{title} | 陳翊嘉醫師 · ChenDermatologist",
                description=desc, og_title=title, crumbs=[("自選／隨機出題", "/exam/practice")],
                jsonld_type="WebPage", body=body, page_kind="practice", mock_data=bool(n_mock))


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
    # data-ch lets exam.js add a ✓N badge (rounds of the chapter's notes read on
    # this device) after the link; nothing shows without JS or a finished round.
    rows = "".join(
        f'<tr data-ch="{n}"><td><a href="/exam/fitz-{n}">Ch.{n} {esc(chapters[n]["title"])}</a></td>'
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
            name = (f'<a href="/exam/fitz-{n}">Ch.{n} {title}</a>' if qs or n in data["notes"] else f'Ch.{n} {title}')
            # 閱讀 cell: filled by exam.js for chapters with notes (round count and
            # coverage of the current round); the others stay "—".
            reading_cell = ('<td class="ex-num ex-pg-reading">—</td>' if n in data["notes"]
                            else '<td class="ex-num ex-pg-reading" title="本章尚無重點整理">—</td>')
            # Progress cells start as "—" and are filled from this browser's
            # localStorage by exam.js; data-qids lists the chapter's questions,
            # counted from the answers given on /exam/fitz-<data-ch> only.
            prog_rows.append(
                f'<tr data-ch="{n}" data-order="{idx}" data-qids="{",".join(q["id"] for q in qs)}"'
                f'{" data-notes=\"1\"" if n in data["notes"] else ""}'
                f'{" class=\"ex-none\"" if not qs else ""}>'
                f'<th scope="row">{name}</th>{reading_cell}<td class="ex-num">{len(qs)}</td>'
                '<td class="ex-num ex-pg-done">—</td><td class="ex-num ex-pg-acc">—</td><td class="ex-pg-date">—</td>'
                f'<td class="ex-pg-readcell"><input type="checkbox" class="ex-pg-read" data-ch="{n}" '
                f'aria-label="Ch.{n} 課本已讀完" disabled></td></tr>'
            )
        count = sum(len(by_chapter.get(n, [])) for n in nums)
        part_html.append(
            f'<details class="ex-part"><summary>{esc((part or "").title())} <span class="ex-count">{count} 題次</span></summary>'
            '<div class="ex-table-wrap"><table class="ex-progress"><thead><tr><th scope="col">章節</th>'
            '<th scope="col">閱讀</th><th scope="col">題數</th><th scope="col">已做</th><th scope="col">正確率</th>'
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
        '<p class="ex-lead">目前整理 101–115 年考題以及各章節重點整理</p>'
        '<h2 class="ex-h2 ex-h2-sm">目前甄審筆試出題參考範圍</h2>'
        f'<ol class="ex-refs">{refs}</ol>{NOTICE}'
        # 考古卷 and 考點總覽 sit side by side (stacked on phones).
        '<div class="ex-hub-cards">'
        '<section class="ex-hub-card" aria-labelledby="hub-practice-h"><h2 class="ex-h2" id="hub-practice-h">考古卷</h2>'
        '<p class="ex-meta">選擇年份成卷，或從歷年考題隨機出題'
        + (f'；也可改做模擬考（{len(data["mock"])} 題{MOCK_LABEL}）' if data["mock"] else "") + '。</p>'
        '<p class="ex-meta"><a class="ex-cta" href="/exam/practice">自選年份／隨機出題</a></p></section>'
        + (('<section class="ex-hub-card" aria-labelledby="hub-concepts-h"><h2 class="ex-h2" id="hub-concepts-h">考點總覽</h2>'
            f'<p class="ex-meta">把歷年考題拆成 {len(data["concepts"])} 個考點，依考過的題數排序，'
            '列出每次的考法、牽涉的章節與常見陷阱；可搜尋、依章節篩選。</p>'
            '<p class="ex-meta"><a class="ex-cta" href="/exam/concepts">看考點總覽</a></p></section>')
           if data["concepts"] else "") +
        '</div>'
        f'{SEARCH_BOX.format(index=f"/exam/search-index.json?v={SEARCH_VERSION[0]}")}'
        # Filled by exam.js from this device's reading places; hidden without JS or records.
        '<section class="ex-continue" aria-labelledby="ex-continue-h" hidden></section>'
        '<h2 class="ex-h2">依章節瀏覽與讀書進度</h2>'
        '<p class="ex-meta">已做題數、正確率（以每題最近一次作答計算）與「課本已讀完」只存在這台裝置的瀏覽器，'
        '不同電腦或手機不會同步。正確率低於 60% 以紅字標示。</p>'
        '<p class="ex-meta">章節統計只計算在該章頁面作答的題目。</p>'
        '<p class="ex-meta">「閱讀」欄記錄各章重點整理的閱讀進度：每一段在畫面上停留夠久才算讀過，'
        '讀過約 75% 算讀完一次（✓ 後面是次數），之後從 0% 開始下一輪；同樣只存在這台裝置。</p>'
        f'<div class="ex-toolbar ex-progress-bar" data-exam-total="{total}"><span id="ex-progress-summary" class="ex-meta" aria-live="polite"></span>'
        '<label class="ex-check">排序 <select class="ex-select ex-progress-sort" aria-label="章節排序" disabled>'
        '<option value="order">章節順序</option><option value="todo">尚未作答優先</option>'
        '<option value="low">正確率低優先</option><option value="reading">閱讀進度低優先</option></select></label></div>' + "".join(part_html)
        + '<h2 class="ex-h2" id="rank-h">出題頻率：最常考的章節</h2>'
        f'<p class="ex-meta">有考題的 {len(ranked)} 章依題數排序。一題可能計入多章，所以加總會超過題數。</p>'
        '<table class="ex-rank" id="ex-rank" aria-labelledby="rank-h" data-rank-page="25"><thead><tr><th scope="col">章節</th>'
        '<th scope="col">題數</th><th scope="col"><span class="ex-sr">比例</span></th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        '<div class="ex-more-wrap" hidden><span class="ex-more-count" aria-live="polite"></span>'
        '<button type="button" class="ex-more" aria-controls="ex-rank">載入更多</button></div>'
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
SECTION_BLOCK = re.compile(r'<section class="ex-note" id="([a-z0-9-]+)"(?: data-w="\d+")?>(.*?)</section>', re.S)
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


def nav_search(data, pages, index: dict) -> list:
    """Section headings for the site-wide search (header search button).

    Pagefind splits Traditional Chinese into single characters, so 「乾癬」
    alone misses most chapters. The site search matches these headings as
    plain substrings first: [[chapter, title, [[section id, heading], ...],
    [chapter-level names and abbreviations from the hub search, e.g. 乾癬]], ...]."""
    names: dict[int, list[str]] = {}
    for n, sid, _, found, abbrs, primary, primary_abbrs in index["entries"]:
        if sid == "":
            names[n] = [t for t in found[:primary] + abbrs[:primary_abbrs] if t != data["chapters"][n]["title"]]
    out = []
    for n in sorted(pages):
        heads = [[sid, plain(title)] for sid, title in SECTION.findall(data["notes"].get(n) or "")]
        out.append([n, data["chapters"][n]["title"], heads, names.get(n, [])])
    return out


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
        tm = data["timemachine"].get(q["id"])
        if tm:
            row["tm"] = tm
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
    # Every chapter with questions gets a page, and so does every chapter that has
    # notes but was never tested (batch 10, 2026-10-21); the hub ranking still lists
    # tested chapters only.
    pages: dict[int, list] = dict(by_chapter)
    for n in data["notes"]:
        pages.setdefault(n, [])
    CHAPTER_PAGES.clear()
    CHAPTER_PAGES.update(pages)
    client = json.dumps(client_data(data), ensure_ascii=False, separators=(",", ":")) + "\n"
    DATA_VERSION[0] = hashlib.sha256(client.encode("utf-8")).hexdigest()[:10]
    mock = json.dumps(mock_client_data(data), ensure_ascii=False, separators=(",", ":")) + "\n"
    MOCK_VERSION[0] = hashlib.sha256(mock.encode("utf-8")).hexdigest()[:10]
    hub_index = search_index(data, pages)
    index = json.dumps(hub_index, ensure_ascii=False, separators=(",", ":")) + "\n"
    SEARCH_VERSION[0] = hashlib.sha256(index.encode("utf-8")).hexdigest()[:10]
    files: dict[str, str] = {}
    files["index.html"] = hub_page(shell, data, by_chapter, by_year, by_book)
    for n, qs in sorted(pages.items()):
        files[f"fitz-{n}.html"] = chapter_page(shell, data, data["chapters"][n], qs)
    for y, qs in sorted(by_year.items()):
        files[f"year-{y}.html"] = year_page(shell, data, y, qs)
    for b, qs in sorted(by_book.items()):
        files[f"{b}.html"] = book_page(shell, data, b, qs)
    files["practice.html"] = practice_page(shell, by_year, len(data["mock"]))
    files["review.html"] = review_page(shell)
    if data["concepts"]:
        files["concepts.html"] = concepts_page(shell, data, by_chapter)
    files["exam-data.json"] = client
    files["search-index.json"] = index
    files["nav-search.json"] = json.dumps(nav_search(data, pages, hub_index), ensure_ascii=False, separators=(",", ":")) + "\n"
    if data["mock"]:
        files["mock-data.json"] = mock
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
.ex-tm{border:1px solid #bfdbfe;border-left:4px solid #2563eb;background:#eff6ff;border-radius:8px;padding:8px 12px;margin:10px 0 0;font-size:13.5px;line-height:1.75;color:#1e293b;overflow-wrap:anywhere}
.ex-tm p{margin:4px 0}.ex-tm-h{font-weight:700;color:#1e40af}
.ex-tm-rows{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px 12px;margin:4px 0}
.ex-tm-rows dt{font-weight:700;color:#1e3a8a;white-space:nowrap}.ex-tm-rows dd{margin:0}
.ex-tm-level{display:inline-block;font-size:12px;font-weight:700;border-radius:6px;padding:0 7px;margin-right:6px}
.ex-tm-same{background:#dcfce7;color:#14532d}.ex-tm-diff{background:#fee2e2;color:#7f1d1d}
.ex-tm-src-h{font-weight:700;font-size:12.5px;color:#1e3a8a}.ex-tm .ex-sources a{color:#1d4ed8}
@media (max-width:560px){.ex-tm-rows{grid-template-columns:minmax(0,1fr);gap:0}.ex-tm-rows dd{margin-bottom:6px}}
/* a long McKee reference inside the notes must wrap, or it widens the page on phones */
.ex-note .ex-ref{white-space:normal;overflow-wrap:anywhere}
.ex-links{border:1px solid var(--border);border-radius:12px;padding:10px 14px;margin:14px 0;background:#fff}
.ex-links ul{margin:4px 0 8px;padding-left:20px;font-size:14px;line-height:1.8}.ex-links a{color:var(--teal-deep);text-decoration:underline;text-underline-offset:2px}.ex-links-name{font-weight:700;font-size:13.5px;margin:8px 0 0}
.ex-progress-bar{flex-wrap:wrap;gap:10px;align-items:center}
.ex-table-wrap{overflow-x:auto}
.ex-progress{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0;background:#fff;min-width:640px}
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
:root[data-theme="dark"] .ex-mock-notice{background:#3a2818;color:#fed7aa;border-color:#9a3412}
:root[data-theme="dark"] .ex-mock-tag{background:#332a14;color:#fde68a}
:root[data-theme="dark"] .ex-hit,:root[data-theme="dark"] .ex-flag,:root[data-theme="dark"] .ex-warn{background:#332a14;color:#fde68a}
:root[data-theme="dark"] .ex-dispute{background:#332a14;border-color:#92400e;color:#fde68a}
:root[data-theme="dark"] .ex-dispute-h{color:#fcd34d}:root[data-theme="dark"] .ex-sources a{color:#fde68a}
:root[data-theme="dark"] .ex-flag-note{background:#24211c;color:#d6d3cd}:root[data-theme="dark"] .ex-flag-tag{color:#a4d4c4}
:root[data-theme="dark"] .ex-ref-mckee{background:#2e1065;color:#ddd6fe}
:root[data-theme="dark"] .ex-tm{background:#172036;border-color:#1e3a8a;border-left-color:#60a5fa;color:#dbeafe}
:root[data-theme="dark"] .ex-tm-h,:root[data-theme="dark"] .ex-tm-rows dt,:root[data-theme="dark"] .ex-tm-src-h{color:#93c5fd}
:root[data-theme="dark"] .ex-tm .ex-sources a{color:#bfdbfe}
:root[data-theme="dark"] .ex-tm-same{background:#14532d;color:#dcfce7}:root[data-theme="dark"] .ex-tm-diff{background:#7f1d1d;color:#fee2e2}
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
.ex-fieldset:disabled{opacity:.55}
.ex-mock-note{font-size:12.5px;color:var(--ink-2);line-height:1.7;margin:6px 0 2px}
.ex-mock-tag{font-size:11px;font-weight:700;border-radius:9999px;padding:1px 8px;background:#fef3c7;color:#854d0e}
.ex-mock-notice{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:10px 14px;margin:0 0 14px;font-size:13px;font-weight:600;color:#7c2d12;line-height:1.7}
.ex-checks{display:flex;flex-wrap:wrap;gap:6px 14px}
.ex-check{font-size:14px;display:inline-flex;align-items:center;gap:4px;margin-right:12px}
.ex-select{border:1px solid var(--border);border-radius:8px;padding:4px 8px;font-size:14px;background:#fff;color:inherit}
:root[data-theme="dark"] .ex-cta{background:#a4b5a8;color:#16140f}
:root[data-theme="dark"] .ex-select{background:#24211c;border-color:#3a352c}
.ex-layout{max-width:48rem;margin:0 auto;padding:3rem 1.25rem 4rem}
.ex-content{min-width:0}
.ex-toc-side{display:none}
@media (min-width:1100px){.ex-layout{max-width:76rem;display:grid;grid-template-columns:250px minmax(0,48rem);gap:44px;justify-content:center}.ex-toc-side{display:block;position:sticky;top:84px;align-self:start;max-height:calc(100vh - 110px);overflow:auto}.ex-toc-mobile{display:none}}
.ex-toc{border:1px solid var(--border);border-radius:12px;background:#fff;padding:10px 14px;margin-bottom:16px;font-size:13px}
.ex-toc summary{font-weight:700;cursor:pointer}
.ex-toc ol{margin:6px -6px 0;padding-left:0;line-height:1.45;list-style:none}
.ex-toc li{margin:0}
.ex-toc a{display:block;color:var(--teal-deep);text-decoration:none;padding:3px 6px;border-radius:6px;overflow-wrap:break-word;scroll-margin:8px}
.ex-toc a:hover{background:rgba(77,99,88,.08)}
.ex-toc a:focus-visible{outline:2px solid var(--teal-deep);outline-offset:1px}
.ex-toc a[aria-current="location"]{background:#e3ece5;color:var(--ink);font-weight:600}
@media (max-width:1099px),(pointer:coarse){.ex-toc a{padding:7px 8px;min-height:32px;box-sizing:border-box}}
.ex-toc-qs{font-weight:700;margin-top:4px;border-top:1px solid var(--line);padding-top:4px}
.ex-note ul{list-style:disc;padding-left:22px}
.ex-note li{margin:4px 0}
mark.ex-key{background:linear-gradient(transparent 42%,#fde9a8 42%);color:inherit;padding:0 1px}
.ex-qref{font-size:10.5px;margin-left:3px;vertical-align:super;white-space:nowrap;color:#b45309;font-weight:600}
.ex-trap{border-left:4px solid #f87171;background:#fef5f5;border-radius:8px;padding:8px 12px;margin:10px 0;font-size:14px;line-height:1.8}
.ex-trap>strong:first-child{display:inline-block;background:#ef5350;color:#fff;border-radius:6px;font-size:11px;padding:0 7px;margin-right:8px}
.ex-n{font-family:Inter,ui-monospace,monospace;font-weight:700;color:#0c5159;white-space:nowrap}
.ex-notes-tools{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;margin:6px 0 14px;font-size:12px;color:var(--muted)}
.ex-legend{display:inline-flex;flex-wrap:wrap;gap:4px 12px;align-items:center}
.ex-legend-trap{border-left:3px solid #f87171;background:#fef5f5;padding:0 6px;border-radius:4px}
:root[data-theme="dark"] .ex-toc{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .ex-toc a{color:#a4b5a8}
:root[data-theme="dark"] .ex-toc a:hover{background:rgba(164,181,168,.1)}
:root[data-theme="dark"] .ex-toc a[aria-current="location"]{background:rgba(164,181,168,.2);color:#eef3ef}
:root[data-theme="dark"] mark.ex-key{background:linear-gradient(transparent 42%,rgba(234,179,8,.32) 42%)}
:root[data-theme="dark"] .ex-qref{color:#f2c14e}
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
.ex-more-wrap{display:flex;flex-direction:column;align-items:center;gap:6px;margin:8px 0 16px}
.ex-more-count{font-size:12.5px;color:var(--muted)}
.ex-more{flex:none;white-space:nowrap;border:1px solid #4d6358;border-radius:9999px;padding:6px 20px;font-size:13px;font-weight:600;background:#fff;color:#4d6358;cursor:pointer}
.ex-hub-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:22px 0 6px}
.ex-hub-card{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:14px;padding:4px 18px 14px;background:rgba(77,99,88,.05)}
.ex-hub-card .ex-h2{margin-top:12px}
.ex-hub-card .ex-meta:last-child{margin-top:auto;padding-top:6px}
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
.ex-resume.ex-resume-up{bottom:72px}
@media (max-width:767px){body.dn-has-sticky-cta .ex-resume.ex-resume-up{bottom:124px}}
.ex-continue{border:1px solid var(--line);border-radius:14px;padding:2px 18px 14px;margin:16px 0 0;background:rgba(77,99,88,.05)}
.ex-continue[hidden]{display:none}
.ex-continue .ex-h2{margin:12px 0 8px}
.ex-continue-main{margin:0;font-size:15.5px;line-height:1.6;font-weight:700;overflow-wrap:anywhere}
.ex-continue-sub{margin:2px 0 0;font-size:13px;line-height:1.7;color:var(--muted)}
.ex-continue-go{margin:10px 0 0}
.ex-continue-more{margin:10px 0 0;font-size:13px;line-height:1.8;color:var(--ink-2)}
.ex-continue-more a{color:var(--teal-deep);text-underline-offset:2px;overflow-wrap:anywhere}
.ex-continue-sep{margin:0 6px;opacity:.5}
:root[data-theme="dark"] .ex-continue{background:rgba(164,181,168,.07)}
:root[data-theme="dark"] .ex-continue-more a{color:#a4b5a8}
.ex-reading{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;margin:0 0 10px;padding:6px 12px;border-radius:10px;background:rgba(77,99,88,.07);font-size:13px;line-height:1.7}
.ex-reading[hidden]{display:none}
.ex-reading-reset{border:0;background:transparent;color:var(--teal-deep);font:inherit;font-size:12.5px;cursor:pointer;padding:2px 4px;text-decoration:underline;text-underline-offset:2px}
:root[data-theme="dark"] .ex-reading{background:rgba(164,181,168,.09)}
:root[data-theme="dark"] .ex-reading-reset{color:#a4b5a8}
.ex-progress .ex-pg-reading{white-space:normal;min-width:92px}
.ex-rd{display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:2px 5px}
@media (max-width:767px){.ex-progress tbody th{max-width:190px}}
.ex-rd-meter{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.ex-rd-badge{font-size:11px;font-weight:700;color:#14532d;background:#dcfce7;border-radius:9999px;padding:0 6px;white-space:nowrap}
.ex-rd-bar{display:inline-block;width:40px;max-width:48px;height:6px;border-radius:9999px;background:#e7e0d3;overflow:hidden;vertical-align:middle}
.ex-rd-fill{display:block;height:100%;background:#4d6358}
.ex-rd-pct{font-size:12px;white-space:nowrap}
.ex-rank .ex-rd-badge{display:inline-block;margin-left:6px;vertical-align:1px}
:root[data-theme="dark"] .ex-rd-badge{background:#14532d;color:#dcfce7}
:root[data-theme="dark"] .ex-rd-bar{background:#3a352c}
:root[data-theme="dark"] .ex-rd-fill{background:#a4b5a8}
.cx-rule{font-size:12.5px;line-height:1.75;color:var(--ink-2);background:#f6f3ee;border-radius:8px;padding:6px 10px;margin:8px 0 12px}
.cx-list{list-style:none;padding:0;margin:10px 0}
.cx-list>li{content-visibility:auto;contain-intrinsic-size:auto 56px;scroll-margin-top:80px}
.cx-list>li[hidden],.cx-tools[hidden],.cx-empty[hidden]{display:none}
.cx-list details{border:1px solid var(--border);border-radius:12px;background:#fff;margin:8px 0}
.cx-list summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding:10px 14px 10px 32px;position:relative}
.cx-list summary::-webkit-details-marker{display:none}
.cx-list summary::before{content:"";position:absolute;left:14px;top:17px;border:5px solid transparent;border-left:7px solid #4d6358;border-right:0;transition:transform .15s}
.cx-list details[open]>summary::before{transform:rotate(90deg)}
.cx-list details[open]>summary{border-bottom:1px dashed var(--border)}
.cx-list details>div{padding:2px 14px 12px}
.cx-name{flex:1 1 18em;min-width:0;font-weight:700;font-size:14.5px;line-height:1.65;overflow-wrap:anywhere}
.cx-name small{display:block;font-weight:500;font-size:12.5px;line-height:1.5;color:var(--muted);margin-top:1px}
.cx-meta{display:inline-flex;flex-wrap:wrap;align-items:center;gap:4px 6px;font-size:12px;color:var(--muted)}
.cx-meta b,.cx-meta i,.cx-meta em{font-style:normal;font-weight:700;border-radius:9999px;padding:1px 8px;white-space:nowrap}
.cx-meta b{background:#e3efe9;color:#0c5159}
.cx-meta i{background:#f1ece4;color:#4d6358}
.cx-meta em{background:#fee2e2;color:#7f1d1d}
.cx-meta span{white-space:nowrap}
.cx-h{font-size:12.5px;font-weight:700;color:#0c5159;margin:10px 0 4px}
.cx-how,.cx-traps{list-style:none;padding:0;margin:0}
.cx-how li{font-size:13.5px;line-height:1.75;padding:6px 0;border-bottom:1px solid var(--line)}
.cx-how a{font-weight:700;color:var(--teal-deep);margin-right:6px;white-space:nowrap}
.cx-how b{display:inline-block;font-size:11.5px;border:1px solid var(--border);border-radius:6px;padding:0 6px;margin-right:6px;line-height:1.6}
.cx-how em{display:inline-block;font-style:normal;font-size:11px;font-weight:700;border-radius:6px;padding:0 6px;margin-right:6px;line-height:1.7;background:#fee2e2;color:#7f1d1d}
.cx-how em.cx-flag{background:#fef3c7;color:#854d0e}
.cx-how span{display:block;overflow-wrap:anywhere}
.cx-traps li{border-left:3px solid #f87171;background:#fef5f5;border-radius:6px;padding:5px 10px;margin:5px 0;font-size:13.5px;line-height:1.75;overflow-wrap:anywhere}
.cx-traps b{color:#b91c1c;white-space:nowrap;margin-left:8px}
.cx-chs{font-size:12.5px;color:var(--ink-2);margin:10px 0 0;line-height:1.8}
.cx-chs a{color:var(--teal-deep)}
.cx-also{border:1px solid var(--border);border-radius:12px;background:#fff;padding:8px 14px;margin:10px 0}
.cx-also summary{cursor:pointer;font-weight:700;font-size:14px}
.cx-also ul{list-style:none;padding:0;margin:6px 0 0}
.cx-also li{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px;padding:5px 0;border-top:1px solid var(--line);font-size:13.5px}
.cx-also a{flex:1 1 16em;min-width:0;color:var(--teal-deep);text-decoration:none}
.cx-also .cx-name{font-size:13.5px}
.cx-tools{margin:16px 0 8px}
.cx-filters{display:flex;flex-wrap:wrap;gap:6px 4px;margin:10px 0 0}
.cx-filters .ex-select{max-width:min(100%,22rem)}
.cx-filters .ex-check{flex-wrap:wrap;max-width:100%}
.cx-status{font-size:13px;color:var(--ink-2);margin:8px 0 0}
.cx-status:empty{display:none}
.ex-toc-cx{font-weight:700;margin-top:4px;border-top:1px solid var(--line);padding-top:4px}
.ex-toc-cx+.ex-toc-qs{margin-top:0;border-top:0;padding-top:0}
:root[data-theme="dark"] .cx-rule{background:#24211c;color:#d6d3cd}
:root[data-theme="dark"] .cx-list details,:root[data-theme="dark"] .cx-also{background:#24211c;border-color:#3a352c}
:root[data-theme="dark"] .cx-list details[open]>summary,:root[data-theme="dark"] .cx-how li,:root[data-theme="dark"] .cx-also li,:root[data-theme="dark"] .cx-how b{border-color:#3a352c}
:root[data-theme="dark"] .cx-list summary::before{border-left-color:#a4b5a8}
:root[data-theme="dark"] .cx-chs{color:#c9c3b8}
:root[data-theme="dark"] .cx-name small{color:#a8a094}
:root[data-theme="dark"] .cx-meta b{background:#1f3a33;color:#bfe3d6}
:root[data-theme="dark"] .cx-meta i{background:#3a352c;color:#cfe0d6}
:root[data-theme="dark"] .cx-meta em,:root[data-theme="dark"] .cx-how em{background:#7f1d1d;color:#fee2e2}
:root[data-theme="dark"] .cx-how em.cx-flag{background:#332a14;color:#fde68a}
:root[data-theme="dark"] .cx-h{color:#a4d4c4}
:root[data-theme="dark"] .cx-how a,:root[data-theme="dark"] .cx-chs a,:root[data-theme="dark"] .cx-also a{color:#a4b5a8}
:root[data-theme="dark"] .cx-traps li{background:rgba(127,29,29,.3);border-left-color:#b45454}
:root[data-theme="dark"] .cx-traps b{color:#fca5a5}
</style>
"""


PREVIEW_CSS = ROOT / "admin" / "exam-preview.css"

# The admin exam editor previews a note fragment in a script-less sandboxed
# iframe. The pages get their variables and body font from the site shell, which
# the preview does not load, so the values it needs are repeated here (copied
# from notes.html; the exam CSS uses only these five variables).
PREVIEW_BASE = """/* Generated by _gen_exam.py from EXAM_STYLE: do not edit. Used only by the admin
   exam editor's note preview (admin/exam-editor.js). */
:root{--ink:#2a2620;--ink-2:#5e574e;--line:#ebe4d8;--border:#dcd5c8;--muted:#8b8378;--teal-deep:#4d6358}
html{-webkit-text-size-adjust:100%}
body{margin:0;padding:16px 20px 32px;background:#fff;color:var(--ink);font-family:Inter,'Noto Sans TC','PingFang TC','Microsoft JhengHei',-apple-system,system-ui,sans-serif;font-size:15px;line-height:1.7}
.ex-main{max-width:60rem;overflow-wrap:anywhere}
.ex-main table{display:block;overflow-x:auto}
mark[data-q]{background:linear-gradient(transparent 42%,#fde9a8 42%);color:inherit;padding:0 1px}
mark[data-q]::after{content:attr(data-q);font-size:10.5px;margin-left:2px;vertical-align:super;white-space:nowrap;color:#b45309;font-weight:600}
"""


def preview_css() -> str:
    match = re.fullmatch(r"<style data-exam-style>\n(.*)</style>\n", EXAM_STYLE, re.S)
    if not match:
        raise SystemExit("EXAM_STYLE is no longer a single <style data-exam-style> block")
    return PREVIEW_BASE + match.group(1)


def main() -> int:
    check = "--check" in sys.argv
    files = build()
    stale = []
    extras = {PREVIEW_CSS: preview_css()}
    for path, content in extras.items():
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
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
