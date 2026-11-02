/* wordmark.js: the home page hero (index.html). Draws "consult" in its real letterforms, first as
   a dim word, then builds it once, left to right, from hexagons clipped to the glyphs: each
   hexagon pops in a gas-flame colour and cools to white, and the word settles into solid white.
   The build lasts about 7.5 s; the canvas sits inside a <button>, so the wordmark pauses and
   resumes it (WCAG 2.2.2) until it finishes, then stops being a button. Reduced motion shows the
   finished word. It also sizes the lockup so the quote mark plus the word span the content width.
   site.js handles tabs and copy buttons. frameAt() is a pure function of elapsed time; draw() and
   drawHex() are the only canvas code. */
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
  /* Timings in ms. lead: pause before the first hexagon; sweep: the front crosses the word;
     spread: how ragged the front is; lag..lag+lagSpread: delay before a hexagon starts to cool;
     cool: flame colour to white; pop: dot to full cell; settle: squares to solid white type. */
  var T = { lead: 200, sweep: 3600, spread: 1300, lag: 800, lagSpread: 600, cool: 750, pop: 260, settle: 450 };

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
    return { cols: cols, cells: cells, font: font, spans: spans, S: S, xh: xh };
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
    /* The dim word, fading out as the built word settles. */
    ctx.setTransform(dpr * k, 0, 0, dpr * k, 0, 0);
    ctx.clearRect(0, 0, w / k, h / k);
    if (f.solid < 1) fillWord(ctx, token('--wm-plan'), 1 - f.solid);
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
