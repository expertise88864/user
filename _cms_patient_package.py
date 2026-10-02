"""Archive immutable Git outputs and all ignored Pagefind bytes for review.

Recording and ordinary verification only inspect portable content snapshots.
The explicit rebuild command delegates to a system-temporary trusted pipeline;
it never runs archive code or modifies the original checkout. Neither an archive
nor a rebuild approves medical content, verifies live author intent, passes CI
or publishes anything.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import unicodedata
import zipfile

import _cms_generated_package as package

MAX_FILES = 10_000
MAX_BLOB = 50_000_000
MAX_TOTAL = 256_000_000
MAX_MANIFEST = 2_000_000
MAX_ARCHIVE = 280_000_000
FIELDS = {'version', 'state', 'trackedPackage', 'extraFiles', 'generationVerified',
          'liveAuthorIntentVerified', 'contentApproved', 'ciVerified', 'published'}
FALSE_FIELDS = ('generationVerified', 'liveAuthorIntentVerified', 'contentApproved',
                'ciVerified', 'published')


def safe_path(name: str) -> str:
    if (not isinstance(name, str) or not name or len(name.encode('utf8')) > 1000 or
            '\\' in name or ':' in name or PurePosixPath(name).as_posix() != name or
            name.startswith('/') or any(part in {'', '.', '..'} for part in name.split('/')) or
            any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError('Unsafe archive path')
    return name


def unique_paths(names: list[str]) -> None:
    normalized = [unicodedata.normalize('NFC', safe_path(n)).casefold() for n in names]
    if len(set(normalized)) != len(normalized):
        raise ValueError('Archive paths collide on a different filesystem')


def identity(info: os.stat_result) -> tuple:
    # Windows stat/fstat can expose different deprecated ctime semantics.
    # Compare the documented creation timestamp there, while retaining inode,
    # device, size, modification time and full byte comparisons on every OS.
    clock = info.st_birthtime_ns if os.name == 'nt' else info.st_ctime_ns
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, clock


def ordinary(info: os.stat_result, *, directory=False) -> bool:
    reparse = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
    return (not getattr(info, 'st_file_attributes', 0) & reparse and
            (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)))


def pagefind_files(root: Path) -> dict[str, bytes]:
    """Read every regular output, rejecting links, races and oversized content."""
    root = root.resolve()
    folder = root / 'pagefind'
    if not ordinary(folder.lstat(), directory=True) or folder.resolve() != folder:
        raise ValueError('Pagefind output must be a real directory under the repository')
    result = {}
    total = 0
    directories = [folder]
    directory_count = 0
    while directories:
        directory = directories.pop()
        directory_count += 1
        if directory_count > MAX_FILES:
            raise ValueError('Pagefind directory inventory exceeds its bound')
        before = directory.lstat()
        if not ordinary(before, directory=True) or not directory.resolve().is_relative_to(folder):
            raise ValueError('Pagefind contains a linked directory')
        for path in sorted(directory.iterdir()):
            name = safe_path(path.relative_to(root).as_posix())
            info = path.lstat()
            if ordinary(info, directory=True):
                directories.append(path)
                continue
            if not ordinary(info) or info.st_nlink != 1:
                raise ValueError('Pagefind contains a link or non-ordinary file')
            if info.st_size > MAX_BLOB:
                raise ValueError('Pagefind blob exceeds its bound')
            # Check the opened handle before reading. A replaced parent/file
            # cannot make the archive read an external target through a link.
            with path.open('rb') as source:
                opened = os.fstat(source.fileno())
                if (not ordinary(opened) or opened.st_nlink != 1 or identity(opened) != identity(info) or
                        path.resolve() != path or not path.resolve().is_relative_to(folder)):
                    raise ValueError('Pagefind file changed while opening')
                raw = source.read(MAX_BLOB + 1)
                if (len(raw) != info.st_size or identity(os.fstat(source.fileno())) != identity(info) or
                        identity(path.lstat()) != identity(info)):
                    raise ValueError('Pagefind file changed while reading')
            result[name] = raw
            total += len(raw)
            if len(result) > MAX_FILES or total > MAX_TOTAL:
                raise ValueError('Pagefind inventory exceeds its bound')
        if identity(directory.lstat()) != identity(before):
            raise ValueError('Pagefind directory changed while reading')
    unique_paths(list(result))
    if 'pagefind/pagefind.js' not in result or not result:
        raise ValueError('Pagefind output is missing its entry point')
    return dict(sorted(result.items()))


def zip_entry(name: str, raw: bytes, mode: int) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_STORED
    return info, raw


def record(root: Path, tracked_raw: bytes, *, now=None) -> bytes:
    root = root.resolve()
    package.verify(root, tracked_raw, now=now)
    tracked = package.parse(tracked_raw, canonical=True, limit=package.MAX_MANIFEST)
    extra = pagefind_files(root)
    names = list(tracked['files']) + list(extra)
    unique_paths(names)
    if any(n == 'pagefind' or n.startswith('pagefind/') for n in tracked['files']):
        raise ValueError('Pagefind must have one complete ignored-output inventory')
    total = sum(row['size'] for row in tracked['files'].values()) + sum(map(len, extra.values()))
    if len(names) > MAX_FILES or total > MAX_TOTAL:
        raise ValueError('Patient package exceeds its bound')
    descriptor = {'version': 1, 'state': 'patient_package_recorded', 'trackedPackage': tracked,
                  'extraFiles': {n: {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
                                 for n, raw in extra.items()}, **dict.fromkeys(FALSE_FIELDS, False)}
    manifest = package.encode(descriptor)
    if len(manifest) > MAX_MANIFEST:
        raise ValueError('Patient package manifest exceeds its bound')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', allowZip64=False) as archive:
        info, raw = zip_entry('manifest.json', manifest, 0o644)
        archive.writestr(info, raw)
        for name in sorted(names):
            row = tracked['files'].get(name)
            raw = package.run(root, 'cat-file', 'blob', row['blobSha']) if row else extra[name]
            expected = row or descriptor['extraFiles'][name]
            if len(raw) > MAX_BLOB or len(raw) != expected['size'] or hashlib.sha256(raw).hexdigest() != expected['sha256']:
                raise ValueError('Patient package bytes differ from their identity')
            info, raw = zip_entry('files/' + name, raw, 0o755 if row and row['mode'] == '100755' else 0o644)
            archive.writestr(info, raw)
            if output.tell() > MAX_ARCHIVE:
                raise ValueError('Patient archive exceeds its bound')
    if pagefind_files(root) != extra:
        raise ValueError('Pagefind output changed during archive creation')
    raw = output.getvalue()
    if len(raw) > MAX_ARCHIVE:
        raise ValueError('Patient archive exceeds its bound')
    return raw


def verify(root: Path, raw: bytes, *, now=None) -> dict:
    if len(raw) > MAX_ARCHIVE:
        raise ValueError('Patient archive exceeds its bound')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        items = archive.infolist()
        if not items or len(items) > MAX_FILES + 1:
            raise ValueError('Patient archive inventory exceeds its bound')
        names = [item.filename for item in items]
        unique_paths(names)
        if names[0] != 'manifest.json' or items[0].file_size > MAX_MANIFEST:
            raise ValueError('Patient archive requires one bounded manifest')
        for item in items:
            if (item.compress_type != zipfile.ZIP_STORED or item.flag_bits & 1 or
                    item.file_size != item.compress_size or item.file_size > MAX_BLOB or
                    not stat.S_ISREG(item.external_attr >> 16)):
                raise ValueError('Patient archive contains an unsupported entry')
        if sum(item.file_size for item in items[1:]) > MAX_TOTAL:
            raise ValueError('Patient package exceeds its bound')
        manifest_raw = archive.read(items[0])
        descriptor = package.parse(manifest_raw, canonical=True, limit=MAX_MANIFEST)
        if (not isinstance(descriptor, dict) or set(descriptor) != FIELDS or
                type(descriptor['version']) is not int or descriptor['version'] != 1 or
                descriptor['state'] != 'patient_package_recorded' or
                any(type(descriptor[k]) is not bool or descriptor[k] for k in FALSE_FIELDS)):
            raise ValueError('Invalid preparatory patient package')
        tracked = descriptor['trackedPackage']
        package.verify(root, package.encode(tracked), now=now)
        extra = descriptor['extraFiles']
        if not isinstance(extra, dict) or 'pagefind/pagefind.js' not in extra:
            raise ValueError('Patient package lacks the complete Pagefind inventory')
        for name, row in extra.items():
            if (not safe_path(name).startswith('pagefind/') or name in tracked['files'] or
                    not isinstance(row, dict) or set(row) != {'size', 'sha256'} or
                    type(row['size']) is not int or not 0 <= row['size'] <= MAX_BLOB or
                    not isinstance(row['sha256'], str) or len(row['sha256']) != 64 or
                    any(c not in '0123456789abcdef' for c in row['sha256'])):
                raise ValueError('Invalid Pagefind identity')
        expected = {**tracked['files'], **extra}
        unique_paths(list(expected))
        if names != ['manifest.json'] + ['files/' + n for n in sorted(expected)]:
            raise ValueError('Patient archive omits or adds an output')
        canonical = io.BytesIO()
        with zipfile.ZipFile(canonical, 'w', allowZip64=False) as copy:
            info, content = zip_entry('manifest.json', manifest_raw, 0o644)
            copy.writestr(info, content)
            for item in items[1:]:
                row = expected[item.filename[6:]]
                mode = 0o755 if row.get('mode') == '100755' else 0o644
                if stat.S_IMODE(item.external_attr >> 16) != mode:
                    raise ValueError('Patient output mode differs')
                content = archive.read(item)
                if len(content) != row['size'] or hashlib.sha256(content).hexdigest() != row['sha256']:
                    raise ValueError('Patient output bytes differ')
                info, content = zip_entry(item.filename, content, mode)
                copy.writestr(info, content)
        if canonical.getvalue() != raw:
            raise ValueError('Patient archive is not canonical')
    return {'archiveSha256': hashlib.sha256(raw).hexdigest(), 'files': len(expected),
            'ignoredPagefindFiles': len(extra), 'immutableIdentityVerified': True,
            **dict.fromkeys(FALSE_FIELDS, False)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    sub = parser.add_subparsers(dest='command', required=True)
    capture = sub.add_parser('record')
    capture.add_argument('manifest', type=Path)
    capture.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('verify')
    check.add_argument('archive', type=Path)
    rebuild = sub.add_parser('rebuild', help='Compare every output to isolated trusted generation')
    rebuild.add_argument('archive', type=Path)
    rebuild.add_argument('--pipeline-head', required=True, help='Exact trusted current HEAD, not inferred from the archive')
    rebuild.add_argument('--content-date', required=True, help='Frozen YYYY-MM-DD used for the recorded generation')
    args = parser.parse_args()
    if args.command == 'record':
        if args.output.resolve().is_relative_to(args.root.resolve()):
            raise ValueError('Archive output must be outside the repository')
        if args.manifest.stat().st_size > package.MAX_MANIFEST:
            raise ValueError('Tracked manifest exceeds its bound')
        raw = record(args.root, args.manifest.read_bytes())
        result = verify(args.root, raw)
        # Preserve an existing export instead of silently replacing its bytes.
        with args.output.open('xb') as destination:
            destination.write(raw)
    else:
        if args.archive.stat().st_size > MAX_ARCHIVE:
            raise ValueError('Patient archive exceeds its bound')
        raw = args.archive.read_bytes()
        if args.command == 'rebuild':
            from _cms_patient_rebuild import verify as rebuild_package
            result = rebuild_package(args.root, raw, args.pipeline_head, args.content_date)
        else:
            result = verify(args.root, raw)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
