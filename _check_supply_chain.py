from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FLOATING_RE = re.compile(r"^(?:[\^~*]|latest$|>|<|>=|<=)", re.I)

# CODE_REVIEW Phase 7 — package.json pinning above does NOT cover packages run
# via `npx <pkg>@latest` inside pipeline scripts (e.g. _run_pagefind.py's
# pagefind), which are pulled fresh at build time and can ship client-served
# code. Match a `<pkg>@latest` spec in ANY form — Python's quoted argv element
# `"pagefind@latest"`, a shell/PowerShell UNQUOTED `npx pagefind@latest`, or a
# quoted command string. We strip line comments first so an explanatory
# `# ...@latest` note is ignored; any docstring/prose that mentions it verbatim
# must be reworded, and the checker excludes its own file (it necessarily
# contains the signature).
LATEST_SPEC_RE = re.compile(r"[\w@./-]*@latest\b")
LINE_COMMENT_RE = re.compile(r"(?m)(?:#|//).*$")
NPX_SCAN_SUFFIXES = (".py", ".sh", ".ps1", ".mjs", ".js", ".cjs")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def root_dependencies(package: dict) -> dict[str, str]:
    deps: dict[str, str] = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, version in package.get(field, {}).items():
            deps[f"{field}.{name}"] = str(version)
    return deps


def main() -> int:
    errors: list[str] = []
    package_path = ROOT / "package.json"
    lock_path = ROOT / "package-lock.json"

    if not package_path.exists():
        errors.append("package.json is missing")
    if not lock_path.exists():
        errors.append("package-lock.json is missing; use npm ci-compatible locked installs")
    if errors:
        print("[FAIL] Supply-chain audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1

    package = load_json(package_path)
    lock = load_json(lock_path)

    if lock.get("lockfileVersion") != 3:
        errors.append("package-lock.json should use lockfileVersion 3")
    root_lock = lock.get("packages", {}).get("", {})
    if root_lock.get("name") != package.get("name"):
        errors.append("package-lock.json root package name does not match package.json")

    for label, version in root_dependencies(package).items():
        if FLOATING_RE.match(version):
            errors.append(f"package.json: {label} uses floating range {version!r}; pin root dependencies exactly")

    lock_root_deps = root_lock.get("dependencies", {})
    for name, version in package.get("dependencies", {}).items():
        if lock_root_deps.get(name) != version:
            errors.append(f"package-lock.json: root dependency {name} should match package.json ({version})")

    # Forbid unpinned `"<pkg>@latest"` in any tracked pipeline script.
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "*.py", "*.sh", "*.ps1", "*.mjs", "*.js", "*.cjs"],
            cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.split()
    except Exception:
        tracked = [p.as_posix() for suf in NPX_SCAN_SUFFIXES for p in ROOT.rglob(f"*{suf}")]
    self_name = Path(__file__).name
    for rel in tracked:
        path = ROOT / rel
        # Skip this checker's own file — it necessarily contains the `@latest`
        # signature in its pattern definition + docs (a detector matching itself).
        if not path.is_file() or "node_modules" in rel or Path(rel).name == self_name:
            continue
        try:
            src = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Strip line comments (keeps newlines, so line numbers stay accurate).
        scrubbed = LINE_COMMENT_RE.sub("", src)
        for m in LATEST_SPEC_RE.finditer(scrubbed):
            line = scrubbed.count("\n", 0, m.start()) + 1
            errors.append(f"{rel}:{line}: unpinned '{m.group(0)}' — pin an exact version (build-time npx pulls ship to users)")

    if errors:
        print("[FAIL] Supply-chain audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] Supply-chain audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
