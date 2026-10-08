"""장면표(JSON) → 움직이는 세로 숏폼(v2). 글자 중심 + 채널 캐릭터(안테나 로봇 '레이더').

v1(shorts.py)은 정지 카드를 천천히 확대했다. v2는 장면을 시간 t의 함수로 그려 초당 30장씩 찍는다.
  - 핵심 단어 형광펜: 장면표 글자 안에서 **이렇게** 감싸면 된다
  - 숫자 카운트업: stat 값, price 할인가
  - 요소가 차례로 등장, 자막은 읽는 속도에 맞춰 밝아짐
  - 로봇은 장면 종류마다 다르게 반응 (훅=점프, 비교=두리번, 숫자=가리키기, 주의=땀, 마무리=손 흔들기)
같은 화면을 다시 찍어도 똑같이 나오도록(재현 가능) 애니메이션은 모두 render(t) 한 함수에서 계산한다.
목소리: 네이버 클로바 보이스(기본 화자 ndain). 키가 없으면 맥 음성(say)으로 대신한다.
효과음: 장면 시작마다 로봇 소리("비리비리")를 직접 합성해 넣는다 — 외부 음원을 쓰지 않아 저작권 걱정이 없다.
사용: python -m radar shorts2 briefs/shorts/파일.json → out/shorts/파일-v2.mp4
"""
import hashlib
import html
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import numpy as np

from .shorts import OUT, ROOT, W, H, _run

FPS = 30
PAD = 0.35   # 장면 끝 여백(초)
# 채널 오프닝 종류와 길이(초). 행동 → 뚝 멈춤(0.22초) → 자리로 슝(0.35) → 콩(0.15) → 브리핑
INTROS = {"bignews": 1.4, "dance": round(4 * 60 / 128 + 0.22 + 0.5, 3), "fly": 2.22, "rocket": 2.22,
          # 내용과 엮은 오프닝: 패션쇼·광고팝업·사이렌·글자폭탄·쇼핑카트·슬롯머신·돋보기·영수증
          "outfit": 2.32, "adpop": 2.32, "siren": 2.32, "textflood": 2.32, "cart": 2.22, "slot": 2.32, "magnifier": 2.32, "receipt": 2.32,
          # 장르 테스트용: 놀이문화 불꽃놀이 · 생활꿀팁 전구 · 전자제품 언박싱
          "fireworks": 2.32, "lightbulb": 2.32, "unbox": 2.32}
SR = 44100
VOICE = {"tts": "clova", "speaker": "ndain", "speed": "-2"}   # 숏폼은 조금 빠르게   # 장면표에서 "voice2": {...} 로 바꿀 수 있음
TTS_CACHE = ROOT / "data" / "tts_cache"    # 같은 문장·화자는 다시 돈 내고 만들지 않는다


def _clova(text: str, speaker: str, speed: str, out: Path) -> bool:
    kid, key = os.environ.get("CLOVA_API_KEY_ID"), os.environ.get("CLOVA_API_KEY")
    if not (kid and key):
        return False
    TTS_CACHE.mkdir(parents=True, exist_ok=True)
    cached = TTS_CACHE / (hashlib.sha1(f"{speaker}|{speed}|{text}".encode()).hexdigest()[:16] + ".mp3")
    if not cached.exists():
        body = urllib.parse.urlencode({"speaker": speaker, "text": text, "format": "mp3", "speed": speed}).encode()
        req = urllib.request.Request("https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts", data=body, headers={
            "X-NCP-APIGW-API-KEY-ID": kid, "X-NCP-APIGW-API-KEY": key, "Content-Type": "application/x-www-form-urlencoded"})
        cached.write_bytes(urllib.request.urlopen(req, timeout=30).read())
    out.write_bytes(cached.read_bytes())
    return True


FX_GAP = 0.8                          # 오프닝·장면 시작 소리와 효과 사이 최소 틈(초)
FX_TAIL = {"good": 1.6, "bad": 2.6}   # 효과가 끝까지 보이려면 필요한 시간(초) — 모자라면 장면을 늘린다


def _fx_time(narration: str, target: str | None, offset: float, speech: float) -> float:
    """효과를 터뜨릴 시각 = 핵심 단어를 말하는 순간. 자막 하이라이트와 같은 방식(글자 수 비례)으로 계산한다.
    target(fx_at)을 주면 그 단어, 없으면 대본의 첫 **강조** 단어."""
    words = narration.split()
    clean = [w.replace("**", "") for w in words]
    idx = next((k for k, w in enumerate(clean) if target and target in w), None)
    if idx is None:
        idx = next((k for k, w in enumerate(words) if "**" in w), 0)
    total = sum(len(w) for w in clean) or 1
    return offset + sum(len(w) for w in clean[:idx]) / total * speech


def _intro_sfx(kind: str, total: float, out: Path) -> float:
    """오프닝 소리. 행동 소리(댄스 비트·날갯짓·제트) → 뚝 끊김 → "삐?" → 슝 → 콩. 모두 직접 합성."""
    rng = np.random.default_rng(5)
    buf = np.zeros(int(SR * total))
    def put(sig, at, gain=1.0):
        i = int(at * SR); n = min(sig.size, buf.size - i)
        if n > 0: buf[i:i + n] += sig[:n] * gain
    def tone(f0, f1, dur, warble=0.0, square=0.4):
        t = np.arange(int(SR * dur)) / SR
        f = np.linspace(f0, f1, t.size) * (1 + warble * np.sin(2 * np.pi * 28 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        return ((1 - square) * np.sin(ph) + square * np.sign(np.sin(ph)) * 0.5) * np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))
    def noise(dur, smooth=1, decay=0.5):
        n = rng.standard_normal(int(SR * dur))
        if smooth > 1: n = np.convolve(n, np.ones(smooth) / smooth, "same")      # 이동평균 = 저음만 남기기
        t = np.arange(n.size) / SR
        return n * np.exp(-t / (dur * decay))
    d0 = total - 0.5
    m = d0 if kind == "bignews" else d0 - 0.22
    if kind == "bignews":       # 삐빅(감지) → 빅↗뉴↘스!↗(로봇 말투)
        for at, sig in [(0.22, tone(1500, 1900, 0.06)), (0.30, tone(2300, 2900, 0.08)), (0.45, tone(1900, 1950, 0.07)),
                        (0.55, tone(1300, 1250, 0.08)), (0.66, tone(2000, 3000, 0.14, warble=0.03))]:
            put(sig, at)
    elif kind == "dance":       # 128BPM 4박: 킥·박수·하이햇·베이스·신스 → m에서 뚝
        beat = 60 / 128
        music = np.zeros(int(SR * m))
        def mput(sig, at, gain):
            i = int(at * SR); n = min(sig.size, music.size - i)
            if n > 0: music[i:i + n] += sig[:n] * gain
        for k in range(4):
            tk = np.arange(int(SR * 0.16)) / SR
            mput(np.sin(2 * np.pi * np.cumsum(np.linspace(150, 45, tk.size)) / SR) * np.exp(-tk / 0.07), k * beat, 1.0)   # 킥
            mput(tone(110 if k % 2 == 0 else 98, 110 if k % 2 == 0 else 98, 0.2, square=0.7), k * beat, 0.35)              # 베이스
            hh = noise(0.035); mput(hh - np.convolve(hh, np.ones(8) / 8, "same"), (k + 0.5) * beat, 0.5)                  # 하이햇
            for f0 in (440, 523, 659): mput(tone(f0, f0, 0.11, square=0.8), (k + 0.5) * beat, 0.16)                        # 신스 화음
            if k % 2: cl = noise(0.09); mput(cl - np.convolve(cl, np.ones(20) / 20, "same"), k * beat, 0.6)                # 박수
        put(music, 0)           # m 이후는 없음 = 뚝 끊김
    elif kind == "fly":         # 퍼덕퍼덕 + 짹짹 → 날개 펑
        for k in range(int(m * 7)):
            put(noise(0.05, smooth=30), k / 7, 0.9)
        put(tone(3000, 4200, 0.06, square=0.1), 0.3, 0.6); put(tone(3200, 4400, 0.06, square=0.1), 0.38, 0.6)
        put(tone(3000, 4300, 0.07, square=0.1), 0.95, 0.6)
        put(noise(0.12, smooth=12), m, 0.8)
    elif kind == "rocket":      # 제트 엔진(점점 높아짐) → 뚝 꺼짐 → 떨어지는 휘파람
        n = int(SR * m); t = np.arange(n) / SR
        jet = np.convolve(rng.standard_normal(n), np.ones(18) / 18, "same") * np.minimum(1, t / 0.15) * 1.6
        whine = 0.15 * np.sin(2 * np.pi * np.cumsum(np.linspace(220, 440, n)) / SR)
        put(jet + whine, 0)
        put(tone(1800, 600, 0.22, square=0.2), m + 0.02, 0.7)
    elif kind == "outfit":      # 찰칵! + 슉 ×4 (패션쇼)
        for k in range(4):
            put(noise(0.025), k * 0.4 + 0.01, 0.9); put(tone(4200, 3600, 0.03, square=0.2), k * 0.4 + 0.02, 0.5)
            put(tone(700, 1400, 0.12, square=0.1), k * 0.4 + 0.12, 0.25)
    elif kind == "adpop":       # 띵!(광고) → 퍽!(쳐냄) ×3 → 마지막은 얼굴에 철썩
        for at, side in [(0.15, 1), (0.5, 1), (0.85, 1), (1.25, 0)]:
            put(tone(1568, 1568, 0.12, square=0.1), at, 0.6); put(tone(2093, 2093, 0.18, square=0.1), at + 0.06, 0.5)
            if side: put(noise(0.06, smooth=6), at + 0.25, 1.0)
        put(noise(0.08, smooth=3), 1.25, 1.0)
    elif kind == "siren":       # 사각사각 일기 → 삐뽀삐뽀
        for k in range(16): put(noise(0.035, smooth=2), 0.05 + k * 0.05, 0.25)
        for k in range(int((m - 0.85) / 0.18) + 1):
            f0 = 950 if k % 2 == 0 else 700
            put(tone(f0, f0, 0.18, square=0.6), 0.85 + k * 0.18, 0.6)
    elif kind == "textflood":   # 툭툭툭 쌓이다가 → 뽁! 탈출
        for k in range(10): put(tone(160, 80, 0.08, square=0.0), 0.30 + k * 0.1, 0.9)
        put(tone(500, 1300, 0.1, square=0.2), 1.25, 0.8)
    elif kind == "cart":        # 덜덜덜 바퀴 → 끼이익 → 딩동
        tt = np.arange(int(SR * 0.75)) / SR
        put(noise(0.75, smooth=4, decay=10) * (0.55 + 0.45 * np.sign(np.sin(2 * np.pi * 30 * tt))), 0, 0.6)
        put(tone(1700, 1400, 0.35, warble=0.05, square=0.6), 0.75, 0.6)
        put(tone(1319, 1319, 0.18, square=0.1), 1.1, 0.5); put(tone(1047, 1047, 0.25, square=0.1), 1.25, 0.5)
    elif kind == "slot":        # 철컥 → 촤라라락 → 띵(7) → 띵(?) 엇박
        put(noise(0.06, smooth=10), 0.15, 0.8); put(tone(300, 180, 0.08, square=0.3), 0.15, 0.6)
        for k in range(int((1.25 - 0.3) / 0.045)): put(tone(2800, 2800, 0.012, square=0.5), 0.3 + k * 0.045, 0.4)
        put(tone(1568, 1568, 0.2, square=0.1), 1.0, 0.7); put(tone(1047, 990, 0.25, square=0.1), 1.25, 0.7)
    elif kind == "magnifier":   # 흠? 흠? 흠? → 쾅! 도장
        for at in (0.2, 0.55, 0.9): put(tone(800, 650, 0.09, square=0.2), at, 0.5)
        put(tone(130, 55, 0.22, square=0.7), 1.05, 1.0); put(noise(0.1, smooth=4), 1.05, 0.8)
    elif kind == "receipt":     # 지이이익 인쇄 → 띵! (999999)
        tt = np.arange(int(SR * 1.2)) / SR
        put(noise(1.2, smooth=2, decay=10) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 22 * tt))), 0.1, 0.45)
        put(tone(2093, 2093, 0.3, square=0.1), 1.3, 0.7)
    elif kind == "fireworks":   # 피융~ → 펑! ×3
        for at in (0.1, 0.55, 1.0):
            put(tone(600, 2000, 0.35, square=0.1), at, 0.5)
            put(noise(0.5, smooth=3, decay=0.3), at + 0.35, 1.0)
            for k in range(6): put(noise(0.02), at + 0.45 + k * 0.05 + (k % 2) * 0.02, 0.4)   # 타닥타닥
    elif kind == "lightbulb":   # 흠 띠·띠·띠 → 띵!
        for at in (0.2, 0.4, 0.6): put(tone(500, 500, 0.06, square=0.3), at, 0.5)
        put(tone(2093, 2093, 0.4, square=0.05), 0.8, 0.6); put(tone(2637, 2637, 0.4, square=0.05), 0.8, 0.5)
        put(tone(3136, 3300, 0.2, square=0.05), 0.95, 0.3)
    elif kind == "unbox":       # 달그락달그락 → 찌익(테이프) → 뿅! ✨
        for k in range(6): put(noise(0.05, smooth=8), 0.1 + k * 0.1, 0.7)
        put(noise(0.18), 0.72, 0.6)
        put(tone(400, 1600, 0.12, square=0.3), 0.9, 0.7); put(tone(2637, 2800, 0.25, square=0.05), 1.0, 0.4)
    if kind != "bignews":
        put(tone(1200, 1900, 0.12), m + 0.04, 0.8)          # 앗! "삐?"
    put(tone(2600, 700, 0.3, warble=0.02), d0)              # 슝~
    put(tone(420, 240, 0.09), d0 + 0.33)                    # 콩
    peak = {"bignews": 0.22, "dance": 0.5, "rocket": 0.36}.get(kind, 0.32)   # 댄스 비트는 목소리와 비슷한 크기로 신나게
    sig = (buf / max(1e-9, np.abs(buf).max()) * peak * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(sig.tobytes())
    return total


def _intro_kind(spec: dict, name: str) -> str | None:
    """장면표 "intro": 종류 이름이면 그것, false면 없음, 안 쓰면 영상마다 돌아가며 자동 선택."""
    v = spec.get("intro", True)
    if v is False:
        return None
    if isinstance(v, str) and v in INTROS:
        return v
    kinds = list(INTROS)
    return kinds[sum(map(ord, name)) % len(kinds)]


def _chirp(kind: str, seed: int, out: Path) -> float:
    """귀여운 로봇 소리를 합성해 wav로 저장하고 길이(초)를 돌려준다.
    biri = 장면 시작 "비리비리", bibik = 훅 "삐빅!", down = 마무리 "삐리~" (내려가는 소리)"""
    rng = np.random.default_rng(seed)
    def tone(f0, f1, dur, warble=0.0):
        t = np.arange(int(SR * dur)) / SR
        f = np.linspace(f0, f1, t.size) * (1 + warble * np.sin(2 * np.pi * 28 * t))
        ph = 2 * np.pi * np.cumsum(f) / SR
        w = 0.6 * np.sin(ph) + 0.4 * np.sign(np.sin(ph)) * 0.5        # 사인 + 약한 사각파 = 장난감 로봇 음색
        env = np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))
        return w * env
    gap = lambda d: np.zeros(int(SR * d))
    if kind == "bibik":
        sig = np.concatenate([tone(1500, 1900, 0.07), gap(0.03), tone(2300, 2900, 0.09)])
    elif kind == "down":
        sig = tone(3000, 1300, 0.34, warble=0.04)
    elif kind == "yay":      # 좋은 소식: 도-미-솔-도 올라가는 아르페지오
        sig = np.concatenate([np.concatenate([tone(f, f * 1.02, 0.065), gap(0.01)]) for f in (1047, 1319, 1568)]
                             + [tone(2093, 2150, 0.14, warble=0.03)])
    elif kind == "sad":      # 나쁜 소식: 힘 빠지게 내려가는 "뾰-로롱"
        sig = np.concatenate([tone(1200, 900, 0.16), gap(0.04), tone(1000, 560, 0.3, warble=0.05)])
    else:
        notes = rng.choice([1700, 2100, 2500, 2900, 3300], size=6)
        sig = np.concatenate([np.concatenate([tone(f, f * 1.08, 0.042), gap(0.008)]) for f in notes])
    sig = (sig / max(1e-9, np.abs(sig).max()) * 0.18 * 32767).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(sig.tobytes())
    return sig.size / SR


def _fmt(s) -> str:
    """글자 이스케이프 + **강조** → 형광펜, 줄바꿈 → <br>"""
    s = html.escape(str(s)).replace("\n", "<br>")
    return re.sub(r"\*\*(.+?)\*\*", r'<mark class="hl">\1</mark>', s)


CSS = """
:root{--bg:#10151c;--panel:#18202b;--fg:#f4f6f8;--muted:#9aa7b4;--accent:#5ab0ff;--hot:#ffd166;--bad:#ff7a6b;--good:#7bd88f}
*{box-sizing:border-box;margin:0}
body{width:1080px;height:1920px;background:radial-gradient(1200px 900px at 80% 10%,#1d2a3a 0,var(--bg) 60%);color:var(--fg);
 font-family:"Apple SD Gothic Neo","Noto Sans KR",sans-serif;overflow:hidden;position:relative;word-break:keep-all}
.top{position:absolute;top:120px;left:80px;right:160px;display:flex;align-items:center;gap:18px;z-index:5}
.kicker:empty{display:none}
.top .kicker{position:absolute;left:0;top:-10px}
.kicker{color:var(--hot);font-weight:900;font-size:84px;letter-spacing:-2px;line-height:1.1;white-space:nowrap}   /* 오프닝 대표 키워드: 본 제목과 같은 노랑, 버튼 없이 */
.dots{margin-left:auto;display:flex;gap:10px}.dots i{width:16px;height:16px;border-radius:50%;background:#33404f}.dots i.on{background:var(--fg)}
.stage{position:absolute;top:250px;left:80px;right:160px;height:770px;display:flex;flex-direction:column;justify-content:center;gap:30px}
.cap{position:absolute;top:1180px;left:70px;right:150px;background:rgba(0,0,0,.55);border-radius:28px;padding:30px 36px;
 font-size:50px;line-height:1.38;font-weight:700;text-wrap:balance}
.cap span{opacity:.35}.cap span.on{opacity:1}.cap mark{background:none;color:var(--hot)}
.tag{position:absolute;bottom:90px;left:80px;font-size:28px;color:var(--muted)}
.rv{opacity:0}
mark.hl{color:inherit;background:linear-gradient(transparent 58%,rgba(255,209,102,.55) 58%) no-repeat;background-size:0% 100%;padding:0 4px;border-radius:4px}
.big{font-size:330px;font-weight:900;letter-spacing:-8px;color:var(--hot);line-height:1}
.big.mid{font-size:190px;letter-spacing:-4px}.big.sm{font-size:130px;letter-spacing:-2px}
.h{font-size:86px;font-weight:900;line-height:1.2;letter-spacing:-2px}
.card{background:var(--panel);border-radius:32px;padding:38px 40px}
.cmp{display:grid;grid-template-columns:1fr 1fr;gap:22px}.cmp .card{padding:44px 30px}
.cmp .lab{font-size:40px;color:var(--muted);margin-bottom:26px}.cmp .row{font-size:62px;font-weight:900;margin:14px 0}
.cmp .row.sm{font-size:46px;font-weight:700}.cmp .after{outline:5px solid var(--bad)}
.plan{font-size:46px;color:var(--muted)}.was{font-size:90px;color:var(--muted);text-decoration:line-through;text-decoration-thickness:8px}
.now{font-size:170px;font-weight:900;color:var(--hot);letter-spacing:-4px;line-height:1}
.badge{display:inline-block;background:var(--hot);color:#1a1300;font-weight:900;font-size:46px;padding:12px 28px;border-radius:18px}
.note{font-size:42px;color:var(--muted)}
.grp .gl{font-size:44px;font-weight:900;margin-bottom:16px}.grp .gl.ok{color:var(--good)}.grp .gl.maybe{color:var(--hot)}
.grp li{font-size:48px;margin:12px 0 12px 44px}
.warn{border:6px solid var(--hot)}.warn li{font-size:54px;font-weight:800;margin:18px 0 18px 50px}
.dt{display:flex;align-items:baseline;gap:30px;margin:14px 0}.dt b{font-size:130px;color:var(--hot);font-weight:900;letter-spacing:-3px;min-width:330px}
.dt span{font-size:50px;font-weight:700}
.step{display:flex;gap:28px;align-items:flex-start;margin:6px 0}.step b{flex:none;width:92px;height:92px;border-radius:50%;background:var(--accent);
 color:#08111b;font-size:52px;font-weight:900;display:flex;align-items:center;justify-content:center}.step span{font-size:52px;font-weight:800;line-height:1.3;padding-top:12px}
.stat{font-size:200px;font-weight:900;color:var(--hot);letter-spacing:-5px;line-height:1}.stat.mid{font-size:140px}
.statl{font-size:56px;font-weight:800;line-height:1.3}.src{font-size:36px;color:var(--muted)}
.quote{border-left:14px solid var(--accent);padding:10px 0 10px 40px;font-size:60px;font-weight:800;line-height:1.35}
.qsrc{font-size:38px;color:var(--muted)}
#bot{position:absolute;right:170px;top:1036px;width:144px;height:153px;image-rendering:pixelated}
#fx,#topfx{position:absolute;left:0;top:0;width:1080px;height:1920px;image-rendering:pixelated}
#news{display:none;position:absolute;left:540px;top:300px;background:var(--hot);color:#1a1300;font:900 120px/1 "Apple SD Gothic Neo",sans-serif;
 padding:22px 40px;border-radius:24px;border:8px solid #1a1300;white-space:nowrap;opacity:0;letter-spacing:-3px}
#bang{position:absolute;right:196px;top:950px;background:var(--hot);color:#1a1300;font:900 56px/1 "Apple SD Gothic Neo",sans-serif;
 padding:10px 22px;border-radius:14px;opacity:0}
"""

# 안테나 로봇 '레이더' — 16x17 픽셀. a 안테나, k 테두리, w 몸, d 얼굴 화면, e 눈, m 입, s 팔·몸 그늘, c 가슴 불빛
BOT = [
    "......aaa.......",
    "......aaa.......",
    ".......k........",
    "...kkkkkkkkkk...",
    "..kwwwwwwwwwwk..",
    "..kwddddddddwk..",
    "..kwdeeddeedwk..",
    "..kwdeeddeedwk..",
    "..kwddddddddwk..",
    "..kwdddmmdddwk..",
    "..kwwwwwwwwwwk..",
    "...kkkkkkkkkk...",
    "....kkkkkkkk....",
    "....kwwccwwk....",
    "....kwwwwwwk....",
    "....kkkkkkkk....",
    ".....kk..kk.....",
]

# 캐릭터: AI 채널 로봇 + 생활 채널 친구 3인방. 같은 16x17 픽셀 틀이라 표정·팔·효과 코드를 함께 쓴다.
#   blink = 깜빡이는 부분(안테나·프로펠러 끝·귀 끝·램프), chest = 가슴 불빛, arm_shift = 팔 위치 보정(몸이 넓은 깡통은 ±1)
_fix = lambda rows: [(r + "." * 16)[:16] for r in rows]
CHARS = {
    "ai": {"grid": BOT, "pal": {}, "blink": [[6, 0], [7, 0], [8, 0], [6, 1], [7, 1], [8, 1]], "chest": [[7, 13], [8, 13]], "chest_off": "w", "arm_shift": [0, 0]},
    "prop": {"grid": _fix(["..pppppppppppp..", ".......kk.......", ".......kk.......", ".....kkkkkk.....", "...kkMMMMMMkk...",
                           "..kMMMMMMMMMMk..", "..kMddddddddMk..", "..kMdeeeeeedMk..", "..kMddddddddMk..", "..kMMMMMMMMMMk..",
                           "...kkMMMMMMkk...", "....kkkkkkkk....", ".....kMMMMk.....", "....kMMccMMk....", "....kMMMMMMk....",
                           ".....kkkkkk.....", ".....kk..kk....."]),
             "pal": {"p": "#ffd166", "k": "#3d5a5a", "M": "#6fe0c0", "d": "#123030", "e": "#ffd166", "m": "#ffd166", "c": "#ff8fb1", "s": "#6fe0c0"},
             "blink": [[2, 0], [3, 0], [12, 0], [13, 0]], "chest": [[7, 13], [8, 13]], "chest_off": "M", "arm_shift": [0, 0]},
    "tv": {"grid": _fix(["...k........k...", "...kk......kk...", "....k......k....", "..kkkkkkkkkkkk..", "..kooooooooook..",
                         "..kokkkkkkkkok..", "..kokddddddkok..", "..kokdeddedkok..", "..kokdmmmmdkok..", "..kokkkkkkkkok..",
                         "..kooooooooook..", "..kkkkkkkkkkkk..", "......kkkk......", "....kowwwwok....", "....kooooook....",
                         "....kkkkkkkk....", ".....kk..kk....."]),
           "pal": {"k": "#6a3a3a", "o": "#ff8a7a", "d": "#2a1a22", "e": "#ffffff", "m": "#ffd166", "w": "#ffe3dc", "s": "#ff8a7a"},
           "blink": [[3, 0], [12, 0]], "chest": [[6, 13], [9, 13]], "chest_off": "o", "arm_shift": [0, 0]},
    "can": {"grid": _fix([".......yy.......", "......yyyy......", ".......kk.......", "....kkkkkkkk....", "...kaaaaaaaak...",
                          "...kBBBaaBBBk...", "...kBeBkkBeBk...", "...kBBBaaBBBk...", "...kaaaaaaaak...", "...kaaammaaak...",
                          "...kaaaaaaaak...", "...kaaaaaaaak...", "...kaagggaaak...", "...kaagggaaak...", "...kaaaaaaaak...",
                          "...kkkkkkkkkk...", "....kk....kk...."]),
            "pal": {"y": "#fff3b0", "k": "#6a5a2a", "a": "#ffc861", "B": "#2a2a2a", "e": "#ffffff", "m": "#8b5a2b", "g": "#7bd88f", "s": "#ffc861"},
            "blink": [[7, 0], [8, 0], [6, 1], [7, 1], [8, 1], [9, 1]], "chest": [[6, 12], [7, 12], [8, 12]], "chest_off": "a", "arm_shift": [-1, 1]},
}

JS = r"""(() => {   // 같은 페이지에 장면을 다시 넣어도 변수가 겹치지 않게 감싼다
const CH = %CHAR%, BOT = CH.grid, TYPE = %TYPE%, MOOD = %MOOD%, SPEECH = %SPEECH%, OFFSET = %OFFSET%, CHIRP = %CHIRP%, INTRO = %INTRO%, FXAT = %FXAT%, IK = %IKIND%, ACC = %ACC%;
const COL = {k:'#4a5a70', w:'#e8eef5', d:'#0f2233', e:'#5ae0ff', m:'#5ae0ff', s:'#9fb0c3', c:'#ff7a6b', a:'#ffd166', A:'#7a6a3a', x:'#7ec8ff', n:'#2b4a7a', p:'#ff8fb1', g:'#7bd88f', y:'#ffd166', B:'#05070a'};
Object.assign(COL, CH.pal);   // 캐릭터 색
const FACE = new Set(['d', 'e', 'm', '.']);   // 표정은 얼굴 화면과 빈칸에만 그린다 → 몸 모양이 다른 친구 로봇에도 같은 표정 코드가 통함
const armX = x => x <= 7 ? x + CH.arm_shift[0] : x + CH.arm_shift[1];
const cv = document.getElementById('bot'), g = cv.getContext('2d');
const rv = [...document.querySelectorAll('.stage .rv')];
const n = rv.length, gap = n ? Math.min(0.45, (SPEECH * 0.5) / n) : 0;
rv.forEach((el, i) => el.dataset.at = (INTRO ? INTRO - 0.2 : 0.12) + i * gap);   // 오프닝 글자가 흩어지고 로봇이 착지하는 순간 본 제목 등장
const words = [...document.querySelectorAll('.cap span')];
const total = words.reduce((a, w) => a + w.textContent.length, 0);
let acc = 0; words.forEach(w => { w.dataset.at = OFFSET + (acc / total) * SPEECH; acc += w.textContent.length; });
document.querySelectorAll('.cnt').forEach(el => el.dataset.to = el.textContent);
{ const kk = document.querySelector('.kicker');            // 키워드는 한 줄로 — 길면 들어갈 만큼 글자를 줄임
  if (kk && kk.textContent) { let fs = 84; while (kk.scrollWidth > 900 && fs > 44) { fs -= 2; kk.style.fontSize = fs + 'px'; } } }
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);

function countText(src, p) {        // "174,000원" → p(0~1)만큼 올라간 숫자, 형식(쉼표·소수점)은 유지
  const m = src.match(/\d[\d,]*(\.\d+)?/); if (!m) return src;
  const dec = m[1] ? m[1].length - 1 : 0, v = parseFloat(m[0].replace(/,/g, '')) * p;
  let s = v.toFixed(dec); if (m[0].includes(',')) s = Number(s).toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  return src.replace(m[0], s);
}

function drawBot(t) {
  const grid = BOT.map(r => r.split(''));
  const set = (x, y, ch) => { if (grid[y] && x >= 0 && x < 16 && FACE.has(BOT[y][x])) grid[y][x] = ch; };
  const setRaw = (x, y, ch) => { if (grid[y] && x >= 0 && x < 16) grid[y][x] = ch; };
  const eyes = (pat) => { for (const y of [6, 7]) pat.split('').forEach((ch, i) => set(4 + i, y, ch)); };
  let dx = 0, dy = (Math.floor(t * 2) % 2) ? 0 : -1, look = 0, arm = 'down', mouth = 'n', sweat = false;
  if (TYPE === 'hook' && t < 0.7 && !INTRO) { dy = -Math.round(Math.sin(Math.PI * t / 0.7) * 4); mouth = 'o'; }
  if (TYPE === 'compare') look = Math.floor(t / 0.9) % 2 ? 1 : -1;
  if (TYPE === 'stat' || TYPE === 'price') { arm = t > 0.3 ? 'point' : 'down'; look = -1; }
  if (TYPE === 'quote') look = -1;
  if (TYPE === 'warning') { if (t % 1.2 < 0.5) dx = Math.floor(t * 14) % 2 ? 1 : -1; sweat = true; mouth = 'o'; }
  if (TYPE === 'steps' || TYPE === 'checklist') dy = (t % 0.8) < 0.15 ? 1 : 0;
  if (TYPE === 'outro') arm = Math.floor(t * 4) % 2 ? 'wave1' : 'wave2';
  let mood = '';
  if (MOOD === 'good') {             // 점프하며 색종이 던지기 → 신나게 손 흔들기
    const u = t - FX_T0;
    if (u > 0 && u < 0.5) { dy = -Math.round(Math.sin(Math.PI * u / 0.5) * 3); arm = 'point'; }
    else if (u >= 0.5 && u < 3) arm = Math.floor(t * 5) % 2 ? 'wave1' : 'wave2';
    if (u > 0) mood = 'happy';
  }
  if (MOOD === 'bad' && t >= RAIN0) {   // 우산 들고 버티다가 → 돌풍에 우산 날아감 → 손 뻗고 울먹
    if (t < GUST) { arm = 'point'; if (t > GUST - 0.5) dx = Math.floor(t * 18) % 2 ? 1 : 0; }
    else { arm = (t - GUST) < 1.2 ? (Math.floor(t * 8) % 2 ? 'wave1' : 'wave2') : 'down'; mood = 'sad'; }
    look = 0;
  }
  // 눈: 깜빡임 > 두리번
  if (t % 2.8 < 0.12) { eyes('dddddddd'); for (let i = 0; i < 8; i++) set(4 + i, 7, 'deeddeed'[i]); }
  else if (look < 0) eyes('eeddeedd'); else if (look > 0) eyes('ddeeddee');
  if (mouth === 'o') { set(7, 8, 'm'); set(8, 8, 'm'); }
  if (mood === 'happy') { eyes('deeddeed'); for (const x of [6, 7, 8, 9]) set(x, 9, 'm'); }
  if (mood === 'sad') { eyes('dddddddd'); for (let i = 0; i < 8; i++) set(4 + i, 7, 'deeddeed'[i]);
                        set(5, 8 + Math.floor((t * 4) % 2), 'x'); set(10, 8 + Math.floor((t * 4 + 1) % 2), 'x'); }
  // 안테나·가슴 불빛 깜빡
  const chirping = t < CHIRP;                     // 로봇 소리 나는 동안: 안테나 빠르게 깜빡 + 입 벙긋
  if (chirping ? Math.floor(t * 16) % 2 : Math.floor(t * 3) % 2) for (const [x, y] of CH.blink) setRaw(x, y, 'A');
  if (chirping && Math.floor(t * 16) % 2) { set(7, 8, 'm'); set(8, 8, 'm'); }
  if (Math.floor(t * 1.5) % 2) for (const [x, y] of CH.chest) setRaw(x, y, CH.chest_off);
  // 팔
  const arms = {down: [[3,13],[3,14],[12,13],[12,14]], point: [[3,13],[3,14],[12,12],[13,11],[14,10]],
                wave1: [[3,13],[3,14],[13,12],[14,11],[14,10]], wave2: [[3,13],[3,14],[13,12],[13,11],[12,10]]};
  for (const [x, y] of arms[arm]) set(armX(x), y, 's');
  if (sweat) set(14, 4 + Math.floor((t * 6) % 4), 'x');
  g.clearRect(0, 0, 16, 17);
  grid.forEach((row, y) => row.forEach((ch, x) => { if (ch !== '.') { g.fillStyle = COL[ch]; g.fillRect(x, y, 1, 1); } }));
  cv.style.transform = `translate(${dx * 9}px, ${dy * 9}px)`;
  botDx = dx; botDy = dy;
  const bang = document.getElementById('bang');
  bang.style.opacity = (TYPE === 'hook' && !INTRO && t > 0.15 && t < 1.8) ? 1 : 0;
}

// ── 효과 층: 색종이(좋은 소식) / 비 + 날아가는 우산(나쁜 소식) ──
const P = 9, BX = 1080 - 170 - 144, BY = 1036;        // 픽셀 크기, 로봇 캔버스 왼쪽 위
const HAND = [BX + 14.5 * P, BY + 10.5 * P];
const FX_T0 = FXAT - INTRO, RAIN0 = FX_T0 - 0.25, GUST = FX_T0 + 1.4;   // 효과는 핵심 단어를 말하는 순간(FXAT)에 맞춘다
let botDx = 0, botDy = 0;
const fx = document.getElementById('fx'), f = fx.getContext('2d');
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed);
  x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
const R = rng(7), CONF = ['#ffd166', '#5ab0ff', '#ff7a6b', '#7bd88f', '#c792ff', '#f4f6f8'];
const confetti = MOOD !== 'good' ? [] : Array.from({length: 150}, (_, i) => {
  const second = i >= 95, ang = (100 + R() * 70) * Math.PI / 180, sp = (second ? 1200 : 1700) + R() * 1100;
  return {t0: FX_T0 + (second ? 0.8 : 0) + R() * 0.08, vx: Math.cos(ang) * sp, vy: -Math.sin(ang) * sp, k: 1.8 + R() * 1.0,
          col: CONF[Math.floor(R() * CONF.length)], rot: R() * 6.28, rs: 5 + R() * 9, ph: R() * 6.28, sw: 25 + R() * 60, tall: R() < 0.5};
});
const G = 1500;    // 중력(px/s²). 공기 저항 k 때문에 종이는 천천히 떨어지며 하늘하늘 흔들린다
function drawConfetti(t) {
  for (const c of confetti) {
    const u = t - c.t0; if (u <= 0) continue;
    const e = Math.exp(-c.k * u), vt = G / c.k;
    const x = HAND[0] + c.vx * (1 - e) / c.k + c.sw * Math.sin(2 * Math.PI * 1.3 * u + c.ph) * (1 - Math.exp(-1.5 * u));
    const y = HAND[1] + vt * u + (c.vy - vt) * (1 - e) / c.k;
    if (y > 1960) continue;
    const flip = Math.abs(Math.cos(c.rot + c.rs * u));         // 뒤집히며 도는 느낌: 폭이 줄었다 늘었다
    const C = 13, w = Math.max(4, Math.round(C * flip / 4) * 4), h = c.tall ? C * 1.5 : C;   // 색종이 한 장 = 13px 도트
    f.fillStyle = c.col; f.fillRect(Math.round(x - w / 2), Math.round(y), w, h);
  }
}
const drops = MOOD !== 'bad' ? [] : Array.from({length: 170}, () => ({x: R() * 1500, sp: 1500 + R() * 700, ph: R()}));
const wind = t => t < GUST ? -160 : -160 - 700 * Math.min(1, (t - GUST) / 0.3);
const UMB = ["....rrr....", "..rrwrrwr..", ".rrrwrrwrr.", "rrrrwrrwrrr", ".....h.....", ".....h.....", ".....h.....",
             ".....h.....", ".....h.....", ".....h.....", ".....h.....", ".....hh...."];
const UP = 12;   // 우산 도트 크기 (로봇보다 살짝 크게 — 화면에서 잘 보이게)
const UCOL = {r: '#ff7a6b', w: '#ffd166', h: '#e8eef5'};
function drawUmbrella(x, y, th) {
  f.save(); f.translate(Math.round(x), Math.round(y)); f.rotate(th);
  UMB.forEach((row, r) => [...row].forEach((ch, c) => { if (ch !== '.') { f.fillStyle = UCOL[ch]; f.fillRect((c - 5) * UP, (r - 11) * UP, UP, UP); } }));
  f.restore();
}
function drawRain(t) {
  if (t < RAIN0) return;
  const fade = Math.min(1, (t - RAIN0) / 0.3);                  // 비는 서서히 들어온다
  f.fillStyle = `rgba(8,14,26,${0.22 * fade})`; f.fillRect(0, 0, 1080, 1920);
  f.fillStyle = `rgba(126,200,255,${0.55 * fade})`;
  for (const d of drops) {
    const cyc = 2100 / d.sp, u = ((t + d.ph * cyc) % cyc), y = -100 + d.sp * u, x = d.x + wind(t) * u * 0.7;
    const sx = wind(t) / d.sp;                                  // 바람 방향으로 기운 빗줄기
    for (let k = 0; k < 3; k++) f.fillRect(Math.round(x - sx * k * 12), Math.round(y - k * 12), 4, 10);
  }
  const theta0 = -0.35;
  if (t < GUST) {                                               // 바람에 흔들리다 점점 세게 펄럭
    const shake = t > GUST - 0.6 ? 0.28 * Math.sin(t * 30) * (t - (GUST - 0.6)) / 0.6 : 0;
    drawUmbrella(HAND[0] + botDx * P, HAND[1] + botDy * P, theta0 + 0.07 * Math.sin(t * 6) + shake);
  } else {                                                      // 돌풍: 위로 떠올라 빙글빙글 날아감
    const u = t - GUST;
    drawUmbrella(HAND[0] - 650 * u - 300 * u * u, HAND[1] - 950 * u + 260 * u * u, theta0 - 9 * u);
  }
}
// ── 채널 오프닝: 귀여운 행동(종류별) → 뚝 멈춤 "앗!" → 허둥지둥 자리로 슝 → 콩 → 브리핑 ──
// IK: bignews(헉! 데이터 글자) / dance(댄스 비트) / fly(새처럼 파닥) / rocket(아이언맨 공중부양)
const HOME = [BX + 72, BY + 76.5], MID = [540, 980], BIG = 4.2;
const D0 = INTRO - 0.5;                                   // 자리로 출발하는 시각 (슝 0.35초 + 콩 0.15초)
const M = IK === 'bignews' ? D0 : D0 - 0.22;              // 행동이 뚝 끊기는 시각 (그 뒤 0.22초 얼음)
const BEAT = 60 / 128;                                    // 댄스 비트 128BPM
const easeInBack = x => { const c = 1.9; return (c + 1) * x * x * x - c * x * x; };
const clamp01 = x => Math.min(1, Math.max(0, x));
function actPose(t) {                                     // 행동 중 로봇 위치·크기·기울기
  if (IK === 'dance') {
    const b = t / BEAT, sq = Math.exp(-(b % 1) * 7);      // 박자마다 쿵: 살짝 눌렸다 펴짐
    return {x: MID[0] + 45 * Math.sin(Math.PI * b), y: MID[1] + 22 * sq, sx: BIG * (1 + 0.07 * sq), sy: BIG * (1 - 0.07 * sq), rot: 10 * Math.sin(Math.PI * b)};
  }
  if (IK === 'fly') {
    const up = 140 * clamp01(t / 0.35);
    return {x: MID[0] + 35 * Math.sin(2 * Math.PI * 0.7 * t), y: MID[1] - up + 38 * Math.sin(2 * Math.PI * 1.8 * t),
            sx: BIG, sy: BIG, rot: 6 * Math.sin(2 * Math.PI * 1.8 * t + 1)};
  }
  if (IK === 'rocket') {
    const up = 230 * (1 - Math.pow(1 - clamp01(t / 1.2), 2));
    return {x: MID[0] + 3 * Math.sin(t * 33), y: MID[1] - up + 5 * Math.sin(t * 41), sx: BIG, sy: BIG, rot: 4 * Math.sin(t * 6)};
  }
  if (IK === 'cart') {                                   // 카트 타고 질주 → 끼이익 급정거
    const p = 1 - Math.pow(1 - clamp01(t / 0.75), 3), ride = t < 0.75;
    const lean = t >= 0.75 ? -12 * Math.exp(-(t - 0.75) * 5) * Math.cos((t - 0.75) * 18) : 8;
    return {x: -320 + (MID[0] + 320) * p, y: MID[1] - 60 + (ride ? 7 * Math.sin(t * 45) : 0), sx: BIG, sy: BIG, rot: lean};
  }
  if (IK === 'textflood') {                              // 자막 상자에 파묻혔다가 뽁! 튀어나옴
    const u = clamp01((t - 1.25) / 0.15);
    return {x: MID[0], y: MID[1] - 400 * (1 - Math.pow(1 - u, 2)) + (t > 1.4 ? 10 * Math.sin((t - 1.4) * 20) * Math.exp(-(t - 1.4) * 6) : 0), sx: BIG, sy: BIG, rot: 0};
  }
  if (IK === 'outfit') {                                 // 패션쇼: 찰칵마다 포즈 반대로
    const li = Math.min(3, Math.floor(t / 0.4)), snap = Math.exp(-(t % 0.4) * 14);
    return {x: MID[0], y: MID[1] - 8 * snap, sx: BIG, sy: BIG, rot: li % 2 ? 7 : -7};
  }
  if (IK === 'siren' && t > 0.85) return {x: MID[0] + (Math.floor(t * 30) % 2 ? 6 : -6), y: MID[1], sx: BIG, sy: BIG, rot: 0};
  if (IK === 'slot' && t > 1.3) return {x: MID[0], y: MID[1], sx: BIG, sy: BIG, rot: 9 * clamp01((t - 1.3) / 0.1)};   // 갸우뚱
  if (IK === 'magnifier' && t > 1.05 && t < 1.2) return {x: MID[0] + (Math.floor(t * 40) % 2 ? 8 : -8), y: MID[1], sx: BIG, sy: BIG, rot: 0};  // 쾅!
  if (IK === 'lightbulb' && t > 0.8 && t < 1.15) return {x: MID[0], y: MID[1] - 60 * Math.sin(Math.PI * (t - 0.8) / 0.35), sx: BIG, sy: BIG, rot: 0};  // 띵! 깡총
  if (IK === 'unbox' && t < 0.7) return {x: MID[0] + (Math.floor(t * 20) % 2 ? 6 : -6), y: MID[1], sx: BIG, sy: BIG, rot: 0};   // 상자 흔들기
  if (['adpop', 'siren', 'slot', 'magnifier', 'receipt', 'fireworks', 'lightbulb', 'unbox'].includes(IK)) return {x: MID[0], y: MID[1] + 6 * Math.sin(t * 4), sx: BIG, sy: BIG, rot: 0};
  const pop = t > 0.45 ? 1 + 0.14 * Math.exp(-(t - 0.45) * 9) * Math.cos((t - 0.45) * 30) : 1;   // bignews: 헉! 움찔
  const shake = (t > 0.45 && t < 0.7) ? (Math.floor(t * 40) % 2 ? 7 : -7) : 0;
  return {x: MID[0] + shake, y: MID[1], sx: BIG * pop, sy: BIG * pop, rot: 0};
}
function introState(t) {
  if (t < M) return actPose(t);
  if (t < D0) {                                           // 뚝! 그 자세로 얼음 (로켓은 불 꺼져 툭 떨어짐)
    const st = {...actPose(M - 1e-3)}, u = t - M;
    if (IK === 'rocket') st.y += 0.5 * 2600 * u * u;
    if (IK === 'fly') st.y += 0.5 * 1400 * u * u;
    st.x += Math.floor(t * 50) % 2 ? 4 : -4;
    return st;
  }
  const from = introState(D0 - 1e-3);
  if (t < D0 + 0.35) {                                    // 슝: 살짝 뒤로 뺐다가(어설픈 출발) 자리로 휙
    const p = easeInBack((t - D0) / 0.35), sc = BIG + (1 - BIG) * clamp01(p);
    return {x: from.x + (HOME[0] - from.x) * p, y: from.y + (HOME[1] - from.y) * p, sx: sc, sy: sc, rot: from.rot * (1 - clamp01(p))};
  }
  const q = (t - D0 - 0.35) / 0.3, wob = Math.exp(-q * 4) * Math.cos(q * 14);      // 콩: 찌그러졌다 출렁
  return {x: HOME[0], y: HOME[1] + 6 * wob, sx: 1 + 0.25 * wob, sy: 1 - 0.25 * wob, rot: 0};
}
// 도트 영문 서체 5x7 (직접 그림 — 외부 서체 없음). 가독성보다 '데이터가 쏟아지는' 분위기용
const FONT = {A:'01110100011000111111100011000110001',B:'11110100011000111110100011000111110',C:'01110100011000010000100001000101110',
D:'11110100011000110001100011000111110',E:'11111100001000011110100001000011111',F:'11111100001000011110100001000010000',
G:'01110100011000010111100011000101111',H:'10001100011000111111100011000110001',I:'01110001000010000100001000010001110',
J:'00111000100001000010000101001001100',K:'10001100101010011000101001001010001',L:'10000100001000010000100001000011111',
M:'10001110111010110101100011000110001',N:'10001110011010110011100011000110001',O:'01110100011000110001100011000101110',
P:'11110100011000111110100001000010000',Q:'01110100011000110001101011001001101',R:'11110100011000111110101001001010001',
S:'01111100001000001110000010000111110',T:'11111001000010000100001000010000100',U:'10001100011000110001100011000101110',
V:'10001100011000110001100010101000100',W:'10001100011000110101101011010101010',X:'10001100010101000100010101000110001',
Y:'10001100010101000100001000010000100',Z:'11111000010001000100010001000011111',0:'01110100011001110101110011000101110',
1:'00100011000010000100001000010001110',2:'01110100010000100010001000100011111',3:'11110000010000101110000010000111110',
4:'00010001100101010010111110001000010',5:'11111100001111000001000011000101110',6:'00110010001000011110100011000101110',
7:'11111000010001000100010000100001000',8:'01110100011000101110100011000101110',9:'01110100011000101111000010001001100',
'!':'00100001000010000100001000000000100','♪':'00110001010010000100011001110011000','?':'01110100010000100010001000000000100'};
const ITXT = document.getElementById('news').textContent.toUpperCase();
const LR = rng(11), LCOL = ['#ffd166', '#5ae0ff', '#f4f6f8'];
const LETTERS = (() => {
  if (!INTRO || IK !== 'bignews') return [];
  const out = [], chars = [...ITXT], sizes = chars.map(() => 12 + Math.floor(LR() * 14));
  let width = chars.reduce((a, ch, i) => a + (ch === ' ' ? 34 : sizes[i] * 6.2), 0);
  const k = Math.min(1, 960 / width); let x = 540 - width * k / 2;
  chars.forEach((ch, i) => {                         // 큰 글자: BIG NEWS! — 크기·높이 제각각
    if (ch === ' ') { x += 34 * k; return; }
    const sz = Math.max(5, Math.round(sizes[i] * k));
    out.push({ch, x, y: MID[1] - 520 - 3.5 * sz + (LR() - 0.5) * 80, s: sz, col: LCOL[i % 3], a: 1, at: 0.45 + out.length * 0.03, seed: i * 17});
    x += sz * 6.2;
  });
  const pool = [...ITXT.replace(/[^A-Z0-9]/g, '')] .concat(['0', '1', '0', '1']);
  for (let i = 0; i < 36; i++) {                     // 작은 글자·0/1: 로봇 둘레에 데이터처럼 흩뿌림
    const ang = LR() * Math.PI * 2, rad = 300 + LR() * 240, sz = 4 + Math.floor(LR() * 7);
    const xx = Math.min(1020, Math.max(30, 540 + Math.cos(ang) * rad)), yy = Math.min(1560, Math.max(250, MID[1] + Math.sin(ang) * rad * 1.15));
    out.push({ch: pool[Math.floor(LR() * pool.length)], x: xx, y: yy, s: sz, col: LCOL[Math.floor(LR() * 3)], a: 0.3 + LR() * 0.6,
              at: 0.45 + LR() * 0.3, seed: 100 + i * 31});
  }
  return out;
})();
function drawGlyph(ch, x, y, s, dissolve, seed, ctx = f) {
  const bits = FONT[ch]; if (!bits) return;
  const gp = Math.max(1, Math.round(s * 0.18));     // 점 사이 틈 → 전광판 도트 느낌
  for (let i = 0; i < 35; i++) {
    if (bits[i] !== '1') continue;
    if (dissolve && ((i * 131 + seed * 977) % 100) / 100 < dissolve) continue;   // 사라질 때 도트가 부서지듯
    ctx.fillRect(Math.round(x + (i % 5) * s), Math.round(y + Math.floor(i / 5) * s), s - gp, s - gp);
  }
}
function drawLetters(t) {
  const e = Math.min(1, Math.max(0, (t - D0 - 0.05) / 0.27));     // 로봇 출발 → 바깥으로 흩어지며 소멸
  for (const L of LETTERS) {
    const u = t - L.at; if (u < 0 || e >= 1) continue;
    if (u < 0.15 && Math.floor(t * 40 + L.seed) % 3 === 0) continue;                // 등장할 때 지지직
    let x = L.x, y = L.y;
    if (Math.floor(t * 25 + L.seed) % 13 === 0) x += 14;                              // 가끔 옆으로 튐(글리치)
    const cx = x + L.s * 2.5, cy = y + L.s * 3.5;
    x += (cx - MID[0]) * e * 0.9; y += (cy - MID[1]) * e * 0.9;
    f.globalAlpha = L.a * (1 - e); f.fillStyle = L.col;
    drawGlyph(L.ch, x, y, u < 0.06 ? Math.round(L.s * 1.3) : L.s, e, L.seed);
  }
  f.globalAlpha = 1;
}

// 로봇 픽셀(col,row) → 화면 좌표 (기울기는 무시 — 소품 위치용)
const SP = (st, c, r) => [st.x + (c + 0.5 - 8) * 9 * st.sx, st.y + (r + 0.5 - 8.5) * 9 * st.sy];
const IR = rng(23);
const NOTES = Array.from({length: 10}, (_, i) => ({x: 120 + IR() * 840, y: 520 + IR() * 700, beat: i % 4, s: 13 + Math.floor(IR() * 8),
                                                 col: ['#ffd166', '#5ae0ff', '#ff7a6b', '#c792ff'][i % 4]}));
const FEATHERS = Array.from({length: 12}, () => ({t0: IR() * 1.3, dx: (IR() - 0.5) * 300, ph: IR() * 6.28}));
const WING = ["....ww", "..wwws", "wwwwss", ".wwss.", "..ss.."];          // 왼쪽 날개 (오른쪽은 좌우 반전)
function wing(st, up, side) {
  const q = 9 * st.sx, [ax, ay] = SP(st, side < 0 ? 2 : 13, 11);
  WING.forEach((row, r) => [...row].forEach((ch, c) => {
    if (ch === '.') return;
    const cx = side < 0 ? ax - (6 - c) * q : ax + (c + 1) * q, cy = up ? ay - (5 - r) * q : ay + (r - 1) * q;
    f.fillStyle = ch === 'w' ? '#e8eef5' : '#9fb0c3'; f.fillRect(Math.round(cx), Math.round(cy), Math.ceil(q), Math.ceil(q));
  }));
}
function hashf(a, b) { const x = Math.sin(a * 12.9898 + b * 78.233) * 43758.5453; return x - Math.floor(x); }
function drawAct(t, st) {
  if (IK === 'siren' && t >= 0.85 && t < M) {                               // 삐뽀삐뽀 빨강·파랑
    const red = Math.floor((t - 0.85) / 0.18) % 2 === 0;
    f.fillStyle = red ? 'rgba(255,60,60,0.3)' : 'rgba(60,120,255,0.3)'; f.fillRect(0, 0, 1080, 1920);
    f.fillStyle = red ? 'rgba(255,90,90,0.35)' : 'rgba(90,150,255,0.35)';
    for (let k = 0; k < 6; k++) f.fillRect(red ? k * 40 : 1080 - (k + 1) * 40, 0, 40, 1920 - k * 220);
  }
  if (IK === 'cart') {
    const q = 9 * st.sx * 0.9, [x0, y0] = EDGE(st, 0, 16.6);
    spr(f, Math.floor(t * 20) % 2 ? CART : CART2, CARTPAL, x0, y0, q);
    if (t < 0.75) { f.fillStyle = 'rgba(232,238,245,0.5)';                 // 속도선
      for (let k = 0; k < 8; k++) { const len = 120 + hashf(k, 2) * 260; f.fillRect(Math.round(st.x - 330 - len - hashf(k, 3) * 220), Math.round(650 + hashf(k, 1) * 750), Math.round(len), 10); } }
    if (t >= 0.75 && t < 1.05) { f.fillStyle = '#ffd166';                  // 바퀴 불꽃
      for (let k = 0; k < 8; k++) f.fillRect(Math.round(x0 + 2 * q + hashf(k, Math.floor(t * 30)) * 12 * q), Math.round(y0 + 9 * q + hashf(Math.floor(t * 30), k) * 40), 12, 12); }
  }                                  // 행동 중 소품: 디스코 / 날개·깃털 / 제트 불꽃·연기
  if (IK === 'dance' && t < M) {
    const b = Math.floor(t / BEAT), ph = (t / BEAT) % 1, cols = ['#ffd166', '#5ae0ff', '#ff7a6b', '#7bd88f', '#c792ff'];
    for (let k = 0; k < 12; k++) {                        // 바닥 타일이 박자마다 색 바뀜
      f.globalAlpha = 0.55 * (1 - 0.5 * ph); f.fillStyle = cols[(k + b) % 5]; f.fillRect(k * 90 + 4, MID[1] + 420, 82, 46);
    }
    for (let k = 0; k < 3; k++) {                         // 위에서 내려오는 조명
      f.globalAlpha = 0.16 * (1 - ph); f.fillStyle = cols[(b + k * 2) % 5]; f.fillRect(((b * 3 + k * 4) % 10) * 108, 0, 108, MID[1] + 420);
    }
    f.globalAlpha = 1;
    for (const n of NOTES) if (b % 4 === n.beat || (b + 2) % 4 === n.beat) {   // ♪ 가 박자에 맞춰 떠오름
      f.fillStyle = n.col; drawGlyph('♪', n.x, n.y - ph * 60, n.s, 0, 1);
    }
  }
  if (IK === 'fly' && t < M) {
    const up = Math.floor(t * 14) % 2 === 0;               // 파닥파닥
    wing(st, up, -1); wing(st, up, 1);
    for (const fe of FEATHERS) {                           // 깃털이 하늘하늘
      const u = t - fe.t0; if (u < 0 || u > 1.2) continue;
      const [x0, y0] = SP(st, 8, 12);
      f.fillStyle = `rgba(232,238,245,${1 - u / 1.2})`;
      f.fillRect(Math.round(x0 + fe.dx * u + 30 * Math.sin(u * 7 + fe.ph)), Math.round(y0 + 160 * u), 12, 8);
    }
  }
  if (IK === 'fly' && t >= M && t < M + 0.18) {             // 날개가 펑 사라짐
    const u = (t - M) / 0.18;
    for (const side of [-1, 1]) { const [x0, y0] = SP(st, side < 0 ? 0 : 15, 10);
      f.fillStyle = `rgba(200,210,225,${1 - u})`;
      for (let k = 0; k < 8; k++) f.fillRect(Math.round(x0 + Math.cos(k * 0.8) * 90 * u), Math.round(y0 + Math.sin(k * 0.8) * 90 * u), 14, 14); }
  }
  if (IK === 'rocket') {
    const q = Math.round(9 * st.sx), fr = Math.floor(t * 30);
    if (t < M) for (const c of [5.5, 9.5]) {               // 발에서 불꽃 (매 프레임 길이가 일렁)
      const [fx0, fy0] = SP(st, c, 16.5), len = 4 + Math.floor(hashf(fr, c) * 4);
      for (let k = 0; k < len; k++) {
        f.fillStyle = k === 0 ? '#fff3b0' : k < 2 ? '#ffd166' : k < 4 ? '#ff9f43' : '#ff7a6b';
        const w = Math.max(q * 0.5, q * (1.6 - k * 0.25));
        f.fillRect(Math.round(fx0 - w / 2), Math.round(fy0 + k * q), Math.round(w), q);
      }
    }
    for (let i = 0; i < 26; i++) {                          // 연기: 불꽃 아래로 퍼지며 옅어짐
      const t0 = i * 0.06, u = t - t0; if (u < 0 || u > 0.9 || t0 > M) continue;
      const p0 = actPose(t0), [sx0, sy0] = SP(p0, i % 2 ? 5.5 : 9.5, 16.5), d = (hashf(i, 3) - 0.5) * 2;
      const sz = 14 + u * 40;
      f.fillStyle = `rgba(150,160,175,${0.5 * (1 - u / 0.9)})`;
      f.fillRect(Math.round(sx0 + d * 140 * u - sz / 2), Math.round(sy0 + 5 * q + 200 * u), Math.round(sz), Math.round(sz));
    }
  }
}

const tg = document.getElementById('topfx').getContext('2d');
const EDGE = (st, c, r) => [st.x + (c - 8) * 9 * st.sx, st.y + (r - 8.5) * 9 * st.sy];      // 로봇 픽셀 칸의 왼쪽 위
function spr(ctx, rows, pal, x, y, q) { rows.forEach((row, r) => [...row].forEach((ch, c) => { if (ch !== '.') {
  ctx.fillStyle = pal[ch]; ctx.fillRect(Math.round(x + c * q), Math.round(y + r * q), Math.ceil(q), Math.ceil(q)); } })); }
function withRot(st, fn) { tg.save(); tg.translate(st.x, st.y); tg.rotate((st.rot || 0) * Math.PI / 180); tg.translate(-st.x, -st.y); fn(); tg.restore(); }
const LOOKS = [{body: 'n'}, {body: 'w', bow: true, glasses: true}, {body: 'y', hat: 'top'}, {body: 'p', hat: 'cap', glasses: true}];
const HAT_TOP = ["..BBBB..", "..BBBB..", "..BBBB..", "..cccc..", "BBBBBBBB"], HAT_CAP = ["..gggggg..", ".gggggggg.", "gggggggggggg"];
const HATPAL = {B: '#05070a', c: '#ff7a6b', g: '#7bd88f'};
const ADS = [{at: 0.15, x: 200, y: 560, side: -1}, {at: 0.5, x: 860, y: 680, side: 1}, {at: 0.85, x: 190, y: 1200, side: -1}, {at: 1.25, side: 0}];
const BOOK = ["bbbbbbbbbbbb", "bwwwwwbwwwwb", "bwwwwwbwwwwb", "bwwwwwbwwwwb", "bbbbbbbbbbbb"], BOOKPAL = {b: '#8b5a2b', w: '#f4f6f8'};
const BOXES = Array.from({length: 10}, (_, i) => ({at: 0.08 + i * 0.1, x: MID[0] + (IR() - 0.5) * 240, w: 320 + Math.floor(IR() * 360),
                                                   ty: 1320 - (i + 1) * 70, vx: (IR() - 0.5) * 2400, vy: -700 - IR() * 500, hot: IR() < 0.3}));
const CART = ["k...............", ".kkkkkkkkkkkkkk.", ".k.k.k.k.k.k.kk.", ".kkkkkkkkkkkkkk.", "..k.k.k.k.k.k.k.", "..kkkkkkkkkkkkk.",
              "...k........k...", "..kkkkkkkkkkk...", "..oo........oo.."];
const CART2 = CART.slice(0, 8).concat(["..OO........OO.."]), CARTPAL = {k: '#9fb0c3', o: '#4a5a70', O: '#7a8aa0'};
const SYMS = ['7', 'A', 'I', '?', '!', 'B'];
function adBox(x, y, rot, sc) {
  tg.save(); tg.translate(x, y); tg.rotate(rot); tg.scale(sc, sc);
  tg.fillStyle = '#1a1300'; tg.fillRect(-123, -73, 246, 146); tg.fillStyle = '#ffd166'; tg.fillRect(-115, -65, 230, 130);
  tg.fillStyle = '#1a1300'; drawGlyph('A', -66, -42, 12, 0, 1, tg); drawGlyph('D', 6, -42, 12, 0, 1, tg); drawGlyph('X', 88, -58, 4, 0, 1, tg);
  tg.restore();
}
function drawTop(t, st) {
  const q = 9 * st.sx;
  if (IK === 'outfit' && t < M) {
    const L = LOOKS[Math.min(3, Math.floor(t / 0.4))], [hx, hy] = EDGE(st, 4, 3);
    withRot(st, () => { if (L.hat === 'top') spr(tg, HAT_TOP, HATPAL, hx, hy - 5 * q, q); if (L.hat === 'cap') spr(tg, HAT_CAP, HATPAL, hx - q, hy - 3 * q, q); });
    const fl = 1 - (t % 0.4) / 0.08;                                        // 찰칵 플래시
    if (fl > 0) { tg.fillStyle = `rgba(255,255,255,${0.55 * fl})`; tg.fillRect(0, 0, 1080, 1920); }
  }
  if (IK === 'adpop') for (const d of ADS) {
    const u = t - d.at; if (u < 0) continue;
    let x, y, rot = 0;
    if (d.side) { x = d.x; y = d.y; const v = u - 0.25; if (v > 0) { x += d.side * 2400 * v; y += -600 * v + 1500 * v * v; rot = d.side * 8 * v; } }
    else { [x, y] = SP(st, 8, 7); if (t >= D0) { const v = t - D0; y += 1500 * v * v; rot = 2 * v; } }    // 마지막 광고는 얼굴에 철썩
    if (x < -300 || x > 1380 || y > 2100) continue;
    adBox(x, y, rot, u < 0.1 ? 0.6 + 4 * u : 1);
  }
  if (IK === 'siren' && t < 0.85) withRot(st, () => {
    const [bx, by] = EDGE(st, 2, 11);
    spr(tg, BOOK, BOOKPAL, bx, by, q);
    tg.fillStyle = '#4a5a70';
    for (let k = 0; k < Math.floor(clamp01(t / 0.8) * 6); k++)               // 사각사각 써지는 줄
      tg.fillRect(Math.round(bx + 7.3 * q), Math.round(by + (1.3 + Math.floor(k / 2)) * q + (k % 2) * q * 0.5), Math.round(q * (k % 2 ? 1.8 : 2.8)), Math.round(q * 0.25));
    const pp = clamp01(t / 0.8);
    tg.fillStyle = '#ffd166'; tg.fillRect(Math.round(bx + (7.5 + (pp * 9) % 3) * q), Math.round(by + (pp * 3 - 1) * q), Math.round(q * 0.5), Math.round(q * 2));
  });
  if (IK === 'textflood') for (const b of BOXES) {
    const u = t - b.at; if (u < 0) continue;
    let y = -120 + (b.ty + 120) * Math.min(1, (u / 0.22) ** 2), x = b.x, a = 1;
    if (t > 1.25) { const v = t - 1.25; x += b.vx * v; y += b.vy * v + 1600 * v * v; a = Math.max(0, 1 - v / 0.4); }
    if (a <= 0) continue;
    tg.globalAlpha = a; tg.fillStyle = '#33404f'; tg.fillRect(Math.round(x - b.w / 2), Math.round(y), b.w, 66);
    tg.fillStyle = '#18202b'; tg.fillRect(Math.round(x - b.w / 2 + 6), Math.round(y + 6), b.w - 12, 54);
    tg.fillStyle = b.hot ? '#ffd166' : '#e8eef5'; tg.fillRect(Math.round(x - b.w / 2 + 22), Math.round(y + 18), Math.round(b.w * 0.62), 12);
    tg.fillStyle = '#9aa7b4'; tg.fillRect(Math.round(x - b.w / 2 + 22), Math.round(y + 38), Math.round(b.w * 0.4), 8);
    tg.globalAlpha = 1;
  }
  if (IK === 'slot' && t < D0) withRot(st, () => {
    const [sx0, sy0] = EDGE(st, 4, 5), w = 8 * q, h = 5 * q, s = Math.floor(Math.min(w / 2 / 6, h / 8));
    tg.fillStyle = '#0f2233'; tg.fillRect(sx0, sy0, w, h); tg.fillStyle = '#4a5a70'; tg.fillRect(sx0 + w / 2 - q * 0.2, sy0, q * 0.4, h);
    for (const [k, stop, fin] of [[0, 1.0, '7'], [1, 1.25, '?']]) {         // 촤라라락 → 7 / ? 로 엇갈림
      const rx = sx0 + k * w / 2 + (w / 2 - 5 * s) / 2, base = sy0 + (h - 7 * s) / 2;
      tg.save(); tg.beginPath(); tg.rect(sx0 + k * w / 2, sy0, w / 2, h); tg.clip();
      if (t < stop) { const pos = t * 16 + k * 0.5, off = (pos % 1) * 8 * s; tg.fillStyle = '#5ae0ff';
        drawGlyph(SYMS[Math.floor(pos) % 6], rx, base - 8 * s + off, s, 0, 1, tg); drawGlyph(SYMS[(Math.floor(pos) + 1) % 6], rx, base + off, s, 0, 1, tg); }
      else { tg.fillStyle = fin === '7' ? '#ffd166' : '#ff7a6b'; drawGlyph(fin, rx, base + Math.exp(-(t - stop) * 14) * Math.cos((t - stop) * 30) * s, s, 0, 1, tg); }
      tg.restore();
    }
    const [lx, ly] = EDGE(st, 15, 6), pull = t < 0.15 ? 0 : t < 0.3 ? (t - 0.15) / 0.15 : 1 - clamp01((t - 0.3) / 0.2);
    tg.fillStyle = '#9fb0c3'; tg.fillRect(lx, ly + pull * 3 * q, q * 0.5, 4 * q - pull * 3 * q);
    tg.fillStyle = '#ff7a6b'; tg.fillRect(lx - q * 0.4, ly - q + pull * 3 * q, q * 1.3, q * 1.3);
    if (t > 1.3) { tg.fillStyle = '#ffd166'; const [qx, qy] = EDGE(st, 12, -1); for (let k = 0; k < 2; k++) if (t > 1.3 + k * 0.1) drawGlyph('?', qx + k * 70, qy - k * 50, 10, 0, 1, tg); }
  });
  if (IK === 'magnifier' && t < D0) {
    const cx = st.x + 60 + 150 * Math.sin(Math.min(t, 1.05) * 3.2), cy = st.y - 80, R = 125;
    tg.fillStyle = 'rgba(15,34,51,0.9)'; tg.beginPath(); tg.arc(cx, cy, R, 0, 6.283); tg.fill();
    tg.fillStyle = '#5ae0ff'; tg.fillRect(Math.round(cx - 45), Math.round(cy - 45), 90, 90);          // 렌즈 속 커다란 눈
    tg.fillStyle = '#e8eef5'; tg.fillRect(Math.round(cx - 45), Math.round(cy - 45), 24, 24);
    for (let a = 0; a < 40; a++) { const an = a / 40 * 6.283; tg.fillStyle = '#9fb0c3'; tg.fillRect(Math.round(cx + Math.cos(an) * R - 7), Math.round(cy + Math.sin(an) * R - 7), 14, 14); }
    tg.fillStyle = '#8b5a2b'; for (let k = 0; k < 8; k++) tg.fillRect(Math.round(cx + R * 0.72 + k * 16), Math.round(cy + R * 0.72 + k * 16), 22, 22);
    if (t > 1.05) { const u = t - 1.05, sc = u < 0.08 ? 2.2 - 15 * u : 1;      // 쾅! 판정 도장
      tg.save(); tg.translate(820, 560); tg.rotate(-0.25); tg.scale(sc, sc); tg.fillStyle = '#ff7a6b'; drawGlyph('X', -70, -98, 28, 0, 1, tg);
      tg.fillStyle = '#ffd166'; ['F', 'A', 'K', 'E', '?'].forEach((ch, i) => drawGlyph(ch, -110 + i * 46, 110, 7, 0, 1, tg)); tg.restore(); }
  }
  if (IK === 'receipt' && t < D0) withRot(st, () => {                        // 가슴에서 영수증이 지이이익
    const [cx, cy] = SP(st, 7.5, 13.5), w = 190, L = 1000 * Math.pow(clamp01(t / 1.3), 1.4);
    tg.fillStyle = '#f4f6f8'; tg.fillRect(Math.round(cx - w / 2), Math.round(cy), w, Math.round(L));
    tg.fillStyle = '#9aa7b4';
    for (let k = 0; k * 34 < L; k++) { const yy = cy + L - 30 - k * 34; if (yy < cy + 40) break;
      [...String(Math.floor(hashf(k, 7) * 900000 + 100000))].forEach((d, i) => drawGlyph(d, cx - w / 2 + 14 + i * 28, yy, 4, 0, 1, tg)); }
    if (t > 1.3) { tg.fillStyle = '#ff7a6b'; [...'999999'].forEach((d, i) => drawGlyph(d, cx - w / 2 + 12 + i * 29, cy + 6, 5, 0, 1, tg)); }
  });
}

const FW = [0.1, 0.55, 1.0].map((at, i) => ({at, x: [300, 780, 540][i], y: [430, 380, 300][i], col: ['#ffd166', '#5ae0ff', '#ff7a6b'][i],
  parts: Array.from({length: 26}, (_, k) => ({a: k / 26 * 6.283 + IR() * 0.2, v: 380 + IR() * 260}))}));
const BULB = ["..yyy..", ".yyyyy.", "yyywyyy", "yyyyyyy", ".yyyyy.", "..yyy..", "..sss..", "..sss.."], BULBOFF = BULB.map(r => r.replace(/[yw]/g, 'o'));
const BOX = ["bbbbbbbbbbbb", "bbbbbtbbbbbb", "bbbbbtbbbbbb", "bbbbbtbbbbbb", "bbbbbbbbbbbb"], LID = ["BBBBBBBBBBBB"];
const GADGET = ["kkkkkk", "kcccck", "kcwcck", "kcccck", "kkkkkk", "..kk.."];
const PAL2 = {y: '#ffd166', w: '#ffffff', s: '#9fb0c3', o: '#4a5a70', b: '#b07a45', B: '#8b5a2b', t: '#e8d3a8', k: '#4a5a70', c: '#5ae0ff'};
function drawGenreIntro(t, st) {
  const q = 9 * st.sx;
  if (IK === 'fireworks' && t < D0) for (const fw of FW) {              // 피융~ 펑! 픽셀 불꽃
    const u = t - fw.at; if (u < 0) continue;
    const [hx, hy] = SP(st, 1, 10);
    if (u < 0.35) { const p = u / 0.35, x = hx + (fw.x - hx) * p, y = hy + (fw.y - hy) * (1 - (1 - p) ** 2);
      tg.fillStyle = '#ffd166'; tg.fillRect(Math.round(x - 7), Math.round(y - 7), 14, 14);
      tg.fillStyle = 'rgba(255,209,102,0.4)'; tg.fillRect(Math.round(x - 4), Math.round(y + 10), 8, 30); continue; }
    const v = u - 0.35, a = Math.max(0, 1 - v / 0.9);
    tg.globalAlpha = a; tg.fillStyle = fw.col;
    for (const pt of fw.parts) tg.fillRect(Math.round(fw.x + Math.cos(pt.a) * pt.v * v * Math.exp(-v * 1.5)), Math.round(fw.y + Math.sin(pt.a) * pt.v * v * Math.exp(-v * 1.5) + 220 * v * v), 14, 14);
    tg.globalAlpha = 1;
  }
  if (IK === 'lightbulb' && t < D0) {                                       // 흠... → 띵! 전구
    const [bx, by] = EDGE(st, 5.5, -9), lit = t >= 0.8;
    if (!lit) { tg.fillStyle = '#9aa7b4'; for (let k = 0; k < 3; k++) if (t > 0.2 + k * 0.2) tg.fillRect(Math.round(bx + k * 2.4 * q), Math.round(by + 6 * q), Math.round(q), Math.round(q)); }
    else { spr(tg, BULB, PAL2, bx, by, q);
      if (Math.floor(t * 12) % 2 || t < 1.0) { tg.fillStyle = '#ffd166';                                 // 빛줄기
        for (let k = 0; k < 8; k++) { const an = k / 8 * 6.283, r0 = 6 * q, cx = bx + 3.5 * q, cy = by + 3 * q;
          tg.fillRect(Math.round(cx + Math.cos(an) * r0), Math.round(cy + Math.sin(an) * r0), Math.round(q), Math.round(q)); } } }
  }
  if (IK === 'unbox' && t < D0) {                                           // 달그락 → 뚜껑 열리고 뿅!
    const [bx, by] = EDGE(st, 2, 12);
    spr(tg, BOX, PAL2, bx, by, q);
    if (t < 0.85) spr(tg, LID, PAL2, bx, by - q, q);
    else { const v = t - 0.85;                                                // 뚜껑은 위로 휙 날아가고
      tg.save(); tg.globalAlpha = Math.max(0, 1 - v / 0.3); tg.translate(bx + 6 * q, by - q - 900 * v); tg.rotate(-6 * v); spr(tg, LID, PAL2, -6 * q, 0, q); tg.restore();
      const u = t - 0.9; if (u > 0) { const yy = by - (u < 0.25 ? u / 0.25 * 17 : 17) * q;   // 제품은 머리 위로 뿅
        tg.fillStyle = 'rgba(255,240,180,0.28)'; tg.beginPath(); tg.moveTo(bx + 2 * q, by); tg.lineTo(bx + 10 * q, by); tg.lineTo(bx + 13 * q, by - 19 * q); tg.lineTo(bx - q, by - 19 * q); tg.fill();
        spr(tg, GADGET, PAL2, bx + 3 * q, yy, q);
        if (Math.floor(t * 10) % 2) { tg.fillStyle = '#ffd166'; for (const [dx, dy] of [[-1.5, -1], [7, 0], [-1, 5], [7.5, 6]]) tg.fillRect(Math.round(bx + (3 + dx) * q), Math.round(yy + dy * q), Math.round(q * 0.7), Math.round(q * 0.7)); } } }
  }
}
// 장르 소품: 같은 로봇에 소품만 바꿔 '같은 회사의 다른 채널'로 보이게
const ACCS = {
  party:   {at: [9, -3], rows: ["..w..", "..p..", ".pyp.", ".ypy.", "pypyp"], pal: {w: '#ffffff', p: '#ff8fb1', y: '#ffd166'}},
  headset: {at: [1, 2], rows: [".kkkkkkkkkkkk.", "k............k", "k............k", "BB..........BB", "BB..........BB", "BB..........BB", "BBk.........BB", "..k.........", "..kkk......."],
            pal: {k: '#4a5a70', B: '#1b2430'}},
  beret:   {at: [2, 0], rows: ["......k.....", "..rrrrrrrr..", ".rrrrrrrrrrr", "rrrrrrrrrrrr"], pal: {r: '#c94c4c', k: '#1b2430'}},
  apron:   {at: [5, 12], rows: ["a....a", "gggggg", "gggggg", "gGGGgg"], pal: {a: '#7bd88f', g: '#7bd88f', G: '#4fae66'}},
};
function drawAcc(st) {
  const A = ACCS[ACC]; if (!A) return;
  withRot(st, () => { const [ax, ay] = EDGE(st, A.at[0], A.at[1]); spr(tg, A.rows, A.pal, ax, ay, 9 * st.sx); });
}

function drawIntro(t) {
  const grid = BOT.map(r => r.split(''));
  const set = (x, y, ch) => { if (grid[y] && x >= 0 && x < 16 && FACE.has(BOT[y][x])) grid[y][x] = ch; };
  const setRaw = (x, y, ch) => { if (grid[y] && x >= 0 && x < 16) grid[y][x] = ch; };
  const rows = (ys, pat) => { for (const y of ys) pat.split('').forEach((ch, i) => set(4 + i, y, ch)); };
  const shock = () => { rows([5, 6], 'deeddeed'); rows([7], 'dddddddd'); rows([8, 9], 'dddmmddd'); set(5, 5, 'w'); set(9, 5, 'w'); set(14, 4, 'x'); };
  let arms = [[3,13],[3,14],[12,13],[12,14]];
  if (t >= D0) rows([6, 7], 'ddeeddee');                                                     // 자리 쪽을 보며 출발
  else if (t >= M) { shock(); arms = [[2,12],[1,11],[13,12],[14,11]]; }                      // 뚝! 앗!
  else if (IK === 'dance') {
    rows([6, 7], 'deeddeed'); for (const x of [6, 7, 8, 9]) set(x, 9, 'm');                  // 신난 얼굴
    arms = Math.floor(t / BEAT) % 2 ? [[2,12],[1,11],[1,10],[12,13],[12,14]] : [[3,13],[3,14],[13,12],[14,11],[14,10]];
  } else if (IK === 'fly') { rows([6, 7], 'dddddddd'); rows([7], 'deeddeed'); arms = []; }   // 눈 감고 ^^ (팔 대신 날개)
  else if (IK === 'rocket') { rows([6], 'deeddeed'); rows([7], 'dddddddd'); arms = [[3,13],[3,14],[3,15],[12,13],[12,14],[12,15]]; }  // 비장한 눈, 팔 쭉
  else if (IK === 'outfit') {
    const L = LOOKS[Math.min(3, Math.floor(t / 0.4))];
    for (const y of [13, 14]) for (let x = 5; x <= 10; x++) if (grid[y][x] === 'w') grid[y][x] = L.body;     // 셔츠 색
    if (L.glasses) { rows([6, 7], 'dBBddBBd'); set(5, 6, 'w'); set(9, 6, 'w'); } else rows([6, 7], 'deeddeed');
    if (L.bow) for (const x of [6, 7, 8, 9]) set(x, 12, 'c');                                                  // 나비넥타이
    for (const x of [7, 8]) set(x, 9, 'm');
    arms = Math.floor(t / 0.4) % 2 ? [[3,13],[3,14],[13,12],[14,11],[14,10]] : [[2,12],[1,11],[1,10],[12,13],[12,14]];
  } else if (IK === 'adpop') {
    const a = ADS.filter(d => t >= d.at).pop();
    rows([6, 7], !a ? 'deeddeed' : a.side < 0 ? 'eeddeedd' : a.side > 0 ? 'ddeeddee' : 'deeddeed');
    const sw = ADS.find(d => d.side && t >= d.at + 0.25 && t < d.at + 0.37);                                    // 퍽! 쳐내기
    if (sw) arms = sw.side < 0 ? [[2,12],[1,11],[0,11],[12,13],[12,14]] : [[3,13],[3,14],[13,12],[14,11],[15,11]];
  } else if (IK === 'siren') {
    if (t < 0.85) { rows([6], 'dddddddd'); rows([7, 8], 'deeddeed'); arms = [[3,13],[3,14],[12,13],[11,14]]; }  // 일기 쓰는 중(아래 봄)
    else { shock(); arms = []; }                                                                               // 일기장 등 뒤로 숨김
  } else if (IK === 'textflood') {
    if (t < 1.25) { rows([6, 7], 'deeddeed'); rows([9], 'ddmddmdd'); }
    else { shock(); arms = [[2,12],[1,11],[13,12],[14,11]]; }                                                  // 푸하!
  } else if (IK === 'cart') {
    if (t < 0.75) { rows([6, 7], 'deeddeed'); for (const x of [6, 7, 8, 9]) set(x, 9, 'm'); arms = [[2,12],[1,11],[13,12],[14,11]]; }
    else { rows([6], 'dddddddd'); rows([7], 'eeeddeee'); }
  } else if (IK === 'slot') {
    arms = t < 0.15 ? [[3,13],[3,14],[13,12],[14,11],[14,10]] : [[3,13],[3,14],[13,13],[14,13]];              // 레버 당기기
  } else if (IK === 'magnifier') {
    if (t > 1.05) shock(); else rows([6, 7], Math.sin(t * 3.2) > 0 ? 'ddeeddee' : 'eeddeedd');
    arms = [[3,13],[3,14],[13,12],[14,11],[14,10]];
  } else if (IK === 'receipt') {
    if (t < 0.7) { rows([6], 'dddddddd'); rows([7, 8], 'deeddeed'); }
    else if (t < 1.3) rows([5, 6, 7], 'deeddeed');                                                            // 점점 커지는 눈
    else shock();
  }
  else if (IK === 'fireworks') {
    rows([6], 'deeddeed'); rows([7], 'dddddddd'); for (const x of [6, 7, 8, 9]) set(x, 9, 'm');             // 위를 보며 신남
    const c = ['#ffd166', '#5ae0ff', '#ff7a6b'][Math.floor(t / 0.45) % 3];
    if (Math.floor(t * 10) % 2) { set(5, 6, 'w'); set(9, 6, 'w'); }                                        // 눈에 불꽃 반짝
    arms = [[2,12],[1,11],[1,10],[12,13],[12,14]];
  } else if (IK === 'lightbulb') {
    if (t < 0.8) rows([5, 6], 'eeddeedd'); else { rows([6, 7], 'deeddeed'); for (const x of [6, 7, 8, 9]) set(x, 9, 'm'); arms = [[2,12],[1,11],[13,12],[14,11]]; }
  } else if (IK === 'unbox') {
    if (t < 0.9) { rows([6], 'dddddddd'); rows([7, 8], 'deeddeed'); } else { rows([5, 6], 'deeddeed'); set(5, 5, 'w'); set(9, 5, 'w'); for (const x of [7, 8]) { set(x, 8, 'm'); set(x, 9, 'm'); } }
  }
  else if (t < 0.25) rows([6, 7], Math.floor(t * 12) % 2 ? 'eeddeedd' : 'ddeeddee');        // bignews: 두리번
  else if (t < 0.45) { rows([6, 7], 'dddddddd'); rows([5, 6], 'deeddeed'); }                 // 찌릿 — 눈이 위로
  else { shock(); arms = [[2,12],[1,11],[13,12],[14,11]]; }                                  // 헉!
  const lit = (IK === 'bignews' && t > 0.25 && t < 0.9) || (IK === 'dance' && t < M) ? Math.floor(t * 8) % 2 || IK === 'bignews' : Math.floor(t * 6) % 2;
  if (!lit) for (const [x, y] of CH.blink) setRaw(x, y, 'A');
  for (const [x, y] of arms) set(armX(x), y, 's');
  g.clearRect(0, 0, 16, 17);
  grid.forEach((row, y) => row.forEach((ch, x) => { if (ch !== '.') { g.fillStyle = COL[ch]; g.fillRect(x, y, 1, 1); } }));
  const st = introState(t);
  cv.style.transform = `translate(${st.x - HOME[0]}px, ${st.y - HOME[1]}px) rotate(${st.rot || 0}deg) scale(${st.sx}, ${st.sy})`;
  f.clearRect(0, 0, 1080, 1920);
  f.fillStyle = `rgba(4,8,14,${0.6 * (t < D0 ? 1 : Math.max(0, 1 - (t - D0) / 0.35))})`; f.fillRect(0, 0, 1080, 1920);
  drawLetters(t);
  drawAct(t, st);
  tg.clearRect(0, 0, 1080, 1920);
  if (IK !== 'outfit' || t >= D0) drawAcc(st);
  drawTop(t, st);
  drawGenreIntro(t, st);
  if (IK === 'bignews' && t > 0.25 && t < 0.9 && Math.floor(t * 20) % 2) {
    const ax = st.x + (7.5 - 8) * 9 * st.sx, ay = st.y + (0.5 - 8.5) * 9 * st.sy, Q = 14;
    f.fillStyle = '#ffd166';
    for (const sgn of [-1, 1]) for (let k = 0; k < 5; k++)                     // 지그재그 번개
      f.fillRect(Math.round(ax + sgn * (40 + k * Q) + (k % 2 ? sgn * 10 : 0)), Math.round(ay - 30 - k * Q), Q, Q);
  }
  if (t > D0 + 0.35) {                                                          // 착지 먼지
    const q = t - D0 - 0.35; f.fillStyle = `rgba(200,210,225,${Math.max(0, 1 - q / 0.15)})`;
    for (const sgn of [-1, 1]) for (let k = 0; k < 3; k++) f.fillRect(HOME[0] + sgn * (80 + q * 400 + k * 14), BY + 150 - k * 10, 10, 10);
  }
  document.querySelector('.cap').style.opacity = t < INTRO - 0.2 ? 0 : 1;
}

function drawFx(t) {
  f.clearRect(0, 0, 1080, 1920);
  if (MOOD === 'good') drawConfetti(t);
  if (MOOD === 'bad') drawRain(t);
}

window.render = (t) => {
  rv.forEach(el => {
    const p = ease((t - el.dataset.at) / 0.3);
    el.style.opacity = p; el.style.transform = `translateY(${(1 - p) * 28}px)`;
    el.querySelectorAll('mark.hl').forEach(mk => mk.style.backgroundSize = `${ease((t - el.dataset.at - 0.3) / 0.4) * 100}% 100%`);
    el.querySelectorAll('.cnt').forEach(c => c.textContent = countText(c.dataset.to, ease((t - el.dataset.at) / 0.9)));
  });
  words.forEach(w => w.classList.toggle('on', t >= w.dataset.at));
  const opening = INTRO && t < INTRO - 0.2;
  const kk = document.querySelector('.kicker'); if (kk) kk.style.visibility = opening ? 'visible' : 'hidden';
  document.querySelector('.dots').style.visibility = opening ? 'hidden' : 'visible';   // 오프닝엔 키워드만
  if (INTRO && t < INTRO) { drawIntro(t); return; }
  document.getElementById('news').style.opacity = 0;
  tg.clearRect(0, 0, 1080, 1920);
  drawBot(t - INTRO);
  drawAcc({x: HOME[0] + botDx * 9, y: HOME[1] + botDy * 9, sx: 1, sy: 1, rot: 0});
  drawFx(t - INTRO);
};
})();
"""


def _body(sc: dict) -> str:
    t, f = sc["type"], _fmt
    if t == "hook":
        size = "" if len(sc["big"]) <= 4 else ("mid" if len(sc["big"]) <= 7 else "sm")
        return f'<div class="big {size} rv">{f(sc["big"])}</div><div class="h rv">{f(sc["text"])}</div>'
    if t == "compare":
        small = any(len(r) > 9 for c in (sc["left"], sc["right"]) for r in c["rows"])

        def col(c, cls):
            return f'<div class="card {cls} rv"><div class="lab">{f(c["label"])}</div>' + "".join(
                f'<div class="row{" sm" if small else ""}">{f(r)}</div>' for r in c["rows"]) + "</div>"
        return f'<div class="cmp">{col(sc["left"], "")}{col(sc["right"], "after" if sc.get("mark_right", True) else "")}</div>'
    if t == "price":
        return (f'<div class="plan rv">{f(sc["plan"])}</div><div class="was rv">{f(sc["before"])}</div>'
                f'<div class="now rv"><span class="cnt">{html.escape(sc["after"])}</span></div>'
                f'<div class="rv"><span class="badge">{f(sc["badge"])}</span></div><div class="note rv">{f(sc["note"])}</div>')
    if t == "checklist":
        return "".join(f'<div class="card grp rv"><div class="gl {"ok" if j == 0 else "maybe"}">{f(g["label"])}</div><ul>'
                       + "".join(f"<li>{f(x)}</li>" for x in g["items"]) + "</ul></div>" for j, g in enumerate(sc["groups"]))
    if t == "warning":
        return '<div class="card warn rv"><ul>' + "".join(f"<li>{f(x)}</li>" for x in sc["items"]) + "</ul></div>"
    if t == "outro":
        return ("".join(f'<div class="dt rv"><b>{f(d)}</b><span>{f(s)}</span></div>' for d, s in sc.get("dates", []))
                + "".join(f'<div class="statl rv">· {f(x)}</div>' for x in sc.get("lines", []))
                + f'<div class="h rv" style="margin-top:20px">{f(sc["text"])}</div>')
    if t == "dates":         # 날짜 목록 (축제·일정)
        return ("".join(f'<div class="dt rv"><b>{f(d)}</b><span>{f(x)}</span></div>' for d, x in sc["dates"])
                + (f'<div class="src rv">{f(sc["note"])}</div>' if sc.get("note") else ""))
    if t == "steps":
        return "".join(f'<div class="step rv"><b>{k + 1}</b><span>{f(x)}</span></div>' for k, x in enumerate(sc["items"]))
    if t == "stat":
        return "".join(f'<div class="rv"><div class="stat{" mid" if len(st["value"]) > 6 else ""}"><span class="cnt">'
                       f'{html.escape(st["value"])}</span></div><div class="statl">{f(st["label"])}</div></div>'
                       for st in sc["stats"]) + (f'<div class="src rv">{f(sc["source"])}</div>' if sc.get("source") else "")
    if t == "quote":
        return f'<div class="quote rv">“{f(sc["quote"])}”</div><div class="qsrc rv">— {f(sc["by"])}</div>'
    raise ValueError(f"모르는 장면 종류: {t}")


def _caption(text: str) -> str:
    """자막을 어절 단위 span으로. **강조** 어절은 노란색."""
    out, inside = [], False
    for w in text.split():
        hot = inside or w.startswith("**") or "**" in w
        inside = (inside + w.count("**")) % 2 == 1   # 강조가 여러 어절에 걸쳐도 이어지게
        w = html.escape(w.replace("**", ""))
        out.append(f"<span><mark>{w}</mark></span>" if hot else f"<span>{w}</span>")
    return " ".join(out)


def _page(sc: dict, i: int, n: int, speech: float, offset: float = 0.0, chirp: float = 0.0,
          intro: float = 0.0, intro_text: str = "BIG NEWS!", fx_at: float = 0.0, keyword: str = "", ikind: str = "", acc: str = "", char: str = "ai") -> str:
    dots = "".join(f'<i class="{"on" if k == i else ""}"></i>' for k in range(n))
    js = (JS.replace("%CHAR%", json.dumps(CHARS.get(char, CHARS["ai"]))).replace("%TYPE%", json.dumps(sc["type"])).replace("%MOOD%", json.dumps(sc.get("mood", ""))).replace("%SPEECH%", f"{speech:.3f}")
          .replace("%OFFSET%", f"{offset:.3f}").replace("%CHIRP%", f"{chirp:.3f}").replace("%INTRO%", f"{intro:.3f}").replace("%FXAT%", f"{fx_at:.3f}").replace("%IKIND%", json.dumps(ikind)).replace("%ACC%", json.dumps(acc)))
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f'<div class="top"><span class="kicker">{_fmt(keyword) if intro else ""}</span><span class="dots">{dots}</span></div>'
            f'<div class="stage">{_body(sc)}</div><canvas id="fx" width="1080" height="1920"></canvas><div class="cap">{_caption(sc["narration"])}</div>'
            f'<div id="bang">!</div><div id="news">{html.escape(intro_text)}</div><canvas id="bot" width="16" height="17"></canvas><canvas id="topfx" width="1080" height="1920"></canvas>'
            f'<div class="tag">샘플 · 자료: 장면표 출처 참조</div><script>{js}</script></body></html>')


def render(spec_path: str) -> Path:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    name = Path(spec_path).stem + "-v2"
    work = OUT / name
    work.mkdir(parents=True, exist_ok=True)
    scenes = spec["scenes"]

    # 1) 음성 먼저 — 장면 길이가 음성 길이로 정해진다. 장면 시작에 로봇 효과음, 목소리는 그 직후
    voice = {**VOICE, **spec.get("voice2", {})}
    durs = []
    for i, sc in enumerate(scenes):
        text = sc["narration"].replace("**", "")
        raw = work / f"s{i}.voice.mp3"
        if not (voice["tts"] == "clova" and _clova(text, voice["speaker"], str(voice["speed"]), raw)):
            raw = work / f"s{i}.voice.aiff"
            _run(["say", "-v", spec.get("voice", "Yuna"), "-r", str(spec.get("rate", 200)), "-o", str(raw), text])
        speech = float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(raw)]))
        ik = _intro_kind(spec, Path(spec_path).stem) if i == 0 else None     # 첫 장면엔 채널 오프닝
        intro = INTROS[ik] if ik else 0.0
        if ik:
            chirp = _intro_sfx(ik, intro, work / f"s{i}.chirp.wav")
        else:
            chirp = _chirp({"hook": "bibik", "outro": "down"}.get(sc["type"], "biri"), i, work / f"s{i}.chirp.wav")
        offset = round(max(chirp - 0.04, intro + 0.05), 3)
        dur = offset + speech + PAD
        ins = ["-i", str(raw), "-i", str(work / f"s{i}.chirp.wav")]
        mix = (f"[0:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(offset * 1000)}:all=1[v];"
               f"[1:a]aformat=channel_layouts=stereo[c];")
        fx_at, mood = 0.0, sc.get("mood")
        if mood in FX_TAIL:      # 좋은/나쁜 소식 효과: 핵심 단어 순간에, 앞 효과와 틈을 두고
            fx_at = max(_fx_time(sc["narration"], sc.get("fx_at"), offset, speech), (intro or chirp) + FX_GAP)
            dur = max(dur, fx_at + FX_TAIL[mood])
            _chirp({"good": "yay", "bad": "sad"}[mood], i, work / f"s{i}.mood.wav")
            ins += ["-i", str(work / f"s{i}.mood.wav")]
            mix += f"[2:a]aformat=channel_layouts=stereo,adelay={int(fx_at * 1000)}:all=1[m];[v][c][m]amix=inputs=3"
        else:
            mix += "[v][c]amix=inputs=2"
        mix += f":duration=longest:normalize=0,apad=whole_dur={dur:.3f}"
        _run(["ffmpeg", "-y", *ins, "-filter_complex", mix, "-ar", str(SR), "-ac", "2", str(work / f"s{i}.wav")])
        durs.append((speech, dur, offset, 0.0 if intro else chirp, intro, fx_at, ik or ""))

    # 2) 장면마다 t를 1/30초씩 움직이며 찍어서 ffmpeg로 바로 넘긴다
    from playwright.sync_api import sync_playwright
    parts = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, sc in enumerate(scenes):
            speech, dur, offset, chirp, intro, fx_at, ik = durs[i]
            pg.set_content(_page(sc, i, len(scenes), speech, offset, chirp, intro, spec.get("intro_text", "BIG NEWS!"), fx_at,
                                 spec.get("keyword") or scenes[0]["kicker"], ik, spec.get("acc", ""), spec.get("char", "ai")))   # 오프닝 좌상단 대표 키워드 → 썸네일·저장 목록 구분
            seg = work / f"s{i}.mp4"
            enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                                    "-i", str(work / f"s{i}.wav"), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", str(seg)],
                                   stdin=subprocess.PIPE)
            for k in range(int(dur * FPS) + 1):
                pg.evaluate(f"render({k / FPS})")
                enc.stdin.write(pg.screenshot(type="jpeg", quality=92))
            enc.stdin.close()
            if enc.wait() != 0:
                raise RuntimeError(f"장면 {i} 인코딩 실패")
            parts.append(seg)
        b.close()

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{q.name}'\n" for q in parts), encoding="utf-8")
    final = OUT / f"{name}.mp4"
    # 이어 붙이면서 전체 음량을 유튜브 기준(-14 LUFS)에 맞춘다. 화면은 다시 인코딩하지 않음
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "copy",
          "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), str(final)])
    return final
