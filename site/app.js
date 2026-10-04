/* Bloodborne PS5 mods - project site script. Vanilla JS, no dependencies, no network calls
   other than loading the comparison images from assets/cmp/ when a scene is opened.
   - Feature filter chips on the main page (progressive enhancement).
   - Comparison tool (slider, blink, difference, strips) on compare.html, canvas based. */
(function () {
  'use strict';

  /* ------------------------------------------------------------------ feature filter */
  function initFilter() {
    var chips = document.querySelectorAll('.chip[data-filter]');
    var cards = document.querySelectorAll('.card[data-group]');
    var status = document.getElementById('filter-status');
    if (!chips.length || !cards.length) { return; }
    function apply(filter) {
      var shown = 0;
      Array.prototype.forEach.call(cards, function (card) {
        var groups = (card.getAttribute('data-group') || '').split(' ');
        var ok = filter === 'all' || groups.indexOf(filter) !== -1;
        card.hidden = !ok;
        if (ok) { shown++; }
      });
      Array.prototype.forEach.call(chips, function (chip) {
        chip.setAttribute('aria-pressed', chip.getAttribute('data-filter') === filter ? 'true' : 'false');
      });
      if (status) { status.textContent = 'Showing ' + shown + ' of ' + cards.length + ' mods.'; }
    }
    Array.prototype.forEach.call(chips, function (chip) {
      chip.addEventListener('click', function () { apply(chip.getAttribute('data-filter')); });
    });
    apply('all');
  }

  /* ------------------------------------------------------------------ comparison tool */
  var BASE = 'assets/cmp/';
  var MODES = [
    { id: 'slider', label: 'Slider (A | B)' },
    { id: 'blink', label: 'Blink (A / B)' },
    { id: 'diff', label: 'Difference |A - B|' },
    { id: 'vstrips', label: 'Vertical strips (A to D)' },
    { id: 'hstrips', label: 'Horizontal strips (A to D)' }
  ];
  var SLOTS = ['a', 'b', 'c', 'd'];

  function initCompare(root, DATA) {
    var $ = function (id) { return document.getElementById(id); };
    var el = {
      set: $('cmp-set'), scene: $('cmp-scene'), mode: $('cmp-mode'),
      a: $('cmp-a'), b: $('cmp-b'), c: $('cmp-c'), d: $('cmp-d'),
      fC: $('f-c'), fD: $('f-d'), fRate: $('f-rate'), fGain: $('f-gain'), fFloor: $('f-floor'),
      fSplit: $('f-split'), fBlink: $('f-blink'),
      rate: $('cmp-rate'), gain: $('cmp-gain'), gainVal: $('cmp-gain-val'),
      floor: $('cmp-floor'), floorVal: $('cmp-floor-val'), split: $('cmp-split'),
      viewer: $('cmp-viewer'), canvas: $('cmp-canvas'), status: $('cmp-status'), sr: $('cmp-sr'),
      title: $('cmp-title'), desc: $('cmp-desc'), hint: $('cmp-hint'), states: $('cmp-states'),
      verdict: $('cmp-verdict'), verdictTitle: $('cmp-verdict-title'), stats: $('cmp-stats'),
      loaded: $('cmp-loaded'), zoomLabel: $('cmp-zoom-label'),
      pause: $('cmp-pause'), flip: $('cmp-flip')
    };
    var ctx = el.canvas.getContext('2d', { alpha: false });
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var S = {
      set: 0, scene: 0, mode: 'slider', a: '', b: '', c: '', d: '',
      split: 0.5, scale: 1, tx: 0, ty: 0, fit: true,
      blinkOn: false, paused: reduceMotion, rate: 800, gain: 8, floor: 6,
      dpr: 1
    };
    var imgs = {};          /* url -> decoded Image */
    var inflight = {};      /* url -> Promise */
    var loadedBytes = {};   /* url -> bytes */
    var diffCache = { key: '', canvas: null, stats: null };
    var blinkTimer = null;
    var token = 0;
    var drag = null;

    var curSet = function () { return DATA.sets[S.set]; };
    var curScene = function () { return curSet().scenes[S.scene]; };
    var stateOf = function (id) {
      var st = curScene().states;
      for (var i = 0; i < st.length; i++) { if (st[i].id === id) { return st[i]; } }
      return null;
    };
    var urlOf = function (st) { return BASE + st.file; };
    var W = function () { return curScene().w; };
    var H = function () { return curScene().h; };

    /* ---------- loading (lazy: only the images that the current view needs) ---------- */
    function loadImage(st) {
      var url = urlOf(st);
      if (imgs[url]) { return Promise.resolve(imgs[url]); }
      if (inflight[url]) { return inflight[url]; }
      inflight[url] = new Promise(function (resolve, reject) {
        var im = new Image();
        im.decoding = 'async';
        im.onload = function () { imgs[url] = im; loadedBytes[url] = st.bytes; delete inflight[url]; resolve(im); };
        im.onerror = function () { delete inflight[url]; reject(new Error('Could not load ' + st.file)); };
        im.src = url;
      });
      return inflight[url];
    }

    function neededIds() {
      var ids = [];
      var slots = (S.mode === 'vstrips' || S.mode === 'hstrips') ? SLOTS : ['a', 'b'];
      slots.forEach(function (k) { if (S[k] && ids.indexOf(S[k]) === -1) { ids.push(S[k]); } });
      return ids;
    }

    function setStatus(msg) { el.status.textContent = msg || ''; }

    function refresh() {
      var my = ++token;
      var sts = neededIds().map(stateOf).filter(Boolean);
      var pending = sts.filter(function (st) { return !imgs[urlOf(st)]; });
      if (pending.length) {
        var kb = Math.round(pending.reduce(function (n, st) { return n + st.bytes; }, 0) / 1024);
        setStatus('Loading ' + pending.length + (pending.length === 1 ? ' image' : ' images') + ' (about ' + kb + ' KB)...');
        el.viewer.setAttribute('aria-busy', 'true');
      }
      Promise.all(sts.map(loadImage)).then(function () {
        if (my !== token) { return; }
        setStatus('');
        el.viewer.removeAttribute('aria-busy');
        updateLoaded();
        draw();
      }).catch(function (err) {
        if (my !== token) { return; }
        el.viewer.removeAttribute('aria-busy');
        setStatus(err.message + '. Check your connection and reload the page.');
      });
    }

    function updateLoaded() {
      var n = 0, bytes = 0, k;
      for (k in loadedBytes) { if (Object.prototype.hasOwnProperty.call(loadedBytes, k)) { n++; bytes += loadedBytes[k]; } }
      el.loaded.textContent = n + (n === 1 ? ' image' : ' images') + ' loaded so far, ' + Math.round(bytes / 1024) + ' KB in total.';
    }

    /* ---------- geometry ---------- */
    function vsize() { return { w: el.viewer.clientWidth, h: el.viewer.clientHeight }; }
    function fitScale() { var v = vsize(); return Math.min(v.w / W(), v.h / H()); }
    function applyFit() {
      var v = vsize(), s = fitScale();
      S.scale = s;
      S.tx = Math.round((v.w - W() * s) / 2);
      S.ty = Math.round((v.h - H() * s) / 2);
      S.fit = true;
      updateZoomUi();
    }
    function clampPan() {
      var v = vsize(), iw = W() * S.scale, ih = H() * S.scale;
      S.tx = iw <= v.w ? Math.round((v.w - iw) / 2) : Math.min(0, Math.max(v.w - iw, S.tx));
      S.ty = ih <= v.h ? Math.round((v.h - ih) / 2) : Math.min(0, Math.max(v.h - ih, S.ty));
    }
    function setZoom(z, cx, cy) {
      var v = vsize();
      cx = (cx == null) ? v.w / 2 : cx;
      cy = (cy == null) ? v.h / 2 : cy;
      z = Math.max(fitScale(), Math.min(16, z));
      var k = z / S.scale;
      S.tx = cx - (cx - S.tx) * k;
      S.ty = cy - (cy - S.ty) * k;
      S.scale = z;
      S.fit = Math.abs(z - fitScale()) < 1e-6;
      clampPan();
      updateZoomUi();
      draw();
    }
    function updateZoomUi() {
      el.zoomLabel.textContent = 'Zoom ' + Math.round(S.scale * 100) + ' percent' + (S.fit ? ' (fit)' : '');
      el.canvas.classList.toggle('pan', !S.fit);
      /* when not zoomed the page may still scroll vertically over the viewer on touch devices */
      el.canvas.style.touchAction = S.fit ? 'pan-y' : 'none';
    }
    function resize() {
      var v = vsize();
      S.dpr = Math.min(window.devicePixelRatio || 1, 2);
      el.canvas.width = Math.max(1, Math.round(v.w * S.dpr));
      el.canvas.height = Math.max(1, Math.round(v.h * S.dpr));
      if (S.fit) { applyFit(); } else { clampPan(); }
      draw();
    }

    /* ---------- difference image (computed client-side from the two decoded images) ---------- */
    var scratchA = document.createElement('canvas');
    var scratchB = document.createElement('canvas');
    function computeDiff(A, B, sa, sb) {
      var key = [urlOf(sa), urlOf(sb), S.gain, S.floor].join('|');
      if (diffCache.key === key) { return diffCache; }
      var w = A.naturalWidth, h = A.naturalHeight;
      scratchA.width = scratchB.width = w;
      scratchA.height = scratchB.height = h;
      var xa = scratchA.getContext('2d', { willReadFrequently: true });
      var xb = scratchB.getContext('2d', { willReadFrequently: true });
      xa.drawImage(A, 0, 0);
      xb.drawImage(B, 0, 0);
      var da = xa.getImageData(0, 0, w, h).data;   /* throws SecurityError on file:// */
      var db = xb.getImageData(0, 0, w, h).data;
      var oc = document.createElement('canvas');
      oc.width = w; oc.height = h;
      var ox = oc.getContext('2d');
      var o = ox.createImageData(w, h), od = o.data;
      var gain = S.gain, floor = S.floor, changed = 0, n = w * h, sum = 0, i, p;
      for (i = 0, p = 0; i < n; i++, p += 4) {
        var la = 0.2126 * da[p] + 0.7152 * da[p + 1] + 0.0722 * da[p + 2];
        var lb = 0.2126 * db[p] + 0.7152 * db[p + 1] + 0.0722 * db[p + 2];
        var d = Math.abs(la - lb) - floor;
        if (d > 0) { changed++; sum += d; }
        var v = d > 0 ? Math.min(255, d * gain) : 0;
        od[p] = od[p + 1] = od[p + 2] = v;
        od[p + 3] = 255;
      }
      ox.putImageData(o, 0, 0);
      diffCache = { key: key, canvas: oc, stats: { changed: changed / n, mean: sum / n } };
      return diffCache;
    }

    /* ---------- drawing ---------- */
    function img(id) { var st = stateOf(id); return st ? imgs[urlOf(st)] : null; }

    function tag(text, x, y, align, accent) {
      ctx.font = '600 14px system-ui, -apple-system, "Segoe UI", Arial, sans-serif';
      var v = vsize(), maxW = Math.max(60, v.w / 2 - 24), t = text;
      while (ctx.measureText(t).width > maxW && t.length > 4) { t = t.slice(0, -2); }
      if (t !== text) { t += '...'; }
      var w = ctx.measureText(t).width + 16, h = 24;
      var rx = align === 'right' ? x - w : x;
      ctx.fillStyle = 'rgba(0,0,0,0.78)';
      ctx.fillRect(rx, y, w, h);
      if (accent) { ctx.fillStyle = accent; ctx.fillRect(rx, y, 3, h); }
      ctx.fillStyle = '#fff';
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'left';
      ctx.fillText(t, rx + 8, y + h / 2 + 1);
    }

    function nameOf(id) { var st = stateOf(id); return st ? st.short : ''; }

    /* strips: slots A to D that have an image, without repeating the same image twice */
    function stripSlots() {
      var seen = [], out = [];
      SLOTS.forEach(function (k) {
        if (S[k] && seen.indexOf(S[k]) === -1) { seen.push(S[k]); out.push({ letter: k.toUpperCase(), id: S[k] }); }
      });
      return out;
    }

    function draw() {
      var v = vsize(), m = S.mode;
      ctx.setTransform(S.dpr, 0, 0, S.dpr, 0, 0);
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, v.w, v.h);
      var A = img(S.a), B = img(S.b);
      if (!A || !B) { return; }
      var w = W(), h = H();
      ctx.imageSmoothingEnabled = S.scale < 1;
      ctx.imageSmoothingQuality = 'high';
      ctx.save();
      ctx.translate(Math.round(S.tx), Math.round(S.ty));
      ctx.scale(S.scale, S.scale);
      var overlay = null;
      if (m === 'slider') {
        ctx.drawImage(A, 0, 0, w, h);
        ctx.save();
        ctx.beginPath(); ctx.rect(S.split * w, 0, w - S.split * w, h); ctx.clip();
        ctx.drawImage(B, 0, 0, w, h);
        ctx.restore();
        overlay = 'slider';
      } else if (m === 'blink') {
        ctx.drawImage(S.blinkOn ? B : A, 0, 0, w, h);
        overlay = 'blink';
      } else if (m === 'diff') {
        var sa = stateOf(S.a), sb = stateOf(S.b), res = null;
        try { res = computeDiff(A, B, sa, sb); setStatus(''); }
        catch (e) {
          setStatus('The difference view reads pixels, which browsers block for files opened from disk. Serve the folder over http (for example "python3 -m http.server" in the site folder) or use the hosted page.');
        }
        if (res) { ctx.drawImage(res.canvas, 0, 0, w, h); updateStats(res.stats); }
        else { ctx.drawImage(A, 0, 0, w, h); }
        overlay = 'diff';
      } else {
        var ids = stripSlots(), k;
        var n = ids.length;
        for (k = 0; k < n; k++) {
          var im = img(ids[k].id); if (!im) { continue; }
          ctx.save();
          ctx.beginPath();
          if (m === 'vstrips') { ctx.rect(k * w / n, 0, w / n, h); } else { ctx.rect(0, k * h / n, w, h / n); }
          ctx.clip();
          ctx.drawImage(im, 0, 0, w, h);
          ctx.restore();
        }
        overlay = { strips: ids };
      }
      ctx.restore();
      drawOverlay(overlay);
    }

    function drawOverlay(o) {
      var v = vsize(), s = S.scale, w = W(), h = H();
      var left = Math.max(8, S.tx + 8), top = Math.max(8, S.ty + 8);
      var right = Math.min(v.w - 8, S.tx + w * s - 8);
      if (o === 'slider') {
        var x = Math.round(S.tx + S.split * w * s);
        var y0 = Math.max(0, S.ty), y1 = Math.min(v.h, S.ty + h * s);
        ctx.fillStyle = 'rgba(0,0,0,0.6)'; ctx.fillRect(x - 2, y0, 4, y1 - y0);
        ctx.fillStyle = '#fff'; ctx.fillRect(x - 1, y0, 2, y1 - y0);
        var cy = (y0 + y1) / 2;
        ctx.beginPath(); ctx.arc(x, cy, 17, 0, Math.PI * 2);
        ctx.fillStyle = '#fff'; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(0,0,0,0.6)'; ctx.stroke();
        ctx.fillStyle = '#111';
        ctx.beginPath(); ctx.moveTo(x - 4, cy - 6); ctx.lineTo(x - 11, cy); ctx.lineTo(x - 4, cy + 6); ctx.closePath(); ctx.fill();
        ctx.beginPath(); ctx.moveTo(x + 4, cy - 6); ctx.lineTo(x + 11, cy); ctx.lineTo(x + 4, cy + 6); ctx.closePath(); ctx.fill();
        tag('A: ' + nameOf(S.a), left, top, 'left');
        tag('B: ' + nameOf(S.b), right, top, 'right', '#8db4ff');
      } else if (o === 'blink') {
        tag((S.blinkOn ? 'B: ' + nameOf(S.b) : 'A: ' + nameOf(S.a)), left, top, 'left', S.blinkOn ? '#8db4ff' : null);
      } else if (o === 'diff') {
        tag('Difference |A - B|, gain ' + S.gain + 'x, noise floor ' + S.floor, left, top, 'left');
        tag('A: ' + nameOf(S.a) + '  B: ' + nameOf(S.b), left, top + 28, 'left');
      } else if (o && o.strips) {
        var n = o.strips.length, vert = S.mode === 'vstrips', k;
        for (k = 0; k < n; k++) {
          var lab = o.strips[k].letter + ': ' + nameOf(o.strips[k].id);
          if (vert) { tag(lab, Math.max(8, S.tx + k * w * s / n + 8), top, 'left'); }
          else { tag(lab, left, Math.max(8, S.ty + k * h * s / n + 8), 'left'); }
          if (k > 0) {
            ctx.fillStyle = '#fff';
            if (vert) { ctx.fillRect(Math.round(S.tx + k * w * s / n) - 1, Math.max(0, S.ty), 2, Math.min(v.h, h * s)); }
            else { ctx.fillRect(Math.max(0, S.tx), Math.round(S.ty + k * h * s / n) - 1, Math.min(v.w, w * s), 2); }
          }
        }
      }
    }

    function updateStats(st) {
      var pct = (st.changed * 100);
      el.stats.textContent = 'Difference statistics (approximate, the images are lossy WebP): ' +
        pct.toFixed(pct < 1 ? 2 : 1) + ' percent of pixels differ by more than ' + S.floor + ' brightness levels; mean excess difference ' + st.mean.toFixed(2) + ' levels.';
    }

    /* ---------- blink ---------- */
    function restartBlink() {
      if (blinkTimer) { clearInterval(blinkTimer); blinkTimer = null; }
      if (S.mode === 'blink' && !S.paused) {
        blinkTimer = setInterval(function () { S.blinkOn = !S.blinkOn; draw(); }, S.rate);
      }
      el.pause.setAttribute('aria-pressed', S.paused ? 'true' : 'false');
      el.pause.textContent = S.paused ? 'Play blink' : 'Pause blink';
    }

    /* ---------- UI population ---------- */
    function fill(sel, items, value, allowNone) {
      sel.textContent = '';
      if (allowNone) { var o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'None'; sel.appendChild(o0); }
      items.forEach(function (it) {
        var o = document.createElement('option');
        o.value = it.value; o.textContent = it.label; sel.appendChild(o);
      });
      sel.value = value;
    }
    function stateItems() { return curScene().states.map(function (st) { return { value: st.id, label: st.label }; }); }

    function populateSets() {
      fill(el.set, DATA.sets.map(function (s, i) { return { value: String(i), label: s.title }; }), String(S.set));
    }
    function populateScenes() {
      fill(el.scene, curSet().scenes.map(function (s, i) { return { value: String(i), label: s.title }; }), String(S.scene));
    }
    function populateStates() {
      var items = stateItems();
      fill(el.a, items, S.a); fill(el.b, items, S.b);
      fill(el.c, items, S.c, true); fill(el.d, items, S.d, true);
    }
    function populateModes() {
      fill(el.mode, MODES.map(function (m) { return { value: m.id, label: m.label }; }), S.mode);
    }

    function applyScene(resetStates) {
      var sc = curScene();
      el.viewer.style.aspectRatio = sc.w + ' / ' + sc.h;
      el.viewer.style.maxWidth = sc.w + 'px';
      if (resetStates) { S.a = sc.a; S.b = sc.b; S.c = ''; S.d = ''; }
      populateScenes(); populateStates();
      updateModeUi();
      applyFit();
      renderInfo();
      refresh();
      resize();
      announce();
      writeHash();
    }

    function updateModeUi() {
      var strips = S.mode === 'vstrips' || S.mode === 'hstrips';
      el.fC.classList.toggle('hidden', !strips);
      el.fD.classList.toggle('hidden', !strips);
      el.fRate.classList.toggle('hidden', S.mode !== 'blink');
      el.fBlink.classList.toggle('hidden', S.mode !== 'blink');
      el.fGain.classList.toggle('hidden', S.mode !== 'diff');
      el.fFloor.classList.toggle('hidden', S.mode !== 'diff');
      el.fSplit.classList.toggle('hidden', S.mode !== 'slider');
      el.stats.classList.toggle('hidden', S.mode !== 'diff');
      if (strips) {
        var unused = curScene().states.map(function (x) { return x.id; }).filter(function (id) { return id !== S.a && id !== S.b; });
        if (!S.c && unused.length) { S.c = unused.shift(); }
        if (!S.d && unused.length) { S.d = unused.shift(); }
        populateStates();
      }
      el.canvas.classList.toggle('slider', S.mode === 'slider');
      el.canvas.classList.toggle('pan', !S.fit);
    }

    function renderInfo() {
      var sc = curScene(), set = curSet();
      el.title.textContent = sc.title;
      el.desc.textContent = sc.desc;
      el.hint.textContent = sc.hint;
      el.verdictTitle.textContent = set.title + ': what to expect';
      el.verdict.textContent = '';
      [set.summary, set.verdict].forEach(function (t) {
        var p = document.createElement('p'); p.textContent = t; el.verdict.appendChild(p);
      });
      el.states.textContent = '';
      sc.states.forEach(function (st) {
        var li = document.createElement('li');
        var slot = SLOTS.filter(function (k) { return S[k] === st.id; }).map(function (k) { return k.toUpperCase(); }).join('');
        var tg = document.createElement('span'); tg.className = 'tag'; tg.textContent = slot || '-';
        var a = document.createElement('a'); a.href = urlOf(st); a.textContent = st.label; a.target = '_blank'; a.rel = 'noopener';
        var sz = document.createElement('span'); sz.className = 'size';
        sz.textContent = Math.round(st.bytes / 1024) + ' KB, ' + sc.w + 'x' + sc.h;
        li.appendChild(tg); li.appendChild(a); li.appendChild(sz);
        if (st.note) { var nt = document.createElement('span'); nt.className = 'small'; nt.textContent = st.note; li.appendChild(nt); }
        el.states.appendChild(li);
      });
      el.canvas.setAttribute('aria-label', 'Image comparison: ' + sc.title + '. Use the controls above to choose the mode and the images.');
    }

    function announce() {
      var m = MODES.filter(function (x) { return x.id === S.mode; })[0];
      el.sr.textContent = curScene().title + ', ' + (m ? m.label : S.mode) + ', A: ' + nameOf(S.a) + ', B: ' + nameOf(S.b) + '.';
    }

    /* ---------- hash (shareable links) ---------- */
    function writeHash() {
      var p = ['set=' + curSet().id, 'scene=' + curScene().id, 'mode=' + S.mode, 'a=' + S.a, 'b=' + S.b];
      if (S.c) { p.push('c=' + S.c); }
      if (S.d) { p.push('d=' + S.d); }
      if (S.mode === 'slider') { p.push('split=' + S.split.toFixed(2)); }
      try { history.replaceState(null, '', '#' + p.join('&')); } catch (e) { /* ignore */ }
    }
    function resetStates() {
      var sc = curScene();
      S.a = sc.a; S.b = sc.b; S.c = ''; S.d = '';
    }
    function readHash() {
      var h = location.hash.replace(/^#/, '');
      var q = {}, i, j;
      h.split('&').forEach(function (kv) { var x = kv.indexOf('='); if (x > 0) { q[kv.slice(0, x)] = decodeURIComponent(kv.slice(x + 1)); } });
      for (i = 0; i < DATA.sets.length; i++) {
        if (DATA.sets[i].id === q.set) {
          S.set = i; S.scene = 0;
          for (j = 0; j < DATA.sets[i].scenes.length; j++) { if (DATA.sets[i].scenes[j].id === q.scene) { S.scene = j; } }
        }
      }
      resetStates();
      SLOTS.forEach(function (k) { if (q[k] && stateOf(q[k])) { S[k] = q[k]; } });
      if (MODES.some(function (m) { return m.id === q.mode; })) { S.mode = q.mode; }
      if (q.split && !isNaN(+q.split)) { S.split = Math.max(0, Math.min(1, +q.split)); }
    }

    /* ---------- events ---------- */
    el.set.addEventListener('change', function () { S.set = +el.set.value; S.scene = 0; applyScene(true); });
    el.scene.addEventListener('change', function () { S.scene = +el.scene.value; applyScene(true); });
    el.mode.addEventListener('change', function () {
      S.mode = el.mode.value; S.blinkOn = false;
      updateModeUi(); restartBlink(); renderInfo(); refresh(); draw(); announce(); writeHash();
    });
    SLOTS.forEach(function (k) {
      el[k].addEventListener('change', function () {
        S[k] = el[k].value; diffCache.key = '';
        renderInfo(); refresh(); draw(); announce(); writeHash();
      });
    });
    el.rate.addEventListener('change', function () { S.rate = +el.rate.value; restartBlink(); });
    el.gain.addEventListener('input', function () { S.gain = +el.gain.value; el.gainVal.textContent = S.gain; draw(); });
    el.floor.addEventListener('input', function () { S.floor = +el.floor.value; el.floorVal.textContent = S.floor; draw(); });
    el.split.addEventListener('input', function () { S.split = +el.split.value / 100; draw(); });
    el.split.addEventListener('change', writeHash);
    el.pause.addEventListener('click', function () { S.paused = !S.paused; restartBlink(); });
    el.flip.addEventListener('click', function () { S.blinkOn = !S.blinkOn; draw(); });
    $('cmp-zoom-fit').addEventListener('click', function () { applyFit(); draw(); });
    $('cmp-zoom-1').addEventListener('click', function () { setZoom(1); });
    $('cmp-zoom-2').addEventListener('click', function () { setZoom(2); });
    $('cmp-zoom-4').addEventListener('click', function () { setZoom(4); });

    function syncSplit() { el.split.value = Math.round(S.split * 100); }
    function ptr(e) { var r = el.canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; }
    function lineX() { return S.tx + S.split * W() * S.scale; }

    el.canvas.addEventListener('pointerdown', function (e) {
      if (e.button !== undefined && e.button > 0) { return; }
      var p = ptr(e);
      el.canvas.setPointerCapture(e.pointerId);
      if (S.mode === 'slider' && (S.fit || Math.abs(p.x - lineX()) < 24)) {
        drag = { t: 'split' };
        S.split = Math.max(0, Math.min(1, (p.x - S.tx) / (W() * S.scale)));
        syncSplit(); draw();
      } else if (!S.fit) {
        drag = { t: 'pan', x: p.x, y: p.y, tx: S.tx, ty: S.ty };
        el.canvas.classList.add('panning');
      }
    });
    el.canvas.addEventListener('pointermove', function (e) {
      if (!drag) { return; }
      var p = ptr(e);
      if (drag.t === 'split') {
        S.split = Math.max(0, Math.min(1, (p.x - S.tx) / (W() * S.scale)));
        syncSplit(); draw();
      } else {
        S.tx = drag.tx + p.x - drag.x; S.ty = drag.ty + p.y - drag.y; clampPan(); draw();
      }
    });
    function endDrag() {
      if (drag && drag.t === 'split') { writeHash(); }
      drag = null; el.canvas.classList.remove('panning');
    }
    el.canvas.addEventListener('pointerup', endDrag);
    el.canvas.addEventListener('pointercancel', endDrag);
    el.canvas.addEventListener('dblclick', function () { applyFit(); draw(); });
    el.canvas.addEventListener('wheel', function (e) {
      /* plain wheel scrolls the page while the image is fitted; Ctrl/Cmd + wheel (and trackpad pinch) zooms */
      if (!(e.ctrlKey || e.metaKey || !S.fit)) { return; }
      e.preventDefault();
      var p = ptr(e);
      setZoom(S.scale * (e.deltaY < 0 ? 1.2 : 1 / 1.2), p.x, p.y);
    }, { passive: false });

    el.canvas.addEventListener('keydown', function (e) {
      var k = e.key, step = e.shiftKey ? 0.1 : 0.02, handled = true;
      if (k === 'ArrowLeft' || k === 'ArrowRight') {
        if (S.mode === 'slider') {
          S.split = Math.max(0, Math.min(1, S.split + (k === 'ArrowLeft' ? -step : step)));
          syncSplit(); draw(); writeHash();
        } else if (!S.fit) { S.tx += (k === 'ArrowLeft' ? 40 : -40); clampPan(); draw(); }
        else { handled = false; }
      } else if (k === 'ArrowUp' || k === 'ArrowDown') {
        if (!S.fit) { S.ty += (k === 'ArrowUp' ? 40 : -40); clampPan(); draw(); } else { handled = false; }
      } else if (k === ' ' || k === 'Enter') {
        if (S.mode === 'blink') { S.paused = !S.paused; restartBlink(); } else { handled = false; }
      } else if (k === '+' || k === '=') { setZoom(S.scale * 1.25); }
      else if (k === '-') { setZoom(S.scale / 1.25); }
      else if (k === '0') { applyFit(); draw(); }
      else if (k >= '1' && k <= '9') {
        var st = curScene().states[+k - 1];
        if (st) { S.b = st.id; el.b.value = st.id; diffCache.key = ''; renderInfo(); refresh(); draw(); announce(); writeHash(); }
      } else { handled = false; }
      if (handled) { e.preventDefault(); }
    });

    if (typeof ResizeObserver === 'function') { new ResizeObserver(function () { resize(); }).observe(el.viewer); }
    else { window.addEventListener('resize', resize); }

    /* ---------- go ---------- */
    readHash();
    S.rate = +el.rate.value; S.gain = +el.gain.value; S.floor = +el.floor.value;
    el.gainVal.textContent = S.gain; el.floorVal.textContent = S.floor;
    populateSets(); populateModes();
    applyScene(false);
    syncSplit();
    restartBlink();
    window.addEventListener('hashchange', function () {
      readHash(); populateSets(); populateModes(); applyScene(false); syncSplit(); restartBlink();
    });
  }

  function start() {
    initFilter();
    var root = document.getElementById('cmp');
    if (root && window.CMP_DATA && window.CMP_DATA.sets) { initCompare(root, window.CMP_DATA); }
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', start); }
  else { start(); }
})();
