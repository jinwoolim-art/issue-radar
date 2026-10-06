"""요금·프로모션 페이지 변경 감시 (트랙 2).

페이지 본문 텍스트를 날짜별로 저장하고, 직전 저장본과 다르면 바뀐 줄만 뽑아 알린다.
이건 '기록이 쌓여야 의미 있는' 데이터라 7일 삭제 대상이 아니다.
"""
import difflib
import hashlib
import re
from pathlib import Path

from bs4 import BeautifulSoup

from . import http
from .models import now_utc

PRICING = Path(__file__).resolve().parent.parent / "data" / "pricing"


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    lines = (re.sub(r"\s+", " ", l).strip() for l in soup.get_text("\n").splitlines())
    return "\n".join(l for l in lines if l)


def check(page: dict) -> dict:
    if page.get("needs_browser"):
        return {"id": page["id"], "name": page["name"], "status": "skipped", "note": "브라우저 방식 필요(다음 단계)"}
    folder = PRICING / page["id"]
    folder.mkdir(parents=True, exist_ok=True)
    text = page_text(http.get(page["url"]).text)
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    snapshots = sorted(folder.glob("*.txt"))
    prev = snapshots[-1].read_text(encoding="utf-8") if snapshots else None

    if prev is not None and hashlib.sha256(prev.encode()).hexdigest()[:12] == digest:
        return {"id": page["id"], "name": page["name"], "status": "unchanged", "chars": len(text)}

    path = folder / f"{now_utc():%Y%m%d-%H%M%S}.txt"
    path.write_text(text, encoding="utf-8")
    if prev is None:
        return {"id": page["id"], "name": page["name"], "status": "first_snapshot",
                "chars": len(text), "path": str(path)}
    diff = [l for l in difflib.unified_diff(prev.splitlines(), text.splitlines(), lineterm="", n=0)
            if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return {"id": page["id"], "name": page["name"], "status": "changed",
            "changes": diff[:60], "path": str(path)}
