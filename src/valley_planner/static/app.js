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

// ----- Route: goals in priority order, planned for a fresh Year 1 -----
const SETTING_LABELS = {
  tiles: "Tiles you farm", wood_per_day: "Wood from a chopping day", floors_per_day: "Mines floors a day",
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
  routeTimer = setTimeout(planRoute, wait);
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

function drawNeeds(v) {
  const goals = v ? v.goals.filter((g) => g.tier !== "off") : [];
  if (!goals.length) {
    $("#needs-head").innerHTML = 'No goals chosen yet. Pick some on the <a href="#route" data-go="route">Route tab</a> and this adds up what they take.';
    $("#needs-tiles").innerHTML = $("#needs-where").innerHTML = "";
    $("#needs-choices-box").hidden = true;
    $("#needs-head a").addEventListener("click", (e) => { e.preventDefault(); show("route"); });
    return;
  }
  $("#needs-head").textContent = `Everything your goals need from ${v.today.replace(/, Year \d+/, "")} to ${v.end.replace(/, Year \d+/, "")}, added up. ` +
    "Open any line to see what it is for. Where an item can be got more than one way, the ways are joined by OR, and the one the route plans is ticked.";
  const res = v.resources.filter((x) => x.total > 0);
  const gold = res.find((x) => x.id === "gold"), bars = res.filter((x) => x.group ? x.group === "bars" : BARS.includes(x.id));
  const rest = res.filter((x) => x !== gold && !bars.includes(x));

  // The tiles: gold first and wide, then each material, the bars together, then the days
  const tile = (label, big, line, cls = "") => `<div class="ntile${cls}"><div class="n-lab">${esc(label)}</div><div class="n-big">${big}</div>${line ? `<div class="n-line">${line}</div>` : ""}</div>`;
  let tiles = "";
  if (gold) {
    const g = gold, end = v.end.replace(/, Year \d+/, "");
    tiles += `<div class="ntile wide"><div class="n-lab">Gold</div><div class="n-big">${amt(g.total, "g")}</div>` +
      `<div class="nmeter" role="img" aria-label="${esc(`${num(g.have)}g in hand, about ${about(g.expected || 0)}g more expected, ${num(g.short)}g short`)}">` +
      `<span class="m-have" style="width:${pct(g.have, g.total)}%"></span><span class="m-exp" style="width:${pct(g.expected || 0, g.total)}%"></span></div>` +
      `<div class="n-line"><b class="ok">${amt(g.have, "g")}</b> in hand` +
      (g.expected ? ` · <b class="exp">about ${about(g.expected)}g</b> more by ${esc(end)}${g.note ? ` ${esc(g.note)}` : ""}` : "") +
      (g.short > 0 ? ` · <b class="bad">about ${about(g.short)}g short</b>` : ' · <b class="ok">covered</b>') + "</div>" +
      (g.extra ? `<div class="n-line small">${esc(g.extra)}</div>` : "") + "</div>";
  }
  tiles += rest.map((x) => tile(x.label, amt(x.total, x.unit),
    [x.have ? `${amt(x.have, x.unit)} in hand` : "", x.days ? `about <b>${x.days} ${esc(x.days_label)}</b>` : "", esc(x.note)].filter(Boolean).join(" · "))).join("");
  if (bars.length) tiles += tile("Bars", bars.map((x) => `${num(x.total)} ${esc(x.label.replace(/ Bar$/, ""))}`).join(" · "),
    bars.map((x) => `${esc(x.label.replace(/ Bar$/, ""))}: ${esc(x.note)}`).join(", "), " wide mid");
  const d = v.days, spent = d.chop + d.stumps + d.mine + d.fish;
  if (spent) tiles += tile("Days", `${spent}`, [["chopping", d.chop], ["stumps", d.stumps], ["mining", d.mine], ["fishing", d.fish]]
    .filter(([, n]) => n).map(([k, n]) => `${k} ${n}`).join(" · ") + ` · of ${d.left} days left` +
    (spent > d.left ? ` <b class="bad">· ${spent - d.left} more than there are</b>` : ""));
  $("#needs-tiles").innerHTML = tiles;

  // Where it goes: a collapsible row per goal, its items under it
  const where = (x) => x.breakdown.map((b, i) => `<details class="ngoal"${i ? "" : " open"}><summary><span class="ng-row"><span>${esc(b.label)}${also(b.also)}</span>` +
    `<span>${amt(b.amount, x.unit)}</span></span>${bar(b.amount, x.total)}</summary><ul class="nitems">` + b.items.map((it) =>
      `<li><span>${esc(it.label)}${it.how ? `: ${esc(it.how)}` : ""}${also(it.also)}${it.this_year === false ? ' <span class="later">not this year</span>' : ""}</span><span>${amt(it.amount, x.unit)}</span></li>`
    ).join("") + "</ul></details>").join("");
  const wood = rest.find((x) => x.id === "wood"), others = [...rest.filter((x) => x !== wood), ...bars];
  const compact = others.map((x) => `<li><span><b>${esc(x.label)} ${amt(x.total, x.unit)}</b> · ` +
    esc(x.breakdown.flatMap((b) => b.items.map((it) => `${it.label.replace(/^The /, "the ")} ${num(it.amount)}`)).join(", ")) + "</span></li>").join("");
  $("#needs-where").innerHTML = (gold ? `<section class="parch panel"><h2 class="sign">Where the gold goes</h2>${where(gold)}</section>` : "") +
    (wood || others.length ? '<section class="parch panel">' + (wood ? `<h2 class="sign">Where the ${esc(wood.label)} goes</h2>${where(wood)}` : "") +
      (others.length ? `<h3>${esc(others.map((x) => x.label).join(", ").replace(/, ([^,]*)$/, " and $1"))}</h3><ul class="list ncompact">${compact}</ul>` : "") + "</section>" : "");

  // Choose how: each way as a card, joined by OR
  const TAG = { planned: "✓ PLANNED", luck: "LUCK", no: "✕ NOT THIS YEAR", later: "LATER", possible: "" };
  const card = (o, i) => {
    if (o.more) return `<button type="button" class="ncard more" aria-expanded="false" data-label="${esc(o.label)}" data-more="${esc(o.detail)}">${esc(o.label)}</button>`;
    let tag = o.tag || TAG[o.state] || "";
    const planned = o.planned ?? o.state === "planned";
    if (planned && !tag.startsWith("✓")) tag = "✓ " + tag;
    if (o.state === "no" && !tag.startsWith("✕")) tag = "✕ " + tag;
    const cls = planned ? (o.state === "luck" || o.odds != null ? "planned c-luck" : "planned") : o.state;  // planned on luck: amber, ticked
    const line = [o.detail, o.gold ? amt(o.gold, "g") : "", o.when].filter(Boolean).map(esc).join(" · ") + also(o.also);
    return `<div class="ncard c-${cls}${i ? "" : " first"}">${tag ? `<b class="c-tag">${esc(tag)}</b>` : ""}<b class="c-ttl">${esc(o.label)}</b>${line ? `<span>${line}</span>` : ""}</div>`;
  };
  $("#needs-choices-box").hidden = !v.choices.length;
  $("#needs-choices").innerHTML = v.choices.map((c) => `<div class="nchoice"><div class="nc-item"><b>${esc(c.item)}</b><br><span class="sub">${esc(c.where)}</span></div>` +
    `<div class="nc-ways">${c.options.map((o, i) => i ? `<span class="way"><span class="or">OR</span>${card(o, i)}</span>` : card(o, i)).join("")}</div></div>`).join("");
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

const views = {
  async route() {
    if (!routeState) {
      routeState = loadRouteState(await get("/api/route/objectives"));
      drawSettings();
    }
    await planRoute();
  },

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
    todoRoute();
    const y = v.yesterday;
    $("#todo-review-box").hidden = !y;
    if (y) {
      $("#todo-review-head").textContent = `${y.label}: ${y.done} of ${y.total} done`;
      $("#todo-review").innerHTML = list(y.items.map((r) => li(esc(r.title),
        r.done === true ? "done" : r.done === false ? (r.ticked ? "you ticked it" : "not done") : (r.ticked ? "ticked" : "can't tell"))));
    }
  },

  async plan() {
    const rs = routeState || loadRouteState(await get("/api/route/objectives"));
    const body = routeBody(rs, rs.start);
    if (!body.targets.length && !body.nice.length) { drawNeeds(null); return; }
    $("#needs-head").textContent = "Adding it up…";
    const r = await fetch("/api/needs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
    drawNeeds(await r.json());
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
  if (location.hash.slice(1) !== name) history.replaceState(null, "", `#${name}`);
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
  const first = location.hash.slice(1);
  show(views[first] ? first : "morning");  // a link can open a tab: …/#route
}

start();
