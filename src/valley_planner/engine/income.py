"""Gold pace: what the farm can earn between today and a deadline, from what's already there.

Counted, at the game's sale prices for this farmer (normal quality, a
cautious floor; better quality only adds):
- what you could sell now (the Sell tab's bin total);
- the crops in the ground: each harvest left before it dies at the season
  change (or the deadline), regrowing ones every RegrowDays;
- fruit trees: a fruit a day in season once grown;
- animals: one produce every DaysToProduce, the deluxe item at its chance
  for full happiness and today's friendship.
Then, separately, a planning estimate: replanting the tiles you farm now,
each time they come free, with the season's best-paying seed you can buy
(gold per tile per day after the seed's cost). Machines, fishing, mining
and foraging aren't counted: they're yours to add on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..facts.animals import Animal
from ..facts.conditions import SEASONS
from ..facts.sell import sell_price
from ..views import crops as crops_view
from ..views.farm import Farm

YEAR = 112


@dataclass
class Stream:
    label: str
    gold: int
    by_day: dict[int, int] = field(default_factory=dict)  # days played -> gold that day


def _season(d: int) -> str:
    return SEASONS[(d - 1) // 28 % 4]


def _price(farm: Farm, oid: str) -> int:
    info = farm.items.get(oid)
    if not info:
        return 0
    return sell_price(info.price, 0, farm.farmer, f"(O){oid}", info.name, info.category, info.type,
                      profit_margin=farm.save.profit_margin)


def _season_end(d: int, seasons: tuple[str, ...]) -> int:
    """Last day a crop standing on day d survives: the end of its run of seasons."""
    end = ((d - 1) // 28 + 1) * 28
    while _season(end + 1) in seasons and end - d < YEAR:
        end += 28
    return end


def project(farm: Farm, deadline: int, *, sell_now: int = 0) -> dict:
    s, today = farm.save, farm.save.days_played
    farming = s.skills.get("farming", 0)
    streams: list[Stream] = []
    if sell_now:
        streams.append(Stream("selling what you hold now", sell_now, {today: sell_now}))

    planted = Stream("crops in the ground", 0)
    tiles = 0
    for c in s.crops:
        if c.forage or c.dead or not c.harvest_id or c.harvest_id == "-1":
            continue
        info = farm.crops.get(c.seed_id) if c.seed_id else farm.crops.by_harvest.get(c.harvest_id)
        if not info:
            continue
        tiles += c.location == "Farm"
        greenhouse = c.location == "Greenhouse" or c.location.startswith("Island")
        last = deadline if greenhouse else min(deadline, _season_end(today, info.seasons))
        each = round(_price(farm, c.harvest_id) * info.expected_stack(farming))
        d = today + c.days_left
        while d <= last:
            planted.by_day[d] = planted.by_day.get(d, 0) + each
            planted.gold += each
            if not info.regrow:
                break
            d += info.regrow
    streams.append(planted)

    trees = Stream("fruit trees", 0)
    for t in s.fruit_trees:
        price = sum(_price(farm, f) for f in t.get("fruit_ids", [])[:1])
        for d in range(today + max(0, t.get("days_left", 0)), deadline + 1):
            if _season(d) in t.get("seasons", []) or t.get("location") == "Greenhouse":
                trees.by_day[d] = trees.by_day.get(d, 0) + price
                trees.gold += price
    streams.append(trees)

    herd = Stream("animal produce", 0)
    for d in s.animals:
        a = Animal.from_save(d)
        kind = farm.animals.kinds.get(a.type)
        if not kind or not kind.produce:
            continue
        odds = farm.animals.odds(a, professions=set(s.professions))
        plain = _price(farm, kind.produce[0][0])
        deluxe = _price(farm, kind.deluxe[0][0]) if kind.deluxe else plain
        each = round(odds["produce"] * ((1 - odds["deluxe"]) * plain + odds["deluxe"] * deluxe))
        start = today + max(0, kind.days_to_mature - a.age) + 1
        for day in range(start, deadline + 1, max(1, kind.days_to_produce)):
            herd.by_day[day] = herd.by_day.get(day, 0) + each
            herd.gold += each
    streams.append(herd)

    replant = _replant(farm, deadline, tiles)
    total = sum(x.gold for x in streams)
    return {"deadline": farm.label(deadline), "money": s.money, "streams": [_json(x) for x in streams],
            "counted": total, "with_money": s.money + total, "replant": replant,
            "by_day": _cumulative(streams, s.money, today, deadline)}


def _replant(farm: Farm, deadline: int, tiles: int) -> dict:
    """The planning estimate: the tiles you farm now, replanted with the best seed each season."""
    rows = crops_view.countdown(farm)["crops"]
    best = None
    for r in rows:
        if r["status"] == "too_late" or not r["seed_price"] or not r["harvests"]:
            continue
        span = max(1, r["grow"] + (r["harvests"] - 1) * (r["regrow"] or 0))
        per_day = (r["income"] - r["seed_price"]) / span
        if best is None or per_day > best[0]:
            best = (per_day, r)
    if not best or not tiles:
        return {"tiles": tiles, "gold": 0, "crop": "", "per_tile_day": 0}
    days_left = max(0, min(deadline, _season_end(farm.save.days_played, ())) - farm.save.days_played)
    gold = int(best[0] * days_left * tiles * 0.5)  # half the time: tiles come free as crops finish
    return {"tiles": tiles, "crop": best[1]["crop"], "per_tile_day": round(best[0], 1), "gold": gold,
            "note": "this season only; tiles free up as today's crops finish, so about half the days count"}


def _json(x: Stream) -> dict:
    return {"label": x.label, "gold": x.gold}


def _cumulative(streams: list[Stream], money: int, today: int, deadline: int) -> list[dict]:
    """Gold on hand by date (every 7 days), if everything counted is sold the day it's ready."""
    out, run = [], money
    for d in range(today, deadline + 1):
        run += sum(x.by_day.get(d, 0) for x in streams)
        if (d - today) % 7 == 0 or d == deadline:
            out.append({"day": d, "gold": run})
    return out


def afford_day(by_day: list[dict], need: int) -> int | None:
    """The first listed day the running total reaches `need`."""
    return next((x["day"] for x in by_day if x["gold"] >= need), None)
