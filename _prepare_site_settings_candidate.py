"""Prepare approved settings onto a clean codex candidate; never publish/merge."""
import argparse
import json
from pathlib import Path
from _prepare_article_candidate import apply, git
from _site_settings_delivery import REPO, plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main',required=True);parser.add_argument('--request-head',required=True)
    parser.add_argument('--check',action='store_true',help='Read-only validation; never write candidate files')
    args=parser.parse_args();root=Path(__file__).resolve().parent
    if git(root,'remote','get-url','origin').decode().strip() not in {'https://github.com/'+REPO,'https://github.com/'+REPO+'.git'}:
        raise ValueError('Settings preparation requires the fixed repository origin')
    if not args.check and not git(root,'branch','--show-current').decode().strip().startswith('codex/'):
        raise ValueError('Settings extraction writes only a clean codex candidate')
    from _delivery import API
    files,proof=plan(API(REPO),args.main,args.request_head)
    if not args.check:apply(root,files,expected_head=args.main)
    print(json.dumps({'preparedAgainst':args.main,'requestHead':args.request_head,'paths':sorted(files),
                      'sourcePrepared':not args.check,'authorIntentVerified':True,'ciVerified':False,'published':False}))


if __name__=='__main__':main()
