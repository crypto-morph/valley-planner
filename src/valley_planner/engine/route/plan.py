"""Objectives in priority order: place each one's purchases and days, and say what can't be done.

Targets (ticked) come first, in your order; nice-to-haves follow, in their order. Each objective is placed
as early as the cash, the days and its rules allow without moving anything above it, and what it builds
(the greenhouse, the Seed Maker) feeds into the economy for everything below.

Planning choices, marked so they can be tuned: Wood comes from chopping days (`WOOD_PER_DAY`), bars,
ore and coal are bought from Clint at Year-1 prices, any other material costs a gathering day, and a
random-only slot isn't counted as achievable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ...facts.bundles import VAULT
from ..cc import Planner, Slot, Way
from ..unlocks import Unlock
from .simulate import YEAR_DAYS, Farmsim

WOOD, STONE, HARDWOOD = "388", "390", "709"
WOOD_PER_DAY = 100  # planning choice: Wood from a day spent chopping
FLOORS_PER_DAY = 8  # planning choice: Mines floors gained in a day spent mining
MINES_OPEN = 5  # the landslide clears on day 5
BOUGHT = {"334": 5 * 75 + 150, "335": 5 * 150 + 150, "336": 5 * 400 + 150, "382": 150,  # Clint, Year 1
          "378": 75, "380": 150, "384": 400}
DATE_GATES = {"place:UndergroundMine": 5, "place:Railroad": 31}  # places that simply open on a day
HARD = ("Island", "quest", "Rusty Key", "Willy's boat")  # gates the route can't plan in Year 1
SKILL_RE = re.compile(r"^(Farming|Fishing|Foraging|Mining|Combat) level (\d+)", re.I)

CATALOG = {  # id -> (label, default deadline as days played in Year 1)
    "greenhouse": ("The greenhouse", 84),
    "seed_maker": ("A Seed Maker", 112),
    "kitchen": ("The kitchen", 112),
    "cc": ("The Community Center", 112),
}


@dataclass
class Step:
    label: str
    day: int  # when it's bought / done
    ready: int  # when it's in hand
    gold: int = 0
    chop_days: list[int] = field(default_factory=list)
    mine_days: list[int] = field(default_factory=list)


@dataclass
class Outcome:
    id: str
    label: str
    tier: str
    deadline: int
    status: str = "ok"  # ok / late / impossible
    finish: int | None = None
    steps: list[Step] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class Req:
    label: str
    earliest: int
    latest: int
    chain: list[Unlock]
    lead: int
    activity: str | None = None  # fish / forage / mine: a day spent getting it
    luck: float | None = None
    season: str = ""  # the way's label: fishing at one place in one season shares a day


class Router:
    def __init__(self, farm, *, tiles: int = 60):
        self.farm = farm
        self.sim = Farmsim(farm, tiles=tiles)
        self.spends: list[tuple[int, int]] = []
        self.busy: dict[int, str] = {}  # day -> what it's spent on
        self.have: dict[str, int] = {}  # unlock key -> day it's ready
        self.seed_maker_day: int | None = None
        self.greenhouse_day: int | None = None
        self.festivals = {d for d in range(1, YEAR_DAYS + 1) if self._festival(d)}
        self.floor = 0  # deepest Mines floor the route has planned for
        self.vault_day: int | None = None
        self.fish_days: dict[str, int] = {}
        self.planner = Planner(farm, YEAR_DAYS)
        self._result = None

    # ----- the economy, as committed so far -----
    def result(self, extra: list[tuple[int, int]] = ()):
        return self.sim.run(self.spends + list(extra), seed_maker_day=self.seed_maker_day,
                            greenhouse_day=self.greenhouse_day)

    def _festival(self, d: int) -> bool:
        from ...facts.conditions import SEASONS
        key = f"{SEASONS[(d - 1) // 28 % 4]}{(d - 1) % 28 + 1}"
        return key in self.farm.data.asset("Data/Festivals/FestivalDates")

    def free_days(self, lo: int, hi: int) -> list[int]:
        return [d for d in range(max(1, lo), min(YEAR_DAYS, hi) + 1)
                if d not in self.busy and d not in self.festivals]

    # ----- requirements -----
    def chain(self, w: Way) -> list[Unlock]:
        """Everything a way needs that isn't done, each once, prerequisites first."""
        out, seen = [], set()
        for k in w.unlocks:
            for u in self.planner.unlocks.chain(k):
                if u.key not in seen:
                    seen.add(u.key)
                    out.append(u)
        return out

    def viable(self, w: Way) -> bool:
        """A way whose unlocks are all things the route can plan (no quests, no island)."""
        return w.odds is None and (w.earliest is not None) and not self.cost(self.chain(w))[3]

    def way_gold(self, w: Way) -> int:
        return self.cost(self.chain(w))[0]

    def pick(self, s: Slot) -> Way | None:
        """The cheapest viable way (then the soonest); the planner's own pick if none is viable."""
        ok = [w for w in s.ways if self.viable(w)]
        if ok:
            return min(ok, key=lambda w: (self.way_gold(w), len(w.unlocks), w.earliest))
        return s.best

    def slot_req(self, s: Slot) -> Req | None:
        if s.have:
            return None
        w = self.pick(s)
        if w is None:
            return Req(f"{s.name} ({s.bundle})", 1, 0, [], 0)
        chain = self.chain(w)
        lead = sum(u.days for u in chain)
        if w.source.kind == "animal" and "(deluxe)" in w.source.label:
            kind = w.source.label.removeprefix("a ").removesuffix(" (deluxe)")
            extra = self.farm.animals.deluxe_days(kind) if kind in self.farm.animals.kinds else None
            if extra:
                k = self.farm.animals.kinds[kind]
                lead += extra - (k.days_to_mature + k.days_to_produce)
        activity = {"fish": "fish", "forage": "forage", "mine": "mine", "dig": "forage",
                    "crabpot": "forage"}.get(w.source.kind)
        return Req(f"{s.name} ({s.bundle})", w.earliest or 1, w.latest_start or 0, chain, lead, activity, w.odds,
                   season=w.source.label)

    def bundle_reqs(self, rooms: set[str] | None = None) -> list[Req]:
        """For each open bundle, the cheapest ways to fill the slots it still needs."""
        out = []
        for _key, need, slots in self.planner.bundle_slots():
            if rooms and not any(s.room in rooms for s in slots):
                continue
            reqs = [r for s in slots if (r := self.slot_req(s))]
            have = sum(1 for s in slots if s.have)
            reqs.sort(key=lambda r: (r.luck is not None, r.latest == 0, self.cost(r.chain)[0], r.earliest))
            out += reqs[:max(0, need - have)]
        return out

    def requirements(self, oid: str) -> tuple[list[Req], int, list[str]]:
        """(requirements, gold that's simply paid, notes) for an objective."""
        if oid == "greenhouse":
            return self.bundle_reqs({"Pantry"}), 0, []
        if oid == "cc":
            vault = sum(b.gold or 0 for b in self.farm.bundles.in_area(VAULT) if not b.done)
            return self.bundle_reqs(), vault, []
        if oid == "kitchen":
            u = self.planner.unlocks.get("kitchen")
            return [Req("the kitchen", 1, YEAR_DAYS, [u], u.days)], 0, []
        if oid == "seed_maker":
            u = self.planner.unlocks.get("machine:(BC)25")
            u.how = "Farming level 9"
            return [Req("a Seed Maker", 1, YEAR_DAYS, [u], 0)], 0, []
        return [], 0, [f"unknown objective {oid}"]

    # ----- placing -----
    def cost(self, chain: list[Unlock]) -> tuple[int, int, list[str], list[str]]:
        """(gold, chop days, skill gates, problems) for the unlocks not already planned."""
        gold, wood, gates, problems = 0, 0, [], []
        for u in chain:
            if u.key in self.have or u.done:
                continue
            if u.key.startswith("floor:"):
                gates.append(f"Floor {u.key[6:]}")
                continue
            if u.key in DATE_GATES:
                gates.append(f"Day {DATE_GATES[u.key]}")
                continue
            if u.key == "place:Desert":
                if self.vault_day is None:
                    problems.append("the bus to the Desert (pay the Vault first)")
                else:
                    gates.append(f"Day {self.vault_day + 1}")
                continue
            gold += u.gold
            for mat, n in u.materials:
                if mat == WOOD:
                    wood += n
                elif mat in BOUGHT:
                    gold += BOUGHT[mat] * n
                elif mat == HARDWOOD:
                    problems.append(f"{n} Hardwood (needs a Steel Axe; not planned yet)")
                elif mat != STONE:
                    wood += 0  # other materials: a gathering day each, below
            m = SKILL_RE.match(u.how or "")
            if m:
                gates.append(f"{m.group(1)} {m.group(2)}")
            elif u.how and (u.how.startswith("buy it from") or "colour is random" in u.how or u.how == "mining"):
                pass
            elif u.how and not u.gold and not u.materials:
                if any(h in u.how or h in u.label for h in HARD):
                    problems.append(f"{u.label}: {u.how}")
                # other recipes (letters, events, Clint's Furnace): assumed to come in time
        return gold, math.ceil(wood / WOOD_PER_DAY) if wood else 0, gates, problems

    def place(self, req: Req, deadline: int) -> tuple[Step | None, str]:
        if req.luck is not None:
            return None, f"{req.label}: only by luck ({req.luck:.0%} chance by the deadline)"
        latest_ready = min(req.latest or deadline, deadline)
        if req.latest == 0:
            return None, f"{req.label}: no way to get it before the deadline"
        gold, chops, gates, problems = self.cost(req.chain)
        if problems:
            return None, f"{req.label}: needs {'; '.join(problems)}"
        res = self.result()
        start = req.earliest
        floor_need = max((int(g.split()[1]) for g in gates if g.startswith("Floor")), default=0)
        for g in gates:
            skill, level = g.split()
            if skill == "Day":
                start = max(start, int(level))
                continue
            if skill == "Floor":
                continue
            if skill.lower() != "farming":
                continue  # other skills: assumed reached (not modelled yet)
            day = res.level_day(int(level))
            if day is None or day > latest_ready - req.lead:
                return None, f"{req.label}: Farming {level} isn't reached in time with {self.sim.tiles} tiles"
            start = max(start, day)
        for b in range(max(1, start - req.lead if not req.chain else start), latest_ready - req.lead + 1):
            chop = self.free_days(1, b - 1)[-chops:] if chops else []
            if len(chop) < chops:
                continue
            mine = self.mining_days(floor_need, b)
            if mine is None:
                continue
            if gold and self.result([(b, gold)]).lowest_from(b) < 0:
                continue
            ready = max(b, max(mine, default=0) + 1) + req.lead
            act = None
            if req.activity == "fish":
                shared = self.fish_days.get(req.season)
                if shared and max(ready, req.earliest) <= shared <= latest_ready:
                    act = shared
                else:
                    options = [d for d in self.free_days(max(ready, req.earliest), latest_ready)
                               if _season(d) == _season(max(ready, req.earliest))]
                    if not options:
                        continue
                    act = options[0]
            elif req.activity == "forage":
                act = max(ready, req.earliest)  # picked up on the way: no day of its own
            return Step(req.label, b, act or ready, gold, chop, mine), ""
        short = self.result([(latest_ready - req.lead, gold)]).lowest_from(max(1, latest_ready - req.lead)) \
            if gold else 0
        if gold and short < 0:
            return None, f"{req.label}: about {-short:,}g short by {self.farm.label(latest_ready - req.lead)}"
        return None, f"{req.label}: no free days left before {self.farm.label(latest_ready)}"

    def mining_days(self, floor: int, by: int) -> list[int] | None:
        """New mining days needed (before `by`) to have reached `floor`; [] if already there."""
        have = max(self.floor, self.farm.when.mine_lowest)
        if floor <= have:
            return []
        n = math.ceil((floor - have) / FLOORS_PER_DAY)
        days = self.free_days(MINES_OPEN, by - 1)[:n]
        return days if len(days) == n else None

    def pay_vault(self, gold: int, out: Outcome, placed: list) -> None:
        res = self.result()
        day = next((d.day for d in res.days if self.result([(d.day, gold)]).lowest_from(d.day) >= 0), None)
        if day is None or day > out.deadline:
            out.problems.append(f"the Vault's {gold:,}g isn't there by {self.farm.label(out.deadline)}")
            return
        self.spends.append((day, gold))
        self.vault_day = day
        placed.append((Step(f"pay the Vault ({gold:,}g)", day, day, gold), Req("vault", day, day, [], 0)))

    def commit(self, step: Step, req: Req) -> None:
        if step.gold:
            self.spends.append((step.day, step.gold))
        for d in step.chop_days:
            self.busy.setdefault(d, "chop")
        for d in step.mine_days:
            self.busy.setdefault(d, "mine")
        self.floor += len(step.mine_days) * FLOORS_PER_DAY
        if req.activity == "fish":
            self.fish_days.setdefault(req.season, step.ready)
            self.busy.setdefault(step.ready, "fish")
        for u in req.chain:
            self.have.setdefault(u.key, step.day + u.days)

    def objective(self, oid: str, tier: str, deadline: int | None = None) -> Outcome:
        label, default = CATALOG.get(oid, (oid, YEAR_DAYS))
        out = Outcome(oid, label, tier, deadline or default)
        reqs, paid, notes = self.requirements(oid)
        out.problems += notes
        reqs.sort(key=lambda r: (r.latest or 0) - r.lead)
        placed: list[tuple[Step, Req]] = []
        desert = [r for r in reqs if any(u.key == "place:Desert" for u in r.chain)]
        reqs = [r for r in reqs if r not in desert]
        for r in reqs + ([None] if paid else []) + desert:
            if r is None:  # the Vault, after everything else and before the desert's items (it brings the bus)
                self.pay_vault(paid, out, placed)
                continue
            step, why = self.place(r, out.deadline)
            if step is None:
                out.problems.append(why)
            else:
                placed.append((step, r))
                self.commit(step, r)  # provisionally, so later requirements see it
        if self.vault_day is not None and oid == "cc":  # the bus is coming: slots only the desert fills
            done = {st.label for st, _ in placed}
            for r in self.bundle_reqs():
                if r.label in done or not any(u.key == "place:Desert" for u in r.chain):
                    continue
                step, why = self.place(r, out.deadline)
                if step:
                    placed.append((step, r))
                    self.commit(step, r)
                    out.problems = [p for p in out.problems if not p.startswith(r.label)]
        out.steps = [s for s, _ in sorted(placed, key=lambda p: p[0].day)]
        out.finish = max((s.ready for s in out.steps), default=None)
        if out.problems:
            out.status = "impossible" if any("only by luck" not in p for p in out.problems) else "luck"
        if oid == "greenhouse" and not out.problems and out.finish:
            self.greenhouse_day = out.finish + 1
        if oid == "seed_maker" and not out.problems and out.finish:
            self.seed_maker_day = out.finish
        return out


def _season(d: int) -> int:
    return (d - 1) // 28


def route(farm, targets: list[str], nice: list[str] = (), *, tiles: int = 60,
          deadlines: dict[str, int] | None = None) -> dict:
    """Plan targets (in order) then nice-to-haves (in order); what each achieves, when, and what can't be."""
    r = Router(farm, tiles=tiles)
    outcomes = [r.objective(o, "target", (deadlines or {}).get(o)) for o in targets]
    outcomes += [r.objective(o, "nice", (deadlines or {}).get(o)) for o in nice]
    res = r.result()

    def label(d):
        return farm.label(d) if d else ""

    return {
        "tiles": tiles,
        "objectives": [{"id": o.id, "label": o.label, "tier": o.tier, "status": o.status,
                        "deadline": label(o.deadline), "finish": label(o.finish), "problems": o.problems,
                        "steps": [{"what": s.label, "day": label(s.day), "ready": label(s.ready),
                                   "gold": s.gold,
                                   "chop_days": len(s.chop_days), "mine_days": len(s.mine_days)}
                                  for s in o.steps]} for o in outcomes],
        "cash": [{"day": label(d.day), "cash": d.cash, "farming": d.level} for d in res.days if d.day % 7 == 1],
        "busy": {label(d): what for d, what in sorted(r.busy.items())},
    }
