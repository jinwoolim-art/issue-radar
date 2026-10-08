"""휴대폰·팀원용 웹 앱 묶음 (out/site/) 만들기 + 클라우드플레어 페이지에 올리기.

- index.html = 트렌드 계기판, log.html = 수집 로그
- manifest + 아이콘 → 휴대폰 "홈 화면에 추가" 하면 앱처럼 열림 (PWA)
- 올리기: npx wrangler pages deploy (클라우드플레어 무료 요금제는 한 달 배포 500회 → 2시간에 한 번까지만)
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
SITE = OUT / "site"
PROJECT = "p4m-issue-radar"
STAMP = ROOT / "data" / "last_deploy.txt"
MIN_GAP = 2 * 3600
ACCESS_OK = ROOT / "data" / "access_confirmed"   # 탐님이 접근 제한 설정을 확인한 뒤에만 만든다

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="112" fill="#1f2a37"/>
<circle cx="256" cy="256" r="168" fill="none" stroke="#3987e5" stroke-width="10" opacity=".35"/>
<circle cx="256" cy="256" r="104" fill="none" stroke="#3987e5" stroke-width="10" opacity=".55"/>
<polyline points="110,330 190,270 250,300 320,200 400,150" fill="none" stroke="#ffffff" stroke-width="26"
 stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="400" cy="150" r="22" fill="#3987e5" stroke="#fff" stroke-width="8"/></svg>"""

HEAD = """<link rel="manifest" href="manifest.webmanifest" crossorigin="use-credentials">
<link rel="apple-touch-icon" href="icon-180.png"><link rel="icon" href="icon-192.png">
<meta name="theme-color" content="#1f2a37"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="이슈레이더"><meta name="mobile-web-app-capable" content="yes">
<style>.appnav{position:sticky;top:0;z-index:9;display:flex;gap:6px;padding:8px 12px;background:#1f2a37;
 font:600 13px -apple-system,"Apple SD Gothic Neo",sans-serif}.appnav a{color:#cfd6df;text-decoration:none;padding:6px 12px;
 border-radius:999px}.appnav a.on{background:#3987e5;color:#fff}</style>"""


def _nav(active):
    items = [("index.html", "📊 트렌드 계기판"), ("log.html", "🗂 수집 로그"), ("shorts.html", "🎬 샘플 영상")]
    return '<nav class="appnav">' + "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in items) + "</nav>"


def _icons():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        for size in (180, 192, 512):
            pg = b.new_page(viewport={"width": size, "height": size})
            pg.set_content(f'<html><body style="margin:0">{ICON_SVG.replace("<svg ", f"<svg width={size} height={size} ")}</body></html>')
            pg.screenshot(path=str(SITE / f"icon-{size}.png"), omit_background=True)
        b.close()


def build() -> Path:
    SITE.mkdir(parents=True, exist_ok=True)
    for src, dst in [(OUT / "trends.html", "index.html"), (OUT / "log.html", "log.html")]:
        if not src.exists():
            continue
        html = src.read_text(encoding="utf-8")
        html = html.replace("</head>", HEAD + "</head>", 1).replace("<body>", "<body>" + _nav(dst), 1)
        (SITE / dst).write_text(html, encoding="utf-8")
    _shorts_page()
    (SITE / "manifest.webmanifest").write_text(json.dumps({
        "name": "이슈 레이더 — 트렌드 계기판", "short_name": "이슈레이더", "start_url": "index.html",
        "display": "standalone", "background_color": "#f3f3f0", "theme_color": "#1f2a37", "lang": "ko",
        "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
    }, ensure_ascii=False), encoding="utf-8")
    if not (SITE / "icon-512.png").exists():
        _icons()
    (SITE / "_headers").write_text("/*\n  Cache-Control: no-cache\n  X-Robots-Tag: noindex\n", encoding="utf-8")
    return SITE


def _shorts_page():
    """out/shorts/*.mp4 → site/shorts/ + 목록 페이지 (최신순). 장면표(JSON)의 제목·출처를 함께 보여 준다."""
    vids = sorted((OUT / "shorts").glob("*.mp4"), reverse=True)
    (SITE / "shorts").mkdir(exist_ok=True)
    cards = []
    for k, v in enumerate(vids, 1):
        shutil.copy2(v, SITE / "shorts" / v.name)
        v2 = v.stem.endswith("-v2")
        spec = ROOT / "briefs" / "shorts" / f"{v.stem.removesuffix('-v2')}.json"
        meta = json.loads(spec.read_text(encoding="utf-8")) if spec.exists() else {}
        title = meta.get("title", v.stem) + (" — v2 캐릭터·움직임" if v2 else "")
        src = "".join(f"<li>{s}</li>" for s in meta.get("sources", []))
        cards.append(f'''<article class="v"><video src="shorts/{v.name}" controls playsinline preload="metadata"></video>
<div class="t"><b>{k}. {title}</b><div class="m">{meta.get("line", "")} · {v.stem[:10]} · {"v2: 레이더 로봇 + 형광펜·카운트업" if v2 else "v1: 정지 카드 + 맥 음성"}</div>
<ul class="m">{src}</ul></div></article>''')
    page = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>샘플 영상</title><style>
:root{{--bg:#f3f3f0;--card:#fff;--fg:#0b0b0b;--muted:#5d5c58;--line:#e4e3de}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121211;--card:#1c1c1b;--fg:#f2f2f0;--muted:#b7b6ad;--line:#2f2f2d;color-scheme:dark}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,"Apple SD Gothic Neo",sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:16px}}h1{{font-size:20px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}}
.v{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}}video{{width:100%;aspect-ratio:9/16;background:#000;display:block}}
.t{{padding:10px 12px}}.guide{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:0 0 16px}}
.guide ol{{margin:6px 0 0;padding-left:20px}}.m{{color:var(--muted);font-size:12px;margin:4px 0 0;padding-left:16px;overflow-wrap:anywhere}}div.m{{padding-left:0}}
</style></head><body><div class="wrap"><h1>샘플 영상</h1>
<div class="guide"><b>팀 평가 기준</b> — 영상마다 번호와 함께 1~5점으로 적어 주세요.<ol>
<li><b>첫 3초</b>: 넘기지 않고 계속 볼 것 같은가</li><li><b>저장할 만한가</b>: 나중에 다시 꺼내 볼 정보가 있는가</li>
<li><b>이해</b>: 한 번 보고 무슨 말인지 아는가</li><li><b>그래픽·음성</b>: 이 수준으로 올려도 되는가, 무엇이 먼저 바뀌어야 하나</li></ol>
<div class="m" style="padding:0;margin-top:6px">음성은 맥 기본 음성, 화면은 글자 카드뿐인 무료 러프본입니다. 내용과 구성 위주로 봐 주세요.</div></div>
<div class="grid">{"".join(cards) or "<p>아직 영상이 없습니다.</p>"}</div></div></body></html>'''
    page = page.replace("</head>", HEAD + "</head>", 1).replace("<body>", "<body>" + _nav("shorts.html"), 1)
    (SITE / "shorts.html").write_text(page, encoding="utf-8")


def deploy(force=False) -> bool:
    """2시간에 한 번까지만 올린다 (무료 배포 한도 보호). 로그인 안 돼 있으면 조용히 건너뜀.
    ⚠️ 접근 제한(Cloudflare Access, 팀원 이메일만)을 켰다고 확인되기 전에는 절대 올리지 않는다."""
    if not ACCESS_OK.exists():
        print("  배포 보류: 접근 제한(팀원 이메일만) 설정 확인 전 — data/access_confirmed 파일이 생기면 배포 시작")
        return False
    if not force and STAMP.exists() and time.time() - float(STAMP.read_text()) < MIN_GAP:
        return False
    build()
    r = subprocess.run(["npx", "--yes", "wrangler", "pages", "deploy", str(SITE), "--project-name", PROJECT,
                        "--branch", "main", "--commit-dirty=true"], cwd=ROOT, capture_output=True, text=True,
                       timeout=300, env={**__import__("os").environ, "PATH": "/opt/homebrew/bin:/usr/bin:/bin"})
    if r.returncode != 0:
        print("  배포 건너뜀:", (r.stderr or r.stdout).strip().splitlines()[-1:] or "")
        return False
    STAMP.write_text(str(time.time()))
    print("  배포 완료:", [l for l in r.stdout.splitlines() if "pages.dev" in l][-1:] or "")
    return True
