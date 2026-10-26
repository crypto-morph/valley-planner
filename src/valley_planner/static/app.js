"use strict";
// Valley Planner: each tab fetches its view from the local server and draws it.

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const get = async (url) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const unsure = (sure) => (sure === false ? ' <span class="unsure" title="depends on things the save can\'t tell yet">(maybe)</span>' : "");

const views = {
  async today() {
    const [hours, cal] = await Promise.all([get("/api/hours"), get("/api/calendar?days=14")]);
    $("#hours").innerHTML = `<p class="sub">${esc(hours.date)}</p><ul class="list">` + hours.shops.map((s) =>
      `<li><span>${esc(s.shop)}</span><span>${s.open.length ? esc(s.open.join(", ")) : `<span class="unsure">${esc(s.closed)}</span>`}${unsure(s.sure)}</span></li>`
    ).join("") + "</ul>";
    $("#days").innerHTML = cal.days.filter((d) => d.events.length || d.today).map((d) =>
      `<div class="day${d.today ? " today" : ""}"><h3>${esc(d.weekday)} ${esc(d.date)}</h3><ul class="list">` +
      (d.events.length ? d.events.map((e) =>
        `<li><span class="ev-${esc(e.kind)}">${esc(e.label)}${unsure(e.sure)}</span><span class="sub">${esc([e.detail, e.start && e.end ? `${e.start}–${e.end}` : e.start].filter(Boolean).join(" · "))}</span></li>`
      ).join("") : '<li class="sub">Nothing special</li>') + "</ul></div>"
    ).join("");
  },

  async crops() {
    const v = await get("/api/crops");
    const c = v.countdown;
    $("#countdown-head").textContent = `${c.season} ${c.day}: ${c.days_left} days left this season` + (c.agriculturist ? " · Agriculturist" : "");
    $("#countdown").innerHTML = "<tr><th>Crop</th><th>When</th><th>Days</th><th>Seeds</th><th>Each sells</th></tr>" + c.crops.map((r) =>
      `<tr><td>${esc(r.crop)}${r.regrow ? ` <span class="sub">(regrows every ${r.regrow})</span>` : ""}</td>` +
      `<td class="status-${esc(r.status)}">${esc(r.text)}${r.warn ? `<br><span class="sub">${esc(r.warn)}</span>` : ""}</td>` +
      `<td>${r.grow}</td><td>${r.held_seeds ? `${r.held_seeds} held` : ""}${r.seed_price ? `${r.held_seeds ? " · " : ""}${r.seed_price}g at ${esc(r.where)}` : ""}</td>` +
      `<td>${r.sell_each}g</td></tr>`
    ).join("");
    const m = v.mine;
    $("#mine-head").textContent = `${m.total} planted · ${m.ready} ready · ${m.thirsty} not watered today` +
      (m.dies ? ` · ${m.dies} won't ripen before the season ends` : "") +
      (m.compared ? (Object.keys(m.missed).length ? ` · missed water yesterday: ${Object.entries(m.missed).map(([k, n]) => `${n} ${k}`).join(", ")}` : " · nothing missed water yesterday") : "");
    $("#mine").innerHTML = "<tr><th>Crop</th><th>Where</th><th>Status</th><th>Count</th><th>Not watered</th></tr>" + m.rows.map((r) =>
      `<tr><td>${esc(r.crop)}</td><td>${esc(r.location)}</td><td class="status-${esc(r.status)}">${esc(r.status === "growing" || r.status === "dies" ? `ripens ${r.ripens}` : r.status)}${r.status === "dies" ? " (dies first)" : ""}</td>` +
      `<td>${r.count}</td><td>${r.thirsty || ""}</td></tr>`
    ).join("");
  },

  async cart() {
    const v = await get("/api/cart?days=14");
    $("#cart-days").innerHTML = v.days.map((d) =>
      `<div class="day"><h3>${esc(d.date)} <span class="sub">${esc(d.place)}</span></h3><ul class="list">` +
      d.items.map((i) => `<li><span>${esc(i.name)}${i.stock && i.stock > 1 ? ` ×${i.stock}` : ""}${unsure(i.sure)}</span><span>${i.price.toLocaleString()}g</span></li>`).join("") +
      "</ul></div>"
    ).join("") || '<p class="sub">No cart in the next two weeks.</p>';
  },
};

async function searchCart() {
  const q = $("#cart-q").value.trim();
  if (q.length < 3) { $("#cart-hits").innerHTML = ""; return; }
  const v = await get(`/api/cart/search?q=${encodeURIComponent(q)}`);
  $("#cart-hits").innerHTML = v.hits.length
    ? '<ul class="list">' + v.hits.map((h) => `<li><span>${esc(h.date)} · ${esc(h.name)}${unsure(h.sure)}</span><span>${h.price.toLocaleString()}g</span></li>`).join("") + "</ul>"
    : `<p class="sub">Not at the cart in the next two years.</p>`;
}

async function show(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  document.querySelectorAll(".view").forEach((s) => (s.hidden = s.id !== `view-${name}`));
  try {
    await views[name]();
  } catch (e) {
    $(`#view-${name}`).insertAdjacentHTML("afterbegin", `<p class="parch panel">Couldn't load this: ${esc(e.message)}</p>`);
  }
}

async function start() {
  try {
    const m = await get("/api/meta");
    $("#status").textContent = m.save ? `${m.player} · ${m.farm} Farm · ${m.date}` : "No save found";
  } catch (e) {
    $("#status").textContent = e.message;
  }
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  let timer;
  $("#cart-q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(searchCart, 250); });
  show("today");
}

start();
