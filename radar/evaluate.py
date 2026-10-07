"""정답지(data/golden/labels.json)로 레이더의 라인 분류·이슈 묶기 정확도를 잰다.
분류 규칙이나 AI 분류를 바꿀 때마다 돌려서 숫자로 비교한다. 멈춤 기준: 라인 90%, 묶기 85%."""
import json
from collections import Counter
from pathlib import Path

GOLD = Path(__file__).resolve().parent.parent / "data" / "golden" / "labels.json"


def run(pred_line=None, pred_cluster=None):
    """pred_line/pred_cluster: n → 예측값. 안 주면 정답지 만들 때의 레이더 예측으로 채점."""
    g = json.loads(GOLD.read_text(encoding="utf-8"))
    items = {r["n"]: r for r in g["items"]}
    pl = pred_line or {n: r["pred_line"] for n, r in items.items()}
    pc = pred_cluster or {n: r["pred_cluster"] for n, r in items.items()}
    ok = sum(pl[n] == r["true_line"] for n, r in items.items())
    print(f"라인 분류 정확도: {ok}/{len(items)} = {ok / len(items):.0%}  (기준 90%)")
    by = Counter()
    for n, r in items.items():
        by[(r["true_line"], pl[n] == r["true_line"])] += 1
    for line in sorted({r["true_line"] for r in items.values()}):
        t, f = by[(line, True)], by[(line, False)]
        print(f"   {line:<14} {t}/{t + f}")
    pairs = [(a, b, True) for grp in g["same_issue"] for i, a in enumerate(grp) for b in grp[i + 1:]]
    pairs += [(a, b, False) for grp in g["not_same"] for i, a in enumerate(grp) for b in grp[i + 1:]]
    good = sum((pc[a] == pc[b]) == same for a, b, same in pairs)
    print(f"이슈 묶기 정확도: {good}/{len(pairs)} 쌍 = {good / len(pairs):.0%}  (기준 85%)")
    wrong = [(n, r["title"][:50], pl[n], r["true_line"]) for n, r in items.items() if pl[n] != r["true_line"]]
    print("\n틀린 예 (예측 → 정답):")
    for n, t, p, tr in wrong[:12]:
        print(f"   #{n} {t} | {p} → {tr}")


if __name__ == "__main__":
    run()
