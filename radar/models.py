from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Item:
    """출처 하나에서 가져온 글/영상 한 건. 모든 수집기는 이 형태로 돌려준다."""
    source: str                     # sources.yaml 의 id
    title: str
    url: str
    published_at: datetime | None = None
    summary: str = ""
    metric: float = 0.0             # 반응 수치 (HN 포인트, 깃허브 오늘 스타, 레딧 추천, 유튜브 조회수 등)
    comments: int = 0
    metric_label: str = ""          # "points", "stars today", "views" ...
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        if d.get("published_at"):
            d["published_at"] = datetime.fromisoformat(d["published_at"])
        return cls(**d)


def now_utc():
    return datetime.now(timezone.utc)
