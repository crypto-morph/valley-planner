"""The Crops tab: the season countdown (what you can still plant, and with what) and your crops in the ground.

Countdown: a crop planted today is ready `grow` days later (fewer with
Speed-Gro or the Agriculturist; see facts/crops.py). Outdoors a crop dies
at the change of season unless it also grows next season, so the last
harvest day is the end of its run of seasons. Seeds count as available when
a regular shop sells them today (Pierre's, JojaMart, the Oasis) or you hold
some; the cart is listed separately.

In the ground: from the save's crops. A crop dies overnight at the season
change if its location follows the valley's seasons (not the Greenhouse,
not the island, which is always summer) and it doesn't grow next season.
Missed water: last night's save (<save>_old) — a crop on the same tile that
grew no further overnight wasn't watered the day before.
"""

from __future__ import annotations

from collections import defaultdict

from ..facts.conditions import SEASONS, location_accessible
from ..facts.crops import AGRICULTURIST, SPEED_GRO, speed_boost
from ..facts.sell import sell_price
from .farm import REGULAR_SEED_SHOPS, Farm, date_label

SOON = 3  # days: "plant by …" turns urgent
SHOP_PLACE = {"Sandy": "Desert", "Joja": "JojaMart"}  # shops you can only use while their place is open
SEASONLESS = {"Greenhouse"}  # crops here ignore seasons
ALWAYS_SUMMER_PREFIX = "Island"  # the island's own season


def _location_season(location: str, season: str) -> str | None:
    """The season a location follows; None if crops there ignore seasons."""
    if location in SEASONLESS:
        return None
    return "summer" if location.startswith(ALWAYS_SUMMER_PREFIX) else season


def _run_end(seasons: tuple[str, ...], season: str) -> int | None:
    """Last day (counting this season's days 1-28 on) a crop can stand: None if it never dies of the season."""
    if all(s in seasons for s in SEASONS):
        return None
    i, end = SEASONS.index(season), 28
    while SEASONS[(i + 1) % 4] in seasons and end < 112:
        i, end = i + 1, end + 28
    return end


def countdown(farm: Farm) -> dict:
    s, w = farm.save, farm.when
    agri = AGRICULTURIST in s.professions
    held = farm.held()
    offers: dict[str, list] = defaultdict(list)
    for o in farm.shops.offers(w, profit_margin=s.profit_margin):
        if o.shop in REGULAR_SEED_SHOPS and o.available is not False and o.price \
                and location_accessible(SHOP_PLACE.get(o.shop, ""), w):
            offers[o.item].append(o)
    ferts = []
    for fid, boost in SPEED_GRO.items():
        qid = f"(O){fid}"
        sold = sorted(offers.get(qid, []), key=lambda o: o.price)
        ferts.append({"id": qid, "name": farm.name(qid), "boost": boost, "held": held.get(qid, 0),
                      "sold": [{"shop": o.shop, "price": o.price} for o in sold],
                      "available": bool(held.get(qid) or sold)})
    rows = []
    for seed, c in farm.crops.by_seed.items():
        if w.season not in c.seasons:
            continue
        qid = f"(O){seed}"
        sold = sorted(offers.get(qid, []), key=lambda o: o.price)
        have = held.get(qid, 0)
        if not sold and not have:
            continue  # you can't get the seeds now
        indoors_only = _denied_outdoors(farm.data.asset("Data/Crops").get(seed) or {})
        end = None if indoors_only else _run_end(c.seasons, w.season)
        base = c.grow_with(speed_boost(agriculturist=agri))
        horizon = end if end is not None else w.day + 112
        harvests = 0
        if w.day + base <= horizon:
            harvests = 1 + ((horizon - w.day - base) // c.regrow if c.regrow else 0)
        options = []
        for f in ferts:
            g = c.grow_with(speed_boost(f["id"], agriculturist=agri))
            options.append({"fertilizer": f["name"], "grow": g, "available": f["available"],
                            "ok_today": end is None or w.day + g <= end,
                            "last_day": date_label(w.season, end - g) if end is not None and end - g <= 28 else ""})
        price = int((farm.items.get(c.harvest).price if farm.items.get(c.harvest) else 0) or 0)
        each = sell_price(price, 0, farm.farmer, f"(O){c.harvest}", farm.name(f"(O){c.harvest}"),
                          farm.items.get(c.harvest).category if farm.items.get(c.harvest) else None,
                          profit_margin=s.profit_margin)
        income = round(harvests * c.expected_stack(s.skills.get("farming", 0)) * each)
        seed_price = sold[0].price if sold else 0
        last = None if end is None else end - base
        if last is None or w.day <= last:
            days = None if last is None else last - w.day
            status = "ok" if days is None or days > SOON else ("today" if days == 0 else "soon")
            nxt = SEASONS[(SEASONS.index(w.season) + 1) % 4]
            text = ("Indoors only: greenhouse, garden pots, or Ginger Island" if indoors_only else
                    "Grows all year" if last is None else "Last day to plant: today" if days == 0 else
                    f"Plant by {date_label(*_season_day(w.season, last))}"
                    + (f" (it carries on into {nxt.capitalize()})" if end and end > 28 else ""))
        else:
            fix = next((o for o in options if o["ok_today"] and o["available"]), None)
            fix_any = next((o for o in options if o["ok_today"]), None)
            if fix:
                status, text = "fertilizer", f"Only with {fix['fertilizer']} ({fix['grow']} days)"
            elif fix_any:
                status, text = "too_late", f"Too late: {fix_any['fertilizer']} would do it, but you have none to hand"
            else:
                status, text = "too_late", "Too late: it would die before it ripens"
        warn = ""
        if status != "too_late" and seed_price and harvests and income < seed_price:
            plural = "s" if harvests > 1 else ""
            warn = f"won't pay back: {harvests} harvest{plural} ≈ {income}g for a {seed_price}g seed"
        rows.append({"crop": farm.name(f"(O){c.harvest}"), "seed": farm.name(qid), "seed_id": qid, "grow": base,
                     "regrow": c.regrow or None, "carries": bool(end and end > 28), "status": status, "text": text,
                     "warn": warn, "harvests": harvests, "income": income, "sell_each": each, "held_seeds": have,
                     "seed_price": seed_price, "where": sold[0].shop if sold else "",
                     "options": [o for o in options if status in ("fertilizer", "too_late") or not o["ok_today"]]})
    order = {"today": 0, "soon": 1, "fertilizer": 2, "ok": 3, "too_late": 4}
    rows.sort(key=lambda r: (order[r["status"]], r["crop"]))
    return {"season": w.season.capitalize(), "day": w.day, "days_left": 28 - w.day, "crops": rows,
            "fertilizers": ferts, "agriculturist": agri}


def _denied_outdoors(crop: dict) -> bool:
    """A planting rule refuses it outdoors (cactus: indoors or the island only)."""
    return any(r.get("Result") == "Deny" and "LOCATION_IS_OUTDOORS" in (r.get("Condition") or "")
               and r.get("PlantedIn") in ("Any", "Ground") for r in crop.get("PlantableLocationRules") or [])


def _season_day(season: str, day: int) -> tuple[str, int]:
    i = SEASONS.index(season)
    while day > 28:
        i, day = i + 1, day - 28
    return SEASONS[i % 4], day


def mine(farm: Farm) -> dict:
    s, w = farm.save, farm.when
    nxt = SEASONS[(SEASONS.index(w.season) + 1) % 4]
    prev = farm.yesterday
    before = {(c.location, c.tile): c for c in (prev.crops if prev else []) if c.tile}
    wet = s.wet  # the valley's weather (the island has its own)
    groups: dict[tuple, dict] = {}
    missed: dict[str, int] = defaultdict(int)
    for c in s.crops:
        if c.forage or not c.harvest_id or c.harvest_id == "-1":
            continue
        name = farm.name(f"(O){c.harvest_id}")
        info = farm.crops.get(c.seed_id) if c.seed_id else farm.crops.by_harvest.get(c.harvest_id)
        here = _location_season(c.location, w.season)
        ripens = w.day + c.days_left
        rained_on = here == w.season and not c.in_pot  # outdoors in the valley
        if c.dead:
            status = "dead"
        elif c.ready:
            status = "ready"
        elif here == w.season and info and nxt not in info.seasons and ripens > 28:
            status = "dies"
        else:
            status = "growing"
        p = before.get((c.location, c.tile))
        stuck = bool(p and p.harvest_id == c.harvest_id and c.grown is not None and p.grown is not None
                     and c.grown <= p.grown and not c.dead)
        if stuck:
            missed[name] += 1
        thirsty = status in ("growing", "dies") and not c.watered and not (wet and rained_on)
        key = (name, c.location, status, ripens if status != "ready" else w.day)
        g = groups.setdefault(key, {"crop": name, "location": c.location, "status": status, "count": 0,
                                    "ripens": date_label(*_season_day(w.season, ripens))
                                    if status in ("growing", "dies") else "",
                                    "in_days": c.days_left, "thirsty": 0, "missed": 0, "fertilizer": set()})
        g["count"] += 1
        g["thirsty"] += int(thirsty)
        g["missed"] += int(stuck)
        if c.fertilizer:
            g["fertilizer"].add(farm.name(c.fertilizer))
    rows = [{**g, "fertilizer": sorted(g["fertilizer"])} for g in groups.values()]
    order = {"ready": 0, "dies": 1, "growing": 2, "dead": 3}
    rows.sort(key=lambda r: (order[r["status"]], r["in_days"], r["crop"]))
    return {"total": sum(r["count"] for r in rows), "ready": sum(r["count"] for r in rows if r["status"] == "ready"),
            "thirsty": sum(r["thirsty"] for r in rows),
            "dies": sum(r["count"] for r in rows if r["status"] == "dies"),
            "dead": sum(r["count"] for r in rows if r["status"] == "dead"),
            "missed": dict(missed), "compared": prev is not None, "rain": wet, "rows": rows}
