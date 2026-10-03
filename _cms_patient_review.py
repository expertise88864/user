"""Immutable patient-review identity and final author approval, read-only.

Original source approval does not approve generated translations or summaries.
The review manifest freezes every tracked and ignored search output. The final
author request lives on the existing draft branch; it never writes main. These
checks grant no CI or deployment permit. Both publication engines and the author
API must adopt this contract before a generated package can be delivered.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import os
import re

from _cms_delivery import (FILE, HASH, MAX_BYTES, REPO, ImmutableBlobs, ancestor, approved_sources,
                           github_file, parse, receipts, revision, slug_for, utc)

PREFIX = '.cms-review/'
MAX_REVIEW_BYTES = 2_100_000
APPROVAL_FIELDS = {'reviewHead', 'manifestBlobSha', 'manifestSha256', 'approvalHead',
                   'approvalBlobSha', 'approvedAt'}
REQUEST_FIELDS = {'version', 'file', 'sourceRequestHead', 'sourceRequest', 'reviewHead',
                  'manifestBlobSha', 'manifestSha256', 'archiveSha256', 'contentDate',
                  'approvedBy', 'approvedAt', 'contentApproved'}
REVIEW_FIELDS = {'version', 'repository', 'file', 'contentDate', 'archiveSha256', 'patientManifest'}


def review_path(file: str) -> str:
    return PREFIX + slug_for(file) + '.json'


def validate_approval(value: dict, *, now=None) -> dict:
    if not isinstance(value, dict) or set(value) != APPROVAL_FIELDS:
        raise ValueError('Invalid final patient approval identity')
    for key in ('reviewHead', 'manifestBlobSha', 'approvalHead', 'approvalBlobSha'):
        revision(value[key])
    if not isinstance(value['manifestSha256'], str) or not HASH.fullmatch(value['manifestSha256']):
        raise ValueError('Invalid patient manifest digest')
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or utc(value['approvedAt']) > current:
        raise ValueError('Patient approval timestamp is in the future')
    return value


def source_entry(entry: dict) -> dict:
    """An upgrade adds a final approval; the original source witness stays exact."""
    return {key: (1 if key == 'version' else value)
            for key, value in entry.items() if key != 'patientApproval'}


def manifest(raw: bytes, *, now=None) -> dict:
    import _cms_generated_package as tracked
    import _cms_patient_package as patient
    value = parse(raw, canonical=True, limit=MAX_REVIEW_BYTES)
    if (not isinstance(value, dict) or set(value) != REVIEW_FIELDS or
            type(value['version']) is not int or value['version'] != 1 or
            value['repository'] != REPO):
        raise ValueError('Invalid patient review manifest')
    slug_for(value['file'])
    day = value['contentDate']
    if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d\d-\d\d', day) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('Invalid frozen patient content date')
    if not isinstance(value['archiveSha256'], str) or not HASH.fullmatch(value['archiveSha256']):
        raise ValueError('Invalid complete patient archive digest')
    descriptor = value['patientManifest']
    if (not isinstance(descriptor, dict) or set(descriptor) != patient.FIELDS or
            type(descriptor['version']) is not int or descriptor['version'] != 1 or
            descriptor['state'] != 'patient_package_recorded' or
            any(type(descriptor[k]) is not bool or descriptor[k] for k in patient.FALSE_FIELDS)):
        raise ValueError('Patient review requires the unapproved complete package')
    package = descriptor['trackedPackage']
    if (not isinstance(package, dict) or set(package) != tracked.FIELDS or
            type(package['version']) is not int or package['version'] != 1 or
            package['repository'] != REPO or package['file'] != value['file'] or
            package['state'] != 'generated_package_recorded' or
            any(type(package[k]) is not bool or package[k] for k in
                ('generationVerified', 'contentApproved', 'ciVerified', 'published'))):
        raise ValueError('Invalid recorded patient Git package')
    for key in ('pipelineHead', 'sourceHead', 'generatedHead', 'generatedTreeSha'):
        revision(package[key])
    proof = package['sourceEvidence']
    if receipts(tracked.encode({'version': 1, 'requests': [proof]}), now=now) != [proof] or proof['version'] != 1 or proof['file'] != value['file'] or proof['action'] == 'unpublish' or proof['preparedAgainst'] != package['pipelineHead']:
        raise ValueError('Patient review lost its original source approval')
    rows, extra = package['files'], descriptor['extraFiles']
    if (not isinstance(rows, dict) or not rows or not isinstance(extra, dict) or
            'pagefind/pagefind.js' not in extra or set(rows) & set(extra)):
        raise ValueError('Patient review lacks its complete file inventory')
    names = [*rows, *extra]
    patient.unique_paths(names)
    if len(names) > patient.MAX_FILES:
        raise ValueError('Patient review file count exceeds its bound')
    total = 0
    for name, row in {**rows, **extra}.items():
        fields = {'mode', 'blobSha', 'size', 'sha256'} if name in rows else {'size', 'sha256'}
        if (not isinstance(row, dict) or set(row) != fields or
                type(row['size']) is not int or not 0 <= row['size'] <= patient.MAX_BLOB or
                not isinstance(row['sha256'], str) or not HASH.fullmatch(row['sha256'])):
            raise ValueError('Invalid patient output identity')
        if name in rows:
            if name.startswith('pagefind/') or row['mode'] not in {'100644', '100755'}:
                raise ValueError('Invalid patient Git output mode')
            revision(row['blobSha'])
        elif not name.startswith('pagefind/'):
            raise ValueError('Ignored patient output escapes Pagefind')
        total += row['size']
    if total > patient.MAX_TOTAL:
        raise ValueError('Patient review byte count exceeds its bound')
    for name in (value['file'], 'en/' + value['file'], FILE):
        if rows.get(name, {}).get('mode') != '100644':
            raise ValueError('Patient review lacks its Chinese, English or source receipt')
    return value


def encode(value: dict) -> bytes:
    from _cms_generated_package import encode as canonical
    return canonical(value)


def create(descriptor_raw: bytes, archive_sha256: str, content_date: str, *, now=None) -> bytes:
    descriptor = parse(descriptor_raw, canonical=True, limit=2_000_000)
    value = {'version': 1, 'repository': REPO, 'file': descriptor['trackedPackage']['file'],
             'contentDate': content_date, 'archiveSha256': archive_sha256,
             'patientManifest': descriptor}
    raw = encode(value)
    manifest(raw, now=now)
    return raw


def parent(api, head: str, expected: str) -> dict:
    record = api.get('/git/commits/' + revision(head))
    if (not isinstance(record, dict) or record.get('sha') != head or
            [p.get('sha') for p in record.get('parents', [])] != [expected]):
        raise ValueError('Patient history is not the exact direct successor')
    revision(record.get('tree', {}).get('sha'))
    return record


def changed_one(api, before: str, after: str, path: str, blob: str) -> None:
    record = api.get('/compare/' + before + '...' + after)
    if (not isinstance(record, dict) or record.get('status') != 'ahead' or
            record.get('total_commits') != 1 or record.get('merge_base_commit', {}).get('sha') != before or
            [r.get('filename') for r in record.get('files', [])] != [path]):
        raise ValueError('Patient control commit changed other files')
    row = record['files'][0]
    if (row.get('status') not in {'added', 'modified'} or row.get('sha') != blob or
            type(row.get('changes')) is not int or row['changes'] < 1 or 'previous_filename' in row):
        raise ValueError('Patient control diff is not an ordinary intent or manifest')


def leaf_tree(api, head: str) -> dict:
    rows = {name: row for name, row in api.entries(head).items() if row.get('type') != 'tree'}
    import _cms_patient_package as patient
    patient.unique_paths(list(rows))
    if len(rows) > patient.MAX_FILES:
        raise ValueError('Patient Git tree count exceeds its bound')
    if any(row.get('type') != 'blob' or row.get('mode') not in {'100644', '100755'} for row in rows.values()):
        raise ValueError('Patient Git tree contains a link or submodule')
    return rows


def same_entry(left, right):
    return bool(left and right and all(left.get(k) == right.get(k) for k in ('mode', 'type', 'sha')))


def load_review(api, review_head: str, file: str, *, expected_source=None, now=None) -> tuple[dict, str, bytes]:
    """Verify immutable snapshots only. Rebuild and current intent are separate."""
    if not isinstance(api, ImmutableBlobs):
        api = ImmutableBlobs(api)
    review_head = revision(review_head)
    path = review_path(file)
    blob, raw = github_file(api, path, review_head, MAX_REVIEW_BYTES)
    value = manifest(raw, now=now)
    package = value['patientManifest']['trackedPackage']
    proof = package['sourceEvidence']
    if value['file'] != file or expected_source is not None and proof != expected_source:
        raise ValueError('Patient review belongs to another source request')
    parent(api, review_head, package['generatedHead'])
    changed_one(api, package['generatedHead'], review_head, path, blob)
    generated = parent(api, package['generatedHead'], package['sourceHead'])
    if generated['tree']['sha'] != package['generatedTreeSha']:
        raise ValueError('Patient generated tree changed')
    parent(api, package['sourceHead'], package['pipelineHead'])
    tree = leaf_tree(api, package['generatedHead'])
    if set(tree) != set(package['files']) or any(
            tree[name].get('mode') != row['mode'] or tree[name].get('sha') != row['blobSha']
            for name, row in package['files'].items()):
        raise ValueError('Patient review omits or changes an immutable Git output')
    # Executable generator/runtime bytes must already exist unchanged in the
    # approved source tree. A generated package cannot introduce an executable.
    source = leaf_tree(api, package['sourceHead'])
    if any(row['mode'] == '100755' and not same_entry(source.get(name), row) for name, row in tree.items()):
        raise ValueError('Patient generation changed executable files')
    pipeline = leaf_tree(api, package['pipelineHead'])
    changed = {name for name in set(pipeline) | set(source)
               if not same_entry(pipeline.get(name), source.get(name))}
    if FILE not in changed or not changed <= set(proof['sourceSha256']) | {FILE}:
        raise ValueError('Patient source preparation changed unrelated files')
    _, receipt = github_file(api, FILE, package['sourceHead'])
    if receipts(receipt, now=now) != [proof]:
        raise ValueError('Patient review must prepare one active source request')
    approved_sources(api, proof)
    for name, digest in proof['sourceSha256'].items():
        _, content = github_file(api, name, package['sourceHead'], 1_500_000)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('Patient source preparation differs from its approved input')
    if tree.get(FILE, {}).get('sha') != source.get(FILE, {}).get('sha'):
        raise ValueError('Patient generation changed its source approval receipt')
    return value, blob, raw


def expected_request(entry: dict, review: dict) -> dict:
    proof = source_entry(entry)
    approval = entry['patientApproval']
    original = {'version': 1, 'file': proof['file'], 'action': proof['action'],
                'draftHead': proof['draftHead'], 'manifestSha': proof['manifestSha'],
                'blobSha': proof['articleBlobSha'], 'baseSha': proof['baseSha'],
                'approvedBy': proof['approvedBy'], 'contentApproved': True,
                'requestedAt': proof['requestedAt'], 'scheduledAt': proof['scheduledAt']}
    return {'version': 2, 'file': proof['file'], 'sourceRequestHead': proof['requestHead'],
            'sourceRequest': original, 'reviewHead': approval['reviewHead'],
            'manifestBlobSha': approval['manifestBlobSha'], 'manifestSha256': approval['manifestSha256'],
            'archiveSha256': review['archiveSha256'], 'contentDate': review['contentDate'],
            'approvedBy': 'expertise88864', 'approvedAt': approval['approvedAt'], 'contentApproved': True}


def verify_delivery(candidate: str, api, entry: dict, *, now=None) -> dict:
    """Bind final patient approval to every candidate byte and its live request."""
    api = api if isinstance(api, ImmutableBlobs) else ImmutableBlobs(api)
    approval = validate_approval(entry.get('patientApproval'), now=now)
    if entry.get('version') != 2 or entry['action'] == 'unpublish' or utc(approval['approvedAt']) < utc(entry['requestedAt']):
        raise ValueError('Patient approval does not follow its source request')
    review, blob, raw = load_review(api, approval['reviewHead'], entry['file'],
                                   expected_source=source_entry(entry), now=now)
    if blob != approval['manifestBlobSha'] or hashlib.sha256(raw).hexdigest() != approval['manifestSha256']:
        raise ValueError('Final patient review manifest changed')
    request_path = '.cms-requests/' + slug_for(entry['file']) + '.json'
    request_blob, request_raw = github_file(api, request_path, approval['approvalHead'], 8_000)
    expected = expected_request(entry, review)
    request = parse(request_raw, canonical='compact', limit=8_000)
    if (request_blob != approval['approvalBlobSha'] or not isinstance(request, dict) or
            set(request) != REQUEST_FIELDS or type(request.get('version')) is not int or
            type(request.get('contentApproved')) is not bool or request != expected):
        raise ValueError('Patient receipt lost its explicit final author approval')
    parent(api, approval['approvalHead'], entry['requestHead'])
    changed_one(api, entry['requestHead'], approval['approvalHead'], request_path, request_blob)
    ancestor(api, approval['reviewHead'], candidate)
    expected_files = review['patientManifest']['trackedPackage']['files']
    actual = leaf_tree(api, candidate)
    path = review_path(entry['file'])
    controlled = {FILE, path}
    if (set(actual) - controlled != set(expected_files) - controlled or
            actual.get(path, {}).get('mode') != '100644' or actual[path].get('sha') != blob or
            any(actual[name].get('mode') != row['mode'] or actual[name].get('sha') != row['blobSha']
                for name, row in expected_files.items() if name not in controlled)):
        raise ValueError('Candidate differs from the complete approved patient package')
    return review


def verify_workspace(root, sha: str, api, *, now=None) -> dict:
    """Check actual build output, including ignored Pagefind, before deployment."""
    from pathlib import Path
    import _cms_generated_package as tracked
    import _cms_patient_package as patient
    root = Path(root).resolve()
    api = api if isinstance(api, ImmutableBlobs) else ImmutableBlobs(api)
    _, raw = github_file(api, FILE, sha)
    items = receipts(raw, now=now)
    if any(e['action'] != 'unpublish' for e in items) and read_control(root, FILE, MAX_BYTES) != raw:
        raise ValueError('Patient build receipt differs from its immutable candidate')
    count = 0
    for entry in items:
        if entry['action'] == 'unpublish':
            continue
        review = verify_delivery(sha, api, entry, now=now)
        package = review['patientManifest']['trackedPackage']
        path = review_path(entry['file'])
        current_manifest = read_control(root, path, MAX_REVIEW_BYTES)
        approval = entry['patientApproval']
        if hashlib.sha256(current_manifest).hexdigest() != approval['manifestSha256']:
            raise ValueError('Patient build manifest differs from final approval')
        # Git object bytes are immutable and independent of checkout CRLF.
        # Generation drift remains independently blocking in the quality job;
        # additionally compare its real tracked output via Git's normal text
        # attributes without staging or altering the index.
        actual = tracked.inventory(root, tracked.commit(root, sha)[0])
        excluded = {FILE, path}
        if {n: r for n, r in actual.items() if n not in excluded} != {
                n: r for n, r in package['files'].items() if n not in excluded}:
            raise ValueError('Patient manifest raw Git output digests differ')
        if tracked.run(root, 'diff', '--name-only', sha, '--', '.', ':!' + FILE, ':!' + path).strip():
            raise ValueError('Patient tracked build outputs changed after approval')
        if tracked.run(root, 'ls-files', '--others', '--exclude-standard', '-z').strip():
            raise ValueError('Patient build introduced unrecorded files')
        extra = {n: {'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                 for n, content in patient.pagefind_files(root).items()}
        if extra != review['patientManifest']['extraFiles']:
            raise ValueError('Patient ignored search outputs changed after approval')
        count += len(actual) - len(excluded) + len(extra)
    return {'sha': sha, 'patientPackages': len([e for e in items if e['action'] != 'unpublish']),
            'outputFilesVerified': count, 'published': False}


def read_control(root, name, limit):
    """Read one bounded ordinary control file without accepting a replacement."""
    import _cms_patient_package as patient
    path = root / name
    info = path.lstat()
    if (not patient.ordinary(info) or info.st_nlink != 1 or info.st_size > limit or
            path.resolve() != path or not path.is_relative_to(root)):
        raise ValueError('Patient control must be an ordinary bounded file')
    with path.open('rb') as source:
        if patient.identity(os.fstat(source.fileno())) != patient.identity(info):
            raise ValueError('Patient control changed while opening')
        raw = source.read(limit + 1)
        if (len(raw) != info.st_size or patient.identity(os.fstat(source.fileno())) != patient.identity(info) or
                patient.identity(path.lstat()) != patient.identity(info)):
            raise ValueError('Patient control changed while reading')
    return raw


def frozen_content_date(root, *, now=None):
    """Use the recorded Preview date; final approvals retain exact hash binding."""
    from pathlib import Path
    root = Path(root).resolve()
    receipt = root / FILE
    if not os.path.lexists(receipt):
        return None
    receipt_raw = read_control(root, FILE, MAX_BYTES)
    items = receipts(receipt_raw, now=now)
    dates = set()
    for entry in items:
        if entry['action'] == 'unpublish':
            continue
        path = review_path(entry['file'])
        if entry['version'] == 1 and not os.path.lexists(root / path):
            # Source preparation precedes creation of its frozen Preview.
            continue
        raw = read_control(root, path, MAX_REVIEW_BYTES)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if entry['version'] == 2:
            approval = entry['patientApproval']
            if blob != approval['manifestBlobSha'] or hashlib.sha256(raw).hexdigest() != approval['manifestSha256']:
                raise ValueError('Frozen patient manifest differs from final approval')
        value = manifest(raw, now=now)
        if value['file'] != entry['file'] or value['patientManifest']['trackedPackage']['sourceEvidence'] != source_entry(entry):
            raise ValueError('Frozen patient clock belongs to another source request')
        if entry['version'] == 1:
            # A v1 manifest records a reproducible, still-unapproved Preview.
            # It cannot grant publication: immutable Git and actual build bytes
            # are separately verified by the Preview post-build gate, and final
            # delivery still requires the owner's exact v2 approval.
            row = value['patientManifest']['trackedPackage']['files'][FILE]
            receipt_blob = hashlib.sha1(b'blob ' + str(len(receipt_raw)).encode() + b'\0' + receipt_raw).hexdigest()
            if row['blobSha'] != receipt_blob or row['sha256'] != hashlib.sha256(receipt_raw).hexdigest():
                raise ValueError('Frozen Preview receipt differs from its source package')
        dates.add(value['contentDate'])
    if len(dates) > 1:
        raise ValueError('Active patient packages have conflicting frozen dates')
    return next(iter(dates), None)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    from _delivery import API
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, help='exact built candidate SHA')
    args = parser.parse_args()
    print(json.dumps(verify_workspace(Path(__file__).resolve().parent, revision(args.workspace), API(REPO))))
