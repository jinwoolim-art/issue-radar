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
.top{position:absolute;top:120px;left:80px;right:160px;display:flex;align-items:center;gap:18px}
.kicker{background:var(--accent);color:#08111b;font-weight:800;font-size:38px;padding:10px 26px;border-radius:999px}
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
#fx{position:absolute;left:0;top:0;width:1080px;height:1920px;image-rendering:pixelated}
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

JS = r"""(() => {   // 같은 페이지에 장면을 다시 넣어도 변수가 겹치지 않게 감싼다
const BOT = %BOT%, TYPE = %TYPE%, MOOD = %MOOD%, SPEECH = %SPEECH%, OFFSET = %OFFSET%, CHIRP = %CHIRP%;
const COL = {k:'#4a5a70', w:'#e8eef5', d:'#0f2233', e:'#5ae0ff', m:'#5ae0ff', s:'#9fb0c3', c:'#ff7a6b', a:'#ffd166', A:'#7a6a3a', x:'#7ec8ff'};
const cv = document.getElementById('bot'), g = cv.getContext('2d');
const rv = [...document.querySelectorAll('.stage .rv')];
const n = rv.length, gap = n ? Math.min(0.45, (SPEECH * 0.5) / n) : 0;
rv.forEach((el, i) => el.dataset.at = 0.12 + i * gap);
const words = [...document.querySelectorAll('.cap span')];
const total = words.reduce((a, w) => a + w.textContent.length, 0);
let acc = 0; words.forEach(w => { w.dataset.at = OFFSET + (acc / total) * SPEECH; acc += w.textContent.length; });
document.querySelectorAll('.cnt').forEach(el => el.dataset.to = el.textContent);
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x, 0), 1), 3);

function countText(src, p) {        // "174,000원" → p(0~1)만큼 올라간 숫자, 형식(쉼표·소수점)은 유지
  const m = src.match(/\d[\d,]*(\.\d+)?/); if (!m) return src;
  const dec = m[1] ? m[1].length - 1 : 0, v = parseFloat(m[0].replace(/,/g, '')) * p;
  let s = v.toFixed(dec); if (m[0].includes(',')) s = Number(s).toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  return src.replace(m[0], s);
}

function drawBot(t) {
  const grid = BOT.map(r => r.split(''));
  const set = (x, y, ch) => { if (grid[y] && x >= 0 && x < 16) grid[y][x] = ch; };
  const eyes = (pat) => { for (const y of [6, 7]) pat.split('').forEach((ch, i) => set(4 + i, y, ch)); };
  let dx = 0, dy = (Math.floor(t * 2) % 2) ? 0 : -1, look = 0, arm = 'down', mouth = 'n', sweat = false;
  if (TYPE === 'hook' && t < 0.7) { dy = -Math.round(Math.sin(Math.PI * t / 0.7) * 4); mouth = 'o'; }
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
    mood = 'happy';
  }
  if (MOOD === 'bad') {              // 우산 들고 버티다가 → 돌풍에 우산 날아감 → 손 뻗고 울먹
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
  if (chirping ? Math.floor(t * 16) % 2 : Math.floor(t * 3) % 2) for (const [x, y] of [[6,0],[7,0],[8,0],[6,1],[7,1],[8,1]]) set(x, y, 'A');
  if (chirping && Math.floor(t * 16) % 2) { set(7, 8, 'm'); set(8, 8, 'm'); }
  if (Math.floor(t * 1.5) % 2) { set(7, 13, 'w'); set(8, 13, 'w'); }
  // 팔
  const arms = {down: [[3,13],[3,14],[12,13],[12,14]], point: [[3,13],[3,14],[12,12],[13,11],[14,10]],
                wave1: [[3,13],[3,14],[13,12],[14,11],[14,10]], wave2: [[3,13],[3,14],[13,12],[13,11],[12,10]]};
  for (const [x, y] of arms[arm]) set(x, y, 's');
  if (sweat) set(14, 4 + Math.floor((t * 6) % 4), 'x');
  g.clearRect(0, 0, 16, 17);
  grid.forEach((row, y) => row.forEach((ch, x) => { if (ch !== '.') { g.fillStyle = COL[ch]; g.fillRect(x, y, 1, 1); } }));
  cv.style.transform = `translate(${dx * 9}px, ${dy * 9}px)`;
  botDx = dx; botDy = dy;
  const bang = document.getElementById('bang');
  bang.style.opacity = (TYPE === 'hook' && t > 0.15 && t < 1.8) ? 1 : 0;
}

// ── 효과 층: 색종이(좋은 소식) / 비 + 날아가는 우산(나쁜 소식) ──
const P = 9, BX = 1080 - 170 - 144, BY = 1036;        // 픽셀 크기, 로봇 캔버스 왼쪽 위
const HAND = [BX + 14.5 * P, BY + 10.5 * P];
const FX_T0 = 0.18, GUST = 1.6;
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
  f.fillStyle = 'rgba(8,14,26,0.22)'; f.fillRect(0, 0, 1080, 1920);
  f.fillStyle = 'rgba(126,200,255,0.55)';
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
  drawBot(t);
  drawFx(t);
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


def _page(sc: dict, i: int, n: int, speech: float, offset: float = 0.0, chirp: float = 0.0) -> str:
    dots = "".join(f'<i class="{"on" if k == i else ""}"></i>' for k in range(n))
    js = (JS.replace("%BOT%", json.dumps(BOT)).replace("%TYPE%", json.dumps(sc["type"])).replace("%MOOD%", json.dumps(sc.get("mood", ""))).replace("%SPEECH%", f"{speech:.3f}")
          .replace("%OFFSET%", f"{offset:.3f}").replace("%CHIRP%", f"{chirp:.3f}"))
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f'<div class="top"><span class="kicker">{_fmt(sc["kicker"])}</span><span class="dots">{dots}</span></div>'
            f'<div class="stage">{_body(sc)}</div><canvas id="fx" width="1080" height="1920"></canvas><div class="cap">{_caption(sc["narration"])}</div>'
            f'<div id="bang">!</div><canvas id="bot" width="16" height="17"></canvas>'
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
        kind = {"good": "yay", "bad": "sad"}.get(sc.get("mood")) or {"hook": "bibik", "outro": "down"}.get(sc["type"], "biri")
        chirp = _chirp(kind, i, work / f"s{i}.chirp.wav")
        offset = round(chirp - 0.04, 3)
        _run(["ffmpeg", "-y", "-i", str(raw), "-i", str(work / f"s{i}.chirp.wav"), "-filter_complex",
              f"[0:a]aresample={SR},aformat=channel_layouts=stereo,adelay={int(offset * 1000)}:all=1[v];"
              f"[1:a]aformat=channel_layouts=stereo[c];[v][c]amix=inputs=2:duration=longest:normalize=0,apad=pad_dur={PAD}",
              "-ar", str(SR), "-ac", "2", str(work / f"s{i}.wav")])
        durs.append((speech, offset + speech + PAD, offset, chirp))

    # 2) 장면마다 t를 1/30초씩 움직이며 찍어서 ffmpeg로 바로 넘긴다
    from playwright.sync_api import sync_playwright
    parts = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, sc in enumerate(scenes):
            speech, dur, offset, chirp = durs[i]
            pg.set_content(_page(sc, i, len(scenes), speech, offset, chirp))
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
