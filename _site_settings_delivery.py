"""Immutable settings extraction and live publication gate. No draft code execution.

An author request is intent, never CI/Preview/production approval. Active proof
cannot be replaced or removed until a separately verified retirement exists.
"""
from __future__ import annotations
import argparse
import hashlib
import json

from _cms_delivery import ImmutableBlobs, ancestor, github_file, parse, revision
from _cms_retirement import baseline, main_sha
from _site_settings_data import catalog_of, exact, parse_json, settings_of, settings_record

FILE = '.site-settings-delivery.json'
REPO = 'expertise88864/user'
SOURCE, CATALOG = '_site_settings.json', 'assets/settings-catalog.json'
BRANCH, MANIFEST, REQUEST = 'cms-settings/site', '.cms-settings/site.json', '.cms-settings-requests/site.json'
FIELDS = {'version', 'repository', 'source', 'requestHead', 'requestBlobSha', 'draftHead', 'manifestBlobSha',
          'baseMain', 'baseSha', 'catalogSha', 'settingsBlobSha', 'preparedAgainst', 'sourceSha256', 'settingsApproved'}
DEFAULT = {'version': 1, 'legacyPicks': True, 'font': {'bodyFont': '', 'headFont': '', 'bodySize': ''}, 'order': [],
           'picks': ['acne-myths', 'sunscreen-myths', 'atopic-dermatitis-overview', 'topical-steroids-guide', 'hairloss-myths']}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf8')


def receipt(raw):
    value = parse(raw, canonical=True, limit=16_000)
    exact(value, ('version', 'request'))
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Invalid site settings proof version')
    entry = value['request']
    if entry is None:
        return None
    exact(entry, FIELDS)
    if type(entry['version']) is not int or entry['version'] != 1 or entry['repository'] != REPO or entry['source'] != SOURCE or entry['settingsApproved'] is not True:
        raise ValueError('Invalid site settings author proof')
    for key in ('requestHead', 'requestBlobSha', 'draftHead', 'manifestBlobSha', 'baseMain', 'baseSha',
                'catalogSha', 'settingsBlobSha', 'preparedAgainst'):
        revision(entry[key])
    digest = entry['sourceSha256']
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('Invalid site settings digest')
    return entry


def optional(api, path, head, limit=32_000):
    if path not in api.entries(head):
        return None
    return github_file(api, path, head, limit)


def live(api, head):
    revision(head)
    ref = api.get('/git/ref/heads/' + BRANCH)
    obj = ref.get('object') if isinstance(ref, dict) else None
    if not isinstance(ref, dict) or ref.get('ref') != 'refs/heads/' + BRANCH or not isinstance(obj, dict) or obj.get('type') != 'commit' or obj.get('sha') != head:
        raise ValueError('Site settings author request was cancelled or superseded')


def payload(api, head, *, prepared_against):
    """Read the complete approved snapshot, including collateral tree checks."""
    revision(head); revision(prepared_against)
    source_sha, source_raw = github_file(api, SOURCE, head, 32_000)
    manifest_sha, manifest_raw = github_file(api, MANIFEST, head, 8_000)
    request_sha, request_raw = github_file(api, REQUEST, head, 8_000)
    manifest = parse(manifest_raw, canonical='compact', limit=8_000)
    exact(manifest, ('version', 'source', 'baseMain', 'baseSha', 'catalogSha', 'blobSha', 'status'))
    if type(manifest['version']) is not int or manifest['version'] != 1 or manifest['source'] != SOURCE or manifest['status'] != 'draft':
        raise ValueError('Invalid site settings manifest')
    for key in ('baseMain', 'baseSha', 'catalogSha', 'blobSha'):
        revision(manifest[key])
    if manifest['blobSha'] != source_sha:
        raise ValueError('Site settings manifest does not bind its source')
    request = parse(request_raw, canonical='compact', limit=8_000)
    exact(request, ('version', 'status', 'branch', 'draftHead', 'blobSha', 'baseMain', 'baseSha', 'catalogSha', 'settingsApproved'))
    if type(request['version']) is not int or request['version'] != 1 or request['status'] != 'requested' or request['branch'] != BRANCH or request['settingsApproved'] is not True:
        raise ValueError('Explicit version-bound site settings approval is required')
    draft = revision(request['draftHead'])
    if any(request[key] != manifest[key] for key in ('blobSha', 'baseMain', 'baseSha', 'catalogSha')):
        raise ValueError('Site settings request does not match its manifest')
    commit = api.get('/git/commits/' + head)
    parents = commit.get('parents') if isinstance(commit, dict) else None
    if not isinstance(commit, dict) or commit.get('sha') != head or not isinstance(parents, list) or len(parents) != 1 or not isinstance(parents[0], dict) or parents[0].get('sha') != draft:
        raise ValueError('Site settings request is not the single child of its draft')
    if github_file(api, SOURCE, draft)[0] != source_sha or github_file(api, MANIFEST, draft, 8_000)[0] != manifest_sha or optional(api, REQUEST, draft, 8_000) is not None:
        raise ValueError('Site settings request changed approved content or reused an older request')
    def non_request(tree):
        return sorted((p, e.get('type'), e.get('mode'), e.get('sha')) for p, e in tree.items() if p != REQUEST and e.get('type') != 'tree')
    if non_request(api.entries(draft)) != non_request(api.entries(head)):
        raise ValueError('Site settings request changed more than its intent')
    base = manifest['baseMain']
    ancestor(api, base, prepared_against)
    ancestor(api, base, draft)
    base_sha, base_raw = github_file(api, SOURCE, base)
    catalog_sha, catalog_raw = github_file(api, CATALOG, base, 200_000)
    if base_sha != manifest['baseSha'] or catalog_sha != manifest['catalogSha']:
        raise ValueError('Site settings baseline blobs do not match the manifest')
    articles = catalog_of(parse_json(catalog_raw, 200_000))
    # The existing source may outlive its original catalogue. Validate its
    # stored grammar; the newly approved source must match this catalogue.
    before = settings_record(parse_json(base_raw))
    settings = settings_of(parse(source_raw, canonical=True, limit=32_000), articles)
    if before['legacyPicks'] is False and settings['legacyPicks'] is True:
        raise ValueError('Source-owned recommendations cannot reactivate legacy KV')
    allowed = {SOURCE, MANIFEST, REQUEST}
    def collateral(tree):
        return sorted((p, e.get('type'), e.get('mode'), e.get('sha')) for p, e in tree.items() if p not in allowed and e.get('type') != 'tree')
    if collateral(api.entries(base)) != collateral(api.entries(head)):
        raise ValueError('Site settings branch contains collateral changes')
    proof = {'version': 1, 'repository': REPO, 'source': SOURCE, 'requestHead': head, 'requestBlobSha': request_sha,
             'draftHead': draft, 'manifestBlobSha': manifest_sha, 'baseMain': base, 'baseSha': base_sha,
             'catalogSha': catalog_sha, 'settingsBlobSha': source_sha, 'preparedAgainst': prepared_against,
             'sourceSha256': hashlib.sha256(source_raw).hexdigest(), 'settingsApproved': True}
    receipt(encoded({'version': 1, 'request': proof}))
    return source_raw, proof


def plan(api, expected_main, request_head):
    """Return only approved data plus receipt. Never merge/execute draft code."""
    api = ImmutableBlobs(api); revision(expected_main); revision(request_head)
    if main_sha(api) != expected_main:
        raise ValueError('Site settings main changed before preparation')
    live(api, request_head)
    existing = optional(api, FILE, expected_main, 16_000)
    if existing is None or receipt(existing[1]) is not None:
        raise ValueError('Site settings preparation requires installed, inactive proof')
    source, proof = payload(api, request_head, prepared_against=expected_main)
    current_source = github_file(api, SOURCE, expected_main)
    current_catalog = github_file(api, CATALOG, expected_main, 200_000)
    if current_source[0] != proof['baseSha'] or current_catalog[0] != proof['catalogSha']:
        raise ValueError('Site settings preparation baseline changed')
    live(api, request_head)
    if main_sha(api) != expected_main:
        raise ValueError('Site settings main changed during preparation')
    return {SOURCE: source, FILE: encoded({'version': 1, 'request': proof})}, proof


def verify(candidate, api):
    """Fail closed on cancellation, payload drift and unapproved settings edits."""
    candidate = revision(candidate); api = ImmutableBlobs(api)
    current = main_sha(api); previous = baseline(api, candidate, current)
    config_sha, config_raw = github_file(api, SOURCE, candidate)
    _, proof_raw = github_file(api, FILE, candidate, 16_000)
    entry = receipt(proof_raw)
    old_config = optional(api, SOURCE, previous)
    old_proof = optional(api, FILE, previous, 16_000)
    old_entry = receipt(old_proof[1]) if old_proof else None
    from _site_settings_retirement import verify_transition
    verify_transition(candidate, api, entry)
    if entry is None:
        if old_config is None:
            articles = catalog_of(parse_json(github_file(api, CATALOG, candidate, 200_000)[1], 200_000))
            if old_proof is not None or settings_of(parse_json(config_raw), articles) != DEFAULT or config_raw != encoded(DEFAULT):
                raise ValueError('Only exact default bootstrap settings may be installed without author intent')
        elif old_proof is None or old_config[0] != config_sha:
            raise ValueError('Site settings changed without an approved request')
    else:
        live(api, entry['requestHead'])
        ancestor(api, entry['preparedAgainst'], candidate)
        source, expected = payload(api, entry['requestHead'], prepared_against=entry['preparedAgainst'])
        if entry != expected or config_sha != entry['settingsBlobSha'] or config_raw != source:
            raise ValueError('Site settings payload/proof differs from its author-approved snapshot')
        if old_entry is None:
            if entry['preparedAgainst'] != previous or not old_config or old_config[0] != entry['baseSha']:
                raise ValueError('New site settings request has a stale preparation baseline')
            if github_file(api, CATALOG, previous, 200_000)[0] != entry['catalogSha']:
                raise ValueError('New site settings request catalogue changed')
        live(api, entry['requestHead'])
    if main_sha(api) != current:
        raise ValueError('Site settings main changed during verification')
    return {'sha': candidate, 'activeRequest': entry is not None, 'authorIntentVerified': True,
            'candidatePayloadVerified': True, 'published': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sha'); args = parser.parse_args()
    from _delivery import API
    print(json.dumps(verify(args.sha, API(REPO)), ensure_ascii=True))


if __name__ == '__main__':
    main()
