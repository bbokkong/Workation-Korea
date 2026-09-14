#!/usr/bin/env python3
import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'site' / 'data' / 'programs.json'
STATUS = ROOT / 'site' / 'data' / 'sync_status.json'
sys.path.insert(0, str(HERE))
from scrapers import scrape_url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='0이면 전체 프로그램 확인')
    ap.add_argument('--delay', type=float, default=1.0, help='사이트 요청 사이 대기 초')
    args = ap.parse_args()

    programs = json.loads(DATA.read_text(encoding='utf-8'))
    targets = programs[:args.limit] if args.limit else programs
    started = datetime.now(timezone.utc).isoformat()
    changed = errors = checked = verified_count = 0
    counts = Counter()

    for i, x in enumerate(targets, 1):
        old = (x.get('status'), x.get('remaining_seats'), x.get('deadline'), x.get('status_verified'))
        r = scrape_url(
            x.get('primary_url', ''),
            title=x.get('title', ''),
            provider=x.get('provider', ''),
            timeout=18,
        )
        x.update({
            'status': r['status'],
            'status_verified': bool(r.get('verified')),
            'remaining_seats': r['remaining_seats'],
            'remaining_text': r['remaining_text'],
            'deadline': r['deadline'],
            'source_checked_at': r['checked_at'],
            'source_http_status': r['http_status'],
            'source_final_url': r.get('final_url') or x.get('primary_url', ''),
            'source_note': r['note'],
            'status_confidence': r['confidence'],
            'source_title_matched': bool(r.get('title_matched')),
        })
        new = (x.get('status'), x.get('remaining_seats'), x.get('deadline'), x.get('status_verified'))
        changed += old != new
        errors += r['http_status'] is None and r['confidence'] <= .05
        checked += 1
        verified_count += bool(r.get('verified'))
        counts[r['status']] += 1
        flag = '✓확정' if r.get('verified') else '△참고'
        print(f'[{i}/{len(targets)}] {x.get("title")} -> {r["status"]} {flag} / {r["deadline"] or "no deadline"}')
        if i < len(targets):
            time.sleep(max(0, args.delay))

    finished = datetime.now(timezone.utc).isoformat()
    DATA.write_text(json.dumps(programs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {
        'ok': True,
        'last_sync': {
            'started_at': started,
            'finished_at': finished,
            'checked': checked,
            'changed': changed,
            'errors': errors,
            'verified': verified_count,
            'status_counts': dict(counts),
        },
        'note': 'GitHub Actions 자동 확인 · 보수적 모집상태 판정 v2',
    }
    STATUS.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary['last_sync'], ensure_ascii=False))


if __name__ == '__main__':
    main()
