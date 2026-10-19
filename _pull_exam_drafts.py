#!/usr/bin/env python
"""Bring the admin CMS exam drafts into the current checkout (maintainer step).

The /admin exam editor saves to the cloud branch `cms-exam/drafts` and never to
main. This script fetches that branch, reads its manifest (.cms-exam/drafts.json)
and copies only the source files it lists into the working tree:

  data/exam/notes/fitz-<N>.frag   whole file, one per listed chapter
  data/exam/explanations.json     only the listed question ids are applied onto
                                  the CURRENT file, so edits made on main after
                                  the draft branch was created are kept

Nothing is committed, pushed or deleted. Next steps are printed at the end:
python _gen_exam.py, review the diff, then the normal codex/* candidate flow
(CI, PR review). It also prints the exact branch head that was imported and a
cleanup command that deletes the draft branch only while the remote is still at
that head (--force-with-lease), so a draft saved after the import is never lost. Run it from a clean checkout of the candidate branch.

Fail-closed rules (nothing is written unless every listed item can be applied):
  * a target path with uncommitted changes in the working tree is refused;
  * a chapter that changed on HEAD since the draft branch was created is a
    conflict (the draft was edited from an older version of that file);
  * a question whose entry on HEAD differs from both the draft and the version
    the branch was created from is a conflict;
  * explanations.json must round-trip exactly through
    json.dumps(data, indent=1, ensure_ascii=False) (the generator's format),
    for the current file, the draft file and the base file.
Exit codes: 0 done / nothing to do, 1 conflict or invalid data, 2 refused (dirty tree, git failure).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BRANCH = "cms-exam/drafts"
MANIFEST = ".cms-exam/drafts.json"
EXPLANATIONS = "data/exam/explanations.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
QID = re.compile(r"^\d{3}-\d{2}$")


class PullError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if check and result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise PullError(f"git {' '.join(args[:2])} 失敗：{detail}", 2)
    return result


def show(repo: Path, rev: str, path: str) -> bytes | None:
    result = git(repo, "show", f"{rev}:{path}", check=False)
    return result.stdout if result.returncode == 0 else None


def note_path(chapter: int) -> str:
    return f"data/exam/notes/fitz-{chapter}.frag"


def read_manifest(repo: Path, rev: str) -> dict:
    raw = show(repo, rev, MANIFEST)
    if raw is None:
        raise PullError(f"{BRANCH} 沒有 {MANIFEST}，不是由後台建立的草稿分支，已停止。")
    try:
        record = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise PullError(f"{MANIFEST} 不是有效的 JSON：{error}") from error
    keys = ["version", "baseMain", "updated", "notes", "explanations"]
    valid = (isinstance(record, dict) and list(record) == keys and record["version"] == 1
             and isinstance(record["baseMain"], str) and SHA.match(record["baseMain"])
             and isinstance(record["updated"], str)
             and isinstance(record["notes"], list) and all(isinstance(n, int) and not isinstance(n, bool) and n > 0 for n in record["notes"])
             and isinstance(record["explanations"], list) and all(isinstance(q, str) and QID.match(q) for q in record["explanations"]))
    if not valid:
        raise PullError(f"{MANIFEST} 格式不符，已停止。")
    return record


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)


def parse_exact(raw: bytes, label: str) -> dict:
    """Parse explanations.json and require the generator's exact serialization."""
    text = raw.decode("utf-8").replace("\r\n", "\n")
    data = json.loads(text)
    if not isinstance(data, dict) or dumps(data) != text:
        raise PullError(f"{label} 的格式不是 json.dumps(indent=1, ensure_ascii=False) 的精確輸出，為避免破壞資料已停止。")
    return data


def cleanup_command(remote: str, imported: str) -> str:
    """Delete the draft branch only if the remote is still at the imported head."""
    return f"git push --force-with-lease=refs/heads/{BRANCH}:{imported} {remote} --delete {BRANCH}"


def pull(repo: Path, remote: str = "origin", dry_run: bool = False, out=print) -> int:
    repo = Path(repo)
    try:
        return _pull(repo, remote, dry_run, out)
    except PullError as error:
        out(str(error))
        return error.code


def _pull(repo: Path, remote: str, dry_run: bool, out) -> int:
    listing = git(repo, "ls-remote", "--heads", remote, BRANCH).stdout.decode("utf-8", "replace").strip()
    if not listing:
        out(f"{remote} 上沒有 {BRANCH}：目前沒有雲端草稿需要整合。")
        return 0
    ref = f"refs/remotes/{remote}/{BRANCH}"
    git(repo, "fetch", remote, f"+refs/heads/{BRANCH}:{ref}")
    imported = git(repo, "rev-parse", ref).stdout.decode("utf-8").strip()
    record = read_manifest(repo, ref)
    if not record["notes"] and not record["explanations"]:
        out("草稿分支的清單是空的，沒有可整合的項目。")
        return 0
    if git(repo, "cat-file", "-e", record["baseMain"] + "^{commit}", check=False).returncode:
        raise PullError(f"本機沒有草稿分支建立時的 main（{record['baseMain']}）；先 git fetch {remote} main 再重試。", 2)

    paths = [note_path(ch) for ch in record["notes"]] + ([EXPLANATIONS] if record["explanations"] else [])
    dirty = git(repo, "status", "--porcelain", "--untracked-files=all", "--", *paths).stdout.decode("utf-8", "replace").strip()
    if dirty:
        raise PullError("下列檔案在工作區有未提交的修改，為避免覆蓋已停止：\n" + dirty, 2)

    base = record["baseMain"]
    writes: list[tuple[Path, bytes]] = []
    report: list[str] = []
    conflicts: list[str] = []

    for chapter in record["notes"]:
        path = note_path(chapter)
        draft, current, origin = show(repo, ref, path), show(repo, "HEAD", path), show(repo, base, path)
        if draft is None or current is None:
            conflicts.append(f"Ch.{chapter}：{path} 在草稿分支或目前的 HEAD 找不到。")
        elif draft == current:
            report.append(f"考試重點 Ch.{chapter}：已是草稿內容，略過。")
        elif current != origin:
            conflicts.append(f"Ch.{chapter}：HEAD 在草稿分支建立後也改過這一章；請手動比對 {path} 與 {ref} 後合併。")
        else:
            target = repo / path
            body = draft.replace(b"\r\n", b"\n")
            if b"\r\n" in target.read_bytes():
                body = body.replace(b"\n", b"\r\n")
            writes.append((target, body))
            report.append(f"考試重點 Ch.{chapter}：套用草稿。")

    if record["explanations"]:
        target = repo / EXPLANATIONS
        current_bytes = target.read_bytes()
        crlf = b"\r\n" in current_bytes
        draft_raw, origin_raw = show(repo, ref, EXPLANATIONS), show(repo, base, EXPLANATIONS)
        if draft_raw is None:
            raise PullError(f"草稿分支缺少 {EXPLANATIONS}。")
        current_data = parse_exact(current_bytes, f"目前的 {EXPLANATIONS}")
        draft_data = parse_exact(draft_raw, f"草稿分支的 {EXPLANATIONS}")
        origin_data = parse_exact(origin_raw, f"建立草稿時的 {EXPLANATIONS}") if origin_raw is not None else {}
        changed = False
        for qid in record["explanations"]:
            if qid not in draft_data or qid not in current_data:
                conflicts.append(f"{qid}：草稿或目前的詳解檔沒有這個題號。")
            elif current_data[qid] == draft_data[qid]:
                report.append(f"題目詳解 {qid}：已是草稿內容，略過。")
            elif current_data[qid] != origin_data.get(qid):
                conflicts.append(f"{qid}：HEAD 在草稿分支建立後也改過這題詳解；請手動比對後合併。")
            else:
                current_data[qid] = draft_data[qid]   # replacing a key keeps the file's key order
                changed = True
                report.append(f"題目詳解 {qid}：套用草稿。")
        if changed:
            text = dumps(current_data)
            writes.append((target, (text.replace("\n", "\r\n") if crlf else text).encode("utf-8")))

    for line in report:
        out(line)
    if conflicts:
        out("有衝突，未寫入任何檔案：")
        for line in conflicts:
            out("  - " + line)
        return 1
    if dry_run:
        out(f"（dry-run）會寫入 {len(writes)} 個檔案。")
        return 0
    for target, data in writes:
        target.write_bytes(data)
    out(f"已更新 {len(writes)} 個檔案（未 commit）。")
    out("下一步：python _gen_exam.py 重新生成 exam/**；檢查 git diff；"
        "在 codex/* 候選分支 commit、push，走 CI 與 PR review。")
    out(f"本次匯入的草稿分支 head：{imported}")
    out(f"整合發佈後，維護者用下面的條件式刪除雲端草稿分支（只有分支仍停在上面這個 head 才會刪；"
        f"若之後又有人存了新草稿就會被拒絕、分支保留）：\n  {cleanup_command(remote, imported)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--dry-run", action="store_true", help="只顯示會做什麼，不寫入")
    args = parser.parse_args(argv)
    return pull(Path(__file__).resolve().parent, args.remote, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
