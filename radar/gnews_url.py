"""구글 뉴스 RSS 링크(news.google.com/rss/articles/...) → 원문 기사 주소.

구글 뉴스 링크는 자바스크립트로 원문에 넘어가서 그냥 받으면 빈 페이지다.
기사 페이지에 들어있는 서명(sg)·시각(ts)으로 구글 내부 API(batchexecute)에 원문 주소를 묻는다.
"""
import json
import re
from functools import lru_cache
from urllib.parse import quote

from bs4 import BeautifulSoup

from . import http

_API = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


@lru_cache(maxsize=2048)
def resolve(url: str) -> str:
    m = re.search(r"/articles/([^?/]+)", url)
    if "news.google.com" not in url or not m:
        return url
    art_id = m.group(1)
    page = BeautifulSoup(http.get(f"https://news.google.com/articles/{art_id}").text, "lxml")
    node = page.select_one("[data-n-a-sg][data-n-a-ts]")
    if not node:
        return url
    inner = json.dumps(["garturlreq",
                        [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                         "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                        art_id, int(node["data-n-a-ts"]), node["data-n-a-sg"]], separators=(",", ":"))
    payload = json.dumps([[["Fbv4je", inner, None, "generic"]]], separators=(",", ":"))
    r = http.post(_API, content=f"f.req={quote(payload)}",
                  headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    body = r.text.split("\n\n", 1)[-1]
    return json.loads(json.loads(body)[0][2])[1]
