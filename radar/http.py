import time

import httpx
from curl_cffi import requests as cffi

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

_client = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"},
                       follow_redirects=True, timeout=20)
_last_hit: dict[str, float] = {}
MIN_INTERVAL = 1.5  # 같은 사이트에 연속 요청할 때 최소 간격(초) — 차단 방지 + 예의
BLOCK_CODES = {403, 429, 503}
CHALLENGE_MARKS = ("Just a moment", "cf-challenge", "Attention Required")


class Response:
    """httpx 응답과 위장 접속(curl_cffi) 응답을 같은 모양으로 감싼다."""

    def __init__(self, status_code, content: bytes, text: str, url: str, via: str):
        self.status_code, self.content, self.text, self.url, self.via = status_code, content, text, url, via

    def json(self):
        import json
        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"{self.status_code} for {self.url}", request=None, response=None)


def _blocked(status: int, text: str) -> bool:
    return status in BLOCK_CODES or any(m in text[:5000] for m in CHALLENGE_MARKS)


def _wait(url):
    host = httpx.URL(url).host
    wait = MIN_INTERVAL - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def get(url, **kw) -> Response:
    """보통 접속 → 봇 차단(403·429·503·챌린지 페이지)이면 진짜 크롬처럼 위장 접속으로 한 번 더.
    로그인·유료 벽은 뚫지 않는다 (공개 페이지만)."""
    _wait(url)
    r = _client.get(url, **kw)
    if not _blocked(r.status_code, r.text):
        r.raise_for_status()
        return Response(r.status_code, r.content, r.text, str(r.url), "httpx")
    c = cffi.get(url, impersonate="chrome", timeout=25, params=kw.get("params"), headers=kw.get("headers"))
    resp = Response(c.status_code, c.content, c.text, str(c.url), "chrome-impersonate")
    if _blocked(c.status_code, c.text):
        raise httpx.HTTPStatusError(f"blocked({c.status_code}) even with impersonation: {url}",
                                    request=None, response=None)
    resp.raise_for_status()
    return resp


def post(url, **kw) -> httpx.Response:
    r = _client.post(url, **kw)
    r.raise_for_status()
    return r


def article_text(url: str) -> str:
    """기사·블로그 원문에서 메뉴·광고를 걷어 낸 본문만 (trafilatura)."""
    import trafilatura
    html = get(url).text
    return trafilatura.extract(html, include_comments=False, include_tables=True, favor_recall=True) or ""
