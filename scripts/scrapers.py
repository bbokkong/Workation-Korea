import re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime, timezone

UA='Mozilla/5.0 (compatible; WorkationKoreaBot/1.0; +https://example.com/bot)'

ACTIVE_HINTS=['모집중','신청하기','예약하기','참가신청','참가 신청','예약상품정보','신청 프로그램','워케이션 신청 문의','접수중','신청 접수']
PLANNED_HINTS=['모집예정','오픈예정','신청예정','곧 오픈']
CLOSED_HINTS=['모집마감','모집 마감','신청마감','신청 마감','예약마감','예약 마감','접수마감','접수 마감']

DATE_PATTERNS=[
    re.compile(r'(?:신청\s*기간|접수\s*기간|모집\s*기간)[^\d]{0,20}(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})[^~\n]{0,20}[~∼-][^\d]{0,10}(?:(20\d{2})[.\-/년]\s*)?(\d{1,2})[.\-/월]\s*(\d{1,2})'),
    re.compile(r'(?:마감|신청마감|접수마감)[^\d]{0,15}(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})'),
]
SEAT_PATTERNS=[
    re.compile(r'(?:잔여|남은)\s*(?:자리|좌석|인원)?\s*[:：]?\s*(\d{1,4})\s*(?:명|석|자리)?'),
    re.compile(r'(\d{1,4})\s*(?:자리|석)\s*(?:남음|잔여)'),
]

def textify(html):
    soup=BeautifulSoup(html,'html.parser')
    for t in soup(['script','style','noscript']): t.decompose()
    return ' '.join(soup.stripped_strings)

def extract_deadline(text):
    for i,p in enumerate(DATE_PATTERNS):
        m=p.search(text)
        if not m: continue
        g=m.groups()
        if i==0:
            y2=g[3] or g[0]
            return f'{int(y2):04d}-{int(g[4]):02d}-{int(g[5]):02d}'
        return f'{int(g[0]):04d}-{int(g[1]):02d}-{int(g[2]):02d}'
    return None

def extract_remaining(text):
    for p in SEAT_PATTERNS:
        m=p.search(text)
        if m:
            try: return int(m.group(1))
            except: pass
    return None

def classify_status(url,text,http_status):
    host=urlparse(url).netloc.lower()
    low=text.lower()
    # Domain-specific active application pages seen in 2026.
    if 'jb-worcation.com' in host and ('예약상품정보' in text or '신청 프로그램' in text or '얼른 신청하세요' in text):
        return '모집중', .92, '공식 신청/예약 페이지가 활성화되어 있음'
    if 'busaness.com' in host and ('워케이션 신청 문의' in text or 'workation' in low):
        return '모집중', .82, '공식 사이트에서 워케이션 신청 문의 및 운영 정보 확인'
    if http_status and http_status >= 400:
        return '확인필요', .15, f'공식 페이지 HTTP {http_status}'
    if any(k in text for k in CLOSED_HINTS) and not any(k in text for k in ACTIVE_HINTS):
        return '마감', .86, '공식 페이지의 마감 문구 감지'
    if any(k in text for k in PLANNED_HINTS):
        return '모집예정', .84, '공식 페이지의 모집예정 문구 감지'
    if any(k in text for k in ACTIVE_HINTS):
        return '모집중', .80, '공식 페이지의 신청/예약 가능 문구 감지'
    return '확인필요', .35, '명확한 모집 상태 문구를 자동 판별하지 못함'

def scrape_url(url,timeout=16):
    now=datetime.now(timezone.utc).isoformat()
    if not url:
        return dict(status='확인필요',remaining_seats=None,remaining_text='공식 미공개',deadline=None,
                    checked_at=now,http_status=None,note='공식 URL 없음',confidence=0)
    try:
        r=requests.get(url,headers={'User-Agent':UA,'Accept-Language':'ko-KR,ko;q=0.9,en;q=0.6'},timeout=timeout,allow_redirects=True)
        text=textify(r.text[:2500000])
        status,conf,note=classify_status(url,text,r.status_code)
        rem=extract_remaining(text)
        deadline=extract_deadline(text)
        remaining_text=(f'잔여 {rem}명/석' if rem is not None else ('공식 미공개' if status in ('모집중','모집예정') else '확인 필요'))
        return dict(status=status,remaining_seats=rem,remaining_text=remaining_text,deadline=deadline,
                    checked_at=now,http_status=r.status_code,note=note,confidence=conf)
    except Exception as e:
        return dict(status='확인필요',remaining_seats=None,remaining_text='확인 필요',deadline=None,
                    checked_at=now,http_status=None,note=f'접속 오류: {type(e).__name__}',confidence=.05)
