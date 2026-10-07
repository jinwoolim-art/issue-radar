"""가벼운 지표 기록 — 원문은 7일 뒤 지우지만, 키워드·라인별 '하루 언급량' 숫자는 계속 쌓는다.

data/metrics/YYYY-MM-DD.json = {"라인:AI 검색 노출(GEO)": [url, ...], "제품:ChatGPT": [url, ...], ...}
하루 여러 번 스캔해도 같은 글은 한 번만 센다 (url 기준).
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import Item
from .score import Cluster, tag

DIR = Path(__file__).resolve().parent.parent / "data" / "metrics"


def record(clusters: list[Cluster]):
    DIR.mkdir(parents=True, exist_ok=True)
    path = DIR / f"{datetime.now():%Y-%m-%d}.json"
    day = {k: set(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()} if path.exists() else {}
    for cl in clusters:
        for it, _ in cl.items:
            keys = {f"라인:{cl.corner}"}
            p, c = tag(it)
            keys |= {f"제품:{x}" for x in p} | {f"회사:{x}" for x in c}
            for k in keys:
                day.setdefault(k, set()).add(it.url)
    path.write_text(json.dumps({k: sorted(v) for k, v in day.items()}, ensure_ascii=False), encoding="utf-8")


def series(key: str, days: int = 30) -> list[tuple[str, int]]:
    """키 하나의 날짜별 언급량. 예: series("제품:ChatGPT")"""
    out = []
    for i in range(days - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        f = DIR / f"{d}.json"
        if f.exists():
            out.append((d, len(json.loads(f.read_text(encoding="utf-8")).get(key, []))))
    return out
