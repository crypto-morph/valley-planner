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
BOUGHT = {"334": 5 * 75 + 150, "335": 5 * 150 + 150, "336": 5 * 400 + 150, "382": 150,  # Clint, Year 1
          "378": 75, "380": 150, "384": 400}
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
    def slot_req(self, s: Slot) -> Req | None:
        if s.have or s.best is None:
            return None
        w: Way = s.best
        chain = [u for k in w.unlocks for u in self.planner.unlocks.chain(k)]
        lead = sum(u.days for u in chain)
        if w.source.kind == "animal" and "(deluxe)" in w.source.label:
            kind = w.source.label.removeprefix("a ").removesuffix(" (deluxe)")
            extra = self.farm.animals.deluxe_days(kind) if kind in self.farm.animals.kinds else None
            if extra:
                k = self.farm.animals.kinds[kind]
                lead += extra - (k.days_to_mature + k.days_to_produce)
        activity = {"fish": "fish", "forage": "forage", "mine": "mine", "dig": "forage"}.get(w.source.kind)
        return Req(f"{s.name} ({s.bundle})", w.earliest or 1, w.latest_start or 0, chain, lead, activity, w.odds)

    def requirements(self, oid: str) -> tuple[list[Req], int, list[str]]:
        """(requirements, gold that's simply paid, notes) for an objective."""
        slots = self.planner.slots()
        if oid == "greenhouse":
            return [r for s in slots if s.room == "Pantry" and (r := self.slot_req(s))], 0, []
        if oid == "cc":
            vault = sum(b.gold or 0 for b in self.farm.bundles.in_area(VAULT) if not b.done)
            return [r for s in slots if (r := self.slot_req(s))], vault, []
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
            elif u.how and (u.how.startswith("buy it from") or "colour is random" in u.how):
                pass
            elif u.how and not u.gold and not u.materials:
                problems.append(f"{u.label}: {u.how}")
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
        for g in gates:
            skill, level = g.split()
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
            if gold and self.result([(b, gold)]).lowest_from(b) < 0:
                continue
            ready = b + req.lead
            act = None
            if req.activity:
                options = self.free_days(max(ready, req.earliest), latest_ready)
                if not options:
                    continue
                act = options[0]
            return Step(req.label, b, act or ready, gold, chop), ""
        short = self.result([(latest_ready - req.lead, gold)]).lowest_from(max(1, latest_ready - req.lead)) \
            if gold else 0
        if gold and short < 0:
            return None, f"{req.label}: about {-short:,}g short by {self.farm.label(latest_ready - req.lead)}"
        return None, f"{req.label}: no free days left before {self.farm.label(latest_ready)}"

    def commit(self, step: Step, req: Req) -> None:
        if step.gold:
            self.spends.append((step.day, step.gold))
        for d in step.chop_days:
            self.busy[d] = "chop"
        if req.activity and step.ready not in self.busy:
            self.busy[step.ready] = req.activity
        for u in req.chain:
            self.have.setdefault(u.key, step.day + u.days)

    def objective(self, oid: str, tier: str, deadline: int | None = None) -> Outcome:
        label, default = CATALOG.get(oid, (oid, YEAR_DAYS))
        out = Outcome(oid, label, tier, deadline or default)
        reqs, paid, notes = self.requirements(oid)
        out.problems += notes
        reqs.sort(key=lambda r: (r.latest or 0) - r.lead)
        placed: list[tuple[Step, Req]] = []
        for r in reqs:
            step, why = self.place(r, out.deadline)
            if step is None:
                out.problems.append(why)
            else:
                placed.append((step, r))
                self.commit(step, r)  # provisionally, so later requirements see it
        if paid:
            res = self.result()
            day = next((d.day for d in res.days if d.cash >= paid and self.result([(d.day, paid)]).lowest_from(d.day)
                        >= 0), None)
            if day is None or day > out.deadline:
                out.problems.append(f"the Vault's {paid:,}g isn't there by {self.farm.label(out.deadline)}")
            else:
                self.spends.append((day, paid))
                placed.append((Step(f"pay the Vault ({paid:,}g)", day, day, paid), Req("vault", day, day, [], 0)))
        out.steps = [s for s, _ in sorted(placed, key=lambda p: p[0].day)]
        out.finish = max((s.ready for s in out.steps), default=None)
        if out.problems:
            out.status = "impossible" if any("only by luck" not in p for p in out.problems) else "luck"
        if oid == "greenhouse" and not out.problems and out.finish:
            self.greenhouse_day = out.finish + 1
        if oid == "seed_maker" and not out.problems and out.finish:
            self.seed_maker_day = out.finish
        return out


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
                        "steps": [{"what": s.label, "day": label(s.day), "ready": label(s.ready), "gold": s.gold,
                                   "chop_days": len(s.chop_days)} for s in o.steps]} for o in outcomes],
        "cash": [{"day": label(d.day), "cash": d.cash, "farming": d.level} for d in res.days if d.day % 7 == 1],
        "busy": {label(d): what for d, what in sorted(r.busy.items())},
    }
