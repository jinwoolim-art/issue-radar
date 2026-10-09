"""사용법:
    python -m radar scan       # 출처 전부 스캔 → out/latest.md, out/latest.json
    python -m radar pricing    # 요금 페이지 변경 확인
    python -m radar all        # 둘 다
    python -m radar yt "주제" ["검색어2" ...]   # 유튜브 리서치: 영상 목록 + 자막 → data/research/
    python -m radar yt-retry                    # 차단 등으로 못 받은 자막만 이어 받기 (가장 최근 리서치)
    python -m radar trends                      # 트렌드 계기판: 키워드별 유튜브 반응·검색 관심도·언급량 → out/trends.html
"""
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import logview, metrics, pricing, report, research, site, store
from .score import build_clusters
from .sources import COLLECTORS, MissingKey

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def load_config():
    return yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))


def scan(cfg):
    sources = {s["id"]: s for s in cfg["sources"]}
    items, status = [], {}
    for src in cfg["sources"]:
        if src.get("enabled") is False:   # 설정에서 꺼 둔 출처 (이유는 sources.yaml 주석)
            continue
        try:
            got = COLLECTORS[src["type"]](src)
            items += got
            status[src["name"]] = f"✅{len(got)}"
        except MissingKey as e:
            status[src["name"]] = f"🔑키없음({e})"
        except Exception as e:  # 출처 하나가 깨져도 나머지는 계속
            status[src["name"]] = f"❌{type(e).__name__}"
        print(f"  {src['name']:<16} {status[src['name']]}")

    store.fill_first_seen(items)
    # 로컬 AI 분류 (새 글만, 결과 캐시). Ollama가 꺼져 있으면 규칙 기반으로 그대로 진행
    from . import classify
    lines = classify.classify([{"url": it.url, "title": it.title, "summary": it.summary,
                                "source": sources[it.source]["name"]} for it in items])
    for it in items:
        if it.url in lines:
            it.extra["ai_line"] = lines[it.url]
    print(f"  AI 분류: {len(lines)}/{len(items)}건")
    path = store.save_scan(items)
    prev = store.previous_scan(exclude=path)
    clusters = build_clusters(items, sources, prev)
    md = report.write(clusters, sources, status)
    metrics.record(clusters)
    log = logview.write(items, clusters, sources, status)
    site.deploy()   # 2시간에 한 번까지만 올림
    removed = store.prune()
    print(f"\n수집 {len(items)}건 → 이슈 {len(clusters)}개 → {md}\n로그 페이지 → {log}"
          + (f" (오래된 스캔 {removed}개 삭제)" if removed else ""))


def check_pricing(cfg):
    for page in cfg.get("pricing_pages", []):
        try:
            r = pricing.check(page)
        except Exception as e:
            r = {"name": page["name"], "status": f"error {type(e).__name__}"}
        print(f"  {r['name']:<14} {r['status']}" + (f" ({r.get('chars')}자)" if r.get("chars") else ""))
        for line in r.get("changes", [])[:20]:
            print("     ", line)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "yt":
        if len(sys.argv) < 3:
            sys.exit('사용법: python -m radar yt "주제" ["추가 검색어" ...]')
        topic = sys.argv[2]
        out = research.youtube(topic, queries=[topic] + sys.argv[3:])
        print(f"유튜브 리서치 완료 → {out}/digest.md")
        return
    if cmd == "trends":
        from . import trends, trendview
        print("[트렌드 계기판 수집]")
        out = trends.collect()
        page = trendview.write()
        print(f"→ {out}\n계기판 → {page}")
        site.deploy(force=True)
        return
    if cmd == "shorts":
        from . import shorts
        print("숏폼 샘플 →", shorts.render(sys.argv[2]))
    if cmd == "shorts2":
        from . import shorts_anim
        print("숏폼 샘플(v2 움직임) →", shorts_anim.render(sys.argv[2]))
    if cmd == "story":       # 스토리 영상: 삐빅 탄생기
        from . import story_nativity
        print("스토리 영상 →", story_nativity.render())
    if cmd == "publish":     # 원스톱: 장면표 여러 개 → 영상 렌더링 → 팀 사이트 배포 (휴대폰에서 바로 보기)
        from . import shorts_anim, site
        for spec in sys.argv[2:]:
            print("  렌더링 →", shorts_anim.render(spec).name)
        site.deploy(force=True)
        print("보기: https://p4m-issue-radar.pages.dev/shorts.html")
        return
    if cmd == "deploy":
        site.deploy(force=True)
        return
    if cmd == "yt-retry":
        out = research.retry()
        print(f"→ {out}/digest.md")
        return
    cfg = load_config()
    if cmd in ("scan", "all"):
        print("[이슈 스캔]")
        scan(cfg)
    if cmd in ("pricing", "all"):
        print("\n[요금 페이지]")
        check_pricing(cfg)


if __name__ == "__main__":
    main()
