"""Rebuild a recorded patient package using an explicitly trusted pipeline.

The archive is read, never extracted or executed. Only a fresh system-temporary
checkout of the caller's exact current pipeline runs code. Approved source is
reconstructed independently before generation; every Git output and ignored
Pagefind byte must then match. This does not verify live author intent, approve
clinical content, pass CI, modify the original checkout or publish anything.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import contextmanager
from argparse import ArgumentTypeError
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

import _cms_generated_package as package
import _cms_patient_package as patient
from _normalize_date_modified import content_date_argument
from _prepare_article_candidate import revision


def environment(temporary: Path) -> dict[str, str]:
    """Do not pass GitHub/Vercel/session tokens or inherited Git/npm options."""
    allowed = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'LANG', 'LC_ALL'}
    env = {key.upper(): value for key, value in os.environ.items() if key.upper() in allowed}
    # HOME/USERPROFILE are child-process values only, never the user's shell vars.
    env.update({'HOME': str(temporary), 'USERPROFILE': str(temporary),
                'APPDATA': str(temporary / 'appdata'),
                'LOCALAPPDATA': str(temporary / 'localappdata'),
                'TMP': str(temporary), 'TEMP': str(temporary), 'TMPDIR': str(temporary),
                'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                'GIT_TERMINAL_PROMPT': '0',
                'NPM_CONFIG_USERCONFIG': str(temporary / 'npmrc'),
                'NPM_CONFIG_GLOBALCONFIG': str(temporary / 'global-npmrc'),
                'NPM_CONFIG_CACHE': str(temporary / 'npm-cache'),
                'NPM_CONFIG_IGNORE_SCRIPTS': 'true',
                'NPM_CONFIG_REGISTRY': 'https://registry.npmjs.org/'})
    (temporary / 'npmrc').write_text('ignore-scripts=true\n', encoding='ascii')
    (temporary / 'global-npmrc').write_bytes(b'')
    return env


def command(checkout: Path, args: list[str], env: dict, log, timeout=60, *, data=None) -> bytes:
    result = subprocess.run(args, cwd=checkout, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=timeout, input=data)
    log.write(result.stdout)
    log.flush()
    if result.returncode:
        # Detailed output stays in the caller's private log; no credential or
        # draft text is interpolated into the public exception message.
        raise ValueError(f'Patient rebuild command failed (exit {result.returncode})')
    return result.stdout


def git(checkout: Path, env: dict, log, *args: str) -> bytes:
    return command(checkout, ['git', *args], env, log)


def install_dependencies(checkout: Path, env: dict, log) -> dict:
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm', path=env.get('PATH'))
    if not npm:
        raise ValueError('Locked dependency installation requires npm')
    command(checkout, [npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], env, log, 300)
    code = ('import os,sys,json;sys.path.insert(0,os.getcwd());'
            'from _run_pagefind import locked_binary;'
            'print(json.dumps(str(locked_binary())))')
    binary = Path(json.loads(command(checkout, [sys.executable, '-I', '-B', '-c', code], env, log)))
    pagefind_version = command(checkout, [str(binary), '--version'], env, log).decode().strip()
    if pagefind_version.lower() != 'pagefind 1.5.2':
        raise ValueError('Unexpected Pagefind tool version')
    return {'python': sys.version, 'node': command(checkout, ['node', '--version'], env, log).decode().strip(),
            'npm': command(checkout, [npm, '--version'], env, log).decode().strip(),
            'pagefind': pagefind_version, 'pagefindBinarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'dependencyScriptsEnabled': False, 'generationRegistryResolution': False,
            'dependencyInstallMayUseNetwork': True}


def generate(checkout: Path, frozen_date: str, env: dict, log) -> None:
    # -I discards inherited Python import settings. The only import root is the
    # trusted checkout. Draft code and archive-provided modules are never loaded.
    code = ('import os,sys;sys.path.insert(0,os.getcwd());import _run_quality as q;'
            'q.run_steps("Patient regeneration",q.regeneration_steps(sys.argv[1]));'
            'q.run_steps("Patient build artifacts",q.BUILD_GENERATED_STEPS)')
    command(checkout, [sys.executable, '-I', '-B', '-c', code, frozen_date], env, log, 900)


def reconstruct_source(checkout: Path, descriptor: dict, env: dict, log, *, now=None) -> None:
    tracked = descriptor['trackedPackage']
    proof = tracked['sourceEvidence']
    # Reconstruction helpers also come from the pipeline, with the same clean
    # environment as generators. No child launched during catalog evaluation
    # inherits the parent session's credential or Python/Git configuration.
    code = ('import os,sys,json,hashlib;from pathlib import Path;from datetime import datetime;'
            'sys.path.insert(0,os.getcwd());'
            'from _prepare_article_candidate import plan,apply;'
            'from _cms_delivery import with_receipt;'
            'data=json.load(sys.stdin);proof=data["proof"];root=Path.cwd();'
            'clock=datetime.fromisoformat(data["now"]) if data["now"] else None;'
            'files=plan(root,proof["requestHead"],proof["file"],proof["articleBlobSha"]);'
            'files=with_receipt(root,files,proof,now=clock);'
            'apply(root,files,expected_head=proof["preparedAgainst"]);'
            'print(json.dumps({name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}))')
    payload = json.dumps({'proof': proof, 'now': now.isoformat() if now is not None else None}).encode('utf8')
    result = command(checkout, [sys.executable, '-I', '-B', '-c', code], env, log, data=payload)
    digests = json.loads(result)
    # Recreating the entire tree also checks catalog changes. Merely matching a
    # digest supplied by a receipt would permit unrelated draft-controlled JS.
    git(checkout, env, log, 'add', '--all')
    expected_tree, _ = package.commit(checkout, tracked['sourceHead'])
    if git(checkout, env, log, 'write-tree').decode().strip() != expected_tree:
        raise ValueError('Source preparation differs from independent reconstruction')
    source_entries = package.entries(checkout, expected_tree)
    for name, digest in digests.items():
        row = source_entries.get(name)
        raw = package.run(checkout, 'cat-file', 'blob', row['blobSha']) if row else b''
        if hashlib.sha256(raw).hexdigest() != digest or hashlib.sha256((checkout / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Source preparation changed reconstructed raw bytes')
    # Change only the disposable checkout's detached HEAD, after verifying every
    # materialized source byte. No checkout of the untrusted source branch runs.
    git(checkout, env, log, 'update-ref', '--no-deref', 'HEAD', tracked['sourceHead'])


def compare_outputs(checkout: Path, descriptor: dict, env: dict, log) -> dict:
    expected = descriptor['trackedPackage']['files']
    source_tree, _ = package.commit(checkout, descriptor['trackedPackage']['sourceHead'])
    source_entries = package.entries(checkout, source_tree)
    # Generators can legitimately delete obsolete tracked artifacts. Refresh
    # only this disposable index so cached source paths cannot masquerade as
    # surviving outputs; unexpected additions still fail the complete census.
    git(checkout, env, log, 'add', '--all')
    paths = git(checkout, env, log, 'ls-files', '-z', '--cached', '--others', '--exclude-standard')
    actual = {name.decode('utf8') for name in paths.split(b'\0') if name}
    if actual != set(expected):
        raise ValueError('Rebuild added, omitted or renamed a tracked output')
    total = 0
    for name, row in expected.items():
        patient.safe_path(name)
        path = checkout / name
        try:
            info = path.lstat()
        except FileNotFoundError as error:
            raise ValueError('Rebuild omitted a tracked output') from error
        if (not patient.ordinary(info) or info.st_nlink != 1 or path.resolve() != path or
                not path.resolve().is_relative_to(checkout) or info.st_size != row['size']):
            raise ValueError('Rebuild output is missing, linked or has a different size')
        if row['mode'] != source_entries.get(name, {'mode': '100644'})['mode']:
            raise ValueError('Rebuild changed an output Git mode')
        if os.name != 'nt' and bool(stat.S_IMODE(info.st_mode) & 0o111) != (row['mode'] == '100755'):
            raise ValueError('Rebuild output mode differs')
        with path.open('rb') as stream:
            if patient.identity(os.fstat(stream.fileno())) != patient.identity(info):
                raise ValueError('Rebuild output changed while opening')
            raw = stream.read(patient.MAX_BLOB + 1)
            if (patient.identity(os.fstat(stream.fileno())) != patient.identity(info) or
                    patient.identity(path.lstat()) != patient.identity(info) or len(raw) != info.st_size):
                raise ValueError('Rebuild output changed while reading')
        total += len(raw)
        if total > patient.MAX_TOTAL or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Rebuild tracked output bytes differ')
    extra = patient.pagefind_files(checkout)
    found = {name: {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
             for name, raw in extra.items()}
    if found != descriptor['extraFiles']:
        raise ValueError('Rebuild Pagefind inventory or raw bytes differ')
    ignored = git(checkout, env, log, 'ls-files', '-z', '--others', '--ignored', '--exclude-standard')
    for raw_name in ignored.split(b'\0'):
        if not raw_name:
            continue
        name = raw_name.decode('utf8')
        if (name.startswith('node_modules/') or '__pycache__' in Path(name).parts or name in extra):
            continue
        raise ValueError('Rebuild produced an unrecorded ignored output')
    return {'trackedFiles': len(expected), 'pagefindFiles': len(extra)}


@contextmanager
def workspace(root: Path):
    temp_root = Path(tempfile.gettempdir()).resolve()
    temporary = Path(tempfile.mkdtemp(prefix='cms-patient-rebuild-', dir=temp_root)).resolve()
    if not temporary.is_relative_to(temp_root) or temporary.is_relative_to(root):
        raise ValueError('Rebuild workspace escaped system temporary storage')
    try:
        yield temporary
    finally:
        # A failed guard leaves the directory for inspection; it cannot trigger
        # an automatic recursive cleanup of an unverified replacement target.
        if (temporary.resolve() != temporary or not temporary.is_relative_to(temp_root) or
                temporary.is_relative_to(root) or not patient.ordinary(temporary.lstat(), directory=True)):
            raise ValueError('Rebuild cleanup target changed')
        def remove_readonly(function, name, error):
            target = Path(name)
            # Windows Git objects can carry the readonly attribute. Clear it
            # only on the verified ordinary temporary child that failed; never
            # retry against a link, replacement target or unrelated OS error.
            if (os.name != 'nt' or not isinstance(error, PermissionError) or
                    function not in {os.unlink, os.rmdir} or
                    not target.resolve().is_relative_to(temporary)):
                raise error
            info = target.lstat()
            if not (patient.ordinary(info) or patient.ordinary(info, directory=True)):
                raise error
            os.chmod(target, info.st_mode | stat.S_IWUSR)
            function(target)
        shutil.rmtree(temporary, onexc=remove_readonly)


def verify(root: Path, raw: bytes, expected_pipeline: str, frozen_date: str, *, now=None, log=None) -> dict:
    root = root.resolve()
    expected_pipeline = revision(expected_pipeline)
    try:
        frozen_date = content_date_argument(frozen_date)
    except ArgumentTypeError as error:
        raise ValueError('Rebuild requires a valid frozen content date') from error
    receipt = patient.verify(root, raw, now=now)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        descriptor = package.parse(archive.read('manifest.json'), canonical=True, limit=patient.MAX_MANIFEST)
    tracked = descriptor['trackedPackage']
    if (tracked['pipelineHead'] != expected_pipeline or
            package.run(root, 'rev-parse', 'HEAD').decode().strip() != expected_pipeline):
        raise ValueError('Archive pipeline differs from the explicitly trusted current HEAD')
    # Preflight bounds/types/path collisions before any tool code is executed.
    pipeline_tree, _ = package.commit(root, expected_pipeline)
    pipeline = package.inventory(root, pipeline_tree)
    patient.unique_paths(list(pipeline))
    for required in ('_run_quality.py', '_prepare_article_candidate.py', '_cms_delivery.py',
                     'package.json', 'package-lock.json'):
        if required not in pipeline or pipeline[required]['mode'] != '100644':
            raise ValueError('Trusted pipeline lacks ordinary build inputs')
    original_refs = package.run(root, 'show-ref')
    original_status = package.run(root, 'status', '--porcelain', '--untracked-files=all')
    private_log = tempfile.TemporaryFile() if log is None else None
    output = private_log if private_log is not None else log
    try:
        with workspace(root) as temporary:
            env = environment(temporary)
            checkout = temporary / 'checkout'
            command(temporary, ['git', 'clone', '--no-hardlinks', '--no-checkout', '--',
                                str(root), str(checkout)], env, output)
            git(checkout, env, output, 'config', 'core.autocrlf', 'false')
            # Import commits reachable only through a supplied immutable
            # package. This fetch uses a local path, never GitHub credentials.
            git(checkout, env, output, 'fetch', '--no-tags', '--no-write-fetch-head', '--',
                str(root), tracked['sourceHead'], tracked['generatedHead'])
            git(checkout, env, output, 'checkout', '--detach', expected_pipeline)
            reconstruct_source(checkout, descriptor, env, output, now=now)
            tools = install_dependencies(checkout, env, output)
            generate(checkout, frozen_date, env, output)
            counts = compare_outputs(checkout, descriptor, env, output)
    finally:
        if private_log is not None:
            private_log.close()
    if (package.run(root, 'show-ref') != original_refs or
            package.run(root, 'status', '--porcelain', '--untracked-files=all') != original_status or
            package.run(root, 'rev-parse', 'HEAD').decode().strip() != expected_pipeline):
        raise ValueError('Original checkout changed during patient rebuild')
    return {**receipt, 'state': 'patient_package_rebuilt', 'pipelineHead': expected_pipeline,
            'sourceHead': tracked['sourceHead'], 'generatedHead': tracked['generatedHead'],
            'generatedTreeSha': tracked['generatedTreeSha'], 'contentDate': frozen_date,
            'packageLockSha256': pipeline['package-lock.json']['sha256'],
            'tools': tools, **counts, 'generationVerified': True,
            'liveAuthorIntentVerified': False, 'contentApproved': False,
            'ciVerified': False, 'published': False}
