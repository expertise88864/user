"""HTML documents that automatic site builders may inspect and rewrite.

Public and utility pages live directly in these deployed source roots. Do not
recurse into audit evidence, draft exports, package output or nested backups.
Discover the entire ordinary-file inventory before any caller starts writing.
"""
from pathlib import Path


SOURCE_ROOTS = ((), ('blog',), ('admin',))
ENGLISH_ROOTS = (('en',), ('en', 'blog'))


def _linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def site_html_files(root: str | Path, *, include_en: bool = True) -> list[Path]:
    """Return deterministic ordinary .html sources; reject linked source roots."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Site source root is not a directory')
    files = []
    for parts in SOURCE_ROOTS + (ENGLISH_ROOTS if include_en else ()):
        directory = root
        for part in parts:
            directory = directory / part
            if _linked(directory):
                raise ValueError(f'Linked site source directory: {directory}')
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise ValueError(f'Site source directory is not a directory: {directory}')
        for path in directory.glob('*.html'):
            if not path.name.endswith('.html'):
                continue
            if _linked(path) or not path.is_file():
                raise ValueError(f'Site HTML source is not an ordinary file: {path}')
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())
