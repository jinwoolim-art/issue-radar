"""수집 로그 페이지 — out/log.html. 스캔할 때마다 새로 만든다 (브라우저에서 열어 두면 10분마다 새로고침).

보이는 것: 출처별 상태, 이번 스캔에 들어온 모든 글(걸러진 것 포함), 새 글 표시, 라인·출처 필터, 검색,
오늘 언급량, 요금 페이지 변경 기록, 유튜브 리서치 목록.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Item
from .score import Cluster

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))


def _kst(dt):
    return dt.astimezone(KST).strftime("%m-%d %H:%M") if dt else ""


def _rows(items: list[Item], clusters: list[Cluster], sources: dict) -> list[dict]:
    where = {}
    for rank, cl in enumerate(clusters, 1):
        for it, heat in cl.items:
            where[it.url] = (rank, cl.corner, cl.score)
    fs_path = ROOT / "data" / "first_seen.json"
    first_seen = json.loads(fs_path.read_text(encoding="utf-8")) if fs_path.exists() else {}
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = []
    for it in items:
        rank, corner, score = where.get(it.url, (None, "걸러짐(AI 무관)", 0))
        seen = first_seen.get(it.url)
        rows.append({
            "t": _kst(it.published_at), "ts": it.published_at.timestamp() if it.published_at else 0,
            "src": sources[it.source]["name"], "line": corner, "rank": rank, "score": score,
            "title": it.title, "url": it.url,
            "metric": f"{int(it.metric):,} {it.metric_label}" if it.metric else "",
            "comments": it.comments or "",
            "pub": it.extra.get("publisher") or it.extra.get("channel") or it.extra.get("subreddit") or "",
            "new": bool(seen and datetime.fromisoformat(seen) > day_ago),
        })
    rows.sort(key=lambda r: -r["ts"])
    return rows


def _pricing() -> list[dict]:
    out = []
    for d in sorted((ROOT / "data" / "pricing").glob("*/")):
        snaps = sorted(d.glob("*.txt"))
        if snaps:
            out.append({"id": d.name, "count": len(snaps),
                        "first": snaps[0].stem[:8], "last": snaps[-1].stem[:13].replace("-", " ")})
    return out


def _research() -> list[dict]:
    out = []
    for d in sorted((ROOT / "data" / "research").glob("2*/"), reverse=True):
        meta = d / "meta.json"
        topic = json.loads(meta.read_text(encoding="utf-8"))["topic"] if meta.exists() else d.name
        out.append({"topic": topic, "path": str(d / "digest.md")})
    return out


def write(items: list[Item], clusters: list[Cluster], sources: dict, status: dict) -> Path:
    rows = _rows(items, clusters, sources)
    mfile = ROOT / "data" / "metrics" / f"{datetime.now():%Y-%m-%d}.json"
    mentions = sorted(((k, len(v)) for k, v in json.loads(mfile.read_text(encoding="utf-8")).items()),
                      key=lambda x: -x[1])[:16] if mfile.exists() else []
    data = {"rows": rows, "status": status, "mentions": mentions, "pricing": _pricing(),
            "research": _research(), "at": datetime.now(KST).strftime("%Y-%m-%d %H:%M")}
    out = ROOT / "out" / "log.html"
    out.parent.mkdir(exist_ok=True)
    # <script> 안의 JSON은 HTML로 해석되지 않으므로 '</' 만 끊어 주면 된다 (태그 조기 종료 방지)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out.write_text(PAGE.replace("__DATA__", payload), encoding="utf-8")
    return out


PAGE = r"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>수집 로그</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--mute:#6b6b6b;--line:#e5e5e5;--chip:#f2f2f2;--new:#d9480f;--ok:#2b8a3e;--bad:#c92a2a}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--mute:#9a9a9a;--line:#2e2e2e;--chip:#242424}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,"Apple SD Gothic Neo",sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:16px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:24px 0 8px}
.mute{color:var(--mute)}.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--chip);border-radius:6px;padding:3px 8px;font-size:12px;cursor:pointer;border:1px solid transparent}
.chip.on{border-color:var(--fg)}.ok{color:var(--ok)}.bad{color:var(--bad)}
.bar{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--line);z-index:1}
input{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font-size:14px;margin-bottom:8px}
table{width:100%;border-collapse:collapse}td,th{padding:6px 6px;border-bottom:1px solid var(--line);vertical-align:top;text-align:left}
th{font-size:12px;color:var(--mute);font-weight:500}td.t{white-space:nowrap;color:var(--mute);font-size:12px}
a{color:inherit}.new{color:var(--new);font-weight:600;font-size:11px;margin-right:4px}
.small{font-size:12px;color:var(--mute)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.box{border:1px solid var(--line);border-radius:8px;padding:10px}
@media (max-width:700px){.hide-m{display:none}}
</style></head><body><div class="wrap">
<h1>수집 로그</h1><div class="mute" id="at"></div>
<div class="grid" style="margin-top:12px">
 <div class="box"><b>출처 상태</b><div id="status" class="small"></div></div>
 <div class="box"><b>오늘 언급량 (누적)</b><div id="mentions" class="small"></div></div>
 <div class="box"><b>요금 페이지 감시</b><div id="pricing" class="small"></div><b style="display:block;margin-top:8px">유튜브 리서치</b><div id="research" class="small"></div></div>
</div>
<h2>이번 스캔에 들어온 글 <span class="mute" id="count"></span></h2>
<div class="bar">
 <input id="q" placeholder="제목·출처 검색 (예: 광고, 제미나이, 네이버)">
 <div class="chips" id="newchip"></div><div class="chips" id="lines" style="margin-top:6px"></div><div class="chips" id="srcs" style="margin-top:6px"></div>
</div>
<table><thead><tr><th>시각</th><th>라인</th><th>제목</th><th class="hide-m">출처</th><th class="hide-m">반응</th></tr></thead><tbody id="rows"></tbody></table>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const st={q:'',line:null,src:null,onlyNew:false};
try{Object.assign(st,JSON.parse(decodeURIComponent(location.hash.slice(1))||'{}'))}catch(e){}
const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
$('at').textContent=`마지막 수집 ${D.at} · 이 페이지는 10분마다 새로고침`;
$('status').innerHTML=Object.entries(D.status).map(([k,v])=>`<div>${esc(k)} <span class="${v.startsWith('✅')?'ok':'bad'}">${esc(v)}</span></div>`).join('');
$('mentions').innerHTML=D.mentions.map(([k,n])=>`<div>${esc(k)} <b>${n}</b></div>`).join('')||'아직 없음';
$('pricing').innerHTML=D.pricing.map(p=>`<div>${esc(p.id)}: 스냅샷 ${p.count}개 · 마지막 변경 ${esc(p.last)}</div>`).join('')||'없음';
$('research').innerHTML=D.research.map(r=>`<div>${esc(r.topic)}</div>`).join('')||'없음';
function chips(el,vals,key){el.innerHTML=vals.map(([v,n])=>`<span class="chip ${st[key]===v?'on':''}" data-v="${esc(v)}">${esc(v)} ${n}</span>`).join('');
 el.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{st[key]=st[key]===c.dataset.v?null:c.dataset.v;render()})}
function count(k){const m={};D.rows.forEach(r=>m[r[k]]=(m[r[k]]||0)+1);return Object.entries(m).sort((a,b)=>b[1]-a[1])}
function render(){
 location.replace('#'+encodeURIComponent(JSON.stringify(st)));
 const q=st.q.toLowerCase();
 const rs=D.rows.filter(r=>(!st.line||r.line===st.line)&&(!st.src||r.src===st.src)&&(!st.onlyNew||r.new)&&(!q||(r.title+r.src+r.pub).toLowerCase().includes(q)));
 $('count').textContent=`${rs.length} / ${D.rows.length}건`;
 const nn=D.rows.filter(r=>r.new).length;
 $('newchip').innerHTML=`<span class="chip ${st.onlyNew?'on':''}" id="nc">새 글만 (24시간) ${nn}</span>`;$('nc').onclick=()=>{st.onlyNew=!st.onlyNew;render()};
 chips($('lines'),count('line'),'line');chips($('srcs'),count('src'),'src');
 $('rows').innerHTML=rs.slice(0,800).map(r=>`<tr><td class="t">${esc(r.t)}</td><td class="small">${esc(r.line)}${r.rank?`<br>종합 ${r.rank}위`:''}</td>
 <td>${r.new?'<span class="new">NEW</span>':''}<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>${r.pub?`<div class="small">${esc(r.pub)}</div>`:''}</td>
 <td class="small hide-m">${esc(r.src)}</td><td class="small hide-m">${esc(r.metric)}${r.comments?`<br>댓글 ${r.comments}`:''}</td></tr>`).join('');
}
$('q').value=st.q;$('q').oninput=e=>{st.q=e.target.value;render()};
render();setTimeout(()=>location.reload(),600000);
</script></body></html>"""
