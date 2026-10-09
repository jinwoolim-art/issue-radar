"""스토리 영상: 삐빅 탄생기 (성탄 장면 패러디, 약 30초).

레퍼런스 구성을 그대로 따른다: 고요한 마구간(자장가) → 바깥 밤하늘(정적) → 천사가 하늘을 가득 메움(합창 폭발)
→ 천사 얼굴 클로즈업 고함 → 합창 고조 + 카메라 아래로 → 마구간으로 급줌 → 아기가 깜짝 "삐빅! 빅뉴스!" → 뚝 끊김 → 엔딩 카드.
아기 = 삐빅, 하늘의 천사 = 위잉·치직·딸깍. 나머지 인물(엄마·아빠·목자)은 일반적인 성탄 인물을 픽셀로 새로 그렸다.
음악: '고요한 밤'(1818년 작곡, 저작권 만료) 오르골 + 합성 합창. 대사는 클로바(로봇별 목소리).
사용: python -m radar story → out/shorts/2026-10-09_story-bbibik-birth.mp4
"""
import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from .shorts import OUT, W, H
from .shorts_anim import CHARS, JS as ANIM_JS, _clova

FPS = 30
TOTAL = 30.0
SR = 44100
NAME = "2026-10-09_story-bbibik-birth"
FONT_JS = re.search(r"const FONT = \{.*?\};", ANIM_JS, re.S).group(0)

PAGE_JS = r"""(() => {
const U = 12, cv = document.getElementById('c'), g = cv.getContext('2d');
const CH = %CHARS%;
%FONT%
const BASE = {k:'#4a5a70', w:'#e8eef5', d:'#0f2233', e:'#5ae0ff', m:'#5ae0ff', s:'#9fb0c3', c:'#ff7a6b', a:'#ffd166', A:'#7a6a3a', O:'#7a1f2a'};
const PAL = k => Object.assign({}, BASE, CH[k].pal, {O: '#7a1f2a'});
const clamp01 = x => Math.min(1, Math.max(0, x)), ease = x => x * x * (3 - 2 * x);
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed);
  x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
function spr(rows, p, x, y, s) {
  for (let r = 0; r < rows.length; r++) for (let c = 0; c < rows[r].length; c++) {
    const ch = rows[r][c]; if (ch === '.' || !p[ch]) continue;
    g.fillStyle = p[ch]; g.fillRect(x + c * s, y + r * s, s + 0.03, s + 0.03);
  }
}
const mirror = rows => rows.map(r => [...r].reverse().join(''));
function setCam(sc, cx, cy, shx = 0, shy = 0) { g.setTransform(U * sc, 0, 0, U * sc, 540 - cx * U * sc + shx, 960 - cy * U * sc + shy); }
function screen() { g.setTransform(1, 0, 0, 1, 0, 0); }

// ── 로봇 얼굴 ──
function faceRows(k, mode, t) {
  const rows = CH[k].grid.map(r => r.split(''));
  const set = (x, y, c) => { if (rows[y] && x >= 0 && x < 16) rows[y][x] = c; };
  if (k === 'ai') {
    if (mode === 'sleep') { for (let x = 4; x < 12; x++) { rows[6][x] = 'd'; rows[7][x] = 'deeddeed'[x - 4]; } }
    if (mode === 'peek') { for (let x = 4; x < 12; x++) rows[6][x] = 'd'; if (Math.floor(t * 8) % 2) for (const [x, y] of CH.ai.blink) set(x, y, 'A'); }
    if (mode === 'shock') { for (let x = 4; x < 12; x++) { rows[5][x] = 'deeddeed'[x - 4]; rows[6][x] = 'deeddeed'[x - 4]; rows[7][x] = 'd'; }
      set(5, 5, 'w'); set(9, 5, 'w'); for (const [x, y] of [[7,8],[8,8],[7,9],[8,9]]) set(x, y, 'O');
      if (Math.floor(t * 14) % 2) for (const [x, y] of CH.ai.blink) set(x, y, 'A'); }
  }
  const open = mode === 'sing' ? Math.floor(t * 4 + (k.length)) % 2 === 0 : mode === 'yell';
  if (open) {
    if (k === 'can') { for (const x of [6, 7, 8, 9]) set(x, 9, 'O'); set(7, 8, 'O'); set(8, 8, 'O');
      if (mode === 'yell') { for (const x of [6, 7, 8, 9]) set(x, 10, 'O'); set(4, 6, 'e'); set(6, 6, 'e'); set(9, 6, 'e'); set(11, 6, 'e'); } }
    if (k === 'prop') { for (const x of [6, 7, 8, 9]) set(x, 8, 'O'); if (mode === 'yell') for (const x of [5, 6, 7, 8, 9, 10]) set(x, 9, 'O'); }
    if (k === 'tv') { for (const x of [6, 7, 8, 9]) set(x, 8, 'O'); }
  }
  return rows.map(r => r.join(''));
}

// ── 성탄 인물·소품 (일반적인 인물을 픽셀로) ──
const MARY = ["......vvvv......", "....vvvvvvvv....", "...vvvsssssvv...", "...vvseesseevv..", "...vvsssssssvv..",
  "...vvssscsssvv..", "...vvvsssssvvv..", "..vvvvvwwwwvvvv.", "..vvvvwwwwwwvvv.", ".vvvvwwwhhwwwvvv", ".vvvwwwwhhwwwwvv",
  ".vvvwwwwwwwwwwvv", "vvvvwwwwwwwwwwvv", "vvvvvwwwwwwwwvvv", "vvvvvvwwwwwwvvvv", "vvvvvvvvvvvvvvvv", "vvvvvvvvvvvvvvvv", ".vvvvvvvvvvvvvv."];
const MARYP = {v: '#3d6fe0', s: '#f2c9a0', e: '#4a2a1a', c: '#e8a0a0', w: '#eef0f5', h: '#f2c9a0'};
const MAN = ["....tttttt....k.", "...tttttttt...k.", "..tttssssstt..k.", "..ttseesseet..k.", "..ttsssssst...k.", "..ttrrssrrt...k.",
  "...trrrrrrt..sk.", "...rrrrrrrr..sk.", "..oooorrooooosk.", ".ooooooooooooo.k", ".oooooooooooo..k", ".ooooyyyyoooo..k",
  ".oooooooooooo..k", ".oooooooooooo..k", "..ooooooooooo..k", "..ooooooooooo..k", "..ooooooooooo..k", "..ooooooooooo..k",
  "..oooooooooooo.k", "..oooooooooooo.k", "..ooooo..ooooo.k", "..kkk.....kkk..k"];
const JOSEPH = {t: '#c8a060', s: '#f2c9a0', e: '#4a2a1a', r: '#5a3a1a', o: '#a0522d', y: '#d4a017', k: '#5a3a1a'};
const SHEP1 = {t: '#e0e0d0', s: '#e8b88a', e: '#4a2a1a', r: '#3a2a1a', o: '#3f8f4f', y: '#e0e0d0', k: '#3a2a1a'};
const SHEP2 = {t: '#d4b483', s: '#f0c49a', e: '#4a2a1a', r: '#8a5a2a', o: '#c0392b', y: '#f0d070', k: '#3a2a1a'};
const NOSTAFF = MAN.map(r => r.slice(0, 13) + '...');   // 지팡이 없는 목자
const MANGER = ["yyyyyyyyyyyyyyyyyyyyyyyyyyyyyy", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", ".bBBBBBBBBBBBBBBBBBBBBBBBBBBb.", "..bBBBBBBBBBBBBBBBBBBBBBBBBb..",
  "...bBBBBBBBBBBBBBBBBBBBBBBb...", "....bbbbbbbbbbbbbbbbbbbbbb....", ".....b..................b.....", "....bb..................bb...."];
const MANGERP = {y: '#e8c060', b: '#8b5a2b', B: '#6b4423'};
const STAR = ["....y....", "....y....", "...yyy...", "yyyyyyyyy", ".yyyyyyy.", "..yyyyy..", "..yy.yy..", ".yy...yy.", ".y.....y."];
const STABLE = ["..........RRRR..........", "........RRRRRRRR........", "......RRRRRRRRRRRR......", "....RRRRRRRRRRRRRRRR....",
  "..RRRRRRRRRRRRRRRRRRRR..", "RRRRRRRRRRRRRRRRRRRRRRRR", "..bbbbbbbbbbbbbbbbbbbb..", "..bbbbbbbbbbbbbbbbbbbb..", "..bbbbbbbbLLLLbbbbbbbb..",
  "..bbbbbbbLLLLLLbbbbbbb..", "..bbbbbbbLLLLLLbbbbbbb..", "..bbbbbbbLLLLLLbbbbbbb..", "..bbbbbbbLLLLLLbbbbbbb..", "..bbbbbbbLLLLLLbbbbbbb.."];
const STABLEP = {R: '#5a3420', b: '#7a4a2a', L: '#ffcf6b'};
const TREE = ["....g....", "...ggg...", "..ggggg..", "...ggg...", "..ggggg..", ".ggggggg.", "..ggggg..", ".ggggggg.", "ggggggggg", "....t....", "....t...."];
const TREEP = {g: '#123a2a', t: '#3a2a1a'};
const WING = ["....ww", "..wwww", "wwwwww", ".wwwww", "..ww.."], WING2 = ["..ww..", ".wwwww", "wwwwww", "..wwww", "....ww"];
const WINGP = {w: '#f4f6fb'};

// ── 장면: 마구간 안 ──
const STRAW = Array.from({length: 60}, (_, i) => { const R = rng(i + 3); return [R() * 90, 119 + R() * 40, 1 + R() * 3]; });
function drawInterior(t, babyMode) {
  for (let y = 0, i = 0; y < 118; y += 6, i++) { g.fillStyle = i % 2 ? '#5e3b1f' : '#6b4423'; g.fillRect(0, y, 90, 6); g.fillStyle = '#3e2612'; g.fillRect(0, y + 5.4, 90, 0.6); }
  const glow = g.createRadialGradient(45, 76, 2, 45, 76, 40); glow.addColorStop(0, 'rgba(255,220,120,0.35)'); glow.addColorStop(1, 'rgba(255,220,120,0)');
  g.fillStyle = glow; g.fillRect(0, 0, 90, 118);
  const tw = 1 + 0.06 * Math.sin(t * 5);
  spr(STAR, {y: '#ffd166'}, 45 - 4.5 * tw, 72 - 4.5 * tw, tw);
  g.fillStyle = '#b8893c'; g.fillRect(0, 118, 90, 42);
  g.fillStyle = '#d9ae55'; for (const [x, y, l] of STRAW) g.fillRect(x, y, l, 0.5);
  const br = k => 0.25 * Math.sin(t * 2 + k);
  spr(MAN, SHEP1, 70, 95 + br(1), 1); spr(NOSTAFF, SHEP2, 78, 97 + br(2), 1);
  spr(MAN, JOSEPH, 60, 97 + br(3), 1);
  spr(MARY, MARYP, 8, 100 + br(4), 1);
  const baby = faceRows('ai', babyMode, t).slice(0, 12);
  spr(baby, PAL('ai'), 39, 97.5, 0.75);
  g.fillStyle = '#f4f0e6'; g.fillRect(38, 105.3, 14, 1.4);           // 강보
  spr(MANGER, MANGERP, 30, 106, 1);
}

// ── 장면: 바깥 밤하늘 ──
const SKYSTARS = Array.from({length: 130}, (_, i) => { const R = rng(i * 7 + 1); return [R() * 90, R() * 125, 0.4 + R() * 0.7, R() * 6.28]; });
function drawExterior(t) {
  for (let i = 0; i < 20; i++) { const p = i / 19; g.fillStyle = `rgb(${10 + p * 32},${18 + p * 42},${56 + p * 90})`; g.fillRect(0, i * 8, 90, 8.2); }
  for (const [x, y, s, ph] of SKYSTARS) { g.globalAlpha = 0.5 + 0.5 * Math.sin(t * 3 + ph); g.fillStyle = '#ffffff'; g.fillRect(x, y, s, s); }
  g.globalAlpha = 1;
  spr(STAR, {y: '#ffd166'}, 41, 92, 0.9);
  g.fillStyle = '#0b1f1a'; g.beginPath(); g.moveTo(0, 132); g.quadraticCurveTo(25, 124, 45, 130); g.quadraticCurveTo(70, 136, 90, 127); g.lineTo(90, 160); g.lineTo(0, 160); g.fill();
  spr(TREE, TREEP, 6, 112, 1.6); spr(TREE, TREEP, 74, 116, 1.3);
  const lg = g.createRadialGradient(45, 124, 1, 45, 124, 18); lg.addColorStop(0, 'rgba(255,207,107,0.45)'); lg.addColorStop(1, 'rgba(255,207,107,0)');
  g.fillStyle = lg; g.fillRect(25, 105, 40, 40);
  spr(STABLE, STABLEP, 33, 112, 1);
}

// ── 천사 (위잉·치직·딸깍) ──
const ANG = Array.from({length: 96}, (_, i) => { const R = rng(i * 13 + 5);
  return {k: ['prop', 'tv', 'can'][i % 3], x: 2 + R() * 76, y: 4 + R() * 98, s: 0.32 + R() * 0.36, at: 8.4 + Math.pow(i / 96, 1.25) * 7.5, ph: R() * 6.28}; });
function drawAngel(k, x, y, s, t, mode, ph = 0) {
  const flap = Math.floor(t * 6 + ph) % 2;
  spr(flap ? WING : WING2, WINGP, x - 5 * s, y + 8 * s, s);
  spr(mirror(flap ? WING : WING2), WINGP, x + 15 * s, y + 8 * s, s);
  g.fillStyle = '#ffd166'; g.fillRect(x + 4 * s, y - 2.6 * s, 8 * s, 1.3 * s);   // 후광
  g.fillStyle = 'rgba(255,240,170,0.9)'; g.fillRect(x + 5.5 * s, y - 2.2 * s, 5 * s, 0.5 * s);
  spr(faceRows(k, mode, t + ph), PAL(k), x, y, s);
}
function drawAngels(t, mode, all) {
  for (const a of ANG) {
    const u = t - a.at; if (!all && u < 0) continue;
    const pop = all ? 1 : Math.min(1, u / 0.15), s = a.s * pop;
    drawAngel(a.k, a.x + (a.s - s) * 8, a.y + Math.sin(t * 2 + a.ph) * 1.2, s, t, mode, a.ph);
  }
}
function drawBlurPass(t) {                                  // 카메라 가까이 큰 천사들이 흐릿하게 스쳐 감
  g.filter = 'blur(10px)';
  for (const [k, x0, y0, sp, d] of [['tv', -40, 30, 70, 0], ['can', 100, 70, -80, 0.3], ['prop', -30, 100, 60, 0.7]]) {
    const u = t - 12.4 - d; if (u < 0) continue;
    drawAngel(k, x0 + sp * u, y0 + Math.sin(u * 3) * 3, 3.2, t, 'sing');
  }
  g.filter = 'none';
}

// ── 글자 ──
function drawGlyph(ch, x, y, s) { const b = FONT[ch]; if (!b) return; const gp = Math.max(1, Math.round(s * 0.18));
  for (let i = 0; i < 35; i++) if (b[i] === '1') g.fillRect(Math.round(x + (i % 5) * s), Math.round(y + Math.floor(i / 5) * s), s - gp, s - gp); }
function koText(txt, y, size, color, alpha = 1, scale = 1, x = 540) {
  screen(); g.save(); g.globalAlpha = alpha; g.translate(x, y); g.scale(scale, scale);
  g.font = `900 ${size}px "Apple SD Gothic Neo", sans-serif`; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.lineJoin = 'round'; g.lineWidth = size * 0.12; g.strokeStyle = '#120d02'; g.strokeText(txt, 0, 0); g.fillStyle = color; g.fillText(txt, 0, 0);
  g.restore();
}
const NEWS = (() => { const R = rng(99), out = []; let x = 90;
  [...'BIG NEWS!'].forEach((ch, i) => { if (ch === ' ') { x += 40; return; } const s = 18 + Math.floor(R() * 12);
    out.push({ch, x, y: 330 + (R() - 0.5) * 120, s, col: ['#ffd166', '#5ae0ff', '#f4f6f8'][i % 3], at: 0.25 + i * 0.05}); x += s * 6.2; });
  for (let i = 0; i < 26; i++) out.push({ch: 'BIGNEWS01'[Math.floor(R() * 9)], x: 40 + R() * 1000, y: 200 + R() * 1500, s: 5 + Math.floor(R() * 7),
    col: ['#ffd166', '#5ae0ff', '#f4f6f8'][Math.floor(R() * 3)], at: 0.3 + R() * 0.4});
  return out; })();
function bigNews(u) {
  screen();
  for (const L of NEWS) { const v = u - L.at; if (v < 0) continue; if (v < 0.12 && Math.floor(u * 40) % 3 === 0) continue;
    g.fillStyle = L.col; drawGlyph(L.ch, L.x + (Math.floor(u * 25 + L.x) % 13 === 0 ? 12 : 0), L.y, v < 0.06 ? Math.round(L.s * 1.3) : L.s); }
}

// ── 엔딩 카드 ──
function endCard(u) {
  screen(); g.fillStyle = '#0e1430'; g.fillRect(0, 0, 1080, 1920);
  for (const [x, y, s, ph] of SKYSTARS) { g.globalAlpha = 0.3 + 0.3 * Math.sin(u * 3 + ph); g.fillStyle = '#fff'; g.fillRect(x * 12, y * 12, s * 6, s * 6); }
  g.globalAlpha = 1;
  const pop = Math.min(1, u / 0.25);
  koText('삐빅 크루 탄생!', 720, 130, '#ffd166', pop, 0.7 + 0.3 * pop);
  const crew = [['ai', '삐빅'], ['prop', '위잉'], ['tv', '치직'], ['can', '딸깍']];
  crew.forEach(([k, name], i) => {
    const x = 81 + i * 242, bob = Math.sin(u * 6 + i) * 6, show = clamp01((u - 0.15 - i * 0.12) / 0.2);
    if (show <= 0) return;
    g.setTransform(12, 0, 0, 12, x, 920 + bob + (1 - show) * 60); spr(faceRows(k, 'normal', u), PAL(k), 0, 0, 1);
    koText(name, 1170, 52, '#f4f6f8', show, 1, x + 96);
  });
  koText('AI 소식은 @bbibik_ai', 1360, 50, '#f4f6f8', clamp01((u - 0.7) / 0.3));
  koText('생활 꿀정보는 @bbibik_crew', 1440, 50, '#f4f6f8', clamp01((u - 0.85) / 0.3));
}

window.render = (t) => {
  screen(); g.filter = 'none'; g.globalAlpha = 1; g.fillStyle = '#000'; g.fillRect(0, 0, 1080, 1920);
  if (t < 6.8) {                                                       // 1. 고요한 마구간 (가까이 → 중간 → 전체)
    const [sc, cx, cy] = t < 2.2 ? [2.6, 45, 103] : t < 4.2 ? [1.75, 40, 102] : [1.08, 47, 96];
    setCam(sc, cx, cy); drawInterior(t, t > 4.6 && t < 5.6 ? 'peek' : 'sleep');
    koText('삐빅 크루 탄생기', 170, 64, '#f4f6f8', clamp01(1 - (t - 5.8) / 0.6));
  } else if (t < 8.3) { setCam(1, 45, 80); drawExterior(t); }          // 2. 바깥 밤하늘 (정적)
  else if (t < 16.4) {                                                 // 3. 천사들이 하늘을 메움 + 합창
    setCam(1 + 0.12 * clamp01((t - 8.3) / 8), 45, 76); drawExterior(t); drawAngels(t, 'sing', false);
    if (t > 12.4 && t < 14.6) drawBlurPass(t);
  } else if (t < 19.4) {                                               // 4. 딸깍 클로즈업 고함 → 한 발 물러남
    setCam(1.1, 45, 76); drawExterior(t); drawAngels(t, 'sing', true);
    const big = t < 17.6, s = big ? 5.8 : 2.3, sh = big ? (Math.floor(t * 30) % 2 ? 1 : -1) : 0;
    if (big) { setCam(1, 45, 80); g.fillStyle = 'rgba(14,20,48,0.85)'; g.fillRect(0, 0, 90, 160); }
    drawAngel('can', 45 - 8 * s + sh, (big ? 82 : 72) - 8.5 * s, s, t, 'yell');
    const u = t - 16.45; koText('축하해!!!', 300, 170, '#ffd166', 1, u < 0.12 ? 1.4 - 3.3 * u : 1);
  } else if (t < 23.8) {                                               // 5. 하늘 가득 합창, 카메라는 아래 마구간으로
    const p = ease(clamp01((t - 19.4) / 4.4)); setCam(1.05, 45, 70 + p * 32); drawExterior(t); drawAngels(t, 'sing', true);
  } else if (t < 24.8) {                                               // 6. 마구간으로 급줌
    const p = clamp01((t - 23.8) / 1.0); setCam(1 + p * p * 9, 45, 102 + p * 22); drawExterior(t); drawAngels(t, 'sing', true);
    if (p > 0.7) { screen(); g.fillStyle = `rgba(255,220,140,${(p - 0.7) / 0.3})`; g.fillRect(0, 0, 1080, 1920); }
  } else if (t < 27.0) {                                               // 7. 아기 삐빅 깜짝! "삐빅! 빅뉴스!"
    const sh = t < 25.7 ? (Math.floor(t * 30) % 2 ? 10 : -10) : 0;
    setCam(2.4, 45, 103, sh, 0); drawInterior(t, 'shock'); bigNews(t - 24.8);
  } else if (t >= 27.4) endCard(t - 27.4);                             // 8. 뚝 → 엔딩 카드
};
})();"""


def _page() -> str:
    js = PAGE_JS.replace("%CHARS%", json.dumps(CHARS)).replace("%FONT%", FONT_JS)
    return (f"<html><head><meta charset='utf-8'><style>*{{margin:0}}body{{width:{W}px;height:{H}px;background:#000;overflow:hidden}}"
            f"canvas{{display:block;image-rendering:pixelated}}</style></head><body><canvas id='c' width='{W}' height='{H}'></canvas>"
            f"<script>{js}</script></body></html>")


# ── 소리 ──
def _tone(f0, f1, dur, square=0.4, warble=0.0):
    t = np.arange(int(SR * dur)) / SR
    f = np.linspace(f0, f1, t.size) * (1 + warble * np.sin(2 * np.pi * 28 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return ((1 - square) * np.sin(ph) + square * np.sign(np.sin(ph)) * 0.5) * np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))


def _musicbox(f, dur):
    t = np.arange(int(SR * dur)) / SR
    s = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t) + 0.18 * np.sin(2 * np.pi * 3.9 * f * t) * np.exp(-t / 0.12)
    return s * np.minimum(1, t / 0.003) * np.exp(-t / 0.7)


def _formant(f):
    return (np.exp(-((f - 700) / 180) ** 2) + 0.7 * np.exp(-((f - 1150) / 220) ** 2)
            + 0.25 * np.exp(-((f - 2600) / 350) ** 2) + 0.05)


def _choir(freqs, dur, rng):
    """'아—' 모음 합창: 음마다 살짝 다른 3명, 비브라토, 모음 공명(포먼트)으로 사람 목소리 느낌을 낸다"""
    n = int(SR * dur); t = np.arange(n) / SR; out = np.zeros(n)
    for f0 in freqs:
        for _ in range(3):
            det = f0 * 2 ** (rng.uniform(-9, 9) / 1200)
            vib = 1 + 0.006 * np.sin(2 * np.pi * rng.uniform(4.6, 5.6) * t + rng.uniform(0, 6.28))
            ph = 2 * np.pi * np.cumsum(det * vib) / SR
            for k in range(1, 26):
                if det * k > 7000:
                    break
                out += _formant(det * k) / k ** 0.3 * np.sin(k * ph)
    env = np.minimum(1, t / 0.04) * np.minimum(1, (dur - t) / 0.12)
    return out * env


def _decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def _voice(work: Path, name: str, text: str, char: str, extra: dict | None = None) -> np.ndarray:
    v = {"speaker": "ndain", **CHARS[char].get("voice", {})}
    ex = {k: str(v[k]) for k in ("alpha", "pitch") if k in v}
    ex.update(extra or {})
    out = work / f"{name}.mp3"
    if not _clova(text, v["speaker"], "0", out, ex):
        raise RuntimeError("클로바 키가 없습니다 (.env의 CLOVA_API_KEY_ID / CLOVA_API_KEY)")
    return _decode(out)


def _soundtrack(work: Path) -> Path:
    rng = np.random.default_rng(3)
    quiet, loud = np.zeros(int(SR * TOTAL)), np.zeros(int(SR * TOTAL))   # 레퍼런스의 핵심 = 조용함과 폭발의 대비
    def put(sig, at, gain=1.0, to=None):
        dst = loud if to is None else to
        i = int(at * SR); n = min(sig.size, dst.size - i)
        if n > 0:
            dst[i:i + n] += sig[:n] * gain
    # 1) 고요한 밤 오르골 (0~6.5초). 6/8박, 8분음표 0.18초
    melody = [(392, 3), (440, 1), (392, 2), (329.63, 6), (392, 3), (440, 1), (392, 2), (329.63, 6), (587.33, 4), (587.33, 2), (493.88, 6)]
    at = 0.15
    for f, n in melody:
        put(_musicbox(f, n * 0.18 + 0.5), at, 0.22, quiet)
        at += n * 0.18
    for at2, f in [(0.15, 196), (2.31, 196), (4.47, 196)]:
        put(_musicbox(f, 1.6), at2, 0.12, quiet)
    # 2) 아기의 첫 소리 "삐…빅?"
    put(_tone(1800, 1900, 0.05, square=0.3), 4.75, 0.25, quiet); put(_tone(1400, 2200, 0.1, square=0.3), 4.95, 0.25, quiet)
    # 3) 합창: 8.3초에 폭발 (6.8~8.3초는 정적)
    chords = [(8.3, 2.0, [130.81, 196, 261.63, 329.63, 392]), (10.3, 2.0, [174.61, 220, 261.63, 349.23, 440]),
              (12.3, 2.0, [196, 246.94, 293.66, 392, 493.88]), (14.3, 2.1, [130.81, 196, 261.63, 329.63, 392]),
              (16.4, 1.2, [220, 261.63, 329.63, 440, 523.25]), (17.6, 1.8, [174.61, 220, 261.63, 349.23, 440]),
              (19.4, 2.0, [130.81, 196, 261.63, 329.63, 523.25]), (21.4, 1.6, [196, 246.94, 293.66, 392, 587.33]),
              (23.0, 1.8, [130.81, 196, 261.63, 392, 523.25])]
    for at, dur, fr in chords:
        put(_choir(fr, dur + 0.08, rng), at, 0.06 if at < 16.4 else 0.08)
    tt = np.arange(int(SR * 0.8)) / SR
    put(np.sin(2 * np.pi * 55 * tt) * np.exp(-tt / 0.25), 8.3, 0.9)                    # 쿵 (합창 시작)
    put(np.sin(2 * np.pi * 50 * tt) * np.exp(-tt / 0.25), 16.4, 0.9)                   # 쿵 (클로즈업)
    for at in (12.4, 12.7, 13.1):                                                         # 휙 (흐릿한 천사)
        n = rng.standard_normal(int(SR * 0.5)); n = np.convolve(n, np.ones(30) / 30, "same")
        put(n * np.sin(np.linspace(0, np.pi, n.size)), at, 0.8)
    put(_tone(300, 2000, 1.0, square=0.1), 23.8, 0.35)                                   # 급줌
    loud[int(24.8 * SR):] *= 0                                                            # 합창 뚝
    # 4) 대사
    put(_voice(work, "yell_can", "축하해!!!", "can"), 16.5, 1.6)
    put(_voice(work, "yell_prop", "축하해!", "prop"), 16.75, 0.9)
    put(_voice(work, "yell_tv", "축하해!", "tv"), 16.95, 0.9)
    put(_tone(1500, 1900, 0.07), 24.85, 0.3); put(_tone(2300, 2900, 0.09), 24.95, 0.3)
    put(_voice(work, "baby", "삐빅! 빅뉴스!", "ai", {"pitch": "-3"}), 25.1, 1.5)
    loud[int(27.0 * SR):] *= 0                                                            # 뚝
    # 5) 엔딩: 오르골 아르페지오
    for i, f in enumerate([392, 493.88, 587.33, 783.99]):
        put(_musicbox(f, 1.2), 27.5 + i * 0.12, 0.2, quiet)
    rms = lambda x, a, b: np.sqrt(np.mean(x[int(a * SR):int(b * SR)] ** 2)) + 1e-9
    loud *= 0.22 / rms(loud, 8.4, 16.3)                    # 합창 구간 기준
    quiet *= 0.22 * 10 ** (-15 / 20) / rms(quiet, 0.2, 6.4)  # 자장가는 15dB 작게
    buf = quiet + loud
    buf = np.tanh(buf * 1.2) / np.tanh(1.2) * 0.95         # 큰 소리 끝만 살짝 눌러 찢어지지 않게
    wav = work / "story.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((buf * 32767).astype(np.int16).tobytes())
    return wav


def render() -> Path:
    work = OUT / NAME
    work.mkdir(parents=True, exist_ok=True)
    wav = _soundtrack(work)
    from playwright.sync_api import sync_playwright
    silent = work / "video.mp4"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.on("pageerror", lambda e: print("pageerror:", e))
        pg.set_content(_page())
        enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        for k in range(int(TOTAL * FPS)):
            pg.evaluate(f"render({k / FPS})")
            enc.stdin.write(pg.screenshot(type="jpeg", quality=92))
        enc.stdin.close(); enc.wait()
        b.close()
    final = OUT / f"{NAME}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-ar", str(SR), "-shortest", str(final)], check=True)
    return final
