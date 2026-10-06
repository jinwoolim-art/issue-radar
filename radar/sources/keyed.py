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
