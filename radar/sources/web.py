"""키 없이 되는 A등급 수집기: RSS, Hacker News, Anthropic 뉴스, GitHub 트렌딩."""
import re
import time
from calendar import timegm
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urljoin

import feedparser
from bs4 import BeautifulSoup

from .. import http
from ..models import Item, now_utc


def _clean(html: str, limit=300) -> str:
    text = BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:limit]


def rss(src) -> list[Item]:
    feed = feedparser.parse(http.get(src["url"]).content)
    items = []
    for e in feed.entries[:40]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        items.append(Item(
            source=src["id"],
            title=_clean(e.get("title", ""), 200),
            url=e.get("link", ""),
            published_at=datetime.fromtimestamp(timegm(t), timezone.utc) if t else None,
            summary=_clean(e.get("summary", "")),
        ))
    return items


def gnews(src) -> list[Item]:
    """구글 뉴스 키워드 검색 피드 — 콘텐츠 라인별 키워드 감시.
    키워드가 이미 라인을 정하므로 extra['line'] 에 박아 두고 코너 분류에서 우선한다."""
    items = []
    for q in src["queries"]:
        hl = "hl=ko&gl=KR&ceid=KR:ko" if q.get("lang", "ko") == "ko" else "hl=en-US&gl=US&ceid=US:en"
        url = f"https://news.google.com/rss/search?q={quote(q['q'])}+when:{q.get('days', src.get('days', 3))}d&{hl}"
        for it in rss({"id": src["id"], "url": url})[:src.get("per_query", 15)]:
            title, _, publisher = it.title.rpartition(" - ")
            if any(b.lower() in publisher.lower() for b in src.get("block_publishers", [])):
                continue
            it.title = title or it.title
            it.summary = ""   # 구글 뉴스 요약은 매체 목록이라 쓸모없음
            it.extra = {"line": q["line"], "publisher": publisher, "query": q["q"],
                        "decay_hours": q.get("decay_hours", 36)}
            items.append(it)
    return items


def hackernews(src) -> list[Item]:
    # Algolia HN API: 최근 24시간, 일정 포인트 이상 글을 포인트·댓글수와 함께 한 번에 받는다
    since = int(time.time()) - 24 * 3600
    url = ("https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=100"
           f"&numericFilters=created_at_i>{since},points>{src.get('min_points', 40)}")
    items = []
    for h in http.get(url).json()["hits"]:
        items.append(Item(
            source=src["id"],
            title=h.get("title") or "",
            url=h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
            published_at=datetime.fromtimestamp(h["created_at_i"], timezone.utc),
            metric=h.get("points") or 0,
            comments=h.get("num_comments") or 0,
            metric_label="points",
            extra={"discussion": f"https://news.ycombinator.com/item?id={h['objectID']}"},
        ))
    return items


def anthropic_news(src) -> list[Item]:
    # 목록 페이지에 날짜가 없어서, 처음 발견된 시점을 기준으로 삼는다 (radar.store 의 first_seen)
    soup = BeautifulSoup(http.get(src["url"]).text, "lxml")
    seen, items = set(), []
    for a in soup.select('a[href^="/news/"]'):
        href = a["href"]
        title = a.find(["h2", "h3", "h4"]) or a
        title = title.get_text(" ", strip=True)
        if href in seen or len(title) < 8:
            continue
        seen.add(href)
        items.append(Item(source=src["id"], title=title[:200], url=urljoin(src["url"], href)))
    return items[:30]


def github_trending(src) -> list[Item]:
    soup = BeautifulSoup(http.get(src["url"]).text, "lxml")
    items = []
    for row in soup.select("article.Box-row"):
        link = row.select_one("h2 a")
        if not link:
            continue
        repo = re.sub(r"\s+", "", link.get_text())
        desc = row.select_one("p")
        today = re.search(r"([\d,]+) stars today", row.get_text())
        items.append(Item(
            source=src["id"],
            title=repo,
            url=urljoin("https://github.com", link["href"]),
            published_at=now_utc() - timedelta(hours=12),
            summary=desc.get_text(" ", strip=True) if desc else "",
            metric=int(today.group(1).replace(",", "")) if today else 0,
            metric_label="stars today",
        ))
    return items
