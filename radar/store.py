"""잠깐 보관소: 스캔 결과는 RETENTION_DAYS 동안만 두고 지운다 (반응 속도 계산용)."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from .models import Item, now_utc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCANS = DATA / "scans"
FIRST_SEEN = DATA / "first_seen.json"
RETENTION_DAYS = 7


def save_scan(items: list[Item]) -> Path:
    SCANS.mkdir(parents=True, exist_ok=True)
    path = SCANS / f"{now_utc():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps([i.to_dict() for i in items], ensure_ascii=False), encoding="utf-8")
    return path


def previous_scan(exclude: Path | None = None) -> dict[str, Item]:
    """직전 스캔을 url → Item 으로. 반응이 얼마나 빨리 늘었는지 비교할 때 쓴다."""
    files = sorted(p for p in SCANS.glob("*.json") if p != exclude) if SCANS.exists() else []
    if not files:
        return {}
    data = json.loads(files[-1].read_text(encoding="utf-8"))
    return {d["url"]: Item.from_dict(d) for d in data}


def fill_first_seen(items: list[Item]):
    """발행일이 없는 항목(Anthropic 뉴스 등)은 처음 발견한 시각을 발행일로 쓴다."""
    seen = json.loads(FIRST_SEEN.read_text(encoding="utf-8")) if FIRST_SEEN.exists() else {}
    now = now_utc().isoformat()
    first_run = not seen
    for it in items:
        if it.url not in seen:
            # 맨 처음 실행 때는 목록 전체가 "새 글"로 보이지 않도록 오래된 것으로 기록
            seen[it.url] = (now_utc() - timedelta(days=30)).isoformat() if first_run else now
        if it.published_at is None:
            it.published_at = datetime.fromisoformat(seen[it.url])
    DATA.mkdir(parents=True, exist_ok=True)
    FIRST_SEEN.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")


def prune():
    cutoff = now_utc() - timedelta(days=RETENTION_DAYS)
    removed = 0
    for p in SCANS.glob("*.json") if SCANS.exists() else []:
        if datetime.strptime(p.stem, "%Y%m%d-%H%M%S").replace(tzinfo=cutoff.tzinfo) < cutoff:
            p.unlink()
            removed += 1
    return removed
