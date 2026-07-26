#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Block absolute-cure and sponsorship claims in patient-facing medical copy.

CODE_REVIEW TD-64 — the repo already decided this rule. styles/DermNotes/
BannedYMYL.yml lists the phrases at `level: error`, calling them a
"regulatory + liability risk under 醫療法". But the only thing that ran it was
.github/workflows/vale.yml, which triggers on `pull_request` — and this
repository has never had one: zero merge commits, a single branch, the admin
editor and every deploy pushing straight to main. So a rule the author marked
as an error has never executed once. It also carried `fail_on_error: false`,
so it would not have blocked even if it had.

Nothing in the 30-step gate looked for these phrases either (measured: no
checker mentioned any of them), which is why this exists.

NEGATION IS THE WHOLE DIFFICULTY. Vale's rule is a plain substring match with
`nonword: false`, and the one hit on the live corpus is:

    現有療法皆無法保證根治   ("no current therapy can guarantee a cure")

which is the most responsible sentence on the page. A checker that flagged it
would punish exactly the writing it exists to encourage, and would train the
author to route around the gate. So a claim only counts when it is NOT negated.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _html_scan import (  # noqa: E402
    attributes,
    blank_script_style,
    iter_inline_scripts,
    iter_tags,
    mask_comments,
    mask_inert_regions,
    tag_name,
)

SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}

# Verbatim from styles/DermNotes/BannedYMYL.yml — kept as an independent copy on
# purpose. If the two ever diverge the site has two answers to "what may we
# claim", which is worth a failure rather than a silent merge.
# CODE_REVIEW TD-64 — that sentence used to be a promise this file did not
# keep: nothing read the YAML, so the physician could add a token there and
# this list would quietly stay behind. check_policy_in_sync() below now
# compares the two sets on every run. The copy stays independent (so a typo in
# one is caught rather than inherited); what is enforced is that they AGREE.
BANNED_CLAIMS = (
    "保證根治",
    r"100%\s*治癒",
    "完全治癒",
    "永久痊癒",
    "一次治好",
    "一勞永逸",
    "唯一療法",
    "最有效的療法",
    "最好的治療",
    "治療王者",
    "神藥",
    # Sponsorship-suggestive language: the site explicitly disclaims sponsorship,
    # so copy that contradicts that promise is a defect.
    "推薦使用",
    "強力推薦",
    "首選品牌",
    "業界第一",
)

# A claim preceded by one of these, within NEGATION_WINDOW characters AND
# inside the same clause, is a denial of the claim rather than the claim.
NEGATORS = (
    "無法", "不能", "不會", "沒有", "沒辦法", "難以", "並非", "不是", "未能",
    "不可能", "別相信", "不存在", "談不上", "稱不上", "無所謂",
    "cannot", "can't", "not ", "no ", "never", "unable",
)
NEGATION_WINDOW = 14

# CODE_REVIEW TD-64 — the list above has every compound form (不能/不會/不是/
# 不可能) and missed the plainest denial in the language: a bare 不 directly in
# front of the phrase. 本院不保證根治 and 不推薦使用任何特定品牌 — both exactly
# the responsible copy this checker exists to protect — were reported as
# claims. These are matched ONLY when immediately adjacent to the phrase;
# putting 不 in NEGATORS would excuse any claim with a 不 anywhere in a
# 14-character window, which is most Chinese prose.
ADJACENT_NEGATORS = ("不", "未", "非", "無", "沒", "別", "勿", "毋", "莫")

# CODE_REVIEW TD-64 — negation has to stop at the clause boundary. A bare
# "is there a negator nearby" test excuses
#
#     不能保證改善，但能完全治癒     ("cannot promise improvement, but CAN cure")
#
# because 不能 sits within the window — while that sentence asserts a cure in
# the clearest possible way. Punctuation and contrast markers end the scope of
# the preceding negation, so the search window is cut at the last one.
#
# Only marks that genuinely END a statement count. `、` is an enumeration comma
# — it separates items INSIDE one clause — so treating it as a boundary broke
# 治療不能保證改善、完全治癒或永久痊癒, a responsible compound denial, by
# discarding the 不能 that governs the whole list. `，` and `：` are the same
# story: 本療法不能做到：完全治癒 carries its negation across the colon.
# The asymmetry is deliberate. Cutting too eagerly produces FALSE POSITIVES
# that block the physician's correct writing and teach him to bypass the gate —
# the exact outcome this checker was designed to avoid — while cutting too
# rarely lets a claim through a narrow phrase list within a 14-character window.
# Contrast markers stay, because they are the reliable signal that the polarity
# flipped.
#
# BLOCK_BREAK is the sentinel that block-level markup leaves behind when the
# body is flattened (see flatten_body). Two adjacent block elements are two
# statements, not one sentence.
#
# CODE_REVIEW TD-64 — this was U+001F, chosen because it cannot occur in HTML
# text. But Python counts U+001F as whitespace, so `.strip()` and `\s` silently
# ate it: <p>不</p><h2>保證根治</h2> had its statement break removed by an
# rstrip() and the 不 excused the heading. A sentinel that every string helper
# deletes is a trap for the next edit, not just for that one. U+E000 is private
# use, so it is not whitespace and no helper touches it — and main() asserts the
# corpus never contains it, so the "cannot occur" property is verified on every
# run rather than assumed.
BLOCK_BREAK = ""
CLAUSE_BOUNDARIES = ("。", "；", "！", "？", ".", ";", "!", "?", BLOCK_BREAK)
CONTRAST_MARKERS = ("但是", "但", "然而", "不過", "可是", "卻", "however", "but ")

# CODE_REVIEW TD-64 — the soft separators above are deliberately NOT boundaries,
# which leaves one hole: 本療法不能改善，能完全治癒 keeps 不能 in scope even
# though the segment after the comma has flipped to a positive assertion. The
# signal is an affirmative modal GOVERNING the claim — the mirror image of the
# contrast markers.
#
# The test is that the segment ENDS with the modal, i.e. the modal sits
# immediately before the claim. Two earlier attempts were wrong in opposite
# directions. "Starts with" missed 沒有副作用，本療法可完全治癒, because an
# ordinary subject stood in front (and patching that with a list of allowed
# discourse adverbs only moved the boundary — 仍可 worked, 本療法可 still did
# not). "Contains anywhere" would fire on 不能保證改善，本療法的效能與完全治癒
# 無關, where 能 is the second half of the noun 效能 and the negation genuinely
# governs — a false positive on correct writing, which is the failure mode this
# whole checker is built to avoid. Adjacency is what makes it a modal here.
#
# This heuristic is INCOMPLETE and is meant to be: it recognises a closed set of
# affirmative constructions rather than parsing Chinese. Escaping it needs all
# three of a negator within 14 characters, a soft separator between that negator
# and the claim, and an affirmative construction not on the list — and the
# residue is one of fifteen literal phrases. Each round of review has added the
# construction it found; widening the window or accepting any modal anywhere
# would trade that narrow residue for false positives on correct medical
# writing, which is the worse failure here.
SOFT_SEPARATORS = ("，", "、", "：", ",", ":")
AFFIRMATIVE_RESET = ("能", "可以", "可", "會", "保證", "一定", "必定", "絕對", "確保")
# ...except where the modal is asking rather than asserting. 能否完全治癒因人而異
# and 也可能完全治癒 are both responsible writing and both end in a modal.
AMBIVALENT_OPENERS = ("能否", "可否", "是否", "能不能", "可不可以", "可能")
# A modal usually takes a complement verb before its object: 可以達到完全治癒 is
# the same assertion as 可完全治癒. At most ONE, from a closed list of verbs that
# take a RESULT as their object, so 很難達到完全治癒 (難 is not a modal) and
# 才可能達到完全治癒 (可能 is hedged) are both still excused.
COMPLEMENT_VERBS = ("達到", "達成", "實現", "做到", "取得", "獲得", "得到", "帶來")

# CODE_REVIEW TD-64 — one more hole in the same place: 沒有副作用，保證根治 has
# an EMPTY segment after the comma (the phrase starts it), so no modal can be
# found and the earlier 沒有 — which negates 副作用, a different predicate —
# excused the claim.
#
# These phrases carry their own affirmative verb, so one of them OPENING a new
# segment is itself the assertion. Only verb-headed phrases qualify. The noun
# phrases (完全治癒, 永久痊癒, 神藥, 首選品牌…) must stay out: they can be a
# later item in a list governed by one negated verb, which is exactly the
# compound denial 治療不能保證改善，完全治癒或永久痊癒 that this file has been
# protecting since round 2, and 沒有特效藥，神藥不存在 alongside it.
ASSERTIVE_CLAIMS = ("保證根治", "推薦使用", "強力推薦")

# Only for <title> INTERIORS, which are RCDATA — there are no real tags in
# there, so there are no quoted attributes for a first-`>` regex to trip over.
# Body flattening deliberately does not use this; see flatten_body().
TAG_RE = re.compile(r"<[^>]+>")
TITLE_RE = re.compile(r"<title\b[^>]*>([\s\S]*?)</title>", re.I)

# Phrasing content: markup that formats words INSIDE a sentence. Everything
# else is treated as a block break. Defaulting unknown tags to "block" is the
# safe direction for a blocker — an unknown wrapper splitting one sentence at
# worst costs a negation that a same-clause denial would still carry.
INLINE_ELEMENTS = frozenset("""
a abbr b bdi bdo cite code data dfn em i kbd mark q rt ruby s samp small span
strong sub sup time u var wbr font big strike tt ins del label output picture
source img
""".split())
BILINGUAL_ATTRS = ("data-zh", "data-en")
# Off-page surfaces: what a search result, a shared link, or a structured-data
# consumer shows. A claim here is published even though no page renders it.
# CODE_REVIEW TD-64 — descriptions only, at first. og:title and twitter:title
# are the headline a shared link shows, which is at least as visible as the
# description under it; _check_metadata_uniqueness already treats them as real
# surfaces of this site.
META_DESC_NAMES = {
    "description", "og:description", "twitter:description",
    "og:title", "twitter:title",
}
LD_PROSE_FIELDS = {"description", "name", "headline", "text", "abstract"}
# Fallback only, for a block that does not parse as JSON. Escape-aware, unlike
# the version this replaced.
LD_STRING_FALLBACK_RE = re.compile(
    r'"(?:' + "|".join(sorted(LD_PROSE_FIELDS)) + r')"\s*:\s*"((?:[^"\\]|\\.)*)"'
)

# Anti-vacuity floor: this must never pass because it stopped reading the site.
MIN_FILES_SCANNED = 100


def ld_strings(block: str) -> list[str]:
    """Prose fields out of one JSON-LD block.

    CODE_REVIEW TD-64 — this used to be a `"field"\\s*:\\s*"([^"]*)"` regex,
    which stops at the first ESCAPED quote: in
    {"description":"所謂\\"神藥\\"並宣稱保證根治"} it captured up to 所謂 and the
    claim after it was never scanned, then the whole script block was stripped.
    JSON-LD is JSON, so parse it as JSON and walk. The regex survives only as a
    fallback for a block that does not parse — better to over-scan a malformed
    block than to skip it silently.
    """
    try:
        data = json.loads(block)
    except (ValueError, TypeError):
        return LD_STRING_FALLBACK_RE.findall(block)

    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key.lower() in LD_PROSE_FIELDS:
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return found


def published_surfaces(src: str) -> list[tuple[str, str]]:
    """(surface name, text) for every place this page publishes prose.

    CODE_REVIEW TD-64 — three things were wrong with the first version, all of
    them in extraction rather than matching:

      1. It hand-rolled regexes that demanded double quotes and a fixed
         attribute order, so `data-en='保證根治'`,
         `<meta content="…" name="description">` and
         `<script type='application/ld+json'>` — all valid HTML — were simply
         not seen, and the blocking gate passed. This module now uses the
         _html_scan parser built for exactly this problem earlier in the same
         review, instead of inventing a fourth copy of HTML parsing.
      2. Every surface was concatenated with a space and scanned as ONE string,
         so a negator ending one surface excused a claim beginning the next:
         `<span data-zh="不會" data-en="完全治癒">` became "不會 完全治癒" and
         the English cure claim passed. These values are published
         independently and share no grammatical scope, so they are returned —
         and scanned — separately.
      3. HTML comments survived: `TAG_RE` removes the delimiters, and if the
         comment contains a `>` its body leaked into the visible text, so
         `<!-- 用法: a > b, 禁止使用「保證根治」 -->` blocked the gate over
         prose no reader ever sees.
    """
    surfaces: list[tuple[str, str]] = []

    # Comments and raw-text elements are masked first, then script and style
    # bodies — the latter through the shared scanner, because `</script >`
    # closes a script and the old local regex did not know that.
    masked = mask_inert_regions(src)
    body = flatten_body(blank_script_style(masked))
    surfaces.append(("body", html.unescape(body)))

    # <title> — the SERP headline. Comments masked (a commented-out title is
    # not published) but RCDATA left intact, or there would be nothing to read.
    for m in TITLE_RE.finditer(mask_comments(src)):
        surfaces.append(("title", html.unescape(TAG_RE.sub(" ", m.group(1)))))

    # Bilingual attributes and description metadata, by PARSED attribute name.
    for _start, tag in iter_tags(masked):
        attrs = attributes(tag)
        if not attrs:
            continue
        for name in BILINGUAL_ATTRS:
            if attrs.get(name):
                surfaces.append((name, html.unescape(attrs[name])))
        meta_name = (attrs.get("name") or attrs.get("property") or "").lower()
        if tag_name(tag) == "meta" and meta_name in META_DESC_NAMES and attrs.get("content"):
            surfaces.append((meta_name, html.unescape(attrs["content"])))

    # JSON-LD prose, selected by parsed type rather than by a literal pattern.
    for attrs, block in iter_inline_scripts(masked):
        if attrs.get("type", "").strip().lower() != "application/ld+json":
            continue
        for value in ld_strings(block):
            surfaces.append(("json-ld", value))

    return [(kind, text) for kind, text in surfaces if text.strip()]


def flatten_body(dom: str) -> str:
    """Visible text, with a tag becoming a space or a statement break.

    CODE_REVIEW TD-64 — two mistakes, one round apart. First every tag
    collapsed to a space, so `<p>本療法不能改善</p><h2>完全治癒</h2>` became one
    string and the paragraph's negation excused the heading's claim; they are
    two statements to every reader, so inline formatting still collapses to a
    space (不能保證<strong>完全治癒</strong> keeps its negation) while everything
    else leaves a BLOCK_BREAK.

    Then the fix was written as `<[^>]+>`, the exact regex shape _html_scan
    exists to replace: it stops at the first `>`, and 379 tags on this site
    carry a `>` inside a quoted bilingual attribute. The tail of such an
    attribute leaked into the body — so an attribute containing 不會 could
    excuse a genuinely visible claim right after it. Tag boundaries now come
    from the shared quote-aware walker.
    """
    out: list[str] = []
    pos = 0
    for start, tag in iter_tags(dom):
        out.append(dom[pos:start])
        out.append(" " if tag_name(tag) in INLINE_ELEMENTS else BLOCK_BREAK)
        pos = start + len(tag)
    out.append(dom[pos:])
    return "".join(out)


def is_negated(text: str, start: int) -> bool:
    if text[:start].rstrip().endswith(ADJACENT_NEGATORS):
        return True

    window = text[max(0, start - NEGATION_WINDOW):start]
    cut = 0
    for marker in CLAUSE_BOUNDARIES + CONTRAST_MARKERS:
        idx = window.lower().rfind(marker.lower())
        if idx != -1:
            cut = max(cut, idx + len(marker))
    clause = window[cut:]

    # Polarity reset: the segment the claim sits in opens with an affirmative
    # modal, so a negation before the preceding comma no longer governs it.
    split_at = -1
    for sep in SOFT_SEPARATORS:
        idx = clause.rfind(sep)
        if idx != -1:
            split_at = max(split_at, idx + len(sep))
    if split_at != -1:
        tail = clause[split_at:].strip()
        if not tail and text[start:].startswith(ASSERTIVE_CLAIMS):
            return False        # the phrase itself opens the new segment
        for verb in COMPLEMENT_VERBS:
            if tail.endswith(verb):
                tail = tail[: -len(verb)].rstrip()
                break
        governed = (
            tail.endswith(AFFIRMATIVE_RESET)
            and not tail.endswith(AMBIVALENT_OPENERS)
            and not any(neg.lower() in tail.lower() for neg in NEGATORS)
        )
        if governed:
            clause = clause[split_at:]

    return any(neg.lower() in clause.lower() for neg in NEGATORS)


def scan_text(text: str) -> list[tuple[str, str]]:
    """(matched phrase, context) for each NON-negated banned claim."""
    hits: list[tuple[str, str]] = []
    for pattern in BANNED_CLAIMS:
        for m in re.finditer(pattern, text, re.I):
            if is_negated(text, m.start()):
                continue
            ctx = re.sub(
                r"[\s" + BLOCK_BREAK + r"]+", " ",
                text[max(0, m.start() - 40):m.end() + 40],
            ).strip()
            hits.append((m.group(0), ctx))
    return hits


VALE_RULE = ROOT / "styles" / "DermNotes" / "BannedYMYL.yml"


def vale_tokens() -> list[str] | None:
    """The `tokens:` list from BannedYMYL.yml, or None if it cannot be read.

    Parsed by hand rather than with PyYAML: this file is a flat list and the
    gate must not gain a third-party dependency to run.
    """
    if not VALE_RULE.exists():
        return None
    out: list[str] = []
    in_tokens = False
    for raw in VALE_RULE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^\s*tokens\s*:", line):
            in_tokens = True
            continue
        if in_tokens:
            m = re.match(r"^\s+-\s+(.*)$", line)
            if not m:
                break
            out.append(m.group(1).strip().strip("'\""))
    return out


def check_policy_in_sync() -> list[str]:
    """Fail if this file and the Vale rule disagree about what may be claimed."""
    tokens = vale_tokens()
    if tokens is None:
        return [f"{VALE_RULE.relative_to(ROOT).as_posix()} is missing — the claim policy "
                f"this checker mirrors no longer exists"]
    if not tokens:
        return [f"{VALE_RULE.relative_to(ROOT).as_posix()}: could not parse any tokens; "
                f"the sync assertion would pass vacuously"]
    mine, theirs = set(BANNED_CLAIMS), set(tokens)
    if mine == theirs:
        return []
    only_here = sorted(mine - theirs)
    only_vale = sorted(theirs - mine)
    return [
        "claim policy has diverged between _check_ymyl_claims.py and "
        f"{VALE_RULE.relative_to(ROOT).as_posix()} — "
        f"only in the checker: {only_here or 'none'}; only in the Vale rule: "
        f"{only_vale or 'none'}. The site must have ONE answer to what it may claim."
    ]


def selftest() -> list[str]:
    """Fixtures, run every time. A claim checker that stops matching is worse
    than none: it would read as a clean bill of health for the whole corpus."""
    cases = [
        ("這個療法保證根治。", 1, "bare claim is caught"),
        ("現有療法皆無法保證根治，清除率約 50-70%。", 0,
         "NEGATED claim is not a claim — the live corpus's only hit"),
        ("There is no 完全治癒 for this condition", 0,
         "English negator ADJACENT to a ZH claim"),
        # The window is deliberately narrow. A negator far from the claim does
        # NOT excuse it: "No current therapy is guaranteed to be a 完全治癒
        # option" reads as an assertion to a patient scanning the page, and a
        # wide window is exactly how a claim checker gets quietly neutered.
        ("No current therapy is guaranteed to be a 完全治癒 option", 1,
         "a DISTANT negator must not excuse the claim"),
        ("本院首選品牌就是它", 1, "sponsorship-suggestive phrase"),
        ("多數人可改善，但不會完全治癒。", 0, "negated cure claim"),
        ("號稱神藥的產品要小心", 1, "神藥 without a negator nearby"),
        ("100% 治癒是不可能的說法", 1,
         "negator AFTER the claim does not excuse it — the claim is still asserted first"),
        ("治療目標是控制而非根治。", 0, "no banned phrase at all"),
        # Clause scope — a negator that belongs to a DIFFERENT predicate must
        # not excuse the claim that follows the contrast marker.
        ("不能保證改善，但能完全治癒。", 1,
         "contrastive clause: 不能 negates改善, the cure is still asserted"),
        ("我們不做誇大宣傳。這個療法保證根治。", 1,
         "negator in the PREVIOUS sentence does not reach across the full stop"),
        ("沒有任何療法能完全治癒。", 0, "genuine denial in the same clause"),
        # `、` is an enumeration comma INSIDE a clause, not a boundary: this is
        # a responsible compound denial and must not be blocked.
        ("治療不能保證改善、完全治癒或永久痊癒。", 0, "compound denial across 、"),
        ("本療法不能做到：完全治癒。", 0, "negation carries across a colon"),
        # Round 4 — the polarity reset. The comma is still not a boundary; what
        # ends the negation's scope is the affirmative modal opening the next
        # segment, which is the same signal as a contrast marker.
        ("本療法不能改善，能完全治癒。", 1, "affirmative modal after ，flips polarity"),
        ("藥物不能立即見效，可以完全治癒。", 1, "可以 after ，flips polarity"),
        ("目前不能保證改善，能否完全治癒因人而異。", 0,
         "能否 is a question, not an assertion — must stay excused"),
        ("治療不能保證改善，完全治癒或永久痊癒。", 0,
         "compound denial across ，— no modal, so the negation still governs"),
        ("不能保證改善，也不能完全治癒。", 0, "a second denial after ，"),
        # Round 5 — the modal need not be the first character of the segment.
        ("本療法不能改善，也能完全治癒。", 1, "也能 asserts as plainly as 能"),
        ("藥物不能立即見效，仍可完全治癒。", 1, "仍可 after ，flips polarity"),
        ("不能保證改善，也可能完全治癒。", 0,
         "也可能 is hedged, not an absolute claim — the ambivalent rule wins"),
        # Round 6 — the modal governs the claim by ADJACENCY, not by position.
        ("沒有副作用，本療法可完全治癒。", 1, "an ordinary subject may precede the modal"),
        ("不能保證改善，本療法的效能與完全治癒無關。", 0,
         "能 inside the noun 效能 is not a modal — the negation still governs"),
        # Round 7 — a modal normally takes a complement verb before its object.
        ("沒有副作用，本療法可以達到完全治癒。", 1, "modal + 達到 + claim"),
        ("沒有特效藥，很難達到完全治癒。", 0, "難 is not a modal — 沒有 still governs"),
        # Round 8 — the plainest denial in the language.
        ("本院不保證根治。", 0, "a bare 不 directly in front is a denial"),
        ("本站不推薦使用任何特定品牌。", 0, "不推薦使用 is the disclaimer, not the claim"),
        ("本院保證根治。", 1, "control: the same sentence without the 不"),
        ("市面上沒有神藥。", 0, "沒 directly in front"),
        (BLOCK_BREAK.join(("不", "保證根治")), 1,
         "an adjacent negator must not reach across a BLOCK_BREAK either — the "
         "sentinel used to be U+001F, which Python's rstrip() counts as whitespace"),
        # Round 10 — a verb-headed phrase OPENING a new segment is the assertion.
        ("沒有副作用，保證根治。", 1, "沒有 negates 副作用, not the claim after the comma"),
        ("沒有收取贊助，推薦使用本產品。", 1, "same shape, sponsorship half"),
        ("沒有特效藥，神藥不存在。", 0,
         "神藥 is a NOUN phrase — it can be a later item under one negated verb"),
        ("本站不做業配，也不保證根治。", 0, "control: the second half is itself a denial"),
        ("本院不做醫美，保證根治異位性皮膚炎。", 1,
         "…but a 不 elsewhere in the window must NOT excuse the claim — which is "
         "why 不 is adjacency-only and not a NEGATORS entry"),
    ]
    failures = []
    for text, want, label in cases:
        got = len(scan_text(text))
        if (got > 0) != (want > 0):
            failures.append(
                f"_check_ymyl_claims selftest [{label}]: expected "
                f"{'a hit' if want else 'no hit'}, got {got}"
            )
    return failures


def extraction_selftest() -> list[str]:
    """Fixtures for published_surfaces(), run in the gate alongside the rest.

    CODE_REVIEW TD-64 — the first fixture set only exercised scan_text(), so
    every extraction defect review found (single quotes, attribute order,
    whitespace around `=`, cross-surface negation bleed, comment leakage)
    passed the self-test while the gate silently missed real claims. Matching
    was never the fragile part; extraction was.
    """
    cases = [
        ("<span data-en='保證根治'>x</span>", 1, "single-quoted attribute"),
        ('<meta content="完全治癒" name="description">', 1, "meta attributes in the other order"),
        ('<meta name = "description" content = "一勞永逸">', 1, "whitespace around ="),
        ("<script type='application/ld+json'>"
         '{"description":"永久痊癒"}</script>', 1, "single-quoted JSON-LD type"),
        ('<span data-zh="不會" data-en="完全治癒">x</span>', 1,
         "a negator in ONE surface must not excuse a claim in ANOTHER"),
        ('<span data-zh="不會完全治癒">x</span>', 0,
         "negation within the SAME surface still excuses"),
        ("<!-- 用法: a > b, 禁止使用「保證根治」 -->", 0,
         "an HTML comment is not published, even when it contains a >"),
        ("<!-- <p>保證根治</p> 壞例子 -->", 0, "comment with a nested tag"),
        ("<title>本療法保證根治</title>", 1, "the SERP headline is a published surface"),
        ('<script type="application/ld+json">'
         '{"description":"所謂\\"神藥\\"並宣稱保證根治"}</script>', 1,
         "claim after an escaped quote in JSON-LD"),
        # Round 4 — every one of these passed the gate while the fixtures above
        # were green, because all four defects were in extraction.
        ("<p>本療法不能改善</p><h2>完全治癒</h2>", 1,
         "adjacent BLOCK elements are two statements, not one sentence"),
        ("<p>本療法不能保證<strong>完全治癒</strong></p>", 0,
         "inline formatting must NOT split a sentence"),
        ('<!-- <span data-en="保證根治">x</span> -->', 0,
         "a commented-out attribute is not published"),
        ('<!-- <meta name="description" content="完全治癒"> -->', 0,
         "a commented-out meta description is not published"),
        ('<script>const a = "保證根治";</script >', 0,
         "</script > with a space still closes the script"),
        ("<!-- <title>保證根治</title> -->", 0,
         "a commented-out title is not published"),
        # Round 6 — the shared-link headline is as visible as the description.
        ('<meta property="og:title" content="本療法保證根治">', 1, "og:title"),
        ('<meta content="本療法保證根治" name="twitter:title">', 1,
         "twitter:title, attributes reversed"),
        ("<script-template>x</script-template><p>本療法保證根治</p>", 1,
         "<script-template> must not blank the document after it"),
        # Round 8 — 379 tags on this site carry a `>` inside a quoted attribute.
        ('<span data-note="示例 > 不會">完全治癒</span>', 1,
         "a `>` inside a quoted attribute must not leak a negator into the body"),
        ('<span data-note="示例 > x">本療法保證根治</span>', 1,
         "…nor swallow the visible claim that follows it"),
        ('<p title="a > b">本療法不會完全治癒</p>', 0,
         "control: the real in-body negation still works around a quoted >"),
        ("<p>不</p><h2>保證根治</h2>", 1,
         "a one-character negator in the previous BLOCK does not reach the heading"),
        ("<p>本院不保證根治</p>", 0,
         "control: the same negator inside the same block still governs"),
    ]
    failures = []
    for markup, want, label in cases:
        got = sum(len(scan_text(text)) for _kind, text in published_surfaces(markup))
        if (got > 0) != (want > 0):
            failures.append(
                f"_check_ymyl_claims extraction selftest [{label}]: expected "
                f"{'a hit' if want else 'no hit'}, got {got}"
            )
    return failures


def main() -> int:
    errors = check_policy_in_sync() + selftest() + extraction_selftest()
    scanned = 0
    findings: list[str] = []

    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        scanned += 1
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8", errors="replace")
        if BLOCK_BREAK in src:
            # The sentinel's whole job rests on it never occurring for real.
            errors.append(
                f"{rel} contains U+E000, which flatten_body() uses as its statement "
                f"separator — pick a different sentinel before this file ships"
            )
        for kind, text in published_surfaces(src):
            for phrase, ctx in scan_text(text):
                findings.append(
                    f"{rel} [{kind}]: absolute-cure / sponsorship claim {phrase!r} — …{ctx}…"
                )

    if scanned < MIN_FILES_SCANNED:
        errors.append(
            f"only {scanned} HTML file(s) scanned (expected >= {MIN_FILES_SCANNED}) — file "
            f"discovery is broken, so a pass here would mean nothing"
        )

    errors.extend(findings)

    if errors:
        print("[FAIL] YMYL claim audit found issues:")
        for e in errors[:80]:
            print(" - " + e)
        if len(errors) > 80:
            print(f" ... {len(errors) - 80} more")
        print("Fix: medical copy must not promise an absolute cure. Use 改善 / 可控制 / "
              "多數有效 / 根據臨床指引. See styles/DermNotes/BannedYMYL.yml.")
        return 1

    print(f"[OK] YMYL claim audit passed ({scanned} files, "
          f"{len(BANNED_CLAIMS)} banned phrases, negation-aware)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
