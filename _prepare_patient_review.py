"""Prepare a reproducible patient review package from a live source request.

All code runs from the explicitly trusted main in disposable system-temporary
checkouts. Draft history is read as immutable input, never checked out or run.
The original checkout and remote refs remain unchanged. The exported package
and Git transport support later explicit approval; they grant no publication
permission, final medical approval or CI success.
"""
from __future__ import annotations

import argparse
import builtins
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import types
import zipfile

GENERATED_REF = 'refs/patient-review/generated'
MAX_BUNDLE = 280_000_000
EXECUTION_ROOT = Path(__file__).resolve().parent
HELPER_NAMES = ('_prepare_patient_review', '_cms_generated_package', '_cms_patient_package',
                '_cms_patient_rebuild', '_cms_delivery', '_normalize_date_modified',
                '_prepare_article_candidate', '_process_article_requests', '_validate_article_request',
                '_article_visibility', '_sync_hub_catalog', '_html_scan')
HELPER_PATHS = {name + '.py': EXECUTION_ROOT / (name + '.py') for name in HELPER_NAMES}
# No project helper executes at import time. Bind the already-running entry
# point, then validate every helper before compiling its immutable Git bytes.
ENTRY_HASH = hashlib.sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def trusted_runtime(root: Path, main: str) -> dict[str, bytes]:
    if root != EXECUTION_ROOT:
        raise ValueError('Preparation must execute from the trusted checkout itself')
    # Use stdlib Git reads until helper provenance is established. A stale
    # helper must not perform the checks that supposedly establish its trust.
    def read(*args):
        return subprocess.run(['git', *args], cwd=root, capture_output=True,
                              check=True, timeout=60).stdout
    entries = {}
    for row in read('ls-tree', '-r', '-z', '--full-tree', main).split(b'\0'):
        if row:
            header, name = row.split(b'\t', 1)
            entries[name.decode('utf8')] = header.decode('ascii').split()
    sources = {}
    for module in HELPER_NAMES:
        name = module + '.py'
        loaded = root / name
        info = loaded.lstat()
        reparse = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
        if (loaded.parent != root or not stat.S_ISREG(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & reparse):
            raise ValueError('Loaded preparation helper is outside the trusted checkout')
        current = loaded.read_bytes().replace(b'\r\n', b'\n')
        if module == '_prepare_patient_review' and hashlib.sha256(current).hexdigest() != ENTRY_HASH:
            raise ValueError('Preparation entry point changed during execution')
        row = entries.get(name)
        if not row or row[:2] != ['100644', 'blob']:
            raise ValueError('Trusted preparation helper is not an ordinary Git blob')
        raw = read('cat-file', 'blob', row[2])
        if raw.replace(b'\r\n', b'\n') != current:
            raise ValueError('Loaded preparation helper differs from the trusted pipeline')
        sources[module] = raw
    return sources


def load_runtime(root: Path, sources: dict[str, bytes]):
    """Run only verified source snapshots, without stale pyc or cached helpers.

    Project imports use this small private module set. Standard-library imports
    retain Python's normal behavior; unexpected project dependencies fail closed.
    No global sys.modules entry is removed or replaced.
    """
    modules = {}

    def import_verified(name, globals=None, locals=None, fromlist=(), level=0):
        if level or (name not in sources and name.split('.')[0] not in sys.stdlib_module_names):
            raise ImportError('Unbound preparation dependency: ' + name)
        if name not in sources:
            return builtins.__import__(name, globals, locals, fromlist, level)
        if name == '_prepare_patient_review':
            raise ImportError('Preparation helpers must not import the entry point')
        if name not in modules:
            module = types.ModuleType(name)
            module.__file__ = str(root / (name + '.py'))
            module.__builtins__ = {**vars(builtins), '__import__': import_verified}
            modules[name] = module
            exec(compile(sources[name], module.__file__, 'exec'), module.__dict__)
        return modules[name]

    return types.SimpleNamespace(
        package=import_verified('_cms_generated_package'),
        patient=import_verified('_cms_patient_package'),
        rebuild=import_verified('_cms_patient_rebuild'),
        delivery=import_verified('_cms_delivery'),
        dates=import_verified('_normalize_date_modified'),
        candidate=import_verified('_prepare_article_candidate'),
        process=import_verified('_process_article_requests'),
        request=import_verified('_validate_article_request'))


def artifact_destination(output: Path, root: Path) -> Path:
    """Normalize ordinary temp paths while rejecting link/reparse aliases."""
    output = output.absolute()
    if not output.parent.is_dir():
        raise ValueError('Review artifacts require a new directory in system temporary storage')
    for parent in (output.parent, *output.parent.parents):
        info = parent.lstat()
        reparse = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & reparse:
            raise ValueError('Review artifacts require ordinary parent directories')
    # Resolve the existing parent, not a nonexistent output. This accepts safe
    # Windows short/long-name and case normalization without trusting aliases.
    output = output.parent.resolve(strict=True) / output.name
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (not output.is_relative_to(temp_root) or output.is_relative_to(root) or
            os.path.lexists(output)):
        raise ValueError('Review artifacts require a new directory in system temporary storage')
    return output


def unchanged_source(root: Path, main: str, head: str, file: str,
                     refs: bytes, status: bytes, runtime) -> None:
    runtime.process.unchanged_main(root, main)
    runtime.request.verify_request_head(root, head, file)
    package = runtime.package
    if (package.run(root, 'rev-parse', 'HEAD').decode().strip() != main or
            package.run(root, 'show-ref') != refs or
            package.run(root, 'status', '--porcelain', '--untracked-files=all') != status):
        raise ValueError('Trusted checkout changed during patient preparation')


def write_artifacts(output: Path, files: dict[str, bytes], check_current, patient) -> None:
    # The caller receives a complete report only after exclusive writes succeed.
    # A partial directory after an I/O failure is retained for diagnosis, never
    # presented as a prepared package and never recursively removed here.
    output.mkdir()
    directory = output.lstat()
    if not patient.ordinary(directory, directory=True) or output.resolve() != output:
        raise ValueError('Artifact directory changed before writing')
    report_identity = None
    try:
        for name, raw in files.items():
            check_current()
            current = output.lstat()
            if (not patient.ordinary(current, directory=True) or output.resolve() != output or
                    (current.st_dev, current.st_ino) != (directory.st_dev, directory.st_ino)):
                raise ValueError('Artifact directory changed during writing')
            path = output / name
            with path.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                written = os.fstat(stream.fileno())
                if not patient.ordinary(written) or written.st_nlink != 1 or written.st_size != len(raw):
                    raise ValueError('Artifact output is not an ordinary complete file')
            if patient.identity(path.lstat()) != patient.identity(written) or path.resolve() != path:
                raise ValueError('Artifact output changed during writing')
            if name == 'report.json':
                report_identity = patient.identity(written)
        check_current()
    except Exception:
        # Preserve the package bytes for diagnosis, but retire our own success
        # report after cancellation/I/O failure. Never remove a replacement.
        report = output / 'report.json'
        try:
            current = output.lstat()
            if (report_identity is not None and output.resolve() == output and
                    patient.ordinary(current,directory=True) and
                    (current.st_dev,current.st_ino)==(directory.st_dev,directory.st_ino) and
                    patient.identity(report.lstat()) == report_identity and report.resolve() == report):
                with report.open('rb') as stream:
                    same = (patient.identity(os.fstat(stream.fileno())) == report_identity and
                            stream.read(len(files['report.json'])+1) == files['report.json'])
                if same and patient.identity(report.lstat()) == report_identity:
                    report.unlink()
        except FileNotFoundError:
            pass
        raise


def prepare(root: Path, output: Path, request_head: str, file: str,
            expected_main: str, content_date: str, *, now=None, log=None) -> dict:
    root = root.resolve()
    if root != EXECUTION_ROOT:
        raise ValueError('Preparation must execute from the trusted checkout itself')
    if any(not isinstance(value,str) or not re.fullmatch(r'(?!0{40})[a-f0-9]{40}',value)
           for value in (expected_main,request_head)):
        raise ValueError('Preparation requires full nonzero commit identities')
    main, head = expected_main, request_head
    actual = subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,
                            check=True,timeout=60).stdout.decode().strip()
    if actual != main:
        raise ValueError('Explicit pipeline must match trusted checkout and current main')
    # Establish the boundary before ANY project helper import or execution.
    status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'],
                            cwd=root, capture_output=True, check=True, timeout=60).stdout
    if status.strip():
        raise ValueError('Trusted checkout must be clean; preserve edits in the original checkout')
    sources = trusted_runtime(root, main)
    runtime = load_runtime(root, sources)
    package, patient, rebuild = runtime.package, runtime.patient, runtime.rebuild
    read_blob, revision = runtime.candidate.read_blob, runtime.candidate.revision
    slug = runtime.request.article_slug(file)
    try:
        content_date = runtime.dates.content_date_argument(content_date)
    except argparse.ArgumentTypeError as error:
        raise ValueError('Review preparation requires a valid frozen content date') from error
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Preparation clock requires a timezone')
    now = now.astimezone(timezone.utc)
    output = artifact_destination(output, root)
    if package.run(root, 'rev-parse', 'HEAD').decode().strip() != main or runtime.process.live_main(root) != main:
        raise ValueError('Explicit pipeline must match trusted checkout and current main')
    status = package.run(root, 'status', '--porcelain', '--untracked-files=all')
    if status.strip():
        raise ValueError('Trusted checkout must be clean; preserve edits in the original checkout')
    refs = package.run(root, 'show-ref')
    request_raw = read_blob(root, head, '.cms-requests/' + slug + '.json')[1]
    request = runtime.request.request_record(request_raw, file, now=now)
    if request['action'] == 'unpublish':
        raise ValueError('Unpublish retains its separate visibility-only workflow')
    files, proof = runtime.request.request_plan(root, head, file, request['blobSha'], now=now)
    if proof['preparedAgainst'] != main:
        raise ValueError('Source request was prepared against another pipeline')
    files = runtime.delivery.with_receipt(root, files, proof, now=now)
    unchanged_source(root, main, head, file, refs, status, runtime)
    # Validate every trusted input and object bound before running build tools.
    tree, _ = package.commit(root, main)
    trusted = package.inventory(root, tree)
    patient.unique_paths(list(trusted))
    for name in ('_run_quality.py', '_prepare_article_candidate.py', '_cms_delivery.py',
                 'package.json', 'package-lock.json'):
        if trusted.get(name, {}).get('mode') != '100644':
            raise ValueError('Trusted pipeline lacks ordinary build inputs')
    private_log = tempfile.TemporaryFile() if log is None else None
    build_log = private_log if private_log is not None else log
    try:
        with rebuild.workspace(root) as temporary:
            env = rebuild.environment(temporary)
            checkout = temporary / 'checkout'
            rebuild.command(temporary, ['git', 'clone', '--no-hardlinks', '--no-checkout', '--',
                                         str(root), str(checkout)], env, build_log)
            git = lambda *args: rebuild.git(checkout, env, build_log, *args)
            git('config', 'core.autocrlf', 'false')
            git('config', 'user.name', 'Patient Review Preparation')
            git('config', 'user.email', 'patient-review@example.invalid')
            git('checkout', '--detach', main)
            # apply is an existing bounded source writer. Code remains from
            # trusted main; only the validated article/media/receipt are added.
            runtime.candidate.apply(checkout, files, expected_head=main)
            git('add', '--', *sorted(files))
            # Freeze Git-derived article dates and commit identities too. The
            # second replay must see exactly this history, not today's clock.
            env.update({'GIT_AUTHOR_DATE': content_date + 'T12:00:00Z',
                        'GIT_COMMITTER_DATE': content_date + 'T12:00:00Z'})
            git('commit', '-m', 'Prepare patient source: ' + slug)
            source = revision(git('rev-parse', 'HEAD').decode().strip())
            if any(read_blob(checkout, source, name)[1] != raw for name, raw in files.items()):
                raise ValueError('Source commit changed approved raw bytes')
            tools = rebuild.install_dependencies(checkout, env, build_log)
            rebuild.generate(checkout, content_date, env, build_log)
            git('add', '--all')
            git('commit', '--allow-empty', '-m', 'Record generated patient review: ' + slug)
            generated = revision(git('rev-parse', 'HEAD').decode().strip())
            manifest = package.encode(package.create(checkout, source, generated, file, now=now))
            archive = patient.record(checkout, manifest, now=now)
            with zipfile.ZipFile(io.BytesIO(archive)) as stored:
                descriptor_raw = stored.read('manifest.json')
                descriptor = package.parse(descriptor_raw, canonical=True, limit=patient.MAX_MANIFEST)
            # Transport source/generated history only. Packaging the original
            # draft history would also export unrelated draft-controlled files.
            # Later validation must fetch the exact still-live author request
            # separately through its trusted, read-only repository transport.
            git('update-ref', GENERATED_REF, generated)
            bundle_path = temporary / 'objects.bundle'
            git('bundle', 'create', str(bundle_path), GENERATED_REF, '^' + main)
            if bundle_path.stat().st_size > MAX_BUNDLE:
                raise ValueError('Immutable Git transport exceeds its bound')
            bundle = bundle_path.read_bytes()
            git('checkout', '--detach', main)
            replay = rebuild.verify(checkout, archive, main, content_date, now=now, log=build_log)
            unchanged_source(root, main, head, file, refs, status, runtime)
            report = {'version': 1, 'repository': runtime.delivery.REPO, 'file': file,
                      'state': 'awaiting_generated_content_approval', 'pipelineHead': main,
                      'requestHead': head, 'sourceHead': source, 'generatedHead': generated,
                      'generatedTreeSha': descriptor['trackedPackage']['generatedTreeSha'],
                      'contentDate': content_date, 'sourceEvidence': proof,
                      'archive': 'patient-package.zip', 'archiveSha256': hashlib.sha256(archive).hexdigest(),
                      'manifest': 'patient-manifest.json', 'manifestSha256': hashlib.sha256(descriptor_raw).hexdigest(),
                      'objects': 'objects.bundle', 'objectsSha256': hashlib.sha256(bundle).hexdigest(),
                      'bundleRefs': {GENERATED_REF: generated},
                      'originalDraftHistoryIncluded': False,
                      'immutableRequestObjectFetchRequired': True,
                      'trackedFiles': replay['trackedFiles'], 'pagefindFiles': replay['pagefindFiles'],
                      'tools': tools, 'generationVerified': True, 'sourceRequestSeenLive': True,
                      'contentApproved': False, 'finalAuthorIntentVerified': False,
                      'ciVerified': False, 'published': False}
            def still_current():
                unchanged_source(root, main, head, file, refs, status, runtime)
                if trusted_runtime(root, main) != sources:
                    raise ValueError('Preparation helper changed during execution')
            write_artifacts(output, {'patient-package.zip': archive, 'patient-manifest.json': descriptor_raw,
                                     'objects.bundle': bundle, 'report.json': package.encode(report)}, still_current, patient)
            return report
    finally:
        if private_log is not None:
            private_log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--request-head', required=True)
    parser.add_argument('--file', required=True)
    parser.add_argument('--expected-main', required=True)
    parser.add_argument('--content-date', required=True)
    args = parser.parse_args()
    result = prepare(args.root, args.output, args.request_head, args.file,
                     args.expected_main, args.content_date)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
