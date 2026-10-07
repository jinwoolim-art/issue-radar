"""B등급 수집기: 무료지만 키/계정이 필요한 출처 (Reddit, YouTube). 키가 없으면 건너뛴다."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import http
from ..models import Item, now_utc


class MissingKey(Exception):
    pass


def _env(name):
    v = os.getenv(name)
    if not v:
        raise MissingKey(name)
    return v


def reddit(src) -> list[Item]:
    cid, secret = _env("REDDIT_CLIENT_ID"), _env("REDDIT_CLIENT_SECRET")
    ua = os.getenv("REDDIT_USER_AGENT", "issue-radar/0.1")
    token = http.post("https://www.reddit.com/api/v1/access_token",
                      auth=(cid, secret), data={"grant_type": "client_credentials"},
                      headers={"User-Agent": ua}).json()["access_token"]
    headers = {"Authorization": f"bearer {token}", "User-Agent": ua}
    cutoff = now_utc() - timedelta(hours=36)
    items = []
    for sub in src["subreddits"]:
        data = http.get(f"https://oauth.reddit.com/r/{sub}/hot?limit={src.get('limit', 25)}",
                        headers=headers).json()
        for c in data["data"]["children"]:
            p = c["data"]
            created = datetime.fromtimestamp(p["created_utc"], timezone.utc)
            if p.get("stickied") or created < cutoff:
                continue
            items.append(Item(
                source=src["id"],
                title=p["title"],
                url=p["url"] if not p.get("is_self") else f"https://www.reddit.com{p['permalink']}",
                published_at=created,
                summary=(p.get("selftext") or "")[:300],
                metric=p.get("score", 0),
                comments=p.get("num_comments", 0),
                metric_label="upvotes",
                extra={"subreddit": sub, "discussion": f"https://www.reddit.com{p['permalink']}"},
            ))
    return items


SEARCH_CACHE = Path(__file__).resolve().parents[2] / "data" / "youtube_search.json"


def _searched_ids(api, key, src) -> list[str]:
    """키워드 검색(최근 24시간). 검색은 1회 100유닛이라 search_every_hours 마다만 하고,
    그 사이에는 지난번에 찾은 영상 목록을 재사용한다 (조회수는 videos 호출로 매번 갱신, 1유닛)."""
    queries = src.get("queries", [])
    cache = json.loads(SEARCH_CACHE.read_text(encoding="utf-8")) if SEARCH_CACHE.exists() else {}
    hours = src.get("search_every_hours", 3)
    if (cache.get("queries") == queries
            and now_utc() - datetime.fromisoformat(cache["at"]) < timedelta(hours=hours)):
        return cache["ids"]
    after = (now_utc() - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = []
    for q in queries:
        r = http.get(f"{api}/search", params={
            "part": "id", "q": q["q"], "type": "video", "order": "viewCount",
            "regionCode": q.get("region", "KR"), "relevanceLanguage": q.get("lang", "ko"),
            "publishedAfter": after, "maxResults": 25, "key": key}).json()
        ids += [v["id"]["videoId"] for v in r.get("items", [])]
    SEARCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SEARCH_CACHE.write_text(json.dumps({"at": now_utc().isoformat(), "queries": queries, "ids": ids}),
                            encoding="utf-8")
    return ids


# 한국어·영어 외 문자(키릴·아랍·태국·힌디, 한글 없는 한자) 제목은 채널 대상이 아니라 제외
_FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ]")
_HAN, _HANGUL = re.compile(r"[一-鿿]"), re.compile(r"[가-힣]")


def _foreign(title: str) -> bool:
    return bool(_FOREIGN.search(title) or (_HAN.search(title) and not _HANGUL.search(title)))


def youtube(src) -> list[Item]:
    key = _env("YOUTUBE_API_KEY")
    api = "https://www.googleapis.com/youtube/v3"
    video_ids = []
    # 인기 급상승(과학기술) — 1유닛
    for region in src.get("regions", ["KR"]):
        r = http.get(f"{api}/videos", params={
            "part": "id", "chart": "mostPopular", "regionCode": region,
            "videoCategoryId": src.get("category_id", "28"), "maxResults": 50, "key": key}).json()
        video_ids += [v["id"] for v in r.get("items", [])]
    video_ids += _searched_ids(api, key, src)
    video_ids = list(dict.fromkeys(video_ids))
    items = []
    for i in range(0, len(video_ids), 50):
        r = http.get(f"{api}/videos", params={
            "part": "snippet,statistics", "id": ",".join(video_ids[i:i + 50]), "key": key}).json()
        for v in r.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            if _foreign(sn["title"]):
                continue
            items.append(Item(
                source=src["id"],
                title=sn["title"],
                url=f"https://www.youtube.com/watch?v={v['id']}",
                published_at=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")),
                summary=sn.get("description", "")[:300],
                metric=int(st.get("viewCount", 0)),
                comments=int(st.get("commentCount", 0)),
                metric_label="views",
                extra={"channel": sn.get("channelTitle"), "video_id": v["id"]},
            ))
    return items


# ── 네이버 (검색 API: 뉴스·블로그·카페글 / 하루 25,000회 무료) ──
NAVER = "https://openapi.naver.com/v1"


def _naver_headers():
    return {"X-Naver-Client-Id": _env("NAVER_CLIENT_ID"), "X-Naver-Client-Secret": _env("NAVER_CLIENT_SECRET")}


def naver_query(kind: str, query: str, display: int = 30, sort: str = "date") -> dict:
    """kind: news | blog | cafearticle. 결과의 total 은 그 검색어의 '전체 언급량' 지표로도 쓴다."""
    return http.get(f"{NAVER}/search/{kind}.json", headers=_naver_headers(),
                    params={"query": query, "display": display, "sort": sort}).json()


def _naver_date(it: dict):
    if it.get("pubDate"):   # 뉴스: RFC 822
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(it["pubDate"]).astimezone(timezone.utc)
    if it.get("postdate"):  # 블로그: yyyymmdd
        return datetime.strptime(it["postdate"], "%Y%m%d").replace(tzinfo=timezone.utc)
    return None


def naver(src) -> list[Item]:
    _naver_headers()   # 키 없으면 MissingKey 로 건너뜀
    clean = lambda s: re.sub(r"<[^>]+>|&quot;|&amp;|&lt;|&gt;", "", s or "")
    items = []
    for q in src["queries"]:
        for kind in src.get("kinds", ["news", "blog", "cafearticle"]):
            data = naver_query(kind, q["q"], display=src.get("per_query", 20))
            for it in data.get("items", []):
                items.append(Item(
                    source=src["id"], title=clean(it["title"]),
                    url=it.get("originallink") or it["link"],
                    published_at=_naver_date(it), summary=clean(it.get("description"))[:300],
                    extra={"line": q.get("line"), "naver_kind": kind, "query": q["q"],
                           "decay_hours": q.get("decay_hours", 36),
                           "publisher": it.get("bloggername") or it.get("cafename") or ""},
                ))
    return items


def naver_datalab(groups: dict[str, list[str]], days: int = 90, unit: str = "week") -> dict:
    """네이버 검색어 트렌드. groups={"ChatGPT 광고": ["챗GPT 광고","ChatGPT 광고"]} →
    {"ChatGPT 광고": [(날짜, 0~100 상대값), ...]}. 최대 5그룹."""
    end = datetime.now().date()
    body = {"startDate": str(end - timedelta(days=days)), "endDate": str(end), "timeUnit": unit,
            "keywordGroups": [{"groupName": g, "keywords": kw[:20]} for g, kw in list(groups.items())[:5]]}
    r = http.post(f"{NAVER}/datalab/search", headers={**_naver_headers(), "Content-Type": "application/json"},
                  json=body).json()
    return {res["title"]: [(d["period"], d["ratio"]) for d in res["data"]] for res in r.get("results", [])}
