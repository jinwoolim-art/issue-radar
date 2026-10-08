"""장면표(JSON) → 세로 숏폼 영상(러프). 무료: 장면 카드 이미지 + 맥 내장 한국어 음성 + ffmpeg.

장면 종류(type): hook / compare / price / checklist / warning / outro / steps / stat / quote
나중에 그래픽을 올릴 때는 같은 장면표를 유료 영상 AI나 영상 공장에 넘기면 된다 (장면표가 '프롬프트 정의'의 뼈대).
사용: python -m radar shorts briefs/shorts/파일.json → out/shorts/파일.mp4
"""
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "shorts"
W, H, FPS = 1080, 1920, 30
e = lambda s: html.escape(str(s).replace("**", "")).replace("\n", "<br>")   # v2 강조 표시(**)는 v1에선 지움

CSS = """
:root{--bg:#10151c;--panel:#18202b;--fg:#f4f6f8;--muted:#9aa7b4;--accent:#5ab0ff;--hot:#ffd166;--bad:#ff7a6b;--good:#7bd88f}
*{box-sizing:border-box;margin:0}
body{width:1080px;height:1920px;background:radial-gradient(1200px 900px at 80% 10%,#1d2a3a 0,var(--bg) 60%);color:var(--fg);
 font-family:"Apple SD Gothic Neo","Noto Sans KR",sans-serif;overflow:hidden;position:relative;word-break:keep-all}
.top{position:absolute;top:120px;left:80px;right:160px;display:flex;align-items:center;gap:18px}
.kicker{background:var(--accent);color:#08111b;font-weight:800;font-size:38px;padding:10px 26px;border-radius:999px}
.dots{margin-left:auto;display:flex;gap:10px}.dots i{width:16px;height:16px;border-radius:50%;background:#33404f}.dots i.on{background:var(--fg)}
.stage{position:absolute;top:260px;left:80px;right:160px;height:880px;display:flex;flex-direction:column;justify-content:center;gap:34px}
.cap{position:absolute;top:1180px;left:70px;right:150px;background:rgba(0,0,0,.55);border-radius:28px;padding:30px 36px;
 font-size:50px;line-height:1.38;font-weight:700;text-wrap:balance}
.tag{position:absolute;bottom:90px;left:80px;font-size:28px;color:var(--muted)}
.big{font-size:330px;font-weight:900;letter-spacing:-8px;color:var(--hot);line-height:1}
.h{font-size:86px;font-weight:900;line-height:1.2;letter-spacing:-2px}
.card{background:var(--panel);border-radius:32px;padding:38px 40px}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.cmp{gap:22px}.cmp .card{padding:44px 30px}.cmp .lab{font-size:40px;color:var(--muted);margin-bottom:26px}.cmp .row{font-size:62px;font-weight:900;margin:14px 0}
.cmp .after{outline:5px solid var(--bad)}
.plan{font-size:46px;color:var(--muted)}.was{font-size:90px;color:var(--muted);text-decoration:line-through;text-decoration-thickness:8px}
.now{font-size:170px;font-weight:900;color:var(--hot);letter-spacing:-4px;line-height:1}
.badge{display:inline-block;background:var(--hot);color:#1a1300;font-weight:900;font-size:46px;padding:12px 28px;border-radius:18px}
.note{font-size:42px;color:var(--muted)}
.grp .gl{font-size:44px;font-weight:900;margin-bottom:16px}.grp .gl.ok{color:var(--good)}.grp .gl.maybe{color:var(--hot)}
.grp li{font-size:48px;margin:12px 0 12px 44px}
.warn{border:6px solid var(--hot)}.warn li{font-size:54px;font-weight:800;margin:18px 0 18px 50px}
.dt{display:flex;align-items:baseline;gap:30px;margin:14px 0}.dt b{font-size:130px;color:var(--hot);font-weight:900;letter-spacing:-3px;min-width:330px}
.dt span{font-size:50px;font-weight:700}
.big.mid{font-size:190px;letter-spacing:-4px}.big.sm{font-size:130px;letter-spacing:-2px}
.step{display:flex;gap:28px;align-items:flex-start;margin:6px 0}.step b{flex:none;width:92px;height:92px;border-radius:50%;background:var(--accent);
 color:#08111b;font-size:52px;font-weight:900;display:flex;align-items:center;justify-content:center}.step span{font-size:52px;font-weight:800;line-height:1.3;padding-top:12px}
.stat{font-size:200px;font-weight:900;color:var(--hot);letter-spacing:-5px;line-height:1}.stat.mid{font-size:140px}
.statl{font-size:56px;font-weight:800;line-height:1.3}.src{font-size:36px;color:var(--muted)}
.quote{border-left:14px solid var(--accent);padding:10px 0 10px 40px;font-size:60px;font-weight:800;line-height:1.35}
.qsrc{font-size:38px;color:var(--muted)}
.cmp .row.sm{font-size:46px;font-weight:700}
"""


def _scene_html(sc: dict, i: int, n: int, title: str) -> str:
    t = sc["type"]
    if t == "hook":
        size = "" if len(sc["big"]) <= 4 else ("mid" if len(sc["big"]) <= 7 else "sm")
        body = f'<div class="big {size}">{e(sc["big"])}</div><div class="h">{e(sc["text"])}</div>'
    elif t == "compare":
        small = any(len(r) > 9 for c in (sc["left"], sc["right"]) for r in c["rows"])  # 양쪽 글자 크기를 맞춘다

        def col(c, cls):
            return f'<div class="card {cls}"><div class="lab">{e(c["label"])}</div>' + "".join(
                f'<div class="row{" sm" if small else ""}">{e(r)}</div>' for r in c["rows"]) + "</div>"
        body = f'<div class="cmp">{col(sc["left"], "")}{col(sc["right"], "after" if sc.get("mark_right", True) else "")}</div>'
    elif t == "price":
        body = (f'<div class="plan">{e(sc["plan"])}</div><div class="was">{e(sc["before"])}</div>'
                f'<div class="now">{e(sc["after"])}</div><div><span class="badge">{e(sc["badge"])}</span></div>'
                f'<div class="note">{e(sc["note"])}</div>')
    elif t == "checklist":
        body = "".join(f'<div class="card grp"><div class="gl {"ok" if j == 0 else "maybe"}">{e(g["label"])}</div><ul>'
                       + "".join(f"<li>{e(x)}</li>" for x in g["items"]) + "</ul></div>"
                       for j, g in enumerate(sc["groups"]))
    elif t == "warning":
        body = '<div class="card warn"><ul>' + "".join(f"<li>{e(x)}</li>" for x in sc["items"]) + "</ul></div>"
    elif t == "outro":
        body = "".join(f'<div class="dt"><b>{e(d)}</b><span>{e(s)}</span></div>' for d, s in sc.get("dates", [])) + \
               "".join(f'<div class="statl">· {e(x)}</div>' for x in sc.get("lines", [])) + \
               f'<div class="h" style="margin-top:20px">{e(sc["text"])}</div>'
    elif t == "steps":
        body = "".join(f'<div class="step"><b>{k + 1}</b><span>{e(x)}</span></div>' for k, x in enumerate(sc["items"]))
    elif t == "stat":
        body = "".join(f'<div><div class="stat{" mid" if len(st["value"]) > 6 else ""}">{e(st["value"])}</div>'
                       f'<div class="statl">{e(st["label"])}</div></div>' for st in sc["stats"]) + \
               (f'<div class="src">{e(sc["source"])}</div>' if sc.get("source") else "")
    elif t == "quote":
        body = f'<div class="quote">“{e(sc["quote"])}”</div><div class="qsrc">— {e(sc["by"])}</div>'
    else:
        raise ValueError(f"모르는 장면 종류: {t}")
    dots = "".join(f'<i class="{"on" if k == i else ""}"></i>' for k in range(n))
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f'<div class="top"><span class="kicker">{e(sc["kicker"])}</span><span class="dots">{dots}</span></div>'
            f'<div class="stage">{body}</div><div class="cap">{e(sc["narration"])}</div>'
            f'<div class="tag">샘플 · 자료: 장면표 출처 참조</div></body></html>')


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])
    return r.stdout


def render(spec_path: str) -> Path:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    name = Path(spec_path).stem
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    scenes = spec["scenes"]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, sc in enumerate(scenes):
            pg.set_content(_scene_html(sc, i, len(scenes), spec["title"]))
            pg.screenshot(path=str(work / f"s{i}.png"))
        b.close()

    parts = []
    for i, sc in enumerate(scenes):
        aiff, wav = work / f"s{i}.aiff", work / f"s{i}.wav"
        _run(["say", "-v", spec.get("voice", "Yuna"), "-r", str(spec.get("rate", 200)), "-o", str(aiff), sc["narration"].replace("**", "")])
        _run(["ffmpeg", "-y", "-i", str(aiff), "-af", "apad=pad_dur=0.35", "-ar", "44100", "-ac", "2", str(wav)])
        dur = float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)]))
        frames = int(dur * FPS) + 1
        seg = work / f"s{i}.mp4"
        # 천천히 확대(켄 번스) — 정지 화면이 덜 지루하게
        zoom = f"zoompan=z='min(zoom+0.0004,1.04)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}"
        _run(["ffmpeg", "-y", "-loop", "1", "-i", str(work / f"s{i}.png"), "-i", str(wav),
              "-vf", f"scale={W * 2}:{H * 2},{zoom},format=yuv420p", "-t", f"{dur:.2f}",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", str(seg)])
        parts.append(seg)

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    final = OUT / f"{name}.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(final)])
    return final
