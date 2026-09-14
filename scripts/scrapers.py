import re
import unicodedata
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

UA = 'Mozilla/5.0 (compatible; WorkationKoreaBot/2.0; +https://github.com/)'

# 보수적으로 판정한다. '신청하기' 같은 단어가 페이지 어딘가에 있다는 이유만으로
# 현재 모집중으로 확정하지 않는다.
STRONG_ACTIVE = [
    '현재 모집중', '모집 중', '접수중', '접수 중', '신청 가능', '예약 가능',
    '지금 신청', '참가 신청', '참여 신청', '신청하기', '예약하기', '신청서 작성',
]
WEAK_ACTIVE = ['워케이션 신청', '프로그램 신청', '예약상품정보', '신청 프로그램']
PLANNED = ['모집예정', '모집 예정', '오픈예정', '오픈 예정', '신청예정', '신청 예정']
CLOSED = [
    '모집마감', '모집 마감', '신청마감', '신청 마감', '예약마감', '예약 마감',
    '접수마감', '접수 마감', '모집 종료', '신청 종료', '접수 종료', '마감되었습니다',
]

DATE_PATTERNS = [
    # 신청/접수/모집 기간: 시작 ~ 종료
    re.compile(
        r'(?:신청\s*기간|접수\s*기간|모집\s*기간|예약\s*기간)[^\d]{0,30}'
        r'(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})[^~∼\n]{0,30}'
        r'[~∼~-][^\d]{0,12}(?:(20\d{2})[.\-/년]\s*)?(\d{1,2})[.\-/월]\s*(\d{1,2})'
    ),
    # 마감일 단일 표기
    re.compile(
        r'(?:신청\s*마감|접수\s*마감|모집\s*마감|마감일|신청기한)[^\d]{0,20}'
        r'(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})'
    ),
]
SEAT_PATTERNS = [
    re.compile(r'(?:잔여|남은)\s*(?:자리|좌석|인원)?\s*[:：]?\s*(\d{1,4})\s*(?:명|석|자리)?'),
    re.compile(r'(\d{1,4})\s*(?:자리|석)\s*(?:남음|잔여)'),
]


def _norm(s):
    s = unicodedata.normalize('NFKC', s or '')
    return re.sub(r'\s+', ' ', s).strip()


def textify(html):
    soup = BeautifulSoup(html, 'html.parser')
    for t in soup(['script', 'style', 'noscript', 'svg']):
        t.decompose()
    # nav/footer는 전역 CTA 때문에 오탐을 만들기 쉬워 제외
    for t in soup.select('nav, footer'):
        t.decompose()
    return _norm(' '.join(soup.stripped_strings)), soup


def _title_tokens(title):
    stop = {'워케이션', '힐링', '유케이션', '센터', '공유오피스', '프로그램'}
    raw = re.split(r'[\s_()\-–·/]+', _norm(title))
    return [x for x in raw if len(x) >= 2 and x not in stop][:5]


def relevant_context(text, title, radius=1600):
    """프로그램명 근처 문맥을 우선 사용해 다른 프로그램/과거 공지의 문구 오탐을 줄인다."""
    if not title:
        return text[:12000], False
    tokens = _title_tokens(title)
    positions = []
    low = text.lower()
    for token in tokens:
        start = 0
        tk = token.lower()
        while True:
            i = low.find(tk, start)
            if i < 0:
                break
            positions.append(i)
            start = i + len(tk)
            if len(positions) > 12:
                break
    if not positions:
        return text[:12000], False
    chunks = []
    for i in sorted(set(positions))[:8]:
        chunks.append(text[max(0, i-radius): min(len(text), i+radius)])
    return _norm(' '.join(chunks)), True


def extract_deadline(text):
    for idx, p in enumerate(DATE_PATTERNS):
        m = p.search(text)
        if not m:
            continue
        g = m.groups()
        try:
            if idx == 0:
                y2 = g[3] or g[0]
                return f'{int(y2):04d}-{int(g[4]):02d}-{int(g[5]):02d}'
            return f'{int(g[0]):04d}-{int(g[1]):02d}-{int(g[2]):02d}'
        except (TypeError, ValueError):
            pass
    return None


def extract_remaining(text):
    for p in SEAT_PATTERNS:
        m = p.search(text)
        if m:
            try:
                n = int(m.group(1))
                # 수용인원/객실수 등을 잘못 잡는 것을 막기 위한 상한
                if 0 <= n <= 500:
                    return n
            except ValueError:
                pass
    return None


def _deadline_state(deadline):
    if not deadline:
        return None
    try:
        d = date.fromisoformat(deadline)
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return 'past' if d < today else 'future'


def classify_status(url, context, full_text, http_status, title_matched, deadline):
    host = urlparse(url).netloc.lower()

    if http_status and http_status >= 400:
        return '확인필요', 0.10, f'공식 페이지 HTTP {http_status}', False

    future_or_past = _deadline_state(deadline)
    strong = [k for k in STRONG_ACTIVE if k in context]
    weak = [k for k in WEAK_ACTIVE if k in context]
    planned = [k for k in PLANNED if k in context]
    closed = [k for k in CLOSED if k in context]

    # 과거 신청기간이 명시돼 있으면 현재 모집중으로 두지 않는다.
    if future_or_past == 'past' and (closed or any(x in context for x in ['신청 기간', '신청기간', '모집 기간', '모집기간'])):
        return '마감', 0.94, f'공식 페이지의 신청 마감일({deadline})이 지남', True

    if closed and not strong:
        return '마감', 0.91 if title_matched else 0.80, f'프로그램 문맥에서 마감 문구 감지: {closed[0]}', title_matched

    if planned:
        return '모집예정', 0.90 if title_matched else 0.78, f'프로그램 문맥에서 모집예정 문구 감지: {planned[0]}', title_matched

    # 사이트별 보수적 규칙. 모두 프로그램 문맥/CTA가 확인될 때만 확정한다.
    if 'thehyuil.co.kr' in host:
        if title_matched and strong and not closed:
            return '모집중', 0.91, f'더휴일 프로그램 페이지에서 활성 신청 문구 확인: {strong[0]}', True
        return '확인필요', 0.52, '더휴일 페이지는 확인했으나 해당 프로그램의 현재 신청 가능 여부를 확정하지 못함', False

    if 'dearmonday.io' in host:
        if title_matched and (strong or ('예약' in context and '가능' in context)) and not closed:
            return '모집중', 0.90, '디어먼데이 예약 페이지에서 해당 프로그램의 예약 가능 문맥 확인', True
        return '확인필요', 0.50, '디어먼데이 페이지에서 현재 예약 가능 여부를 확정하지 못함', False

    if 'jb-worcation.com' in host:
        if title_matched and (strong or weak) and not closed:
            return '모집중', 0.92, '전북 공식 워케이션 페이지에서 해당 프로그램 신청 문맥 확인', True
        return '확인필요', 0.55, '전북 공식 페이지에서 해당 프로그램 모집 상태를 확정하지 못함', False

    if 'busaness.com' in host:
        if (strong or '워케이션 신청 문의' in context) and not closed:
            return '모집중', 0.90, '부산 공식 워케이션 페이지의 신청/문의 활성 문구 확인', True
        return '확인필요', 0.55, '부산 공식 페이지에서 현재 모집 상태를 확정하지 못함', False

    # 일반 규칙: 프로그램명 문맥 + 강한 활성 신호를 동시에 요구
    if title_matched and strong and not closed:
        return '모집중', 0.88, f'해당 프로그램 문맥에서 신청 가능 문구 확인: {strong[0]}', True

    # 미래 마감일과 신청 관련 약한 신호가 함께 있으면 모집중으로 확정 가능
    if title_matched and future_or_past == 'future' and (strong or weak) and not closed:
        return '모집중', 0.89, f'미래 신청 마감일({deadline})과 신청 문구를 함께 확인', True

    # 프로그램명은 못 찾았지만 공식 페이지에 강한 상태 문구가 있으면 참고만 한다.
    if strong:
        return '확인필요', 0.60, f'신청 문구({strong[0]})는 있으나 해당 프로그램과의 연결을 확정하지 못함', False

    return '확인필요', 0.40 if title_matched else 0.28, '해당 프로그램의 현재 모집 상태를 자동 판별하지 못함', False


def scrape_url(url, title='', provider='', timeout=16):
    now = datetime.now(timezone.utc).isoformat()
    if not url:
        return dict(status='확인필요', remaining_seats=None, remaining_text='공식 미공개', deadline=None,
                    checked_at=now, http_status=None, note='공식 URL 없음', confidence=0.0,
                    verified=False, final_url='')
    try:
        r = requests.get(
            url,
            headers={'User-Agent': UA, 'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.6'},
            timeout=timeout,
            allow_redirects=True,
        )
        # HTML이 아닌 파일/이미지 응답은 판정하지 않음
        ctype = (r.headers.get('content-type') or '').lower()
        if ctype and 'html' not in ctype and 'text/' not in ctype:
            return dict(status='확인필요', remaining_seats=None, remaining_text='확인 필요', deadline=None,
                        checked_at=now, http_status=r.status_code, note=f'HTML 페이지가 아님: {ctype[:40]}',
                        confidence=0.10, verified=False, final_url=r.url)

        text, _ = textify(r.text[:3000000])
        context, title_matched = relevant_context(text, title)
        deadline = extract_deadline(context)
        rem = extract_remaining(context)
        status, conf, note, verified = classify_status(
            r.url or url, context, text, r.status_code, title_matched, deadline
        )
        remaining_text = (
            f'잔여 {rem}명/석' if rem is not None
            else ('공식 미공개' if status in ('모집중', '모집예정') else '확인 필요')
        )
        return dict(
            status=status,
            remaining_seats=rem,
            remaining_text=remaining_text,
            deadline=deadline,
            checked_at=now,
            http_status=r.status_code,
            note=note,
            confidence=conf,
            verified=verified,
            final_url=r.url,
            title_matched=title_matched,
        )
    except Exception as e:
        return dict(status='확인필요', remaining_seats=None, remaining_text='확인 필요', deadline=None,
                    checked_at=now, http_status=None, note=f'접속 오류: {type(e).__name__}', confidence=.05,
                    verified=False, final_url=url, title_matched=False)
