"""Import the board-exam concept tagging (考點) into data/exam/concepts/.

Usage:
  python _import_exam_concepts.py --src <dir with concepts.json, qconcepts.json, stats.json>
  python _import_exam_concepts.py --src <dir> --check   # exit 1 if the committed data is stale

The source directory is the concept-tagging workspace output (concepts/final/):
  concepts.json      concept id -> names, home chapter; "_misconceptions" id -> description
  qconcepts.json     question id -> option items (concepts, role, misconception,
                     evidence_status, inverted_true_fact, excluded_from_stats, official_conflict)
  stats.json         per-concept how_tested (one 考法 sentence per question) and chapters_involved
  scan/kaofa_all.json  fallback 考法 sentences keyed "qid:key|concept" (only used when stats has none)

Output (hand-maintained data for _gen_exam.py; re-run this script whenever the source changes):
  data/exam/concepts/concepts.json   one concept per line, sorted by question count

Trap (常見陷阱) counting rule, applied here so the pages only display numbers:
an option counts toward a misconception only if it is a distractor that carries
a real wrong idea — not inverted_true_fact (true statement in a 「何者為非」/
「以上皆是」 question), not excluded_from_stats, and evidence_status is not
"uncertain". Every 考法 sentence is still shown; the rule only affects counts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "exam"
OUT = DATA / "concepts" / "concepts.json"
ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
QID = re.compile(r"\d{3}-\d{2}")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RULE = ("題數＝考過這個考點的不重複題數；陷阱次數＝以該錯誤觀念出題的誘答選項數，"
        "不計否定題或「以上皆是」題中本身正確的選項、標記排除統計的選項，以及課本證據不足的選項。")


def jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def counted_trap(item: dict) -> str | None:
    """Why an option is left out of trap counts ('' = counted, None = not a distractor)."""
    if item.get("role") != "distractor":
        return None
    if item.get("inverted_true_fact"):
        return "inverted_true_fact"
    if item.get("excluded_from_stats"):
        return "excluded_from_stats"
    if item.get("evidence_status") == "uncertain":
        return "uncertain"
    if not item.get("misconception"):
        return "no_misconception"
    return ""


def build(src: Path) -> tuple[str, dict]:
    concepts = jload(src / "concepts.json")
    qconcepts = jload(src / "qconcepts.json")
    stats = jload(src / "stats.json")
    kaofa_path = src / "scan" / "kaofa_all.json"
    kaofa = jload(kaofa_path) if kaofa_path.exists() else {}
    misconceptions = concepts.get("_misconceptions", {})
    questions = {q["id"]: q for q in jload(DATA / "questions.json")}
    chapters = {c["chapter"] for c in jload(DATA / "fitz_chapters.json")}

    errors: list[str] = []
    # concept -> question -> option keys, and the trap tallies
    trap_items: dict[str, Counter] = defaultdict(Counter)
    trap_qs: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    excluded = Counter()
    for qid, q in qconcepts.items():
        if qid not in questions:
            errors.append(f"qconcepts: unknown question {qid}")
            continue
        for key, item in q["items"].items():
            if key not in questions[qid]["options"] and not any(
                    s["id"] == key for s in questions[qid].get("statements", [])):
                errors.append(f"qconcepts {qid}:{key}: option not in questions.json")
            why = counted_trap(item)
            if why is None:
                continue
            if why:
                excluded[why] += 1
                continue
            mc = item["misconception"]
            if mc not in misconceptions:
                errors.append(f"qconcepts {qid}:{key}: unknown misconception {mc}")
                continue
            for cid in item["concepts"]:
                trap_items[cid][mc] += 1
                trap_qs[cid][mc].add(qid)

    def flags(qid: str, keys: list[str]) -> list[str]:
        q = qconcepts[qid]
        found = bool(q.get("official_conflict")) or any(
            q["items"].get(k, {}).get("official_conflict") for k in keys)
        return ["official_conflict"] if found else []

    out = []
    for cid, c in stats["concepts"].items():
        if not ID.fullmatch(cid):
            errors.append(f"concept id {cid!r} is not [A-Za-z0-9-]")
            continue
        if c["chapter"] not in chapters:
            errors.append(f"{cid}: unknown chapter {c['chapter']}")
        how = []
        for h in c["how_tested"]:
            qid = h["qid"]
            if not QID.fullmatch(qid) or qid not in qconcepts:
                errors.append(f"{cid}: unknown question {qid}")
                continue
            text = h.get("how") or "；".join(
                s for k in h["keys"] if (s := kaofa.get(f"{qid}:{k}|{cid}")))
            if not text:
                errors.append(f"{cid}: no 考法 for {qid}")
            items = [qconcepts[qid]["items"][k] for k in h["keys"]]
            # An option is shown as 誘答 when it is a wrong option, whatever the counting rule says.
            trap = any(it["role"] == "distractor" and not it.get("inverted_true_fact") for it in items)
            row = {"q": qid, "k": h["keys"], "t": text}
            if trap:
                row["trap"] = 1
            if fl := flags(qid, h["keys"]):
                row["flags"] = fl
            how.append(row)
        if len(how) != c["n_questions"]:
            errors.append(f"{cid}: n_questions {c['n_questions']} but {len(how)} 考法")
        traps = [{"desc": misconceptions[m], "n": trap_items[cid][m], "nq": len(trap_qs[cid][m])}
                 for m in sorted(trap_items[cid], key=lambda m: (-len(trap_qs[cid][m]), -trap_items[cid][m], m))]
        out.append({
            "id": cid, "zh": c["name_zh"].strip(), "en": c["name_en"].strip(), "ch": c["chapter"],
            "chs": sorted(set(c["chapters_involved"]) | {c["chapter"]}),
            "years": sorted({questions[h["q"]]["year"] for h in how}),
            "how": how, "traps": traps,
        })
    if errors:
        raise SystemExit("concept import failed:\n  " + "\n  ".join(errors[:30]))
    out.sort(key=lambda c: (-len(c["how"]), c["ch"], c["id"]))

    # Simplified-only characters this site has already ruled out (_check_hant_only.py).
    sys.path.insert(0, str(ROOT))
    from _check_hant_only import SIMPLIFIED  # noqa: E402
    blob = json.dumps(out, ensure_ascii=False)
    bad = sorted({ch for ch in SIMPLIFIED if ch in blob})
    if bad:
        raise SystemExit(f"concept data contains simplified characters {bad}")

    meta = {
        "generated_by": "_import_exam_concepts.py",
        "source": {name: digest(src / name) for name in ("concepts.json", "qconcepts.json", "stats.json")},
        "rule": RULE,
        "counts": {
            "concepts": len(out),
            "how": sum(len(c["how"]) for c in out),
            "trap_items_counted": sum(t["n"] for c in out for t in c["traps"]),
            "trap_items_excluded": dict(sorted(excluded.items())),
        },
    }
    text = ('{"_meta":' + json.dumps(meta, ensure_ascii=False, sort_keys=True) + ',\n"concepts":[\n'
            + ",\n".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) for c in out)
            + "\n]}\n")
    return text, meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", required=True, type=Path, help="concept-tagging output directory (concepts/final)")
    ap.add_argument("--check", action="store_true", help="only verify that the committed data is current")
    args = ap.parse_args()
    text, meta = build(args.src)
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT).as_posix()} is out of date (run without --check)")
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}: {json.dumps(meta['counts'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
