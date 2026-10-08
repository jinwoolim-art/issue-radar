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


def _label_w(text):
    return sum(11 if ord(c) > 0x2000 else 6.5 for c in text)   # 한글은 넓게


def _vclass(star, demand, cut):
    return "go" if star >= 2 and demand >= cut else "opp" if demand >= cut else "mine" if star >= 2 else "wait"


def _quadrant(rows, cut):
    W, H, P = 760, 420, 48
    colw = (W - 2 * P) / 3
    y = lambda d: H - P - d / 100 * (H - 2 * P)
    cy, cx = y(cut), P + 1.5 * colw
    parts = [f'<svg viewBox="0 0 {W} {H}" class="quad" role="img" aria-label="관심 대비 반응 4분면">',
             f'<line x1="{cx}" y1="{P - 10}" x2="{cx}" y2="{H - P}" class="grid"/>',
             f'<line x1="{P}" y1="{cy}" x2="{W - P + 10}" y2="{cy}" class="grid"/>',
             f'<text x="{W - P}" y="{P - 18}" class="ql" text-anchor="end">✅ 지금 할 것</text>',
             f'<text x="{P}" y="{P - 18}" class="ql">💡 기회 (반응 큼, 내 관심 낮음)</text>',
             f'<text x="{W - P}" y="{H - P + 18}" class="ql" text-anchor="end">🤔 내 관심만</text>',
             f'<text x="{P}" y="{H - P + 18}" class="ql">⏸ 지켜보기</text>',
             f'<text x="{W / 2}" y="{H - 6}" class="axis" text-anchor="middle">탐님 관심 → (★1 지켜보기 · ★2 관심 · ★3 핵심)</text>',
             f'<text x="12" y="{H / 2}" class="axis" transform="rotate(-90 12 {H / 2})" text-anchor="middle">시청자 반응 지수 →</text>']
    for s_ in (1, 2, 3):
        parts.append(f'<text x="{P + (s_ - 0.5) * colw}" y="{H - P + 18}" class="axis" text-anchor="middle">{"★" * s_}</text>')
    # 같은 ★ 칸 안에서 반응 순으로 가로로 고르게 벌린다
    pts = []
    for s_ in (1, 2, 3):
        col = sorted([r for r in rows if r["star"] == s_], key=lambda r: -r["demand"])
        for i, r in enumerate(col):
            frac = (i + 0.5) / len(col) if len(col) > 1 else 0.5
            pts.append((r, P + (s_ - 1) * colw + 18 + frac * (colw - 70), y(r["demand"])))
    # 이름표 겹침 피하기: 오른쪽 → 위·아래로 비켜서 → 왼쪽 순으로 시도
    placed = []
    def hit(b):
        return any(not (b[2] < q[0] or b[0] > q[2] or b[3] < q[1] or b[1] > q[3]) for q in placed)
    for r, px, py in sorted(pts, key=lambda t: t[2]):
        placed.append((px - 6, py - 6, px + 6, py + 6))
    labels = []
    for r, px, py in sorted(pts, key=lambda t: t[2]):
        w = _label_w(r["name"])
        for dx, dy, anchor in [(9, 0, "start"), (9, -14, "start"), (9, 14, "start"), (-9, 0, "end"),
                               (-9, -14, "end"), (-9, 14, "end"), (9, -28, "start"), (9, 28, "start")]:
            x0 = px + dx if anchor == "start" else px + dx - w
            box = (x0, py + dy - 10, x0 + w, py + dy + 4)
            if not hit(box) and box[0] > 2 and box[2] < W - 2:
                placed.append(box)
                labels.append((r, px, py, px + dx, py + dy, anchor))
                break
        else:
            labels.append((r, px, py, px + 9, py, "start"))
    for r, px, py, lx, ly, anchor in labels:
        yt = r["yt"]
        data = (f'{r["name"]}|반응 지수 {r["demand"]}|영상당 평균 {_num(yt["views_per_video"])}회|'
                f'최근 7일 영상 {yt["videos_7d"]}개|댓글 {_num(yt["comments_sum"])}개|'
                f'검색 관심도 {(r.get("gt") or {}).get("level", "-")}|업계 언급 {r["media"]}건')
        lead = f'<line x1="{px}" y1="{py}" x2="{lx}" y2="{ly - 4}" class="lead"/>' if abs(ly - py) > 1 else ""
        parts.append(f'<g class="dot" tabindex="0" data-tip="{e(data)}">{lead}'
                     f'<circle cx="{px:.1f}" cy="{py:.1f}" r="14" fill="transparent"/>'
                     f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="var(--series-1)" stroke="var(--surface)" stroke-width="2"/>'
                     f'<text x="{lx:.1f}" y="{ly + 4:.1f}" class="dl" text-anchor="{anchor}">{e(r["name"])}</text></g>')
    parts.append("</svg>")
    return ('<div class="quadwrap"><div class="quadsvg">' + "".join(parts) + '</div>'
            '<aside id="detail" class="detail"><div class="muted">점이나 이름에 마우스를 올리거나 누르면<br>여기에 숫자가 나옵니다.</div></aside></div>')


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
<td><span class="verdict v{_vclass(r["star"], r["demand"], cut)}">{_verdict(r["star"], r["demand"], cut)}</span></td>
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

    g = today.get("general") or {}
    gen = []
    gen.append('<div class="gcol"><div class="ghead">유튜브 한국 인기 급상승 <span class="muted">전 분야</span></div><ol>' + "".join(
        f'<li><a href="https://www.youtube.com/watch?v={e(v["id"])}" target="_blank" rel="noopener">{e(v["title"][:38])}</a>'
        f'<div class="muted">{e(v["category"])} · {_num(v["views"])}회</div></li>' for v in g.get("youtube", [])) +
        "</ol></div>" if g.get("youtube") else '<div class="gcol muted">유튜브 인기: 데이터 없음</div>')
    tt = g.get("tiktok", [])
    gen.append('<div class="gcol"><div class="ghead">틱톡 한국 인기 해시태그 <span class="muted">7일 · 비로그인 공개 범위 상위 3</span></div><ol>' + "".join(
        f'<li><a href="https://www.tiktok.com/tag/{e(t["tag"].lstrip("#"))}" target="_blank" rel="noopener">{e(t["tag"])}</a>'
        f'<div class="muted">{e(t["category"])} · 게시물 {e(t["posts"])} · 조회 {e(t["views"])}</div></li>' for t in tt) +
        '</ol><a class="more" href="https://ads.tiktok.com/creative/creativeCenter/trends/hashtag?region=KR&period=7" target="_blank" rel="noopener">크리에이티브 센터에서 전체 보기 (로그인) →</a></div>'
        if tt else '<div class="gcol muted">틱톡: 데이터 없음</div>')
    gg = g.get("google", [])
    gen.append('<div class="gcol"><div class="ghead">구글 한국 실시간 급상승 <span class="muted">검색량 · 대표 기사</span></div><ol>' + "".join(
        f'<li><b>{e(t["term"])}</b> <span class="pill">{e(t["traffic"])}</span>'
        + (f'<span class="muted"> (+{e(", ".join(t["also"]))})</span>' if t.get("also") else "")
        + "".join(f'<div class="news"><a href="{e(a["url"])}" target="_blank" rel="noopener">{e(a["title"][:46])}</a>'
                  f' <span class="muted">{e(a["source"])}</span></div>' for a in t.get("news", [])[:1])
        + "</li>" for t in gg) + "</ol></div>" if gg else '<div class="gcol muted">구글: 데이터 없음</div>')
    page = PAGE.replace("__GENERAL__", "".join(gen)).replace("__AT__", e(today["at"])).replace("__TILES__", "".join(
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
:root{color-scheme:light;--bg:#f3f3f0;--card:#ffffff;--fg:#0b0b0b;--muted:#5d5c58;--line:#e4e3de;--chip:#f1f0ec;
 --series-1:#2a78d6;--accent:#2a78d6;--accent-soft:#e8f0fb;--head:#1f2a37;--head-fg:#ffffff;--q-go:#eaf2fc}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#121211;--card:#1c1c1b;--fg:#f2f2f0;--muted:#b7b6ad;--line:#2f2f2d;
 --chip:#262624;--series-1:#3987e5;--accent:#3987e5;--accent-soft:#1d2a3b;--head:#0d1620;--head-fg:#f2f2f0;--q-go:#18263a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,"Apple SD Gothic Neo",sans-serif}
.top{background:var(--head);color:var(--head-fg);padding:18px 0 64px}.top .in{max-width:1200px;margin:0 auto;padding:0 16px}
.top h1{font-size:22px;margin:0}.top .sub{opacity:.75;font-size:13px}
.wrap{max-width:1200px;margin:-48px auto 0;padding:0 16px 32px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{background:var(--card);border-radius:10px;padding:12px 14px;border-top:3px solid var(--accent);box-shadow:0 1px 3px rgba(0,0,0,.06)}
.tile .muted{font-size:12px}.big{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums}
.card{background:var(--card);border-radius:12px;padding:16px 18px;margin-top:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card h2{font-size:16px;margin:0 0 4px;display:flex;align-items:center;gap:8px}
.num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:7px;background:var(--accent);color:#fff;font-size:13px}
.desc{color:var(--muted);font-size:12px;margin-bottom:10px}
.muted{color:var(--muted);font-size:12px}.small{font-size:12px}a{color:inherit}a:hover{color:var(--accent)}
.quadwrap{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:14px;align-items:start}
@media (max-width:820px){.quadwrap{grid-template-columns:1fr}}
.quad{width:100%;height:auto}.grid{stroke:var(--line);stroke-width:1.5}
.ql{fill:var(--muted);font-size:12px;font-weight:600}.axis{fill:var(--muted);font-size:11px}.dl{fill:var(--fg);font-size:11px}
.dot{cursor:pointer;outline:none}.dot:hover .dl,.dot:focus .dl,.dot.sel .dl{font-weight:700;fill:var(--accent)}
.dot.sel circle:nth-of-type(2){r:7}.lead{stroke:var(--muted);stroke-width:1}
.detail{position:sticky;top:12px;background:var(--accent-soft);border-radius:10px;padding:14px;min-height:150px;font-size:13px}
.detail h3{margin:0 0 8px;font-size:15px}.detail dl{display:grid;grid-template-columns:auto 1fr;gap:4px 10px;margin:0}
.detail dt{color:var(--muted)}.detail dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums;text-align:right}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:900px}
th{background:var(--chip);font-size:12px;color:var(--muted);font-weight:600;text-align:left;padding:8px 6px;position:sticky;top:0}
td{padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:middle}tbody tr:nth-child(even){background:color-mix(in srgb,var(--chip) 45%,transparent)}
tbody tr:hover{background:var(--accent-soft)}td.n{text-align:right;font-variant-numeric:tabular-nums}
.bar{display:inline-block;width:80px;height:8px;background:var(--chip);border-radius:4px;vertical-align:middle;margin-right:6px}
.bar span{display:block;height:8px;background:var(--series-1);border-radius:4px}.v{font-variant-numeric:tabular-nums;font-weight:600}
.verdict{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;white-space:nowrap;border:1px solid var(--line)}
.verdict.vgo{background:var(--accent-soft);border-color:var(--accent);font-weight:600}
.chg{font-size:12px}.chip{display:inline-block;background:var(--chip);border-radius:6px;padding:3px 8px;margin:3px;font-size:12px}
.chip.new{background:var(--accent-soft);border:1px solid var(--accent)}
.gen{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.gcol{border:1px solid var(--line);border-radius:10px;padding:12px;font-size:13px}
.ghead{font-weight:700;margin-bottom:6px;padding-bottom:6px;border-bottom:1px solid var(--line)}
.gcol ol{margin:6px 0 0;padding-left:20px}.gcol li{margin:6px 0}.news{font-size:12px;margin-top:2px}
.pill{display:inline-block;background:var(--chip);border-radius:999px;padding:0 7px;font-size:11px;color:var(--muted)}
.more{display:inline-block;margin-top:6px;font-size:12px;color:var(--accent)}
details summary{cursor:pointer;color:var(--muted);font-size:12px}
</style></head><body>
<header class="top"><div class="in"><h1>트렌드 계기판</h1><div class="sub">기준 __AT__ · 매일 아침 08:30 갱신 · "탐님 관심" vs "시청자 반응"</div></div></header>
<div class="wrap"><div class="tiles">__TILES__</div>

<section class="card"><h2><span class="num">1</span>관심 vs 반응 — 무엇을 만들까</h2>
<div class="desc">가로 = 탐님 관심(★), 세로 = 시청자 반응 지수. 가로선 = 오늘 키워드들의 반응 중간값(__CUT__). 점이나 이름에 마우스를 올리거나 누르면 숫자가 보입니다.</div>
__QUAD__
<details><summary>반응 지수는 어떻게 계산하나</summary><div class="small">
0~100. <b>유튜브 영상당 평균 조회</b>(최근 7일, 한국) 50점 + <b>댓글 수</b> 20점 + <b>구글 검색 관심도 변화</b>(최근 7일 vs 이전 7일) 30점.
영상당 평균 조회가 높다 = 사람들이 이 주제 영상을 실제로 본다. 영상 수가 적은데 평균 조회가 높으면 경쟁이 적은 기회.</div></details></section>

<section class="card"><h2><span class="num">2</span>키워드 비교표</h2><div class="desc">반응 지수 높은 순. 표 머리글은 스크롤해도 고정.</div>
<div class="scroll"><table><thead><tr><th>키워드</th><th>반응 지수</th><th>판정</th><th>유튜브 영상<br>(7일)</th><th>영상당<br>평균 조회</th><th>댓글</th>
<th>구글 검색 관심도<br>(한국 30일)</th><th>업계 언급<br>(24시간)</th><th>반응 추이</th><th>가장 많이 본 영상</th></tr></thead><tbody>__ROWS__</tbody></table></div></section>

<section class="card"><h2><span class="num">3</span>유튜브 인기 영상 — 시청자가 실제로 본 것 (최근 7일)</h2>
<div class="scroll"><table><thead><tr><th>조회</th><th>영상</th><th>댓글</th><th>키워드</th></tr></thead><tbody>__VIDS__</tbody></table></div></section>

<section class="card"><h2><span class="num">4</span>🆕 새로 등장한 단어</h2><div>__NEW__</div>
<h2 style="margin-top:14px"><span class="num">5</span>지난 24시간 많이 나온 단어</h2><div>__WORDS__</div></section>
<script>
const panel=document.getElementById('detail');
function show(g){document.querySelectorAll('.dot.sel').forEach(x=>x.classList.remove('sel'));g.classList.add('sel');
 const [t,...rest]=g.dataset.tip.split('|');
 panel.innerHTML='<h3>'+t+'</h3><dl>'+rest.map(r=>{const m=r.match(/^(.*?)\s([^\s]+)$/);return m?'<dt>'+m[1]+'</dt><dd>'+m[2]+'</dd>':'<dt>'+r+'</dt><dd></dd>'}).join('')+'</dl>'}
document.querySelectorAll('.dot').forEach(g=>{g.addEventListener('mouseenter',()=>show(g));g.addEventListener('focus',()=>show(g));g.addEventListener('click',()=>show(g))});
</script>
<section class="card"><h2><span class="num">6</span>전체 트렌드 흐름 <span class="muted">(AI 무관 · 참고용)</span></h2>
<div class="gen">__GENERAL__</div></section>
<p class="muted" style="margin-top:28px">출처: 유튜브 Data API(공식) · 구글 트렌드(한국) · 틱톡 크리에이티브 센터(비로그인 공개 화면) · 레이더 수집 37곳(RSS·공식 블로그·커뮤니티). 업계 언급은 "우리가 지켜보는 곳 안에서의 숫자"이며 전국 검색량이 아님.</p>
</div></body></html>"""
