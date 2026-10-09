"""스토리 영상: 삐빅 탄생기 (성탄 장면 패러디, 약 28.5초) — v2

탐님 방향(2026-10-09): 레퍼런스의 컷·카메라·타이밍을 그대로 따른다. 전체가 잔잔하고 엄숙하며, 모두 눈을 지그시 감고 있고,
아기 삐빅만 눈을 멀뚱멀뚱 뜨고 있으며, 17.5초에 천사 딸깍 한 명만 정면으로 눈과 입을 크게 연다. 효과는 과하지 않게.
그림은 '픽셀 + CG 조명'(빛 번짐·빛줄기·먼지·원근 흐림·비네팅). 배경·인물은 저해상도 캔버스(216x384)에 도형으로 그려
그대로 5배 키우므로 형태가 분명한 픽셀이 된다.
오디오: 레퍼런스 원본 0~27.37초 그대로 + 마지막에 "삐빅" 한 번 (엔딩 카드·글자 없음).
사용: python -m radar story [레퍼런스 영상 경로]
"""
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from .shorts import OUT, W, H
from .shorts_anim import CHARS

FPS = 30
REF_END = 27.37          # 레퍼런스 소리를 쓰는 구간 (그 뒤는 틱톡 엔딩 화면)
BIBIK = 27.55            # 마지막 "삐빅"
TOTAL = 28.5
SR = 44100
NAME = "2026-10-09_story-bbibik-birth"
REF = Path.home() / "Downloads" / "IMG_1437.MP4"

PAGE_JS = r"""(() => {
const CH = %CHARS%;
const M = document.getElementById('c'), m = M.getContext('2d');
const L = document.createElement('canvas'); L.width = 216; L.height = 384; const l = L.getContext('2d');   // 픽셀 화면 (5배 확대)
const F = document.createElement('canvas'); F.width = 216; F.height = 384; const fc = F.getContext('2d');  // 앞쪽(흐림용)
const clamp01 = x => Math.min(1, Math.max(0, x)), ease = x => { x = clamp01(x); return x * x * (3 - 2 * x); };
const easeOut = x => 1 - Math.pow(1 - clamp01(x), 3);
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let x = Math.imul(seed ^ seed >>> 15, 1 | seed);
  x = x + Math.imul(x ^ x >>> 7, 61 | x) ^ x; return ((x ^ x >>> 14) >>> 0) / 4294967296; }; }
const BASE = {k:'#4a5a70', w:'#e8eef5', d:'#0f2233', e:'#5ae0ff', m:'#5ae0ff', s:'#9fb0c3', c:'#ff7a6b', a:'#ffd166', A:'#7a6a3a'};
const PAL = k => Object.assign({}, BASE, CH[k].pal, {O: '#7a1f2a', Z: '#e8d8a8'});

// ── 도형 도우미 (월드 좌표) ──
const poly = (c, pts, col) => { c.fillStyle = col; c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]); c.closePath(); c.fill(); };
const ell = (c, x, y, rx, ry, col, rot = 0) => { c.fillStyle = col; c.beginPath(); c.ellipse(x, y, rx, ry, rot, 0, 6.2832); c.fill(); };
const rect = (c, x, y, w, h, col) => { c.fillStyle = col; c.fillRect(x, y, w, h); };
const line = (c, x1, y1, x2, y2, w, col) => { c.strokeStyle = col; c.lineWidth = w; c.lineCap = 'round'; c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke(); };
function star(c, x, y, r, col) { c.fillStyle = col; c.beginPath();
  for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.45 : r; c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); }
  c.closePath(); c.fill(); }
function cam(c, z, cx, cy) { c.setTransform(z, 0, 0, z, 108 - cx * z, 192 - cy * z); }
const toScreen = (x, y, z, cx, cy) => [(108 + (x - cx) * z) * 5, (192 + (y - cy) * z) * 5];
function spr(c, rows, p, x, y, s) {
  for (let r = 0; r < rows.length; r++) for (let q = 0; q < rows[r].length; q++) {
    const ch = rows[r][q]; if (ch === '.' || !p[ch]) continue; c.fillStyle = p[ch]; c.fillRect(x + q * s, y + r * s, s + 0.04, s + 0.04);
  }
}

// ── 로봇 얼굴: 모두 눈을 지그시 감음 / 아기 삐빅은 멀뚱 / 딸깍만 크게 놀람 ──
function faceRows(k, mode) {
  const rows = CH[k].grid.map(r => r.split(''));
  const set = (x, y, ch) => { if (rows[y] && x >= 0 && x < 16) rows[y][x] = ch; };
  if (mode === 'closed') {
    if (k === 'prop') { for (let x = 4; x < 12; x++) set(x, 7, 'd'); for (const x of [5, 6, 9, 10]) set(x, 7, 'e'); }
    if (k === 'tv') { for (const x of [5, 6, 9, 10]) set(x, 7, 'e'); for (const x of [6, 9]) set(x, 6, 'd'); }
    if (k === 'can') { set(5, 6, 'B'); set(10, 6, 'B'); for (const x of [4, 5, 6, 9, 10, 11]) set(x, 6, 'Z'); }
  }
  if (mode === 'wide' && k === 'can') {
    for (const y of [5, 6, 7]) for (const x of [4, 5, 6, 9, 10, 11]) set(x, y, 'e');
    set(5, 6, 'B'); set(10, 6, 'B');
    for (const x of [6, 7, 8, 9]) { set(x, 9, 'O'); set(x, 10, 'O'); } set(7, 8, 'O'); set(8, 8, 'O');
    for (const [x, y] of [[2, 10], [2, 11], [1, 9], [13, 10], [13, 11], [14, 9]]) set(x, y, 's');   // 팔 번쩍
  }
  if (mode === 'blink' && k === 'ai') { for (let x = 4; x < 12; x++) { rows[6][x] = 'd'; rows[7][x] = [5, 6, 9, 10].includes(x) ? 'e' : 'd'; } }
  return rows.map(r => r.join(''));
}

// ── 천사 (후광·날개·로봇) ──
function angel(c, k, x, y, s, t, mode, ph = 0, alpha = 1) {
  if (alpha <= 0) return;
  c.save(); c.globalAlpha = alpha;
  const fl = Math.sin(t * 1.4 + ph) * 0.1;                              // 느린 날갯짓
  ell(c, x + 1.2 * s, y + 10.5 * s, 4.6 * s, 2.7 * s, '#f6f6ff', -0.55 + fl);
  ell(c, x + 14.8 * s, y + 10.5 * s, 4.6 * s, 2.7 * s, '#f6f6ff', 0.55 - fl);
  ell(c, x + 0.6 * s, y + 11.3 * s, 3.2 * s, 1.5 * s, '#d9dcef', -0.55 + fl);
  ell(c, x + 15.4 * s, y + 11.3 * s, 3.2 * s, 1.5 * s, '#d9dcef', 0.55 - fl);
  spr(c, faceRows(k, mode), PAL(k), x, y, s);
  c.strokeStyle = '#ffe28a'; c.lineWidth = Math.max(0.7, 0.85 * s);
  c.beginPath(); c.ellipse(x + 8 * s, y - 1.6 * s, 4.4 * s, 1.2 * s, 0, 0, 6.2832); c.stroke();
  c.restore();
}

// ── 마구간 안 ──
const STRAW = Array.from({length: 70}, (_, i) => { const R = rng(i + 3); return [R() * 240 - 12, 304 + R() * 70, 2 + R() * 4, R() - 0.5]; });
function person(c, x, g, t, robe, cloth, beard, staff, ph) {               // 서 있는 남자 (왼쪽을 봄), 눈 감음
  const b = Math.sin(t * 1.1 + ph) * 0.4;
  poly(c, [[x - 16, g], [x + 16, g], [x + 11, g - 70], [x - 9, g - 70]], robe);
  poly(c, [[x - 9, g - 70], [x + 11, g - 70], [x + 6, g - 60], [x - 6, g - 60]], 'rgba(0,0,0,0.18)');
  rect(c, x - 12, g - 44, 24, 3, '#c9a227');
  ell(c, x, g - 82 + b, 11, 12, cloth);
  ell(c, x - 2, g - 80 + b, 7, 8, '#e8b98f');
  if (beard) poly(c, [[x - 9, g - 77 + b], [x + 4, g - 77 + b], [x + 1, g - 66 + b], [x - 6, g - 68 + b]], beard);
  line(c, x - 7, g - 82 + b, x - 3.5, g - 81.2 + b, 1, '#3a2010');      // 지그시 감은 눈
  ell(c, x - 12, g - 50, 4, 4, '#e8b98f');
  if (staff) { line(c, x + 20, g - 104, x + 20, g, 2.2, '#6b4423');
    c.strokeStyle = '#6b4423'; c.lineWidth = 2.2; c.beginPath(); c.arc(x + 15, g - 104, 5, Math.PI, Math.PI * 2); c.stroke(); }
}
function mary(c, x, g, t) {                                                 // 무릎 꿇은 엄마 (오른쪽을 봄), 눈 감음
  const b = Math.sin(t * 1.2) * 0.4;
  poly(c, [[x - 22, g], [x + 26, g], [x + 18, g - 34], [x - 10, g - 38]], '#2f5fc8');
  poly(c, [[x - 2, g - 36], [x + 14, g - 36], [x + 18, g - 12], [x - 2, g - 12]], '#e9ecf3');
  ell(c, x + 4, g - 50 + b, 13, 16, '#2f5fc8');
  ell(c, x + 3, g - 60 + b, 8, 3.5, '#f2d36b');                              // 앞머리
  ell(c, x + 8, g - 47 + b, 7.5, 8.5, '#f0c8a0');
  line(c, x + 9, g - 48 + b, x + 12.5, g - 47.4 + b, 1, '#5a3a22');
  ell(c, x + 19, g - 28, 4, 5, '#f0c8a0');                                   // 모은 손
}
function manger(c, x, g) {
  for (const sgn of [-1, 1]) { line(c, x + sgn * 30, g - 18, x + sgn * 18, g, 3, '#4e3119'); line(c, x + sgn * 18, g - 18, x + sgn * 30, g, 3, '#4e3119'); }
  poly(c, [[x - 36, g - 38], [x + 36, g - 38], [x + 28, g - 16], [x - 28, g - 16]], '#7a4f2a');
  line(c, x - 32, g - 27, x + 32, g - 27, 1, '#5e3b1f');
  rect(c, x - 37, g - 40, 74, 3, '#8b5e34');
  for (let i = 0; i < 16; i++) { const sx = x - 35 + i * 4.6; line(c, sx, g - 40, sx + (i % 2 ? 3 : -3), g - 45 - (i % 3), 1.1, '#e3bd5a'); }
}
function baby(c, x, g, t) {                                                 // 강보에 싸인 아기 삐빅 (멀뚱멀뚱)
  const s = 1.45, mode = (t > 6.0 && t < 6.25) ? 'blink' : 'open';
  ell(c, x, g - 39, 22, 8.5, '#f6f1e6');                                     // 강보
  spr(c, faceRows('ai', mode).slice(0, 12), PAL('ai'), x - 8 * s, g - 46 - 12 * s, s);   // 얼굴은 강보 위로
  line(c, x - 14, g - 42, x + 4, g - 37, 0.8, '#d8d0bf'); line(c, x - 2, g - 44, x + 14, g - 39, 0.8, '#d8d0bf');
}
function lamb(c, x, g) {
  for (const dx of [-6, -2, 3, 7]) line(c, x + dx, g - 6, x + dx, g, 1.5, '#3a3030');
  ell(c, x, g - 10, 11, 7, '#f2efe8'); ell(c, x - 6, g - 13, 5, 4, '#f7f4ee'); ell(c, x + 5, g - 14, 5, 4, '#f7f4ee');
  ell(c, x + 11, g - 13, 4, 3.5, '#3a3030'); line(c, x + 11, g - 13.5, x + 13, g - 13.2, 0.7, '#cfc6b8');
}
function interior(c, t) {
  for (let i = -4; i < 24; i++) { rect(c, i * 12, -80, 12, 384, i % 2 ? '#5b3a20' : '#4e3119'); rect(c, i * 12, -80, 1, 384, '#35210f'); }
  rect(c, -60, 112, 340, 9, '#3e2714');
  poly(c, [[-60, 10], [108, -40], [280, 10], [280, 18], [108, -32], [-60, 18]], '#3e2714');
  rect(c, -60, 300, 340, 120, '#8f6a2c');
  for (const [x, y, len, sl] of STRAW) line(c, x, y, x + len, y + sl * 2, 0.8, '#c99b45');
  ell(c, 214, 300, 44, 20, '#a8823a'); ell(c, 4, 302, 30, 14, '#a8823a');
  line(c, 108, -80, 108, 140, 0.8, '#2a1a0c');
  star(c, 108, 150, 10, '#ffe28a');
  person(c, 208, 318, t, '#3f7f4a', '#e6e2d0', '#4a3420', false, 2);     // 목자 (초록)
  person(c, 228, 322, t, '#a93a2e', '#d4b483', '#7a5030', false, 3);     // 목자 (빨강)
  person(c, 166, 320, t, '#9a5230', '#c8a060', '#5a3a1e', true, 1);      // 아빠
  manger(c, 108, 318); baby(c, 108, 318, t);
  mary(c, 46, 324, t); lamb(c, 78, 336);
}
// 조명: 별빛 빛줄기 + 따뜻한 빛 + 빛 속 먼지
const DUST = Array.from({length: 45}, (_, i) => { const R = rng(i * 5 + 11); return [R(), R(), 0.3 + R() * 0.7, R() * 6.28]; });
function interiorLight(t, z, cx, cy, a) {
  const [sx, sy] = toScreen(108, 150, z, cx, cy);
  m.save(); m.globalCompositeOperation = 'screen'; m.globalAlpha = a;
  for (const k of [-1, 0, 1]) {
    const gr = m.createLinearGradient(sx, sy, sx, sy + 1500); gr.addColorStop(0, 'rgba(255,225,150,0.2)'); gr.addColorStop(1, 'rgba(255,225,150,0)');
    m.fillStyle = gr; m.beginPath(); m.moveTo(sx, sy); m.lineTo(sx + k * 260 - 130 * z, sy + 1500); m.lineTo(sx + k * 260 + 130 * z, sy + 1500); m.closePath(); m.fill();
  }
  const [bx, by] = toScreen(108, 280, z, cx, cy);
  const wg = m.createRadialGradient(bx, by, 20, bx, by, 520 * Math.max(0.6, z)); wg.addColorStop(0, 'rgba(255,200,120,0.3)'); wg.addColorStop(1, 'rgba(255,200,120,0)');
  m.fillStyle = wg; m.fillRect(0, 0, 1080, 1920);
  for (const [px, py, sp, ph] of DUST) {
    const x = (px * 1080 + Math.sin(t * 0.5 + ph) * 30) % 1080, y = (py * 1920 + t * 18 * sp) % 1920;
    m.fillStyle = `rgba(255,240,200,${0.3 + 0.3 * Math.sin(t * 2 + ph)})`; m.fillRect(Math.round(x / 5) * 5, Math.round(y / 5) * 5, 5, 5);
  }
  m.restore();
}

// ── 바깥 밤 (마구간은 땅 위에) ──
const SKY = Array.from({length: 220}, (_, i) => { const R = rng(i * 7 + 1); return [R() * 300 - 40, -560 + R() * 850, R() < 0.15 ? 1.2 : 0.7, R() * 6.28]; });
function tree(c, x, g, s) { rect(c, x - 1.5 * s, g - 8 * s, 3 * s, 8 * s, '#1c140c');
  for (let i = 0; i < 4; i++) poly(c, [[x - (12 - i * 2.4) * s, g - (6 + i * 7) * s], [x, g - (20 + i * 7) * s], [x + (12 - i * 2.4) * s, g - (6 + i * 7) * s]], '#0f2a22'); }
function exterior(c, t) {
  const gr = c.createLinearGradient(0, -560, 0, 330); gr.addColorStop(0, '#050920'); gr.addColorStop(0.72, '#15225a'); gr.addColorStop(1, '#2a3d84');
  c.fillStyle = gr; c.fillRect(-80, -600, 380, 1000);
  for (const [x, y, s, ph] of SKY) { c.globalAlpha = 0.45 + 0.4 * Math.sin(t * 1.5 + ph); rect(c, x, y, s, s, '#ffffff'); } c.globalAlpha = 1;
  const mist = c.createLinearGradient(0, 270, 0, 320); mist.addColorStop(0, 'rgba(120,140,200,0)'); mist.addColorStop(1, 'rgba(120,140,200,0.25)');
  c.fillStyle = mist; c.fillRect(-80, 270, 380, 50);
  poly(c, [[-80, 304], [10, 286], [80, 298], [150, 284], [300, 300], [300, 420], [-80, 420]], '#16224c');
  tree(c, 18, 322, 1.25); tree(c, 200, 318, 1.05); tree(c, 40, 326, 0.8);
  poly(c, [[-80, 336], [50, 326], [150, 332], [300, 324], [300, 440], [-80, 440]], '#0c171f');
  rect(c, 70, 340, 76, 4, '#2a1c10');                                       // 바닥 받침 (땅 위에 앉힘)
  rect(c, 76, 308, 64, 32, '#5b3a20'); rect(c, 76, 308, 64, 2, '#3a2414');
  poly(c, [[68, 310], [108, 282], [148, 310]], '#3a2414'); poly(c, [[74, 309], [108, 286], [142, 309]], '#4a2e18');
  for (const px of [76, 92, 124, 138]) rect(c, px, 308, 2.5, 32, '#3a2414');
  rect(c, 98, 316, 20, 24, '#ffcf6b'); rect(c, 104, 326, 8, 14, '#c98a3a');
  ell(c, 60, 338, 9, 5, '#7a5a24'); for (const fx of [22, 32, 42]) rect(c, fx, 328, 2, 12, '#3a2414'); rect(c, 20, 331, 26, 1.5, '#3a2414');
  star(c, 108, 250, 6.5, '#ffe28a');
}
function exteriorLight(z, cx, cy, a) {
  m.save(); m.globalCompositeOperation = 'screen'; m.globalAlpha = a;
  for (const [x, y, r, col] of [[108, 328, 320, 'rgba(255,200,110,0.4)'], [108, 250, 260, 'rgba(255,230,150,0.3)']]) {
    const [sx, sy] = toScreen(x, y, z, cx, cy); const gr = m.createRadialGradient(sx, sy, 6, sx, sy, r * z);
    gr.addColorStop(0, col); gr.addColorStop(1, 'rgba(0,0,0,0)'); m.fillStyle = gr; m.fillRect(0, 0, 1080, 1920);
  }
  m.restore();
}

// ── 천사 배치 ──
const SKYANG = (() => { const R = rng(41), out = [];                         // 서로 겹치지 않게 흩뿌림 (격자 X)
  while (out.length < 44) { const x = -6 + R() * 210, y = -80 + R() * 300;
    if (out.every(o => Math.hypot(o.x - x, (o.y - y) * 1.2) > 25)) out.push({k: ['prop', 'tv', 'can'][out.length % 3], x, y, s: 0.85 + R() * 0.45, ph: R() * 6.28, d: R() * 0.5}); }
  return out; })();
const PACK = (() => { const R = rng(77), out = []; let tries = 0;
  while (out.length < 78 && tries++ < 20000) { const x = -8 + R() * 214, y = -4 + R() * 360;
    if (out.every(o => Math.hypot(o.x - x, (o.y - y) * 1.15) > 19)) out.push({k: ['prop', 'tv', 'can'][out.length % 3], x, y, s: 0.7 + R() * 0.55, ph: R() * 6.28}); }
  return out; })();
const MID = [['prop', 22, 108, 2.3], ['tv', 150, 96, 2.3], ['tv', 14, 250, 2.0], ['prop', 160, 260, 2.0], ['tv', 70, 40, 1.4], ['prop', 140, 30, 1.3], ['can', 30, 330, 1.6], ['can', 168, 350, 1.5]];
const FAR = Array.from({length: 16}, (_, i) => { const R = rng(i * 3 + 77); return {k: ['prop', 'tv', 'can'][i % 3], x: R() * 200, y: R() * 360, s: 0.8, ph: R() * 6.28}; });
function skyBG(c) { const gr = c.createLinearGradient(0, 0, 0, 384); gr.addColorStop(0, '#0a1440'); gr.addColorStop(1, '#22348a'); c.fillStyle = gr; c.fillRect(0, 0, 216, 384);
  for (const [x, y, s] of SKY.slice(0, 90)) rect(c, ((x + 40) % 216 + 216) % 216, ((y + 560) % 384 + 384) % 384, s, s, 'rgba(255,255,255,0.6)'); }
function closeSky(t, yell, fgBlur, push) {                                 // 천사 무리 안의 중간 샷
  l.setTransform(1, 0, 0, 1, 0, 0); skyBG(l);
  const z = 1 + push, off = (v, cv) => cv + (v - cv) * z;
  for (const a of FAR) angel(l, a.k, a.x, a.y + Math.sin(t + a.ph) * 2, a.s, t, 'closed', a.ph, 0.55);
  for (const [k, x, y, s] of MID) angel(l, k, off(x, 108), off(y + Math.sin(t * 0.9 + x) * 2, 192), s * z, t, 'closed', x);
  const cs = 3.3 * z; angel(l, 'can', 108 - 8 * cs, 168 - 8.5 * cs + Math.sin(t * 0.8) * 1.5, cs, t, yell ? 'wide' : 'closed', 1);
  fc.setTransform(1, 0, 0, 1, 0, 0); fc.clearRect(0, 0, 216, 384);
  angel(fc, 'tv', -40, 250, 6.0, t, 'closed', 2); angel(fc, 'prop', 150, -30, 5.5, t, 'closed', 3);
  present(1); bloom(0.32); fg(fgBlur); vignette(0.5);
}

// ── 합성 ──
function present(a) { m.save(); m.imageSmoothingEnabled = false; m.globalAlpha = a; m.drawImage(L, 0, 0, 1080, 1920); m.restore(); }
function bloom(a) { m.save(); m.imageSmoothingEnabled = true; m.globalCompositeOperation = 'screen'; m.globalAlpha = a; m.filter = 'blur(16px)'; m.drawImage(L, 0, 0, 1080, 1920); m.restore(); }
function fg(blur) { m.save(); m.imageSmoothingEnabled = false; if (blur > 0.3) m.filter = `blur(${blur}px)`; m.drawImage(F, 0, 0, 1080, 1920); m.restore(); }
function vignette(a) { const gr = m.createRadialGradient(540, 960, 520, 540, 960, 1180); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, `rgba(0,0,0,${a})`);
  m.fillStyle = gr; m.fillRect(0, 0, 1080, 1920); }
function shotInterior(t, a) {
  const p = clamp01(t / 5.2), z = t < 5.2 ? 2.5 - 1.5 * easeOut(p) : 1.0 - 0.03 * clamp01((t - 5.2) / 2.8);
  const cx = 112 - 8 * (1 - easeOut(p)), cy = 272 - 48 * easeOut(p);
  l.setTransform(1, 0, 0, 1, 0, 0); l.fillStyle = '#000'; l.fillRect(0, 0, 216, 384); cam(l, z, cx, cy); interior(l, t);
  present(a); bloom(0.3 * a); interiorLight(t, z, cx, cy, a);
}
function shotExterior(t, a, cy, angels) {
  l.setTransform(1, 0, 0, 1, 0, 0); cam(l, 1, 108, cy); exterior(l, t);
  if (angels) for (const s of SKYANG) angel(l, s.k, s.x, s.y + Math.sin(t * 0.9 + s.ph) * 1.5, s.s, t, 'closed', s.ph, ease((t - 9.0 - s.d) / 1.5));
  present(a); bloom(0.35 * a); exteriorLight(1, 108, cy, a);
}
window.render = (t) => {
  m.setTransform(1, 0, 0, 1, 0, 0); m.filter = 'none'; m.globalCompositeOperation = 'source-over'; m.globalAlpha = 1;
  m.fillStyle = '#000'; m.fillRect(0, 0, 1080, 1920);
  if (t < 8.0) {                                              // 1~2. 이어지는 줌아웃 → 디졸브
    shotInterior(t, 1);
    if (t > 7.5) shotExterior(t, ease((t - 7.5) / 0.5), 250, false);
    vignette(0.45);
  } else if (t < 13.33) {                                     // 3~4. 위로 틸트 → 천사들이 한꺼번에 서서히
    const cy = 250 - 160 * ease((t - 8.0) / 1.0) - 6 * clamp01((t - 9.0) / 4.3);
    shotExterior(t, 1, cy, t > 8.9); vignette(0.45);
  } else if (t < 17.47) closeSky(t, false, 14 * (1 - ease((t - 13.33) / 1.17)), 0.04 * clamp01((t - 13.33) / 4));   // 5~6. 초점 맞춰지기
  else if (t < 18.0) {                                        // 7a. 딸깍 초근접 (0.5초)
    l.setTransform(1, 0, 0, 1, 0, 0); skyBG(l); const s = 12.5; angel(l, 'can', 108 - 8 * s, 205 - 8.5 * s, s, t, 'wide', 1);
    present(1); bloom(0.3); vignette(0.5);
  } else if (t < 21.13) closeSky(t, true, 0, 0.03 + 0.05 * clamp01((t - 18) / 3.1));            // 7b. 딸깍만 눈·입 크게
  else if (t < 24.9) {                                        // 8. 천사로 가득한 하늘, 천천히 다가감
    l.setTransform(1, 0, 0, 1, 0, 0); skyBG(l);
    const z = 1 + 0.07 * clamp01((t - 21.13) / 3.8); cam(l, z, 108, 200);
    for (const a of PACK) angel(l, a.k, a.x, a.y + Math.sin(t * 0.9 + a.ph) * 1.5, a.s, t, 'closed', a.ph);
    poly(l, [[-30, 384], [-30, 330], [40, 312], [70, 330], [70, 384]], '#120c08'); rect(l, 44, 300, 9, 20, '#120c08'); tree(l, 196, 392, 1.2);
    present(1); bloom(0.4); vignette(0.5);
  } else if (t < 28.1) closeSky(t, false, 12 * (1 - ease((t - 24.9) / 1.1)), 0.02 + 0.05 * clamp01((t - 24.9) / 3));  // 9. 합창하는 천사들 → "삐빅"
};
})();"""


def _page() -> str:
    js = PAGE_JS.replace("%CHARS%", json.dumps(CHARS))
    return (f"<html><head><meta charset='utf-8'><style>*{{margin:0}}body{{width:{W}px;height:{H}px;background:#000;overflow:hidden}}"
            f"canvas{{display:block}}</style></head><body><canvas id='c' width='{W}' height='{H}'></canvas><script>{js}</script></body></html>")


def _bibik() -> np.ndarray:
    def tone(f0, f1, dur):
        t = np.arange(int(SR * dur)) / SR
        ph = 2 * np.pi * np.cumsum(np.linspace(f0, f1, t.size)) / SR
        return (0.6 * np.sin(ph) + 0.2 * np.sign(np.sin(ph))) * np.minimum(1, t / 0.004) * np.exp(-t / (dur * 0.9))
    return np.concatenate([tone(1500, 1900, 0.07), np.zeros(int(SR * 0.03)), tone(2300, 2900, 0.09)])


def _soundtrack(work: Path, ref: Path) -> Path:
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-t", str(REF_END), "-i", str(ref), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    orig = np.frombuffer(raw, dtype=np.float32).astype(np.float64)
    buf = np.zeros(int(SR * TOTAL))
    n = min(orig.size, buf.size)
    buf[:n] = orig[:n]
    fade = int(SR * 0.04); buf[n - fade:n] *= np.linspace(1, 0, fade)          # 원본 끝 '틱' 방지
    b = _bibik(); i = int(BIBIK * SR); buf[i:i + b.size] += b * 0.35
    wav = work / "story.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    return wav


def render(ref: str | None = None) -> Path:
    ref = Path(ref) if ref else REF
    work = OUT / NAME
    work.mkdir(parents=True, exist_ok=True)
    wav = _soundtrack(work, ref)
    from playwright.sync_api import sync_playwright
    silent = work / "video.mp4"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.on("pageerror", lambda e: print("pageerror:", e))
        pg.set_content(_page())
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
