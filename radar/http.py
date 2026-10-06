import time

import httpx

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")

_client = httpx.Client(headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"},
                       follow_redirects=True, timeout=20)
_last_hit: dict[str, float] = {}
MIN_INTERVAL = 1.5  # 같은 사이트에 연속 요청할 때 최소 간격(초) — 차단 방지 + 예의


def get(url, **kw) -> httpx.Response:
    host = httpx.URL(url).host
    wait = MIN_INTERVAL - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    r = _client.get(url, **kw)
    r.raise_for_status()
    return r


def post(url, **kw) -> httpx.Response:
    r = _client.post(url, **kw)
    r.raise_for_status()
    return r
