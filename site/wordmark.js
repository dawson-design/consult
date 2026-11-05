/* wordmark.js: the home page hero (index.html). Draws "consult" in its real letterforms, first as
   a pencil sketch (ruled guide lines, then the glyph outlines traced from the font, stroke by
   stroke, with overshoots, wobble, and paper grain), then builds it once, left to right, from
   hexagons clipped to the glyphs: each hexagon pops in a gas-flame colour and cools to white, and
   the word settles into solid white as the pencil fades. The build lasts about 9 s; the canvas
   sits inside a <button>, so the wordmark pauses and resumes it (WCAG 2.2.2) until it finishes,
   then stops being a button. Reduced motion shows the finished word. It also sizes the lockup so
   the quote mark plus the word span the content width. site.js handles tabs and copy buttons.
   frameAt() is a pure function of elapsed time; the sketch plan is computed once from the font
   raster; draw(), drawSketch(), and drawHex() are the only canvas code. */
(function () {
  'use strict';
  var canvas = document.querySelector('canvas[data-wordmark]');
  if (!canvas) return;
  var lockup = canvas.closest('.wm');
  var wrap = canvas.parentNode.tagName === 'BUTTON' ? canvas.parentNode : null;
  var mark = lockup.querySelector('.logo');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  var WORD = 'consult';
  var ROWS = parseInt(canvas.getAttribute('data-rows'), 10) || 16;  /* ascender height, in cells */
  /* Rows below the baseline, so round letters that dip under it (c, o, s, u) are not cut off. */
  var PAD = Math.max(1, Math.ceil(ROWS * 0.06)), TOT = ROWS + PAD;
  var SAMPLE = 12;        /* raster pixels per cell when sampling the font */
  var TRACK = -0.045;     /* letter spacing, in em (close to the logotype's -0.06em) */
  var GAPC = 3;           /* cells between the mark and the word */
  var FONT = '"Archivo", "Arial Black", "Helvetica Neue", Arial, sans-serif';
  /* Timings in ms. lead: pencil time before the first hexagon, so the fill trails the sketch;
     sweep: the front crosses the word; spread: how ragged the front is; lag..lag+lagSpread: delay
     before a hexagon starts to cool; cool: flame colour to white; pop: dot to full cell; settle:
     squares to solid white type. */
  var T = { lead: 1400, sweep: 3600, spread: 1300, lag: 800, lagSpread: 600, cool: 750, pop: 260, settle: 450 };
  /* The pencil sketch, in ms and cells. Three guide lines (ascender, x-height, baseline) are ruled
     first, guideGap apart, each taking `guide`. Then two passes trace the outlines letter by
     letter at an even speed: a faint construction pass with long overshoots and more wobble, then
     a firmer pass closer to the true outline. over: overshoot range past a corner; amp: drift off
     the outline; width: line weight; color: its CSS token. */
  var SK = {
    guide: 420, guideGap: 150,
    passes: [
      { start: 250, dur: 2300, width: 0.06, over: [0.35, 0.9], amp: 0.07, color: '--wm-guide' },
      { start: 950, dur: 2300, width: 0.1, over: [0.1, 0.35], amp: 0.035, color: '--wm-sketch' }
    ]
  };
  var CORNER = 0.6;    /* turn, in radians, that ends one pencil stroke and starts the next */
  var MAXLEN = 9;      /* longest single stroke, in cells; a longer curve takes several */
  var STEP = 0.25;     /* spacing of stroke points, in cells */

  function hash(x, y) { var h = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return h - Math.floor(h); }
  /* Smooth value noise in [0, 1]: neighbouring cells get similar values, so hexagons arrive in clusters. */
  function noise(x, y) {
    var x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
    var sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
    var a = hash(x0, y0), b = hash(x0 + 1, y0), c = hash(x0, y0 + 1), d = hash(x0 + 1, y0 + 1);
    var top = a + (b - a) * sx, bottom = c + (d - c) * sx;
    return top + (bottom - top) * sy;
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  /* Rasterize the word once and lay a honeycomb over it. Returns the hexagons that touch a glyph,
     each with an arrival time (d) and a cooling time (w): horizontal position, plus clustered
     noise, plus a little per-cell jitter. */
  function rasterize() {
    var S = SAMPLE, off = document.createElement('canvas'), o = off.getContext('2d');
    var px = 100;
    o.font = '900 ' + px + 'px ' + FONT;
    var asc = o.measureText('l').actualBoundingBoxAscent || px * 0.72;
    px = px * (ROWS * S) / asc;
    var font = '900 ' + px + 'px ' + FONT;
    o.font = font;
    var spans = [], x = 0;
    for (var i = 0; i < WORD.length; i++) {
      var w = o.measureText(WORD[i]).width;
      spans.push([x, x + w]);
      x += w + TRACK * px;
    }
    var cols = Math.ceil((x - TRACK * px) / S);
    var W = cols * S, H = TOT * S;
    off.width = W; off.height = H;
    o.font = font; o.fillStyle = '#000'; o.textBaseline = 'alphabetic';
    spans.forEach(function (sp, k) { o.fillText(WORD[k], sp[0], ROWS * S); });
    var data = o.getImageData(0, 0, W, H).data;
    function covered(px2, py2) {
      var ix = Math.floor(px2 * S), iy = Math.floor(py2 * S);
      return ix >= 0 && iy >= 0 && ix < W && iy < H && data[(iy * W + ix) * 4 + 3] > 8;
    }
    /* Pointy-top hexagons one cell wide, rows 0.866 apart, odd rows offset half a cell; from row
       -1 and column -1 so the edges of the word have no gaps. */
    var R = 1 / Math.sqrt(3), dy = 1.5 * R, cells = [];
    for (var r = -1; r * dy < TOT; r++) {
      for (var c = -1; c <= cols; c++) {
        var hx = c + 0.5 + (Math.abs(r) % 2 ? 0.5 : 0), hy = R + r * dy;
        var hit = covered(hx, hy);
        for (var k = 0; k < 6 && !hit; k++) {
          var ang = Math.PI / 180 * (60 * k - 30);
          hit = covered(hx + Math.cos(ang) * R * 0.9, hy + Math.sin(ang) * R * 0.9) ||
                covered(hx + Math.cos(ang) * R * 0.5, hy + Math.sin(ang) * R * 0.5);
        }
        if (!hit) continue;
        var d = (hx / cols) * T.sweep + (noise(hx / 5, hy / 5) * 0.75 + hash(hx, hy) * 0.25) * T.spread;
        cells.push({ x: hx, y: hy, d: d, w: d + T.lag + (noise(hx / 4 + 80, hy / 4) * 0.7 + hash(hx + 7, hy) * 0.3) * T.lagSpread });
      }
    }
    var xh = o.measureText('x').actualBoundingBoxAscent / S || ROWS * 0.7;
    var loops = contours(data, W, H).map(function (l) { return outline(l, S); }).filter(function (l) { return l.length > 2; });
    return { cols: cols, cells: cells, font: font, spans: spans, S: S, xh: xh, loops: loops };
  }

  /* Marching squares at the 50% alpha level: the glyphs' closed outlines, in raster pixels. Each
     crossing point is keyed by the pixel-grid edge it lies on, so neighbouring squares share it. */
  function contours(data, W, H) {
    function a(x, y) { return x < 0 || y < 0 || x >= W || y >= H ? 0 : data[(y * W + x) * 4 + 3] / 255; }
    var pts = {}, links = {};
    function at(key, x0, y0, x1, y1) {
      if (!pts[key]) {
        var v0 = a(x0, y0), t = (0.5 - v0) / (a(x1, y1) - v0);
        pts[key] = [x0 + (x1 - x0) * t + 0.5, y0 + (y1 - y0) * t + 0.5];
      }
      return key;
    }
    function link(p, q) { (links[p] = links[p] || []).push(q); (links[q] = links[q] || []).push(p); }
    function square(x, y) {
      var tl = a(x, y) >= 0.5, tr = a(x + 1, y) >= 0.5, br = a(x + 1, y + 1) >= 0.5, bl = a(x, y + 1) >= 0.5, e = [];
      if (tl !== tr) e.push(at('h' + x + ',' + y, x, y, x + 1, y));
      if (tr !== br) e.push(at('v' + (x + 1) + ',' + y, x + 1, y, x + 1, y + 1));
      if (bl !== br) e.push(at('h' + x + ',' + (y + 1), x, y + 1, x + 1, y + 1));
      if (tl !== bl) e.push(at('v' + x + ',' + y, x, y, x, y + 1));
      if (e.length === 2) { link(e[0], e[1]); return; }
      if (e.length !== 4) return;
      /* Saddle: the centre's value says which diagonal pair of corners is joined. */
      var centre = (a(x, y) + a(x + 1, y) + a(x + 1, y + 1) + a(x, y + 1)) / 4 >= 0.5;
      if (centre === tl) { link(e[0], e[1]); link(e[2], e[3]); } else { link(e[0], e[3]); link(e[1], e[2]); }
    }
    for (var y = -1; y < H; y++) for (var x = -1; x < W; x++) square(x, y);
    return walk(pts, links);
  }
  /* Follows the links into closed loops, in the order the scan first met them (top to bottom). */
  function walk(pts, links) {
    var seen = {}, loops = [];
    Object.keys(links).forEach(function (start) {
      var loop = [], k = start, prev = null;
      while (k !== undefined && !seen[k]) {
        seen[k] = true; loop.push(pts[k]);
        var next = links[k][0] !== prev ? links[k][0] : links[k][1];
        prev = k; k = next;
      }
      if (loop.length > 6) loops.push(loop);
    });
    return loops;
  }
  /* A traced loop, simplified to within 0.4 raster pixels and converted to cells. */
  function outline(loop, S) {
    var p = simplify(loop.concat([loop[0]]), 0.4);
    p.pop();
    return p.map(function (q) { return [q[0] / S, q[1] / S]; });
  }
  /* Ramer-Douglas-Peucker: keeps the points that sit more than `tol` off the line between kept points. */
  function simplify(pts, tol) {
    var keep = new Uint8Array(pts.length), stack = [[0, pts.length - 1]];
    keep[0] = keep[pts.length - 1] = 1;
    while (stack.length) {
      var s = stack.pop(), far = 0, at = -1;
      for (var i = s[0] + 1; i < s[1]; i++) {
        var d = offLine(pts[i], pts[s[0]], pts[s[1]]);
        if (d > far) { far = d; at = i; }
      }
      if (far > tol) { keep[at] = 1; stack.push([s[0], at], [at, s[1]]); }
    }
    return pts.filter(function (p, i) { return keep[i]; });
  }
  function offLine(p, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
    if (!len) return Math.hypot(p[0] - a[0], p[1] - a[1]);
    return Math.abs(dx * (a[1] - p[1]) - dy * (a[0] - p[0])) / len;
  }
  /* The angle, in radians, the path turns through at b. */
  function turn(a, b, c) {
    var d = Math.abs(Math.atan2(c[1] - b[1], c[0] - b[0]) - Math.atan2(b[1] - a[1], b[0] - a[0]));
    return d > Math.PI ? 2 * Math.PI - d : d;
  }
  /* Points every `step` along a polyline, keeping both ends. */
  function resample(pts, step) {
    var out = [pts[0]], carry = 0;
    for (var i = 1; i < pts.length; i++) {
      var a = pts[i - 1], b = pts[i], d = Math.hypot(b[0] - a[0], b[1] - a[1]), s = step - carry;
      for (; s < d; s += step) out.push([a[0] + (b[0] - a[0]) * s / d, a[1] + (b[1] - a[1]) * s / d]);
      carry = d - (s - step);
    }
    out.push(pts[pts.length - 1]);
    return out;
  }

  /* Cuts a closed outline into pencil strokes: at each corner, then again so no stroke is longer
     than MAXLEN. A stroke records whether each end is a corner, which gets a long overshoot. */
  function cut(loop) {
    var n = loop.length, corners = [], pieces = [];
    for (var i = 0; i < n; i++) if (turn(loop[(i + n - 1) % n], loop[i], loop[(i + 1) % n]) > CORNER) corners.push(i);
    var sharp = corners.length > 0;
    if (!sharp) corners = [0];
    corners.forEach(function (c, j) {
      var end = j + 1 < corners.length ? corners[j + 1] : corners[0] + n, pts = [];
      for (var i = c; i <= end; i++) pts.push(loop[i % n]);
      pieces.push.apply(pieces, split(resample(pts, STEP), sharp));
    });
    return pieces;
  }
  function split(pts, sharp) {
    var m = pts.length, parts = Math.max(1, Math.round((m - 1) * STEP / MAXLEN)), out = [];
    for (var k = 0; k < parts; k++) {
      var a = Math.round(k * (m - 1) / parts), b = Math.round((k + 1) * (m - 1) / parts);
      out.push({ pts: pts.slice(a, b + 1), start: sharp && k === 0, end: sharp && k === parts - 1 });
    }
    return out;
  }
  /* The point `by` cells past `to`, continuing the line from `from`. */
  function extend(from, to, by) {
    var dx = to[0] - from[0], dy = to[1] - from[1], l = Math.hypot(dx, dy) || 1;
    return [to[0] + dx / l * by, to[1] + dy / l * by];
  }
  /* One pass of a stroke as a hand draws it: it runs past each corner end by a random overshoot,
     drifts off the outline with smooth noise, and sits slightly off the other pass. */
  function pencil(piece, pass, seed) {
    var p = piece.pts, m = p.length, o = pass.over;
    var head = extend(p[Math.min(2, m - 1)], p[0], piece.start ? o[0] + (o[1] - o[0]) * hash(seed, 1) : 0.05);
    var tail = extend(p[Math.max(m - 3, 0)], p[m - 1], piece.end ? o[0] + (o[1] - o[0]) * hash(seed, 2) : 0.05);
    var pts = resample([head].concat(p, [tail]), STEP), last = pts.length - 1;
    var sx = (hash(seed, 3) - 0.5) * pass.amp, sy = (hash(seed, 4) - 0.5) * pass.amp;
    return pts.map(function (q, i) {
      var a = pts[Math.max(0, i - 1)], b = pts[Math.min(last, i + 1)];
      var dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
      var off = (noise(i * STEP * 0.5 + seed * 13.1, seed) - 0.5) * 2 * pass.amp;
      return [q[0] - dy / l * off + sx, q[1] + dx / l * off + sy];
    });
  }
  /* The letter whose advance holds the loop's centre. */
  function letterOf(g, loop) {
    var cx = loop.reduce(function (s, p) { return s + p[0]; }, 0) / loop.length * g.S;
    for (var i = g.spans.length - 1; i > 0; i--) if (cx >= g.spans[i][0]) return i;
    return 0;
  }
  /* The sketch as data: every stroke of both passes with its points and its start and end times,
     ordered letter by letter so the pencil moves at an even speed; the guide heights; and when
     the last line is finished. */
  function plan(g) {
    var pieces = [], lines = [], end = SK.guideGap * 2 + SK.guide;
    g.loops.forEach(function (loop) {
      var letter = letterOf(g, loop);
      cut(loop).forEach(function (pc) { pc.letter = letter; pieces.push(pc); });
    });
    pieces.sort(function (a, b) { return a.letter - b.letter; });
    SK.passes.forEach(function (pass, pi) {
      var drawn = pieces.map(function (pc, i) { return pencil(pc, pass, i * 7.3 + pi * 101.7); });
      var total = drawn.reduce(function (s, d) { return s + d.length; }, 0), at = pass.start;
      drawn.forEach(function (pts, i) {
        var dur = pts.length / total * pass.dur;
        lines.push({ pts: pts, t0: at, t1: at + dur, pass: pass, seed: i * 3.7 + pi * 50 });
        at += dur;
      });
      end = Math.max(end, at);
    });
    return { lines: lines, guides: [0, ROWS - g.xh, ROWS], end: end };
  }

  var BUILT = T.lead + T.sweep + T.spread + T.lag + T.lagSpread + T.cool;  /* last hexagon is white */
  var DONE = BUILT + T.settle;                                            /* nothing changes after this */

  /* Frame at elapsed time `now` (ms since the build began). */
  function frameAt(now) {
    var t = Math.min(now, DONE);
    return { t: t, since: t - T.lead, solid: clamp((t - BUILT) / T.settle, 0, 1) };
  }
  function finished() { return { t: 0, since: Infinity, solid: 1 }; }

  var grid = null, ctx = canvas.getContext('2d');
  var buf = document.createElement('canvas'), b = buf.getContext('2d'), mask = document.createElement('canvas');

  /* Size the lockup: the mark is x-height tall, sits on the baseline, and keeps its viewBox
     shape; then a gap; then the word, together spanning the content width. */
  function layout() {
    var vb = mark && mark.viewBox && mark.viewBox.baseVal, aspect = vb && vb.height ? vb.width / vb.height : 1;
    var m = Math.round(grid.xh), cell = lockup.clientWidth / (grid.cols + m * aspect + GAPC);
    lockup.style.setProperty('--mark', (m * cell) + 'px');
    lockup.style.setProperty('--mark-w', (m * aspect * cell) + 'px');
    lockup.style.setProperty('--gap', (GAPC * cell) + 'px');
    lockup.style.setProperty('--wm-h', (TOT * cell) + 'px');
    lockup.style.setProperty('--wm-pad', (PAD * cell) + 'px');
    return cell;
  }
  function token(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function fillWord(context, color, alpha) {
    context.globalAlpha = alpha;
    context.font = grid.font; context.textBaseline = 'alphabetic'; context.fillStyle = color;
    grid.spans.forEach(function (sp, i) { context.fillText(WORD[i], sp[0], ROWS * grid.S); });
    context.globalAlpha = 1;
  }

  function draw(f) {
    var cell = layout(), w = grid.cols * cell, h = TOT * cell, dpr = window.devicePixelRatio || 1;
    var k = cell / grid.S;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    }
    if (buf.width !== canvas.width || buf.height !== canvas.height) {
      buf.width = mask.width = canvas.width; buf.height = mask.height = canvas.height;
      /* The whole word as one clipping mask, redrawn only when the size changes. */
      var mk = mask.getContext('2d');
      mk.setTransform(dpr * k, 0, 0, dpr * k, 0, 0);
      fillWord(mk, '#000', 1);
    }
    /* The pencil sketch, fading out as the built word settles. */
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (f.solid < 1) drawSketch(f, cell, dpr);
    /* Hexagons go on a buffer, which is clipped to the glyphs and laid over the dim word. */
    b.setTransform(dpr, 0, 0, dpr, 0, 0);
    b.globalCompositeOperation = 'source-over';
    b.clearRect(0, 0, w, h);
    for (var i = 0; i < grid.cells.length; i++) {
      var q = grid.cells[i];
      if (f.since < q.d) continue;
      var cool = clamp((f.since - q.w) / T.cool, 0, 1);
      b.fillStyle = flame(q, f.t, cool);
      drawHex(q, clamp((f.since - q.d) / T.pop, 0, 1), cell, dpr);
    }
    b.globalCompositeOperation = 'destination-in';
    b.setTransform(1, 0, 0, 1, 0, 0);
    b.drawImage(mask, 0, 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(buf, 0, 0);
    /* Settled: solid type over the hexagons, so the held word is the plain logotype. */
    if (f.solid > 0) {
      ctx.setTransform(dpr * k, 0, 0, dpr * k, 0, 0);
      fillWord(ctx, token('--wm-ink1'), f.solid);
    }
  }

  var sk = document.createElement('canvas'), s = sk.getContext('2d'), grain = null, skKey = '';

  /* The pencil layer: the guides and strokes drawn by f.t, roughened by the paper grain and laid
     on the canvas. Once the sketch is complete the layer is kept, and redrawn only on resize. */
  function drawSketch(f, cell, dpr) {
    var key = canvas.width + 'x' + canvas.height;
    if (skKey !== key || f.t < grid.sketch.end) {
      if (sk.width !== canvas.width || sk.height !== canvas.height) { sk.width = canvas.width; sk.height = canvas.height; }
      s.setTransform(1, 0, 0, 1, 0, 0);
      s.clearRect(0, 0, sk.width, sk.height);
      s.setTransform(dpr, 0, 0, dpr, 0, 0);
      s.lineCap = 'round';
      var colors = { '--wm-guide': token('--wm-guide'), '--wm-sketch': token('--wm-sketch') };
      grid.sketch.guides.forEach(function (y, i) { guide(y, i, f.t, cell, colors['--wm-guide']); });
      grid.sketch.lines.forEach(function (ln) { stroke(ln, f.t, cell, colors[ln.pass.color]); });
      roughen();
      skKey = f.t >= grid.sketch.end ? key : '';
    }
    ctx.globalAlpha = 1 - f.solid;
    ctx.drawImage(sk, 0, 0);
    ctx.globalAlpha = 1;
  }
  /* A ruled guide line across the word, drawn left to right: faint, thin, and straight. */
  function guide(y, i, t, cell, color) {
    var u = clamp((t - i * SK.guideGap) / SK.guide, 0, 1), py = Math.max(y * cell, 0.5);
    if (!u) return;
    s.globalAlpha = 0.7; s.strokeStyle = color; s.lineWidth = 0.7;
    s.beginPath(); s.moveTo(0, py); s.lineTo(u * grid.cols * cell, py + u * 0.4); s.stroke();
    s.globalAlpha = 1;
  }
  /* The part of one pencil stroke drawn by `t`, segment by segment, so the line thins towards
     each end where the pencil lands and lifts, and its weight wavers with the hand's pressure. */
  function stroke(ln, t, cell, color) {
    if (t <= ln.t0) return;
    var pts = ln.pts, m = pts.length, shown = Math.min(m, Math.ceil(m * (t - ln.t0) / (ln.t1 - ln.t0)));
    var base = Math.max(0.7, ln.pass.width * cell);
    s.strokeStyle = color;
    for (var i = 1; i < shown; i++) {
      var press = (0.45 + 0.55 * Math.sin(Math.PI * i / (m - 1))) * (0.8 + 0.4 * noise(i * 0.3, ln.seed));
      s.lineWidth = base * press;
      s.beginPath(); s.moveTo(pts[i - 1][0] * cell, pts[i - 1][1] * cell); s.lineTo(pts[i][0] * cell, pts[i][1] * cell); s.stroke();
    }
  }
  /* Keeps the pencil only where the paper's tooth would catch graphite. */
  function roughen() {
    if (!grain) grain = s.createPattern(grainTile(), 'repeat');
    s.setTransform(1, 0, 0, 1, 0, 0);
    s.globalCompositeOperation = 'destination-in';
    s.fillStyle = grain; s.fillRect(0, 0, sk.width, sk.height);
    s.globalCompositeOperation = 'source-over';
  }
  /* Paper tooth: speckled alpha, slightly streaky along x, in device pixels. */
  function grainTile() {
    var N = 128, g = document.createElement('canvas'); g.width = g.height = N;
    var gx = g.getContext('2d'), img = gx.createImageData(N, N);
    for (var i = 0; i < N * N; i++) {
      var x = i % N, y = (i / N) | 0, v = 0.55 * hash(x + 0.5, y + 0.25) + 0.45 * noise(x / 2.2, y / 0.9);
      img.data[i * 4 + 3] = Math.round(255 * (0.2 + 0.8 * clamp((v - 0.25) / 0.5, 0, 1)));
    }
    gx.putImageData(img, 0, 0);
    return g;
  }

  /* One hexagon in the buffer (CSS px under a dpr transform). `pop` grows it from 30% to full
     size; at full size neighbours meet edge to edge, and a hairline stroke in its own colour
     closes anti-aliased seams. */
  function drawHex(q, pop, cell, dpr) {
    var e = 1 - (1 - pop) * (1 - pop), rad = cell / Math.sqrt(3) * (0.3 + 0.7 * e);
    var cx = q.x * cell, cy = q.y * cell;
    b.beginPath();
    for (var i = 0; i < 6; i++) {
      var ang = Math.PI / 180 * (60 * i - 30), px = cx + Math.cos(ang) * rad, py = cy + Math.sin(ang) * rad;
      if (i) b.lineTo(px, py); else b.moveTo(px, py);
    }
    b.closePath();
    b.fill();
    if (pop === 1) { b.strokeStyle = b.fillStyle; b.lineWidth = 1.2 / dpr; b.lineJoin = 'round'; b.stroke(); }
  }

  /* Gas flame: hue drifts between cyan, blue, and violet in slowly sliding bands, with lightness
     varying like a flame's inner and outer cones; `cool` (0..1) takes it to white. */
  function flame(q, t, cool) {
    var drift = t * 0.00035;
    var n = noise(q.x / 9 + drift, q.y / 7 - drift * 0.6);
    var m = noise(q.x / 4 - drift * 1.7, q.y / 4 + 30);
    var hue = 192 + n * 78;                  /* 192 cyan .. 270 violet */
    var light = 50 + m * 38;                 /* blue through pale inner-cone tints */
    light += (100 - light) * cool;
    var sat = (95 - m * 25) * (1 - cool);    /* the lightest tints are also the softest */
    return 'hsl(' + hue.toFixed(1) + ' ' + sat.toFixed(1) + '% ' + light.toFixed(1) + '%)';
  }

  var start = null, elapsed = 0, running = false, raf = 0, retired = false;
  function isBuilt() { return elapsed >= DONE; }
  function tick(now) {
    if (start === null) start = now - elapsed;
    elapsed = now - start;
    draw(frameAt(elapsed));
    if (isBuilt()) { running = false; retire(); return; }
    raf = window.requestAnimationFrame(tick);
  }
  function setLabel(playing) { if (wrap) wrap.setAttribute('aria-label', playing ? 'Pause animation' : 'Play animation'); }
  /* Once the build is over (or motion is reduced) there is nothing to pause, so the wordmark
     stops being a button and never restarts. If it has keyboard focus, it says so and waits for
     focus to move on, rather than leaving focus on a hidden element. */
  function retire() {
    retired = true;
    if (!wrap || wrap.classList.contains('is-done')) return;
    if (document.activeElement === wrap) {
      wrap.setAttribute('aria-label', 'Animation finished');
      wrap.addEventListener('blur', hideButton, { once: true });
      return;
    }
    hideButton();
  }
  function hideButton() {
    wrap.tabIndex = -1;
    wrap.removeAttribute('aria-label');
    wrap.setAttribute('aria-hidden', 'true');
    wrap.classList.add('is-done');
  }
  function play() { if (running) return; running = true; start = null; raf = window.requestAnimationFrame(tick); setLabel(true); }
  function pause() { running = false; window.cancelAnimationFrame(raf); setLabel(false); }
  function still() { if (grid) draw(reduce.matches ? finished() : frameAt(elapsed)); }
  function applyMotion() {
    if (reduce.matches) { pause(); retire(); draw(finished()); return; }
    if (retired) { draw(finished()); return; }   /* never restart without a pause control */
    play();
  }

  function init() {
    grid = rasterize();
    grid.sketch = plan(grid);
    lockup.classList.add('is-drawn');
    /* Review hook: ?t=<ms> freezes the build at that moment (used for screenshots). */
    var frozen = /[?&]t=(\d+)/.exec(window.location.search);
    if (frozen) { retire(); draw(frameAt(parseInt(frozen[1], 10))); return; }
    if (wrap) wrap.addEventListener('click', function () { if (isBuilt()) return; if (running) pause(); else play(); });
    reduce.addEventListener('change', applyMotion);
    if ('ResizeObserver' in window) new ResizeObserver(still).observe(lockup);
    applyMotion();
  }
  /* Wait for Archivo so the raster matches the real logotype; fall back after 2.5 s. */
  var started = false;
  function startOnce() { if (!started) { started = true; init(); } }
  if (document.fonts && document.fonts.load) {
    document.fonts.load('900 100px "Archivo"').then(startOnce, startOnce);
    window.setTimeout(startOnce, 2500);
  } else {
    startOnce();
  }
})();
