"""스캔 결과 → 사람이 읽는 Top N 리포트(md) + 다음 단계(브리프·영상 공장)가 읽을 JSON."""
import json
import re
from datetime import timezone, timedelta
from pathlib import Path

import yaml

from .models import now_utc
from .score import Cluster

OUT = Path(__file__).resolve().parent.parent / "out"
KST = timezone(timedelta(hours=9))
_HANGUL = re.compile(r"[가-힣]")
# 탐님 집중 라인(sources.yaml brief_lines)은 10개씩 — 점수보다 사람이 골라야 하는 라인
BRIEF_LINES = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "sources.yaml")
                             .read_text(encoding="utf-8")).get("brief_lines", {})
WATCH_LINES = set(BRIEF_LINES)
_LINE_LABEL = {"active": "✅ 브리프 대상", "hold": "⏸ 보류 후보군 (수집만)"}


def _cluster_json(rank, cl: Cluster, sources):
    items = sorted(cl.items, key=lambda x: -x[1])
    lead = items[0][0]
    ko = next((it for it, _ in items if _HANGUL.search(it.title)), None)
    return {
        "rank": rank,
        "score": cl.score,
        "corner": cl.corner,
        "headline": lead.title,
        "headline_ko": ko.title if ko else None,
        "products": sorted(cl.products),
        "companies": sorted(cl.companies),
        "sources": sorted({sources[it.source]["name"] for it, _ in items}),
        "official": any(sources[it.source].get("official") for it, _ in items),
        "items": [{
            "source": sources[it.source]["name"],
            "title": it.title,
            "url": it.url,
            "published_at": it.published_at.isoformat() if it.published_at else None,
            "metric": it.metric, "metric_label": it.metric_label, "comments": it.comments,
            "discussion": it.extra.get("discussion"),
            "heat": round(h, 1),
        } for it, h in items[:8]],
    }


def write(clusters: list[Cluster], sources: dict, status: dict, top_n=10) -> Path:
    OUT.mkdir(exist_ok=True)
    stamp = now_utc().astimezone(KST)
    data = {
        "generated_at": stamp.isoformat(),
        "channel": "ai",
        "sources_status": status,
        "issues": [_cluster_json(i + 1, cl, sources) for i, cl in enumerate(clusters[:top_n])],
        # 종합 순위에서 밀려도 코너(콘텐츠 라인)마다 후보가 보이도록 코너별 상위 3개를 따로 뽑는다
        "by_corner": {},
    }
    for i, cl in enumerate(clusters):
        picks = data["by_corner"].setdefault(cl.corner, [])
        if len(picks) < (10 if cl.corner in WATCH_LINES else 3):
            picks.append(_cluster_json(i + 1, cl, sources))
    (OUT / f"{stamp:%Y%m%d-%H%M}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# 오늘의 AI 이슈 Top {top_n}", f"_{stamp:%Y-%m-%d %H:%M} KST 기준_", ""]
    for iss in data["issues"]:
        badge = " · 공식발표" if iss["official"] else ""
        lines.append(f"## {iss['rank']}. {iss['headline_ko'] or iss['headline']}")
        if iss["headline_ko"] and iss["headline_ko"] != iss["headline"]:
            lines.append(f"> {iss['headline']}")
        lines.append(f"**뜨는 점수 {iss['score']}** · 코너: {iss['corner']} · 출처 {len(iss['sources'])}곳"
                     f" ({', '.join(iss['sources'])}){badge}")
        if iss["products"] or iss["companies"]:
            lines.append(f"태그: {', '.join(iss['products'] + iss['companies'])}")
        for it in iss["items"][:4]:
            m = f" — {int(it['metric']):,} {it['metric_label']}" if it["metric"] else ""
            c = f", 댓글 {it['comments']:,}" if it["comments"] else ""
            lines.append(f"- [{it['source']}] [{it['title']}]({it['url']}){m}{c}")
        lines.append("")
    lines.append("---")
    lines.append("# 코너별 후보 (집중 라인 10개, 나머지 3개)")
    for corner, picks in data["by_corner"].items():
        label = _LINE_LABEL.get(BRIEF_LINES.get(corner), "")
        lines.append(f"\n### {corner}" + (f" — {label}" if label else ""))
        for iss in picks:
            lead = iss["items"][0]
            lines.append(f"- (종합 {iss['rank']}위 · {iss['score']}점) [{iss['headline_ko'] or iss['headline']}]({lead['url']})"
                         f" — {', '.join(iss['sources'])}")
    lines.append("\n---")
    lines.append("출처 상태: " + " · ".join(f"{k} {v}" for k, v in status.items()))
    md = OUT / "latest.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    return md
