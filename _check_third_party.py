#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit third-party analytics/ads loading policy.

CODE_REVIEW TD-51 — this checker used to scan ONLY the HTML. That was true
when the GA4 / Clarity / AdSense loader lived in an inline `<script>` block,
but the loader was later extracted to `/assets/inline/analytics-loader.js`
(the same refactor that broke `_normalize_css_links`' DN.initBlog heuristic).
From that moment three of the four assertions here became VACUOUS — no HTML
file contains a tracker domain any more, so:

  * "noindex/internal page must not load analytics" could never fire, and
  * the localhost-guard / bot-guard assertions were gated behind
    `if "pagead2...adsbygoogle.js" in src`, which is never true.

Deleting `isBot()` or `isLocalStaticHost()` from the extracted loader would
have kept the gate fully green. So the checker now RESOLVES first-party
`<script src="/...">` includes and audits the loader body it actually ships.

Policy asserted here (see the noindex note below for the one deliberate
relaxation):
  1. No eager Clarity `<script>` inline in HTML — idle loader only.
  2. No dns-prefetch/preconnect to tracker hosts competing with first paint.
  3. Every file that actually loads a tracker must carry the bot + localhost
     guards, and every page reaching a tracker must reach them through such
     a guarded file.
  4. Internal pages (/admin*, /reset-sw*) must not load trackers at all.
  5. noindex pages must not load ADS. GA4/Clarity on a noindex page is
     explicitly allowed — see NOINDEX_ANALYTICS_NOTE.
"""

from __future__ import annotations

import html as _html
import posixpath
import re
import sys
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__", "pagefind"}

try:
    sys.path.insert(0, str(ROOT))
    from _minify import js_minify as _js_minify
except Exception:  # pragma: no cover - _minify is a sibling, always present
    _js_minify = None

EAGER_CLARITY_RE = re.compile(
    r'<script\s+type="text/javascript">[\s\S]*?www\.clarity\.ms/tag/[\s\S]*?</script>', re.I
)
PRECONNECT_RE = re.compile(
    r'<link\s+rel="(?:dns-prefetch|preconnect)"\s+href="(?:https?:)?//'
    r'(?:pagead2\.googlesyndication\.com|www\.googletagmanager\.com|www\.clarity\.ms)"',
    re.I,
)
# Per-tracker so the ads rule can be enforced independently of GA4/Clarity.
TRACKERS = {
    "ads": re.compile(r"pagead2\.googlesyndication\.com/pagead/js/adsbygoogle\.js", re.I),
    "ga4": re.compile(r"googletagmanager\.com/gtag/js", re.I),
    "clarity": re.compile(r"www\.clarity\.ms/tag", re.I),
}
# First-party script includes, e.g. <script defer src="/assets/inline/x.js?v=1">
# Quote-agnostic (backreferenced) — the generators all emit double quotes, but
# `src='/assets/inline/analytics-loader.js'` is valid HTML the browser loads
# just the same, and a resolver that only saw one quote style would let an
# internal page pull the tracker while reporting nothing. Same reasoning as the
# quote-agnostic attribute matching in _check_dangerous_sinks.
# Root-relative AND page-relative are both accepted; resolve_href() below folds
# them (and any dot segments) to one repo-relative form, because
# `src="assets/inline/analytics-loader.js"` from a root page and
# `src="/assets/inline/../inline/analytics-loader.js"` load exactly the same
# file the canonical form does.
# The value is captured RAW and filtered in first_party_script_targets() rather
# than constrained in the pattern: browsers resolve HTML character references
# inside attributes, so `src="/assets/inline/analytics-loader&#46;js"` fetches
# the loader while a pattern demanding a literal `.js` would see nothing. Every
# match below runs against the entity-decoded page.
SCRIPT_SRC_RE = re.compile(r"""<script\b[^>]*\bsrc=(["'])([^"']*)\1""", re.I)

# The ONE file allowed to contain tracker code. Per-page resolution follows
# direct <script src> only, so tracker code reachable another way — e.g. inside
# a bundle that blog-shared.js injects at runtime — would satisfy the guard
# assertion yet stay invisible to the internal-page and noindex-ads rules.
# Rather than chase every literal injection site, the invariant is pinned:
# trackers live in the canonical loader, and the canonical loader is included
# directly from HTML. Both halves are asserted below, so moving either fails
# the gate with an explanation instead of quietly reopening the blind spot.
CANONICAL_TRACKER_FILES = {"assets/inline/analytics-loader.js"}

# Pages that are internal tooling — trackers must never load there at all.
# PREFIX match, mirroring the runtime contract in analytics-loader.js
# (`p.indexOf('/admin') === 0 || p.indexOf('/reset-sw') === 0`). The earlier
# pattern only recognised admin.html, admin/… and exactly reset-sw.html, so a
# page named admin-preview.html or reset-sw-debug.html would be internal to the
# browser and ordinary to this audit — and with ads disabled and analytics
# allowed on noindex pages, nothing else would have caught it.
INTERNAL_RE = re.compile(r"^(?:en/)?(?:admin|reset-sw)", re.I)

# DECISION (TD-51) — the pre-extraction rule was a blanket "noindex page must
# not load analytics or ads". Its external justification is the ADS half:
# AdSense policy is what actually cares whether a page is thin/unindexed. The
# analytics half was self-referential (`_gen_en_pages.set_noindex` stripped
# trackers solely to satisfy this checker) and, once the loader moved out of
# the HTML, silently stopped being true anyway. These pages load GA4/Clarity
# today and legitimately should — measuring them is the point:
NOINDEX_ANALYTICS_NOTE = (
    "404.html (broken-link tracking), notes.html, "
    "blog/severe-scabies-treatment.html + its EN mirror (live articles held "
    "back from the index, still worth measuring)"
)

# Anti-vacuity floors. If the resolver silently stops finding the loader these
# trip instead of the checker going quietly green again — the exact failure
# mode this rewrite exists to prevent.
MIN_TRACKER_FILES = 1
MIN_PAGES_WITH_ANALYTICS = 100

# The early return every tracker load must sit behind, whitespace-flattened.
GUARD_SRC = "if(isBot()||isLocalStaticHost())return"

# What each guard predicate must actually DO. Asserting only that
# `function isBot(){…}` exists is forgeable: `function isBot(){return false}`
# keeps every string this checker looked for while switching the guard off for
# everyone. Checking for tokens is not enough either — `return !BOT_RE.test(…)`
# still contains `navigator.userAgent` and `.test(` while INVERTING the guard,
# so real visitors would be skipped and bots measured. So each predicate also
# pins its exact positive return expression (whitespace-stripped). Changing a
# predicate on purpose means updating the constant here — deliberately, rather
# than the guard quietly changing meaning.
GUARD_PREDICATES = {
    "isBot": {
        "tokens": ("navigator.userAgent", ".test("),
        "positive_return": "returnBOT_RE.test(navigator.userAgent||'')",
    },
    "isLocalStaticHost": {
        "tokens": ("location.hostname", "localhost", ".test("),
        "positive_return": r"return/^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname)",
    },
}

# isBot() delegates to a mutable pattern, so pinning its return expression is
# not enough on its own: `var BOT_RE = /$a/` keeps every token, the positive
# return, the guard, the body extent and the scheduler call intact while making
# the predicate false for every crawler. The pattern itself is therefore
# checked — declared exactly once, never reassigned, and still naming the
# crawler families the guard exists for.
BOT_RE_NAME = "BOT_RE"
BOT_RE_REQUIRED = (
    "bot", "crawl", "spider", "googlebot", "bingbot", "gptbot", "claudebot", "ccbot",
)

# Robots directive, parsed order- and quote-independently on the DECODED page.
# `<meta content='noindex,follow' name='robots'>` is valid HTML that browsers
# and crawlers honour; a fixed-order double-quoted pattern would have read the
# page as indexable and skipped the noindex rules entirely.
META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.I)
META_ATTR_RE = re.compile(
    r"""\b(name|content)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I
)


def is_noindex_page(decoded: str) -> bool:
    for tag in META_TAG_RE.findall(decoded):
        attrs: dict[str, str] = {}
        for m in META_ATTR_RE.finditer(tag):
            attrs[m.group(1).lower()] = m.group(2) or m.group(3) or m.group(4) or ""
        if attrs.get("name", "").strip().lower() == "robots" and re.search(
            r"\bnoindex\b", attrs.get("content", ""), re.I
        ):
            return True
    return False

# Adjacent string-literal concatenation, folded before scanning for the loader
# filename: `"/assets/inline/analytics-" + "loader.js"` names the same file
# without ever spelling it out.
_ADJACENT_LITERALS_RE = re.compile(r"""(['"])([^'"\n]*)\1\s*\+\s*(['"])([^'"\n]*)\3""")


def decode_page(text: str) -> str:
    """HTML entities + percent-encoding resolved, adjacent literals folded.

    Everything downstream must see what the BROWSER resolves, not how the
    source happens to spell it: `analytics-loader&#46;js` (entity),
    `analytics-loader%2ejs` (percent-encoded — Vercel serves the static asset
    either way) and `"analytics-" + "loader.js"` (split literal) are all the
    same file.
    """
    return fold_adjacent_literals(urllib.parse.unquote(_html.unescape(text)))


def fold_adjacent_literals(text: str, rounds: int = 6) -> str:
    """Collapse `"a" + "b"` into `"ab"`, repeatedly, so split filenames surface."""
    for _ in range(rounds):
        folded = _ADJACENT_LITERALS_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(4)}{m.group(1)}", text)
        if folded == text:
            break
        text = folded
    return text


# A `/` starts a regex literal (rather than division) when the previous
# significant character is an operator or opener — the same rule
# `_minify.js_minify` uses. It deliberately PRESERVES regex literals, so a
# quantifier like `/x{1,3}/` would otherwise be counted as a block brace and
# throw the guarded-body extent off by a whole function.
_REGEX_PREV = set("=(,;:!&|?{}[+-*%<>~^")


def assignment_sites(flat: str, name: str) -> list[re.Match[str]]:
    """Every `name = …` (not `==`) in whitespace-flattened JS, declarations included.

    A plain lookbehind is wrong here: flattening turns `var BOT_RE =` into
    `varBOT_RE=`, so `(?<![\\w$.])` sees the `r` of `var` and skips the very
    declaration it is meant to find — which read as "assigned 0 times" and
    fired on the healthy file.
    """
    out: list[re.Match[str]] = []
    for m in re.finditer(rf"{re.escape(name)}=(?!=)", flat):
        before = flat[:m.start()]
        if (not before
                or before.endswith(("var", "let", "const"))
                or not (before[-1].isalnum() or before[-1] in "_$.")):
            out.append(m)
    return out


def match_brace(flat: str, open_at: int) -> int:
    """Index just past the `}` closing the `{` at `open_at`, or -1 if unbalanced.

    String and regex literals are skipped so a brace inside a URL, a message or
    a quantifier can neither end the body early nor extend it past its real
    end. Unbalanced input returns -1 so the caller FAILS instead of assuming an
    extent that would silently count every later tracker as guarded.
    """
    depth = 0
    i = open_at
    last_signif = "\n"
    while i < len(flat):
        ch = flat[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < len(flat):
                if flat[i] == "\\":
                    i += 2
                    continue
                if flat[i] == quote:
                    i += 1
                    break
                i += 1
            last_signif = quote
            continue
        if ch == "/" and (last_signif in _REGEX_PREV or last_signif == "\n"):
            i += 1
            in_class = False
            while i < len(flat):
                c = flat[i]
                if c == "\\":
                    i += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    i += 1
                    break
                i += 1
            last_signif = "/"
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        last_signif = ch
        i += 1
    return -1


def strip_js_comments(src: str) -> str:
    """Comment-stripped JS, so commented-out code does not read as 'loaded'.

    AdSense is currently disabled by commenting the block out inside
    analytics-loader.js — a raw substring scan would report it as live.
    """
    if _js_minify is None:
        return src
    try:
        return _js_minify(src)
    except Exception:
        return src


def first_party_script_targets(page_rel: str, decoded: str) -> list[str]:
    """Repo-relative targets of every first-party <script src> on the page."""
    out: list[str] = []
    for _quote, value in SCRIPT_SRC_RE.findall(decoded):
        href = value.strip()
        if not href or href.startswith(("http://", "https://", "//", "data:")):
            continue
        href = urllib.parse.unquote(href.split("#", 1)[0].split("?", 1)[0])
        if not href.lower().endswith(".js"):
            continue
        out.append(resolve_href(page_rel, href))
    return out


def resolve_href(page_rel: str, href: str) -> str:
    """Repo-relative, dot-segment-folded target of a <script src>.

    `/a/b.js`, `a/b.js` from a root page and `/a/../a/b.js` all fold to `a/b.js`,
    so an internal page cannot dodge tracker resolution by spelling the same
    file differently.
    """
    if href.startswith("/"):
        segments = href.split("/")
    else:
        segments = posixpath.dirname(page_rel).split("/") + href.split("/")
    out: list[str] = []
    for seg in segments:
        if seg in ("", "."):
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        out.append(seg)
    return "/".join(out)


def iter_html() -> list[Path]:
    out: list[Path] = []
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        out.append(path)
    return out


def find_tracker_files() -> dict[str, set[str]]:
    """Every first-party .js whose live (comment-stripped) code loads a tracker.

    Enumerated independently of what the HTML happens to reference, so a
    tracker pulled in by a dynamically-injected bundle is still found.
    """
    hits: dict[str, set[str]] = {}
    for path in sorted(ROOT.rglob("*.js")):
        parts = path.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        # decode_page() here too, not just on the HTML side: a tracker URL
        # written as "https://www.google" + "tagmanager.com/gtag/js" names the
        # same endpoint, and classifying it is what feeds every rule below.
        code = decode_page(strip_js_comments(path.read_text(encoding="utf-8", errors="replace")))
        found = {name for name, rx in TRACKERS.items() if rx.search(code)}
        if found:
            hits[path.relative_to(ROOT).as_posix()] = found
    return hits


def main() -> int:
    errors: list[str] = []
    tracker_files = find_tracker_files()

    # --- 3a. The shipping loader must keep its bot + localhost guards. -------
    for rel, kinds in sorted(tracker_files.items()):
        code = decode_page(strip_js_comments((ROOT / rel).read_text(encoding="utf-8", errors="replace")))
        flat = re.sub(r"\s+", "", code)
        if rel not in CANONICAL_TRACKER_FILES:
            errors.append(
                f"{rel}: tracker code ({', '.join(sorted(kinds))}) outside the canonical loader "
                f"({', '.join(sorted(CANONICAL_TRACKER_FILES))}). Per-page resolution follows "
                f"direct <script src> only, so a tracker in a runtime-injected bundle would be "
                f"invisible to the internal-page and noindex-ads rules — move it, or teach the "
                f"resolver to propagate through injection sites"
            )
        # The predicates must exist AND still do what their names claim, and
        # must not be reassignable — `function isBot(){return false}` or a later
        # `isBot = function(){return false}` would otherwise switch the guard
        # off for everyone while every string checked here stayed in place.
        # The crawler pattern isBot() delegates to.
        bot_assigns = assignment_sites(flat, BOT_RE_NAME)
        if len(bot_assigns) != 1:
            errors.append(
                f"{rel}: {BOT_RE_NAME} must be assigned exactly once "
                f"(found {len(bot_assigns)}) — a later reassignment silently disables isBot()"
            )
        elif flat[bot_assigns[0].end():bot_assigns[0].end() + 1] != "/":
            errors.append(
                f"{rel}: {BOT_RE_NAME} is no longer a regex literal — cannot verify that "
                f"isBot() still recognises crawlers"
            )
        else:
            start = bot_assigns[0].end()
            end = start + 1
            in_class = False
            while end < len(flat):
                c = flat[end]
                if c == "\\":
                    end += 2
                    continue
                if c == "[":
                    in_class = True
                elif c == "]":
                    in_class = False
                elif c == "/" and not in_class:
                    break
                end += 1
            pattern = flat[start:end].lower()
            missing = [tok for tok in BOT_RE_REQUIRED if tok not in pattern]
            if missing:
                errors.append(
                    f"{rel}: {BOT_RE_NAME} no longer matches the crawler families the guard "
                    f"exists for — missing {', '.join(missing)}. A pattern like /$a/ keeps "
                    f"isBot() structurally intact while making it false for every bot"
                )

        for pred, spec in GUARD_PREDICATES.items():
            if flat.count(f"function{pred}(") != 1:
                errors.append(
                    f"{rel}: {pred} must be declared exactly once "
                    f"(found {flat.count(f'function{pred}(')}) — a duplicate declaration is "
                    f"hoisted over the real one"
                )
                continue
            decl = flat.find(f"function{pred}(")
            open_brace = flat.find("{", decl)
            close = match_brace(flat, open_brace) if open_brace != -1 else -1
            if close < 0:
                errors.append(f"{rel}: could not read the body of {pred}() — braces unbalanced")
                continue
            body = flat[open_brace:close].replace(" ", "")
            missing = [tok for tok in spec["tokens"] if tok.replace(" ", "") not in body]
            if missing:
                errors.append(
                    f"{rel}: {pred}() no longer tests what its name claims — missing "
                    f"{', '.join(missing)}. A predicate that just returns a constant "
                    f"disables the guard while leaving every marker in place"
                )
            elif spec["positive_return"] not in body:
                errors.append(
                    f"{rel}: {pred}() no longer returns its expected POSITIVE test "
                    f"`{spec['positive_return']}` — an inverted or rewritten predicate keeps "
                    f"every token in place while reversing who is guarded. If the change is "
                    f"intended, update GUARD_PREDICATES deliberately"
                )
            if any(m.start() >= close or m.start() < decl
                   for m in assignment_sites(flat, pred)):
                errors.append(
                    f"{rel}: {pred} is reassigned somewhere outside its declaration — "
                    f"the guard can be swapped out at runtime"
                )
        # Presence of the guard is not enough, and neither is textual order.
        # Three things have to hold together, or the guard is decorative:
        #   A. the early return is the FIRST statement of some function,
        #   B. every live tracker reference sits inside THAT function's body,
        #   C. that function is actually scheduled/called.
        # Without B, the classic refactor
        #   function load(){ if(isBot()||isLocalStaticHost()) return }
        #   function actualLoad(){ /* trackers */ }
        #   requestIdleCallback(actualLoad)
        # keeps every guard string present, keeps the trackers textually after
        # the guard, and keeps all tracker code inside the canonical loader —
        # while bots and localhost fire the requests anyway.
        guard_m = re.search(
            r"function([A-Za-z_$][\w$]*)\(\)(\{)" + re.escape(GUARD_SRC), flat
        )
        if guard_m is None:
            errors.append(
                f"{rel}: the bot/localhost early-return `{GUARD_SRC}` must be the FIRST "
                f"statement of the function that loads the trackers "
                f"(loads: {', '.join(sorted(kinds))})"
            )
        else:
            fname = guard_m.group(1)
            body_start = guard_m.start(2)
            body_end = match_brace(flat, body_start)
        if guard_m is not None and body_end < 0:
            errors.append(
                f"{rel}: could not determine the extent of the guarded {guard_m.group(1)}() "
                f"body — braces do not balance. Refusing to guess: an assumed extent would "
                f"silently count every later tracker as guarded"
            )
        elif guard_m is not None:
            for name, rx in TRACKERS.items():
                outside = [
                    m.start() for m in rx.finditer(flat)
                    if not (body_start < m.start() < body_end)
                ]
                if outside:
                    errors.append(
                        f"{rel}: {name} tracker is referenced outside the guarded "
                        f"{fname}() body (offset {outside[0]}, body {body_start}-{body_end}) "
                        f"— bots and local test hosts would still hit it"
                    )
            # C — the guarded function must actually RUN. Accepting any mention
            # of the identifier was too loose: `void load` or
            # `const deferred = load` would have read as "scheduled" while
            # analytics was dead site-wide. Require a real call or a hand-off
            # to a scheduler.
            # A SECOND `function load(){}` declaration is hoisted over the real
            # one, so the guarded, tracker-bearing body becomes dead and
            # analytics silently stops — while `requestIdleCallback(load)` still
            # reads as an invocation. Require exactly one binding, and never
            # count a declaration site as a call.
            if flat.count(f"function{fname}(") != 1:
                errors.append(
                    f"{rel}: {fname} is declared {flat.count(f'function{fname}(')} times — a "
                    f"later declaration is hoisted over the guarded one, leaving its trackers "
                    f"dead and the guard meaningless"
                )
            outside_decl = [
                m for m in re.finditer(rf"\b{re.escape(fname)}\b", flat)
                if not (guard_m.start(1) <= m.start() < guard_m.start(2))
                and not (body_start < m.start() < body_end)
                and flat[max(0, m.start() - 8):m.start()] != "function"
            ]
            invoked = any(
                flat[m.end():m.end() + 1] == "("
                or re.search(
                    r"(?:requestIdleCallback|setTimeout|setInterval|queueMicrotask"
                    r"|requestAnimationFrame|then|addEventListener)\([^()]*$",
                    flat[max(0, m.start() - 60):m.start()],
                )
                for m in outside_decl
            )
            if not invoked:
                errors.append(
                    f"{rel}: the guarded {fname}() is never called or handed to a scheduler "
                    f"— the trackers inside it are dead, or something else loads them"
                )

    # --- 3c. The canonical loader must not be reachable indirectly. ---------
    # If some first-party script injected it at runtime, a page could load
    # trackers without naming the loader in its own HTML, and rules 4 and 5
    # below would never see that page.
    for js in sorted(ROOT.rglob("*.js")):
        parts = js.relative_to(ROOT).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        rel_js = js.relative_to(ROOT).as_posix()
        if rel_js in tracker_files:
            continue
        code = decode_page(strip_js_comments(js.read_text(encoding="utf-8", errors="replace")))
        for canonical in sorted(tracker_files):
            # Filename, not full path — same reasoning as the page-level scan:
            # an assembled or relative reference still names the file.
            if canonical.rsplit("/", 1)[-1] in code:
                errors.append(
                    f"{rel_js}: references the tracker loader {canonical}. It must be included "
                    f"directly from HTML — an injected include hides the loading page from the "
                    f"internal-page and noindex-ads rules"
                )

    pages_with_analytics = 0

    for path in iter_html():
        rel = path.relative_to(ROOT).as_posix()
        src = path.read_text(encoding="utf-8")
        # Character references decoded once, up front — every match below runs
        # against what the browser actually sees, not the source spelling.
        decoded = decode_page(src)

        # --- 1 + 2. HTML-level rules (unchanged, still meaningful). ----------
        if EAGER_CLARITY_RE.search(decoded):
            errors.append(f"{rel}: eager Clarity script found; use idle third-party loader only")
        if PRECONNECT_RE.search(decoded):
            errors.append(
                f"{rel}: third-party dns-prefetch/preconnect should not compete with critical rendering"
            )

        # --- Resolve what this page EFFECTIVELY loads. ----------------------
        # A tracker named in the HTML itself is the pre-extraction shape: it
        # runs unconditionally, bypassing the bot/localhost guards. That is a
        # violation on its own — a page can carry BOTH the guarded loader and
        # a stray inline tag, so this is tested independently of what the
        # resolved first-party scripts contribute.
        inline_hits = {name for name, rx in TRACKERS.items() if rx.search(decoded)}
        resolved: set[str] = set()
        resolved_targets = first_party_script_targets(rel, decoded)
        for target in resolved_targets:
            resolved |= tracker_files.get(target, set())

        # A page can pull the canonical loader without a `src` attribute at
        # all — `<script type="module">import "/assets/inline/analytics-loader.js"</script>`
        # loads exactly the same trackers. Counting occurrences of the loader's
        # FILENAME (not its full path) and comparing against the includes the
        # src parser resolved catches every such form — module import, dynamic
        # import(), a hand-rolled injector, <link rel=preload> — and also the
        # path-shaped dodges, since `"/assets/inline/" + "analytics-loader.js"`
        # and a relative or dot-segmented spelling all still contain the
        # filename. Its trackers count as loaded, so the internal-page and
        # noindex-ads rules below apply, and the unsupported form is reported
        # so the resolver is not silently outrun again. (Residual: splitting
        # the filename itself across string fragments would evade this — no
        # generator does anything of the sort, and rule 3b still catches the
        # tracker domains such code would have to name.)
        for canonical in sorted(tracker_files):
            filename = canonical.rsplit("/", 1)[-1]
            accounted = sum(1 for t in resolved_targets if t == canonical)
            if decoded.count(filename) > accounted:
                resolved |= tracker_files[canonical]
                errors.append(
                    f"{rel}: names {filename} in a form page-level tracker resolution cannot "
                    f"follow — module import, dynamic import(), an assembled path, a hand-rolled "
                    f"injector, or a non-first-party origin. Include the loader with a plain "
                    f"first-party <script src> so this page's tracker set can be resolved"
                )

        effective = inline_hits | resolved
        if not effective:
            continue
        if {"ga4", "clarity"} & effective:
            pages_with_analytics += 1

        # --- 3b. A tracker reached WITHOUT going through a guarded file. -----
        if inline_hits:
            errors.append(
                f"{rel}: loads {', '.join(sorted(inline_hits))} directly in the HTML, bypassing "
                f"the guarded loader ({', '.join(sorted(tracker_files)) or 'none found'})"
            )

        # --- 4. Internal tooling pages: no trackers at all. ------------------
        if INTERNAL_RE.match(rel):
            errors.append(
                f"{rel}: internal page must not load analytics or ads "
                f"(loads: {', '.join(sorted(effective))})"
            )
            continue

        # --- 5. noindex pages: ads forbidden, analytics allowed. ------------
        is_noindex = is_noindex_page(decoded)
        if is_noindex and "ads" in effective:
            errors.append(f"{rel}: noindex page must not load ads (AdSense)")

    # --- 6. Anti-vacuity. ---------------------------------------------------
    if len(tracker_files) < MIN_TRACKER_FILES:
        errors.append(
            f"no first-party file loads GA4/Clarity/AdSense — the resolver found nothing to "
            f"audit, so every rule above passed vacuously"
        )
    if pages_with_analytics < MIN_PAGES_WITH_ANALYTICS:
        errors.append(
            f"only {pages_with_analytics} page(s) resolve to loading analytics "
            f"(expected >= {MIN_PAGES_WITH_ANALYTICS}) — script resolution is probably broken, "
            f"which would make the guard assertions vacuous"
        )

    if errors:
        print("[FAIL] Third-party loading audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1

    print(
        f"[OK] Third-party loading audit passed "
        f"({pages_with_analytics} pages load analytics via "
        f"{', '.join(sorted(tracker_files)) or 'no'} guarded loader; "
        f"noindex pages may carry analytics — {NOINDEX_ANALYTICS_NOTE})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
