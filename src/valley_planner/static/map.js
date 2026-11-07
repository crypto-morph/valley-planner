/* Pictures of the game's maps, drawn from the player's own game files (served by /api/map and /api/tex).
 *
 *   ValleyMap.drawArea(canvas, "Farm", {x: 61, y: 21, radius: 8, marks: [{x: 61, y: 21, kind: "cross"}]})
 *   ValleyMap.drawWhole(canvas, "Town", {scale: 1})
 *
 * Options (both): overlay (default true: what the save has there — crops, objects, buildings…), scale (screen
 * pixels per art pixel; drawArea 2, drawWhole 1), season ("spring"… default the save's), marks.
 * drawArea also takes x, y (the centre tile) and radius (tiles each side, default 8); the window is clipped to the
 * map. A mark is {x, y, kind, label?, inside?, color?} (inside: the label sits on the tile, not above it): kind "cross" (a bold X on the tile), "square3" (a 3x3 outline whose
 * top-left tile is x, y), "rect" (with w, h: an outline from x, y), "dot" (a round spot on the tile).
 * Both return a promise of {x0, y0, cols, rows, scale, width, height} (the window drawn, in tiles), so a page can
 * turn a mouse position back into a tile: tile x = x0 + floor(px / (16 * scale)).
 * Plain script: attaches ValleyMap (and drawArea / drawWhole) to window.
 */
(function () {
  "use strict";
  const TILE = 16;
  const json = new Map();
  const images = new Map();
  const tinted = new Map();

  function getJSON(url) {
    if (!json.has(url)) {
      json.set(url, fetch(url).then((r) => {
        if (!r.ok) throw new Error(`${url}: ${r.status}`);
        return r.json();
      }).catch((e) => { json.delete(url); throw e; }));
    }
    return json.get(url);
  }

  function image(url) {
    if (!images.has(url)) {
      images.set(url, new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => { images.delete(url); reject(new Error(`couldn't load ${url}`)); };
        img.src = url;
      }));
    }
    return images.get(url);
  }

  async function load(location, opts) {
    const q = opts.season ? `?season=${encodeURIComponent(opts.season)}` : "";
    const loc = encodeURIComponent(location);
    const [map, scene] = await Promise.all([
      getJSON(`/api/map/${loc}${q}`),
      opts.overlay === false ? null : getJSON(`/api/map/${loc}/sprites${q}`).catch(() => null),
    ]);
    const sheetImgs = await Promise.all(map.sheets.map((s) => (s.url ? image(s.url).catch(() => null) : null)));
    const texImgs = {};
    if (scene) {
      await Promise.all(Object.entries(scene.textures).map(async ([name, url]) => {
        texImgs[name] = await image(url).catch(() => null);
      }));
    }
    return { map, scene, sheetImgs, texImgs };
  }

  function tint(img, src, rgb) {
    const key = `${img.src}|${src.join(",")}|${rgb.join(",")}`;
    if (!tinted.has(key)) {
      const c = document.createElement("canvas");
      c.width = src[2];
      c.height = src[3];
      const g = c.getContext("2d");
      g.drawImage(img, src[0], src[1], src[2], src[3], 0, 0, src[2], src[3]);
      g.globalCompositeOperation = "multiply";
      g.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
      g.fillRect(0, 0, src[2], src[3]);
      g.globalCompositeOperation = "destination-in";
      g.drawImage(img, src[0], src[1], src[2], src[3], 0, 0, src[2], src[3]);
      tinted.set(key, c);
    }
    return tinted.get(key);
  }

  function drawLayer(ctx, data, layer, view, s) {
    const { map, sheetImgs } = data;
    const W = map.width;
    const tiles = layer.tiles;
    if (!tiles) return;
    for (let ty = view.y0; ty < view.y0 + view.rows; ty++) {
      for (let tx = view.x0; tx < view.x0 + view.cols; tx++) {
        const v = tiles[ty * W + tx];
        if (v < 0) continue;
        const sheet = map.sheets[v >> 16];
        const img = sheetImgs[v >> 16];
        if (!sheet || !img) continue;
        const i = v & 0xffff;
        const [tw, th] = sheet.tile;
        ctx.drawImage(img, (i % sheet.columns) * tw, Math.floor(i / sheet.columns) * th, tw, th,
          (tx - view.x0) * TILE * s, (ty - view.y0) * TILE * s, tw * s, th * s);
      }
    }
  }

  function drawSprites(ctx, data, view, s) {
    if (!data.scene) return;
    const left = view.x0 * TILE, top = view.y0 * TILE;
    const right = left + view.cols * TILE, bottom = top + view.rows * TILE;
    for (const sp of data.scene.sprites) {
      const [sx, sy, w, h] = sp.src;
      if (sp.x + w < left || sp.x > right || sp.y + h < top || sp.y > bottom) continue;
      const img = data.texImgs[sp.tex];
      if (!img) continue;
      const dx = Math.round((sp.x - left) * s), dy = Math.round((sp.y - top) * s);
      const source = sp.tint ? tint(img, sp.src, sp.tint) : img;
      const [ox, oy] = sp.tint ? [0, 0] : [sx, sy];
      if (sp.flip) {
        ctx.save();
        ctx.translate(dx + w * s, dy);
        ctx.scale(-1, 1);
        ctx.drawImage(source, ox, oy, w, h, 0, 0, w * s, h * s);
        ctx.restore();
      } else {
        ctx.drawImage(source, ox, oy, w, h, dx, dy, w * s, h * s);
      }
    }
  }

  function drawMarks(ctx, marks, view, s) {
    const T = TILE * s;
    for (const m of marks || []) {
      const px = (m.x - view.x0) * T, py = (m.y - view.y0) * T;
      const color = m.color || "#e8261c";
      const kind = m.kind || "cross";
      ctx.save();
      ctx.lineJoin = "miter";
      if (kind === "cross") {
        const inset = Math.max(2, 2 * s);
        const path = () => {
          ctx.beginPath();
          ctx.moveTo(px + inset, py + inset); ctx.lineTo(px + T - inset, py + T - inset);
          ctx.moveTo(px + T - inset, py + inset); ctx.lineTo(px + inset, py + T - inset);
        };
        path(); ctx.lineCap = "square"; ctx.strokeStyle = "#fff"; ctx.lineWidth = 3 * s + 2; ctx.stroke();
        path(); ctx.strokeStyle = color; ctx.lineWidth = 2 * s; ctx.stroke();
      } else if (kind === "square3" || kind === "rect") {
        const w = (kind === "rect" ? (m.w || 1) : 3) * T, h = (kind === "rect" ? (m.h || 1) : 3) * T;
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2 * s + 2; ctx.strokeRect(px + s, py + s, w - 2 * s, h - 2 * s);
        ctx.strokeStyle = color; ctx.lineWidth = 2 * s; ctx.strokeRect(px + s, py + s, w - 2 * s, h - 2 * s);
      } else if (kind === "dot") {
        ctx.beginPath(); ctx.arc(px + T / 2, py + T / 2, T * 0.28, 0, Math.PI * 2);
        ctx.fillStyle = color; ctx.fill(); ctx.lineWidth = Math.max(1, s); ctx.strokeStyle = "#fff"; ctx.stroke();
      }
      if (m.label) {
        const size = Math.max(10, 6 * s);
        ctx.font = `bold ${size}px system-ui, sans-serif`;
        const tw = ctx.measureText(m.label).width + 8;
        const lx = Math.min(Math.max(0, px + T / 2 - tw / 2), view.cols * T - tw);
        const ly = m.inside ? py + (T - size - 4) / 2 : py - size - 6 >= 0 ? py - size - 6 : py + T + 2;
        ctx.fillStyle = "rgba(43,26,14,0.85)"; ctx.fillRect(lx, ly, tw, size + 4);
        ctx.fillStyle = "#fff"; ctx.textBaseline = "top"; ctx.fillText(m.label, lx + 4, ly + 2);
      }
      ctx.restore();
    }
  }

  function render(canvas, data, view, s, marks) {
    canvas.width = view.cols * TILE * s;
    canvas.height = view.rows * TILE * s;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const layers = data.map.layers;
    for (const l of layers) if (l.group === "Back" || l.group === "Buildings") drawLayer(ctx, data, l, view, s);
    drawSprites(ctx, data, view, s);
    for (const l of layers) if (l.group === "Front" || l.group === "AlwaysFront") drawLayer(ctx, data, l, view, s);
    if (data.scene && data.scene.raining) {  // the game dims the light when it rains outdoors
      ctx.save(); ctx.globalCompositeOperation = "multiply"; ctx.fillStyle = "rgb(150, 160, 190)";
      ctx.fillRect(0, 0, canvas.width, canvas.height); ctx.restore();
    }
    drawMarks(ctx, marks, view, s);
    return { ...view, scale: s, width: data.map.width, height: data.map.height };
  }

  async function drawArea(canvas, location, opts = {}) {
    const data = await load(location, opts);
    const r = opts.radius ?? 8, s = opts.scale ?? 2;
    const W = data.map.width, H = data.map.height;
    const cols = Math.min(W, 2 * r + 1), rows = Math.min(H, 2 * r + 1);
    const x0 = Math.max(0, Math.min(W - cols, Math.round(opts.x ?? W / 2) - r));
    const y0 = Math.max(0, Math.min(H - rows, Math.round(opts.y ?? H / 2) - r));
    return render(canvas, data, { x0, y0, cols, rows }, s, opts.marks);
  }

  async function drawWhole(canvas, location, opts = {}) {
    const data = await load(location, opts);
    const view = { x0: 0, y0: 0, cols: data.map.width, rows: data.map.height };
    return render(canvas, data, view, opts.scale ?? 1, opts.marks);
  }

  window.ValleyMap = { drawArea, drawWhole };
  window.drawArea = drawArea;
  window.drawWhole = drawWhole;
})();
