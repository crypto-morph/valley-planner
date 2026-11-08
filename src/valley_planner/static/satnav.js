/* Today as a satnav: one instruction at a time, the next one under it, and the valley's map following the walk.
 *
 *   const nav = ValleySatnav.mount(element, {params: {done: "tv,water", spouse: "Penny"}, onDone: (id) => tick(id)});
 *   await nav.ready;                  // the plan is in and the first map is drawn
 *   nav.next(); nav.back();           // one instruction on or back (also: Next/Back buttons, arrow keys, a swipe)
 *   nav.done();                       // "Arrived — done with this stop": onDone(id, row), then on to the next stop
 *   nav.reload({time: 1100}); nav.destroy();
 *
 * Options: params (as for /api/today: time, energy, where, done, spouse), onDone(id, row) (the host ticks the stop;
 * the satnav strikes it and moves on without asking the server again), fill (the map takes the element's spare
 * height, for a page of its own), url (default /api/today).
 * The steps come from each plan row's `steps` (facts/walk.py Walker.steps: a compass leg, the edge you leave by, the
 * door you go in at), then the stop itself; the day ends with `home_steps`. Needs static/map.js (window.ValleyMap).
 * Plain script: attaches ValleySatnav to window. Styles come with it (<style id="valley-satnav-css">), under .vsn.
 */
(function () {
  "use strict";
  const TILE = 16;
  const ROUTE = "#C2255C";  // the Map tab's route colour
  const PUCK = "#1C7ED6";
  const HEADINGS = { north: 0, northeast: 45, east: 90, southeast: 135, south: 180, southwest: 225, west: 270, northwest: 315 };
  const SHORT = { north: "N", northeast: "NE", east: "E", southeast: "SE", south: "S", southwest: "SW", west: "W", northwest: "NW" };
  const GLYPHS = {  // 48x48, white on the dark banner
    walk: '<path d="M24 3 41 22H30.5V45h-13V22H7z" fill="currentColor"/>',
    exit: '<path d="M5 5h38" stroke="currentColor" stroke-width="4.5" stroke-linecap="round"/>' +
      '<path d="M24 11 39 27H29.5V45h-11V27H9z" fill="currentColor"/>',
    door: '<rect x="11" y="4" width="26" height="40" rx="2" fill="none" stroke="currentColor" stroke-width="3.5"/>' +
      '<path d="M15 44V8h18v36" fill="currentColor" opacity=".25"/><circle cx="30" cy="26" r="2.4" fill="currentColor"/>' +
      '<path d="M3 26h14m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
    arrive: '<path d="M24 3C15.7 3 9 9.6 9 17.8 9 29 24 45 24 45s15-16 15-27.2C39 9.6 32.3 3 24 3z" fill="currentColor"/>' +
      '<circle cx="24" cy="18" r="6" fill="#14181C"/>',
    home: '<path d="M6 23 24 7l18 16" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>' +
      '<path d="M11 21v22h10V31h6v12h10V21L24 10z" fill="currentColor"/>',
  };
  const STYLE = `
.vsn { --vsn-bg: #14181C; --vsn-bg2: #20262C; --vsn-ink: #F4F6F2; --vsn-dim: #A9B3AC; --vsn-hi: #FFD43B;
  display: flex; flex-direction: column; gap: 0; color: var(--ink, #1C2620); font-family: var(--font, system-ui, sans-serif);
  -webkit-tap-highlight-color: transparent; }
.vsn:focus { outline: none; }
.vsn.vsn-fill { height: 100%; min-height: 0; }
.vsn-banner { background: var(--vsn-bg); color: var(--vsn-ink); border-radius: 14px 14px 0 0; padding: 14px 16px 12px;
  display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; align-items: center; position: relative; }
.vsn-arrow { grid-column: 1; grid-row: 2 / span 2; width: 84px; display: grid; justify-items: center; gap: 2px; color: var(--vsn-ink); }
.vsn-arrow svg { width: 72px; height: 72px; display: block; transition: transform .25s ease; }
.vsn-arrow .vsn-compass { font: 700 13px/1 var(--font, system-ui, sans-serif); letter-spacing: .06em; color: var(--vsn-dim); }
.vsn-dist { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; min-width: 0; }
.vsn-dist b { font: 800 34px/1.05 var(--font, system-ui, sans-serif); font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.vsn-dist span { font-size: 15px; color: var(--vsn-dim); }
.vsn-text { font: 700 21px/1.25 var(--font, system-ui, sans-serif); margin: 0; overflow-wrap: anywhere; }
.vsn-why { grid-column: 1 / -1; margin: 6px 0 0; font-size: 15px; line-height: 1.4; color: #D5DCD6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; cursor: pointer; }
.vsn-why.vsn-open { -webkit-line-clamp: unset; display: block; }
.vsn-why:empty { display: none; }
.vsn-meta { grid-column: 1 / -1; grid-row: 1; display: flex; justify-content: space-between; gap: 12px; font-size: 13px;
  line-height: 1.3; color: var(--vsn-dim); margin-bottom: 4px; min-width: 0; }
.vsn-meta span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vsn-meta strong { color: var(--vsn-hi); font-size: 14px; font-variant-numeric: tabular-nums; flex: none; }
.vsn-progress { grid-column: 1 / -1; height: 4px; border-radius: 2px; background: rgba(255,255,255,.12); margin-top: 8px; overflow: hidden; }
.vsn-progress i { display: block; height: 100%; background: var(--vsn-hi); transition: width .25s ease; }
.vsn-then { background: var(--vsn-bg2); color: var(--vsn-ink); display: flex; align-items: center; gap: 10px;
  padding: 9px 16px; font-size: 15px; min-height: 44px; box-sizing: border-box; }
.vsn-then svg { width: 22px; height: 22px; flex: none; color: var(--vsn-dim); }
.vsn-then b { color: var(--vsn-dim); font-weight: 700; flex: none; }
.vsn-then span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.vsn-map { position: relative; overflow: hidden; background: #0D1012; height: var(--vsn-map-h, clamp(260px, 48vh, 560px));
  touch-action: pan-y; user-select: none; -webkit-user-select: none; }
.vsn.vsn-fill .vsn-map { height: auto; flex: 1 1 auto; min-height: 220px; }
.vsn-stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; will-change: transform; }
.vsn-stage canvas { display: block; image-rendering: pixelated; }
.vsn-over { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.vsn-place { position: absolute; left: 10px; top: 10px; background: rgba(20,24,28,.86); color: #fff; font-size: 13px;
  font-weight: 700; padding: 5px 10px; border-radius: 999px; pointer-events: none; }
.vsn-north { position: absolute; right: 10px; top: 10px; width: 30px; height: 30px; border-radius: 50%;
  background: rgba(20,24,28,.86); color: #fff; display: grid; place-items: center; font: 800 12px/1 system-ui, sans-serif; pointer-events: none; }
.vsn-status { position: absolute; inset: auto 10px 10px 10px; background: rgba(20,24,28,.86); color: #fff; font-size: 14px;
  padding: 8px 12px; border-radius: 8px; }
.vsn-status[hidden] { display: none; }
.vsn-bar { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 10px; background: var(--panel, #fff);
  border: 1px solid var(--line, #D9DDD3); border-top: 0; border-radius: 0 0 14px 14px; }
.vsn-bar button { font: 700 17px/1.1 var(--font, system-ui, sans-serif); min-height: 52px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--line, #D9DDD3); background: var(--panel-2, #F8F9F4); color: var(--ink, #1C2620);
  display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 0 12px; }
.vsn-bar button:disabled { opacity: .4; cursor: default; }
.vsn-bar button:focus-visible, .vsn-stops button:focus-visible { outline: 3px solid var(--vsn-hi); outline-offset: 2px; }
.vsn-bar .vsn-next { background: var(--accent, #2B6A3E); border-color: var(--accent, #2B6A3E); color: #fff; }
.vsn-bar .vsn-done { grid-column: 1 / -1; background: transparent; color: var(--accent, #2B6A3E); border-color: var(--accent, #2B6A3E); }
.vsn-bar .vsn-done.vsn-now { background: var(--accent, #2B6A3E); color: #fff; }
.vsn-bar .vsn-done[hidden] { display: none; }
.vsn-bar svg { width: 20px; height: 20px; }
.vsn-stops { list-style: none; margin: 10px 0 0; padding: 0 0 4px; display: flex; gap: 6px; overflow-x: auto; scrollbar-width: thin; }
.vsn-stops button { font: 14px/1.2 var(--font, system-ui, sans-serif); min-height: 44px; display: flex; align-items: center; gap: 8px;
  padding: 4px 12px 4px 4px; border-radius: 22px; border: 1px solid var(--line, #D9DDD3); background: var(--panel, #fff);
  color: var(--ink, #1C2620); cursor: pointer; white-space: nowrap; max-width: 260px; }
.vsn-stops button span:last-child { overflow: hidden; text-overflow: ellipsis; }
.vsn-stops .vsn-n { display: grid; place-items: center; min-width: 34px; height: 34px; border-radius: 17px; background: ${ROUTE};
  color: #fff; font-weight: 800; font-size: 14px; }
.vsn-stops [aria-current="step"] { border-color: ${ROUTE}; box-shadow: inset 0 0 0 1px ${ROUTE}; }
.vsn-stops .vsn-gone { opacity: .55; text-decoration: line-through; }
.vsn-stops .vsn-gone .vsn-n { background: var(--muted, #4F5A53); }
@media (max-width: 520px) {
  .vsn-banner { padding: 12px 12px 10px; gap: 2px 12px; border-radius: 12px 12px 0 0; }
  .vsn-arrow { width: 64px; }
  .vsn-arrow svg { width: 58px; height: 58px; }
  .vsn-dist b { font-size: 28px; }
  .vsn-text { font-size: 18px; }
  .vsn-meta { font-size: 12px; }
  .vsn-then { padding: 8px 12px; }
}
@media (prefers-reduced-motion: reduce) { .vsn-arrow svg, .vsn-progress i { transition: none; } }
`;

  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k === "html") n.innerHTML = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid);
    return n;
  }

  function svg(tag, attrs) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    return n;
  }

  function glyph(kind, heading) {
    const turn = (kind === "walk" || kind === "exit") && heading in HEADINGS ? HEADINGS[heading] : 0;
    return `<svg viewBox="0 0 48 48" aria-hidden="true" style="transform:rotate(${turn}deg)">${GLYPHS[kind] || GLYPHS.walk}</svg>`;
  }

  function query(params) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params || {})) {
      if (v === undefined || v === null || v === "") continue;
      q.set(k, Array.isArray(v) ? v.join(",") : String(v));
    }
    const s = q.toString();
    return s ? `?${s}` : "";
  }

  function injectCSS() {
    if (document.getElementById("valley-satnav-css")) return;
    document.head.append(el("style", { id: "valley-satnav-css", text: STYLE }));
  }

  // The day as a list of instructions: each stop's walk, then the stop itself; the walk home last.
  function buildSteps(data) {
    const out = [];
    const st = data.start || ["Farm", 64, 16];
    let pos = { loc: st[0], x: st[1], y: st[2] };
    const walkOn = (steps, stop, row) => {
      for (const s of steps || []) {
        out.push({ ...s, stop, row });
        pos = { loc: s.loc, x: s.to[0], y: s.to[1] };
      }
    };
    data.plan.forEach((row, i) => {
      walkOn(row.steps, i, row);
      const at = row.spot ? { loc: row.spot[0], x: row.spot[1], y: row.spot[2] } : pos;
      out.push({ kind: "arrive", stop: i, row, loc: at.loc, from: [at.x, at.y], to: [at.x, at.y], points: [[at.x, at.y]],
        text: row.title, why: row.why || "" });
      if (!row.spot) pos = at;
    });
    const home = data.plan.length;
    walkOn(data.home_steps, home, null);
    if (data.home_steps && data.home_steps.length) {
      out.push({ kind: "home", stop: home, row: null, loc: pos.loc, from: [pos.x, pos.y], to: [pos.x, pos.y],
        points: [[pos.x, pos.y]], text: "Home", why: data.home ? `Back at the farmhouse about ${data.home}.` : "" });
    }
    return out;
  }

  function mount(root, opts = {}) {
    if (!window.ValleyMap) throw new Error("ValleySatnav needs static/map.js (ValleyMap) loaded first");
    injectCSS();
    const url = opts.url || "/api/today";
    let params = { ...(opts.params || {}) };
    const state = { data: null, steps: [], i: 0, loc: null, map: null, z: 1, px: 0, py: 0, gone: new Set(),
      canvases: new Map(), drawing: null, anim: 0, dead: false };
    const names = new Map();  // map id -> its name, picked up from the exits' words

    root.classList.add("vsn");
    if (opts.fill) root.classList.add("vsn-fill");
    root.replaceChildren();
    const arrow = el("div", { class: "vsn-arrow" });
    const dist = el("div", { class: "vsn-dist" });
    const text = el("p", { class: "vsn-text" });
    const why = el("p", { class: "vsn-why", title: "Tap to show it all" });
    const meta = el("div", { class: "vsn-meta" });
    const bar = el("i");
    const banner = el("section", { class: "vsn-banner", "aria-live": "polite", "aria-atomic": "true",
      "aria-label": "Current instruction" }, arrow, dist, text, why, meta, el("div", { class: "vsn-progress" }, bar));
    const then = el("div", { class: "vsn-then", "aria-label": "Next instruction" });
    const stage = el("div", { class: "vsn-stage" });
    const over = svg("svg", { class: "vsn-over", "aria-hidden": "true" });
    const placeChip = el("div", { class: "vsn-place" });
    const status = el("div", { class: "vsn-status", role: "status", text: "Loading today…" });
    const mapBox = el("div", { class: "vsn-map", role: "img", "aria-label": "Map of this part of the walk" },
      stage, over, placeChip, el("div", { class: "vsn-north", title: "North is up", text: "N" }), status);
    const backBtn = el("button", { type: "button", class: "vsn-back", html:
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Back' });
    const nextBtn = el("button", { type: "button", class: "vsn-next", html:
      'Next<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>' });
    const doneBtn = el("button", { type: "button", class: "vsn-done", text: "Arrived — done with this stop" });
    const stops = el("ol", { class: "vsn-stops", "aria-label": "Today's stops" });
    root.append(banner, then, mapBox, el("div", { class: "vsn-bar" }, backBtn, nextBtn, doneBtn), stops);
    if (!root.hasAttribute("tabindex")) root.setAttribute("tabindex", "-1");

    backBtn.addEventListener("click", () => go(state.i - 1));
    nextBtn.addEventListener("click", () => go(state.i + 1));
    doneBtn.addEventListener("click", () => done());
    why.addEventListener("click", () => why.classList.toggle("vsn-open"));

    // Arrow keys when the satnav (or nothing in particular) has focus; a sideways swipe on a phone.
    const onKey = (e) => {
      const a = document.activeElement;
      if (!state.steps.length || e.altKey || e.ctrlKey || e.metaKey) return;
      if (!(root.contains(a) || a === document.body) || !root.offsetParent) return;
      if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
      if (e.key === "ArrowRight") { go(state.i + 1); e.preventDefault(); }
      else if (e.key === "ArrowLeft") { go(state.i - 1); e.preventDefault(); }
    };
    document.addEventListener("keydown", onKey);
    let swipe = null;
    root.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" || e.target.closest("button")) return;
      swipe = { x: e.clientX, y: e.clientY, id: e.pointerId };
    });
    root.addEventListener("pointerup", (e) => {
      if (!swipe || swipe.id !== e.pointerId) return;
      const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y;
      swipe = null;
      if (Math.abs(dx) > 60 && Math.abs(dx) > 1.5 * Math.abs(dy)) go(state.i + (dx < 0 ? 1 : -1));
    });
    root.addEventListener("pointercancel", () => { swipe = null; });

    // --- the map ---------------------------------------------------------------------------------------------
    function size() { return { w: mapBox.clientWidth, h: mapBox.clientHeight }; }
    function toScreen(x, y) {
      return [state.px + (x + 0.5) * TILE * state.z, state.py + (y + 0.5) * TILE * state.z];
    }
    function view(z, cx, cy) {  // where the stage goes for a centre tile at zoom z, kept on the map
      const { w, h } = size();
      const mw = state.map.width * TILE * z, mh = state.map.height * TILE * z;
      let px = w / 2 - (cx + 0.5) * TILE * z, py = h / 2 - (cy + 0.5) * TILE * z;
      px = mw <= w ? (w - mw) / 2 : Math.min(0, Math.max(w - mw, px));
      py = mh <= h ? (h - mh) / 2 : Math.min(0, Math.max(h - mh, py));
      return { z, px, py };
    }
    function frame(step) {  // the view for a step: its whole leg in sight, close enough to read the ground
      const { w, h } = size();
      const pts = [...(step.points || []), step.from, step.to].filter(Boolean);
      if (step.kind === "arrive" || step.kind === "home" || step.kind === "door") {
        const row = step.row;
        if (row && row.spot && row.spot[0] === step.loc) pts.push([row.spot[1], row.spot[2]]);
      }
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const pad = 5;
      const bw = Math.max(...xs) - Math.min(...xs) + 1 + 2 * pad, bh = Math.max(...ys) - Math.min(...ys) + 1 + 2 * pad;
      const whole = Math.min(w / (state.map.width * TILE), h / (state.map.height * TILE));
      const cover = Math.max(w / (state.map.width * TILE), h / (state.map.height * TILE));  // no empty bands
      const near = (Math.min(w, h) < 420 ? 1.5 : 2.5) * (pts.length > 3 ? 1.2 : 1);  // close, but with the ground around
      const z = Math.max(Math.min(whole, 0.5), Math.min(cover, near), Math.min(near, w / (bw * TILE), h / (bh * TILE)));
      return view(z, (Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2);
    }
    function apply() {
      stage.style.transform = `translate(${state.px}px, ${state.py}px) scale(${state.z})`;
      drawOverlay();
    }
    function moveTo(target, animate) {
      cancelAnimationFrame(state.anim);
      const still = !animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (still) { Object.assign(state, target); apply(); return; }
      const from = { z: state.z, px: state.px, py: state.py }, t0 = performance.now(), ms = 420;
      const tick = (t) => {
        const k = Math.min(1, (t - t0) / ms), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        // zoom in the log so the middle of the move doesn't swing wide
        state.z = from.z * Math.pow(target.z / from.z, e);
        state.px = from.px + (target.px - from.px) * e;
        state.py = from.py + (target.py - from.py) * e;
        apply();
        if (k < 1) state.anim = requestAnimationFrame(tick);
      };
      state.anim = requestAnimationFrame(tick);
    }

    async function mapCanvas(loc) {
      if (!state.canvases.has(loc)) {
        const canvas = document.createElement("canvas");
        state.canvases.set(loc, ValleyMap.drawWhole(canvas, loc, { scale: 1 }).then((info) => ({ canvas, info }))
          .catch((e) => { state.canvases.delete(loc); throw e; }));
      }
      return state.canvases.get(loc);
    }

    async function showMap(step) {
      if (state.loc === step.loc && state.map) { moveTo(frame(step), true); return; }
      const ticket = (state.drawing = {});
      status.hidden = false;
      status.textContent = "Drawing the map…";
      placeChip.textContent = placeName(step.loc);
      let got;
      try {
        got = await mapCanvas(step.loc);
      } catch (e) {
        if (state.drawing !== ticket) return;
        stage.replaceChildren(); over.replaceChildren(); state.map = null; state.loc = null;
        status.textContent = `Couldn't draw ${placeName(step.loc)}: ${e.message}`;
        return;
      }
      if (state.drawing !== ticket || state.dead) return;
      status.hidden = true;
      stage.replaceChildren(got.canvas);
      state.loc = step.loc;
      state.map = got.info;
      moveTo(frame(current()), false);
      // the next maps along the way, drawn while you read this one
      for (const s of state.steps.slice(state.i, state.i + 12)) if (s.loc !== step.loc) mapCanvas(s.loc).catch(() => {});
    }

    function line(points, attrs) {
      const d = points.map(([x, y], i) => { const [sx, sy] = toScreen(x, y); return `${i ? "L" : "M"}${sx.toFixed(1)},${sy.toFixed(1)}`; }).join("");
      return svg("path", { d, fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round", ...attrs });
    }

    function chevrons(points, g) {  // arrowheads every ~70 screen pixels, pointing the way you walk
      let carry = 30;
      for (let i = 1; i < points.length; i++) {
        const [ax, ay] = toScreen(...points[i - 1]), [bx, by] = toScreen(...points[i]);
        const len = Math.hypot(bx - ax, by - ay);
        if (!len) continue;
        const ang = Math.atan2(by - ay, bx - ax) * 180 / Math.PI;
        let d = carry;
        while (d < len) {
          const x = ax + (bx - ax) * d / len, y = ay + (by - ay) * d / len;
          g.append(svg("path", { d: "M-4,-5.5 L3.5,0 L-4,5.5", fill: "none", stroke: "#fff", "stroke-width": 2.6,
            "stroke-linecap": "round", "stroke-linejoin": "round", transform: `translate(${x},${y}) rotate(${ang})` }));
          d += 70;
        }
        carry = d - len;
      }
    }

    function drawOverlay() {
      over.replaceChildren();
      const step = current();
      if (!state.map || !step || step.loc !== state.loc) return;
      const g = svg("g", {});
      // the rest of the day, faint; this stop's walk stronger; this instruction bold
      for (const leg of state.data.route) {
        const mine = leg.stop === step.stop;
        for (const ln of leg.lines) {
          if (ln.loc !== state.loc || ln.points.length < 2) continue;
          if (mine) g.append(line(ln.points, { stroke: "#fff", "stroke-width": 7, opacity: 0.55 }));
          g.append(line(ln.points, { stroke: ROUTE, "stroke-width": mine ? 4 : 3, opacity: mine ? 0.6 : 0.28,
            "stroke-dasharray": leg.stop >= state.data.plan.length ? "7 6" : null }));
        }
      }
      const pts = step.points || [];
      if (pts.length > 1 && step.kind !== "door") {
        g.append(line(pts, { stroke: "#fff", "stroke-width": 12 }));
        g.append(line(pts, { stroke: ROUTE, "stroke-width": 7.5 }));
        chevrons(pts, g);
      }
      // stops on this map: numbered pins, this one large
      state.data.plan.forEach((row, i) => {
        if (!row.spot || row.spot[0] !== state.loc) return;
        const big = i === step.stop, r = big ? 13 : 9, gone = state.gone.has(row.id);
        if (big && step.kind === "door") return;  // the door's own square marks it
        const [sx, sy] = toScreen(row.spot[1], row.spot[2]);
        const pin = svg("g", { transform: `translate(${sx},${sy - (big ? 24 : 0)})`, opacity: gone ? 0.5 : big ? 1 : 0.8 });
        if (big) {  // a teardrop whose point is on the tile
          pin.append(svg("path", { d: `M0,${r + 11} L-9,${r - 6} L9,${r - 6} Z`, fill: ROUTE, stroke: "#fff", "stroke-width": 2.5, "stroke-linejoin": "round" }));
          pin.append(svg("circle", { cy: r + 11, r: 3, fill: "#fff" }));
        }
        pin.append(svg("circle", { r, fill: gone ? "#666" : ROUTE, stroke: "#fff", "stroke-width": big ? 3 : 2 }));
        const n = svg("text", { "text-anchor": "middle", "dominant-baseline": "central", fill: "#fff",
          "font-size": big ? 14 : 11, "font-weight": 800, "font-family": "system-ui, sans-serif" });
        n.textContent = String(i + 1);
        pin.append(n);
        g.append(pin);
      });
      // where this instruction leaves the map, or the door it goes in at
      if (step.kind === "exit") {
        const [sx, sy] = toScreen(...step.to);
        const label = `${{ north: "↑", northeast: "↗", east: "→", southeast: "↘", south: "↓", southwest: "↙", west: "←", northwest: "↖" }[step.heading] || "→"} ${placeName(step.onto)}`;
        const t = svg("text", { x: 0, y: 0, fill: "#fff", "font-size": 14, "font-weight": 800, "font-family": "system-ui, sans-serif",
          "dominant-baseline": "central" });
        t.textContent = label;
        const wpx = label.length * 8.2 + 16;
        const { w, h } = size();
        const lx = Math.min(Math.max(6, sx - wpx / 2), w - wpx - 6), ly = Math.min(Math.max(20, sy + (step.heading === "north" ? 26 : -26)), h - 20);
        const tag = svg("g", { transform: `translate(${lx},${ly})` });
        tag.append(svg("rect", { x: 0, y: -14, width: wpx, height: 28, rx: 14, fill: "#14181C", stroke: ROUTE, "stroke-width": 2 }));
        t.setAttribute("x", 8);
        tag.append(t);
        g.append(tag);
      }
      if (step.kind === "door") {
        const [sx, sy] = toScreen(...step.to);
        const s = 10 * Math.max(1, state.z) * 0.9;
        g.append(svg("rect", { x: sx - s, y: sy - s, width: 2 * s, height: 2 * s, rx: 3, fill: "none", stroke: "#FFD43B", "stroke-width": 3.5 }));
      }
      // you are here: at the start of this instruction, pointing the way to go (at a stop, its pin says it)
      if (step.kind === "arrive" && step.row && step.row.spot) { over.append(g); return; }
      const [px, py] = toScreen(...step.from);
      const puck = svg("g", { transform: `translate(${px},${py})` });
      puck.append(svg("circle", { r: 20, fill: PUCK, opacity: 0.18 }));
      if (step.heading in HEADINGS && step.kind !== "arrive") {
        puck.append(svg("path", { d: "M0,-19 L8,-6 L-8,-6 Z", fill: PUCK, stroke: "#fff", "stroke-width": 2, "stroke-linejoin": "round",
          transform: `rotate(${HEADINGS[step.heading]})` }));
      }
      puck.append(svg("circle", { r: 9, fill: PUCK, stroke: "#fff", "stroke-width": 3 }));
      g.append(puck);
      over.append(g);
    }

    // --- the words -------------------------------------------------------------------------------------------
    function current() { return state.steps[state.i]; }

    function placeName(loc) { return names.get(loc) || ({ BusStop: "Bus Stop", Mountain: "Mountains", Town: "Pelican Town" })[loc] || loc; }

    function stopName(row) { return row ? row.title.split(":")[0] : "Home"; }

    function distance(step) {
      if (step.kind === "walk" || (step.kind === "exit" && step.tiles > 0)) {
        return [`${step.tiles} tile${step.tiles === 1 ? "" : "s"}`, step.minutes ? `about ${step.minutes} min` : ""];
      }
      if (step.kind === "exit") return ["Now", ""];
      if (step.kind === "door") return ["Door", ""];
      if (step.kind === "arrive") return [step.row.time || "Here", step.row.place ? `at ${step.row.place}` : ""];
      return [state.data.home || "Home", "home"];
    }

    function short(step) {
      if (!step) return "That's the day done.";
      if (step.kind === "arrive") return `Arrive: ${step.text}`;
      return step.text;
    }

    function render() {
      const step = current();
      if (!step) return;
      arrow.innerHTML = glyph(step.kind, step.heading) +
        (step.kind === "walk" || step.kind === "exit" ? `<span class="vsn-compass">${SHORT[step.heading] || ""}</span>` : "");
      const [big, small] = distance(step);
      dist.replaceChildren(...[el("b", { text: big }), small ? el("span", { text: small }) : null].filter(Boolean));
      text.textContent = step.text;
      why.textContent = step.kind === "arrive" || step.kind === "home" ? step.why : "";
      why.classList.remove("vsn-open");
      const row = step.row, total = state.data.plan.length;
      meta.replaceChildren(
          el("span", { text: row ? `Stop ${step.stop + 1} of ${total} · ${stopName(row)}` : "The walk home" }),
        el("strong", { text: row ? `${row.kind === "farm" ? "" : "arrive "}${row.time}` : state.data.home ? `home ${state.data.home}` : "" }));
      bar.style.width = `${((state.i + 1) / state.steps.length) * 100}%`;
      const nx = state.steps[state.i + 1];
      then.innerHTML = nx ? glyph(nx.kind, nx.heading) : glyph("home");
      then.append(el("b", { text: "Then" }), el("span", { text: short(nx) }));
      backBtn.disabled = state.i === 0;
      nextBtn.disabled = state.i >= state.steps.length - 1;
      const canTick = row && !state.gone.has(row.id);
      doneBtn.hidden = !canTick;
      doneBtn.classList.toggle("vsn-now", step.kind === "arrive");
      doneBtn.textContent = "Arrived — done with this stop";
      doneBtn.setAttribute("aria-label", row ? `Arrived, done with stop ${step.stop + 1}: ${row.title}` : "");
      renderStops(step);
      return showMap(step);
    }

    function renderStops(step) {
      stops.replaceChildren(...state.data.plan.map((row, i) => el("li", {}, el("button", {
        type: "button", class: state.gone.has(row.id) ? "vsn-gone" : null, "aria-current": i === step.stop ? "step" : null,
        "aria-label": `Stop ${i + 1}, ${row.time}, ${row.title}${state.gone.has(row.id) ? ", done" : ""}`,
        onclick: () => go(state.steps.findIndex((s) => s.stop === i)),
      }, el("span", { class: "vsn-n", text: String(i + 1) }), el("span", { text: `${row.time} ${stopName(row)}` })))));
      const on = stops.querySelector('[aria-current="step"]');
      if (on) stops.scrollTo({ left: Math.max(0, on.parentElement.offsetLeft - stops.clientWidth / 2 + on.offsetWidth / 2) });
    }

    function go(i) {
      if (!state.steps.length) return;
      const k = Math.max(0, Math.min(state.steps.length - 1, i));
      if (k === state.i && state.loc) return;
      state.i = k;
      render();
    }

    function done() {
      const step = current();
      if (!step || !step.row || state.gone.has(step.row.id)) return;
      const row = step.row;
      state.gone.add(row.id);
      try { if (opts.onDone) opts.onDone(row.id, row); } catch (e) { console.error(e); }
      const nx = state.steps.findIndex((s) => s.stop > step.stop && !(s.row && state.gone.has(s.row.id)));
      if (nx >= 0) go(nx); else render();
    }

    async function load() {
      status.hidden = false;
      status.textContent = "Loading today…";
      const r = await fetch(url + query(params));
      if (!r.ok) {
        let msg = `${r.status}`;
        try { msg = (await r.json()).detail || msg; } catch (_) { /* not json */ }
        throw new Error(msg);
      }
      const data = await r.json();
      if (state.dead) return;
      state.data = data;
      state.gone.clear();
      state.steps = buildSteps(data);
      for (const s of state.steps) {  // "Leave by the east edge to Bus Stop": the map's own name, for the labels
        const m = s.kind === "exit" && / edge to (.+)$/.exec(s.text);
        if (m) names.set(s.onto, m[1]);
        if (s.kind === "arrive" && s.row.spot && s.row.place) names.set(s.row.spot[0], s.row.place);
      }
      state.i = 0;
      state.loc = null;
      if (!state.steps.length) {
        status.textContent = "Nothing to walk to today.";
        text.textContent = "Nothing planned";
        return;
      }
      await render();
    }

    const resize = new ResizeObserver(() => { const s = current(); if (state.map && s && s.loc === state.loc) moveTo(frame(s), false); });
    resize.observe(mapBox);

    const ready = load().catch((e) => {
      status.hidden = false;
      status.textContent = `Couldn't load today: ${e.message}`;
    });

    return {
      ready,
      next: () => go(state.i + 1),
      back: () => go(state.i - 1),
      done,
      get index() { return state.i; },
      get steps() { return state.steps.map(({ row, ...s }) => ({ ...s, id: row ? row.id : "home" })); },
      reload(next) {
        if (next) params = { ...params, ...next };
        return load();
      },
      destroy() {
        state.dead = true;
        cancelAnimationFrame(state.anim);
        document.removeEventListener("keydown", onKey);
        resize.disconnect();
        root.replaceChildren();
        root.classList.remove("vsn", "vsn-fill");
      },
    };
  }

  window.ValleySatnav = { mount };
})();
