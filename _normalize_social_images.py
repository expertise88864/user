#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Point every page's og:image / twitter:image at its own static card.

Each page under blog/ has a 1200x630 card at assets/og/<slug>.png, rendered by
_gen_og_cards.py. There is no dynamic fallback any more — see image_for().
"""

from __future__ import annotations

import html
import re
import struct
import zlib
import sys
from pathlib import Path


ROOT = Path(__file__).parent
DOMAIN = 'https://chendermatologist.com'
BLOG = ROOT / 'blog'
OG_DIR = ROOT / 'assets' / 'og'

sys.path.insert(0, str(ROOT))
from _gen_og_cards import TOP_LEVEL_PAGES, card_slug  # noqa: E402


def image_intact(data: bytes) -> bool:
    """True if the file is structurally complete, not just correctly headed.

    CODE_REVIEW SEO-5 round 3 — reading dimensions out of a header says
    nothing about whether the rest of the file survived. A PNG truncated
    immediately after IHDR still reports 1200x630 and would have been reported
    as a verified share image, while no platform could render it.

    This is a structural check, not a decode: CI installs only html5validator
    and lxml, so depending on Pillow here would mean the gate behaved
    differently on a developer's machine than in the pipeline that guards the
    push. Truncation and appended garbage — the ways a committed asset
    actually breaks — are exactly what the terminators below catch.
    """
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        i = 8
        seen_ihdr = False
        while i + 12 <= len(data):
            length = int.from_bytes(data[i:i + 4], 'big')
            kind = data[i + 4:i + 8]
            end = i + 8 + length
            if i == 8 and kind != b'IHDR':
                return False
            if end + 4 > len(data):
                return False                    # chunk claims past EOF
            # CODE_REVIEW SEO-5 round 3 — the CRC used to be skipped over, so a
            # flipped byte inside IDAT — corruption that leaves the container
            # intact — passed as a complete file. PNG stores a CRC32 over the
            # type and data of every chunk; checking it is what turns this from
            # "the wrapper is the right shape" into "the bytes are the bytes".
            if zlib.crc32(data[i + 4:end]) != int.from_bytes(data[end:end + 4], 'big'):
                return False
            seen_ihdr = seen_ihdr or kind == b'IHDR'
            i = end + 4
            if kind == b'IEND':
                return seen_ihdr and i == len(data)
        return False
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        if int.from_bytes(data[4:8], 'little') + 8 != len(data):
            return False
        # Walk the RIFF chunks too: a correct outer length says nothing about
        # what is inside it.
        i = 12
        seen_payload = False
        while i + 8 <= len(data):
            size = int.from_bytes(data[i + 4:i + 8], 'little')
            seen_payload = seen_payload or data[i:i + 4] in (b'VP8 ', b'VP8L', b'VP8X')
            i += 8 + size + (size & 1)           # chunks are word-aligned
        return seen_payload and i == len(data)
    if data[:2] == b'\xff\xd8':
        return data[-2:] == b'\xff\xd9' and _jpeg_walks(data)
    return False


def _jpeg_walks(data: bytes) -> bool:
    """Every JPEG segment length must land on the next marker, up to SOS."""
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            return False
        marker = data[i + 1]
        if marker == 0xD9:
            return True
        if marker == 0xDA:                       # entropy-coded data follows
            return True
        if 0xD0 <= marker <= 0xD8:
            i += 2
            continue
        i += 2 + int.from_bytes(data[i + 2:i + 4], 'big')
    return False


def image_size(path: Path) -> tuple[int, int] | None:
    """(width, height) of a complete PNG, WebP or JPEG, without Pillow.

    Returns None for anything this cannot vouch for — an unknown format, or a
    file whose structure does not hold together. Callers treat None as "cannot
    be verified", which is an error rather than a skip.

    JPEG is here for about.html, which shares a portrait rather than a
    generated card and would otherwise be the one page left without declared
    dimensions.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not image_intact(data):
        return None
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    # CODE_REVIEW SEO-5 round 2 — WebP was unparsed, and image_for() falls back
    # to the .webp twin when a .png is missing. So this function could return
    # None for a URL this very module had just emitted, and the checker built
    # on it would then either skip its dimension test or reject a legitimate
    # asset. Both callers now understand every format the site can emit.
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP' and len(data) >= 30:
        fmt = data[12:16]
        if fmt == b'VP8 ':
            return struct.unpack('<HH', data[26:30])[0] & 0x3FFF, \
                   struct.unpack('<HH', data[26:30])[1] & 0x3FFF
        if fmt == b'VP8L':
            bits = int.from_bytes(data[21:25], 'little')
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if fmt == b'VP8X':
            w = int.from_bytes(data[24:27], 'little') + 1
            h = int.from_bytes(data[27:30], 'little') + 1
            return w, h
        return None
    if data[:2] != b'\xff\xd8':
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = struct.unpack('>H', data[i + 2:i + 4])[0]
        # SOF0..SOF15, minus the DHT/JPG/DAC markers that share the range.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack('>HH', data[i + 5:i + 9])
            return width, height
        i += 2 + length
    return None


# CODE_REVIEW SEO-1 — clean_text/title_from_page/date_from_page/SITE_SUFFIX_RE
# lived here only to build the /api/og query string. That fallback is gone, so
# they went with it rather than staying as code that looks maintained but has
# no caller.
def image_for(slug: str, src: str) -> str:
    for ext in ('png', 'webp'):
        if (OG_DIR / f'{slug}.{ext}').exists():
            return f'{DOMAIN}/assets/og/{slug}.{ext}'
    # about.html keeps the portrait it already ships: a photograph of the
    # physician is a better share image for that page than a generated card.
    existing = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', src, re.I)
    if existing and '/api/og' not in existing.group(1) \
            and 'logo-512' not in existing.group(1):
        return existing.group(1)
    # CODE_REVIEW SEO-1 — the fallback used to be /api/og?…, and api/og.js:147
    # answers with `Content-Type: image/svg+xml`. Facebook, X and LINE all
    # ignore an SVG og:image, so 28 articles shared with no preview card at
    # all while this normalizer reported success. The fallback is now a raster
    # that every platform renders, and it is LOUD: a generic logo card is a
    # degraded result, not a correct one. _check_seo_signals fails the gate on
    # it, and `python _gen_og_cards.py` produces the missing card.
    print(f'[WARN] {slug}: no assets/og/{slug}.png — falling back to the site '
          f'logo. Run: python _gen_og_cards.py')
    return f'{DOMAIN}/logo-512.png'


def patch_meta(src: str, image_url: str) -> str:
    escaped = html.escape(image_url, quote=True)
    # CODE_REVIEW SEO-4 — pages carrying a dn-og-extras block let
    # _normalize_og_article_meta own twitter:image and the og:image dimensions.
    # Inserting them here as well made the two normalizers fight: this one
    # added the tag after og:image, that one's ORPHAN_RE stripped anything
    # following its end marker, and consecutive builds flipped between the two
    # states. Existing values are still refreshed; only INSERTION is deferred.
    owned = 'dn-og-extras:start' in src
    for attr in ('property="og:image"', 'name="twitter:image"'):
        src, n = re.subn(
            rf'(<meta\s+{attr}\s+content=")[^"]*(")',
            lambda m: m.group(1) + escaped + m.group(2),
            src,
            count=1,
            flags=re.I,
        )
        # CODE_REVIEW SEO-1 — this only ever REPLACED, so 13 newer articles
        # that shipped without a twitter:image kept shipping without one and
        # the normalizer reported success. X falls back to og:image, so
        # nothing looked broken; the tag was simply never there. Insert it
        # next to og:image when it is missing.
        if n == 0 and not owned and attr.startswith('name="twitter:image"'):
            src = re.sub(
                r'(<meta\s+property="og:image"\s+content="[^"]*"\s*/?>)',
                lambda m: m.group(1) + '\n  <meta name="twitter:image" content="'
                + escaped + '" />',
                src,
                count=1,
                flags=re.I,
            )

    # CODE_REVIEW SEO-4 — one article shipped without a twitter:card, so X
    # rendered it as a small thumbnail instead of the large card every other
    # page gets. Inserted with the value all 65 other pages already use.
    if 'name="twitter:card"' not in src and not owned:
        src = re.sub(
            r'(<meta\s+property="og:image"\s+content="[^"]*"\s*/?>)',
            lambda m: '<meta name="twitter:card" content="summary_large_image" />\n  '
            + m.group(1),
            src, count=1, flags=re.I,
        )

    # CODE_REVIEW SEO-4 — og:image:width / og:image:height were emitted only
    # by _normalize_og_article_meta, which skips every non-article page, so
    # ten pages including the HOMEPAGE shipped a share image with no declared
    # size. The numbers are read out of the file rather than assumed, so they
    # cannot drift from the asset.
    local = image_url.replace(DOMAIN + '/', '')
    size = image_size(ROOT / local) if not local.startswith('http') else None
    if size:
        for key, value in (('og:image:width', size[0]), ('og:image:height', size[1])):
            pattern = rf'(<meta\s+property="{key}"\s+content=")[^"]*(")'
            src, n = re.subn(pattern, lambda m: m.group(1) + str(value) + m.group(2),
                             src, count=1, flags=re.I)
            if n == 0 and not owned:
                src = re.sub(
                    r'(<meta\s+property="og:image"\s+content="[^"]*"\s*/?>)',
                    lambda m: m.group(1) + f'\n  <meta property="{key}" '
                    f'content="{value}" />',
                    src, count=1, flags=re.I,
                )
    return src


def targets() -> list[Path]:
    # CODE_REVIEW SEO-1 — the two blog hub pages used to be skipped, which left
    # topics.html on the /api/og SVG endpoint (no platform renders it) and
    # index.html on the 512x512 site logo. The public top-level pages were not
    # covered at all: support.html was also on the SVG endpoint, and the
    # HOMEPAGE shared as a 512x512 square logo. They are shared like any other
    # page, and all of them now have a card.
    pages = sorted(BLOG.glob('*.html'))
    pages += [ROOT / f'{name}.html' for name in TOP_LEVEL_PAGES]
    pages += [ROOT / 'about.html']
    return [p for p in pages if p.exists()]


def main() -> None:
    n = 0
    for path in targets():
        src = path.read_text(encoding='utf-8')
        image_url = image_for(card_slug(path), src)
        next_src = patch_meta(src, image_url)
        if next_src != src:
            path.write_text(next_src, encoding='utf-8')
            n += 1
            print('normalized social image', path.relative_to(ROOT).as_posix())
    print(f'Normalized social images in {n} files')


if __name__ == '__main__':
    main()
