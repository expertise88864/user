"""Exercise the installed checker without the site's historical filters."""
from pathlib import Path
from tempfile import TemporaryDirectory
from html5validator.validator import Validator


def main():
    shell = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Validator regression</title><style>{}</style><body><p>Test</p></body></html>'
    cases = [
        ('modern-css', 'body { overscroll-behavior: contain; }', True),
        ('invalid-css', 'body { overscroll-behavior: impossible; }', False),
    ]
    with TemporaryDirectory() as directory:
        for name, css, expected_valid in cases:
            path = Path(directory) / (name + '.html')
            path.write_text(shell.format(css), encoding='utf-8')
            errors = Validator(errors_only=True).validate([str(path)])
            if (errors == 0) != expected_valid:
                raise SystemExit(f'{name}: unexpected validation result ({errors})')
    print('Checker regression passed: valid modern CSS accepted; invalid value rejected.')


if __name__ == '__main__':
    main()
