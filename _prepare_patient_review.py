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
REVIEW_REF = 'refs/patient-review/candidate'
RELEASE_REF = 'refs/patient-release/candidate'
MAX_BUNDLE = 280_000_000
EXECUTION_ROOT = Path(__file__).resolve().parent
HELPER_NAMES = ('_prepare_patient_review', '_cms_generated_package', '_cms_patient_package',
                '_cms_patient_rebuild', '_cms_patient_review', '_cms_delivery', '_normalize_date_modified',
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
        review=import_verified('_cms_patient_review'),
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


def trusted_context(root: Path, main: str):
    """Establish provenance before importing any project helper."""
    root = root.resolve()
    if root != EXECUTION_ROOT:
        raise ValueError('Preparation must execute from the trusted checkout itself')
    if not isinstance(main,str) or not re.fullmatch(r'(?!0{40})[a-f0-9]{40}',main):
        raise ValueError('Preparation requires a full nonzero pipeline identity')
    def read(*args):
        return subprocess.run(['git',*args],cwd=root,capture_output=True,check=True,timeout=60).stdout
    if read('rev-parse','HEAD').decode().strip() != main:
        raise ValueError('Explicit pipeline must match trusted checkout and current main')
    status = read('status','--porcelain','--untracked-files=all')
    if status.strip():
        raise ValueError('Trusted checkout must be clean; preserve edits in the original checkout')
    sources = trusted_runtime(root,main)
    runtime = load_runtime(root,sources)
    runtime.process.unchanged_main(root,main)
    return root,sources,runtime,status,read('show-ref')


def prepare_release(root: Path, output: Path, approval_head: str, file: str,
                    expected_main: str, archive_path: Path | None, *, now=None, log=None) -> dict:
    """Build an exact candidate from explicit approval, without remote writes.

    Execute the trusted pipeline before materializing the reviewed Git history.
    Neither draft code nor archive code executes. Only the delivery receipt
    differs from the frozen author preview. The bundle still needs independent
    model review and the complete remote candidate/production delivery gates.
    """
    root,sources,runtime,status,refs = trusted_context(root,expected_main)
    package,patient,rebuild,review = runtime.package,runtime.patient,runtime.rebuild,runtime.review
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Preparation clock requires a timezone')
    now = now.astimezone(timezone.utc)
    approval_head = runtime.candidate.revision(approval_head)
    slug = runtime.request.article_slug(file)
    output = artifact_destination(output,root)
    evidence = package.GitEvidence(root)
    request_path = '.cms-requests/' + slug + '.json'
    request_blob,request_raw = runtime.delivery.github_file(
        runtime.delivery.ImmutableBlobs(evidence),request_path,approval_head,8000)
    request = runtime.delivery.parse(request_raw,canonical='compact',limit=8000)
    if (not isinstance(request,dict) or set(request) != review.REQUEST_FIELDS or
            type(request.get('version')) is not int or request['version'] != 2 or
            request.get('file') != file or type(request.get('contentApproved')) is not bool):
        raise ValueError('Release preparation requires exact final generated approval')
    frozen,manifest_blob,manifest_raw = review.load_review(evidence,request['reviewHead'],file,now=now)
    descriptor = frozen['patientManifest']
    proof = descriptor['trackedPackage']['sourceEvidence']
    if descriptor['trackedPackage']['pipelineHead'] != expected_main:
        raise ValueError('Final approval belongs to an older trusted pipeline')
    entry = {**proof,'version':2,'patientApproval':{
        'reviewHead':request['reviewHead'],'manifestBlobSha':manifest_blob,
        'manifestSha256':hashlib.sha256(manifest_raw).hexdigest(),
        'approvalHead':approval_head,'approvalBlobSha':request_blob,'approvedAt':request['approvedAt']}}
    receipt = package.encode({'version':1,'requests':[entry]})
    runtime.delivery.receipts(receipt,now=now)
    if request != review.expected_request(entry,frozen):
        raise ValueError('Final approval differs from the complete immutable patient preview')
    review.parent(evidence,approval_head,proof['requestHead'])
    review.changed_one(evidence,proof['requestHead'],approval_head,request_path,request_blob)
    def still_current():
        unchanged_source(root,expected_main,approval_head,file,refs,status,runtime)
        if trusted_runtime(root,expected_main) != sources:
            raise ValueError('Preparation helper changed during execution')
    still_current()
    archive = None
    if archive_path is not None:
        archive_path = archive_path.absolute()
        for parent_path in archive_path.parents:
            if not patient.ordinary(parent_path.lstat(),directory=True) or parent_path.resolve() != parent_path:
                raise ValueError('Patient archive has a linked parent')
        archive = review.read_control(archive_path.parent,archive_path.name,patient.MAX_ARCHIVE)
        if hashlib.sha256(archive).hexdigest() != frozen['archiveSha256']:
            raise ValueError('Patient archive differs from final author approval')
        patient.verify(root,archive,now=now)
        with zipfile.ZipFile(io.BytesIO(archive)) as stored:
            if stored.read('manifest.json') != package.encode(descriptor):
                raise ValueError('Patient archive manifest differs from final author approval')
    private_log = tempfile.TemporaryFile() if log is None else None
    build_log = private_log if private_log is not None else log
    try:
        with rebuild.workspace(root) as temporary:
            env = rebuild.environment(temporary)
            checkout = temporary/'checkout'
            rebuild.command(temporary,['git','clone','--no-hardlinks','--no-checkout','--',
                                      str(root),str(checkout)],env,build_log)
            git = lambda *args: rebuild.git(checkout,env,build_log,*args)
            git('config','core.autocrlf','false')
            git('config','user.name','Patient Release Preparation')
            git('config','user.email','patient-release@example.invalid')
            git('fetch','--no-tags','--no-write-fetch-head','--',str(root),
                request['reviewHead'],approval_head)
            git('checkout','--detach',expected_main)
            # Reconstruct and generate from trusted main; archive bytes are
            # validated but never extracted or used as executable inputs.
            rebuild.reconstruct_source(checkout,descriptor,env,build_log,now=now)
            tools = rebuild.install_dependencies(checkout,env,build_log)
            rebuild.generate(checkout,frozen['contentDate'],env,build_log)
            counts = rebuild.compare_outputs(checkout,descriptor,env,build_log)
            generated = descriptor['trackedPackage']['generatedHead']
            if git('write-tree').decode().strip() != package.commit(checkout,generated)[0]:
                raise ValueError('Regenerated tree differs from approved patient outputs')
            if archive is None:
                # Canonical ZIP_STORED packaging has fixed timestamps/modes.
                # Rebuild only from trusted generation and immutable approved
                # blobs; equality to the owner's original archive hash is
                # mandatory. A missing supplied archive never selects this mode.
                archive = patient.record(checkout,package.encode(descriptor['trackedPackage']),now=now)
                if hashlib.sha256(archive).hexdigest() != frozen['archiveSha256']:
                    raise ValueError('Rebuilt patient archive differs from final author approval')
                patient.verify(checkout,archive,now=now)
                with zipfile.ZipFile(io.BytesIO(archive)) as stored:
                    if stored.read('manifest.json') != package.encode(descriptor):
                        raise ValueError('Rebuilt archive manifest differs from final author approval')
            # Bind HEAD only after the independently generated complete tree
            # matches. No untrusted branch is checked out or executed.
            git('update-ref','--no-deref','HEAD',generated)
            runtime.candidate.apply(checkout,{review.review_path(file):manifest_raw},expected_head=generated)
            git('add','--',review.review_path(file))
            if git('write-tree').decode().strip() != package.commit(checkout,request['reviewHead'])[0]:
                raise ValueError('Reconstructed review tree differs from final approval')
            git('update-ref','--no-deref','HEAD',request['reviewHead'])
            runtime.candidate.apply(checkout,{runtime.delivery.FILE:receipt},expected_head=request['reviewHead'])
            git('add','--',runtime.delivery.FILE)
            env.update({'GIT_AUTHOR_DATE':request['approvedAt'],'GIT_COMMITTER_DATE':request['approvedAt']})
            git('commit','-m','Prepare approved patient candidate: '+slug)
            candidate = runtime.candidate.revision(git('rev-parse','HEAD').decode().strip())
            review.verify_delivery(candidate,package.GitEvidence(checkout),entry,now=now)
            review.verify_workspace(checkout,candidate,package.GitEvidence(checkout),now=now)
            if git('diff','--name-only',request['reviewHead'],candidate).decode().splitlines() != [runtime.delivery.FILE]:
                raise ValueError('Release candidate changed reviewed patient content')
            still_current()
            git('update-ref',RELEASE_REF,candidate)
            bundle_path = temporary/'objects.bundle'
            git('bundle','create',str(bundle_path),RELEASE_REF,'^'+expected_main)
            bundle = review.read_control(temporary,bundle_path.name,MAX_BUNDLE)
            report = {'version':1,'repository':runtime.delivery.REPO,'file':file,
                      'state':'approved_candidate_prepared','pipelineHead':expected_main,
                      'reviewHead':request['reviewHead'],'approvalHead':approval_head,
                      'candidateHead':candidate,'contentDate':frozen['contentDate'],
                      'patientApproval':entry['patientApproval'],'archiveSha256':frozen['archiveSha256'],
                      'objects':'objects.bundle','objectsSha256':hashlib.sha256(bundle).hexdigest(),
                      'bundleRefs':{RELEASE_REF:candidate},'originalDraftHistoryIncluded':False,
                      'immutableApprovalObjectFetchRequired':True,'generationVerified':True,
                      'finalAuthorIntentVerified':True,'contentApproved':True,
                      'independentReviewVerified':False,'ciVerified':False,'published':False,
                      'archiveRebuiltFromTrustedPipeline':archive_path is None,
                      'tools':tools,**counts}
            files = {'objects.bundle':bundle}
            if archive_path is None:
                report['archive'] = 'patient-package.zip'
                files['patient-package.zip'] = archive
            files['report.json'] = package.encode(report)
            write_artifacts(output,files,still_current,patient)
            return report
    finally:
        if private_log is not None:
            private_log.close()


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
            # Freeze the complete package in the previewable Git history. This
            # commit records outputs for the author; it is not final approval.
            review_raw = runtime.review.create(descriptor_raw, hashlib.sha256(archive).hexdigest(), content_date, now=now)
            review_path = runtime.review.review_path(file)
            if review_path in package.inventory(checkout, package.commit(checkout, generated)[0]):
                raise ValueError('Prior patient review requires a separate reviewed retirement')
            runtime.candidate.apply(checkout, {review_path: review_raw}, expected_head=generated)
            git('add', '--', review_path)
            git('commit', '-m', 'Freeze complete patient review: ' + slug)
            review_head = revision(git('rev-parse', 'HEAD').decode().strip())
            review_blob = read_blob(checkout, review_head, review_path)[0]
            runtime.review.load_review(package.GitEvidence(checkout), review_head, file,
                                       expected_source=proof, now=now)
            # Transport source/generated history only. Packaging the original
            # draft history would also export unrelated draft-controlled files.
            # Later validation must fetch the exact still-live author request
            # separately through its trusted, read-only repository transport.
            git('update-ref', GENERATED_REF, generated)
            git('update-ref', REVIEW_REF, review_head)
            bundle_path = temporary / 'objects.bundle'
            git('bundle', 'create', str(bundle_path), GENERATED_REF, REVIEW_REF, '^' + main)
            if bundle_path.stat().st_size > MAX_BUNDLE:
                raise ValueError('Immutable Git transport exceeds its bound')
            bundle = bundle_path.read_bytes()
            git('checkout', '--detach', main)
            replay = rebuild.verify(checkout, archive, main, content_date, now=now, log=build_log)
            unchanged_source(root, main, head, file, refs, status, runtime)
            report = {'version': 1, 'repository': runtime.delivery.REPO, 'file': file,
                      'state': 'awaiting_generated_content_approval', 'pipelineHead': main,
                      'requestHead': head, 'sourceHead': source, 'generatedHead': generated,
                      'reviewHead': review_head, 'reviewPath': review_path, 'reviewBlobSha': review_blob,
                      'reviewManifest': 'review-manifest.json', 'reviewManifestSha256': hashlib.sha256(review_raw).hexdigest(),
                      'generatedTreeSha': descriptor['trackedPackage']['generatedTreeSha'],
                      'contentDate': content_date, 'sourceEvidence': proof,
                      'archive': 'patient-package.zip', 'archiveSha256': hashlib.sha256(archive).hexdigest(),
                      'manifest': 'patient-manifest.json', 'manifestSha256': hashlib.sha256(descriptor_raw).hexdigest(),
                      'objects': 'objects.bundle', 'objectsSha256': hashlib.sha256(bundle).hexdigest(),
                      'bundleRefs': {GENERATED_REF: generated, REVIEW_REF: review_head},
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
                                     'review-manifest.json': review_raw,
                                     'objects.bundle': bundle, 'report.json': package.encode(report)}, still_current, patient)
            return report
    finally:
        if private_log is not None:
            private_log.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--request-head')
    choice.add_argument('--approval-head',help='Exact live final generated-content approval')
    parser.add_argument('--file', required=True)
    parser.add_argument('--expected-main', required=True)
    parser.add_argument('--content-date')
    parser.add_argument('--archive',type=Path,help='Complete archive bound by final approval')
    parser.add_argument('--rebuild-approved-archive',action='store_true',
                        help='Reconstruct the exact already-approved canonical archive from trusted generation')
    args = parser.parse_args()
    if args.approval_head:
        if (args.archive is not None) == args.rebuild_approved_archive or args.content_date is not None:
            parser.error('--approval-head requires exactly one of --archive or --rebuild-approved-archive and uses the approved content date')
        result = prepare_release(args.root,args.output,args.approval_head,args.file,
                                 args.expected_main,args.archive)
    else:
        if args.content_date is None or args.archive is not None or args.rebuild_approved_archive:
            parser.error('--request-head requires --content-date and cannot accept final-archive options')
        result = prepare(args.root, args.output, args.request_head, args.file,
                         args.expected_main, args.content_date)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
