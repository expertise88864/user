from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FLOATING_RE = re.compile(r"^(?:[\^~*]|latest$|>|<|>=|<=)", re.I)


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

    if errors:
        print("[FAIL] Supply-chain audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] Supply-chain audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
