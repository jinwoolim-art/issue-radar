"""전체 트렌드 흐름 (AI 무관, 참고용) — 유튜브 인기 급상승 / 틱톡 인기 해시태그 / 구글 실시간 급상승.
모두 공개 범위만: 유튜브 공식 API, 틱톡 크리에이티브 센터 비로그인 화면(상위 3), 구글 트렌드 공식 RSS.
"""
import re

import feedparser

from . import http
from .sources.keyed import _env

API = "https://www.googleapis.com/youtube/v3"


def youtube_popular(n=10) -> list[dict]:
    key = _env("YOUTUBE_API_KEY")
    cats = {c["id"]: c["snippet"]["title"] for c in http.get(f"{API}/videoCategories", params={
        "part": "snippet", "regionCode": "KR", "hl": "ko", "key": key}).json().get("items", [])}
    r = http.get(f"{API}/videos", params={"part": "snippet,statistics", "chart": "mostPopular",
                                         "regionCode": "KR", "maxResults": n, "key": key}).json()
    return [{"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
             "category": cats.get(v["snippet"].get("categoryId"), ""),
             "views": int(v["statistics"].get("viewCount", 0)), "id": v["id"]} for v in r.get("items", [])]


def tiktok_hashtags() -> list[dict]:
    """비로그인으로 보이는 한국 인기 해시태그(최근 7일). 로그인이 필요한 부분은 열지 않는다."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(locale="ko-KR", viewport={"width": 1280, "height": 1400}, user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"))
        pg = ctx.new_page()
        pg.goto("https://ads.tiktok.com/creative/creativeCenter/trends/hashtag?region=KR&period=7",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(9000)
        body = pg.inner_text("body")
        b.close()
    lines = [l.strip() for l in body.split("\n") if l.strip()]
    num = re.compile(r"^[\d.,]+[KMB]?$")
    out = []
    for i, l in enumerate(lines):
        if l.startswith("#") and len(l) > 1:
            nxt = lines[i + 1:i + 8]
            nums = [x for x in nxt if num.match(x)]
            out.append({"tag": l, "category": nxt[0] if nxt and not num.match(nxt[0]) else "",
                        "posts": nums[0] if nums else "", "views": nums[1] if len(nums) > 1 else ""})
    return out


def google_trending(n=10) -> list[dict]:
    feed = feedparser.parse(http.get("https://trends.google.com/trending/rss?geo=KR").content)
    return [{"term": e.title, "traffic": e.get("ht_approx_traffic", "")} for e in feed.entries[:n]]


def collect() -> dict:
    out = {}
    for name, fn in [("youtube", youtube_popular), ("tiktok", tiktok_hashtags), ("google", google_trending)]:
        try:
            out[name] = fn()
        except Exception as e:   # 하나가 실패해도 계기판은 만든다
            out[name] = []
            print(f"  전체 트렌드 {name} 실패: {type(e).__name__}")
    return out
