"""스토리 영상: 삐빅 탄생기 v3 (성탄 장면 패러디, 31초)

탐님 디렉션(2026-10-09) 최종:
- 레퍼런스 컷 시점 그대로 (13.33 · 17.47 · 21.13 · 24.90초). 18초 컷 대신 줌으로 물러남
- 철저한 픽셀 규칙: 모든 그림은 story_pixel 도구(픽셀 타원·다각형·계단식 직선·자동 외곽선)로만
- 픽셀 카메라: 장면을 1배로 그리고 화면 전체를 최근접 확대 (줌하면 픽셀이 같이 커짐)
- 모두 U자 눈을 지그시 감고, 원본 노래 크기에 맞춰 입을 뻥끗, 천천히 끄덕끄덕 (거의 같은 박자, 살짝씩 어긋나게)
- 아기 삐빅만 멀뚱멀뚱·깜빡·두리번 + 물음표 + 작은 "삐빅"
- 줌아웃 중 어린 양이 종종걸음으로 들어와 털썩 앉음. 끝 무렵 엄마와 양이 카메라를 돌아봄
- 천사 크루는 적게·크게, 날갯짓 1초 주기, 둥실둥실
- 17.5초 딸깍만 눈 동그랗게·입 최대로·목젖 떨림
- 마지막: 노래하는 크루를 따라 팬 → 가운데 삐빅이 크게 → 윙크 → "삐빅!" → 테크노로 바뀌며 다 같이 춤 (3초)
오디오: 레퍼런스 원본 0~27.37초 + 작은 삐빅 효과음 + 마지막 삐빅 + 직접 합성한 테크노
사용: python -m radar story [레퍼런스 영상 경로]
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from .shorts import OUT, W, H
from .shorts_anim import CHARS
from .story_pixel import PIXEL_JS

FPS = 30
REF_END = 27.37
TOTAL = 31.0
SR = 44100
BPM = 140
TECHNO_AT = 27.7
NAME = "2026-10-09_story-bbibik-birth"
REF = Path.home() / "Downloads" / "IMG_1437.MP4"
BABY_CHIRPS = [1.3, 3.1, 5.5]

STORY_JS = r"""
const ENV = %ENV%, FPS = 30, BEAT = 60 / %BPM%, TECHNO = %TECHNO%;
const env = t => ENV[Math.max(0, Math.min(ENV.length - 1, Math.round(t * FPS)))];
const clamp01 = x => Math.min(1, Math.max(0, x)), ease = x => { x = clamp01(x); return x * x * (3 - 2 * x); };
const easeOut = x => 1 - Math.pow(1 - clamp01(x), 3);
function rngS(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed);
  x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
const cache = new Map(), cached = (key, fn) => { if (!cache.has(key)) cache.set(key, fn()); return cache.get(key); };
const M = document.getElementById('c'), m = M.getContext('2d');
const WORLD = document.createElement('canvas'), w = WORLD.getContext('2d');
const FG = document.createElement('canvas'), fg = FG.getContext('2d');
function sizeTo(cv, a, b) { if (cv.width !== a || cv.height !== b) { cv.width = a; cv.height = b; } }
function clampCam(src, cx, cy, vw) { const vh = vw * 16 / 9; return [Math.min(Math.max(cx, vw / 2), src.width - vw / 2), Math.min(Math.max(cy, vh / 2), src.height - vh / 2), vw, vh]; }
function camera(src, cx, cy, vw, alpha = 1, blur = 0) {                     // 픽셀 카메라: 잘라서 최근접 확대
  const [x, y, a, b] = clampCam(src, cx, cy, vw);
  m.save(); m.imageSmoothingEnabled = false; m.globalAlpha = alpha; if (blur > 0.3) m.filter = `blur(${blur}px)`;
  m.drawImage(src, x - a / 2, y - b / 2, a, b, 0, 0, 1080, 1920); m.restore();
  return [x, y, a];
}
function glow(src, cx, cy, vw, a) { const [x, y, aa, bb] = clampCam(src, cx, cy, vw);       // 은은한 빛 번짐 (렌즈 효과)
  m.save(); m.imageSmoothingEnabled = true; m.globalCompositeOperation = 'screen'; m.globalAlpha = a; m.filter = 'blur(16px)';
  m.drawImage(src, x - aa / 2, y - bb / 2, aa, bb, 0, 0, 1080, 1920); m.restore(); }
function vignette(a) { const gr = m.createRadialGradient(540, 960, 520, 540, 960, 1180); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, `rgba(0,0,0,${a})`);
  m.fillStyle = gr; m.fillRect(0, 0, 1080, 1920); }

// ── 노래·끄덕임: 모두 거의 같은 박자, 살짝씩 어긋나게 ──
const sing = (t, ph) => t < 8.3 ? (env(t - ph) > 0.1 && Math.floor((t + ph) * 1.6) % 2 === 0) : env(t - ph) > 0.42;
const nod = (t, ph) => Math.floor((t + ph) / 1.2) % 2 === 1;
const MARY_SP = (o) => cached('mary' + JSON.stringify(o), () => mary(o));
const MAN_SP = (who, o) => cached(who + JSON.stringify(o), () => man(Object.assign({}, who === 'jo' ? JOSEPH : who === 'sa' ? SHEPA : SHEPB, o)));
const MANGER_SP = (o) => cached('mg' + JSON.stringify(o), () => manger(o));
const ANGEL_SP = (k, o, up) => cached('an' + k + JSON.stringify(o) + up, () => angelCanvas(k, o, up));
function lambS(o) {
  return cached('lamb' + JSON.stringify(o), () => outlined(26, 18, c => {
    const dy = o.sit ? 3 : 0;
    if (!o.sit) { const f = o.frame; for (const [lx, len] of [[5, f ? 5 : 4], [9, f ? 4 : 5], [14, f ? 5 : 4], [18, f ? 4 : 5]]) R(c, lx, 12, 2, len, '#3a3030'); }
    else { R(c, 5, 15, 4, 2, '#3a3030'); R(c, 16, 15, 4, 2, '#3a3030'); }
    E(c, 11, 9 + dy, 10, 5.5, '#f2efe8'); E(c, 5, 6 + dy, 4, 3, '#f7f4ee'); E(c, 12, 5 + dy, 4.5, 3, '#f7f4ee'); E(c, 18, 7 + dy, 3.5, 3, '#f7f4ee');
    if (o.turned) { E(c, 21, 7 + dy, 4, 4, '#3a3030'); P(c, 19, 6 + dy, '#f2efe8'); P(c, 22, 6 + dy, '#f2efe8'); R(c, 16, 4 + dy, 2, 2, '#3a3030'); R(c, 24, 4 + dy, 2, 2, '#3a3030'); }
    else { E(c, 22, 7 + dy, 3.5, 3.5, '#3a3030'); if (o.closed) R(c, 22, 6 + dy, 2, 1, '#8a8080'); else P(c, 23, 6 + dy, '#e8e0d0'); R(c, 19, 4 + dy, 2, 2, '#3a3030'); }
  }));
}
const wingUp = (t, ph) => Math.floor((t + ph) / 0.5) % 2 === 0;               // 1초 주기 날갯짓
const bob = (t, ph) => Math.round(Math.sin((t + ph) * Math.PI) * 2);          // 2초 주기 둥실둥실
function drawAngel(c, k, x, y, t, ph, o) { const sp = ANGEL_SP(k, o, wingUp(t, ph)); c.drawImage(sp, Math.round(x), Math.round(y + bob(t, ph))); }

// ── 1. 마구간 안 (180 x 300) ──
const STRAW = Array.from({length: 70}, (_, i) => { const r = rngS(i + 3); return [Math.floor(r() * 178), 249 + Math.floor(r() * 50)]; });
const MOTES = Array.from({length: 26}, (_, i) => { const r = rngS(i * 9 + 4); return [60 + r() * 60, 130 + r() * 110, 0.3 + r() * 0.6, r() * 6.28]; });
function babyEyes(t) {
  const seq = [[0.8, 'open'], [1.0, 'blink'], [1.7, 'lookL'], [1.95, 'open'], [2.6, 'lookR'], [2.8, 'blink'], [3.5, 'lookL'], [4.2, 'lookR'], [4.5, 'open'], [5.2, 'blink'], [5.4, 'open'], [6.1, 'lookR'], [6.6, 'open'], [7.0, 'blink'], [9, 'open']];
  for (const [end, s] of seq) if (t < end) return s; return 'open';
}
function interiorWorld(t) {
  sizeTo(WORLD, 180, 300); const c = w, floor = 248; c.setTransform(1, 0, 0, 1, 0, 0);
  for (let i = 0; i < 180; i += 10) { R(c, i, 0, 10, 300, (i / 10) % 2 ? '#5b3a20' : '#4e3119'); R(c, i, 0, 1, 300, '#3a2412'); }
  for (const px of [12, 163]) R(c, px, 0, 5, floor, '#3a2414');
  R(c, 0, 60, 180, 5, '#3a2414'); for (let i = 3; i < 180; i += 9) { E(c, i, 66, 3, 2, '#2f7d4a'); if (i % 18 === 3) P(c, i, 67, '#d63a3a'); }
  const ax = 74; R(c, ax, 96, 32, 32, '#0e1a40'); E(c, ax + 16, 96, 16, 10, '#0e1a40');
  for (let i = 0; i < 9; i++) P(c, ax + 3 + (i * 11) % 27, 90 + (i * 7) % 34, '#dfe6ff');
  R(c, ax + 15, 86, 2, 42, '#3a2414'); R(c, ax, 112, 32, 2, '#3a2414'); R(c, ax - 2, 128, 36, 3, '#3a2414');
  for (const lx of [40, 140]) { R(c, lx, 65, 1, 16, '#2a1c10'); R(c, lx - 3, 79, 7, 2, '#2a1c10'); R(c, lx - 2, 81, 5, 6, '#ffd98a'); R(c, lx - 3, 87, 7, 1, '#2a1c10'); }
  for (const [r, a] of [[46, 0.04], [32, 0.05], [20, 0.07]]) E(c, 90, 142, r, r * 0.9, `rgba(255,220,140,${a})`);   // 별빛 (픽셀 단계 원)
  R(c, 90, 0, 1, 137, '#2a1a0c'); S(c, STAR, {y: '#ffd166'}, 86, 137);
  R(c, 0, floor, 180, 52, '#8f6a2c'); for (const [x, y] of STRAW) R(c, x, y, 3, 1, '#c99b45');
  for (const [bx, by] of [[0, floor - 18], [0, floor - 8], [13, floor - 8], [150, floor - 12], [164, floor - 12]]) { R(c, bx, by, 14, 10, '#c9a24a'); R(c, bx, by + 4, 14, 1, '#a8823a'); R(c, bx + 6, by, 1, 10, '#a8823a'); }
  // 사람들 (뒤 → 앞)
  const turned = t > 5.9;
  c.drawImage(MAN_SP('sb', {mouth: sing(t, 0.12), nod: nod(t, 0.1)}), -10, floor - 84);
  c.drawImage(MAN_SP('sa', {mouth: sing(t, 0.06), nod: nod(t, 0.05)}), 140, floor - 82);
  c.drawImage(MAN_SP('jo', {mouth: sing(t, 0.0), nod: nod(t, 0.0)}), 116, floor - 72);
  c.drawImage(MANGER_SP({eyes: babyEyes(t)}), 59, floor - 14);
  c.drawImage(MARY_SP(turned ? {turned: true} : {mouth: sing(t, 0.08), nod: nod(t, 0.08)}), 2, floor - 30);
  // 어린 양: 3~4.5초 종종걸음으로 들어와 → 멈칫 → 5초 털썩 앉음 → 끝 무렵 카메라를 돌아봄
  if (t > 3.0) { const p = clamp01((t - 3.0) / 1.5), lx = -28 + (52 + 28) * p, walking = t < 4.5, sit = t > 5.0;
    const hop = walking ? (Math.floor(t * 8) % 2) : 0;
    c.drawImage(lambS({frame: walking ? Math.floor(t * 8) % 2 : 0, sit, turned: t > 6.05, closed: sit && t <= 6.05}), Math.round(lx), floor + 22 - hop); }
  // 아기의 "뭐지?" 물음표
  for (const [a, b, dx, dy] of [[1.4, 2.2, 0, 0], [3.2, 4.1, 0, 0], [3.4, 4.1, 7, -6], [5.6, 6.5, 0, 0]]) if (t > a && t < b) qmark(c, 102 + dx, floor - 24 + dy, dx ? '#f4f6ff' : '#ffe28a');
  // 빛줄기 (계단식 반투명 픽셀) + 빛 속 먼지
  G(c, [[88, 140], [93, 140], [128, 300], [52, 300]], 'rgba(255,225,150,0.06)');
  G(c, [[89, 140], [92, 140], [108, 300], [72, 300]], 'rgba(255,225,150,0.06)');
  for (const [x, y, sp, ph] of MOTES) P(c, Math.round(x + Math.sin(t * 0.6 + ph) * 3), Math.round(y + ((t * 6 * sp) % 30)), `rgba(255,240,200,${0.35 + 0.3 * Math.sin(t * 2 + ph)})`);
}

// ── 2. 바깥 (180 x 440, 정원 있는 마구간) + 하늘의 천사들 ──
let EXT = null;
function exteriorWorld(t, angels) {
  if (!EXT) { EXT = document.createElement('canvas'); EXT.width = 180; EXT.height = 440; exteriorScene(EXT.getContext('2d'), 180, 440); }
  sizeTo(WORLD, 180, 440); w.setTransform(1, 0, 0, 1, 0, 0); w.drawImage(EXT, 0, 0);
  if (!angels) return;
  for (const a of SKYANG) { const al = ease((t - 9.0 - a.d) / 1.5); if (al <= 0) continue;
    w.save(); w.globalAlpha = al; drawAngel(w, a.k, a.x, a.y, t, a.ph, {eyes: 'U', mouth: sing(t, a.ph * 0.02)}); w.restore(); }
}
const poisson = (n, W, H, d, seed, x0 = 0, y0 = 0) => { const r = rngS(seed), out = []; let tries = 0;
  while (out.length < n && tries++ < 20000) { const x = x0 + r() * W, y = y0 + r() * H; if (out.every(o => Math.hypot(o.x - x, (o.y - y) * 1.1) > d)) out.push({x, y}); }
  return out; };
const KINDS = ['prop', 'tv', 'can'];
const SKYANG = poisson(12, 150, 270, 46, 31, -4, 50).map((p, i) => ({...p, k: KINDS[i % 3], ph: (i * 0.37) % 1.2, d: (i * 0.13) % 0.45}));

// ── 3. 천사 무리 안 (150 x 267) ──
const MIDANG = [['prop', 14, 52], ['tv', 102, 44], ['tv', 6, 160], ['prop', 108, 168], ['can', 56, 212], ['prop', 60, 10],
                ['prop', 34, 80], ['tv', 84, 148]];                          // 딸깍이 물러났을 때 가장자리에 반쯤 걸리는 둘
function skyBG(c, Wd, Hd, seed) { for (let i = 0; i < Hd; i++) { const t = i / Hd; R(c, 0, i, Wd, 1, `rgb(${10 + t * 22},${20 + t * 30},${64 + t * 74})`); }
  const r = rngS(seed); for (let i = 0; i < Wd * Hd / 400; i++) P(c, Math.floor(r() * Wd), Math.floor(r() * Hd), r() < 0.2 ? '#ffffff' : '#aeb8e8'); }
function flockWorld(t, yell) {                                             // 목젖은 19.5초까지만 떨림
  sizeTo(WORLD, 150, 267); w.setTransform(1, 0, 0, 1, 0, 0); skyBG(w, 150, 267, 5);
  for (const [k, x, y] of MIDANG) drawAngel(w, k, x, y, t, x * 0.01, {eyes: 'U', mouth: sing(t, x * 0.002)});
  const o = yell ? {eyes: 'wide', mouth: 'yell', uvula: t < 19.5 ? Math.floor(t * 15) % 2 : 0, arms: 'up'} : {eyes: 'U', mouth: sing(t, 0.03)};
  drawAngel(w, 'can', 57, 112, t, 0.3, o);
}
function foreground(t) { sizeTo(FG, 60, 107); fg.setTransform(1, 0, 0, 1, 0, 0); fg.clearRect(0, 0, 60, 107);
  drawAngel(fg, 'tv', -14, 70, t, 0.2, {eyes: 'U'}); drawAngel(fg, 'prop', 38, -6, t, 0.5, {eyes: 'U'}); }

// ── 4. 하늘 가득 (180 x 320) ──
const PACK = poisson(24, 176, 290, 30, 77, -6, -6).map((p, i) => ({...p, k: KINDS[(i + Math.floor(i / 5)) % 3], ph: (i * 0.29) % 1.2}));
function packedWorld(t) {
  sizeTo(WORLD, 180, 320); w.setTransform(1, 0, 0, 1, 0, 0); skyBG(w, 180, 320, 9);
  for (const a of PACK) drawAngel(w, a.k, a.x, a.y, t, a.ph, {eyes: 'U', mouth: sing(t, a.ph * 0.03)});
  G(w, [[0, 320], [0, 286], [26, 276], [44, 290], [44, 320]], '#120c08'); R(w, 30, 266, 6, 14, '#120c08'); pine(w, 166, 324, 34);
}

// ── 5. 팬 → 삐빅 → 윙크 → 테크노 댄스 (360 x 200) ──
const ROW = [['prop', 6, 88], ['can', 46, 70], ['tv', 86, 96], ['prop', 126, 74], ['can', 166, 92], ['tv', 206, 70], ['can', 246, 96], ['prop', 334, 92], ['tv', 252, 30], ['can', 312, 34]];
const BIB = [282, 80];                                                       // 삐빅 자리 (정가운데)
function panWorld(t) {
  sizeTo(WORLD, 360, 200); w.setTransform(1, 0, 0, 1, 0, 0);
  const dance = t >= TECHNO, beat = Math.floor((t - TECHNO) / BEAT), bp = ((t - TECHNO) / BEAT) % 1;
  skyBG(w, 360, 200, 13);
  if (dance) {                                                               // 디스코: 박자마다 색 바뀌는 픽셀 조명
    const cols = ['rgba(255,209,102,0.16)', 'rgba(90,224,255,0.16)', 'rgba(255,122,107,0.16)', 'rgba(199,146,255,0.16)'];
    for (let k = 0; k < 4; k++) { const x0 = 220 + k * 34 + (beat % 2 ? 8 : -8); G(w, [[x0, 0], [x0 + 6, 0], [x0 + 30, 200], [x0 - 24, 200]], cols[(beat + k) % 4]); }
  }
  for (const [k, x, y] of ROW) {
    if (dance) { const step = (beat % 2 ? 2 : -2), up = beat % 2 === 0;
      drawAngel(w, k, x + step, y - (bp < 0.3 ? 2 : 0), t, 0, {eyes: 'open', mouth: true, arms: up ? 'up' : null}); }
    else drawAngel(w, k, x, y, t, x * 0.004, {eyes: 'U', mouth: sing(t, x * 0.001)});
  }
  let o;
  if (dance) o = {eyes: 'open', mouth: true, arms: beat % 2 === 0 ? 'up' : null};
  else if (t > 27.42 && t < 27.72) o = {eyes: 'wink'};
  else if (t > 27.3) o = {eyes: 'open'};
  else o = {eyes: 'U', mouth: sing(t, 0.05)};
  if (!dance) drawAngel(w, 'ai', BIB[0], BIB[1], t, 0.4, o);            // 댄스 때 삐빅은 앞 층에서 따로 크게
}

window.render = (t) => {
  m.setTransform(1, 0, 0, 1, 0, 0); m.filter = 'none'; m.globalCompositeOperation = 'source-over'; m.globalAlpha = 1;
  m.fillStyle = '#000'; m.fillRect(0, 0, 1080, 1920);
  if (t < 8.0) {                                                            // 1. 끊김 없는 줌아웃 (아기 → 전체)
    interiorWorld(t);
    const p = easeOut(t / 5.2), vw = t < 5.2 ? 44 + (138 - 44) * p : 138 + 4 * clamp01((t - 5.2) / 2.3);
    const cx = 90, cy = t < 5.2 ? 238 + (178 - 238) * p : 178;
    camera(WORLD, cx, cy, vw); glow(WORLD, cx, cy, vw, 0.22);
    if (t > 7.5) { exteriorWorld(t, false); camera(WORLD, 90, 280, 180, ease((t - 7.5) / 0.5)); }   // 2. 디졸브
    vignette(0.45);
  } else if (t < 13.33) {                                                   // 3. 위로 틸트 → 4. 천사들이 한꺼번에 서서히
    exteriorWorld(t, t > 8.9); const cy = 280 - 80 * ease((t - 8.0) / 1.0) - 6 * clamp01((t - 9.0) / 4.3);
    camera(WORLD, 90, cy, 180); glow(WORLD, 90, cy, 180, 0.25); vignette(0.45);
  } else if (t < 17.47) {                                                   // 5~6. 무리 안: 앞쪽이 흐렸다가 초점
    flockWorld(t, false); const vw = 120 - 8 * clamp01((t - 13.33) / 4.1);
    camera(WORLD, 75, 133, vw); glow(WORLD, 75, 133, vw, 0.22);
    vignette(0.5);
  } else if (t < 21.13) {                                                   // 7. 딸깍 초근접 → 줌으로 물러남 (목젖 떨림)
    flockWorld(t, true); const p = easeOut((t - 17.95) / 0.5), vw = 12 + (48 - 12) * p - 3 * clamp01((t - 18.45) / 2.7);   // 덜 극단적으로: 시작은 덜 가깝게, 물러나도 2배 크게   // 입안(목젖) 초근접 0.5초 → 물러남
    const cx = 74.5 + 0.5 * p, cy = 128.5 + (126 - 128.5) * p;           // 카메라는 고정 → 딸깍도 둥실둥실 움직여 보임                 // 입 → 딸깍 몸 중심으로 옮겨 가서 정중앙
    camera(WORLD, cx, cy, vw); glow(WORLD, cx, cy, vw, 0.2); vignette(0.5);
  } else if (t < 24.9) {                                                    // 8. 하늘 가득, 천천히 다가감
    packedWorld(t); const vw = 180 - 14 * clamp01((t - 21.13) / 3.77);
    camera(WORLD, 90, 160, vw); glow(WORLD, 90, 160, vw, 0.3); vignette(0.5);
  } else if (t < 30.8) {                                                    // 9. 팬 → 삐빅 크게 → 윙크 → 삐빅! → 테크노 댄스
    panWorld(t);
    let cx, vw;
    if (t < 27.2) { cx = 175 + (BIB[0] + 17 - 175) * ease((t - 24.9) / 2.3); vw = 100; }   // 이동 거리를 줄여 천천히
    else if (t < TECHNO) { cx = BIB[0] + 17; vw = 100 - 70 * easeOut((t - 27.2) / 0.25); }
    else { cx = BIB[0] + 17; vw = 110; }                                    // 뒤 층: 크루가 작게 보이도록 넓게
    const cy = BIB[1] + 14;
    camera(WORLD, cx, cy, vw); glow(WORLD, cx, cy, vw, t >= TECHNO ? 0.35 : 0.22);
    if (t >= TECHNO) {                                                       // 앞 층: 삐빅은 계속 크게 (클로즈업 유지)
      const beat = Math.floor((t - TECHNO) / BEAT), bp = ((t - TECHNO) / BEAT) % 1;
      sizeTo(FG, 40, 71); fg.setTransform(1, 0, 0, 1, 0, 0); fg.clearRect(0, 0, 40, 71);
      const step = beat === 0 ? 0 : (beat % 2 ? 2 : -2);                    // 원래 자리와 픽셀 격자를 정확히 맞춤 (튀지 않게)
      drawAngel(fg, 'ai', 3 + step, 21 - (bp < 0.3 && beat > 0 ? 2 : 0), t, 0.4, {eyes: 'open', mouth: true, arms: beat % 2 === 0 ? 'up' : null});
      camera(FG, 20, 35, 30); glow(FG, 20, 35, 30, 0.22);
    }
    if (t >= TECHNO && Math.floor((t - TECHNO) / BEAT) % 2 === 0 && ((t - TECHNO) / BEAT) % 1 < 0.15) { m.fillStyle = 'rgba(255,255,255,0.08)'; m.fillRect(0, 0, 1080, 1920); }
    vignette(0.45);
  }
};
"""


def _page(env: list) -> str:
    js = (PIXEL_JS.replace("%CHARS%", json.dumps(CHARS)) + STORY_JS.replace("%ENV%", json.dumps([round(v, 3) for v in env]))
          .replace("%BPM%", str(BPM)).replace("%TECHNO%", str(TECHNO_AT)))
    return (f"<html><head><meta charset='utf-8'><style>*{{margin:0}}body{{width:{W}px;height:{H}px;background:#000;overflow:hidden}}"
            f"canvas{{display:block}}</style></head><body><canvas id='c' width='{W}' height='{H}'></canvas><script>{js}</script></body></html>")


# ── 소리 ──
def _tone(f0, f1, dur, square=0.3):
    t = np.arange(int(SR * dur)) / SR
    ph = 2 * np.pi * np.cumsum(np.linspace(f0, f1, t.size)) / SR
    return ((1 - square) * np.sin(ph) + square * np.sign(np.sin(ph)) * 0.5) * np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))


def _bibik(gain=1.0):
    return np.concatenate([_tone(1500, 1900, 0.07), np.zeros(int(SR * 0.03)), _tone(2300, 2900, 0.09)]) * gain


def _techno(dur):
    """직접 합성한 테크노 (140BPM): 킥 · 오프비트 하이햇 · 쏘우 베이스 아르페지오 · 스탭 화음"""
    rng = np.random.default_rng(9)
    n = int(SR * dur); out = np.zeros(n); beat = 60 / BPM
    def put(sig, at, g):
        i = int(at * SR); k = min(sig.size, n - i)
        if k > 0: out[i:i + k] += sig[:k] * g
    def saw(f, d):
        t = np.arange(int(SR * d)) / SR
        return (2 * ((f * t) % 1) - 1) * np.exp(-t / (d * 0.6))
    tk = np.arange(int(SR * 0.18)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(np.linspace(160, 42, tk.size)) / SR) * np.exp(-tk / 0.08)
    bass = [55, 55, 82.4, 55, 65.4, 55, 98, 82.4]
    for b in range(int(dur / beat) + 1):
        at = b * beat
        put(kick, at, 1.0)
        hh = rng.standard_normal(int(SR * 0.03)); hh -= np.convolve(hh, np.ones(6) / 6, "same"); put(hh * np.exp(-np.arange(hh.size) / SR / 0.012), at + beat / 2, 0.45)
        for q in range(2): put(saw(bass[(b * 2 + q) % 8] * 2, beat / 2), at + q * beat / 2, 0.28)
        if b % 2: [put(saw(f, 0.12), at + beat / 2, 0.1) for f in (523.25, 659.25, 783.99)]
    return out


def _envelope(orig: np.ndarray) -> list:
    """프레임마다 원본 소리 크기(0~1) → 입 뻥끗에 사용"""
    hop = SR // FPS
    rms = np.array([np.sqrt(np.mean(orig[i:i + hop] ** 2)) for i in range(0, len(orig) - hop, hop)])
    ref = np.percentile(rms[rms > 0], 95) if np.any(rms > 0) else 1.0
    env = np.clip(rms / ref, 0, 1)
    sm = np.copy(env)
    for i in range(1, len(sm)):                                  # 빠르게 열리고 천천히 닫히게
        sm[i] = env[i] if env[i] > sm[i - 1] else sm[i - 1] * 0.75 + env[i] * 0.25
    return list(sm) + [0.0] * int((TOTAL - REF_END) * FPS + 2)


def _soundtrack(work: Path, ref: Path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-t", str(REF_END), "-i", str(ref), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    orig = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    buf = np.zeros(int(SR * TOTAL)); n = min(orig.size, buf.size)
    buf[:n] = orig[:n]; fade = int(SR * 0.04); buf[n - fade:n] *= np.linspace(1, 0, fade)
    def put(sig, at, g):
        i = int(at * SR); k = min(sig.size, buf.size - i)
        if k > 0: buf[i:i + k] += sig[:k] * g
    for at in BABY_CHIRPS: put(_bibik(), at, 0.06)                # 아기의 작은 "삐빅"
    put(_bibik(), 27.55, 0.4)                                       # 마지막 "삐빅!"
    put(_techno(TOTAL - TECHNO_AT - 0.2), TECHNO_AT, 0.32)
    buf[int(30.8 * SR):] = 0
    wav = work / "story.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    return wav, _envelope(orig)


def render(ref: str | None = None, frames: list | None = None) -> Path:
    ref = Path(ref) if ref else REF
    work = OUT / NAME
    work.mkdir(parents=True, exist_ok=True)
    wav, env = _soundtrack(work, ref)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.on("pageerror", lambda e: print("pageerror:", e))
        pg.set_content(_page(env))
        if frames:                                                  # 미리보기: 지정한 시각만 png로
            for i, t in enumerate(frames):
                pg.evaluate(f"render({t})"); pg.screenshot(path=str(work / f"preview_{i:02d}.png"))
            b.close(); return work
        silent = work / "video.mp4"
        enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        for k in range(int(TOTAL * FPS)):
            pg.evaluate(f"render({k / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=92))
        enc.stdin.close(); enc.wait()
        b.close()
    final = OUT / f"{NAME}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-ar", str(SR), "-shortest", str(final)], check=True)
    return final
