"""Blocking local equivalents of the Quality gate, including browser budgets.

Requires Python 3.12 with html5validator/lxml, Java 21, Node 20 and
@lhci/cli 0.13.x with Puppeteer on PATH. Reports go outside the source tree.
The other workflows retain their documented informational/operational scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
HTML_IGNORE = [
    'Attribute .* is not allowed on element',
    'Attribute "[^"]+" not allowed on element', 'Element .* not allowed as child of',
    *['CSS: "' + prop + '"' for prop in (
        'inset', 'text-underline-offset', 'text-wrap', 'background-clip',
        'backdrop-filter', 'content-visibility', 'contain-intrinsic-size', 'aspect-ratio')],
    r'CSS: "padding-(top|bottom|left|right)".*env\(', r'CSS: "padding": "env\(',
    *['CSS: "' + prop + '": Unknown dimension' for prop in ('min-height','max-height','height')],
    'CSS: "[a-z-]+": Parse Error', 'CSS: Unrecognized at-rule "@view-transition"',
    'CSS: Parse Error', 'Bad value "speculationrules" for attribute "type" on element "script"',
]


def main() -> int:
    output = Path(tempfile.mkdtemp(prefix='dermnotes-ci-'))
    print(f'CI evidence: {output}', flush=True)
    results = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                               text=True).strip(), 'checks': [], 'passed': False}
    server = None

    def run(name, command, cwd=ROOT):
        print(f'Running {name}', flush=True)
        log = output / (name + '.log')
        with log.open('w', encoding='utf-8') as handle:
            result = subprocess.run(command, cwd=cwd, stdout=handle, stderr=subprocess.STDOUT)
        results['checks'].append({'name':name, 'command':command,
                                  'exit_code':result.returncode, 'log':str(log)})
        if result.returncode:
            print(log.read_text(encoding='utf-8', errors='replace')[-8000:], flush=True)
            raise subprocess.CalledProcessError(result.returncode, command)

    try:
        required = ['node', 'npm', 'java', 'html5validator', 'lhci', 'openssl']
        commands = {name:shutil.which(name + '.cmd' if os.name == 'nt' and name in ('npm','lhci') else name)
                    for name in required}
        missing = [name for name, path in commands.items() if not path]
        if missing:
            raise RuntimeError('Missing CI dependencies: ' + ', '.join(missing))
        run('build', [sys.executable, str(ROOT / '_run_quality.py'), 'build'])
        run('html-validate', [commands['html5validator'], '--root', str(ROOT), '--match', '*.html',
                              '--log', 'INFO', '--ignore-re', *HTML_IGNORE])
        # Ephemeral, untrusted local certificate; no system certificate store or
        # network protection settings are changed. HTTPS avoids local HTTP
        # content injection and serves the same files with the same routes.
        cert = output / 'localhost.pem'
        key = output / 'localhost-key.pem'
        run('local-certificate', [commands['openssl'], 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', str(key), '-out', str(cert), '-sha256', '-days', '1', '-nodes',
            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'])
        # Bind an OS-assigned port; do not accidentally audit an unrelated server.
        with (output / 'server.log').open('w', encoding='utf-8') as log:
            server = subprocess.Popen([commands['node'], str(ROOT / '_serve.mjs'),
                                       '--host', '127.0.0.1', '--port', '0',
                                       '--tls-cert', str(cert), '--tls-key', str(key)], cwd=ROOT,
                                      stdout=log, stderr=subprocess.STDOUT)
        import re
        base = None
        for _ in range(100):
            if server.poll() is not None:
                raise RuntimeError('CI preview server exited before becoming ready')
            match = re.search(r'https://127\.0\.0\.1:(\d+)',
                              (output / 'server.log').read_text(encoding='utf-8'))
            if match and match[1] != '0':
                base = match[0]
                import ssl
                # Trust only this run's generated certificate for readiness.
                context = ssl.create_default_context(cafile=str(cert))
                with urllib.request.urlopen(base, timeout=5, context=context) as response:
                    if response.status == 200:
                        break
            time.sleep(.1)
        if not base:
            raise RuntimeError('CI preview server did not become ready')
        # Puppeteer owns Chrome to avoid chrome-launcher profile cleanup failures
        # on Windows. This script makes no changes to page/network/audit behavior.
        (output / 'browser.cjs').write_text('module.exports = async () => {};\n', encoding='utf-8')
        from urllib.parse import urlsplit
        config = json.loads((ROOT / '.lighthouserc.json').read_text(encoding='utf-8'))
        collect = config['ci']['collect']
        collect['url'] = [base + urlsplit(url).path for url in collect['url']]
        collect['puppeteerScript'] = 'browser.cjs'
        spki = subprocess.check_output([commands['node'], '-e',
            "const c=require('node:crypto'),fs=require('node:fs');"
            "const cert=new c.X509Certificate(fs.readFileSync(process.argv[1]));"
            "console.log(c.createHash('sha256').update(cert.publicKey.export({type:'spki',format:'der'})).digest('base64'));",
            str(cert)], text=True).strip()
        collect['puppeteerLaunchOptions'] = {'args':['--ignore-certificate-errors-spki-list=' + spki]}
        if os.environ.get('CHROME_PATH'):
            config['ci']['collect']['chromePath'] = os.environ['CHROME_PATH']
        (output / 'lighthouserc.json').write_text(json.dumps(config), encoding='utf-8')
        run('lighthouse-collect', [commands['lhci'], 'collect', '--config=lighthouserc.json'], output)
        run('lighthouse-assert', [commands['lhci'], 'assert', '--config=lighthouserc.json'], output)
        results['passed'] = True
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        results['error'] = str(exc)
        print(f'CI FAILED: {exc}', flush=True)
        return 1
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            server.wait(timeout=10)
        (output / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
