#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Conservative repository secret leak audit."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "_bin"}
TEXT_SUFFIXES = {
    # CODE_REVIEW Phase 7 — shell/PowerShell/batch scripts were NOT scanned,
    # yet they are a classic place hard-coded tokens leak (deploy.*, set-domain.*,
    # new-article.ps1, tools/codex_review.*). Added .sh/.ps1/.cmd/.bat; verified
    # 0 false positives on the currently-tracked scripts.
    ".bat",
    ".cjs",
    ".cmd",
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
SENSITIVE_TRACKED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
}
SENSITIVE_TRACKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx")

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub classic PAT", re.compile(r"\bghp_[A-Za-z0-9_]{30,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    # CODE_REVIEW — GitHub OAuth client secret is 40-char hex; checked
    # by name (`OAUTH_CLIENT_SECRET=…`) to avoid false positives on
    # arbitrary SHA-1 hashes.
    ("GitHub OAuth client secret",
     re.compile(r"OAUTH_CLIENT_SECRET\s*=\s*['\"]?([a-f0-9]{40})['\"]?", re.I)),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{24,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    # CODE_REVIEW — Vercel KV REST tokens look like `Atxxxx…` (Upstash
    # tokens are URL-safe base64, ~50+ chars). Checked by name so we
    # don't flag arbitrary long strings.
    ("Vercel KV / Upstash REST token",
     re.compile(r"KV_REST_API_TOKEN\s*=\s*['\"]?([A-Za-z0-9_-]{40,})['\"]?", re.I)),
    (
        "literal secret assignment",
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret|client[_-]?secret|password)\b"
            r"\s*[:=]\s*(['\"])(?!<|your-|example|placeholder|process\.env)[^'\"\n]{16,}\1",
            re.I,
        ),
    ),
]


def tracked_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return [ROOT / line for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        files: list[Path] = []
        for path in ROOT.rglob("*"):
            if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
                files.append(path)
        return files


def decode_text(raw: bytes) -> str | None:
    """Decode a tracked text file BOM-aware. Windows PowerShell/batch files are
    frequently UTF-16 (with or without BOM); a plain utf-8 read raises on those
    (skipping them) or, BOM-less, yields NUL-interleaved text the patterns can't
    match — either way a secret in a .ps1/.bat would slip through the scan.
    Returns None only if the bytes are not decodable as any expected text
    encoding (caller reports it rather than silently skipping)."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    # BOM-less UTF-16 heuristic: many NUL bytes early on.
    if raw[:400].count(0) > 20:
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def is_placeholder(text: str) -> bool:
    lowered = text.lower()
    return "..." in text or "example" in lowered or "placeholder" in lowered or "your_" in lowered


def main() -> int:
    errors: list[str] = []
    for path in tracked_files():
        rel_path = path.relative_to(ROOT)
        rel = rel_path.as_posix()
        if any(part in SKIP_DIRS for part in rel_path.parts):
            continue
        # `git ls-files` still reports paths staged or marked for deletion
        # until the next commit. Secret checks must work in that normal
        # review state instead of crashing on a missing worktree file.
        if not path.is_file():
            continue
        name = path.name
        if name in SENSITIVE_TRACKED_NAMES or name.endswith(SENSITIVE_TRACKED_SUFFIXES):
            errors.append(f"{rel}: sensitive file should not be tracked")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        src = decode_text(path.read_bytes())
        if src is None:
            # Fail closed: an eligible text file we cannot decode is an
            # unscanned gap, not something to silently pass over.
            errors.append(f"{rel}: eligible text file could not be decoded (UTF-8/UTF-16) — cannot scan for secrets")
            continue
        for label, pattern in SECRET_PATTERNS:
            for match in pattern.finditer(src):
                value = match.group(0)
                if is_placeholder(value):
                    continue
                line = src.count("\n", 0, match.start()) + 1
                errors.append(f"{rel}:{line}: possible {label}")

    if errors:
        print("[FAIL] Secret leak audit found issues:")
        for error in errors[:160]:
            print(" - " + error)
        if len(errors) > 160:
            print(f" ... {len(errors) - 160} more")
        return 1
    print("[OK] Secret leak audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
