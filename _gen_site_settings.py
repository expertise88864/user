"""Emit a bounded public settings catalogue from the site's trusted metadata.

The source config is never rewritten. A draft does not change the public site.
"""
from __future__ import annotations

import argparse
import json
from _site_settings_data import ROOT, CONTRACT, load_settings
from _site_settings_render import render_theme


def generate(root=ROOT, *, check=False):
    settings, catalog = load_settings(root)
    content = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode('utf-8')
    if len(content) > 200_000:
        raise ValueError("Settings catalogue exceeds byte limit")
    css = root / 'assets/dn-below-fold.css'
    raw = css.read_bytes()
    theme = render_theme(raw.decode('utf-8'), settings['font']).encode('utf-8')
    outputs = [(root / CONTRACT['catalog'], content), (css, theme)]
    # Validate both outputs before writing either. No network/CMS code is run.
    if check:
        if any(not path.is_file() or path.read_bytes() != value for path, value in outputs):
            raise ValueError("Stale settings catalogue or typography; regenerate before delivery")
    else:
        for path, value in outputs:
            if not path.is_file() or path.read_bytes() != value:
                path.write_bytes(value)
    return len(catalog['articles'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count = generate(check=args.check)
    print(f"[OK] Settings catalogue / typography: {count} public articles ({'checked' if args.check else 'generated'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
