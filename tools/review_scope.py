#!/usr/bin/env python3
"""Review scope for generated output (user decision 2026-10-15, DECISIONS.md D-19).

A file counts as generated only when every build is guaranteed to rewrite it, or to
delete it as stale, from tracked sources. The required CI job "Canonical generated
file consistency" (quality.yml: `_run_quality.py build` then `git diff --exit-code`)
then fails on any such file that does not match its generator, so a review reads
the generator and the source changes in full and only a few sampled generated files.
Anything else, including a generated-looking file no generator writes (an orphan
the build would leave alone), is read in full. Keep this in step with PIPELINE.md.

Usage (from tools/codex_review.sh):
    python tools/review_scope.py <from-commit> <to-commit>
prints the prompt section for the committed range from..to.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = 3
CHECK = ("required CI job 'Canonical generated file consistency' "
         "(_run_quality.py build + git diff --exit-code)")
# Fixed outputs every build rewrites.
FIXED = {
    "sitemap.xml": 2, "blog/feed.xml": 2, "blog/atom.xml": 2, "llms-full.txt": 3,
    ".well-known/ai.txt": 4, "ai/summary.json": 4, "ai/faq.json": 4, "ai/service.json": 4,
    "robots.txt": 5, "admin/exam-preview.css": 0,
}
# (name, generator and its tracked sources)
GROUPS = (
    ("exam pages", "_gen_exam.py from data/exam/** and exam/exam.js (also _gen_exam.py --check)"),
    ("English article mirrors", "_gen_en_pages.py from the same-name blog/*.html and its translation data"),
    ("feeds and sitemap", "_gen_feeds.py from DN.ARTICLES in blog/blog-shared.js and the article pages"),
    ("llms-full.txt", "_gen_llms_full.py"),
    ("AI policy files", "_normalize_ai_well_known.py, _gen_ai_faq.py, _gen_ai_service.py"),
    ("robots.txt", "_normalize_robots.py"),
    ("minified scripts", "_minify.py from the same-name blog/*.js listed in its JS_BUNDLES"),
)


class Tree:
    """Files and the minified bundles of the reviewed head."""

    def __init__(self, end: str):
        raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", "--name-only", end], cwd=ROOT)
        self.files = {p for p in raw.decode("utf-8").split("\0") if p}
        self.bundles: set[str] = set()
        try:
            source = subprocess.check_output(["git", "show", f"{end}:_minify.py"], cwd=ROOT,
                                             stderr=subprocess.DEVNULL).decode("utf-8")
            for node in ast.parse(source).body:
                if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "JS_BUNDLES" for t in node.targets):
                    self.bundles = {str(v) for v in ast.literal_eval(node.value)}
        except (subprocess.CalledProcessError, SyntaxError, ValueError, UnicodeDecodeError):
            self.bundles = set()


def group_of(path: str, tree: Tree) -> int | None:
    """Index into GROUPS when the build rewrites (or prunes) this path, else None."""
    if path in FIXED:
        return FIXED[path]
    parts = path.split("/")
    # _gen_exam.py writes every exam/ page and deletes any other top-level file there
    # except the hand-written exam.js.
    if len(parts) == 2 and parts[0] == "exam" and parts[1] != "exam.js":
        return 0
    # _gen_en_pages.py mirrors each blog/*.html to en/blog/ but never deletes orphans.
    if len(parts) == 3 and parts[:2] == ["en", "blog"] and path.endswith(".html") \
            and f"blog/{parts[2]}" in tree.files:
        return 1
    if len(parts) == 2 and parts[0] == "blog" and path.endswith(".min.js") \
            and path[len("blog/"):-len(".min.js")] in tree.bundles:
        return 6
    return None


def changed(start: str, end: str) -> list[str]:
    raw = subprocess.check_output(["git", "diff", "--name-only", "-z", "--no-renames", start, end],
                                  cwd=ROOT)
    return sorted({p for p in raw.decode("utf-8").split("\0") if p})


def sample(paths: list[str], seed: str) -> list[str]:
    """A few files, fixed for one head but different between heads."""
    if len(paths) <= SAMPLE:
        return paths
    ranked = sorted(paths, key=lambda p: hashlib.sha256(f"{seed}\0{p}".encode()).hexdigest())
    return sorted(ranked[:SAMPLE])


def section(paths: list[str], seed: str, tree: Tree) -> str:
    generated: dict[int, list[str]] = {}
    sources = 0
    for path in paths:
        index = group_of(path, tree)
        if index is None:
            sources += 1
        else:
            generated.setdefault(index, []).append(path)
    lines = [f"CHANGED FILES IN THIS SCOPE: {len(paths)} "
             f"({sources} source, {len(paths) - sources} generated)."]
    if not generated:
        lines.append("No generated output changed: read every changed file in full.")
        return "\n".join(lines)
    lines += [
        "Read every changed SOURCE file in full, including generators and their data.",
        "GENERATED output below is rebuilt from tracked sources and enforced by the "
        + CHECK + ". Review it through its generator and source changes, and read only "
        "the sampled files listed (OLD and NEW); open another generated file only when a "
        "concrete concern from the generator or source review requires it.",
    ]
    for index in sorted(generated):
        name, generator = GROUPS[index]
        files = generated[index]
        lines.append(f"- {name}: {len(files)} file(s); generator: {generator}.")
        lines += [f"    sample: {path}" for path in sample(files, seed)]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 64
    start, end = argv
    print(section(changed(start, end), end, Tree(end)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
