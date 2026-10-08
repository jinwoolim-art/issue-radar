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
PROJECT = "issue-radar"
STAMP = ROOT / "data" / "last_deploy.txt"
MIN_GAP = 2 * 3600

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<rect width="512" height="512" rx="112" fill="#1f2a37"/>
<circle cx="256" cy="256" r="168" fill="none" stroke="#3987e5" stroke-width="10" opacity=".35"/>
<circle cx="256" cy="256" r="104" fill="none" stroke="#3987e5" stroke-width="10" opacity=".55"/>
<polyline points="110,330 190,270 250,300 320,200 400,150" fill="none" stroke="#ffffff" stroke-width="26"
 stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="400" cy="150" r="22" fill="#3987e5" stroke="#fff" stroke-width="8"/></svg>"""

HEAD = """<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png"><link rel="icon" href="icon-192.png">
<meta name="theme-color" content="#1f2a37"><meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="이슈레이더"><meta name="mobile-web-app-capable" content="yes">
<style>.appnav{position:sticky;top:0;z-index:9;display:flex;gap:6px;padding:8px 12px;background:#1f2a37;
 font:600 13px -apple-system,"Apple SD Gothic Neo",sans-serif}.appnav a{color:#cfd6df;text-decoration:none;padding:6px 12px;
 border-radius:999px}.appnav a.on{background:#3987e5;color:#fff}</style>"""


def _nav(active):
    items = [("index.html", "📊 트렌드 계기판"), ("log.html", "🗂 수집 로그")]
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


def deploy(force=False) -> bool:
    """2시간에 한 번까지만 올린다 (무료 배포 한도 보호). 로그인 안 돼 있으면 조용히 건너뜀."""
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
