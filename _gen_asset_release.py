"""Pin cached browser code to an explicit release version and SW generation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from _normalize_css_links import ASSET_VERSION

ROOT = Path(__file__).resolve().parent
MANIFEST = "_asset_release.json"


def text_hash(path: Path) -> str:
    # Git's Windows checkout may use CRLF; production and Ubuntu use LF.
    # All covered assets are UTF-8 text, so pin Git-equivalent text bytes.
    raw = path.read_bytes()
    raw.decode("utf-8")
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def snapshot(root: Path = ROOT, version: str = ASSET_VERSION) -> dict:
    if not re.fullmatch(r"\d{12}", version):
        raise ValueError("Asset release needs a 12-digit version")
    paths = sorted([*root.glob("blog/*.min.js"), *root.glob("assets/inline/*.js"),
                    *root.glob("assets/*.css"), root / "assets/web-vitals.iife.js"])
    if not list(root.glob("blog/*.min.js")) or not list(root.glob("assets/inline/*.js")):
        raise ValueError("Missing browser asset families")
    worker = (root / "sw.js").read_text(encoding="utf-8")
    caches = {}
    for name in ("CACHE", "RUNTIME"):
        values = re.findall(rf"const {name}\s*=\s*'([^']+)'", worker)
        if len(values) != 1:
            raise ValueError(f"Missing or ambiguous SW {name}")
        caches[name] = values[0]
    return {"version": version, "caches": caches, "hash_format": "sha256-utf8-lf",
            "worker_sha256": text_hash(root / "sw.js"),
            "assets": {p.relative_to(root).as_posix(): text_hash(p)
                       for p in paths}}


def validate_transition(previous: dict, current: dict) -> None:
    changed = (previous["assets"] != current["assets"]
               or previous["worker_sha256"] != current["worker_sha256"])
    if changed:
        if current["version"] <= previous["version"]:
            raise ValueError("Cached browser code changed: bump ASSET_VERSION before regenerating")
        for name in ("CACHE", "RUNTIME"):
            if previous["caches"][name] == current["caches"][name]:
                raise ValueError(f"Cached browser code changed: bump SW {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--init", action="store_true")
    args = parser.parse_args()
    path = ROOT / MANIFEST
    current = snapshot()
    if args.init:
        if path.exists():
            raise ValueError("Release manifest already exists; use --write")
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", MANIFEST],
                                 cwd=ROOT, capture_output=True)
        if tracked.returncode == 0:
            raise ValueError("Cannot reinitialize a tracked release manifest")
    else:
        previous = json.loads(path.read_text(encoding="utf-8"))
        validate_transition(previous, current)
        if args.check and previous != current:
            raise ValueError("Asset release manifest is stale; regenerate")
    if args.write or args.init:
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[OK] Cached asset release {ASSET_VERSION}: {len(current['assets'])} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
