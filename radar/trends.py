"""트렌드 계기판 데이터 — 하루 한 번. "탐님 관심(공급)" vs "시청자 반응(수요)".

키워드마다:
  유튜브(공식 API, 한국 최근 7일): 영상 수, 총조회, 영상당 평균 조회, 댓글 수, 상위 영상
  구글 트렌드(한국): 검색 관심도 90일 추이, 최근 7일 vs 이전 7일 변화
  업계 언급량: 레이더가 모은 글 제목 속 등장 횟수 (지난 24시간)
그리고 지난 24시간 글 제목에서 '새로 등장한 단어'를 뽑는다.
결과: data/trends/YYYY-MM-DD.json (숫자만 계속 쌓음)
"""
import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import http
from .models import Item
from .research import _seconds
from .sources.keyed import _env, _foreign

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "trends"
API = "https://www.googleapis.com/youtube/v3"
CFG = ROOT / "config" / "trends.yaml"


def _load():
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))


# ── 유튜브: 키워드별 시청자 반응 ──
def youtube_demand(query: str) -> dict:
    key = _env("YOUTUBE_API_KEY")
    after = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = http.get(f"{API}/search", params={
        "part": "id", "q": query, "type": "video", "regionCode": "KR", "relevanceLanguage": "ko",
        "order": "viewCount", "publishedAfter": after, "maxResults": 50, "key": key}).json()
    ids = [v["id"]["videoId"] for v in r.get("items", [])]
    total = r.get("pageInfo", {}).get("totalResults", 0)
    vids = []
    if ids:
        r = http.get(f"{API}/videos", params={"part": "snippet,statistics,contentDetails",
                                             "id": ",".join(ids), "key": key}).json()
        for v in r.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            if _foreign(sn["title"]):
                continue
            vids.append({"id": v["id"], "title": sn["title"], "channel": sn["channelTitle"],
                         "date": sn["publishedAt"][:10], "views": int(st.get("viewCount", 0)),
                         "comments": int(st.get("commentCount", 0)), "likes": int(st.get("likeCount", 0)),
                         "shorts": _seconds(v["contentDetails"]["duration"]) <= 180})
    views = [v["views"] for v in vids]
    return {
        "videos_7d": len(vids), "videos_total_estimate": total,
        "views_sum": sum(views), "views_per_video": round(sum(views) / len(views)) if views else 0,
        "median_views": sorted(views)[len(views) // 2] if views else 0,
        "comments_sum": sum(v["comments"] for v in vids),
        "top": sorted(vids, key=lambda v: -v["views"])[:5],
    }


# ── 구글 트렌드(한국): 검색 관심도 ──
def google_trends(terms: list[str], anchor: str) -> dict:
    """5개씩 묶되 매 묶음에 anchor를 넣고, anchor 기준으로 환산해 키워드끼리 비교 가능하게 한다."""
    from pytrends.request import TrendReq
    pt = TrendReq(hl="ko-KR", tz=540, timeout=(10, 25))
    others = [t for t in dict.fromkeys(terms) if t != anchor]
    out, anchor_ref = {}, None
    for i in range(0, len(others), 4):
        batch = [anchor] + others[i:i + 4]
        try:
            pt.build_payload(batch, timeframe="today 3-m", geo="KR")
            df = pt.interest_over_time()
        except Exception as e:
            print(f"  구글 트렌드 실패({type(e).__name__}) — 이 묶음 건너뜀: {batch[1:]}")
            time.sleep(10)
            continue
        if df.empty:
            continue
        a_mean = df[anchor].tail(28).mean() or 1
        anchor_ref = anchor_ref or a_mean
        scale = anchor_ref / a_mean
        for t in batch:
            s = [round(float(x) * scale, 1) for x in df[t].tolist()]
            out[t] = {"series": list(zip([d.strftime("%m-%d") for d in df.index], s))}
        time.sleep(6)   # 비공식 경로라 천천히
    for t, d in out.items():
        vals = [v for _, v in d["series"]]
        last7, prev7 = sum(vals[-7:]) / 7, sum(vals[-14:-7]) / 7
        d["level"] = round(last7, 1)
        d["change"] = round((last7 - prev7) / prev7 * 100) if prev7 else None
        d["series"] = d["series"][-30:]
    return out


# ── 업계 언급량 + 새 단어 (지난 24시간 수집 글) ──
STOP = set("""the and for with from that this your you are how what new now its into about has have will can
is of to in on a an by at as it be or vs ai 뉴스 기사 영상 오늘 공개 발표 출시 위해 통해 대한 관련 이번 지난 위한 있는 하는 했다
한다 밝혔다 진행 기반 지원 확대 강화 개최 선정 체결 협력 시장 서비스 기업 국내 글로벌 플랫폼 기술 활용 도입 운영 개발 제공 대표 사업
show 억원 규모 해외 오픈 tool 이유 최대 최초 가능 결과 공식 정부 올해 내년 &quot; quot amp""".split())


def recent_titles(hours=24) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    titles = {}
    for f in sorted((ROOT / "data" / "scans").glob("*.json")):
        if datetime.strptime(f.stem, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc) < since:
            continue
        for d in json.loads(f.read_text(encoding="utf-8")):
            titles[d["url"]] = d["title"]
    return list(titles.values())


def tokens(title: str) -> set:
    words = re.findall(r"[A-Za-z][A-Za-z0-9.\-]{2,}|[가-힣]{2,}", title)
    return {w.lower().strip(".-") for w in words if w.lower() not in STOP}


def mentions(titles: list[str], aliases: list[str]) -> int:
    al = [a.lower() for a in aliases]
    return sum(1 for t in titles if any(a in t.lower() for a in al))


def new_terms(today: Counter, days=7, min_count=3) -> list[tuple[str, int]]:
    past = Counter()
    for i in range(1, days + 1):
        f = DIR / f"{(datetime.now() - timedelta(days=i)):%Y-%m-%d}.json"
        if f.exists():
            past.update(json.loads(f.read_text(encoding="utf-8")).get("term_counts", {}))
    if not past:   # 비교할 과거가 없으면 '새 단어'는 판단 보류
        return []
    return [(t, n) for t, n in today.most_common(300) if n >= min_count and past.get(t, 0) == 0][:20]


def demand_index(yt: dict, gt: dict | None) -> int:
    """시청자 반응 지수 0~100: 영상당 평균 조회(로그) 50 + 댓글 밀도 20 + 검색 관심 상승 30"""
    v = min(50, 50 * math.log10(1 + yt["views_per_video"]) / 5)       # 영상당 10만 회 ≈ 50
    c = min(20, 20 * math.log10(1 + yt["comments_sum"]) / 4)           # 댓글 1만 개 ≈ 20
    g = 0
    if gt and gt.get("change") is not None:
        g = max(0, min(30, 15 + gt["change"] / 4))                     # 변화 0% = 15, +60% 이상 = 30
    return round(v + c + g)


def collect() -> Path:
    cfg = _load()
    titles = recent_titles()
    term_counts = Counter(t for title in titles for t in tokens(title))
    gt = google_trends([k["gt"] for k in cfg["keywords"]], cfg["anchor"])
    rows = []
    for k in cfg["keywords"]:
        yt = youtube_demand(k["yt"])
        g = gt.get(k["gt"])
        rows.append({"name": k["name"], "star": k["star"], "yt": yt, "gt": g,
                     "media": mentions(titles, k["aliases"]), "demand": demand_index(yt, g)})
        print(f"  {k['name']:<16} 영상 {yt['videos_7d']:>2}개 · 평균 {yt['views_per_video']:>8,}회 · "
              f"검색 {g['level'] if g else '-':>5} ({(g or {}).get('change')}%) · 언급 {rows[-1]['media']}")
    DIR.mkdir(parents=True, exist_ok=True)
    out = DIR / f"{datetime.now():%Y-%m-%d}.json"
    out.write_text(json.dumps({
        "at": datetime.now().strftime("%Y-%m-%d %H:%M"), "titles_24h": len(titles),
        "keywords": rows, "term_counts": dict(term_counts.most_common(2000)),
        "new_terms": new_terms(term_counts), "rising_terms": term_counts.most_common(30),
    }, ensure_ascii=False), encoding="utf-8")
    return out
