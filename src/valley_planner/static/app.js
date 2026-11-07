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
  const parts = [], get_ = [], use = [];
  const head = (`<h2>${esc(c.name)}</h2><p class="muted">${c.held ? `You hold ${c.held}` : "You hold none"}${c.museum ? ` · museum: ${esc(c.museum)}` : ""}${c.help_wanted ? " · a Help Wanted request can ask for it this season" : ""}</p>`);
  if (c.sells.length) use.push("<h3>Sells for</h3>" + list(c.sells.map((x) => li(x.quality || "normal", `${x.each}g`))));
  if (c.bundles.length) use.push("<h3>Bundles</h3>" + list(c.bundles.map((b) => li(`${esc(b.bundle)} <span class="sub">(${esc(b.room)})</span>`, `${b.count}${b.quality ? `, quality ${b.quality}+` : ""}${b.open ? "" : " · room not open yet"}`))));
  if (c.grows) get_.push(`<h3>Grows</h3><p>From ${esc(c.grows.seed)} in ${esc(c.grows.seasons.join(", "))}: ${c.grows.days} days${c.grows.regrow ? `, then every ${c.grows.regrow}` : ""}.</p>`);
  if (c.plant) use.push(`<h3>Plant it</h3><p>Grows ${esc(c.plant.crop)} in ${esc(c.plant.seasons.join(", "))}: ${c.plant.days} days${c.plant.regrow ? `, then every ${c.plant.regrow}` : ""}.</p>`);
  if (c.fish) {
    const f = c.fish;
    get_.push("<h3>Catch it</h3>" + (f.trap ? `<p>Crab pot, ${esc(f.water)} water.</p>` :
      `<p>${f.here_now.length ? `This season: ${esc(f.here_now.join(", "))}` : "Not this season"}${f.other_seasons.length ? ` · also ${esc(f.other_seasons.join(", "))}` : ""}<br>${esc(f.times.join(", "))} · ${esc(f.weather === "both" ? "any weather" : f.weather)}${f.min_level ? ` · fishing level ${f.min_level}` : ""} · difficulty ${f.difficulty}</p>`));
  }
  if (c.shops_today.length || c.shops_other.length) get_.push("<h3>Buy it</h3>" + list([
    ...c.shops_today.map((o) => li(`${esc(o.shop)} today${unsure(o.sure)}`, o.trade ? `${o.trade_amount} ${esc(o.trade)}` : `${o.price}g`)),
    ...c.shops_other.map((o) => li(`${esc(o.shop)} <span class="sub">(${esc(o.when || "other days")})</span>`, o.trade ? `${o.trade_amount} ${esc(o.trade)}` : `${o.price}g`)),
  ]));
  if (c.recipes && c.recipes.length) get_.push("<h3>The recipe</h3>" + list(c.recipes.map((r) => li(`${esc(r.shop)}${r.known ? " · you know it" : ""}`, `${r.price}g`))));
  if (c.cart.length) get_.push("<h3>At the cart</h3>" + list(c.cart.map((x) => li(`${esc(x.date)}${unsure(x.sure)}`, `${x.price.toLocaleString()}g`))));
  if (c.machines.length) use.push("<h3>Machines</h3>" + list(c.machines.map((m) => li(`${esc(m.machine)}: ${m.uses > 1 ? `${m.uses} → ` : ""}${esc(m.product)}${m.owned ? ` <span class="sub">(you have ${m.owned})</span>` : ""}`, `${m.sells}g · ${mins(m.minutes, m.days)}`))));
  if (c.gifts) use.push("<h3>Gift tastes</h3>" + list(["love", "like", "dislike", "hate"].filter((t) => c.gifts[t].length).map((t) => li(t, esc(c.gifts[t].join(", "))))));
  return head + tabbed([["Use it", use.join("")], ["Get it", get_.join("")]]);
}

// Where a villager is today, from /api/ask/villager's "today" (one entry, or two on a rain-coinflip day)
function whereToday(today) {
  return today.map((d) => (today.length > 1 ? `<p class="sub">${Math.round(d.chance * 100)}% chance:</p>` : "") +
    (d.stops.length ? list(d.stops.map((st) => li(esc(st.time), esc(st.place)))) : '<p class="sub">Stays home</p>')).join("");
}

// A card's sections as tabs, so a long card opens on one short list instead of everything at once.
function tabbed(sections) {
  const shown = sections.filter(([, html]) => html);
  if (shown.length < 2) return shown.map(([, html]) => html).join("");
  return `<div class="seg card-tabs" role="group">${shown.map(([name], i) => `<button type="button" class="${i ? "" : "on"}" data-pane="${i}">${esc(name)}</button>`).join("")}</div>` +
    shown.map(([, html], i) => `<div class="card-pane" data-pane="${i}"${i ? " hidden" : ""}>${html}</div>`).join("");
}
function wireTabs(root) {
  root.querySelectorAll(".card-tabs button").forEach((b) => b.addEventListener("click", () => {
    root.querySelectorAll(".card-tabs button").forEach((x) => x.classList.toggle("on", x === b));
    root.querySelectorAll(".card-pane").forEach((p) => { p.hidden = p.dataset.pane !== b.dataset.pane; });
  }));
}

function villagerCard(c) {
  const f = c.met ? `${c.hearts} hearts (${c.points} points) · ${c.gifts_this_week}/2 gifts this week${c.gifted_today ? " · gifted today" : ""}${c.talked_today ? " · talked today" : ""}` : "Not met yet";
  const usual = c.loves.filter((x) => !x.rare || x.held), rare = c.loves.filter((x) => x.rare && !x.held);
  const gifts = (c.likes_held.length ? `<h3>Likes, that you hold</h3><p>${esc(c.likes_held.join(", "))}</p>` : "") +
    "<h3>Loves</h3>" + list(usual.map((x) => li(esc(x.name), x.held ? `you hold ${x.held}` : ""))) +
    (rare.length ? `<details class="fold plain"><summary>Rare things (${rare.length})</summary><p class="muted">${rare.map((x) => esc(x.name)).join(", ")}</p></details>` : "");
  return `<h2>${esc(c.name)}</h2><p class="muted">Birthday ${esc(c.birthday)} · ${esc(f)}</p>` +
    tabbed([["Today", whereToday(c.today)], ["Gifts", gifts]]);
}

// " · in the green chest (the farm)" for where something is kept
function inPlaces(where) { return where && where.length ? ` · in ${esc(where.join(", "))}` : ""; }

function errandCard(name, c) {
  const head = `<h2 class="sign">${esc(c.title)}</h2>`;
  if (name === "gunther") {
    return head + `<p class="sub">${c.donated} donated so far.</p>` +
      (c.take.length ? "<h3>Not donated yet</h3>" + list(c.take.map((x) => li(esc(x.name), `${x.kind}${x.held > 1 ? ` · you hold ${x.held}` : ""}${inPlaces(x.where)}`))) : '<p>Nothing you hold is new to the museum.</p>') +
      (c.next_rewards.length ? "<h3>Closest rewards</h3>" + list(c.next_rewards.map((r) => li(esc(r.reward), `${r.left} more: ${esc(r.needs.join(", "))}`))) : "");
  }
  if (name === "clint") {
    return head + (c.busy ? `<p class="sub">${esc(c.busy)}.</p>` : "") +
      (c.geodes.length ? "<h3>Geodes to crack</h3>" + list(c.geodes.map((g) => li(`${g.held} ${esc(g.name)}`, `${g.cost.toLocaleString()}g${inPlaces(g.where)}`))) : "<p>No geodes to crack.</p>") +
      (c.upgrades.length ? "<h3>Tool upgrades</h3>" + list(c.upgrades.map((u) => li(`${esc(u.tool)}${u.can ? " · <b>you can do this now</b>" : ""}`, `${u.gold.toLocaleString()}g + ${esc(u.bars)} (you hold ${u.have_bars})`))) : "");
  }
  if (name === "cc") {
    return head + (c.rooms.length ? c.rooms.map((r) => `<h3>${esc(r.room)}</h3>` + list(r.items.map((x) => li(`${x.count} ${esc(x.name)}${x.quality ? ` (${esc(x.quality)})` : ""}`, `${esc(x.bundle)}${x.open ? "" : " · room not open yet"}${inPlaces(x.where)}`)))).join("") : "<p>Nothing you hold fills an open slot right now.</p>") +
      (c.vault.length ? "<h3>Vault</h3>" + list(c.vault.map((v) => li(esc(v.bundle), v.gold <= c.money ? "<b>you can pay this now</b>" : `${(v.gold - c.money).toLocaleString()}g to go`))) : "");
  }
  if (name === "trees") {
    return head + (c.trees.length ? list(c.trees.map((t) => li(`<b>${esc(t.fruit)}</b> · ${esc(t.where)}`, esc(t.text)))) : "<p>No fruit trees planted.</p>") +
      (c.cave.length ? `<h3>The farm cave: ${esc(c.cave_kind)}</h3><p class="sub">Each night is down to chance, so these are the odds of at least one, not a forecast.</p>` +
        list(c.cave.map((x) => li(esc(x.name), `${Math.round(x.chance * 100)}% a night`))) : "");
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
  const c = await busy("Looking through your chests…", () => get(`/api/errand/${name}`));
  $("#ask-results").innerHTML = "";
  $("#ask-card-body").innerHTML = errandCard(name, c);
  $("#ask-card").hidden = false;
}

async function showCard(kind, id) {
  const c = await get(`/api/ask/${kind}/${encodeURIComponent(id)}`);
  $("#ask-card-body").innerHTML = kind === "item" ? itemCard(c) : villagerCard(c);
  wireTabs($("#ask-card-body"));
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

// ----- Route: goals in priority order, planned for a fresh Year 1 -----
const SETTING_LABELS = {
  tiles: "Tiles you farm", wood_per_day: "Wood from a chopping day", floors_per_week: "Mines floors a week (your target)",
  hardwood_per_day: "Hardwood from a stump day", fish_gold: "Gold from a fishing day", mine_gold: "Gold from a mining day",
  float: "Cash kept back from seeds", quartz_per_day: "Quartz from a mining day", gift_points: "Friendship from each gift",
  jars: "Preserves Jars to have", kegs: "Kegs to have", tappers: "Tappers on oaks (for Kegs)",
  clay_per_day: "Clay from a day digging in the Mines",
};
const FIRST_GOALS = { greenhouse: "target", seed_maker: "target", kitchen: "nice", cc: "nice" };  // the rest start off
const TIERS = { target: "Target", nice: "Nice to have", off: "Off" };
let routeState = null;
let routeTimer;

function loadRouteState(catalog) {
  let saved = null;
  try { saved = JSON.parse(localStorage.getItem("route") || "null"); } catch { saved = null; }
  const ids = catalog.objectives.map((o) => o.id);
  const goals = (saved && saved.goals ? saved.goals.filter((g) => ids.includes(g.id)) : []);
  ids.filter((id) => !goals.some((g) => g.id === id)).forEach((id) =>
    goals.push({ id, tier: FIRST_GOALS[id] || "off" }));
  return { goals, cave: (saved && saved.cave) || "best", start: (saved && saved.start) || "save", settings: { ...catalog.settings, ...((saved && saved.settings) || {}) },
           labels: Object.fromEntries(catalog.objectives.map((o) => [o.id, o.label])), spouses: catalog.spouses || [] };
}
function saveRouteState() {
  try { localStorage.setItem("route", JSON.stringify({ goals: routeState.goals, cave: routeState.cave, start: routeState.start, settings: routeState.settings })); } catch { /* fine */ }
}

function drawSettings() {
  $("#route-settings").innerHTML = Object.entries(SETTING_LABELS).map(([k, label]) =>
    `<label for="rs-${k}">${esc(label)}</label><input id="rs-${k}" type="number" min="0" step="1" data-k="${k}" value="${routeState.settings[k]}">`
  ).join("") + `<label for="rs-spouse">Who to marry</label><select id="rs-spouse"><option value="">Whoever you're closest to</option>` +
    routeState.spouses.map((p) => `<option value="${esc(p.name)}" ${routeState.settings.spouse === p.name ? "selected" : ""}>${esc(p.name)}${p.hearts ? ` (${p.hearts}♥)` : ""}</option>`).join("") + "</select>";
  $("#rs-spouse").onchange = () => { routeState.settings.spouse = $("#rs-spouse").value; changed(); };
  document.querySelectorAll("#route-settings input[type=number]").forEach((inp) => inp.addEventListener("input", () => {
    routeState.settings[inp.dataset.k] = Math.max(0, parseInt(inp.value || "0", 10));
    changed(600);
  }));
  $("#route-start").value = routeState.start;
  $("#route-start").onchange = () => { routeState.start = $("#route-start").value; changed(); };
  $("#route-cave").value = routeState.cave;
  $("#route-cave").onchange = () => { routeState.cave = $("#route-cave").value; changed(); };
}

function changed(wait = 150) {
  saveRouteState();
  clearTimeout(routeTimer);
  routeTimer = setTimeout(() => busy("Planning the rest of the year…", planRoute), wait);
}


// The body /api/route and /api/needs take, from the goals chosen on the Route tab.
const routeBody = (rs, start) => ({ targets: rs.goals.filter((g) => g.tier === "target").map((g) => g.id),
  nice: rs.goals.filter((g) => g.tier === "nice").map((g) => g.id), cave: rs.cave, start, settings: rs.settings });

// The route's next week on the To-do: what to do each day, and which goal it's for.
async function todoRoute() {
  const rs = routeState || loadRouteState(await get("/api/route/objectives"));
  const body = routeBody(rs, "save");
  $("#todo-route").innerHTML = '<p class="sub">Planning…</p>';
  const r = await fetch("/api/route", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { $("#todo-route").innerHTML = ""; return; }
  const v = await r.json();
  const days = [...new Set(v.agenda.map((a) => a.day))];
  const name = (d) => d === v.today ? "Today" : d.replace(/, Year \d+/, "");
  $("#todo-route").innerHTML = days.length ? days.map((d) => `<h3>${esc(name(d))}</h3>` + list(v.agenda.filter((a) => a.day === d).map((a) =>
    `<li class="agenda ${esc(a.kind)}"><span><b>${esc(a.text)}</b><br><span class="sub">${esc(a.why)}</span></span><span class="goal">${esc(a.goal)}</span></li>`))).join("")
    : '<p class="sub">Nothing from the route this week: your goals are on track or out of reach (see the Route tab).</p>';
}

async function planRoute() {
  const body = routeBody(routeState, routeState.start);
  $("#route-tree").classList.add("busy");
  const r = await fetch("/api/route", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("#route-tree").classList.remove("busy");
  if (!r.ok) { $("#route-tree").innerHTML = `<p>Couldn't plan: ${esc(r.statusText)}</p>`; return; }
  const v = await r.json();
  const caveName = { bats: "fruit bats", mushrooms: "mushrooms" };
  $("#route-cave-note").textContent = (v.cave_options
    ? `Fruit bats or mushrooms: planned both, and ${caveName[v.cave] || v.cave} achieve more (` +
      v.cave_options.map((c) => `${caveName[c.cave]}: ${c.targets_ok} target${c.targets_ok === 1 ? "" : "s"}, ${c.nice_ok} nice-to-have${c.nice_ok === 1 ? "" : "s"}, ${c.end_cash.toLocaleString()}g at the year's end`).join("; ") + ")."
    : `Cave: ${caveName[v.cave] || v.cave}.`) + (v.cave_chosen ? " You've already chosen, so the plan uses it from today."
    : v.cave_day ? ` Demetrius makes his offer on ${v.cave_day}.` : " Demetrius's offer doesn't come this year.");
  drawTree(v);
  drawGoals(v);
  tuckAwayOff();
  $("#route-cave").disabled = !!v.cave_chosen;
  if (v.cave_chosen) $("#route-cave").value = v.cave; else $("#route-cave").value = routeState.cave;
  $("#route-cave").title = v.cave_chosen ? "Your save has already chosen; it can't be changed" : "";
  drawCash(v);
}

// ----- Plan: what every chosen goal needs, added up, and the items that can be got more than one way -----
const BARS = ["copper_bar", "iron_bar", "gold_bar", "iridium_bar", "refined_quartz"];  // one "Bars" tile for these
const num = (n) => Math.round(n).toLocaleString();
const amt = (n, unit = "") => `${num(n)}${unit}`;
const about = (n) => num(Math.round(n / 500) * 500);  // "about 105,500g": the forecast isn't exact
const pct = (n, of) => (of ? Math.max(n > 0 ? 1 : 0, Math.min(100, (n / of) * 100)) : 0).toFixed(1);
const also = (xs) => xs && xs.length ? ` <b class="also">· also ${esc(xs.map((x) => x.replace(/^The /, "the ")).join(" and "))}</b>` : "";
const bar = (n, of) => `<span class="nbar" aria-hidden="true"><span style="width:${pct(n, of)}%"></span></span>`;

let needsOpen = "gold";  // the resource whose breakdown is showing

function drawNeeds(v) {
  const goals = v ? v.goals.filter((g) => g.tier !== "off") : [];
  if (!goals.length) {
    $("#needs-head").innerHTML = 'No goals chosen yet. Pick some on the <a href="#route" data-go="route">Route tab</a> and this adds up what they take.';
    $("#needs-tiles").innerHTML = $("#needs-where").innerHTML = $("#needs-single").innerHTML = "";
    $("#needs-choices-box").hidden = true;
    $("#needs-head a").addEventListener("click", (e) => { e.preventDefault(); show("route"); });
    return;
  }
  $("#needs-head").textContent = `Everything your goals need from ${v.today.replace(/, Year \d+/, "")} to ${v.end.replace(/, Year \d+/, "")}, added up. Pick a box to see what it goes to.`;
  const res = v.resources.filter((x) => x.total > 0);
  const uses = (x) => x.breakdown.reduce((n, b) => n + b.items.length, 0);
  const multi = res.filter((x) => x.id === "gold" || uses(x) > 1), single = res.filter((x) => !multi.includes(x));
  if (!multi.some((x) => x.id === needsOpen)) needsOpen = multi.length ? multi[0].id : "";

  // A box per resource that goes to more than one thing; pressing it shows where it goes
  const end = v.end.replace(/, Year \d+/, "");
  const line = (x) => x.id === "gold"
    ? `<span class="nmeter" aria-hidden="true"><span class="m-have" style="width:${pct(x.have, x.total)}%"></span><span class="m-exp" style="width:${pct(x.expected || 0, x.total)}%"></span></span>` +
      `<span class="n-line"><b class="ok">${amt(x.have, "g")}</b> in hand${x.expected ? ` · <b class="exp">~${about(x.expected)}g</b> to come by ${esc(end)}` : ""}` +
      (x.short > 0 ? ` · <b class="bad">~${about(x.short)}g short</b>` : ' · <b class="ok">covered</b>') + "</span>"
    : `<span class="n-line">${[x.have ? `${amt(x.have, x.unit)} in hand` : "", x.days ? `~${x.days} ${esc(x.days_label)}` : "", x.short > 0 && x.have ? `${amt(x.short, x.unit)} short` : ""].filter(Boolean).join(" · ")}</span>`;
  const goalsOf = (x) => x.breakdown.length;
  $("#needs-tiles").innerHTML = multi.map((x) => `<button type="button" class="ntile pick${x.id === "gold" ? " wide" : ""}" data-res="${esc(x.id)}" aria-pressed="${x.id === needsOpen}">` +
    `<span class="n-lab">${esc(x.label)}</span><span class="n-big">${amt(x.total, x.unit)}</span>${line(x)}` +
    `<span class="n-uses">${uses(x)} things · ${goalsOf(x)} goal${goalsOf(x) === 1 ? "" : "s"}</span></button>`).join("") +
    (() => {
      const d = v.days, spent = d.chop + d.stumps + d.mine + d.fish;
      return spent ? `<div class="ntile"><span class="n-lab">Days</span><span class="n-big">${spent}</span><span class="n-line">` +
        [["chopping", d.chop], ["stumps", d.stumps], ["mining", d.mine], ["fishing", d.fish]].filter(([, n]) => n).map(([k, n]) => `${k} ${n}`).join(" · ") +
        ` · of ${d.left} left${spent > d.left ? ` <b class="bad">· ${spent - d.left} too many</b>` : ""}</span></div>` : "";
    })();
  $("#needs-single").innerHTML = single.length ? "<b>Only one use:</b> " + single.map((x) => {
    const it = x.breakdown[0].items[0];
    return `<span>${amt(x.total, x.unit)} ${esc(x.label)} · ${esc(it.label)}${x.have ? ` <span class="sub">(${amt(x.have, x.unit)} in hand)</span>` : ""}</span>`;
  }).join("") : "";
  document.querySelectorAll("#needs-tiles .pick").forEach((b) => b.addEventListener("click", () => { needsOpen = b.dataset.res; drawNeeds(v); }));

  // Where the chosen one goes: by goal, then by item
  const x = res.find((r) => r.id === needsOpen);
  $("#needs-where").innerHTML = x ? `<div class="nwhere-head"><h2>${esc(x.label)}: ${amt(x.total, x.unit)}</h2>` +
    `<span class="sub">${esc([x.days ? `about ${x.days} ${x.days_label}` : "", x.note, x.extra].filter(Boolean).join(" · "))}</span></div>` +
    x.breakdown.map((b) => `<div class="ngoal"><div class="ng-row"><b>${esc(b.label)}${also(b.also)}</b><b>${amt(b.amount, x.unit)}</b></div>${bar(b.amount, x.total)}` +
      `<ul class="nitems">` + b.items.map((it) => `<li><span>${esc(it.label)}${it.how ? `: ${esc(it.how)}` : ""}${also(it.also)}${it.this_year === false ? ' <span class="later">not this year</span>' : ""}</span><span>${amt(it.amount, x.unit)}</span></li>`).join("") +
      "</ul></div>").join("") : "";

  // Choose how: each way a card, joined by OR; press one to plan with it
  const TAG = { planned: "✓ PLANNED", luck: "LUCK", no: "✕ NOT THIS YEAR", later: "LATER", possible: "" };
  const card = (c, o, i) => {
    if (o.more) return `<button type="button" class="ncard more" aria-expanded="false" data-label="${esc(o.label)}" data-more="${esc(o.detail)}">${esc(o.label)}</button>`;
    let tag = o.tag || TAG[o.state] || "";
    const planned = o.planned ?? o.state === "planned";
    if (planned && !tag.startsWith("✓")) tag = "✓ " + tag;
    if (o.state === "no" && !tag.startsWith("✕")) tag = "✕ " + tag;
    const cls = planned ? (o.state === "luck" || o.odds != null ? "planned c-luck" : "planned") : o.state;  // planned on luck: amber, ticked
    const text = [o.detail, o.gold ? amt(o.gold, "g") : "", o.when].filter(Boolean).map(esc).join(" · ") + also(o.also);
    const inner = `${tag ? `<b class="c-tag">${esc(tag)}</b>` : ""}<b class="c-ttl">${esc(o.label)}</b>${text ? `<span>${text}</span>` : ""}`;
    return planned || !o.pick ? `<div class="ncard c-${cls}${i ? "" : " first"}">${inner}</div>`
      : `<button type="button" class="ncard c-${cls}${i ? "" : " first"}" data-item="${esc(c.item)}" data-pick="${esc(o.pick)}" title="Plan with this way">${inner}</button>`;
  };
  $("#needs-choices-box").hidden = !v.choices.length;
  $("#needs-choices").innerHTML = v.choices.map((c) => `<div class="nchoice"><div class="nc-item"><b>${esc(c.item)}</b><br><span class="sub">${esc(c.where)}</span>` +
    (c.picked ? `<br><button type="button" class="linkish" data-unpick="${esc(c.item)}">your choice · undo</button>` : "") + "</div>" +
    `<div class="nc-ways">${c.options.map((o, i) => i ? `<span class="way"><span class="or">OR</span>${card(c, o, i)}</span>` : card(c, o, i)).join("")}</div></div>`).join("");
  const replan = (item, way) => {
    const picks = { ...(routeState.settings.picks || {}) };
    if (way) picks[item] = way; else delete picks[item];
    routeState.settings.picks = picks;
    saveRouteState();
    busy("Re-planning with your choice…", views.plan);
  };
  document.querySelectorAll("#needs-choices [data-pick]").forEach((b) => b.addEventListener("click", () => replan(b.dataset.item, b.dataset.pick)));
  document.querySelectorAll("#needs-choices [data-unpick]").forEach((b) => b.addEventListener("click", () => replan(b.dataset.unpick, "")));
  document.querySelectorAll("#needs-choices .more").forEach((b) => b.addEventListener("click", () => {
    const open = b.getAttribute("aria-expanded") !== "true";
    b.setAttribute("aria-expanded", open);
    b.textContent = open && b.dataset.more ? `${b.dataset.label}: ${b.dataset.more}` : b.dataset.label;
  }));
}

// The route as a tech tree: a lane per goal, weekly columns from today, cards coloured by the days they have
// to spare, and the goal at the end of each lane.
const LANE_STATUS = { ok: "On track", luck: "Down to luck", impossible: "✕ Not this year", done: "Done" };

function drawTree(v) {
  const t = v.tree, n = t.columns.length;
  const year = (/Year (\d+)/.exec(v.today) || [])[1];
  const d = (s) => (s || "").replaceAll(`, Year ${year}`, "");
  const objs = Object.fromEntries(v.objectives.map((o) => [o.id, o]));
  const lanes = Object.fromEntries(t.lanes.map((l) => [l.id, l]));
  const cols = `grid-template-columns: 212px repeat(${n}, 184px) 200px`;
  const head = `<div class="tree-lane tree-head" style="${cols}"><div></div>` + t.columns.map((c, i) =>
    `<div class="tcol${i === 0 ? " now" : ""}"><b>${esc(c.label)}</b><span class="${c.gold ? "due" : ""}">${i === 0 ? "This week · " : ""}${c.gold ? `${c.gold.toLocaleString()}g due` : "nothing to pay"}</span></div>`).join("") +
    `<div class="tcol"><b>Goal</b><span>what it unlocks</span></div></div>`;
  const tiers = (g) => `<div class="tiers" role="group" aria-label="How much ${esc(routeState.labels[g.id])} matters">` + Object.entries(TIERS).map(([k, label]) =>
    `<button type="button" data-goal="${esc(g.id)}" data-tier="${k}" aria-pressed="${g.tier === k}">${label === "Nice to have" ? "Nice" : label}</button>`).join("") + "</div>";
  const card = (c, row) => {
    const helps = c.helps.length ? `<button type="button" class="helps">Helps ${c.helps.length} goals<span class="pop" role="tooltip">` +
      c.helps.map((h) => `<b>${esc(h.goal)}</b> · ${esc(h.why)}`).join("<br>") + "</span></button>" : "";
    const waits = c.waits.map((w) => `<div class="waits">${esc(d(w))}</div>`).join("");
    return `<div class="tcard u-${esc(c.urgency)}${c.helps.length ? " multi" : ""}" style="grid-column: ${c.col + 2}; grid-row: ${row}">${helps}` +
      `<div class="t-tag">${esc(c.tag)}</div><div class="t-ttl">${esc(c.title)}</div><div class="t-det">${esc(d(c.detail))}</div>${waits}</div>`;
  };
  const body = routeState.goals.map((g) => {
    const name = esc(routeState.labels[g.id] || g.id);
    const o = objs[g.id], lane = lanes[g.id];
    const label = (status, extra = "") => `<div class="lane-head" draggable="true" data-goal="${esc(g.id)}" style="grid-row: 1 / span ${extra || 1}">` +
      `<div class="lane-name"><span class="grip" aria-hidden="true">⋮⋮</span>${name}</div><div class="lane-status">${status}</div>${tiers(g)}</div>`;
    if (g.tier === "off" || !o) {
      return `<div class="tree-lane off" style="${cols}">${label('<span class="sub">Switched off</span>')}<div class="lane-note" style="grid-column: 2 / -1">Set it to Target or Nice to plan it and see what it moves.</div></div>`;
    }
    if (o.status === "done") {
      return `<div class="tree-lane done" style="${cols}">${label('<b class="ok">✓ Done in your save</b>')}<div class="lane-note" style="grid-column: 2 / -1"></div></div>`;
    }
    const rows = lane ? lane.rows : [];
    const misses = (o.misses || []).map((m) => `<div class="tcard u-x"><div class="t-tag">✕ ${/luck/.test(m.why) ? "LUCK" : "NOT THIS YEAR"}</div><div class="t-ttl">${esc(m.what)}</div><div class="t-det">${esc(d(m.why))}</div></div>`)
      .concat((o.notes || []).map((p) => `<div class="tcard u-x"><div class="t-tag">✕ NOT THIS YEAR</div><div class="t-det">${esc(d(p))}</div></div>`));
    const info = (o.info || []).map((p) => `<p class="sub">${esc(p)}</p>`).join("");
    const span = Math.max(1, rows.length) + (misses.length || info ? 1 : 0);
    const now = rows.some((r) => r.some((c) => c.urgency === "now"));
    const status = o.status === "ok" ? `<b class="${now ? "bad" : "ok"}">${now ? "On track · act this week" : "On track"}</b>` : `<b class="x">${esc(LANE_STATUS[o.status] || o.status)}</b>`;
    const tier = `<span class="sub">${g.tier === "target" ? "Target" : "Nice to have"}</span>`;
    const rails = rows.map((r, i) => `<div class="rail" style="grid-column: ${r[0].col + 2} / ${n + 2}; grid-row: ${i + 1}"></div>`).join("");
    const cards = rows.map((r, i) => r.map((c) => card(c, i + 1)).join("")).join("");
    const goal = `<div class="tgoal ${o.status === "ok" ? "g-ok" : "g-x"}" style="grid-column: ${n + 2}; grid-row: 1 / span ${Math.max(1, rows.length)}">` +
      `<div class="t-tag">${g.tier === "target" ? "GOAL · TARGET" : "GOAL"}</div><div class="t-ttl">${o.status === "ok" ? "" : "✕ "}${name}</div>` +
      `<div class="t-det">${o.status === "ok" ? `ready ${esc(d(o.finish))}` : `not by ${esc(d(o.deadline))}`}${o.gold ? ` · ${o.gold.toLocaleString()}g` : ""}</div></div>`;
    const bottom = misses.length || info ? `<div class="lane-misses" style="grid-column: 2 / -1; grid-row: ${span}">${misses.join("")}${info}</div>` : "";
    return `<div class="tree-lane" style="${cols}">${label(`${tier}<br>${status}`, span)}${rails}${cards}${goal}${bottom}</div>`;
  }).join("");
  $("#route-tree").innerHTML = head + body;
  $("#route-chips").innerHTML = routeState.goals.filter((g) => g.tier !== "off" && objs[g.id]).map((g) => {
    const o = objs[g.id];
    const cls = o.status === "done" || o.status === "ok" ? "ok" : "x";
    const when = o.status === "done" ? "done" : o.status === "ok" ? d(o.finish) : "not this year";
    return `<span class="chip ${cls}">${o.status === "ok" || o.status === "done" ? "" : "✕ "}${esc(o.label)} · ${esc(when)}</span>`;
  }).join("");
  const syn = t.synergy || [];
  $("#route-synergy-box").hidden = !syn.length;
  $("#route-synergy").innerHTML = syn.map((x) => `<div class="syn"><b>${esc(cap(x.what))}</b> <span class="n">· ${x.goals.length} goals</span><br>` +
    x.goals.map((h) => `${esc(h.goal)}: ${esc(h.why)}`).join(" · ") + "</div>").join("");
  // tiers and priority, right on the lanes
  document.querySelectorAll("#route-tree .tiers button").forEach((b) => b.addEventListener("click", () => {
    const g = routeState.goals.find((x) => x.id === b.dataset.goal);
    if (g && g.tier !== b.dataset.tier) { g.tier = b.dataset.tier; changed(); }
  }));
  let from = null;
  document.querySelectorAll("#route-tree .lane-head").forEach((h) => {
    h.addEventListener("dragstart", () => { from = h.dataset.goal; h.closest(".tree-lane").classList.add("dragging"); });
    h.addEventListener("dragend", () => h.closest(".tree-lane").classList.remove("dragging"));
    h.closest(".tree-lane").addEventListener("dragover", (e) => e.preventDefault());
    h.closest(".tree-lane").addEventListener("drop", (e) => {
      e.preventDefault();
      const to = h.dataset.goal;
      if (!from || from === to) return;
      const goals = routeState.goals, i = goals.findIndex((x) => x.id === from);
      const [moved] = goals.splice(i, 1);
      goals.splice(goals.findIndex((x) => x.id === to), 0, moved);
      changed();
    });
  });
}

function cap(s) { return s ? s[0].toUpperCase() + s.slice(1) : s; }

// The quest log, the special orders taken, and what's on Lewis's board
function drawQuests(q) {
  const left = (n) => n == null ? "" : n <= 0 ? "last day" : `${n} day${n === 1 ? "" : "s"} left`;
  const rows = q.quests.map((x) => li(`<b>${esc(x.title)}</b>${x.who ? ` · ${esc(x.who)}` : ""}<br><span class="sub">${esc(x.objective)}${x.hint ? ` (${esc(x.hint)})` : ""}</span>`,
    [x.deliver_to ? `<b class="ok">you have it${x.where.length ? `: ${esc(x.where.join(", "))}` : ""}</b>` : x.item && x.have === 0 && x.kind === "deliver" ? "you don't have it yet" : "",
     left(x.days_left), x.reward ? `${x.reward.toLocaleString()}g` : ""].filter(Boolean).join(" · ")))
    .concat(q.orders.map((o) => li(`<b>${esc(o.name)}</b> · special order for ${esc(o.who)}<br><span class="sub">${esc(o.text)}</span>`, "")));
  $("#m-quests").innerHTML = (rows.length ? list(rows) : '<p class="sub">No quests in your log.</p>') +
    (q.board.length ? `<p class="sub">On Lewis's board this week: ${esc(q.board.map((b) => `${b.name} (${b.who}, ${b.reward.toLocaleString()}g)`).join("; "))}</p>` : "");
}

// The day from 6 AM to 2 AM: the suggested order, then each shop's hours, on one time axis
function drawDay(d) {
  const m = (t) => Math.floor(t / 100) * 60 + t % 100, a = m(d.from), z = m(d.to);
  const x = (t) => ((m(t) - a) / (z - a) * 100).toFixed(2);
  const w = (s, e) => ((m(e) - m(s)) / (z - a) * 100).toFixed(2);
  const ticks = [[600, "6 AM"], [900, "9"], [1200, "noon"], [1500, "3 PM"], [1800, "6"], [2100, "9"], [2400, "midnight"], [2600, "2 AM"]];
  const clock = (t) => { const h = Math.floor(t / 100) % 24, mm = t % 100; return `${(h + 11) % 12 + 1}${mm ? `:${String(mm).padStart(2, "0")}` : ""} ${h < 12 ? "AM" : "PM"}`; };
  const timed = d.blocks.filter((b) => b.start != null), loose = d.blocks.filter((b) => b.start == null);
  $("#m-day").innerHTML =
    `<div class="dl-row dl-ticks"><span></span><div class="dl-track">${ticks.map(([t, l]) => `<span style="left:${x(t)}%">${l}</span>`).join("")}</div></div>` +
    // the plan in order, each block as wide as its hours allow but never too narrow to read
    `<div class="dl-row"><span class="dl-lab"><b>Your day</b></span><div class="dl-plan">` +
    timed.map((b) => `<div class="dl-block u-${esc(b.urgency)}" style="flex:${m(b.end) - m(b.start)} 1 0">` +
      `<span class="dl-when">${esc(`${clock(b.start)}–${clock(b.end)}`)}</span><b>${esc(b.title)}</b><span>${esc(b.lines.join(" · "))}</span></div>`).join("") + "</div></div>" +
    (loose.length ? `<div class="dl-row"><span class="dl-lab"></span><div>${loose.map((b) => `<p class="bad"><b>${esc(b.title)}</b>: ${esc(b.lines.join(" · "))}</p>`).join("")}</div></div>` : "") +
    `<div class="dl-row dl-head"><span class="dl-lab">Open today</span><span></span></div>` +
    d.shops.map((s) => `<div class="dl-row dl-shop"><span class="dl-lab">${esc(s.name)} <span class="sub">${esc(s.label.replace(/:00/g, "").replace(/ – /g, "–").replace(/12 PM/g, "noon").replace(/12 AM/g, "midnight"))}</span></span><div class="dl-track">` +
      s.spans.map(([o, c]) => `<span class="dl-bar" style="left:${x(o)}%;width:${w(o, c)}%"></span>`).join("") + "</div></div>").join("") +
    (d.closed.length ? `<p class="sub">Shut today: ${esc(d.closed.map((c) => `${c.name} (${c.why})`).join("; "))}</p>` : "");
}

function drawCash(v) {
  const pts = v.cash;
  if (!pts.length) { $("#route-cash").innerHTML = ""; return; }
  const W = 760, H = 220, L = 52, R = 10, T = 10, B = 26;
  const max = Math.max(1000, ...pts.map((p) => p.cash)), min = Math.min(0, ...pts.map((p) => p.cash));
  const d0 = pts[0].day, d1 = pts[pts.length - 1].day;
  const x = (d) => L + (d - d0) / Math.max(1, d1 - d0) * (W - L - R);
  const y = (c) => T + (max - c) / (max - min) * (H - T - B);
  const step = Math.pow(10, Math.floor(Math.log10(max))) * (max / Math.pow(10, Math.floor(Math.log10(max))) > 5 ? 2 : 1);
  let grid = "";
  for (let g = 0; g <= max; g += step) grid += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(g)}" y2="${y(g)}"/><text x="${L - 6}" y="${y(g) + 4}" text-anchor="end">${g >= 1000 ? (g / 1000) + "k" : g}</text>`;
  ["Spring", "Summer", "Fall", "Winter"].forEach((s, i) => {
    const start = Math.floor((d0 - 1) / 112) * 112 + 1 + i * 28;
    if (start + 27 < d0 || start > d1) return;
    const d = Math.max(start, d0);
    grid += `<line class="grid" x1="${x(d)}" x2="${x(d)}" y1="${T}" y2="${H - B}"/><text x="${x(d) + 4}" y="${H - 8}">${s}</text>`;
  });
  const line = pts.map((p, i) => `${i ? "L" : "M"}${x(p.day).toFixed(1)},${y(p.cash).toFixed(1)}`).join("");
  const zero = min < 0 ? `<line class="zero" x1="${L}" x2="${W - R}" y1="${y(0)}" y2="${y(0)}"/>` : "";
  $("#route-cash").innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cash on hand through the year, from ${pts[0].cash}g to ${pts[pts.length - 1].cash}g">` +
    `${grid}${zero}<path class="line" d="${line}"/><g class="hover" visibility="hidden"><line class="cross" y1="${T}" y2="${H - B}"/>` +
    `<rect class="tipbox" rx="3" height="20" fill="var(--panel)" stroke="var(--wood-dark)"/><text class="tip" y="${T + 14}"></text></g>` +
    `<rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" class="hit"/></svg>`;
  const svg = $("#route-cash svg"), hov = svg.querySelector(".hover"), tip = svg.querySelector(".tip"), box = svg.querySelector(".tipbox");
  svg.querySelector(".hit").addEventListener("mousemove", (e) => {
    const r = svg.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(pts.length - 1, Math.round((px - L) / (W - L - R) * (pts.length - 1))));
    const p = pts[i], cx = x(p.day);
    hov.setAttribute("visibility", "visible");
    hov.querySelector(".cross").setAttribute("x1", cx); hov.querySelector(".cross").setAttribute("x2", cx);
    const seasons = ["Spring", "Summer", "Fall", "Winter"];
    tip.textContent = `${seasons[Math.floor((p.day - 1) / 28) % 4]} ${(p.day - 1) % 28 + 1}: ${p.cash.toLocaleString()}g · Farming ${p.farming}`;
    const tx = cx + 140 > W ? cx - 150 : cx + 6;
    tip.setAttribute("x", tx + 6); box.setAttribute("x", tx); box.setAttribute("y", T); box.setAttribute("width", 144);
  });
  svg.querySelector(".hit").addEventListener("mouseleave", () => hov.setAttribute("visibility", "hidden"));
}

// ----- Romance: hearts with your chosen partner, and what you hold that would raise them -----
function drawRomance(v, today) {
  $("#romance-body").hidden = !v.target;
  if (!v.target) return;
  $("#romance-head").textContent = `${v.name}: ${v.hearts}♥ (${v.points.toLocaleString()} points)${v.status !== "Friendly" ? ` · ${v.status}` : ""}`;
  const line = [v.talked_today ? "talked today" : "haven't talked today", v.gifted_today ? "gifted today" : `${v.gifts_left} gift${v.gifts_left === 1 ? "" : "s"} left this week`,
    v.birthday_today ? "it's their birthday today: gifts give 8×" : `birthday ${esc(v.birthday)}`].join(" · ");
  $("#romance-status").innerHTML = esc(line);
  $("#romance-cap").innerHTML = v.at_cap
    ? `<p class="bad">Stuck at ${v.cap_hearts}♥ until you give them ${esc(v.unlock.item)} (${v.unlock.gold.toLocaleString()}g · ${esc(v.unlock.how)}).</p>`
    : `<p class="sub">${v.points_to_next.toLocaleString()} points to ${v.next_heart}♥.</p>`;
  $("#romance-where").innerHTML = whereToday(today);
  $("#romance-events").innerHTML = v.events.length ? `<ul class="list-plain">${v.events.map((e) => `<li><strong>${e.hearts}♥${e.ready ? ", ready now" : ""}:</strong> ${esc(e.how)}.${e.advice ? ` <span class="${/1,500/.test(e.advice) ? "bad" : ""}">${esc(e.advice)}</span>` : ""}</li>`).join("")}</ul><p class="muted small">None of these are needed for the Bouquet, the Pendant or a proposal.</p>` : '<p class="muted">No heart events left.</p>';
  $("#romance-gifts").innerHTML = v.gifts.length ? "<tr><th>Gift</th><th>You hold</th><th>Taste</th><th>Points</th><th>Where</th></tr>" +
    v.gifts.map((g) => `<tr><td>${esc(g.name)}</td><td>${g.held}</td><td class="q-${g.taste === "love" ? "gold" : "silver"}">${esc(g.taste)}</td><td>+${g.points}</td><td class="sub">${esc(g.where.join(", "))}</td></tr>`).join("")
    : '<tr><td class="sub">Nothing you hold is a loved or liked gift for them.</td></tr>';
}

// The Morning tab's priority strip: a few ranked, clickable pointers to the tab (or errand card) with the detail.
// The tag is the days left, in the server's own words ("TOMORROW", "5 DAYS") — no legend needed. A severity of
// "plenty" here only ever means "no deadline, just worth knowing" (a capped romance partner, a Sell hint), so
// it gets a plain neutral style rather than Route's "2+ weeks spare" green, which would mean something else.
const SEVERITY_CLASS = { now: "u-now", soon: "u-soon", plenty: "u-note" };
function drawPriorities(list) {
  $("#m-priorities").hidden = !list.length;
  $("#m-priorities").innerHTML = list.map((p) =>
    `<button type="button" class="tcard ${SEVERITY_CLASS[p.severity] || "u-note"}" data-tab="${esc(p.tab || "")}" data-anchor="${esc(p.anchor || "")}" data-errand="${esc(p.errand || "")}" data-target="${esc(p.target || "")}">` +
    `<div class="t-tag">${esc(p.tag)}</div><div class="t-ttl">${esc(p.title)}</div><div class="t-det">${esc(p.text)}</div></button>`
  ).join("");
  document.querySelectorAll("#m-priorities button").forEach((b) => b.addEventListener("click", async () => {
    if (b.dataset.target) { try { localStorage.setItem("romanceTarget", b.dataset.target); } catch { /* fine */ } }
    if (b.dataset.errand) { showErrand(b.dataset.errand); return; }
    if (!b.dataset.tab) return;
    await show(b.dataset.tab);
    if (b.dataset.anchor) flashInto(b.dataset.anchor);
  }));
}

// Jump to a section on the tab just switched to, and flash it so it's clear what the click was about
function flashInto(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1600);
}

const todayDone = new Set();
let dayAsk = {}, lastDay = null, morningView = null;

function loadDone(date) {
  todayDone.clear();
  try { (JSON.parse(localStorage.getItem(`done:${date}`) || "[]")).forEach((x) => todayDone.add(x)); } catch { /* fine */ }
  todayDone.date = date;
}
function saveDone() {
  try { localStorage.setItem(`done:${todayDone.date}`, JSON.stringify([...todayDone])); } catch { /* fine */ }
}
function tick(id, on) {
  if (on) todayDone.add(id); else todayDone.delete(id);
  saveDone();
  drawNext(lastDay);
}

const extras = (rows) => rows.map((x) => `${esc(x.title)} ${x.gold}g${x.near ? ` (${esc(x.near)})` : ` (${esc(x.place)})`}`).join("; ");

// The one thing to do next, and everything after it. Ticking moves on without asking the server.
function drawNext(v) {
  const rows = v.plan.filter((x) => !todayDone.has(x.id));
  const first = rows[0];
  $("#t-next").innerHTML = first
    ? `<div class="next-when">NEXT, ABOUT ${esc(first.time)}</div><h2>${esc(first.title)}</h2><p>${esc(cap(first.why))}${first.near ? `. ${esc(cap(first.near))}.` : ""}</p>` +
      (first.way.length ? `<ol>${first.way.map((w) => `<li>${esc(w)}</li>`).join("")}</ol>` : "") +
      (first.extras ? `<p class="next-extra"><strong>On the way:</strong> ${extras(first.extras)}</p>` : "") +
      (first.spot ? spotPic(first.spot, first.title) : "") +
      `<button type="button" class="btn light" id="t-done">Done, what's next?</button>`
    : `<h2>All done for today</h2><p>${esc(v.spare.length ? `Energy to spare: ${v.spare.join(", or ")}.` : "Rest up, and get to bed by midnight.")}</p>`;
  if (first) $("#t-done").onclick = () => tick(first.id, true);
  drawMaps($("#t-next"));
  const homeward = v.passing.filter((x) => x.stop >= v.plan.length);
  const line = (x) => `<li class="stop"><label><input type="checkbox" data-stop="${esc(x.id)}" ${todayDone.has(x.id) ? "checked" : ""}><span class="stop-time">${esc(x.time)}</span><span class="stop-text ${todayDone.has(x.id) ? "gone" : ""}"><strong>${esc(x.title)}</strong> <span class="muted">${esc(x.why)}</span>${x.extras ? `<span class="stop-extra">On the way: ${extras(x.extras)}</span>` : ""}</span></label>${x.spot ? `<details class="pic-fold"><summary>Show me where</summary>${spotPic(x.spot, x.title)}</details>` : ""}</li>`;
  $("#t-plan").innerHTML = `<ul class="stops">${v.plan.filter((x) => !first || x.id !== first.id).map(line).join("")}</ul>` +
    (homeward.length ? `<p class="muted"><strong>On the way home:</strong> ${extras(homeward)}</p>` : "") +
    (v.home ? `<p class="muted">Home by about ${esc(v.home)}.${v.spare.length ? ` Then ${esc(v.spare.join(", or "))}.` : ""}</p>` : "") +
    (v.fishing ? `<p class="muted"><strong>Fish at ${esc(v.fishing.place)}</strong> for ${v.fishing.fish.map(esc).join(", ")}.</p>` +
      (v.fishing.spots.length ? `<details class="pic-fold"><summary>Show me today's bubbles</summary>${spotPic([v.fishing.location, ...v.fishing.spots[0]], "", v.fishing.spots.map(([x, y], i) => ({ x, y, kind: "dot", color: "#1C4C74", label: i ? "" : "Bubbles" })))}</details>` : "") : "") +
    (v.left.length ? `<details class="fold plain"><summary>Doesn't fit today (${v.left.length})</summary><ul class="list">${v.left.map((x) => `<li><span>${esc(x.title)}</span><span class="muted">${esc(x.why)}</span></li>`).join("")}</ul></details>` : "");
  document.querySelectorAll("#t-plan input[data-stop]").forEach((c) => c.addEventListener("change", () => tick(c.dataset.stop, c.checked)));
  document.querySelectorAll("#t-plan details.pic-fold").forEach((d) => d.addEventListener("toggle", () => { if (d.open) drawMaps(d); }, { once: true }));
}

function drawPack(p) {
  const s = p.slots;
  $("#t-pack").innerHTML = `<div class="pack-head"><h2>Pack your bag</h2><strong>${s.used} of ${s.max} slots</strong></div>` +
    (p.leave.length ? `<div class="alert amber small"><strong>Put in the Chest:</strong> ${p.leave.map(esc).join(", ")}.</div>` : "") +
    (p.tools.length ? `<p class="muted">Keep with you: ${p.tools.map(esc).join(", ")}.</p>` : "") +
    p.stops.map((x, i) => `<div class="pack-stop"><strong>${i + 1}. ${esc(x.stop)}</strong>${x.gold ? ` <span class="muted">about ${x.gold.toLocaleString()}g</span>` : ""}` +
      (x.first ? `<div class="first">${esc(x.first)}</div>` : "") + (x.items.length ? `<div>${x.items.map(esc).join(", ")}</div>` : "") +
      (x.there.length ? `<div class="muted">Already in the chest there: ${x.there.map(esc).join(", ")}</div>` : "") + "</div>").join("") +
    (p.ship.length ? `<div class="pack-stop"><strong>Shipping bin</strong> <span class="muted">about ${p.ship_gold.toLocaleString()}g</span><div>${p.ship.map((x) => esc(x.name)).join(", ")}</div></div>` : "") +
    (p.left_behind.length ? `<p class="muted small">Left behind today: ${p.left_behind.map((x) => `${x.items.map(esc).join(", ")} in the chest at ${esc(x.place)}`).join("; ")}.</p>` : "") +
    (p.dropped.length ? `<p class="muted small">Bag full, so these go in the bin: ${p.dropped.map(esc).join(", ")}.</p>` : "") +
    (s.free_on_purpose ? `<p class="muted small">Leaves ${s.free_on_purpose} slots free for what you pick up.</p>` : "");
}

// Goals that are off don't need a whole row each: one line lists them, and a press brings the rows back.
let showOff = false;
function tuckAwayOff() {
  const off = [...document.querySelectorAll("#route-tree .tree-lane.off")];
  off.forEach((r) => { r.hidden = !showOff; });
  let more = $("#route-off");
  if (!more) {
    more = document.createElement("button");
    more.id = "route-off"; more.type = "button"; more.className = "btn quiet";
    more.addEventListener("click", () => { showOff = !showOff; tuckAwayOff(); });
    $("#route-tree").after(more);
  }
  more.hidden = !off.length;
  more.textContent = showOff ? "Hide goals that are off" : `Add a goal (${off.length} more to choose from)`;
}

function drawGoals(v) {
  const chosen = v.objectives.filter((o) => o.tier !== "off");
  const off = chosen.filter((o) => o.status !== "ok" && o.status !== "done");
  $("#goals-head").textContent = !chosen.length ? "Choose your goals" : off.length
    ? `${off.length} of ${chosen.length} goal${chosen.length === 1 ? "" : "s"} need${off.length === 1 ? "s" : ""} attention` : "All your goals are on track";
  $("#goals-sub").textContent = chosen.length ? "In priority order. Drag to reorder them under Choose goals." : "Pick some below to get a route.";
  const label = { ok: "On track", done: "Done", luck: "Needs luck", impossible: "Not this year", late: "Late" };
  $("#goal-cards").innerHTML = chosen.map((o, i) => `<section class="card goal"><div class="goal-top"><span class="muted"><strong>${i + 1}</strong></span><h2>${esc(o.label)}</h2><span class="tag ${o.status === "ok" || o.status === "done" ? "green" : "amber"}">${esc(label[o.status] || o.status)}</span></div>` +
    (o.finish ? `<div>Planned by ${esc(o.finish)}.</div>` : "") + (o.problems[0] ? `<div>${esc(o.problems[0])}</div>` : "") + "</section>").join("");
}

function giantCard(g) {
  const head = g.sow_by ? `${g.crop}: sow by ${g.sow_by}, giant on ${g.day}` : `${g.crop} turns giant on ${g.day}${g.sure === false ? " (one of two overlapping squares)" : ""}`;
  const checks = (g.checks || []).map((c) => `<li class="${c.ok ? "ok" : "todo"}"><span aria-hidden="true">${c.ok ? "✓" : "!"}</span> ${esc(c.text)}</li>`).join("");
  return `<div class="giant"><p><strong>${esc(head)}.</strong> ${g.where ? `The top-left (1) is ${esc(g.where)}. ` : ""}${esc(g.text)}</p>
    ${checks ? `<ul class="giant-checks">${checks}</ul>` : ""}
    <canvas class="map-pic" data-map="${esc(JSON.stringify({ loc: "Farm", x: g.tile[0] + 1, y: g.tile[1] + 1, radius: 7,
      marks: [{ x: g.tile[0], y: g.tile[1], kind: "square3", color: "#2B6A3E" },
        ...(g.missing || []).filter(([x, y]) => x !== g.tile[0] || y !== g.tile[1]).map(([x, y, l]) => ({ x, y, kind: "rect", color: "#C77700", label: l, inside: true })),
        { x: g.tile[0], y: g.tile[1], kind: "cross", label: "1" }] }))}"></canvas></div>`;
}

// A picture of a place, with a cross on the tile (or the marks given), drawn by drawMaps once it's in the page.
function spotPic([loc, x, y], label = "", marks = null) {
  return `<canvas class="map-pic" data-map="${esc(JSON.stringify({ loc, x, y, radius: 6, marks: marks || [{ x, y, kind: "cross", label: label.length < 28 ? label : "" }] }))}"></canvas>`;
}

// Draw every <canvas data-map> inside `root` with the game's own tiles (static/map.js).
function drawMaps(root) {
  if (!window.ValleyMap) return;
  root.querySelectorAll("canvas[data-map]").forEach((c) => {
    if (c.dataset.drawn || c.closest("details:not([open])")) return;
    c.dataset.drawn = "1";
    const o = JSON.parse(c.dataset.map);
    window.ValleyMap.drawArea(c, o.loc, o).catch(() => { c.replaceWith(Object.assign(document.createElement("p"), { className: "muted small", textContent: "The picture couldn't be drawn." })); });
  });
}

const views = {
  async route() {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    if (!$("#route-settings").childElementCount) drawSettings();
    await planRoute();
  },

  async dayPlan(ask = {}) {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    dayAsk = ask;
    if (!todayDone.date) { const m = await get("/api/meta"); loadDone(m.date); }
    const v = await get(`/api/today?${new URLSearchParams({ ...ask, done: [...todayDone].join(","), spouse: routeState.settings.spouse || "" })}`);
    lastDay = v;
    const h = v.head;
    $("#m-date").textContent = `${h.weekday}, ${h.date.replace(/, Year \d+/, "")}`;
    $("#m-glance").textContent = `${cap(h.weather)}, ${h.tomorrow} tomorrow · The spirits are ${h.mood}`;
    $("#t-gold").textContent = `${h.money.toLocaleString()}g`;
    const where = $("#t-where");
    if (!where.childElementCount) where.innerHTML = v.places.map((p) => `<option>${esc(p)}</option>`).join("");
    const e = v.energy, now = ask.energy ?? e.now;
    $("#t-energy").innerHTML = `<div class="meter-row"><strong>Energy</strong><strong>${now} / ${e.max}</strong></div><div class="bar-track"><span style="width:${Math.min(100, Math.round(now / e.max * 100))}%"></span></div>`;
    $("#t-warning").hidden = !v.warning;
    $("#t-warning").textContent = v.warning || "";
    $("#t-giant").hidden = !v.giant;
    $("#t-giant").innerHTML = v.giant ? `<h2>Giant crop</h2>${giantCard(v.giant)}<p class="muted small">Green outline: the square. Cross: the top-left (1). Orange: tiles to sow (S), hoe and sow (H), or pull up and sow (P).</p>` : "";
    drawMaps($("#t-giant"));
    $("#t-notes").hidden = !v.notes.length;
    $("#t-notes").textContent = v.notes.join(" ");
    drawNext(v);
    drawPack(v.pack);
    $("#t-skills").innerHTML = v.skills.map((k) => `<div class="skill"><div class="skill-name"><strong>${esc(cap(k.name))} ${k.level}</strong></div>${k.coming ? `<div class="small">${esc(levelLine(k.coming))}</div>` : ""}<div class="muted small">${k.next ? esc(cap(k.ways[0] || "")) : "Maxed"}</div><div class="bar-track thin"><span style="width:${Math.round(k.share * 100)}%"></span></div></div>`).join("");
  },

  async morning() {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    const r = await fetch("/api/morning", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(routeBody(routeState, "save")) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    const v = await r.json();
    morningView = v;
    drawPriorities(v.priorities);
    drawDay(v.day);
    const shown = new Set(v.day.blocks.flatMap((b) => b.lines));
    const notes = v.today.filter((x) => x.kind !== "dish");  // the plan and pack list already carry the jobs
    $("#m-first").innerHTML = notes.length ? "<ul class=\"list\">" + notes.map((x) =>
      `<li class="day-note${x.errand ? " clickable" : ""}"${x.errand ? ` data-errand="${esc(x.errand)}"` : ""}><b>${esc(x.title)}</b><span class="muted">${esc(x.text)}</span></li>`
    ).join("") + "</ul>" : '<p class="muted">Nothing special today.</p>';
    document.querySelectorAll("#m-first li[data-errand]").forEach((el) => el.addEventListener("click", () => showErrand(el.dataset.errand)));
    drawQuests(v.quests);
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
    todoRoute();
    const y = v.yesterday;
    $("#todo-review-box").hidden = !y;
    if (y) {
      $("#todo-review-head").textContent = `${y.label}: ${y.done} of ${y.total} done`;
      $("#todo-review").innerHTML = list(y.items.map((r) => li(esc(r.title),
        r.done === true ? "done" : r.done === "blocked" ? "couldn't: they were busy" : r.done === false ? (r.ticked ? "you ticked it" : "not done") : (r.ticked ? "ticked" : "can't tell"))));
    }
  },

  async plan() {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    const rs = routeState, body = routeBody(rs, rs.start);
    if (!body.targets.length && !body.nice.length) { drawNeeds(null); return; }
    $("#needs-head").textContent = "Adding it up…";
    const r = await fetch("/api/needs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    drawNeeds(await r.json());
  },

  async today() {
    const hours = await get("/api/hours");
    $("#hours").innerHTML = `<p class="sub">${esc(hours.date)}</p><ul class="list">` + hours.shops.map((s) =>
      `<li><span>${esc(s.shop)}</span><span>${s.open.length ? esc(s.open.join(", ")) : `<span class="unsure">${esc(s.closed)}</span>`}${unsure(s.sure)}</span></li>`
    ).join("") + "</ul>";
  },

  async sprinklers(crops) {
    const v = await get(`/api/layout${crops ? `?crops=${crops}` : ""}`);
    sprinklerView = v;
    if (!v.ready) { $("#sp-head").textContent = v.text; return; }
    $("#sp-head").textContent = `${v.sprinklers} Sprinklers water ${v.crops} crops`;
    $("#sp-need").textContent = v.short ? `You need ${v.short} more: ${v.need.join(" and ") || "you hold the bars, so craft them"}.` : "You have them all.";
    $("#sp-fit").textContent = `${v.to_hoe} tiles still to hoe. ${v.lost} of your hoed tiles fall outside the pattern.` +
      (v.scarecrow ? ` ${v.scarecrow} crops are out of the Scarecrow's reach: put a second one on the A.` : "");
    $("#sp-size").innerHTML = v.sizes.map((n) => `<option value="${n}" ${n === v.want ? "selected" : ""}>${n} crops</option>`).join("");
    drawSprinklers();
  },

  async crops() {
    const [v, pick, extras] = await Promise.all([get("/api/crops"), get("/api/picking"), get("/api/extras")]);
    $("#extras").innerHTML = `<ul class="list-plain">${extras.map((x) => `<li><strong>${esc(x.title)}.</strong> ${esc(x.text)}</li>`).join("")}</ul>`;
    $("#giants").innerHTML = (pick.giants.length ? pick.giants.map(giantCard).join("") : '<p class="muted">No square is on its way this season.</p>') +
      (pick.plans.length ? `<h3>Where to sow a block</h3>${pick.plans.map(giantCard).join("")}` : "") +
      (pick.giants.length || pick.plans.length ? '<p class="muted small">Green outline: the square. Cross: the top-left (1), to water and leave unpicked. Orange: tiles to sow (S), hoe and sow (H), or pull up and sow (P).</p>' : "");
    drawMaps($("#giants"));
    $("#waiting").innerHTML = pick.waiting.length ? `<ul class="list-plain">${pick.waiting.map((w) => `<li>${w.count} ${esc(w.crop)}: ${esc(w.now)} today, ${esc(w.best)} on ${esc(w.day)}${w.note ? `; ${esc(w.note)}` : ""}.</li>`).join("")}</ul>` : '<p class="muted">Everything ripe is at its best today.</p>';
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
    $("#mine-trees").innerHTML = m.trees.length ? list(m.trees.map((t) => li(`<b>${esc(t.fruit)}</b> · ${esc(t.where)}`, esc(t.text.replace(/, Year \d+/g, (y) => y))))) : '<p class="sub">No fruit trees planted.</p>';
  },

  async cook() {
    const v = await get("/api/cook");
    const g = (n) => n == null ? "?" : `${n.toLocaleString()}g`;
    const sign = (n) => n == null ? "can't tell" : `${n > 0 ? "+" : ""}${n.toLocaleString()}g`;
    const ings = (r) => r.ingredients.map((i) => `${i.need > 1 ? `${i.need} ` : ""}${esc(i.name)}${i.have ? (i.use ? ` <span class="sub">(worth ${i.each}g as ${esc(i.use)})</span>` : "") : i.buy != null ? ` <span class="sub">(buy ${i.buy}g)</span>` : ' <span class="sub">(none held)</span>'}`).join(", ");
    $("#cook-head").textContent = (v.kitchen ? "" : v.kitchen_days ? `Your kitchen is ready in ${v.kitchen_days} days. ` : "You need the kitchen (the first house upgrade) to cook. ") +
      "A dish sells for the same at the shipping bin or Pierre's. Each ingredient is valued at its best other use: sold as it is, or made into something by a machine you own (jar, keg, smoker, mayonnaise machine...) if that's worth more. Machines take time and you have only so many, so a machine's value is the best case. Cooking uses your backpack and fridge, so move ingredients out of chests first." +
      (v.total ? ` Cooking the ones that gain makes about ${v.total.toLocaleString()}g more than selling their ingredients.` : "") +
      (v.losers ? ` ${v.losers} of your recipes sell for less than their ingredients: cook those for a bundle, a quest, a gift or the energy, not for gold.` : "");
    const head = "<tr><th>Dish</th><th>Ingredients</th><th>Sells</th><th>Cheapest ingredients worth</th><th>Gain: first to last</th><th>You can make</th></tr>";
    const row = (r, extra) => `<tr><td><b>${esc(r.name)}</b>${r.wanted.length ? `<br><span class="also">for ${esc(r.wanted.join(", "))}</span>` : ""}</td><td>${ings(r)}</td>` +
      `<td>${g(r.sells)}</td><td>${g(r.cost)}</td><td class="${(r.profit || 0) > 0 ? "ok" : "bad"}">${sign(r.profit)}${r.worst != null && r.worst !== r.profit ? ` <span class="sub">to ${sign(r.worst)}</span>` : ""}</td><td>${extra(r)}</td></tr>`;
    const makes = (x) => x.can ? `${x.can}${x.worth && x.worth < x.can ? ` <span class="sub">(${x.worth} for a gain)</span>` : ""}` : "";
    $("#cook-now").innerHTML = v.now.length ? head + v.now.map((r) => row(r, makes)).join("") : '<tr><td class="sub">Nothing you can cook now beats selling its ingredients.</td></tr>';
    $("#cook-known").innerHTML = head + v.known.map((r) => row(r, makes)).join("");
    const Q = [[0, "Normal"], [1, "Silver"], [2, "Gold"], [4, "Iridium"]];
    $("#cook-quality").innerHTML = `<tr><th>Dish</th><th>Sells</th>${Q.map(([, n]) => `<th>${n}</th>`).join("")}<th>Cook with</th></tr>` +
      v.now.concat(v.known).map((r) => {
        const ok = Q.filter(([q]) => (r.by_quality[q] ?? -1) > 0).map(([, n]) => n.toLowerCase());
        const advice = !ok.length ? "never for gold: sell the ingredients" : ok.length === 4 ? "any quality" : `${ok[0]}${ok.length > 1 ? ` to ${ok[ok.length - 1]}` : ""} only`;
        return `<tr><td><b>${esc(r.name)}</b></td><td>${g(r.sells)}</td>` +
          Q.map(([q]) => { const x = r.by_quality[q]; return `<td class="${x == null ? "" : x > 0 ? "ok" : "bad"}">${x == null ? "?" : sign(x)}</td>`; }).join("") +
          `<td>${esc(advice)}</td></tr>`;
      }).join("");
    $("#cook-learn").innerHTML = "<tr><th>Dish</th><th>Gain each</th><th>How to learn it</th></tr>" + v.learn.map((r) =>
      `<tr><td><b>${esc(r.name)}</b></td><td class="ok">${sign(r.profit)}</td><td>${esc(r.learn)}</td></tr>`).join("");
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
    $("#sell-hints").innerHTML = v.hints.length ? v.hints.map((h) => `<div class="hint">` +
      `<div class="hint-head"><b>${esc(h.machine)}</b><span>+${h.gain_each.toLocaleString()}g each · about ${h.gain_total.toLocaleString()}g on the ${h.count} ${esc(h.name)} you'd put through it now</span></div>` +
      `<p class="sub">${esc(h.name)} → ${esc(h.product)}</p><ul class="list">` + h.steps.map((st) =>
        `<li><span>${esc(st.label)}</span><span class="sub">${[st.gold ? `${st.gold.toLocaleString()}g` : "", st.materials.join(", "), st.how].filter(Boolean).map(esc).join(" · ")}</span></li>`
      ).join("") + "</ul></div>"
    ).join("") : '<p class="sub">Nothing you don\'t already have would pay better right now.</p>';
  },

  async romance() {
    let target = "";
    try { target = localStorage.getItem("romanceTarget") || ""; } catch { target = ""; }
    const [v, today] = await Promise.all([
      get(`/api/romance?target=${encodeURIComponent(target)}`),
      target ? get(`/api/ask/villager/${encodeURIComponent(target)}`).then((c) => c.today) : Promise.resolve(null),
    ]);
    const sel = $("#romance-target");
    sel.innerHTML = '<option value="">Choose someone…</option>' + v.partners.map((p) =>
      `<option value="${esc(p.name)}">${esc(p.display)} (${p.hearts}♥${p.status !== "Friendly" ? `, ${esc(p.status)}` : ""})</option>`
    ).join("");
    sel.value = v.target || "";
    drawRomance(v, today);
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

const levelLine = (c) => `Level ${c.level}, ${c.sure ? "" : "about "}${c.date}${c.pick ? `: choose ${c.pick}` : c.unlocks ? `: ${c.unlocks}` : ""}`;
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

// "Loading…" over the page while a view waits for the server; shown only if it takes a moment, so quick
// loads don't flicker. Calls can nest: it stays up until the last one is done.
let busyCount = 0, busyTimer;
async function busy(text, work) {
  busyCount++;
  if (busyCount === 1) busyTimer = setTimeout(() => { $("#loading-text").textContent = text; $("#loading").hidden = false; }, 150);
  else $("#loading-text").textContent = text;
  try {
    return await work();
  } finally {
    if (--busyCount === 0) { clearTimeout(busyTimer); $("#loading").hidden = true; }
  }
}
const LOADING = { today: "Reading your save…", goals: "Planning the rest of the year…", farm: "Reading your farm…",
                  people: "Looking through your chests…", calendar: "Filling in the month…" };
// Old links and pointers still land in the right place.
const OLD = { morning: ["today"], todo: ["today"], crops: ["farm", "crops"], sell: ["farm", "sell"], cook: ["farm", "cook"],
              romance: ["people"], plan: ["goals", "plan"], route: ["goals", "route"], cart: ["calendar"], ahead: ["calendar"], sprinklers: ["farm", "sprinklers"] };
const SUBS = { sprinklers: () => views.sprinklers(), crops: () => views.crops(), sell: () => views.sell(), cook: () => views.cook(), route: () => views.route(), plan: () => views.plan() };

let sprinklerView = null;
const TILE_WORDS = { S: "Sprinkler", Q: "Quality Sprinkler", f: "Free once swapped", c: "Crop", n: "Crop, hoe this tile", X: "Your Scarecrow", A: "One more Scarecrow", x: "Something stands here", o: "Dirt left out", ".": "" };
function drawSprinklers() {
  const v = sprinklerView, later = $("#sp-later").checked, rows = (later ? v.later : v.now).rows;
  $("#sp-grid").style.gridTemplateColumns = `repeat(${rows[0].length}, 1fr)`;
  $("#sp-grid").innerHTML = rows.map((r) => [...r].map((t) => `<span class="sp-t sp-${t === "." ? "none" : t}" title="${TILE_WORDS[t]}">${"SQXA".includes(t) ? t : ""}</span>`).join("")).join("");
  $("#sp-key").innerHTML = [...new Set(rows.join(""))].filter((t) => t !== ".").map((t) => `<span class="sp-keyline"><span class="sp-t sp-${t}">${"SQXA".includes(t) ? t : ""}</span> ${TILE_WORDS[t]}</span>`).join("");
  const [x0, y0] = (later ? v.later : v.now).origin, w = rows[0].length, h = rows.length;
  const marks = [];
  rows.forEach((r, j) => [...r].forEach((t, i) => {
    if ("SQ".includes(t)) marks.push({ x: x0 + i, y: y0 + j, kind: "rect", color: t === "Q" ? "#1C4C74" : "#2B6A3E", label: t, inside: true });
    if (t === "A") marks.push({ x: x0 + i, y: y0 + j, kind: "cross", label: "Scarecrow" });
    if (t === "n") marks.push({ x: x0 + i, y: y0 + j, kind: "dot", color: "#C77700" });
  }));
  $("#sp-pic").innerHTML = `<canvas class="map-pic" data-map="${esc(JSON.stringify({ loc: "Farm", x: x0 + Math.floor(w / 2), y: y0 + Math.floor(h / 2), radius: Math.ceil(Math.max(w, h) / 2) + 1, scale: Math.max(w, h) > 24 ? 1 : 2, marks }))}"></canvas>`;
  drawMaps($("#sp-pic"));
  $("#sp-later-note").textContent = later ? `Swap the ${v.quality} marked Q for Quality Sprinklers, on the same tiles. ${v.quality_keep} old ones stay at the edges and ${v.freed} come free. No crop moves.` : "";
}

function showSub(name) {
  document.querySelectorAll(".sub-view").forEach((s) => { const peers = s.parentElement.querySelectorAll(":scope > .sub-view"); if ([...peers].some((p) => p.dataset.for === name)) s.hidden = s.dataset.for !== name; });
  document.querySelectorAll(".seg button").forEach((b) => { if (b.parentElement.parentElement.querySelector(`.sub-view[data-for="${name}"]`)) b.classList.toggle("on", b.dataset.sub === name); });
  return SUBS[name]();
}

const places = {
  async today() {
    await views.dayPlan(dayAsk);  // the plan first: the rest fills in behind it, without holding the page up
    views.morning().catch(() => {});
    views.todo().catch(() => {});
  },
  async farm(sub) {
    await showSub(sub || "crops");
    const m = await get("/api/crops").then((v) => v.mine);
    $("#farm-head").textContent = m.ready ? `${m.ready} crop${m.ready === 1 ? "" : "s"} ready to harvest` : `${m.total} crops growing`;
    $("#farm-sub").textContent = `${m.total} planted, so a dry day costs about ${m.total * 2} energy to water${m.dies ? `. ${m.dies} won't ripen before the season ends.` : "."}`;
  },
  async people() {
    const [q, day] = await Promise.all([get("/api/quests"), lastDay ? lastDay : views.dayPlan().then(() => lastDay)]);
    if (routeState && routeState.settings.spouse) { try { if (!localStorage.getItem("romanceTarget")) localStorage.setItem("romanceTarget", routeState.settings.spouse); } catch { /* fine */ } }
    await Promise.all([views.romance(), views.today()]);
    drawQuests(q);
    const talk = day.plan.find((x) => x.kind === "talk");
    $("#people-head").textContent = talk ? `${talk.title.replace("Talk to ", "See ")}: ${talk.why.split(";")[0]}` : "Who's around today";
    $("#people-sub").textContent = "Where people are, what to give them, and what to take where.";
    const row = (id, label, text) => `<button type="button" class="row-btn" data-errand="${id}"><strong>${esc(label)}</strong><span class="muted">${esc(text)}</span></button>`;
    $("#p-errands").innerHTML = row("cc", "Community Center", "what you hold for bundles") + row("gunther", "Gunther", "new finds for the Museum") + row("clint", "Clint", "geodes and tool upgrades") +
      row("birthdays", "Birthdays", "the next 7 days") + row("trees", "Fruit trees", "what's growing and when") +
      (seasonal.map((e) => row(e.id, e.label, "this season")).join(""));
    document.querySelectorAll("#p-errands [data-errand]").forEach((b) => b.addEventListener("click", () => showErrand(b.dataset.errand)));
  },
  async goals(sub) {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    if (!$("#route-settings").childElementCount) drawSettings();
    await planRoute();
    await showSub(sub || "route");
  },
  async calendar() {
    if (!routeState) routeState = loadRouteState(await get("/api/route/objectives"));
    const [day] = await Promise.all([lastDay ? lastDay : views.dayPlan().then(() => lastDay), drawMonth(calMonth.offset), views.cart()]);
    $("#a-bubbles").innerHTML = day.bubbles.map((b) => `<div class="pack-stop"><strong>${esc(b.place)}</strong><div class="muted">${b.spells.slice(0, 3).map(esc).join("<br>") || "None today"}</div></div>`).join("");
    $("#a-geodes").innerHTML = day.geodes.length ? day.geodes.map((g) => `<div>#${g.crack}: ${g.gives.map((x) => `${esc(x.geode)} gives ${x.stack > 1 ? `${x.stack} ` : ""}${esc(x.item)}`).join(", or ")}</div>`).join("") : '<p class="muted">No geodes held.</p>';
  },
};

const CAL_ICONS = {
  festival: ["M3 20 12 4l9 16zM12 4v16M8 20l4-7 4 7", "Festival"],
  passive: ["M9 3h6M8 6h8l2 5-2 7H8l-2-7zM12 18v3", "Market or fair"],
  derby: ["M3 12c4-6 10-6 14 0-4 6-10 6-14 0zM17 12l4-4v8zM8 11h.01", "Fishing event"],
  birthday: ["M4 20h16v-8H4zM8 12V8M12 12V8M16 12V8M4 16c2 2 4 2 6 0s4-2 6 0 3 1 4 0", "Birthday"],
  cart: ["M3 5h3l2 10h10l2-7H7M9 19h.01M17 19h.01", "Traveling Cart"],
  bookseller: ["M12 7c-2-2-5-2-8-2v14c3 0 6 0 8 2 2-2 5-2 8-2V5c-3 0-6 0-8 2zM12 7v14", "Bookseller"],
  green_rain: ["M5 19C5 9 11 5 20 4c0 10-4 15-13 15M5 21l8-9", "Green rain"],
  tv: ["M3 7h18v12H3zM8 3l4 4 4-4", "New recipe on TV"],
  rain: ["M7 15a4 4 0 1 1 1-8 5 5 0 0 1 9.6 1A3.5 3.5 0 0 1 17 15zM9 18l-1 3M13 18l-1 3M17 18l-1 3", "Rain"],
  storm: ["M7 14a4 4 0 1 1 1-8 5 5 0 0 1 9.6 1A3.5 3.5 0 0 1 17 14zM13 14l-3 4h4l-3 4", "Storm"],
  crops: ["M12 21V8M12 8C10 7 9 5 9 3c2 1 3 3 3 5zM12 8c2-1 3-3 3-5-2 1-3 3-3 5zM12 14c-2-1-4-1-5-3 2-.5 4 1 5 3zM12 14c2-1 4-1 5-3-2-.5-4 1-5 3z", "Crops ripe"],
  season: ["M7 3h10M7 21h10M8 3c0 5 8 6 8 9s-8 4-8 9M16 3c0 5-8 6-8 9s8 4 8 9", "Season ends"],
  quest: ["M6 4h11a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M9 9h6M9 13h6", "Quest deadline"],
  giant: ["M4 20h16M6 20c0-6 2-11 6-11s6 5 6 11M12 9V4M9 6l3-2 3 2", "Giant crop chance"],
  night: ["M20 14A8 8 0 1 1 10 4a6 6 0 0 0 10 10z", "Overnight on the farm"],
  order: ["M5 3h14v18H5zM9 7h6M9 11h6M9 15h4", "Special orders board"],
  level: ["M12 3l2.6 5.8 6.4.7-4.8 4.2 1.4 6.3-5.6-3.2-5.6 3.2 1.4-6.3L3 9.5l6.4-.7z", "New skill level"],
  bins: ["M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13", "Bins"],
};
const calMonth = { offset: 0, view: null, day: null };
const calIcon = (k) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${(CAL_ICONS[k] || CAL_ICONS.quest)[0]}"/></svg>`;
const CAL_SHOWN = 5;  // a phone's day cell holds no more than this; the day panel lists the rest

function drawDay(n, focus) {
  const d = calMonth.view.days[n - 1];
  calMonth.day = n;
  document.querySelectorAll(".cal-cell").forEach((c) => c.setAttribute("aria-pressed", String(Number(c.dataset.day) === n)));
  $("#cal-day").innerHTML = `<h2>${esc(d.date)}</h2>` + (d.items.length ? `<ul class="cal-items">${d.items.map((x, i) => `
    <li class="${x.important ? "vital" : ""} ${i === focus ? "focus" : ""}">
      <span class="cal-ic" aria-hidden="true">${calIcon(x.kind)}</span>
      <div><strong>${esc(x.title)}</strong>${x.important ? ' <span class="cal-flag">Important</span>' : ""}${unsure(x.sure)}
      ${x.text ? `<div class="muted">${esc(x.text)}</div>` : ""}</div></li>`).join("")}</ul>` : `<p class="muted">${d.past ? "Already gone." : "Nothing known for this day."}</p>`);
}

async function drawMonth(offset) {
  const v = await get(`/api/month?${new URLSearchParams({ offset, spouse: routeState.settings.spouse || "" })}`);
  calMonth.view = v; calMonth.offset = v.offset;
  const n = v.important.length;
  const days = new Set(v.important.map((x) => x.day)).size;
  $("#cal-head").textContent = n ? `${days} important day${days === 1 ? "" : "s"} in ${v.label.split(",")[0]}` : `Nothing vital in ${v.label.split(",")[0]}`;
  $("#cal-sub").textContent = "Pick any day to see what's on it.";
  $("#cal-month").textContent = v.label;
  $("#cal-prev").disabled = v.offset <= 0;
  $("#cal-next").disabled = v.offset >= v.max_offset;
  $("#cal-watch").innerHTML = v.watch && !v.watch.banner ? `<div class="alert ${v.watch.level === "green" ? "good" : ""}"><strong>${esc(v.watch.title)}.</strong> ${esc(v.watch.text)}</div>` : "";
  $("#cal-grid").innerHTML = v.weekdays.map((d) => `<div class="cal-wd">${d}</div>`).join("") + v.days.map((d) => {
    const vital = d.items.some((x) => x.important);
    const shown = d.items.slice(0, CAL_SHOWN);
    return `<button type="button" class="cal-cell ${d.past ? "past" : ""} ${d.today ? "today" : ""} ${vital ? "vital" : ""}" data-day="${d.day}"
      aria-label="${esc(d.date)}${d.today ? ", today" : ""}${vital ? ", important" : ""}: ${d.items.length ? esc(d.items.map((x) => x.title).join(", ")) : "nothing"}">
      <span class="cal-num">${d.day}${vital ? ' <span class="cal-bang" aria-hidden="true">!</span>' : ""}</span>
      <span class="cal-icons">${shown.map((x, i) => `<span class="cal-ic" data-i="${i}" title="${esc(x.title)}">${calIcon(x.kind)}</span>`).join("")}${d.items.length > CAL_SHOWN ? `<span class="cal-more">+${d.items.length - CAL_SHOWN}</span>` : ""}</span>
    </button>`;
  }).join("");
  $("#cal-important").innerHTML = n ? v.important.map((x) => `<button type="button" class="cal-jump" data-day="${x.day}"><span class="cal-ic">${calIcon(x.kind)}</span> <strong>${esc(x.date)}</strong> ${esc(x.title)}</button>`).join("") : '<p class="muted">Nothing that would be missed.</p>';
  $("#cal-key").innerHTML = Object.keys(CAL_ICONS).map((k) => `<span class="cal-keyline"><span class="cal-ic">${calIcon(k)}</span> ${CAL_ICONS[k][1]}</span>`).join("");
  const today = v.days.find((d) => d.today);
  drawDay((today || v.days.find((d) => d.items.some((x) => x.important)) || v.days[0]).day);
}

async function drawWatch() {
  const w = (await get("/api/watch")).cabbage;
  const b = $("#watch");
  b.hidden = !(w && w.banner);
  if (!b.hidden) {
    b.className = `watch ${w.level}`;
    b.innerHTML = `<div class="watch-in"><strong>${esc(w.title)}.</strong> ${esc(w.text)}</div>`;
  }
}

async function show(name) {
  const [place, sub] = OLD[name] || [name];
  if (location.hash.slice(1) !== name) history.replaceState(null, "", `#${name}`);
  closeAsk();  // choosing a place puts the search away, so the page you chose is what you see
  window.scrollTo(0, 0);
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.view === place));
  document.querySelectorAll(".view").forEach((s) => (s.hidden = s.id !== `view-${place}`));
  try {
    await busy(LOADING[place] || "Loading…", () => places[place](sub));
  } catch (e) {
    $(`#view-${place}`).insertAdjacentHTML("afterbegin", `<p class="alert red">Couldn't load this: ${esc(e.message)}</p>`);
  }
}

let seasonal = [];
async function start() {
  try {
    const m = await get("/api/meta");
    $("#status").textContent = m.save ? `${m.player}, ${m.farm} Farm, ${m.date}` : "No save found";
    seasonal = m.seasonal_errands || [];
  } catch (e) {
    $("#status").textContent = e.message;
  }
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  drawWatch().catch(() => {});
  $("#sp-later").addEventListener("change", drawSprinklers);
  $("#sp-size").addEventListener("change", (e) => busy("Fitting the pattern…", () => views.sprinklers(e.target.value)));
  $("#cal-prev").addEventListener("click", () => busy("Filling in the month…", () => drawMonth(calMonth.offset - 1)));
  $("#cal-next").addEventListener("click", () => busy("Filling in the month…", () => drawMonth(calMonth.offset + 1)));
  $("#cal-grid").addEventListener("click", (e) => {
    const cell = e.target.closest(".cal-cell");
    const ic = e.target.closest(".cal-ic");
    if (cell) drawDay(Number(cell.dataset.day), ic ? Number(ic.dataset.i) : undefined);
  });
  $("#cal-important").addEventListener("click", (e) => { const j = e.target.closest(".cal-jump"); if (j) drawDay(Number(j.dataset.day)); });
  document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => busy("Loading…", () => showSub(b.dataset.sub))));
  $("#romance-target").addEventListener("change", (e) => {
    try { localStorage.setItem("romanceTarget", e.target.value); } catch { /* fine */ }
    busy("Looking through your chests…", views.romance);
  });
  let timer;
  $("#cart-q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(searchCart, 250); });
  let askTimer;
  $("#ask-q").addEventListener("input", () => { clearTimeout(askTimer); askTimer = setTimeout(searchAsk, 200); });
  $("#ask-close").addEventListener("click", closeAsk);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAsk();
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); $("#ask-q").focus(); }
  });
  const first = location.hash.slice(1);
  show(places[first] || OLD[first] ? first : "today");  // a link can open a place: …/#goals
}

start();

$("#t-recalc").addEventListener("click", () => { $("#t-form").hidden = !$("#t-form").hidden; });
$("#t-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const ask = {};
  const time = $("#t-time").value;
  if (time) ask.time = Number(time.replace(":", ""));
  if ($("#t-energy-in").value !== "") ask.energy = Number($("#t-energy-in").value);
  ask.where = $("#t-where").value;
  await busy("Replanning your day…", () => views.dayPlan(ask));
  $("#t-form").hidden = true;
});
$("#t-reset").addEventListener("click", async () => {
  todayDone.clear(); saveDone();
  $("#t-time").value = ""; $("#t-energy-in").value = "";
  await busy("Reading your save…", () => views.dayPlan({}));
  $("#t-form").hidden = true;
});
