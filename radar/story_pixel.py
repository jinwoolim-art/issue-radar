"""픽셀 규칙을 지키는 스토리용 그림 도구 + 캐릭터 디자인 시트.

규칙 (탐님 2026-10-09): 모든 형태는 픽셀 칸 단위로만. 부드러운 선·회전·반투명 가장자리 금지.
  - 원/다각형은 픽셀 중심이 안에 들어가는 칸만 1x1로 채운다 (안티앨리어싱 없음)
  - 사선은 브레젠험(계단식) 직선
  - 인물은 스프라이트 캔버스에 그린 뒤 자동으로 1픽셀 외곽선
  - 카메라는 장면을 1배로 그리고 화면 전체를 최근접 확대 (픽셀이 같이 커짐)
사용: python -m radar sprites → out/story_design_sheet.png
"""
import json
from pathlib import Path

from .shorts import OUT
from .shorts_anim import CHARS

PIXEL_JS = r"""
const CH = %CHARS%;
const SKIN = '#f0c49a', SKIN2 = '#d9a77a', DARK = '#2a1a12', LIP = '#7a1f2a';
function hex(c) { const n = parseInt(c.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function P(c, x, y, col) { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), 1, 1); }
function R(c, x, y, w, h, col) { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); }
function E(c, cx, cy, rx, ry, col) {                         // 픽셀 타원: 칸 중심이 안에 들면 채움
  c.fillStyle = col;
  for (let y = Math.floor(cy - ry - 1); y <= Math.ceil(cy + ry + 1); y++) for (let x = Math.floor(cx - rx - 1); x <= Math.ceil(cx + rx + 1); x++) {
    const dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry; if (dx * dx + dy * dy <= 1) c.fillRect(x, y, 1, 1);
  }
}
function G(c, pts, col) {                                     // 픽셀 다각형
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]); c.fillStyle = col;
  for (let y = Math.floor(Math.min(...ys)); y <= Math.ceil(Math.max(...ys)); y++) for (let x = Math.floor(Math.min(...xs)); x <= Math.ceil(Math.max(...xs)); x++) {
    const px = x + 0.5, py = y + 0.5; let ins = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const [xi, yi] = pts[i], [xj, yj] = pts[j];
      if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) ins = !ins;
    }
    if (ins) c.fillRect(x, y, 1, 1);
  }
}
function Ln(c, x0, y0, x1, y1, col, th = 1) {                 // 계단식 직선 (브레젠험)
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1; let err = dx + dy;
  c.fillStyle = col;
  for (;;) { c.fillRect(x0, y0, th, th); if (x0 === x1 && y0 === y1) break; const e2 = 2 * err; if (e2 >= dy) { err += dy; x0 += sx; } if (e2 <= dx) { err += dx; y0 += sy; } }
}
function S(c, rows, pal, x, y) {                              // 문자 그림 스프라이트 (1칸 = 1픽셀)
  for (let r = 0; r < rows.length; r++) for (let q = 0; q < rows[r].length; q++) { const ch = rows[r][q]; if (ch !== '.' && pal[ch]) P(c, x + q, y + r, pal[ch]); }
}
function outlined(w, h, draw, ol = DARK) {                    // 그린 뒤 바깥에 1픽셀 외곽선 자동
  const cv = document.createElement('canvas'); cv.width = w + 2; cv.height = h + 2; const c = cv.getContext('2d');
  c.translate(1, 1); draw(c); c.setTransform(1, 0, 0, 1, 0, 0);
  const W2 = w + 2, H2 = h + 2, id = c.getImageData(0, 0, W2, H2), d = id.data, out = new Uint8ClampedArray(d), [r, g, b] = hex(ol);
  for (let y = 0; y < H2; y++) for (let x = 0; x < W2; x++) {
    const i = (y * W2 + x) * 4; if (d[i + 3] !== 0) continue;
    for (const [ox, oy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = x + ox, ny = y + oy;
      if (nx >= 0 && ny >= 0 && nx < W2 && ny < H2 && d[(ny * W2 + nx) * 4 + 3] > 0) { out[i] = r; out[i + 1] = g; out[i + 2] = b; out[i + 3] = 255; break; } }
  }
  c.putImageData(new ImageData(out, W2, H2), 0, 0); return cv;
}

// ── 로봇 얼굴 (16x17) ──
const RBASE = {k:'#4a5a70', w:'#e8eef5', d:'#0f2233', e:'#5ae0ff', m:'#5ae0ff', s:'#9fb0c3', c:'#ff7a6b', a:'#ffd166', A:'#7a6a3a'};
const RPAL = k => Object.assign({}, RBASE, CH[k].pal, {O: LIP, Z: '#f4e6b0', T: '#e8607a', U: '#ffb3c0'});
function robotRows(k, o = {}) {        // o: {eyes:'open'|'U'|'blink'|'lookL'|'lookR'|'wink'|'wide', mouth:false|true|'yell', uvula:0|1, arms:'up'|null}
  const rows = CH[k].grid.map(r => r.split('')), set = (x, y, ch) => { if (rows[y] && x >= 0 && x < 16) rows[y][x] = ch; };
  const eyes = o.eyes || 'open';
  if (k === 'ai') {
    const clear = () => { for (const y of [6, 7]) for (let x = 4; x < 12; x++) set(x, y, 'd'); };
    if (eyes === 'U' || eyes === 'wink') { clear(); if (eyes === 'wink') { set(5, 6, 'e'); set(6, 6, 'e'); set(5, 7, 'e'); set(6, 7, 'e'); } else { set(4, 6, 'e'); set(6, 6, 'e'); set(5, 7, 'e'); }
      set(9, 6, 'e'); set(11, 6, 'e'); set(10, 7, 'e'); }
    if (eyes === 'blink') { clear(); for (const x of [5, 6, 9, 10]) set(x, 7, 'e'); }
    if (eyes === 'lookL' || eyes === 'lookR') { clear(); const s = eyes === 'lookL' ? -1 : 1; for (const [x, y] of [[5, 6], [6, 6], [5, 7], [6, 7], [9, 6], [10, 6], [9, 7], [10, 7]]) set(x + s, y, 'e'); }
    if (o.mouth) { set(6, 9, 'O'); set(7, 9, 'O'); set(8, 9, 'O'); set(9, 9, 'O'); set(7, 8, 'O'); set(8, 8, 'O'); }
  }
  if (k === 'prop') {
    if (eyes === 'U') { for (const y of [6, 7, 8]) for (let x = 4; x < 12; x++) set(x, y, 'd'); for (const [x, y] of [[4, 7], [6, 7], [5, 8], [9, 7], [11, 7], [10, 8]]) set(x, y, 'e'); }
    if (o.mouth) { set(7, 9, 'O'); set(8, 9, 'O'); set(7, 10, 'O'); set(8, 10, 'O'); } else { set(7, 9, 'k'); set(8, 9, 'k'); }
  }
  if (k === 'tv') {
    if (eyes === 'U') { for (const y of [6, 7]) for (let x = 5; x < 11; x++) set(x, y, 'd'); for (const [x, y] of [[5, 6], [7, 6], [6, 7], [8, 6], [10, 6], [9, 7]]) set(x, y, 'e'); }
    for (let x = 5; x < 11; x++) set(x, 8, 'd');
    if (o.mouth) { for (const x of [6, 7, 8, 9]) set(x, 8, 'O'); } else { set(7, 8, 'm'); set(8, 8, 'm'); }
  }
  if (k === 'can') {
    if (eyes === 'U') { set(5, 6, 'B'); set(10, 6, 'B'); for (const [x, y] of [[4, 6], [6, 6], [5, 7], [9, 6], [11, 6], [10, 7]]) set(x, y, 'Z'); }
    if (eyes === 'wide') { for (const y of [5, 6, 7]) for (const x of [4, 5, 6, 9, 10, 11]) set(x, y, 'e'); set(5, 6, 'B'); set(10, 6, 'B'); }
    if (o.mouth === 'yell') {                                   // 크게 벌린 입 + 혀 + 떨리는 목젖
      for (const x of [6, 7, 8, 9]) set(x, 8, 'O');
      for (const y of [9, 10, 11]) for (const x of [5, 6, 7, 8, 9, 10]) set(x, y, 'O');
      for (const x of [6, 7, 8, 9]) set(x, 12, 'O');
      for (const x of [6, 7, 8, 9]) set(x, 11, 'T'); set(7, 12, 'T'); set(8, 12, 'T');
      const ux = o.uvula ? 8 : 7; set(ux, 9, 'U'); set(ux, 10, 'U');
    } else if (o.mouth) { for (const x of [6, 7, 8, 9]) set(x, 9, 'O'); set(7, 8, 'O'); set(8, 8, 'O'); set(7, 10, 'O'); set(8, 10, 'O'); }
  }
  if (o.arms === 'up') { const L = CH[k].arm_shift[0], Rr = CH[k].arm_shift[1];
    for (const [x, y] of [[2, 10], [2, 11], [1, 9], [1, 8]]) set(x + L, y, 's'); for (const [x, y] of [[13, 10], [13, 11], [14, 9], [14, 8]]) set(x + Rr, y, 's'); }
  return rows.map(r => r.join(''));
}
function robot(c, k, x, y, o) { S(c, robotRows(k, o), RPAL(k), x, y); }

// ── 천사 = 후광 + 날개(2장) + 로봇 ──
const HALO = [".gggggggg.", "g........g", ".gggggggg."];
const WUP = ["......ww", "....wwww", "..wwwwww", "wwwwwwww", ".wwwwwwW", "..wwWW.."];
const WDN = ["..wwWW..", ".wwwwwwW", "wwwwwwww", "..wwwwww", "....wwww", "......ww"];
const mir = rows => rows.map(r => [...r].reverse().join(''));
const WPAL = {w: '#f6f6ff', W: '#c9cde4'}, HPAL = {g: '#ffd166'};
function angelCanvas(k, o, wingUp) {
  return outlined(34, 26, c => {
    S(c, wingUp ? WUP : WDN, WPAL, 0, 11); S(c, mir(wingUp ? WUP : WDN), WPAL, 26, 11);
    robot(c, k, 9, 5, o); S(c, HALO, HPAL, 12, 0);
  }, '#141a33');
}

// ── 사람들 (눈은 U자로 감음, 입은 뻥끗) ──
function eyeU(c, x, y) { P(c, x, y, DARK); P(c, x + 2, y, DARK); P(c, x + 1, y + 1, DARK); }
function mary(o = {}) {               // o: {mouth, turned, nod}  무릎 꿇은 엄마 (오른쪽을 봄)
  const hd = o.nod ? 1 : 0;
  return outlined(46, 60, c => {
    G(c, [[10, 26], [34, 26], [44, 59], [2, 59]], '#3d6fe0');
    G(c, [[24, 42], [44, 59], [24, 59]], '#2f58c0');
    G(c, [[17, 30], [29, 30], [31, 59], [15, 59]], '#eef0f5');
    G(c, [[26, 30], [36, 33], [37, 41], [27, 40]], '#3d6fe0');
    E(c, 38, 39, 3, 3.2, SKIN);
    E(c, 22, 17 + hd, 13, 15, '#3d6fe0');
    const fx = o.turned ? 22 : 25;
    E(c, fx, 18 + hd, 8, 9, SKIN);
    E(c, fx - 1, 10 + hd, 8.5, 3.2, '#6b4423');
    if (o.turned) { R(c, fx - 4, 16 + hd, 1, 2, DARK); R(c, fx + 3, 16 + hd, 1, 2, DARK); }
    else { eyeU(c, fx - 5, 17 + hd); eyeU(c, fx + 1, 17 + hd); }
    P(c, fx - 6, 21 + hd, '#e89a9a'); P(c, fx + 4, 21 + hd, '#e89a9a');
    if (o.mouth) { R(c, fx - 1, 22 + hd, 2, 3, LIP); P(c, fx - 2, 23 + hd, LIP); P(c, fx + 1, 23 + hd, LIP); }
    else R(c, fx - 1, 23 + hd, 2, 1, LIP);
  });
}
function man(o = {}) {                // o: {mouth, nod, robe, robe2, cloth, band, beard, staff}  서 있는 남자 (왼쪽을 봄)
  const hd = o.nod ? 1 : 0;
  return outlined(44, 90, c => {
    G(c, [[9, 40], [33, 40], [37, 89], [5, 89]], o.robe);
    G(c, [[27, 40], [33, 40], [37, 89], [30, 89]], o.robe2);
    R(c, 7, 60, 29, 3, '#c9a227');
    G(c, [[11, 44], [4, 58], [9, 61], [15, 48]], o.robe); E(c, 6, 61, 3, 3, SKIN);
    if (o.staff) { R(c, 38, 9, 2, 81, '#6b4423'); Ln(c, 38, 9, 35, 5, '#6b4423', 2); Ln(c, 35, 5, 32, 7, '#6b4423', 2); E(c, 38, 52, 3, 3, SKIN); }
    E(c, 21, 20 + hd, 12, 14, o.cloth); R(c, 10, 13 + hd, 23, 2, o.band);
    E(c, 19, 23 + hd, 8, 9, SKIN);
    if (o.beard) { E(c, 19, 30 + hd, 8, 5.5, o.beard); R(c, 12, 26 + hd, 14, 1, o.beard); }
    eyeU(c, 13, 21 + hd); eyeU(c, 19, 21 + hd);
    if (o.mouth) { R(c, 18, 29 + hd, 3, 3, '#2a1010'); } else R(c, 18, 30 + hd, 3, 1, '#2a1010');
  });
}
const JOSEPH = {robe: '#9a5230', robe2: '#7a3e22', cloth: '#c8a060', band: '#a8823a', beard: '#5a3a1e', staff: true};
const SHEPA = {robe: '#3f8f4f', robe2: '#2f6f3c', cloth: '#e6e2d0', band: '#4a78c0', beard: '#4a3420', staff: false};
const SHEPB = {robe: '#b8432f', robe2: '#8e3123', cloth: '#d4b483', band: '#8a5a2a', beard: null, staff: false};
function lamb() {
  return outlined(26, 18, c => {
    for (const lx of [5, 9, 14, 18]) R(c, lx, 12, 2, 5, '#3a3030');
    E(c, 11, 9, 10, 5.5, '#f2efe8'); E(c, 5, 6, 4, 3, '#f7f4ee'); E(c, 12, 5, 4.5, 3, '#f7f4ee'); E(c, 18, 7, 3.5, 3, '#f7f4ee');
    E(c, 22, 7, 3.5, 3.5, '#3a3030'); P(c, 23, 6, '#e8e0d0'); R(c, 19, 4, 2, 2, '#3a3030');
  });
}
function manger(baby = {}) {         // 구유 + 강보 + 아기 삐빅
  return outlined(60, 46, c => {
    Ln(c, 12, 30, 20, 45, '#4e3119', 2); Ln(c, 20, 30, 12, 45, '#4e3119', 2); Ln(c, 40, 30, 48, 45, '#4e3119', 2); Ln(c, 48, 30, 40, 45, '#4e3119', 2);
    G(c, [[4, 17], [56, 17], [50, 31], [10, 31]], '#7a4f2a'); R(c, 8, 23, 44, 1, '#5e3b1f'); R(c, 9, 27, 42, 1, '#5e3b1f');
    R(c, 2, 15, 56, 3, '#8b5e34');
    robot(c, 'ai', 22, 0, baby);
    E(c, 30, 15, 13, 4.5, '#f6f1e6'); Ln(c, 21, 14, 27, 16, '#d8d0bf'); Ln(c, 31, 13, 38, 15, '#d8d0bf');
    for (const sx of [4, 8, 11, 45, 49, 53]) { P(c, sx, 14, '#e3bd5a'); P(c, sx + 1, 13, '#e3bd5a'); }
  });
}
const STAR = ["....y....", "....y....", "...yyy...", "yyyyyyyyy", ".yyyyyyy.", "..yyyyy..", "..yy.yy..", ".yy...yy.", ".y.....y."];
function stable() {
  return outlined(62, 44, c => {
    G(c, [[0, 18], [31, 0], [62, 18]], '#3a2414'); G(c, [[5, 17], [31, 3], [57, 17]], '#4a2e18');
    R(c, 6, 17, 50, 24, '#5b3a20'); for (const px of [6, 18, 42, 54]) R(c, px, 17, 2, 24, '#3a2414');
    R(c, 25, 24, 12, 17, '#ffcf6b'); R(c, 29, 31, 4, 10, '#c98a3a'); R(c, 2, 41, 58, 3, '#2a1c10');
  });
}

// ── 디자인 시트 ──
function designSheet() {
  const SW = 412, SH = 236, sh = document.createElement('canvas'); sh.width = SW; sh.height = SH; const c = sh.getContext('2d');
  c.fillStyle = '#16182a'; c.fillRect(0, 0, SW, SH);
  const labels = [], put = (cv, x, y, text) => { c.drawImage(cv, x, y); labels.push([x + cv.width / 2, y + cv.height + 2, text]); };
  put(mary({}), 4, 4, '엄마 (기도)'); put(mary({mouth: true, nod: true}), 54, 4, '엄마 (노래)'); put(mary({turned: true}), 104, 4, '엄마 (카메라 봄)');
  put(man({...JOSEPH}), 154, 4, '아빠'); put(man({...JOSEPH, mouth: true, nod: true}), 200, 4, '아빠 (노래)');
  put(man({...SHEPA}), 246, 4, '목자 1'); put(man({...SHEPB, mouth: true}), 286, 4, '목자 2');
  put(lamb(), 104, 76, '어린 양');
  const bstates = [[{}, '멀뚱'], [{eyes: 'blink'}, '깜빡'], [{eyes: 'lookL'}, '왼쪽 봄'], [{eyes: 'lookR'}, '오른쪽 봄']];
  bstates.forEach(([o, t], i) => put(manger(o), 4 + i * 64, 110, '아기 삐빅 · ' + t));
  const st = document.createElement('canvas'); st.width = 9; st.height = 9; S(st.getContext('2d'), STAR, {y: '#ffd166'}, 0, 0); put(st, 300, 116, '별');
  put(stable(), 332, 128, '바깥 마구간');
  const angels = [['prop', {eyes: 'U'}, true, '위잉'], ['prop', {eyes: 'U', mouth: true}, false, '위잉 노래'], ['tv', {eyes: 'U'}, true, '치직'],
                  ['tv', {eyes: 'U', mouth: true}, false, '치직 노래'], ['can', {eyes: 'U'}, true, '딸깍'], ['can', {eyes: 'U', mouth: true}, false, '딸깍 노래'],
                  ['ai', {eyes: 'wink', mouth: true}, true, '삐빅 윙크']];
  angels.forEach(([k, o, up, t], i) => put(angelCanvas(k, o, up), 4 + i * 38, 178, t));
  // 딸깍 놀람: 목젖 두 장 (3배 확대해서)
  for (const u of [0, 1]) { const a = angelCanvas('can', {eyes: 'wide', mouth: 'yell', uvula: u, arms: 'up'}, u === 0);
    const big = document.createElement('canvas'); big.width = a.width * 2; big.height = a.height * 2; const bc = big.getContext('2d'); bc.imageSmoothingEnabled = false; bc.drawImage(a, 0, 0, big.width, big.height);
    put(big, 334, 4 + u * 60, u ? '' : ''); }
  labels.push([370, 122, '딸깍 놀람 · 목젖 떨림 (2장)']);
  // 출력: 4배 최근접 확대 + 한글 라벨
  const Z = 4, out = document.getElementById('c'); out.width = SW * Z; out.height = SH * Z + 40; const o = out.getContext('2d');
  o.fillStyle = '#16182a'; o.fillRect(0, 0, out.width, out.height); o.imageSmoothingEnabled = false; o.drawImage(sh, 0, 0, SW * Z, SH * Z);
  o.font = '600 22px "Apple SD Gothic Neo", sans-serif'; o.textAlign = 'center'; o.fillStyle = '#e8eaf2';
  for (const [x, y, t] of labels) if (t) o.fillText(t, x * Z, y * Z + 20);
  return [out.width, out.height];
}
"""


def _sheet_page() -> str:
    js = PIXEL_JS.replace("%CHARS%", json.dumps(CHARS))
    return ("<html><head><meta charset='utf-8'><style>*{margin:0}body{background:#16182a}canvas{display:block}</style></head>"
            f"<body><canvas id='c'></canvas><script>{js}</script></body></html>")


def design_sheet() -> Path:
    from playwright.sync_api import sync_playwright
    out = OUT / "story_design_sheet.png"
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: print("pageerror:", e))
        pg.set_content(_sheet_page())
        w, h = pg.evaluate("designSheet()")
        pg.set_viewport_size({"width": int(w), "height": int(h)})
        pg.locator("#c").screenshot(path=str(out))
        b.close()
    return out
