#!/usr/bin/env python3
import argparse, json, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
DATA=ROOT/'site'/'data'/'programs.json'
STATUS=ROOT/'site'/'data'/'sync_status.json'
sys.path.insert(0,str(HERE))
from scrapers import scrape_url


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--limit',type=int,default=0,help='0이면 전체 프로그램 확인')
    ap.add_argument('--delay',type=float,default=1.0,help='사이트 요청 사이 대기 초')
    args=ap.parse_args()
    programs=json.loads(DATA.read_text(encoding='utf-8'))
    targets=programs[:args.limit] if args.limit else programs
    started=datetime.now(timezone.utc).isoformat()
    changed=errors=checked=0
    for i,x in enumerate(targets,1):
        old=(x.get('status'),x.get('remaining_seats'),x.get('deadline'))
        r=scrape_url(x.get('primary_url',''),timeout=18)
        x.update({
            'status':r['status'], 'remaining_seats':r['remaining_seats'], 'remaining_text':r['remaining_text'],
            'deadline':r['deadline'], 'source_checked_at':r['checked_at'], 'source_http_status':r['http_status'],
            'source_note':r['note'], 'status_confidence':r['confidence']
        })
        new=(x.get('status'),x.get('remaining_seats'),x.get('deadline'))
        changed += old != new
        errors += r['http_status'] is None and r['confidence'] <= .05
        checked += 1
        print(f'[{i}/{len(targets)}] {x.get("title")} -> {r["status"]} / {r["deadline"] or "no deadline"}')
        if i < len(targets): time.sleep(max(0,args.delay))
    finished=datetime.now(timezone.utc).isoformat()
    DATA.write_text(json.dumps(programs,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    STATUS.write_text(json.dumps({'ok':True,'last_sync':{'started_at':started,'finished_at':finished,'checked':checked,'changed':changed,'errors':errors},'note':'GitHub Actions 자동 확인'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checked':checked,'changed':changed,'errors':errors,'finished_at':finished},ensure_ascii=False))

if __name__=='__main__': main()
