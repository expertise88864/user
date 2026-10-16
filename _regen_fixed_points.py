"""Remember which files a normalizer already left unchanged during one build.

REGEN_STEPS runs `_normalize_css_links.py` and `_normalize_heading_structure.py`
twice: once on the source pages and again after `_gen_en_pages.py` and the
other generators have rewritten some of them. Both normalizers are pure
functions of a file's text (no clock, path, environment or other file is
consulted) and write a file only when the normalized text differs.

So when a pass reads a file and leaves it unchanged, that text is a proven
fixed point: normalize(text) == text. If a later pass of the same build sees
exactly the same text again, normalizing it would again produce no change, so
the later pass may skip it without changing a single output byte. Files the
earlier pass rewrote are NOT recorded (that would need idempotence, which is
not assumed); a later pass reprocesses them exactly as before.

`_run_quality.py` enables this only for its own regeneration phase, by pointing
DN_REGEN_FIXED_POINTS at a private temporary directory that is deleted when
the phase ends. Run on their own (or from any other caller) the normalizers
process every file exactly as they always did.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ENV = "DN_REGEN_FIXED_POINTS"


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


class FixedPoints:
    """Per-normalizer record of {file: digest of text it left unchanged}."""

    def __init__(self, normalizer: str, root: str | Path):
        self.root = Path(root).resolve()
        directory = os.environ.get(ENV)
        self.path = Path(directory) / f"{normalizer}.json" if directory else None
        self.known: dict[str, str] = {}
        if self.path is not None and self.path.is_file():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.known = {str(key): str(value) for key, value in loaded.items()}

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def key(self, path: str | Path) -> str:
        return Path(path).resolve().relative_to(self.root).as_posix()

    def unchanged_since_proven(self, path: str | Path, text: str) -> bool:
        """True only if this exact text was already left unchanged in this build."""
        return self.enabled and self.known.get(self.key(path)) == text_digest(text)

    def record_unchanged(self, path: str | Path, text: str) -> None:
        """Record text that the normalizer just read and did not change."""
        if self.enabled:
            self.known[self.key(path)] = text_digest(text)

    def forget(self, path: str | Path) -> None:
        if self.enabled:
            self.known.pop(self.key(path), None)

    def save(self) -> None:
        if self.path is not None:
            self.path.write_text(json.dumps(self.known, sort_keys=True), encoding="utf-8")
