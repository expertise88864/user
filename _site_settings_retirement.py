"""Separate data-only retirement after exact formal CI/deployment verification.

Keep published author evidence immutable; do not change settings/drafts/refs.
"""
from datetime import datetime, timezone
import re
from _cms_delivery import ImmutableBlobs, github_file, parse, revision, utc
from _cms_retirement import baseline, main_sha, publication_evidence

FILE='.site-settings-delivery.json'
PREFIX='.site-settings-retirements/'
REPO='expertise88864/user'
ARCHIVE=re.compile(r'\.site-settings-retirements/([a-f0-9]{40})\.json\Z')
FIELDS={'version','repository','publishedSha','receiptBlobSha','request','evidence','preparedAt'}


def archives(entries):
    result={}
    for path,entry in entries.items():
        if path==PREFIX[:-1]:
            if entry.get('type')!='tree' or entry.get('mode')!='040000':
                raise ValueError('Malformed settings retirement root')
        elif path.startswith(PREFIX):
            match=ARCHIVE.fullmatch(path)
            if not match or entry.get('type')!='blob' or entry.get('mode')!='100644':
                raise ValueError('Malformed settings retirement archive')
            revision(match[1]);result[path]=revision(entry.get('sha'))
    return result


def optional(api,path,head,limit=16_000):
    return github_file(api,path,head,limit) if path in api.entries(head) else None


def evidence(api,published,candidate,claimed=None):
    _,raw=github_file(api,'_delivery_policy.json',published,32_000)
    policy=parse(raw,limit=32_000)
    if not isinstance(policy,dict) or policy.get('site_settings_author_intent') is not True:
        raise ValueError('Published settings delivery policy missing')
    return publication_evidence(api,published,candidate,claimed)


def verify_transition(candidate,api,current_entry,*,now=None):
    from _site_settings_delivery import receipt
    candidate=revision(candidate);current=main_sha(api);base=baseline(api,candidate,current)
    before=optional(api,FILE,base);old=receipt(before[1]) if before else None
    previous=archives(api.entries(base));after=archives(api.entries(candidate))
    if any(after.get(path)!=sha for path,sha in previous.items()):
        raise ValueError('Immutable settings retirement history was changed')
    added=set(after)-set(previous)
    if old is not None and current_entry is not None and current_entry!=old:
        raise ValueError('Active settings proof requires separate retirement before replacement')
    removed=old is not None and current_entry is None
    if removed or added:
        path=PREFIX+base+'.json'
        if not removed or added!={path}:
            raise ValueError('Settings proof removal requires exact retirement evidence')
        rows=lambda head:{p:(e.get('mode'),e.get('type'),e.get('sha')) for p,e in api.entries(head).items() if e.get('type')!='tree'}
        a,b=rows(base),rows(candidate)
        if {p for p in set(a)|set(b) if a.get(p)!=b.get(p)}!={FILE,path}:
            raise ValueError('Settings retirement must be a separate two-file candidate')
        _,raw=github_file(api,path,candidate,64_000);record=parse(raw,canonical=True,limit=64_000)
        if (not isinstance(record,dict) or set(record)!=FIELDS or type(record['version']) is not int or record['version']!=1
                or record['repository']!=REPO or record['publishedSha']!=base or record['receiptBlobSha']!=before[0]
                or record['request']!=old):
            raise ValueError('Settings retirement does not preserve the exact published request')
        if utc(record['preparedAt'])>(now or datetime.now(timezone.utc)):
            raise ValueError('Settings retirement preparation time is in the future')
        claimed=record['evidence']
        if not isinstance(claimed,dict) or set(claimed)!={'workflows','deploymentId','statusId'}:
            raise ValueError('Settings retirement publication evidence incomplete')
        evidence(api,base,candidate,claimed)
    if main_sha(api)!=current:raise ValueError('Settings main changed during retirement verification')
    return {'retiredRequest':removed,'baseline':base}


def prepare(api,expected_main,*,now=None):
    from _site_settings_delivery import receipt,encoded
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Settings retirement clock requires timezone')
    now=now.astimezone(timezone.utc);expected_main=revision(expected_main);api=ImmutableBlobs(api)
    if main_sha(api)!=expected_main:raise ValueError('Settings retirement main changed')
    before=optional(api,FILE,expected_main);entry=receipt(before[1]) if before else None
    archives(api.entries(expected_main))
    if entry is None:
        if main_sha(api)!=expected_main:raise ValueError('Settings retirement main changed')
        return {}
    path=PREFIX+expected_main+'.json'
    if path in api.entries(expected_main):raise ValueError('Settings retirement archive already exists')
    record={'version':1,'repository':REPO,'publishedSha':expected_main,'receiptBlobSha':before[0],
            'request':entry,'evidence':evidence(api,expected_main,expected_main),
            'preparedAt':now.isoformat(timespec='milliseconds').replace('+00:00','Z')}
    if main_sha(api)!=expected_main:raise ValueError('Settings retirement main changed during preparation')
    return {FILE:encoded({'version':1,'request':None}),path:encoded(record)}
