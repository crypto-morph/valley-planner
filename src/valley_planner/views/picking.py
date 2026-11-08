"""When to pick, and where a giant crop is coming: the harvest rolls are seeded by tile and day (facts/harvest.py).

Quality: a crop picked on a different day rolls a different quality, so one that isn't being replanted can wait
for its best day. A regrowing crop pays for waiting with a later next harvest, so that's said with it.
Giant crops: a ripe Cauliflower, Melon or Pumpkin (and the rest of Data/GiantCrops) whose roll hits that night,
with the same crop on all 9 tiles of its square, becomes a giant crop. The other 8 only need to be the same crop,
at any stage, so a near miss can be finished by sowing the gaps. Nobody has seen this in our saves yet.
"""

from __future__ import annotations

from collections import defaultdict

from ..facts import giant_plan, harvest, layout
from ..facts.conditions import date_of
from ..facts.walk import FARMHOUSE_DOOR
from .farm import Farm

QUALITY = {0: "normal", 1: "silver", 2: "gold", 4: "iridium"}
NIGHTS = 7  # how far ahead to look for giant crops
MOST_MISSING = 5  # gaps worth sowing for one


def _day(farm: Farm, dp: int) -> str:
    return farm.label(dp).rsplit(",", 1)[0]


def waiting(farm: Farm) -> list[dict]:
    """Ripe crops that come out better on a later day, grouped by crop and best day."""
    groups: dict[tuple, dict] = defaultdict(lambda: {"count": 0})
    for a in harvest.quality_ahead(farm.save, farm.data):
        if not a.worth_waiting:
            continue
        g = groups[(a.name, a.best_day, a.best, a.today, bool(a.regrows))]
        g["count"] += 1
    out = []
    for (name, day, best, now, regrows), g in sorted(groups.items(), key=lambda kv: kv[0][1]):
        out.append({"crop": name, "count": g["count"], "day": _day(farm, day), "best": QUALITY[best],
                    "now": QUALITY[now],
                    "note": "it regrows, so waiting also pushes back the next harvest" if regrows else ""})
    return out


LANDMARKS = (("Farmhouse", "F", "your house"), ("Shipping Bin", "B", "the Shipping Bin"), ("Chest", "#", "a Chest"),
             ("Scarecrow", "X", "your Scarecrow"), ("Greenhouse", "W", "the Greenhouse"))
SPRINKLERS = {"Sprinkler": layout.CROSS, "Quality Sprinkler": layout.RING,
              "Iridium Sprinkler": tuple((dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if dx or dy)}
GIANT_SEEDS = {"190": "474", "254": "479", "276": "490"}  # Cauliflower, Melon, Pumpkin: Pierre sells the seeds
TODAY_SOW_DAYS = 3  # Today shows a sowing plan from this many days before its sow-by date
LEGEND = ("1 the top-left: water it and don't pick it · G the square · S sow · H hoe and sow · P pull up what's there"
          " and sow · F your house · B Shipping Bin · # Chest · X Scarecrow · R Sprinkler · c other crops · o dirt")


def _mark(farm: Farm, t) -> str:
    """The letter for what stands on a tile, outside the square."""
    thing = farm.save.farm_objects.get(t, "")
    for name, letter, _words in LANDMARKS:
        if thing == name or (name == "Chest" and "Chest" in thing):
            return letter
    if "Sprinkler" in thing:
        return "R"
    return ""


def _landmark(farm: Farm, top: tuple[int, int]) -> str:
    """The top-left tile in words, from the nearest landmark you can see on the farm."""
    best = None
    if "Farmhouse" in farm.save.farm_objects.values():
        door = FARMHOUSE_DOOR
        best = (abs(door[0] - top[0]) + abs(door[1] - top[1]), door, "your front door")
    for t, thing in farm.save.farm_objects.items():
        for name, _letter, words in LANDMARKS:
            if name == "Farmhouse":
                continue  # the door, above, is the part you know
            if thing == name or (name == "Chest" and "Chest" in thing):
                d = abs(t[0] - top[0]) + abs(t[1] - top[1])
                if best is None or d < best[0]:
                    best = (d, t, words)
    if best is None:
        return ""
    _d, (lx, ly), words = best
    if words == "a Chest":
        words = _which_chest(farm, (lx, ly))
    dx, dy = top[0] - lx, top[1] - ly
    bits = [f"{abs(dy)} {'south' if dy > 0 else 'north'}" if dy else "", f"{abs(dx)} {'east' if dx > 0 else 'west'}"
            if dx else ""]
    return f"{' and '.join(b for b in bits if b)} of {words}"


def _which_chest(farm: Farm, tile: tuple[int, int]) -> str:
    """A Chest in a row of Chests, by its place in the row."""
    objs = farm.save.farm_objects
    x0 = x1 = tile[0]
    while "Chest" in objs.get((x0 - 1, tile[1]), ""):
        x0 -= 1
    while "Chest" in objs.get((x1 + 1, tile[1]), ""):
        x1 += 1
    n = x1 - x0 + 1
    if n == 1:
        return "your Chest"
    if tile[0] == x0:
        return f"the west end of your row of {n} Chests"
    if tile[0] == x1:
        return f"the east end of your row of {n} Chests"
    k = tile[0] - x0 + 1
    return f"Chest {k} from the west in your row of {n}"


def _picture(farm: Farm, top: tuple[int, int], missing=()) -> list[str]:
    """The ground around the square, wide enough to reach the nearest landmark: see LEGEND."""
    x0, y0 = top
    square = {(x0 + dx, y0 + dy) for dx in range(3) for dy in range(3)}
    missing = set(missing)
    crops = {c.tile for c in farm.save.crops if c.location == "Farm" and c.tile and not c.forage}
    xa, xb, ya, yb = x0 - 3, x0 + 5, y0 - 2, y0 + 4
    marks = [t for t in farm.save.farm_objects if _mark(farm, t) and _mark(farm, t) != "R"]
    if marks:  # stretch the picture to the nearest landmark, if it's close
        lx, ly = min(marks, key=lambda t: abs(t[0] - x0 - 1) + abs(t[1] - y0 - 1))
        if abs(lx - x0 - 1) <= 10 and abs(ly - y0 - 1) <= 8:
            xa, xb, ya, yb = min(xa, lx), max(xb, lx), min(ya, ly), max(yb, ly)

    def letter(t) -> str:
        if t == top:
            return "1"
        if t in missing:
            return "P" if t in crops else "S" if t in farm.save.hoed else "H"
        if t in square:
            return "G"
        return _mark(farm, t) or ("c" if t in crops else "o" if t in farm.save.hoed else ".")

    return ["".join(letter((x, y)) for x in range(xa, xb + 1)) for y in range(ya, yb + 1)]


def _letter(farm: Farm, t) -> str:
    """S sow, H hoe and sow, P pull up what's there and sow."""
    crops = {c.tile for c in farm.save.crops if c.location == "Farm" and c.tile and not c.forage}
    return "P" if t in crops else "S" if t in farm.save.hoed else "H"


def _watered(farm: Farm, tile) -> str:
    """Why the tile is watered today without the can, or ""."""
    s = farm.save
    if s.wet:
        return "the rain waters it today"
    for t, thing in s.farm_objects.items():
        reach = SPRINKLERS.get(thing)
        if reach and (tile[0] - t[0], tile[1] - t[1]) in reach:
            return f"your {thing} waters it"
    crop = next((c for c in s.crops if c.location == "Farm" and c.tile == tile), None)
    return "it's watered already" if crop and crop.watered else ""


def _checks(farm: Farm, hit) -> list[dict]:
    """What has to be true today for the square to turn giant on its night, each ticked or not."""
    today = farm.when.days_played
    crop = next((c for c in farm.save.crops if c.location == "Farm" and c.tile == hit.tile), None)
    out = []
    if hit.complete:
        out.append({"ok": True, "text": f"All 9 tiles hold {hit.key}."})
    else:
        out.append({"ok": hit.days_played - today > 1, "text": f"{len(hit.missing)} of the 9 tiles still need "
                    f"{hit.key} (the S, H and P tiles): sow them any day before you sleep on "
                    f"{_day(farm, hit.days_played - 1)}. They needn't grow; hoe their tiles the day you sow."})
    if crop is not None and crop.days_left > 0:
        out.append({"ok": True, "text": f"The top-left ripens on {_day(farm, today + crop.days_left)}. Water it "
                                        "every day until then, or it falls behind and misses the night."})
    wet = _watered(farm, hit.tile)
    out.append({"ok": bool(wet), "text": f"Top-left watered: {wet}." if wet else "Water the top-left (1) today."})
    out.append({"ok": True, "text": "Don't pick the top-left, or any of the 9, until the giant crop is there. A tile"
                                    " other than the top-left can be picked if you sow it again the same day."})
    if hit.days_played == today + 1:
        out.append({"ok": True, "text": "Tonight's the night: sleep as usual and it's there in the morning."})
    return out


def _free(farm: Farm, tiles) -> bool:
    """Every tile still to sow is open ground: no other crop and nothing standing there."""
    crops = {c.tile for c in farm.save.crops if c.location == "Farm" and c.tile and not c.dead}
    return all(t not in crops and t not in farm.save.farm_objects for t in tiles)


def _tracked(farm: Farm) -> list:
    """Squares on their way: complete ones up to the end of the season, near misses in the next week."""
    s = farm.save
    end = 28 - s.day + 1
    found, seen = [], set()
    for night in range(1, end):
        g = harvest.giant_tonight(s, farm.data, night=night)
        for hit in (*g.ready, *(h for h in g.incomplete if (night <= NIGHTS and len(h.missing) <= MOST_MISSING)
                                or _free(farm, h.missing))):
            if hit.tile in seen:
                continue
            seen.add(hit.tile)
            found.append(hit)
    return found


def _square_row(farm: Farm, hit) -> dict:
    day = _day(farm, hit.days_played)
    return {"crop": hit.key, "day": day, "days_played": hit.days_played, "complete": hit.complete,
            "sow": len(hit.missing), "sure": hit.sure, "where": _landmark(farm, hit.tile),
            "text": ("Leave all 9 in the ground until then." if hit.complete else
                     f"Sow {len(hit.missing)} more {hit.key} on the marked tiles first."),
            "checks": _checks(farm, hit), "rows": _picture(farm, hit.tile, hit.missing),
            "tile": list(hit.tile), "missing": [[x, y, _letter(farm, (x, y))] for x, y in hit.missing]}


def plans(farm: Farm, *, limit: int = 1) -> list[dict]:
    """Where to sow a block of each giant crop you can sow this week, so it turns giant soon after it ripens."""
    s, today = farm.save, farm.when.days_played
    entries = farm.data.asset("Data/GiantCrops")
    held = farm.held()
    crops = {c.tile for c in s.crops if c.location == "Farm" and c.tile and not c.forage}
    guards = layout.scarecrows(s.farm_objects)
    tops = None
    out = []
    for key, entry in entries.items():
        harvest_id = str(entry.get("FromItemId", "")).removeprefix("(O)")
        info = farm.crops.by_harvest.get(harvest_id)
        if info is None or (harvest_id not in GIANT_SEEDS and not held.get(f"(O){info.seed}")):
            continue
        sow_days = [d for d in range(today, today + 8) if date_of(d)[0] in info.seasons]
        if not sow_days:
            continue
        season_end = sow_days[0] + 28 - date_of(sow_days[0])[1]
        if tops is None:
            tops = giant_plan.candidates(s.hoed, s.farm_objects, crops, lambda t: farm.walker.open(("Farm", *t)))
        best = giant_plan.find(tops, key=key, chance=float(entry.get("Chance", 1.0)), game_id=farm.when.game_id,
                               sow_days=sow_days, grow=info.grow, last_day=season_end, hoed=s.hoed,
                               objects=s.farm_objects, guarded=lambda t: not layout.unguarded({t}, guards),
                               legacy=farm.when.legacy_random, limit=limit)
        for spot in best:
            missing = [t for t in spot.square]
            wait = (f" It ripens on {_day(farm, spot.ripe_day)} and waits {spot.wait} "
                    f"{'night' if spot.wait == 1 else 'nights'} for it." if spot.wait else "")
            seed = farm.name("(O)" + info.seed)
            out.append({"crop": key, "sow_by": _day(farm, spot.sow_day), "sow_days_played": spot.sow_day,
                        "day": _day(farm, spot.fires_day), "days_played": spot.fires_day,
                        "where": _landmark(farm, spot.tile),
                        "text": f"Sow 1 {seed} on the top-left (1) by {_day(farm, spot.sow_day)} and water it "
                                f"every day: it wins its roll overnight into {_day(farm, spot.fires_day)}.{wait} Sow "
                                f"the other 8 any day before you sleep on {_day(farm, spot.fires_day - 1)}: they "
                                "don't need to grow or be watered, just be there. Hoe their tiles on the day you sow "
                                "them (empty dirt can vanish overnight), and buy all 9 seeds now in case the shop's "
                                "shut that day."
                                + (" Sowing earlier is fine; later misses the night." if spot.sow_day > sow_days[0]
                                   else "")
                                + (f" {spot.unguarded} of the tiles are outside your Scarecrows' reach." if
                                   spot.unguarded else ""),
                        "rows": _picture(farm, spot.tile, missing), "tile": list(spot.tile),
                        "missing": [[x, y, _letter(farm, (x, y))] for x, y in missing]})
    return out


def giants(farm: Farm) -> list[dict]:
    """Giant-crop squares on their way, each with today's checks and a picture."""
    return [_square_row(farm, hit) for hit in _tracked(farm)]


def watch(farm: Farm) -> dict | None:
    """Today's giant-crop job: the square on its way, checked, or else a block to sow in the next few days."""
    squares = giants(farm)
    if squares:
        return {"kind": "square", **squares[0]}
    soon = [p for p in plans(farm, limit=1) if p["sow_days_played"] - farm.when.days_played <= TODAY_SOW_DAYS]
    return {"kind": "plan", **soon[0]} if soon else None
