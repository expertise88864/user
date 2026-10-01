"""Trusted-main discovery creates one source-only review bundle, never a release.

No draft checkout/merge/execution, generated assets, queue/ref writes, CI claims,
credentials in artifacts, or production deployment. Only runner temporary output.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error

from _cms_delivery import ImmutableBlobs, revision
from _cms_retirement import main_sha
from _prepare_article_candidate import apply, git
from _site_settings_delivery import BRANCH, FILE, REPO, REQUEST, SOURCE, live, plan

ROOT=Path(__file__).resolve().parent


def source_bundle(root,output,main,request,files):
    with tempfile.TemporaryDirectory(prefix='site-settings-source-',dir=output) as directory:
        temporary=Path(directory).resolve()
        if temporary.parent!=output.resolve() or not temporary.name.startswith('site-settings-source-'):
            raise ValueError('Settings source workspace escaped its output root')
        checkout=temporary/'checkout'
        subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(root),str(checkout)],check=True,capture_output=True)
        git(checkout,'checkout','--detach',main)
        apply(checkout,files,expected_head=main)
        git(checkout,'add','--',SOURCE,FILE)
        git(checkout,'-c','user.name=CMS source preparation','-c','user.email=cms-source@users.noreply.github.com',
            'commit','-m','[settings source prepared] Independent review and complete delivery still required')
        candidate=git(checkout,'rev-parse','HEAD').decode().strip()
        paths=set(git(checkout,'diff','--name-only',main,candidate).decode().splitlines())
        if not paths or not paths<={SOURCE,FILE} or FILE not in paths:
            raise ValueError('Settings source bundle contains unexpected files')
        for path,raw in files.items():
            if git(checkout,'show',candidate+':'+path)!=raw:
                raise ValueError('Settings source bundle changed approved bytes')
        if git(checkout,'rev-parse',candidate+'^').decode().strip()!=main:
            raise ValueError('Settings source bundle is not a single child of current main')
        name='site-settings-'+request+'.bundle'
        git(checkout,'bundle','create',str(output/name),main+'..HEAD')
        git(checkout,'bundle','verify',str(output/name))
        return {'requestHead':request,'preparedAgainst':main,'sourceCommit':candidate,'bundle':name,
                'paths':sorted(paths),'state':'source_prepared','reviewVerified':False,'ciVerified':False,'published':False}


def process(root,output,api):
    root=root.resolve();output=output.resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError('Settings artifacts require a new output directory')
    if git(root,'status','--porcelain','--untracked-files=all').strip():
        raise ValueError('Settings discovery requires clean trusted main')
    main=git(root,'rev-parse','HEAD').decode().strip();refs=git(root,'show-ref')
    if main_sha(api)!=main:
        raise ValueError('Trusted main changed before settings discovery')
    output.mkdir()
    report={'prepared':[],'deferred':[],'reviewVerified':False,'ciVerified':False,'published':False}
    missing=False
    try:
        ref=api.get('/git/ref/heads/'+BRANCH)
    except urllib.error.HTTPError as error:
        if error.code!=404:raise
        missing=True
    if not missing:
        obj=ref.get('object') if isinstance(ref,dict) else None
        if not isinstance(ref,dict) or ref.get('ref')!='refs/heads/'+BRANCH or not isinstance(obj,dict) or obj.get('type')!='commit':
            raise ValueError('Invalid discovered site settings branch identity')
        head=revision(obj.get('sha'))
        # Invalid identity/transport cannot masquerade as a missing request.
        live(api,head)
        if REQUEST not in ImmutableBlobs(api).entries(head):
            report['deferred'].append({'reason':'author_request_required'})
        else:
            try:
                files,proof=plan(api,main,head)
            except (ValueError,UnicodeError,json.JSONDecodeError) as error:
                report['deferred'].append({'requestHead':head,'reason':'request_rejected','errorType':type(error).__name__})
            else:
                # Bundle integrity/engineering failures must fail the job; they
                # are not invalid author requests and must not be uploaded.
                report['prepared'].append(source_bundle(root,output,main,head,files))
    if main_sha(api)!=main or refs!=git(root,'show-ref') or git(root,'status','--porcelain','--untracked-files=all').strip():
        raise ValueError('Trusted main changed during settings discovery')
    for item in report['prepared']:live(api,item['requestHead'])
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='utf8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=REPO or os.environ.get('GITHUB_REF')!='refs/heads/main':
        raise ValueError('Settings discovery runs only in the trusted main repository runner')
    if git(ROOT,'remote','get-url','origin').decode().strip() not in {'https://github.com/'+REPO,'https://github.com/'+REPO+'.git'}:
        raise ValueError('Settings discovery requires the fixed repository origin')
    runner=os.environ.get('RUNNER_TEMP')
    if not runner or args.output.resolve()!=Path(runner).resolve()/'site-settings-source-artifacts':
        raise ValueError('Settings artifacts must use the fixed runner temporary output')
    from _delivery import API
    report=process(ROOT,args.output,API(REPO))
    print(json.dumps({'prepared':len(report['prepared']),'deferred':len(report['deferred']),
                      'reviewVerified':False,'ciVerified':False,'published':False}))


if __name__=='__main__':main()
