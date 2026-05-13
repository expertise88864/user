from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
NODE = "node.exe" if os.name == "nt" else "node"
SKIP_DIRS = {".git", ".lighthouseci", "node_modules", "__pycache__"}
JS_EXTENSIONS = {".js", ".mjs"}


def iter_js_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in JS_EXTENSIONS:
            continue
        rel_parts = set(path.relative_to(ROOT).parts)
        if rel_parts & SKIP_DIRS:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def main() -> int:
    files = iter_js_files()
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        result = subprocess.run(
            [NODE, "--check", str(path)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            errors.append(f"{rel}: {detail}")

    if errors:
        print("[FAIL] JavaScript syntax audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print(f"[OK] JavaScript syntax audit passed ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
