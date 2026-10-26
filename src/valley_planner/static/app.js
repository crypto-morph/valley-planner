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

const list = (rows) => rows.length ? '<ul class="list">' + rows.join("") + "</ul>" : "";
const li = (left, right = "") => `<li><span>${left}</span><span class="sub">${right}</span></li>`;
const mins = (m, d) => (d ? `${d} day${d > 1 ? "s" : ""}` : m >= 1440 ? `${(m / 1600).toFixed(1)} machine days` : m >= 60 ? `${Math.round(m / 6) / 10} h` : `${m} min`);

function itemCard(c) {
  const parts = [`<h2 class="sign">${esc(c.name)}</h2><p class="sub">${c.held ? `You hold ${c.held}` : "You hold none"}${c.museum ? ` · museum: ${esc(c.museum)}` : ""}${c.help_wanted ? " · a Help Wanted request can ask for it this season" : ""}</p>`];
  if (c.sells.length) parts.push("<h3>Sells for</h3>" + list(c.sells.map((x) => li(x.quality || "normal", `${x.each}g`))));
  if (c.bundles.length) parts.push("<h3>Bundles</h3>" + list(c.bundles.map((b) => li(`${esc(b.bundle)} <span class="sub">(${esc(b.room)})</span>`, `${b.count}${b.quality ? `, quality ${b.quality}+` : ""}${b.open ? "" : " · room not open yet"}`))));
  if (c.grows) parts.push(`<h3>Grows</h3><p>From ${esc(c.grows.seed)} in ${esc(c.grows.seasons.join(", "))}: ${c.grows.days} days${c.grows.regrow ? `, then every ${c.grows.regrow}` : ""}.</p>`);
  if (c.plant) parts.push(`<h3>Plant it</h3><p>Grows ${esc(c.plant.crop)} in ${esc(c.plant.seasons.join(", "))}: ${c.plant.days} days${c.plant.regrow ? `, then every ${c.plant.regrow}` : ""}.</p>`);
  if (c.fish) {
    const f = c.fish;
    parts.push("<h3>Catch it</h3>" + (f.trap ? `<p>Crab pot, ${esc(f.water)} water.</p>` :
      `<p>${f.here_now.length ? `This season: ${esc(f.here_now.join(", "))}` : "Not this season"}${f.other_seasons.length ? ` · also ${esc(f.other_seasons.join(", "))}` : ""}<br>${esc(f.times.join(", "))} · ${esc(f.weather === "both" ? "any weather" : f.weather)}${f.min_level ? ` · fishing level ${f.min_level}` : ""} · difficulty ${f.difficulty}</p>`));
  }
  if (c.shops_today.length || c.shops_other.length) parts.push("<h3>Buy it</h3>" + list([
    ...c.shops_today.map((o) => li(`${esc(o.shop)} today${unsure(o.sure)}`, o.trade ? `${o.trade_amount} ${esc(o.trade)}` : `${o.price}g`)),
    ...c.shops_other.map((o) => li(`${esc(o.shop)} <span class="sub">(${esc(o.when || "other days")})</span>`, o.trade ? `${o.trade_amount} ${esc(o.trade)}` : `${o.price}g`)),
  ]));
  if (c.recipes && c.recipes.length) parts.push("<h3>The recipe</h3>" + list(c.recipes.map((r) => li(`${esc(r.shop)}${r.known ? " · you know it" : ""}`, `${r.price}g`))));
  if (c.cart.length) parts.push("<h3>At the cart</h3>" + list(c.cart.map((x) => li(`${esc(x.date)}${unsure(x.sure)}`, `${x.price.toLocaleString()}g`))));
  if (c.machines.length) parts.push("<h3>Machines</h3>" + list(c.machines.map((m) => li(`${esc(m.machine)}: ${m.uses > 1 ? `${m.uses} → ` : ""}${esc(m.product)}${m.owned ? ` <span class="sub">(you have ${m.owned})</span>` : ""}`, `${m.sells}g · ${mins(m.minutes, m.days)}`))));
  if (c.gifts) parts.push("<h3>Gift tastes</h3>" + list(["love", "like", "dislike", "hate"].filter((t) => c.gifts[t].length).map((t) => li(t, esc(c.gifts[t].join(", "))))));
  return parts.join("");
}

function villagerCard(c) {
  const f = c.met ? `${c.hearts} hearts (${c.points} points) · ${c.gifts_this_week}/2 gifts this week${c.gifted_today ? " · gifted today" : ""}${c.talked_today ? " · talked today" : ""}` : "Not met yet";
  return `<h2 class="sign">${esc(c.name)}</h2><p class="sub">Birthday ${esc(c.birthday)} · ${esc(f)}</p>` +
    "<h3>Loves</h3>" + list(c.loves.map((x) => li(esc(x.name), x.held ? `you hold ${x.held}` : ""))) +
    (c.likes_held.length ? `<h3>Likes that you hold</h3><p>${esc(c.likes_held.join(", "))}</p>` : "") +
    "<h3>Today</h3>" + c.today.map((d) => (c.today.length > 1 ? `<p class="sub">${Math.round(d.chance * 100)}% chance:</p>` : "") +
      (d.stops.length ? list(d.stops.map((st) => li(esc(st.time), esc(st.place)))) : '<p class="sub">Stays home</p>')).join("");
}

function errandCard(name, c) {
  const head = `<h2 class="sign">${esc(c.title)}</h2>`;
  if (name === "gunther") {
    return head + `<p class="sub">${c.donated} donated so far.</p>` +
      (c.take.length ? "<h3>Not donated yet</h3>" + list(c.take.map((x) => li(esc(x.name), `${x.kind}${x.held > 1 ? ` · you hold ${x.held}` : ""}`))) : '<p>Nothing you hold is new to the museum.</p>') +
      (c.next_rewards.length ? "<h3>Closest rewards</h3>" + list(c.next_rewards.map((r) => li(esc(r.reward), `${r.left} more: ${esc(r.needs.join(", "))}`))) : "");
  }
  if (name === "clint") {
    return head + (c.busy ? `<p class="sub">${esc(c.busy)}.</p>` : "") +
      (c.geodes.length ? "<h3>Geodes to crack</h3>" + list(c.geodes.map((g) => li(`${g.held} ${esc(g.name)}`, `${g.cost.toLocaleString()}g`))) : "<p>No geodes to crack.</p>") +
      (c.upgrades.length ? "<h3>Tool upgrades</h3>" + list(c.upgrades.map((u) => li(`${esc(u.tool)}${u.can ? " · <b>you can do this now</b>" : ""}`, `${u.gold.toLocaleString()}g + ${esc(u.bars)} (you hold ${u.have_bars})`))) : "");
  }
  if (name === "cc") {
    return head + (c.rooms.length ? c.rooms.map((r) => `<h3>${esc(r.room)}</h3>` + list(r.items.map((x) => li(`${x.count} ${esc(x.name)}${x.quality ? ` (${esc(x.quality)})` : ""}`, `${esc(x.bundle)}${x.open ? "" : " · room not open yet"}`)))).join("") : "<p>Nothing you hold fills an open slot right now.</p>") +
      (c.vault.length ? "<h3>Vault</h3>" + list(c.vault.map((v) => li(esc(v.bundle), v.gold <= c.money ? "<b>you can pay this now</b>" : `${(v.gold - c.money).toLocaleString()}g to go`))) : "");
  }
  if (name === "grange") {
    return head + `<p><b>${c.score} points: ${esc(c.place)} place</b> (${c.tokens.toLocaleString()} star tokens)` +
      (c.short ? ` · ${c.short} short of first: swap in higher-quality or pricier items, or more kinds` : "") + "</p>" +
      `<p class="sub">${c.kinds.length} kinds (${esc(c.kinds.join(", "))}) · the Fair is ${c.days ? `in ${c.days} days` : "today"}</p>` +
      "<h3>Put these on the display</h3>" + list(c.items.map((x) => li(`${esc(x.name)}${x.quality ? ` (${esc(x.quality)})` : ""}`, `${x.points} points · ${esc(x.kind)} · sells ${x.price}g`))) +
      (c.pack.length ? `<p><b>Pack them first:</b> they're in ${esc(c.pack.join(", "))}, and only your backpack goes to the Fair.</p>` : "");
  }
  return head + (c.birthdays.length ? c.birthdays.map((b) => `<h3>${esc(b.who)} · ${esc(b.date)}</h3>` +
    (b.loved.length ? `<p>Loves: ${esc(b.loved.join(", "))}</p>` : '<p class="sub">You hold nothing they love.</p>') +
    (b.liked.length ? `<p class="sub">Likes: ${esc(b.liked.join(", "))}</p>` : "")).join("") : "<p>No birthdays this week.</p>");
}

async function showErrand(name) {
  const c = await get(`/api/errand/${name}`);
  $("#ask-results").innerHTML = "";
  $("#ask-card-body").innerHTML = errandCard(name, c);
  $("#ask-card").hidden = false;
}

async function showCard(kind, id) {
  const c = await get(`/api/ask/${kind}/${encodeURIComponent(id)}`);
  $("#ask-card-body").innerHTML = kind === "item" ? itemCard(c) : villagerCard(c);
  $("#ask-card").hidden = false;
}

function closeAsk() {
  $("#ask-card").hidden = true;
  $("#ask-results").innerHTML = "";
  $("#ask-q").value = "";
}

async function searchAsk() {
  const q = $("#ask-q").value.trim();
  if (!q) { closeAsk(); return; }
  const v = await get(`/api/ask?q=${encodeURIComponent(q)}`);
  $("#ask-results").innerHTML = v.results.map((r) => `<button type="button" data-kind="${esc(r.kind)}" data-id="${esc(r.id)}">${esc(r.name)}</button>`).join("");
  document.querySelectorAll("#ask-results button").forEach((b) => b.addEventListener("click", () => showCard(b.dataset.kind, b.dataset.id)));
  if (v.results.length === 1) showCard(v.results[0].kind, v.results[0].id);
}

const STATUS_TEXT = { have: "Set aside", ok: "On track", maybe: "Probably", luck: "Luck", blocked: "Unlock first", stuck: "No way yet" };

const views = {
  async morning() {
    const v = await get("/api/morning");
    $("#m-date").textContent = v.date;
    const cc = v.cc;
    $("#m-glance").textContent = `${v.money.toLocaleString()}g · ${v.weather}, tomorrow ${v.tomorrow} · luck ${v.luck > 0.02 ? "good" : v.luck < -0.02 ? "bad" : "neutral"} · Community Center ${cc.bundles_done}/${cc.bundles} bundles, ` +
      `${cc.counts.ok + cc.counts.have} slots on track, ${cc.counts.blocked} need an unlock, ${cc.counts.luck} on luck (by ${cc.deadline})` +
      (cc.gold.gap ? ` · gold: about ${cc.gold.gap.toLocaleString()}g short of the plan` : " · gold: on pace");
    $("#m-first").innerHTML = v.first.length ? list(v.first.map((x) => li(`<b>${esc(x.title)}</b>`, esc(x.text)))) : '<p class="sub">Nothing urgent. A good day to fish, mine or make friends.</p>';
    $("#m-week").innerHTML = list(v.week.map((e) => li(`<span class="ev-${esc(e.kind)}">${esc(e.label)}</span>${unsure(e.sure)}`, esc(e.date))));
  },

  async todo() {
    const v = await get("/api/todo");
    $("#todo-head").textContent = `To do: ${v.date}`;
    const groups = { people: "People", farm: "On the farm", cc: "Community Center", shopping: "Shopping" };
    $("#todo-list").innerHTML = Object.entries(groups).map(([g, label]) => {
      const rows = v.tasks.filter((t) => t.group === g);
      return rows.length ? `<h3>${label}</h3><ul class="list">` + rows.map((t) =>
        `<li><label class="filter"><input type="checkbox" data-task="${esc(t.id)}" ${v.ticks[t.id] ? "checked" : ""}> ${esc(t.title)}</label><span class="sub">${esc(t.why)}</span></li>`
      ).join("") + "</ul>" : "";
    }).join("") || '<p class="sub">Nothing on the list today.</p>';
    document.querySelectorAll("#todo-list input").forEach((box) => box.addEventListener("change", () =>
      fetch(`/api/todo/tick?task=${encodeURIComponent(box.dataset.task)}&done=${box.checked}`, { method: "PUT" })));
    const y = v.yesterday;
    $("#todo-review-box").hidden = !y;
    if (y) {
      $("#todo-review-head").textContent = `${y.label}: ${y.done} of ${y.total} done`;
      $("#todo-review").innerHTML = list(y.items.map((r) => li(esc(r.title),
        r.done === true ? "done" : r.done === false ? (r.ticked ? "you ticked it" : "not done") : (r.ticked ? "ticked" : "can't tell"))));
    }
  },

  async plan() {
    const v = await get("/api/plan");
    const c = v.counts;
    $("#plan-head").textContent = `From ${v.today} to ${v.deadline}: ${c.have} set aside, ${c.ok} on track, ${c.maybe} probably, ${c.luck} on luck, ${c.blocked} waiting on an unlock, ${c.stuck} with no way yet.`;
    $("#plan-rows").innerHTML = "<tr><th>Slot</th><th>Status</th><th>Best way</th><th>When</th><th>Also</th></tr>" + v.slots.map((r) => {
      const b = r.best;
      const when = !b ? "" : b.odds != null ? `${Math.round(b.odds * 100)}% by the deadline` : `from ${esc(b.earliest)}${b.last_start ? `, start by ${esc(b.last_start)}` : ""}`;
      const also = r.others.slice(0, 3).map((o) => `${esc(o.label)}${o.odds != null ? ` (${Math.round(o.odds * 100)}%)` : ""}${o.blocked.length ? ` <span class="sub">after ${esc(o.blocked.join(", "))}</span>` : ""}`).join("<br>");
      return `<tr><td>${esc(r.name)}${r.count > 1 ? ` ×${r.count}` : ""}${r.quality ? ` <span class="sub">(quality ${r.quality}+)</span>` : ""}<br><span class="sub">${esc(r.bundle)} · ${esc(r.room)}</span></td>` +
        `<td class="status-${esc(r.status)}">${esc(STATUS_TEXT[r.status] || r.status)}</td>` +
        `<td>${b ? esc(b.label) : ""}${b && b.blocked.length ? `<br><span class="sub">after ${esc(b.blocked.join(", "))}</span>` : ""}</td><td>${when}${b && b.earliest_after_unlock ? `<br><span class="sub">with the unlocks: ${esc(b.earliest_after_unlock)}</span>` : ""}</td><td class="sub">${also}</td></tr>`;
    }).join("");
    const g = v.gold;
    const need = g.vault + g.unlocks;
    $("#plan-gold").innerHTML = esc(`You have ${g.money.toLocaleString()}g. The Vault still needs ${g.vault.toLocaleString()}g and these unlocks ${g.unlocks.toLocaleString()}g (${need.toLocaleString()}g in all).`) + "<br>" +
      esc(`By ${v.deadline}: about ${g.projected.toLocaleString()}g from ${g.streams.filter((x) => x.gold).map((x) => `${x.label} (${x.gold.toLocaleString()}g)`).join(", ")}`) +
      (g.replant.gold ? esc(`, plus about ${g.replant.gold.toLocaleString()}g replanting your ${g.replant.tiles} tiles with ${g.replant.crop} (${g.replant.note})`) : "") + ". " +
      (g.covered_by ? esc(`That covers it by ${g.covered_by}.`) : g.gap ? `<b>${esc(`About ${g.gap.toLocaleString()}g short`)}</b>${esc(": fishing, mining, machines or skipping the dearest unlocks would close it.")}` : esc("With replanting, that covers it."));
    $("#plan-unlocks").innerHTML = "<tr><th>Unlock</th><th>Cost</th><th>Takes</th><th>Opens</th></tr>" + v.unlocks.map((u) =>
      `<tr><td>${esc(u.label)}${u.how ? `<br><span class="sub">${esc(u.how)}</span>` : ""}</td><td>${u.gold ? `${u.gold.toLocaleString()}g` : ""}${u.materials.length ? `${u.gold ? " + " : ""}${esc(u.materials.map((m) => `${m.count} ${m.name}`).join(", "))}` : ""}</td>` +
      `<td>${u.days ? `${u.days} day${u.days > 1 ? "s" : ""}` : ""}</td><td>${esc(u.slots.join(", "))}</td></tr>`
    ).join("");
  },


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

  async sell() {
    const f = sellFilters();
    const v = await get("/api/sell?" + new URLSearchParams(Object.fromEntries(Object.entries(f).map(([k, x]) => [k, x ? "true" : "false"]))));
    $("#sell-head").textContent = `${v.count} items for about ${v.total.toLocaleString()}g`;
    $("#sell-rows").innerHTML = "<tr><th>Item</th><th>Count</th><th>Each</th><th>Total</th><th>Where</th></tr>" + v.sell.map((r) =>
      `<tr><td>${esc(r.name)}${r.quality ? ` <span class="q-${esc(r.quality)}">${esc(r.quality)}</span>` : ""}</td><td>${r.count}</td><td>${r.each}g</td><td>${r.total.toLocaleString()}g</td><td class="sub">${esc(r.where.join(", "))}</td></tr>`
    ).join("");
    $("#sell-process").innerHTML = v.process.length ? '<ul class="list">' + v.process.map((r) =>
      `<li><span>${r.count} ${esc(r.name)} → ${esc(r.product)} <span class="sub">(${esc(r.machine)}${r.burns ? `, uses ${esc(r.burns)} each` : ""})</span></span><span>${r.seeds ? "" : `+${r.gain.toLocaleString()}g`}</span></li>`
    ).join("") + `</ul><p class="sub">About ${v.process_gain.toLocaleString()}g more than selling them raw.</p>` : '<p class="sub">Nothing worth processing with the machines you have.</p>';
    $("#sell-filters").innerHTML = v.filters.map((x) =>
      `<label class="filter"><input type="checkbox" data-filter="${esc(x.id)}" ${x.on ? "checked" : ""}> ${esc(x.label)} <span class="sub">(${x.count} items, ${x.value.toLocaleString()}g)</span></label>`
    ).join("");
    document.querySelectorAll("#sell-filters input").forEach((box) => box.addEventListener("change", () => {
      saveSellFilters({ ...sellFilters(), [box.dataset.filter]: box.checked });
      views.sell();
    }));
    $("#sell-keep").innerHTML = '<ul class="list">' + v.keep.map((r) =>
      `<li><span>${r.count} ${esc(r.name)}${r.quality ? ` <span class="q-${esc(r.quality)}">${esc(r.quality)}</span>` : ""}</span><span class="sub">${esc(r.why)}</span></li>`
    ).join("") + "</ul>";
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

const SELL_DEFAULTS = { loved: true, liked: false, help_wanted: true, seeds: true };
function sellFilters() {
  try { return { ...SELL_DEFAULTS, ...JSON.parse(localStorage.getItem("sellFilters") || "{}") }; } catch { return { ...SELL_DEFAULTS }; }
}
function saveSellFilters(f) {
  try { localStorage.setItem("sellFilters", JSON.stringify(f)); } catch { /* private window: just don't remember */ }
}

async function searchCart() {
  const q = $("#cart-q").value.trim();
  if (q.length < 3) { $("#cart-hits").innerHTML = ""; return; }
  const v = await get(`/api/cart/search?q=${encodeURIComponent(q)}`);
  $("#cart-hits").innerHTML = v.hits.length
    ? '<ul class="list">' + v.hits.map((h) => `<li><span>${esc(h.date)} · ${esc(h.name)}${unsure(h.sure)}</span><span>${h.price.toLocaleString()}g</span></li>`).join("") + "</ul>"
    : `<p class="sub">Not at the cart in the next two years.</p>`;
}

async function show(name) {
  closeAsk();  // a tab button puts the search away, so the page you chose is what you see
  window.scrollTo(0, 0);
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
    const row = document.querySelector(".errands");
    (m.seasonal_errands || []).forEach((e) => {
      const b = document.createElement("button");
      b.type = "button"; b.dataset.errand = e.id; b.textContent = e.label; b.className = "seasonal";
      b.addEventListener("click", () => showErrand(e.id));
      row.appendChild(b);
    });
  } catch (e) {
    $("#status").textContent = e.message;
  }
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  let timer;
  $("#cart-q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(searchCart, 250); });
  let askTimer;
  $("#ask-q").addEventListener("input", () => { clearTimeout(askTimer); askTimer = setTimeout(searchAsk, 200); });
  $("#ask-close").addEventListener("click", closeAsk);
  document.querySelectorAll("[data-errand]").forEach((b) => b.addEventListener("click", () => showErrand(b.dataset.errand)));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAsk();
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); $("#ask-q").focus(); }
  });
  show("morning");
}

start();
