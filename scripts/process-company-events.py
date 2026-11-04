#!/usr/bin/env python3
"""Run explicitly configured company rules on an existing PostgreSQL service.

No migration, rule creation, provider configuration or scheduler installation.
The supplied active account still needs current settings/assistant rights;
each delegated business action independently checks its responsible person.
"""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from core import Problem
from company_event_worker import process


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor-id',required=True)
    parser.add_argument('--request-id',required=True,help='Retain this ID to resume the exact accepted pages.')
    parser.add_argument('--after',default=None)
    parser.add_argument('--page-size',type=int,default=100)
    parser.add_argument('--max-pages',type=int,default=10)
    args=parser.parse_args()
    dsn=os.environ.get('SMARTPLAN_DATABASE_DSN')
    if not dsn: parser.error('SMARTPLAN_DATABASE_DSN must identify the existing configured runtime database.')
    from online.store import PostgresOffice
    office=None
    try:
        office=PostgresOffice(dsn)
        from online.instance import verify_worker
        verify_worker(office)
        result=process(office,dict(id=args.actor_id),request_id=args.request_id,after=args.after,
                       page_size=args.page_size,max_pages=args.max_pages)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0 if result['complete'] else 2
    except Problem as error:
        print(json.dumps(dict(status=error.status,message=error.message),ensure_ascii=False),file=sys.stderr)
        return 1
    except Exception:
        # Connection strings and provider/configuration data must never leak.
        print('Company event worker could not verify completion; inspect the retained run history.',file=sys.stderr)
        return 1
    finally:
        if office is not None: office.db.close()


if __name__=='__main__':raise SystemExit(main())
