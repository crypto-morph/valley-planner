"""The valley on one page: today's places of interest and the planned walk, for static/world.js to draw on the maps.

`view(farm)` (GET /api/world) returns
- `locations`: the maps to switch between ({id, name, count}), the main outdoor ones first;
- `pois`: places of interest ({id, loc, x, y, kind, layer, title, why, time?, n?, icon?}); kinds: stop (numbered
  by plan order, `n`), forage, dig, bin, bubbles, pan, cart, bookseller, night, giant, shop (layer "doors");
- `villagers`: where each villager is over the day ({name, icon?, stops: [{t, time, loc, x, y, where}]}, t in
  minutes after midnight, indoors drawn at the building's door);
- `route`: today's walk ({stop, home, lines: [{loc, points}]}) and `exits`: the map edges you can walk off
  ({loc, x, y, to, tx, ty}, one per edge and neighbour);
- `start`: {loc, x, y, time} where the plan starts, `focus`: the location of the next stop.

Every source is optional: a forecast we can't make leaves its places off rather than the whole map.
"""

from __future__ import annotations

import logging

from ..facts import artifact_spots, night_events
from ..facts.conditions import clock_of, minutes_of
from ..facts.schedules import Situation, time_label
from ..facts.walk import FARMHOUSE_DOOR, OUTDOORS
from .farm import Farm

MAIN = ("Farm", "BusStop", "Town", "Forest", "Beach", "Mountain", "Backwoods", "Railroad")
DAY_START, DAY_END = 6 * 60, 26 * 60
log = logging.getLogger(__name__)


def _minutes(game_time: int) -> int:
    return minutes_of(int(game_time))


def _clock(minutes: int) -> str:
    return time_label(clock_of(minutes))


def from_day(day: dict) -> tuple[list[dict], list[dict], dict]:
    """(pois, route, start) from the day plan (views/today.view) alone: its stops, what's on the way, bubbles,
    the giant-crop square."""
    pois: list[dict] = []
    plan = day.get("plan") or []
    for i, row in enumerate(plan):
        spot = row.get("spot") or (["Farm", *FARMHOUSE_DOOR] if row.get("kind") == "farm" else None)
        if not spot:
            continue
        pois.append({"id": f"stop:{i}", "plan_id": row.get("id"), "loc": spot[0], "x": spot[1], "y": spot[2],
                     "kind": "stop", "layer": "route", "n": i + 1, "title": row.get("title", ""),
                     "why": row.get("why", ""), "time": row.get("time", "")})
    for p in day.get("passing") or []:
        loc, x, y = p["spot"]
        to = plan[p["stop"]]["title"] if p["stop"] < len(plan) else "home"
        kind = "dig" if p["title"].startswith("Hoe ") else "forage"
        pois.append({"id": f"passing:{loc}:{x}:{y}", "loc": loc, "x": x, "y": y, "kind": kind, "layer": "places",
                     "title": p["title"], "why": f"On the way to stop {p['stop'] + 1} ({to}): about {p['gold']}g"
                     if p["stop"] < len(plan) else f"On the way home: about {p['gold']}g"})
    fishing = day.get("fishing") or {}
    bubbles: dict[str, dict] = {}  # one place per tile: a spot can bubble twice a day
    for group in day.get("bubbles") or []:
        words = group.get("spells") or []
        for j, b in enumerate(group.get("spots") or []):
            spell = (words[j] if j < len(words) else b.get("label", "")).split(", ")[0]
            key = f"bubbles:{b['loc']}:{b['x']}:{b['y']}"
            if key in bubbles:
                bubbles[key]["time"] += f", {spell}"
                continue
            why = "Fish bite much faster in them"
            if fishing.get("location") == b["loc"] and fishing.get("fish"):
                why += f". Bundle fish here today: {', '.join(fishing['fish'])}"
            bubbles[key] = {"id": key, "loc": b["loc"], "x": b["x"], "y": b["y"], "kind": "bubbles",
                            "layer": "places", "title": "Fish bubbles", "why": why, "time": spell}
    pois += bubbles.values()
    pans: dict[str, dict] = {}
    for group in day.get("pans") or []:
        words = group.get("spells") or []
        for j, b in enumerate(group.get("spots") or []):
            spell = (words[j] if j < len(words) else b.get("label", "")).split(", ")[0]
            key = f"pan:{b['loc']}:{b['x']}:{b['y']}"
            if key in pans:  # the same tile again later in the day
                pans[key]["time"] += f"; {spell}"
                continue
            pans[key] = {"id": key, "loc": b["loc"], "x": b["x"], "y": b["y"], "kind": "pan", "layer": "places",
                         "title": "Pan spot", "time": spell,
                         "why": "Ore shimmering in the water: pan it from the shore for ore, coal or gems. Forecast "
                                "as if nobody pans: panning one changes the later spots on this map"}
    pois += pans.values()
    giant = day.get("giant")
    if giant and giant.get("tile"):
        x, y = giant["tile"]
        title = (f"Giant {giant['crop']}: sow by {giant['sow_by']}" if giant.get("kind") == "plan"
                 else f"Giant {giant['crop']} on {giant.get('day', '')}")
        pois.append({"id": "giant", "loc": "Farm", "x": x, "y": y, "kind": "giant", "layer": "places",
                     "title": title, "why": giant.get("text", ""), "w": 3, "h": 3})
    route = [{"stop": leg["stop"], "home": leg["stop"] >= len(plan), "lines": leg["lines"]}
             for leg in day.get("route") or []]
    first = next((ln for leg in route for ln in leg["lines"] if ln["points"]), None)
    start = ({"loc": first["loc"], "x": first["points"][0][0], "y": first["points"][0][1]} if first
             else {"loc": "Farm", "x": FARMHOUSE_DOOR[0], "y": FARMHOUSE_DOOR[1]})
    start["time"] = plan[0]["time"] if plan else ""
    return pois, route, start


def _forage(farm: Farm, taken: set[str]) -> list[dict]:
    from .today import BERRIES, _forage_why
    s, held = farm.save, farm.held()
    out = []
    for f in s.forage:
        key = f"{f.location}:{f.tile[0]}:{f.tile[1]}"
        if f"forage:{key}" in taken or f"passing:{key}" in taken:
            continue
        why, _value = _forage_why(farm, f.item, held)
        out.append({"id": f"forage:{key}", "loc": f.location, "x": f.tile[0], "y": f.tile[1], "kind": "forage",
                    "layer": "places", "title": f.name, "why": why[:1].upper() + why[1:], "qid": f.item})
    berry = BERRIES.get(s.season)
    for b in s.bushes if berry else []:
        key = f"{b.location}:{b.tile[0]}:{b.tile[1]}"
        if f"passing:{key}" in taken:
            continue
        out.append({"id": f"bush:{key}", "loc": b.location, "x": b.tile[0], "y": b.tile[1], "kind": "forage",
                    "layer": "places", "title": f"{farm.name(berry)} bush", "why": "Shake it for berries",
                    "qid": berry})
    return out


def _digs(farm: Farm, taken: set[str]) -> list[dict]:
    out = []
    for sp in artifact_spots.spots(farm.save, farm.data):
        if sp.reachable is False or f"dig:{sp.location}:{sp.tile[0]}:{sp.tile[1]}" in taken:
            continue
        names = " and ".join(f"{d.count} {d.name}" if d.count > 1 else d.name for d in sp.drops) or "nothing known"
        kind = "Worm tile" if sp.kind == "artifact" else "Seed spot"
        first = next((d.id for d in sp.drops if d.id), None)
        why = f"Hoe it for {names}" + ("" if sp.sure else f" (probably: {'; '.join(sp.notes)})" if sp.notes
                                      else " (probably)")
        out.append({"id": f"dig:{sp.location}:{sp.tile[0]}:{sp.tile[1]}", "loc": sp.location, "x": sp.tile[0],
                    "y": sp.tile[1], "kind": "dig", "layer": "places", "title": kind, "why": why, "qid": first})
    return out


def _bins(farm: Farm, taken: set[str]) -> list[dict]:
    marks = {m.name.removeprefix("Garbage:"): m for m in farm.walker.landmarks.get("Town", [])
             if m.name.startswith("Garbage:")}
    out = []
    for c in farm.bins.day(farm.save, farm.when):
        if not c.loot or c.can not in marks or f"bin:{c.can}" in taken:
            continue
        m = marks[c.can]
        other = f", or {c.other.label} once you've opened enough cans" if c.other else ""
        out.append({"id": f"bin:{c.can}", "loc": "Town", "x": m.x, "y": m.y, "kind": "bin", "layer": "places",
                    "title": f"Garbage can: {c.place}", "why": f"{c.loot.label} in it today{other}. Check nobody's "
                    "close by first", "qid": c.loot.item})
    return out


def _calendar(farm: Farm) -> list[dict]:
    """The Traveling Cart and the Bookseller on their days."""
    from .morning import _cart, _cart_counter
    out = []
    for e in farm.calendar.day(farm.when, today_days_played=farm.save.days_played):
        if e.kind == "cart":
            card = _cart(farm)
            if card.get("spots"):
                at = _cart_counter(farm)
                out.append({"id": "cart", "loc": "Forest", "x": at["x"], "y": at["y"], "kind": "cart",
                            "layer": "places", "title": "The Traveling Cart", "why": card["text"][:1].upper()
                            + card["text"][1:], "time": "6:00 AM to 8:00 PM"})
        elif e.kind == "bookseller":
            from .month import bookseller_text
            out.append({"id": "bookseller", "loc": "Town", "x": 109, "y": 27, "kind": "bookseller",
                        "layer": "places", "title": "The Bookseller", "why": bookseller_text(farm,
                                                                                      farm.save.days_played)[0]})
    return out


def _night(farm: Farm) -> list[dict]:
    """Tonight's farm event, where it lands."""
    from .month import NIGHT_WORDS
    nights = night_events.nights(farm.save, farm.data, count=1, festivals=set(farm.calendar.festivals))
    n = nights[0] if nights else None
    if not n or not n.tile or n.kind not in NIGHT_WORDS:
        return []
    title, text = NIGHT_WORDS[n.kind]
    if n.kind == "meteorite" and not n.lands:
        text = f"Only if its landing spot is clear: right now it's {n.what or 'blocked'}."
    return [{"id": "night", "loc": "Farm", "x": n.tile[0], "y": n.tile[1], "kind": "night", "layer": "places",
             "title": f"Tonight: {title}", "why": text + ("" if n.sure else " (not certain yet)"),
             **({"w": 2, "h": 2} if n.kind == "meteorite" else {})}]


def _doors(farm: Farm) -> list[dict]:
    """Shop and house doors on the outdoor maps, with today's opening hours where they keep any."""
    hours = {h["id"]: h for h in farm.hours_today()}
    out = []
    for loc, marks in farm.walker.landmarks.items():
        for m in marks:
            if m.name.startswith("Garbage:"):
                continue
            h = hours.get(m.name)
            why = (f"Closed today: {h['closed']}" if h and h.get("closed") else
                   f"Open {', '.join(h['open'])}" if h and h.get("open") else "")
            out.append({"id": f"door:{loc}:{m.x}:{m.y}", "loc": loc, "x": m.x, "y": m.y + 1, "kind": "shop",
                        "layer": "doors", "title": h["shop"] if h else farm.place(m.name), "why": why})
    return out


def _outside(farm: Farm, location: str) -> tuple[str, int, int] | None:
    from .today import _building_door
    return None if location in OUTDOORS or location == "Railroad" else _building_door(farm, location)


def _villagers(farm: Farm) -> list[dict]:
    """Each villager's day as a list of where they are from when: the first schedule when it's a coin flip."""
    from ..pictures import shared
    s, w = farm.save, farm.when
    chars = farm.schedules.characters
    try:
        tex = shared(farm.data.install.content, farm.data.cache)
    except (AttributeError, OSError):
        tex = None
    out = []
    for name, c in chars.items():
        if not farm.schedules.raw(name) or c.get("CanSocialize") == "FALSE":
            continue
        f = s.friends.get(name)
        days = farm.schedules.today(name, Situation(w, hearts=f.hearts if f else 0, raining=s.wet,
                                                    married=bool(f and f.status == "Married")))
        if not days:
            continue
        d = days[0]
        first = d.start or None
        home = farm.schedules.home(name, w)
        begin = (first.location, first.x, first.y) if first else home
        stops = [(DAY_START, *begin)] + [(_minutes(st.time), st.location, st.x, st.y) for st in d.stops]
        rows = []
        for t, loc, x, y in stops:
            door = _outside(farm, loc)
            at = door or (loc, x, y)
            if rows and door and rows[-1]["where"] == f"inside {farm.place(loc)}":
                continue  # still indoors in the same building
            rows.append({"t": t, "time": _clock(t), "loc": at[0], "x": at[1], "y": at[2],
                         "where": f"inside {farm.place(loc)}" if door else farm.place(loc),
                         "outdoors": door is None})
        icon = None
        if tex is not None:
            try:
                asset = f"Characters/{c.get('TextureName') or name}"
                sw, sh = tex.size(asset)
                icon = {"url": tex.url(asset), "x": 0, "y": 0, "w": 16, "h": 16, "sw": sw, "sh": sh}
            except Exception:  # noqa: BLE001 - a villager without a picture is still on the map
                icon = None
        display = farm.data.text(c.get("DisplayName")) or name
        out.append({"name": display, "id": name, "icon": icon, "unsure": d.chance < 1, "stops": rows})
    return out


def _exits(farm: Farm) -> list[dict]:
    """One arrow per map edge and neighbour: the middle tile of the exit strip."""
    groups: dict[tuple[str, str], list] = {}
    for (loc, x, y), (to, tx, ty) in farm.walker.exits.items():
        groups.setdefault((loc, to), []).append((x, y, tx, ty))
    out = []
    for (loc, to), tiles in groups.items():
        tiles.sort()
        x, y, tx, ty = tiles[len(tiles) // 2]
        out.append({"loc": loc, "x": x, "y": y, "to": to, "tx": tx, "ty": ty, "name": farm.place(to)})
    return out


def _out_of_reach(farm: Farm, pois: list[dict]) -> list[dict]:
    """Say so on the places you can't walk to today (the tide pools before the bridge is mended…)."""
    walker = farm.walker
    reach = walker.reach(("Farm", *FARMHOUSE_DOOR))
    for p in pois:
        if p["layer"] != "places" or p["kind"] in ("bubbles", "pan") or p["loc"] not in OUTDOORS:
            continue  # bubbles are cast to, and pan spots panned, from the shore
        if walker.path(reach, (p["loc"], p["x"], p["y"])) is None:
            p["reach"] = False
            p["why"] = (p["why"] + ". " if p["why"] else "") + "You can't walk there today"
    return []


def _safely(fn, *args) -> list[dict]:
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - one forecast we can't make shouldn't blank the map
        log.exception("world: %s failed", fn.__name__)
        return []


GOAL_STOPS = {"cc": "Community Center", "quest": "Help Wanted", "museum": "Museum", "clint": "Geodes"}
ACTIVITY = ("bubbles", "pan", "dig", "forage", "bin", "cart", "bookseller", "night", "giant")  # icons, in this order


def _worth(farm: Farm, pois: list[dict], day: dict) -> None:
    """Give each place of interest its gold (what picking it up is worth) and the goal it moves on, if any."""
    from .today import _forage_why, _price
    held = farm.held()
    spouse = next((r["id"].split(":", 1)[1] for r in day.get("plan") or [] if r.get("id", "").startswith("talk:")
                   and "gift" in (r.get("why") or "") + (r.get("title") or "")), "")
    for p in pois:
        qid, kind = p.get("qid"), p["kind"]
        if kind in ("forage", "dig", "bin") and qid:
            why, value = _forage_why(farm, qid, held)
            p["gold"] = _price(farm, qid) * (2 if p["title"].startswith("2 ") else 1)
            if why.startswith("keep it for the "):
                p["goal"] = why.removeprefix("keep it for the ").replace(" bundle", "") + " bundle"
        elif kind == "stop":
            pid = p.get("plan_id") or ""
            if pid in GOAL_STOPS:
                p["goal"] = GOAL_STOPS[pid]
            elif pid.startswith(("talk:", "give:")):
                who = pid.split(":", 1)[1]
                p["goal"] = f"{who}" + (" (a gift)" if who == spouse or "gift" in p.get("why", "") else "")
            elif pid.startswith("forage:") and "bundle" in p.get("why", ""):
                p["goal"] = p["why"].split("for the ", 1)[-1].replace(" bundle", "") + " bundle"


def _locked(farm: Farm, loc: str) -> str:
    """What still has to happen before you can go there ("" when you can)."""
    from ..facts.access import place_open
    ok, what = place_open(loc, farm.when)
    return "" if ok else what


def summary(pois: list[dict], loc: str) -> dict:
    """One place at a glance: the goals it moves on, the gold lying about, and what's happening there today."""
    here = [p for p in pois if p["loc"] == loc and p["layer"] != "doors" and p.get("reach") is not False]
    goals = sorted({p["goal"] for p in here if p.get("goal")})
    kinds = {p["kind"] for p in here}
    return {"goals": goals, "gold": sum(p.get("gold", 0) for p in here),
            "icons": [k for k in ACTIVITY if k in kinds], "stops": sorted(p["n"] for p in here if p.get("n"))}


def view(farm: Farm, day: dict | None = None, **today_args) -> dict:
    """Today on the maps; `day` is today's plan if already worked out (else views/today.view with today_args)."""
    if day is None:
        from . import today
        day = today.view(farm, **today_args)
    pois, route, start = from_day(day)
    taken = {p["plan_id"] for p in pois if p.get("plan_id")} | {p["id"] for p in pois}
    for fn in (_forage, _digs, _bins):
        pois += _safely(fn, farm, taken)
    for fn in (_calendar, _night, _doors):
        pois += _safely(fn, farm)
    items = {}
    for fn in (_forage, _digs, _bins):  # what lies on each tile, for the stops and spares that land on one
        items.update({(p["loc"], p["x"], p["y"]): p["qid"] for p in _safely(fn, farm, set()) if p.get("qid")})
    for p in pois:
        p.setdefault("qid", items.get((p["loc"], p["x"], p["y"])) if p["kind"] in ("stop", "forage") else None)
    for p in pois:
        if p.get("qid"):
            p["icon"] = farm.icon(p["qid"])
    _safely(_out_of_reach, farm, pois)
    _safely(_worth, farm, pois, day)
    villagers = _safely(_villagers, farm)
    exits = _safely(_exits, farm)
    counts: dict[str, int] = {}
    for p in pois:
        if p["layer"] != "doors":
            counts[p["loc"]] = counts.get(p["loc"], 0) + 1
    seen = list(MAIN) + sorted({p["loc"] for p in pois} - set(MAIN))
    seen += sorted({ln["loc"] for leg in route for ln in leg["lines"]} - set(seen))
    stops = [p for p in pois if p["kind"] == "stop"]
    focus = stops[0]["loc"] if stops else start["loc"]
    return {"date": (day.get("head") or {}).get("date", ""), "weather": (day.get("head") or {}).get("weather", ""),
            "locations": [{"id": loc, "name": farm.place(loc), "count": counts.get(loc, 0),
                           **summary(pois, loc), "locked": _locked(farm, loc)} for loc in seen],
            "pois": pois, "villagers": villagers, "route": route, "exits": exits, "start": start, "focus": focus,
            "day": [DAY_START, DAY_END]}
