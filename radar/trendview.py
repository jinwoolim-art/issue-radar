"""트렌드 계기판 페이지 — out/trends.html. data/trends/*.json 으로 만든다.

① 오늘 분석 규모  ② 관심 vs 반응 4분면  ③ 키워드 비교표(유튜브·검색·언급)
④ 유튜브 인기 영상  ⑤ 많이 나온 단어 / 새로 등장한 단어  ⑥ 반응지수 추이
"""
import html
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "trends"
e = lambda s: html.escape(str(s if s is not None else ""))


def _num(n):
    n = n or 0
    return f"{n / 10000:.1f}만" if n >= 10000 else f"{n:,}"


def _spark(vals, w=110, h=26):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return '<span class="muted">-</span>'
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - 3 - (v - lo) / rng * (h - 6):.1f}" for i, v in enumerate(vals))
    lx, ly = pts.split()[-1].split(",")
    return (f'<svg width="{w}" height="{h}" class="spark" role="img" aria-label="최근 추이">'
            f'<polyline points="{pts}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>'
            f'<circle cx="{lx}" cy="{ly}" r="3" fill="var(--series-1)"/></svg>')


def _change(c):
    if c is None:
        return '<span class="muted">-</span>'
    arrow = "▲" if c > 0 else ("▼" if c < 0 else "–")
    return f'<span class="chg">{arrow} {c:+d}%</span>'


def _verdict(star, demand, cut):
    if star >= 2 and demand >= cut:
        return "✅ 지금 할 것"
    if star < 2 and demand >= cut:
        return "💡 기회 (반응 큼)"
    if star >= 2:
        return "🤔 내 관심만"
    return "⏸ 지켜보기"


def _quadrant(rows, cut):
    W, H, P = 640, 360, 44
    x = lambda s, i: P + (s - 0.5) / 3 * (W - 2 * P) + ((i % 3) - 1) * 26
    y = lambda d: H - P - d / 100 * (H - 2 * P)
    cy, cx = y(cut), P + 1.5 / 3 * (W - 2 * P)
    parts = [f'<svg viewBox="0 0 {W} {H}" class="quad" role="img" aria-label="관심 대비 반응 4분면">',
             f'<line x1="{cx}" y1="{P - 10}" x2="{cx}" y2="{H - P}" class="grid"/>',
             f'<line x1="{P}" y1="{cy}" x2="{W - P + 10}" y2="{cy}" class="grid"/>',
             f'<text x="{W - P}" y="{P}" class="ql" text-anchor="end">✅ 지금 할 것</text>',
             f'<text x="{P + 4}" y="{P}" class="ql">💡 기회 (반응 큼, 내 관심 낮음)</text>',
             f'<text x="{W - P}" y="{H - P - 8}" class="ql" text-anchor="end">🤔 내 관심만</text>',
             f'<text x="{P + 4}" y="{H - P - 8}" class="ql">⏸ 지켜보기</text>',
             f'<text x="{W / 2}" y="{H - 8}" class="axis" text-anchor="middle">탐님 관심 → (★1 지켜보기 · ★2 관심 · ★3 핵심)</text>',
             f'<text x="14" y="{H / 2}" class="axis" transform="rotate(-90 14 {H / 2})" text-anchor="middle">시청자 반응 지수 →</text>']
    for i, r in enumerate(sorted(rows, key=lambda r: (r["star"], -r["demand"]))):
        px, py = x(r["star"], i), y(r["demand"])
        tip = (f'{r["name"]} · 반응 {r["demand"]} · 영상당 평균 {_num(r["yt"]["views_per_video"])}회 · '
               f'7일 영상 {r["yt"]["videos_7d"]}개')
        parts.append(f'<g class="dot"><title>{e(tip)}</title><circle cx="{px:.1f}" cy="{py:.1f}" r="12" fill="transparent"/>'
                     f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="var(--series-1)" stroke="var(--surface)" stroke-width="2"/>'
                     f'<text x="{px + 8:.1f}" y="{py + 4:.1f}" class="dl">{e(r["name"])}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


def write() -> Path:
    files = sorted(DIR.glob("*.json"))
    if not files:
        raise SystemExit("트렌드 데이터가 없습니다. 먼저 `python -m radar trends`")
    today = json.loads(files[-1].read_text(encoding="utf-8"))
    history = [json.loads(f.read_text(encoding="utf-8")) for f in files[-30:]]
    rows = today["keywords"]
    cut = median(r["demand"] for r in rows)
    hist = {r["name"]: [] for r in rows}
    for d in history:
        m = {r["name"]: r["demand"] for r in d["keywords"]}
        for k in hist:
            hist[k].append(m.get(k))
    yt_videos = sum(r["yt"]["videos_7d"] for r in rows)
    yt_views = sum(r["yt"]["views_sum"] for r in rows)
    yt_comments = sum(r["yt"]["comments_sum"] for r in rows)
    gt_n = sum(1 for r in rows if r.get("gt"))

    tiles = [("분석한 키워드", f"{len(rows)}개"), ("유튜브 영상 (최근 7일)", f"{yt_videos:,}개"),
             ("그 영상들의 조회수 합계", _num(yt_views) + "회"), ("댓글", f"{yt_comments:,}개"),
             ("수집 글 (24시간, 37곳)", f"{today['titles_24h']:,}건"), ("구글 검색 관심도", f"{gt_n}개 키워드"),
             ("데이터 누적", f"{len(files)}일째")]

    table = []
    for r in sorted(rows, key=lambda r: -r["demand"]):
        g = r.get("gt") or {}
        top = r["yt"]["top"][0] if r["yt"]["top"] else None
        table.append(f'''<tr><td><b>{e(r["name"])}</b><div class="muted">{"★" * r["star"]}</div></td>
<td><div class="bar"><span style="width:{r["demand"]}%"></span></div><span class="v">{r["demand"]}</span></td>
<td>{_verdict(r["star"], r["demand"], cut)}</td>
<td class="n">{r["yt"]["videos_7d"]}</td><td class="n">{_num(r["yt"]["views_per_video"])}</td>
<td class="n">{_num(r["yt"]["comments_sum"])}</td>
<td>{_spark([v for _, v in g.get("series", [])])}<div class="muted">관심도 {g.get("level", "-")} {_change(g.get("change"))}</div></td>
<td class="n">{r["media"]}</td><td>{_spark(hist[r["name"]])}</td>
<td class="small">{f'<a href="https://www.youtube.com/watch?v={e(top["id"])}" target="_blank" rel="noopener">{e(top["title"][:42])}</a><div class="muted">{e(top["channel"])} · {_num(top["views"])}회</div>' if top else "-"}</td></tr>''')

    vids = {}
    for r in rows:
        for v in r["yt"]["top"]:
            vids.setdefault(v["id"], {**v, "kw": r["name"]})
    vtable = "".join(
        f'<tr><td class="n">{_num(v["views"])}</td><td><a href="https://www.youtube.com/watch?v={e(v["id"])}" target="_blank" rel="noopener">{e(v["title"])}</a>'
        f'<div class="muted">{e(v["channel"])} · {e(v["date"])}{" · 쇼츠" if v.get("shorts") else ""}</div></td>'
        f'<td class="n">{v["comments"]:,}</td><td class="small">{e(v["kw"])}</td></tr>'
        for v in sorted(vids.values(), key=lambda v: -v["views"])[:20])

    words = "".join(f'<span class="chip">{e(t)} <b>{n}</b></span>' for t, n in today["rising_terms"][:30])
    new = ("".join(f'<span class="chip new">{e(t)} <b>{n}</b></span>' for t, n in today["new_terms"])
           or f'<span class="muted">비교할 과거 데이터를 쌓는 중 ({len(files)}/7일). 7일이 지나면 "지난 7일엔 없던 단어"가 여기 뜹니다.</span>')

    page = PAGE.replace("__AT__", e(today["at"])).replace("__TILES__", "".join(
        f'<div class="tile"><div class="muted">{e(k)}</div><div class="big">{e(v)}</div></div>' for k, v in tiles)
    ).replace("__QUAD__", _quadrant(rows, cut)).replace("__ROWS__", "".join(table)).replace(
        "__VIDS__", vtable).replace("__WORDS__", words).replace("__NEW__", new).replace("__CUT__", str(cut))
    out = ROOT / "out" / "trends.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>트렌드 계기판</title>
<style>
:root{color-scheme:light;--surface:#fcfcfb;--fg:#0b0b0b;--muted:#52514e;--line:#e6e5e1;--chip:#f1f0ec;--series-1:#2a78d6}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--surface:#1a1a19;--fg:#fff;--muted:#c3c2b7;--line:#2f2f2d;--chip:#262624;--series-1:#3987e5}}
body{margin:0;background:var(--surface);color:var(--fg);font:14px/1.5 -apple-system,"Apple SD Gothic Neo",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px}h1{font-size:21px;margin:0}h2{font-size:16px;margin:28px 0 6px}
.muted{color:var(--muted);font-size:12px}.small{font-size:12px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:14px}
.tile{border:1px solid var(--line);border-radius:8px;padding:10px}.big{font-size:20px;font-weight:600}
.quad{width:100%;max-width:760px;height:auto}.grid{stroke:var(--line);stroke-width:1}
.ql{fill:var(--muted);font-size:12px}.axis{fill:var(--muted);font-size:11px}.dl{fill:var(--fg);font-size:11px}
.dot:hover .dl{font-weight:700}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:900px}
td,th{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{font-size:12px;color:var(--muted);font-weight:500}td.n{text-align:right;font-variant-numeric:tabular-nums}
.bar{display:inline-block;width:80px;height:8px;background:var(--chip);border-radius:4px;vertical-align:middle;margin-right:6px}
.bar span{display:block;height:8px;background:var(--series-1);border-radius:4px}.v{font-variant-numeric:tabular-nums}
.chg{font-size:12px}.chip{display:inline-block;background:var(--chip);border-radius:6px;padding:3px 8px;margin:3px;font-size:12px}
.chip.new{border:1px solid var(--fg)}a{color:inherit}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted);font-size:12px}
</style></head><body><div class="wrap">
<h1>트렌드 계기판</h1><div class="muted">기준 __AT__ · 매일 아침 갱신 · "탐님 관심" vs "시청자 반응"</div>
<div class="tiles">__TILES__</div>

<h2>① 관심 vs 반응 — 무엇을 만들까</h2>
<div class="muted">가로 = 탐님 관심(★), 세로 = 시청자 반응 지수. 가로선 = 오늘 키워드들의 반응 중간값(__CUT__). 점에 마우스를 올리면 숫자가 보입니다.</div>
__QUAD__
<details><summary>반응 지수는 어떻게 계산하나</summary><div class="small">
0~100. <b>유튜브 영상당 평균 조회</b>(최근 7일, 한국) 50점 + <b>댓글 수</b> 20점 + <b>구글 검색 관심도 변화</b>(최근 7일 vs 이전 7일) 30점.
영상당 평균 조회가 높다 = 사람들이 이 주제 영상을 실제로 본다. 영상 수가 적은데 평균 조회가 높으면 경쟁이 적은 기회.</div></details>

<h2>② 키워드 비교표</h2>
<div class="scroll"><table><thead><tr><th>키워드</th><th>반응 지수</th><th>판정</th><th>유튜브 영상<br>(7일)</th><th>영상당<br>평균 조회</th><th>댓글</th>
<th>구글 검색 관심도<br>(한국 30일)</th><th>업계 언급<br>(24시간)</th><th>반응 추이</th><th>가장 많이 본 영상</th></tr></thead><tbody>__ROWS__</tbody></table></div>

<h2>③ 유튜브 인기 영상 — 시청자가 실제로 본 것 (최근 7일)</h2>
<div class="scroll"><table><thead><tr><th>조회</th><th>영상</th><th>댓글</th><th>키워드</th></tr></thead><tbody>__VIDS__</tbody></table></div>

<h2>④ 🆕 새로 등장한 단어</h2><div>__NEW__</div>
<h2>⑤ 지난 24시간 많이 나온 단어</h2><div>__WORDS__</div>
<p class="muted" style="margin-top:28px">출처: 유튜브 Data API(공식) · 구글 트렌드(한국) · 레이더 수집 37곳(RSS·공식 블로그·커뮤니티). 업계 언급은 "우리가 지켜보는 곳 안에서의 숫자"이며 전국 검색량이 아님.</p>
</div></body></html>"""
