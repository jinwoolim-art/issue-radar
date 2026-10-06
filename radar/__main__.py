"""사용법:
    python -m radar scan       # 출처 전부 스캔 → out/latest.md, out/latest.json
    python -m radar pricing    # 요금 페이지 변경 확인
    python -m radar all        # 둘 다
"""
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import pricing, report, store
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
    path = store.save_scan(items)
    prev = store.previous_scan(exclude=path)
    clusters = build_clusters(items, sources, prev)
    md = report.write(clusters, sources, status)
    removed = store.prune()
    print(f"\n수집 {len(items)}건 → 이슈 {len(clusters)}개 → {md}"
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
    cfg = load_config()
    if cmd in ("scan", "all"):
        print("[이슈 스캔]")
        scan(cfg)
    if cmd in ("pricing", "all"):
        print("\n[요금 페이지]")
        check_pricing(cfg)


if __name__ == "__main__":
    main()
