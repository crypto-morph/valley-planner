/* Today on the valley's maps: places of interest and the planned walk, from /api/world, drawn over ValleyMap's maps.
 *
 *   const world = ValleyWorld.mount(element, {params: {time: 900, spouse: "Penny"}});
 *   await world.ready;          // the data is in and the first map is drawn
 *   world.show("Town");         // switch map;  world.reload({time: 1200})  // ask again;  world.destroy()
 *
 * Needs static/map.js loaded first (window.ValleyMap). Plain script: attaches ValleyWorld to window. The styles
 * come with it (one <style id="valley-world-css">), scoped under .vw, using the app's colour variables when present.
 * Pan by dragging (mouse or one finger), zoom with the wheel, a pinch or the +/- buttons; arrow keys pan and +/-
 * zoom when the map has focus. Each place is a round button: it opens a small card (Escape or a click away closes).
 */
(function () {
  "use strict";
  const TILE = 16;
  const MIN_Z = 0.25, MAX_Z = 8;
  const ROUTE = "#C2255C";
  const KINDS = {
    stop: { color: ROUTE, label: "Stop" },
    forage: { color: "#2F9E44", label: "Forage" },
    dig: { color: "#8B5A2B", label: "Dig" },
    bin: { color: "#495057", label: "Garbage can" },
    bubbles: { color: "#1C7ED6", label: "Fish bubbles" },
    pan: { color: "#B8860B", label: "Pan spot" },
    cart: { color: "#E8590C", label: "Traveling Cart" },
    bookseller: { color: "#7048E8", label: "Bookseller" },
    night: { color: "#D9480F", label: "Tonight" },
    giant: { color: "#2B8A3E", label: "Giant crop" },
    shop: { color: "#6B4F3A", label: "Door" },
    villager: { color: "#9C36B5", label: "Villager" },
  };
  // Small pictures for places that have no item of their own (24x24 viewBox, drawn in the kind's colour).
  const GLYPHS = {
    forage: '<path d="M6 18c0-8 6-13 13-13 0 8-5 13-13 13zM6 18l7-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
    dig: '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>',
    bin: '<path d="M6 8h12l-1.5 11h-9zM5 6h14M10 4h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    bubbles: '<circle cx="8" cy="15" r="3.2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="15" cy="9" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17" cy="17" r="2" fill="currentColor"/>',
    pan: '<path d="M3 11h18l-2.5 6.5a2 2 0 0 1-1.9 1.5H7.4a2 2 0 0 1-1.9-1.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M21 11l2-2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M10 13.5l2-1.5 2.5 1-1 2h-2.5z" fill="currentColor"/>',
    cart: '<path d="M3 6h3l2 9h10l2-6H7" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="9" cy="19" r="1.8" fill="currentColor"/><circle cx="17" cy="19" r="1.8" fill="currentColor"/>',
    bookseller: '<path d="M4 5h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2-2H4zM20 5h-6a2 2 0 0 0-2 2v12a2 2 0 0 1 2-2h6z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
    night: '<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z" fill="currentColor"/>',
    giant: '<rect x="4" y="4" width="16" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M9.3 4v16M14.7 4v16M4 9.3h16M4 14.7h16" stroke="currentColor" stroke-width="1.2"/>',
    shop: '<path d="M6 21V5h12v16M6 21h12" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><circle cx="15" cy="13" r="1.4" fill="currentColor"/>',
    villager: '<circle cx="12" cy="8" r="4" fill="currentColor"/><path d="M4 21c0-5 4-8 8-8s8 3 8 8" fill="currentColor"/>',
  };
  const LAYERS = [
    { id: "route", label: "Route", on: true },
    { id: "places", label: "Places", on: true },
    { id: "villagers", label: "Villagers", on: false },
    { id: "doors", label: "Doors", on: false },
  ];

  const STYLE = `
.vw { --vw-ink: var(--ink, #1C2620); --vw-muted: var(--muted, #4F5A53); --vw-panel: var(--panel, #fff);
  --vw-line: var(--line, #D9DDD3); --vw-accent: var(--accent, #2B6A3E); --vw-bg: var(--panel-2, #F8F9F4);
  color: var(--vw-ink); font: inherit; min-width: 0; max-width: 100%; }
.vw *, .vw *::before, .vw *::after { box-sizing: border-box; }
.vw-places { display: flex; gap: 6px; overflow-x: auto; padding: 2px 2px 8px; scrollbar-width: thin; }
.vw-place { flex: none; display: inline-flex; align-items: center; gap: 6px; min-height: 36px; padding: 4px 12px;
  border: 1px solid var(--vw-line); border-radius: 999px; background: var(--vw-panel); color: var(--vw-ink);
  font: inherit; font-size: 14px; cursor: pointer; }
.vw-place[aria-pressed="true"] { background: var(--vw-accent); border-color: var(--vw-accent); color: #fff; }
.vw-place .vw-count { font-size: 12px; font-weight: 700; min-width: 20px; padding: 1px 6px; border-radius: 999px;
  background: rgba(0,0,0,.08); text-align: center; }
.vw-place[aria-pressed="true"] .vw-count { background: rgba(255,255,255,.22); }
.vw-place .vw-route-dot { width: 8px; height: 8px; border-radius: 50%; background: ${ROUTE}; flex: none; }
.vw-card { flex-direction: column; align-items: stretch; gap: 2px; width: 196px; border-radius: 10px; padding: 8px 10px;
  text-align: left; white-space: normal; }
.vw-card-head { display: flex; align-items: center; gap: 6px; }
.vw-card-head strong { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vw-card-icons { display: inline-flex; gap: 2px; margin-right: 6px; vertical-align: -3px; }
.vw-card-icons span, .vw-card-icons svg { width: 16px; height: 16px; display: block; }
.vw-card-facts { font-size: 13px; color: var(--vw-muted); }
.vw-card-goals { font-size: 12px; font-weight: 700; color: var(--vw-accent); }
.vw-place[aria-pressed="true"] .vw-card-facts, .vw-place[aria-pressed="true"] .vw-card-goals,
.vw-place[aria-pressed="true"] .vw-card-icons span { color: #fff !important; }
.vw-locked { opacity: .6; }
.vw-place[aria-pressed="true"] .vw-route-dot { background: #fff; }
.vw-view { position: relative; overflow: hidden; height: min(68vh, 640px); min-height: 280px; border-radius: 10px;
  background: #1b1b1b; touch-action: none; user-select: none; -webkit-user-select: none; cursor: grab; outline: none; }
.vw-view:focus-visible { box-shadow: 0 0 0 3px var(--vw-accent); }
.vw-view.vw-dragging { cursor: grabbing; }
.vw-stage { position: absolute; left: 0; top: 0; transform-origin: 0 0; will-change: transform; }
.vw-stage canvas { display: block; image-rendering: pixelated; image-rendering: crisp-edges; }
.vw-over { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
.vw-pins { position: absolute; inset: 0; pointer-events: none; }
.vw-pin { position: absolute; left: 0; top: 0; pointer-events: auto; display: grid; place-items: center;
  width: 28px; height: 28px; margin: -14px 0 0 -14px; padding: 0; border-radius: 50%; border: 2.5px solid currentColor;
  background: #fff; color: #333; font: 700 13px/1 system-ui, sans-serif; cursor: pointer;
  box-shadow: 0 1px 3px rgba(0,0,0,.45); }
.vw-pin:focus-visible { outline: 3px solid #fff; outline-offset: 2px; }
.vw-pin svg { width: 16px; height: 16px; }
.vw-pin { z-index: 1; }
.vw-pin.vw-place-pin, .vw-pin.vw-exit { z-index: 2; }
.vw-pin.vw-far { opacity: .62; }
.vw-pin.vw-stop { z-index: 3; }
.vw-pin.vw-stop { background: ${ROUTE}; border-color: #fff; color: #fff; min-width: 28px; width: auto; padding: 0 6px;
  border-radius: 14px; }
.vw-pin.vw-stop.vw-wide { margin-left: 0; transform: translateX(-50%); }
.vw-pin .vw-more { position: absolute; right: -6px; top: -6px; min-width: 16px; height: 16px; padding: 0 3px;
  border-radius: 8px; background: #222; color: #fff; font-size: 10px; line-height: 16px; }
.vw-pin.vw-person { border-radius: 50%; background: #F4ECD8; }
.vw-pin.vw-person.vw-in { opacity: .8; border-style: dashed; }
.vw-pin.vw-exit { width: auto; height: 26px; margin: -13px 0 0 0; padding: 0 9px 0 7px; border-radius: 13px;
  border: 2px solid #fff; background: rgba(20,20,20,.72); color: #fff; font: 600 12px/1 system-ui, sans-serif;
  gap: 4px; display: inline-flex; align-items: center; white-space: nowrap; transform: translateX(-50%); }
.vw-pin.vw-exit.vw-onroute { background: ${ROUTE}; }
.vw-sprite { display: block; image-rendering: pixelated; background-repeat: no-repeat; }
.vw-zoom { position: absolute; z-index: 6; right: 8px; bottom: 8px; display: flex; flex-direction: column; gap: 6px; }
.vw-zoom button { width: 40px; height: 40px; border-radius: 8px; border: 1px solid rgba(0,0,0,.25);
  background: rgba(255,255,255,.94); color: #222; font: 700 20px/1 system-ui, sans-serif; cursor: pointer; }
.vw-zoom button.vw-fit { font-size: 12px; }
.vw-status { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); color: #eee;
  font-size: 15px; text-align: center; padding: 12px; max-width: 90%; pointer-events: none; }
.vw-pop { position: absolute; z-index: 5; width: min(320px, calc(100% - 72px)); max-height: calc(100% - 16px);
  overflow: auto; background: var(--vw-panel); color: var(--vw-ink); border: 1px solid var(--vw-line);
  border-radius: 10px; box-shadow: 0 6px 24px rgba(0,0,0,.35); padding: 10px 12px; cursor: auto;
  user-select: text; -webkit-user-select: text; touch-action: pan-y; }
.vw-pop[hidden] { display: none; }
.vw-pop .vw-close { position: absolute; right: 4px; top: 4px; width: 32px; height: 32px; border: 0;
  background: transparent; font-size: 20px; line-height: 1; color: var(--vw-muted); cursor: pointer; border-radius: 6px; }
.vw-pop .vw-close:focus-visible { outline: 2px solid var(--vw-accent); }
.vw-entry { display: grid; grid-template-columns: 32px 1fr; gap: 2px 10px; padding: 6px 0; }
.vw-entry + .vw-entry { border-top: 1px solid var(--vw-line); }
.vw-entry .vw-ico { grid-row: span 3; width: 32px; height: 32px; display: grid; place-items: center;
  border-radius: 8px; background: var(--vw-bg); }
.vw-entry .vw-ico svg { width: 20px; height: 20px; }
.vw-entry h3 { margin: 0; padding-right: 26px; font-size: 15px; line-height: 1.3; }
.vw-entry .vw-time { font-size: 13px; font-weight: 700; color: var(--vw-muted); }
.vw-entry p { margin: 0; font-size: 14px; line-height: 1.4; color: var(--vw-ink); }
.vw-tag { display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
  margin-right: 6px; }
.vw-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding: 8px 2px 0; font-size: 14px; }
.vw-tools label { display: inline-flex; align-items: center; gap: 6px; min-height: 32px; cursor: pointer; }
.vw-tools input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--vw-accent); }
.vw-swatch { width: 12px; height: 12px; border-radius: 50%; }
.vw-clock { display: inline-flex; align-items: center; gap: 8px; flex: 1 1 220px; min-width: 0; }
.vw-clock input { flex: 1; min-width: 0; accent-color: #9C36B5; }
.vw-clock output { font-variant-numeric: tabular-nums; min-width: 68px; font-weight: 700; }
.vw-clock[hidden] { display: none; }
.vw-stops { margin: 10px 0 0; padding: 0; list-style: none; display: grid; gap: 4px; }
.vw-stops button { width: 100%; display: grid; grid-template-columns: 30px 72px 1fr; gap: 8px; align-items: center;
  text-align: left; padding: 6px 8px; border: 1px solid var(--vw-line); border-radius: 8px; background: var(--vw-panel);
  color: var(--vw-ink); font: inherit; font-size: 14px; cursor: pointer; }
.vw-stops .vw-n { display: grid; place-items: center; height: 24px; border-radius: 12px; background: ${ROUTE};
  color: #fff; font-weight: 700; font-size: 13px; }
.vw-stops .vw-t { color: var(--vw-muted); font-variant-numeric: tabular-nums; font-size: 13px; }
.vw-stops .vw-what { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vw-sub { font-size: 13px; color: var(--vw-muted); margin: 0 2px 6px; }
@media (max-width: 480px) {
  .vw-view { height: 62vh; border-radius: 8px; }
  .vw-stops button { grid-template-columns: 28px 64px 1fr; }
}`;

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

  function glyph(kind) {
    const svg = GLYPHS[kind] || GLYPHS.shop;
    return el("span", { "aria-hidden": "true", html: `<svg viewBox="0 0 24 24">${svg}</svg>` });
  }

  function sprite(icon, size) {
    const k = size / Math.max(icon.w, icon.h);
    return el("span", {
      class: "vw-sprite", "aria-hidden": "true",
      style: `width:${icon.w * k}px;height:${icon.h * k}px;background-image:url("${icon.url}");` +
        `background-size:${icon.sw * k}px ${icon.sh * k}px;background-position:-${icon.x * k}px -${icon.y * k}px`,
    });
  }

  function clockLabel(minutes) {
    const h = Math.floor(minutes / 60) % 24, m = minutes % 60;
    return `${(h % 12) || 12}:${String(m).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
  }

  function injectCSS() {
    if (document.getElementById("valley-world-css")) return;
    document.head.append(el("style", { id: "valley-world-css", text: STYLE }));
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

  function mount(root, opts = {}) {
    if (!window.ValleyMap) throw new Error("ValleyWorld needs static/map.js (ValleyMap) loaded first");
    injectCSS();
    const url = opts.url || "/api/world";
    let params = { ...(opts.params || {}) };
    const state = {
      data: null, loc: null, map: null, z: 1, px: 0, py: 0, layers: {}, clock: 600, open: null,
      canvases: new Map(), drawing: null, dead: false,
    };
    for (const l of LAYERS) state.layers[l.id] = l.on;

    root.classList.add("vw");
    root.replaceChildren();
    const sub = el("p", { class: "vw-sub" });
    const places = el("div", { class: "vw-places", role: "group", "aria-label": "Maps" });
    const stage = el("div", { class: "vw-stage" });
    const over = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    over.setAttribute("class", "vw-over");
    over.setAttribute("aria-hidden", "true");
    const pins = el("div", { class: "vw-pins" });
    const status = el("div", { class: "vw-status", role: "status", text: "Loading today…" });
    const pop = el("div", { class: "vw-pop", role: "dialog", hidden: true, "aria-modal": "false" });
    const zoomIn = el("button", { type: "button", "aria-label": "Zoom in", text: "+" });
    const zoomOut = el("button", { type: "button", "aria-label": "Zoom out", text: "−" });
    const zoomFit = el("button", { type: "button", class: "vw-fit", "aria-label": "Show the whole map", text: "All" });
    const view = el("div", {
      class: "vw-view", tabindex: "0", role: "application",
      "aria-label": "Map. Drag or use the arrow keys to move, plus and minus to zoom.",
    }, stage, over, pins, el("div", { class: "vw-zoom" }, zoomIn, zoomOut, zoomFit), status, pop);
    const tools = el("div", { class: "vw-tools" });
    const clockInput = el("input", { type: "range", min: "360", max: "1560", step: "10", value: "360",
      "aria-label": "Time of day for the villagers" });
    const clockOut = el("output", { text: clockLabel(360) });
    const clock = el("label", { class: "vw-clock", hidden: true }, el("span", { text: "Villagers at" }), clockInput,
      clockOut);
    for (const l of LAYERS) {
      const box = el("input", { type: "checkbox", checked: l.on });
      box.addEventListener("change", () => {
        state.layers[l.id] = box.checked;
        clock.hidden = !state.layers.villagers;
        closePop();
        drawOverlay();
      });
      const color = l.id === "route" ? ROUTE : l.id === "places" ? KINDS.forage.color
        : l.id === "villagers" ? KINDS.villager.color : KINDS.shop.color;
      tools.append(el("label", {}, box, el("span", { class: "vw-swatch", style: `background:${color}` }),
        el("span", { text: l.label })));
    }
    tools.append(clock);
    const stopList = el("ol", { class: "vw-stops", "aria-label": "Today's stops" });
    root.append(sub, places, view, tools, stopList);

    clockInput.addEventListener("input", () => {
      state.clock = Number(clockInput.value);
      clockOut.textContent = clockLabel(state.clock);
      closePop();
      drawOverlay();
    });

    // --- view transform --------------------------------------------------------------------------------------
    function size() { return { w: view.clientWidth, h: view.clientHeight }; }
    function toScreen(tx, ty) { return [state.px + tx * TILE * state.z, state.py + ty * TILE * state.z]; }
    function clampPan() {
      if (!state.map) return;
      const { w, h } = size();
      const mw = state.map.width * TILE * state.z, mh = state.map.height * TILE * state.z;
      const keep = 60;  // never lose the map entirely
      state.px = mw <= w ? (w - mw) / 2 : Math.min(keep, Math.max(w - mw - keep, state.px));
      state.py = mh <= h ? (h - mh) / 2 : Math.min(keep, Math.max(h - mh - keep, state.py));
    }
    function fitZ() {
      if (!state.map) return 1;
      const { w, h } = size();
      return Math.min(w / (state.map.width * TILE), h / (state.map.height * TILE));
    }
    function apply() {
      clampPan();
      stage.style.transform = `translate(${state.px}px, ${state.py}px) scale(${state.z})`;
      drawOverlay();
    }
    function zoomAt(f, sx, sy) {
      const z = Math.min(MAX_Z, Math.max(Math.min(MIN_Z, fitZ()), state.z * f));
      const k = z / state.z;
      state.px = sx - (sx - state.px) * k;
      state.py = sy - (sy - state.py) * k;
      state.z = z;
      apply();
    }
    function centreOn(tx, ty, z) {
      const { w, h } = size();
      if (z) state.z = Math.min(MAX_Z, Math.max(fitZ(), z));
      state.px = w / 2 - (tx + 0.5) * TILE * state.z;
      state.py = h / 2 - (ty + 0.5) * TILE * state.z;
      apply();
    }
    function startZ() {
      const { w } = size();
      return Math.max(fitZ(), Math.min(3, Math.max(1.25, w / (36 * TILE))));
    }

    zoomIn.addEventListener("click", () => { const { w, h } = size(); zoomAt(1.5, w / 2, h / 2); });
    zoomOut.addEventListener("click", () => { const { w, h } = size(); zoomAt(1 / 1.5, w / 2, h / 2); });
    zoomFit.addEventListener("click", () => { state.z = fitZ(); apply(); });

    view.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = view.getBoundingClientRect();
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      zoomAt(Math.exp(-dy * 0.0018), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });
    view.addEventListener("scroll", () => { view.scrollLeft = 0; view.scrollTop = 0; });

    // Dragging and pinching: a pointer only counts as a drag after it moves a few pixels, so a tap stays a click.
    const pointers = new Map();
    let gesture = null, dragged = false;
    view.addEventListener("pointerdown", (e) => {
      if (pop.contains(e.target) || e.target.closest(".vw-zoom")) { if (!pointers.size) dragged = false; return; }
      if (e.pointerType === "mouse" && e.button !== 0) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      dragged = false;
      gesture = startGesture();
    });
    function startGesture() {
      const pts = [...pointers.values()];
      if (pts.length === 1) return { kind: "pan", x: pts[0].x, y: pts[0].y, px: state.px, py: state.py };
      const [a, b] = pts;
      const r = view.getBoundingClientRect();
      return { kind: "pinch", d: Math.hypot(a.x - b.x, a.y - b.y) || 1, z: state.z, px: state.px, py: state.py,
        mx: (a.x + b.x) / 2 - r.left, my: (a.y + b.y) / 2 - r.top };
    }
    view.addEventListener("pointermove", (e) => {
      if (!pointers.has(e.pointerId)) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (!gesture) return;
      const pts = [...pointers.values()];
      if (gesture.kind === "pan") {
        const dx = pts[0].x - gesture.x, dy = pts[0].y - gesture.y;
        if (!dragged && Math.hypot(dx, dy) < 5) return;
        if (!dragged) {
          dragged = true;
          view.classList.add("vw-dragging");
          try { view.setPointerCapture(e.pointerId); } catch (_) { /* already gone */ }
        }
        state.px = gesture.px + dx;
        state.py = gesture.py + dy;
        apply();
      } else if (pts.length >= 2) {
        dragged = true;
        const [a, b] = pts;
        const r = view.getBoundingClientRect();
        const z = Math.min(MAX_Z, Math.max(Math.min(MIN_Z, fitZ()), gesture.z * Math.hypot(a.x - b.x, a.y - b.y) / gesture.d));
        const mx = (a.x + b.x) / 2 - r.left, my = (a.y + b.y) / 2 - r.top;
        const k = z / gesture.z;
        state.z = z;
        state.px = mx - (gesture.mx - gesture.px) * k;
        state.py = my - (gesture.my - gesture.py) * k;
        apply();
      }
    });
    function endPointer(e) {
      if (!pointers.has(e.pointerId)) return;
      pointers.delete(e.pointerId);
      view.classList.remove("vw-dragging");
      gesture = pointers.size ? startGesture() : null;
      if (!pointers.size) setTimeout(() => { if (!pointers.size) dragged = false; }, 0);  // after its click
    }
    view.addEventListener("pointerup", endPointer);
    view.addEventListener("pointercancel", endPointer);
    view.addEventListener("click", (e) => {
      if (dragged) { e.stopPropagation(); e.preventDefault(); dragged = false; return; }
      if (!pop.contains(e.target) && !e.target.closest(".vw-pin")) closePop();
    }, true);
    view.addEventListener("keydown", (e) => {
      if (e.target !== view) return;
      const step = 64;
      const { w, h } = size();
      const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
      if (moves[e.key]) {
        state.px += moves[e.key][0]; state.py += moves[e.key][1]; apply(); e.preventDefault();
      } else if (e.key === "+" || e.key === "=") { zoomAt(1.5, w / 2, h / 2); e.preventDefault(); }
      else if (e.key === "-" || e.key === "_") { zoomAt(1 / 1.5, w / 2, h / 2); e.preventDefault(); }
    });
    const onDocDown = (e) => { if (state.open && !root.contains(e.target)) closePop(); };
    const onKey = (e) => { if (e.key === "Escape" && state.open) { const back = state.open.pin; closePop(); back?.focus(); } };
    document.addEventListener("pointerdown", onDocDown);
    document.addEventListener("keydown", onKey);
    const resize = new ResizeObserver(() => { if (state.map) apply(); });
    resize.observe(view);

    // --- the overlay: route, exits, places --------------------------------------------------------------------
    function svg(tag, attrs) {
      const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      return n;
    }

    function routeHere() {
      const out = [];
      if (!state.data) return out;
      for (const leg of state.data.route) {
        leg.lines.forEach((ln, i) => {
          if (ln.loc === state.loc) out.push({ leg, ln, next: leg.lines[i + 1], prev: leg.lines[i - 1] });
        });
      }
      return out;
    }

    function chevrons(points, g) {
      // Small arrowheads every ~90 screen pixels along a line, pointing the way you walk.
      let carry = 45;
      for (let i = 1; i < points.length; i++) {
        const [ax, ay] = points[i - 1], [bx, by] = points[i];
        const len = Math.hypot(bx - ax, by - ay);
        if (!len) continue;
        const ang = Math.atan2(by - ay, bx - ax) * 180 / Math.PI;
        let d = carry;
        while (d < len) {
          const x = ax + (bx - ax) * d / len, y = ay + (by - ay) * d / len;
          g.append(svg("path", { d: "M-4,-5 L3,0 L-4,5", fill: "none", stroke: "#fff", "stroke-width": "2.2",
            "stroke-linecap": "round", "stroke-linejoin": "round", transform: `translate(${x},${y}) rotate(${ang})` }));
          d += 90;
        }
        carry = d - len;
      }
    }

    function drawOverlay() {
      over.replaceChildren();
      const keepFocus = document.activeElement && pins.contains(document.activeElement)
        ? document.activeElement.dataset.key : null;
      pins.replaceChildren();
      if (!state.data || !state.map) return;
      const half = TILE * state.z / 2;
      const centre = (x, y) => { const [sx, sy] = toScreen(x, y); return [sx + half, sy + half]; };
      const { w: vw, h: vh } = size();
      const onScreen = (sx, sy, m = 40) => sx > -m && sy > -m && sx < vw + m && sy < vh + m;

      // Outlines for places that cover more than a tile (the giant-crop square, the meteorite).
      for (const p of state.data.pois) {
        if (p.loc !== state.loc || !p.w || !state.layers[p.layer]) continue;
        const [sx, sy] = toScreen(p.x, p.y);
        over.append(svg("rect", { x: sx, y: sy, width: p.w * TILE * state.z, height: p.h * TILE * state.z,
          fill: "rgba(255,255,255,.12)", stroke: KINDS[p.kind]?.color || "#fff", "stroke-width": 3,
          "stroke-dasharray": "6 4" }));
      }

      const exitsShown = new Set();
      if (state.layers.route) {
        const g = svg("g", {});
        for (const { leg, ln, next } of routeHere()) {
          const pts = ln.points.map(([x, y]) => centre(x, y));
          const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
          const dash = leg.home ? "8 7" : null;
          g.append(svg("path", { d, fill: "none", stroke: "#fff", "stroke-width": 8, "stroke-linecap": "round",
            "stroke-linejoin": "round", opacity: 0.9 }));
          const line = svg("path", { d, fill: "none", stroke: ROUTE, "stroke-width": 4.5, "stroke-linecap": "round",
            "stroke-linejoin": "round" });
          if (dash) line.setAttribute("stroke-dasharray", dash);
          g.append(line);
          chevrons(pts, g);
          if (next && next.loc !== state.loc) {
            const [x, y] = ln.points[ln.points.length - 1];
            const key = `${next.loc}`;
            if (!exitsShown.has(key)) {
              exitsShown.add(key);
              addExit(x, y, next.loc, next.points[0], true, leg);
            }
          }
        }
        over.append(g);
      }
      for (const ex of state.data.exits || []) {
        if (ex.loc !== state.loc || exitsShown.has(ex.to)) continue;
        addExit(ex.x, ex.y, ex.to, [ex.tx, ex.ty], false);
      }

      // Places, one button per tile.
      const groups = new Map();
      const add = (key, x, y, entry) => {
        if (!groups.has(key)) groups.set(key, { x, y, entries: [] });
        groups.get(key).entries.push(entry);
      };
      for (const p of state.data.pois) {
        if (p.loc !== state.loc || !state.layers[p.layer]) continue;
        add(`${p.x},${p.y}`, p.x, p.y, p);
      }
      if (state.layers.villagers) {
        for (const v of state.data.villagers || []) {
          const at = whereAt(v, state.clock);
          if (!at || at.loc !== state.loc) continue;
          add(`${at.x},${at.y}`, at.x, at.y, { kind: "villager", id: `villager:${v.id}`, title: v.name, icon: v.icon,
            outdoors: at.outdoors, time: `from ${at.time}`, why: villagerWhy(v, at) });
        }
      }
      for (const [key, grp] of groups) {
        const [sx, sy] = centre(grp.x, grp.y);
        if (!onScreen(sx, sy)) continue;
        const pin = makePin(grp);
        pin.dataset.key = key;
        pin.style.left = `${sx}px`;
        pin.style.top = `${sy}px`;
        pins.append(pin);
        if (state.open && state.open.key === key) state.open.pin = pin;
      }
      if (keepFocus) pins.querySelector(`[data-key="${CSS.escape(keepFocus)}"]`)?.focus({ preventScroll: true });
      if (state.open) placePop();

      function addExit(x, y, to, arrive, onRoute, leg) {
        const [sx, sy] = centre(x, y);
        const W = state.map.width, H = state.map.height;
        const arrow = x <= 1 ? "←" : x >= W - 2 ? "→" : y <= 1 ? "↑" : "↓";
        const name = state.data.locations.find((l) => l.id === to)?.name || to;
        const bx = Math.min(vw - 60, Math.max(60, sx)), by = Math.min(vh - 18, Math.max(18, sy));
        const btn = el("button", {
          type: "button", class: `vw-pin vw-exit${onRoute ? " vw-onroute" : ""}`,
          "aria-label": `${onRoute ? "The route goes on to" : "Go to"} ${name}`,
          title: onRoute ? `The route goes on to ${name}` : name,
          style: `left:${bx}px;top:${by}px`,
          onclick: () => { show(to, arrive); },
        }, el("span", { "aria-hidden": "true", text: arrow }), el("span", { text: name }));
        btn.dataset.key = `exit:${to}`;
        if (onScreen(sx, sy, 0) || onRoute) pins.append(btn);
        void leg;
      }
    }

    function whereAt(v, t) {
      let at = null;
      for (const s of v.stops) if (s.t <= t) at = s;
      return at || v.stops[0];
    }

    function villagerWhy(v, at) {
      const i = v.stops.indexOf(at);
      const next = v.stops[i + 1];
      const here = at.where + (next ? ` until about ${next.time}, then ${next.where}` : " for the rest of the day");
      return (v.unsure ? "Probably (a rainy-day coin flip): " : "") + here[0].toUpperCase() + here.slice(1) + ".";
    }

    function makePin(grp) {
      const es = grp.entries;
      const stops = es.filter((e) => e.kind === "stop");
      const rank = (e) => (e.kind === "stop" ? 0 : e.kind === "villager" ? 2 : e.kind === "shop" ? 3 : 1);
      const first = [...es].sort((a, b) => rank(a) - rank(b))[0];
      const label = es.map((e) => (e.kind === "stop" ? `Stop ${e.n}: ` : "") + e.title).join("; ");
      let pin;
      if (stops.length) {
        const nums = stops.map((s) => s.n).join("·");
        pin = el("button", { type: "button", class: `vw-pin vw-stop${nums.length > 2 ? " vw-wide" : ""}`,
          "aria-label": label, text: nums });
      } else if (first.kind === "villager") {
        pin = el("button", { type: "button", class: `vw-pin vw-person${first.outdoors ? "" : " vw-in"}`,
          "aria-label": label, style: `color:${KINDS.villager.color}` },
          first.icon ? sprite(first.icon, 20) : glyph("villager"));
      } else {
        const color = KINDS[first.kind]?.color || "#333";
        const far = es.every((e) => e.reach === false);
        pin = el("button", { type: "button", class: `vw-pin${first.kind === "shop" ? "" : " vw-place-pin"}${far ? " vw-far" : ""}`,
          "aria-label": label, style: `color:${color}` },
          first.icon ? sprite(first.icon, 18) : glyph(first.kind));
      }
      const extra = es.length - (stops.length || 1);
      if (extra > 0) pin.append(el("span", { class: "vw-more", "aria-hidden": "true", text: `+${extra}` }));
      pin.setAttribute("aria-haspopup", "dialog");
      pin.addEventListener("click", (e) => {
        e.stopPropagation();
        const key = pin.dataset.key;
        if (state.open && state.open.key === key) { closePop(); return; }
        openPop(key, grp, pin);
      });
      pin.addEventListener("focus", () => {  // tabbing to a place off the edge brings it into view
        const r = pin.getBoundingClientRect(), v = view.getBoundingClientRect();
        if (r.left < v.left || r.right > v.right || r.top < v.top || r.bottom > v.bottom) centreOn(grp.x, grp.y);
      });
      return pin;
    }

    function openPop(key, grp, pin) {
      // Stops first, in order, then the rest.
      const order = (e) => (e.kind === "stop" ? e.n : e.kind === "villager" ? 2e3 : e.kind === "shop" ? 3e3 : 1e3);
      const es = [...grp.entries].sort((a, b) => order(a) - order(b));
      const id = `vw-pop-title-${Math.random().toString(36).slice(2, 8)}`;
      const close = el("button", { type: "button", class: "vw-close", "aria-label": "Close", text: "×",
        onclick: () => { closePop(); pin.focus(); } });
      pop.replaceChildren(close, ...es.map((e, i) => {
        const kind = KINDS[e.kind] || KINDS.shop;
        const ico = el("span", { class: "vw-ico", style: `color:${kind.color}` },
          e.icon ? sprite(e.icon, 24) : e.kind === "stop"
            ? el("span", { class: "vw-n", style: `color:${ROUTE};font-weight:700`, text: String(e.n) }) : glyph(e.kind));
        const tag = e.kind === "stop" ? `Stop ${e.n}` : e.title.toLowerCase().startsWith(kind.label.toLowerCase()) ? "" : kind.label;
        return el("div", { class: "vw-entry" }, ico,
          el("h3", { id: i === 0 ? id : null }, tag ? el("span", { class: "vw-tag", style: `color:${kind.color}`, text: tag }) : null,
            document.createTextNode(e.title)),
          e.time ? el("div", { class: "vw-time", text: e.time }) : null,
          e.why ? el("p", { text: e.why[0].toUpperCase() + e.why.slice(1) }) : null);
      }));
      pop.setAttribute("aria-labelledby", id);
      pop.hidden = false;
      pin.setAttribute("aria-expanded", "true");
      state.open = { key, pin, grp };
      placePop();
    }

    function placePop() {
      const { w, h } = size();
      const half = TILE * state.z / 2;
      const [sx0, sy0] = toScreen(state.open.grp.x, state.open.grp.y);
      const sx = sx0 + half, sy = sy0 + half;
      if (sx < 0 || sy < 0 || sx > w || sy > h) { closePop(); return; }  // its place has left the view
      const pw = pop.offsetWidth, ph = pop.offsetHeight;
      const right = w - pw - 56 >= 8 ? w - pw - 56 : w - pw - 8;  // clear of the zoom buttons when there's room
      let left = Math.min(right, Math.max(8, sx - pw / 2));
      let top = sy + 22;
      if (top + ph > h - 8) top = sy - 22 - ph;
      if (top < 8) top = Math.max(8, h - ph - 8);
      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    }

    function closePop() {
      if (!state.open) return;
      state.open.pin?.setAttribute("aria-expanded", "false");
      state.open = null;
      pop.hidden = true;
      pop.replaceChildren();
    }

    // --- maps ------------------------------------------------------------------------------------------------
    async function mapCanvas(loc) {
      if (!state.canvases.has(loc)) {
        const canvas = document.createElement("canvas");
        state.canvases.set(loc, ValleyMap.drawWhole(canvas, loc, { scale: 1 }).then((info) => ({ canvas, info }))
          .catch((e) => { state.canvases.delete(loc); throw e; }));
      }
      return state.canvases.get(loc);
    }

    async function show(loc, at) {
      if (!state.data) return;
      closePop();
      state.loc = loc;
      renderPlaces();
      status.textContent = "Drawing the map…";
      status.hidden = false;
      const ticket = (state.drawing = {});
      let got;
      try {
        got = await mapCanvas(loc);
      } catch (e) {
        if (state.drawing !== ticket) return;
        stage.replaceChildren();
        state.map = null;
        over.replaceChildren(); pins.replaceChildren();
        status.textContent = `Couldn't draw ${placeName(loc)}: ${e.message}`;
        return;
      }
      if (state.drawing !== ticket || state.dead) return;
      status.hidden = true;
      stage.replaceChildren(got.canvas);
      state.map = got.info;
      const target = at || firstHere(loc);
      centreOn(target[0], target[1], startZ());
    }

    function firstHere(loc) {
      const d = state.data;
      const stop = d.pois.find((p) => p.loc === loc && p.kind === "stop");
      if (stop) return [stop.x, stop.y];
      if (d.start.loc === loc) return [d.start.x, d.start.y];
      const leg = d.route.flatMap((l) => l.lines).find((ln) => ln.loc === loc);
      if (leg) return leg.points[0];
      const any = d.pois.find((p) => p.loc === loc && p.layer === "places");
      if (any) return [any.x, any.y];
      return [state.map.width / 2, state.map.height / 2];
    }

    function placeName(loc) {
      return state.data?.locations.find((l) => l.id === loc)?.name || loc;
    }

    function renderPlaces() {
      const onRoute = new Set(state.data.route.flatMap((l) => l.lines.map((ln) => ln.loc)));
      places.replaceChildren(...state.data.locations.map((l) => {
        // a card a place: is it worth the walk today? goals it moves on, gold lying about, what's happening there
        const goals = l.goals || [], icons = l.icons || [];
        const facts = [l.stops && l.stops.length ? `Stop${l.stops.length > 1 ? "s" : ""} ${l.stops.join(", ")}` : "",
          goals.length ? `${goals.length} goal${goals.length > 1 ? "s" : ""}` : "", l.gold ? `${l.gold.toLocaleString()}g to pick up` : ""]
          .filter(Boolean).join(" · ");
        const b = el("button", { type: "button", class: `vw-place vw-card${l.locked ? " vw-locked" : ""}`,
          "aria-pressed": String(l.id === state.loc), onclick: () => show(l.id),
          title: [goals.length ? `Goals: ${goals.join(", ")}` : "", l.locked ? `Needs ${l.locked}` : ""].filter(Boolean).join("\n") },
          el("span", { class: "vw-card-head" },
            onRoute.has(l.id) ? el("span", { class: "vw-route-dot", title: "On today's route" }) : null,
            el("strong", { text: l.name })),
          el("span", { class: "vw-card-facts" },
            icons.length ? el("span", { class: "vw-card-icons" }, ...icons.map((k) => {
              const g = glyph(k); g.style.color = (KINDS[k] || {}).color || "currentColor"; g.title = (KINDS[k] || {}).label || k; return g;
            })) : null,
            el("span", { text: l.locked ? `Needs ${l.locked}` : facts || "Nothing special today" })),
          goals.length && !l.locked ? el("span", { class: "vw-card-goals", text: goals.join(" · ") }) : null);
        return b;
      }));
      const current = places.querySelector('[aria-pressed="true"]');
      if (current) {  // keep the chosen map's chip in sight without scrolling the page
        const r = current.offsetLeft - places.clientWidth / 2 + current.offsetWidth / 2;
        places.scrollTo({ left: Math.max(0, r) });
      }
    }

    function renderStops() {
      const stops = state.data.pois.filter((p) => p.kind === "stop");
      stopList.replaceChildren(...stops.map((s) => el("li", {}, el("button", {
        type: "button", onclick: () => focusPoi(s),
        "aria-label": `Stop ${s.n}, ${s.time}, ${s.title}, ${placeName(s.loc)}`,
      }, el("span", { class: "vw-n", text: String(s.n) }), el("span", { class: "vw-t", text: s.time || "" }),
      el("span", { class: "vw-what", text: `${s.title} · ${placeName(s.loc)}` })))));
    }

    async function focusPoi(p) {
      if (state.loc !== p.loc || !state.map) await show(p.loc, [p.x, p.y]);
      else centreOn(p.x, p.y, Math.max(state.z, startZ()));
      const key = `${p.x},${p.y}`;
      const pin = pins.querySelector(`[data-key="${key}"]`);
      if (pin) { pin.click(); view.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
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
      const now = params.time ? Math.floor(params.time / 100) * 60 + params.time % 100 : 360;
      state.clock = Math.min(1560, Math.max(360, now));
      clockInput.value = String(state.clock);
      clockOut.textContent = clockLabel(state.clock);
      sub.textContent = [data.date, data.weather, data.start?.time ? `plan starts ${data.start.time}` : ""]
        .filter(Boolean).join(" · ");
      renderStops();
      await show(state.loc && data.locations.some((l) => l.id === state.loc) ? state.loc : data.focus);
    }

    const ready = load().catch((e) => {
      status.hidden = false;
      status.textContent = `Couldn't load today's map: ${e.message}`;
    });

    return {
      ready,
      show: (loc, at) => show(loc, at),
      reload(next) {
        if (next) params = { ...params, ...next };
        state.canvases.clear();
        return load();
      },
      destroy() {
        state.dead = true;
        document.removeEventListener("pointerdown", onDocDown);
        document.removeEventListener("keydown", onKey);
        resize.disconnect();
        root.replaceChildren();
        root.classList.remove("vw");
      },
    };
  }

  window.ValleyWorld = { mount };
})();
