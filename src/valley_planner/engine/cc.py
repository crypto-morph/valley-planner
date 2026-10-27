"""The Community Center by a deadline: for every slot still open, how and when you can fill it.

For each open ingredient we look at every source (facts/sources.py) and scan
the days from today to the deadline:
- crop: plant on a day its seeds can be had (held, or a shop's condition
  allows it that day) and harvest `grow` days later, every day of it in the
  crop's seasons; the earliest harvest and the last day you can plant.
- fish / forage: any day in its seasons, once its place is open.
- shop: any day its condition holds (festival stalls on the festival's days).
- animal: once you have that animal (and it's grown), or after buying one.
- machine / cooking: once you own the machine or know the recipe and hold
  the inputs.
- cart / monster: random; the chance of at least one by the deadline.
A slot is "have" if the bundle plan has already set aside what you hold.
Pick-N bundles use the slots you can fill soonest. Everything stays a
day number (Spring 1, Year 1 = 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..facts.access import place_open
from ..facts.bundles import JOJA, VAULT
from ..facts.conditions import When, check
from ..facts.sources import Source, Sources, seasons_text
from ..views.farm import Farm
from .unlocks import Unlock, Unlocks

YEAR = 112
CART_WEEKDAYS = (5, 0)  # Friday, Sunday (day % 7)


@dataclass
class Way:
    source: Source
    earliest: int | None  # day you could have it
    latest_start: int | None  # last day to start (plant, go fishing…) and still have it by the deadline
    blocked: list[str] = field(default_factory=list)  # what has to happen first
    odds: float | None = None  # random sources: chance of at least one by the deadline
    sure: bool = True  # False: a condition we can't decide, or a source whose odds aren't modelled
    unlocks: list[str] = field(default_factory=list)  # unlock keys behind `blocked` (engine/unlocks.py)


@dataclass
class Slot:
    bundle: str
    room: str
    item: str  # qualified id or "category -5"
    name: str
    count: int
    quality: int
    have: bool
    ways: list[Way]
    best: Way | None = None

    @property
    def status(self) -> str:
        if self.have:
            return "have"
        if self.best is None or (self.best.earliest is None and self.best.odds is None):
            return "stuck"
        if self.best.blocked:
            return "blocked"
        if self.best.odds is not None:
            return "luck"
        return "ok" if self.best.sure else "maybe"


def _season_of(d: int) -> str:
    return ("spring", "summer", "fall", "winter")[(d - 1) // 28 % 4]


def _day_ok(src: Source, d: int, w: When) -> bool | None:
    """True / False, or None when the source's condition can't be decided for that day."""
    if not src.in_season(_season_of(d)):
        return False
    if src.days and not src.days[0] <= (d - 1) % 28 + 1 <= src.days[1]:
        return False
    return True if not src.condition else check(src.condition, w.on(d))


class Planner:
    def __init__(self, farm: Farm, deadline: int):
        self.farm = farm
        self.deadline = deadline
        self.sources = Sources(farm.data, farm_type=farm.save.farm_type)
        self.today = farm.save.days_played
        self.held = farm.held()
        self.unlocks = Unlocks(farm)

    def way(self, src: Source, item: str) -> Way:
        f, w = self.farm, self.farm.when
        blocked, keys = [], []
        for need in src.needs:
            kind, _, what = need.partition(":")
            if kind == "place":
                ok, why = place_open("IslandSouth" if what == "Island" else what, w)
                if not ok:
                    blocked.append(why or what)
                    keys.append(need)
            elif kind == "machine" and not f.save.machines.get(self._bc_name(what)):
                blocked.append(f"a {self._bc_display(what)}")
                keys.append(need)
            elif kind == "recipe" and what not in f.save.crafting_recipes and what not in f.save.cooking_recipes:
                blocked.append(f"the {what} recipe")
                keys.append(need)
            elif kind == "animal" and not any(a["type"] == what for a in f.save.animals):
                blocked.append(f"a {what}")
                keys.append(need)
            elif kind == "building" and not f.save.buildings.get(what) and not self.unlocks.get(need).done:
                blocked.append(f"a {what}")
                keys.append(need)
            elif kind == "floor" and w.mine_lowest < int(what):
                blocked.append(f"reaching Mines floor {what}")
                keys.append(need)
            elif kind == "kitchen" and f.save.house_upgrade < 1:
                blocked.append("a kitchen (the first house upgrade)")
                keys.append("kitchen")
        way = self._way(src, item, blocked)
        way.unlocks = keys
        return way

    def _way(self, src: Source, item: str, blocked: list[str]) -> Way:
        f, w, today, end = self.farm, self.farm.when, self.today, self.deadline
        if src.chance is not None and src.kind in ("cart", "monster", "forage"):
            if src.kind == "cart":
                tries = sum(1 for d in range(today, end + 1) if (d - 1) % 28 % 7 % 5 == 0)
                odds = 1 - (1 - src.chance) ** tries
                return Way(src, None, end, blocked, odds)
        if src.kind == "monster":  # a chance per kill, and where it lives isn't in the data
            return Way(src, None, end, [*blocked, f"killing {src.label[2:]}s ({src.chance:.1%} a kill)"], sure=False)
        if src.kind == "crop":
            return self._crop(src, blocked)
        if src.kind == "tree":
            return self._tree(src, item, blocked)
        if src.kind in ("machine", "cooking", "crafting"):
            for oid, n in src.inputs:
                if self.held.get(f"(O){oid}", 0) < n and not oid.startswith("-"):
                    blocked.append(f"{n} {f.name('(O)' + oid)}")
        ok = {d: _day_ok(src, d, w) for d in range(today, end + 1)}
        days = [d for d, v in ok.items() if v is not False]
        lead = src.lead if src.kind in ("animal", "machine", "tapper") else 0
        unsure = src.kind == "mine" or any(ok[d] is None for d in days)
        if not days:
            return Way(src, None, None, blocked)
        fits = [d for d in days if d + lead <= end]
        return Way(src, days[0] + lead, max(fits) if fits else None, blocked, sure=not unsure)

    def _crop(self, src: Source, blocked: list[str]) -> Way:
        f, today, end = self.farm, self.today, self.deadline
        seed = src.inputs[0][0]
        held_seed = self.held.get(f"(O){seed}", 0) > 0
        seed_days = None if held_seed else self._buyable_days(seed)
        grow = src.lead
        first = last = None
        for p in range(today, end - grow + 1):
            if not all(src.in_season(_season_of(x)) for x in range(p, p + grow + 1)):
                continue
            if not held_seed and p not in seed_days:
                continue
            first = first or p + grow
            last = p
        if first is None and not held_seed and not seed_days and not blocked:
            blocked = [*blocked, f"{f.name('(O)' + seed)} (no shop sells them before then)"]
        return Way(src, first, last, blocked)

    def _tree(self, src: Source, item: str, blocked: list[str]) -> Way:
        """Fruit only from a tree you already have: a sapling planted now takes 28 days, then waits for its season."""
        oid = item.removeprefix("(O)")
        for t in self.farm.save.fruit_trees:
            if oid in t.get("fruit_ids", []):
                ready = self.today + max(0, t.get("days_left", 0))
                days = [d for d in range(ready, self.deadline + 1) if src.in_season(_season_of(d))]
                if days:
                    return Way(src, days[0], days[-1], blocked)
        days = [d for d in range(self.today + 28, self.deadline + 1) if src.in_season(_season_of(d))]
        if days:
            return Way(src, days[0], days[-1] - 0, [*blocked, f"planting a {src.label[:-5]} by "
                                                     f"{self.farm.label(days[0] - 28)}"])
        return Way(src, None, None, [*blocked, f"a {src.label[:-5]} planted a season earlier"])

    def _buyable_days(self, seed: str) -> set[int]:
        out = set()
        for s in self.sources.index.get(seed, []):
            if s.kind != "shop":
                continue
            ok, _ = self.sources.open_now(s, self.farm.when)
            if not ok:
                continue
            out |= {d for d in range(self.today, self.deadline + 1) if _day_ok(s, d, self.farm.when)}
        return out

    def _bc_name(self, mid: str) -> str:
        return (self.farm.data.asset("Data/BigCraftables").get(mid.removeprefix("(BC)")) or {}).get("Name") or mid

    def _bc_display(self, mid: str) -> str:
        b = self.farm.data.asset("Data/BigCraftables").get(mid.removeprefix("(BC)")) or {}
        return self.farm.data.text(b.get("DisplayName")) or b.get("Name") or mid

    def bundle_slots(self) -> list[tuple[str, int, list[Slot]]]:
        """(bundle key, how many still needed, every open ingredient as a Slot) for each open bundle."""
        f = self.farm
        plan = f.bundles.plan(f.save.items)
        out = []
        for b in f.bundles.all:
            if b.done or b.area in (VAULT, JOJA):
                continue
            cands = []
            for ing in b.open_ingredients:
                have = (b.key, ing.index) in plan.reserved
                item = ing.item or f"category {ing.category}"
                name = f.name(ing.item) if ing.item else f"any {item}"
                ways = [] if have or not ing.item else [self.way(s, ing.item) for s in self.sources.of(ing.item)]
                slot = Slot(b.display, b.room, item, name, ing.stack, ing.quality, have, ways)
                slot.best = _best(ways)
                cands.append(slot)
            out.append((b.key, b.still_needed, cands))
        return out

    def slots(self) -> list[Slot]:
        f = self.farm
        plan = f.bundles.plan(f.save.items)
        out = []
        for b in f.bundles.all:
            if b.done or b.area in (VAULT, JOJA):
                continue
            cands = []
            for ing in b.open_ingredients:
                have = (b.key, ing.index) in plan.reserved
                item = ing.item or f"category {ing.category}"
                name = f.name(ing.item) if ing.item else f"any {item}"
                ways = [] if have or not ing.item else [self.way(s, ing.item) for s in self.sources.of(ing.item)]
                dish = f.save.dish_of_the_day
                if not have and dish and ing.item == dish[0] and dish[1] >= ing.stack:
                    ways.insert(0, Way(Source("shop", "today's dish at the Saloon"), self.today, self.today))
                slot = Slot(b.display, b.room, item, name, ing.stack, ing.quality, have, ways)
                slot.best = _best(ways)
                cands.append(slot)
            cands.sort(key=_slot_order)
            out += cands[:b.still_needed]
        self._share_unlocks(out)
        return out

    def _share_unlocks(self, slots: list[Slot]) -> None:
        """For slots waiting on an unlock, pick the way whose unlocks add the least gold, counting the ones
        another slot already needs as free (a Deluxe Coop and a rabbit give both Wool and a Rabbit's Foot).
        A planning choice; two passes let early picks benefit from later ones."""
        def chain(x: Way) -> list[Unlock]:
            return [u for k in x.unlocks for u in self.unlocks.chain(k)]

        waiting = [s for s in slots if s.status == "blocked"]
        for _ in range(2):
            chosen: dict[str, int] = {}
            for s in waiting:
                if s.best:
                    for u in chain(s.best):
                        chosen[u.key] = chosen.get(u.key, 0) + 1
            for s in waiting:
                for u in chain(s.best) if s.best else []:  # don't count this slot's own pick as shared
                    chosen[u.key] -= 1
                gated = [x for x in s.ways if x.blocked and x.earliest is not None and x.source.kind != "monster"]
                if gated:
                    s.best = min(gated, key=lambda x: (sum(u.gold for u in chain(x) if chosen.get(u.key, 0) <= 0),
                                                       x.earliest))
                for u in chain(s.best) if s.best else []:
                    chosen[u.key] = chosen.get(u.key, 0) + 1


LIKELY = 0.8  # a random way this likely by the deadline counts as the plan


def _best(ways: list[Way]) -> Way | None:
    """The soonest certain way you can use now; else a likely random one; else the certain way with the
    least to unlock first (random ways stay listed as the backup)."""
    open_ = [x for x in ways if not x.blocked and x.odds is None and x.earliest is not None]
    if open_:
        return min(open_, key=lambda x: (not x.sure, x.earliest))
    luck = sorted((x for x in ways if not x.blocked and x.odds is not None), key=lambda x: -x.odds)
    if luck and luck[0].odds >= LIKELY:
        return luck[0]
    gated = [x for x in ways if x.blocked and x.earliest is not None and x.source.kind != "monster"]
    if gated:
        return min(gated, key=lambda x: (len(x.blocked), x.earliest))
    return luck[0] if luck else (ways[0] if ways else None)


def _slot_order(s: Slot) -> tuple:
    rank = {"have": 0, "ok": 1, "maybe": 2, "luck": 3, "blocked": 4, "stuck": 5}[s.status]
    return rank, (s.best.earliest or math.inf) if s.best else math.inf


def plan(farm: Farm, deadline: int | None = None) -> dict:
    """The open slots, each with its best way and its other ways, ordered by the last safe day."""
    end = deadline or ((farm.save.days_played - 1) // YEAR + 1) * YEAR  # end of this year by default
    p = Planner(farm, end)
    slots = p.slots()

    summary: dict[str, dict] = {}

    def chain(x: Way) -> list[Unlock]:
        out, seen = [], set()
        for k in x.unlocks:
            for u in p.unlocks.chain(k):
                if u.key not in seen:
                    seen.add(u.key)
                    out.append(u)
        return out

    def way_json(x: Way, slot_name: str = "") -> dict:
        steps = chain(x)
        lead = sum(u.days for u in steps)
        if slot_name:
            for u in steps:
                row = summary.setdefault(u.key, {"key": u.key, "label": u.label, "gold": u.gold, "days": u.days,
                                                 "how": u.how, "slots": [],
                                                 "materials": [{"id": m, "name": farm.name(f"(O){m}"), "count": n}
                                                               for m, n in u.materials]})
                row["slots"].append(slot_name)
        earliest = x.earliest
        if earliest is not None and steps:
            earliest = max(earliest, p.today + lead)
        return {"kind": x.source.kind, "label": x.source.label, "seasons": seasons_text(x.source),
                "unlock": [{"label": u.label, "gold": u.gold, "days": u.days, "how": u.how,
                            "materials": [f"{n} {farm.name('(O)' + m)}" for m, n in u.materials]} for u in steps],
                "unlock_gold": sum(u.gold for u in steps),
                "earliest_after_unlock": farm.label(earliest) if earliest and steps else "",
                "earliest": farm.label(x.earliest) if x.earliest else "",
                "last_start": farm.label(x.latest_start) if x.latest_start else "",
                "blocked": x.blocked, "odds": round(x.odds, 3) if x.odds is not None else None, "sure": x.sure,
                "notes": list(x.source.notes)}

    rows = []
    for s in slots:
        rows.append({"bundle": s.bundle, "room": s.room, "item": s.item, "name": s.name, "count": s.count,
                     "quality": s.quality, "status": s.status, "best": way_json(s.best, s.name) if s.best else None,
                     "others": [way_json(x) for x in s.ways if x is not s.best][:5],
                     "_last": s.best.latest_start if s.best and s.best.latest_start else math.inf})
    order = {"stuck": 0, "blocked": 1, "luck": 2, "maybe": 3, "ok": 4, "have": 5}
    rows.sort(key=lambda r: (order[r["status"]], r["_last"]))
    for r in rows:
        r.pop("_last")
    vault = sum(b.gold or 0 for b in farm.bundles.in_area(4) if not b.done)
    unlocks = sorted(summary.values(), key=lambda u: (-len(u["slots"]), u["gold"]))
    bought = sum(u["gold"] for u in unlocks if not u["key"].startswith("place:Desert"))  # the bus is the Vault
    gold = {"money": farm.save.money, "vault": vault, "unlocks": bought}
    from ..views.sell import view as sell_view
    from .income import afford_day, project
    pace = project(farm, end, sell_now=sell_view(farm)["total"])
    need = gold["vault"] + gold["unlocks"]
    gold["short"] = max(0, need - gold["money"])
    gold["projected"] = pace["with_money"]
    gold["projected_replant"] = pace["with_money"] + pace["replant"]["gold"]
    gold["streams"] = pace["streams"]
    gold["replant"] = pace["replant"]
    when = afford_day(pace["by_day"], need)
    gold["covered_by"] = farm.label(when) if when else ""
    gold["gap"] = max(0, need - gold["projected_replant"])
    return {"deadline": farm.label(end), "today": farm.label(p.today), "slots": rows, "unlocks": unlocks,
            "gold": gold,
            "counts": {k: sum(1 for r in rows if r["status"] == k)
                       for k in ("have", "ok", "maybe", "luck", "blocked", "stuck")}}
