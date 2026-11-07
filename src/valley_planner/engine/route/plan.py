"""Objectives in priority order: place each one's purchases and days, and say what can't be done.

Targets (ticked) come first, in your order; nice-to-haves follow, in their order. Each objective is placed
as early as the cash, the days and its rules allow without moving anything above it, and what it builds
(the greenhouse, the Seed Maker) feeds into the economy for everything below.

Planning choices, marked so they can be tuned: Wood comes from chopping days (`WOOD_PER_DAY`), bars,
ore and coal are bought from Clint at Year-1 prices, Quartz and Clay cost days in the Mines, Oak Resin waits
on Tappers on oaks, anything else (Stone, Fiber) is named as not counted, and a random-only slot isn't
counted as achievable. Skills other than Farming are assumed reached, and said so.
"""

from __future__ import annotations

import math
from dataclasses import replace

from ...facts import romance
from ...facts.cave import EARNINGS_TRIGGER, gives, nights_for
from ..cc import Planner, Slot, Way
from ..unlocks import Unlock
from .model import (
    BOUGHT,
    CLAY,
    DATE_GATES,
    HARD,
    HARDWOOD,
    MINES_OPEN,
    OAK_RESIN,
    QUARTZ,
    REFINED_QUARTZ,
    SKILL_RE,
    STONE,
    VAULT_STEP,
    WOOD,
    WOOD_PER_DAY,
    Outcome,
    Req,
    Settings,
    Step,
)
from .objectives import CATALOG, OBJECTIVES, with_needs
from .objectives.qi import QI_STEPS
from .pace import Pace
from .present import AGENDA_DAYS, _agenda, _season, _span, _tree
from .simulate import YEAR_DAYS, Farmsim

__all__ = ["AGENDA_DAYS", "BOUGHT", "CATALOG", "HARDWOOD", "QI_STEPS", "QUARTZ", "REFINED_QUARTZ",
           "STONE", "WOOD", "WOOD_PER_DAY", "Outcome", "Req", "Router", "Settings", "Step", "route"]


class Router:
    def __init__(self, farm, *, settings: Settings | None = None, cave: str | None = None):
        self.farm = farm
        self.s = settings or Settings()
        self.cave = cave  # "bats" / "mushrooms" / None (not chosen yet)
        self.sim = Farmsim(farm, tiles=self.s.tiles, float_gold=self.s.float)
        self.spends: list[tuple[int, int]] = []
        self.busy: dict[int, tuple[str, str]] = {}  # day -> (what it's spent on, for which objective)
        self.current = ""  # the objective being placed
        self.have: dict[str, int] = {}  # unlock key -> day it's ready
        self.seed_maker_day: int | None = None
        self.greenhouse_day: int | None = None
        self.today, self.end = self.sim.today, self.sim.end  # plan from the save's day to the end of its year
        self.year_start = self.end - YEAR_DAYS
        self.festivals = {d for d in range(self.today, self.end + 1) if self._festival(d)}
        self.floor = 0  # deepest Mines floor the route has planned for
        self.pace = Pace.of(farm.when, self.s.floors_per_week)
        self.vault_day: int | None = None
        self.outcomes: dict[str, Outcome] = {}  # the goals placed so far
        self.got: dict[str, tuple[Step, str]] = {}  # requirement -> its step, and the objective that planned it
        self.held = farm.held()
        self.wood_left = self.held.get(f"(O){WOOD}", 0)  # Wood in hand, used before any chopping
        self.fish_days: dict[str, int] = {}
        self.wedding: str | None = None  # who the route marries, once the Pendant is placed
        # Robin builds one thing at a time (no shop or upgrades while a building or the house is under way):
        # her jobs as [start, ready) days, starting with whatever the save has her on
        self.robin: list[tuple[int, int]] = [(self.today, self.today + n) for n in
                                             list(getattr(farm.save, "building_days", {}).values())
                                             + [getattr(farm.save, "house_upgrade_days", 0)] if n > 0]
        # Clint has one tool at a time (the save keeps a single toolBeingUpgraded): his jobs the same way
        self.clint: list[tuple[int, int]] = ([(self.today, self.today + farm.save.tool_at_clint_days)]
                                             if getattr(farm.save, "tool_at_clint", "") else [])
        self.misses: list[tuple[str, str]] = []  # the objective being placed: what can't be, and why
        self.info: list[str] = []
        self.planner = Planner(farm, self.end)
        save = farm.save
        if self.cave is None or save.cave_choice:  # a choice already made in the save wins
            self.cave = {1: "bats", 2: "mushrooms"}.get(save.cave_choice, self.cave)
        if save.machines.get("Seed Maker"):
            self.seed_maker_day = self.today
        if "ccPantry" in save.mail:
            self.greenhouse_day = self.today
        for a in save.animals:  # animals you already have produce from today
            self.have.setdefault(f"animal:{a['type']}", self.today)
        self._result = None

    # ----- the objectives, each in its own module -----
    def done(self, oid: str) -> bool:
        o = OBJECTIVES.get(oid)
        return bool(o and o.done(self))

    def requirements(self, oid: str) -> tuple[list[Req], int, list[str]]:
        """(requirements, gold that's simply paid, notes) for an objective."""
        o = OBJECTIVES.get(oid)
        return o.plan(self) if o else ([], 0, [f"unknown objective {oid}"])

    # ----- the economy, as committed so far -----
    def result(self, extra: list[tuple[int, int]] = ()):
        income, xp = self.side_income()
        return self.sim.run(self.spends + list(extra), seed_maker_day=self.seed_maker_day,
                            greenhouse_day=self.greenhouse_day, income=income, xp=xp)

    def side_income(self) -> tuple[dict[int, int], dict[int, int]]:
        """Gold and farming XP besides crops: each planned animal's produce once it's grown (and 5 XP a day
        for petting it), and fishing on the days nothing else is planned (a planning choice)."""
        income: dict[int, int] = {}
        xp: dict[int, int] = {}
        for key, ready in self.have.items():
            if not key.startswith("animal:"):
                continue
            kind = self.farm.animals.kinds.get(key[7:])
            if not kind or not kind.produce:
                continue
            price = self.farm.items.get(kind.produce[0][0])
            each = (price.price if price else 0) / max(1, kind.days_to_produce)
            for d in range(max(ready, self.today), self.end + 1):
                income[d + 1] = income.get(d + 1, 0) + round(each)
                xp[d] = xp.get(d, 0) + 5
        for d in range(max(2, self.today), self.end + 1):  # the rod arrives on day 2
            what = self.busy.get(d, ("fish", ""))[0]
            if d in self.festivals:
                continue
            if what == "fish" and (d - 1) // 28 % 4 != 3:
                income[d + 1] = income.get(d + 1, 0) + self.s.fish_gold
            elif what == "mine":
                income[d + 1] = income.get(d + 1, 0) + self.s.mine_gold
        return income, xp

    def _festival(self, d: int) -> bool:
        from ...facts.conditions import SEASONS
        key = f"{SEASONS[(d - 1) // 28 % 4]}{(d - 1) % 28 + 1}"
        return key in self.farm.data.asset("Data/Festivals/FestivalDates")

    def free_days(self, lo: int, hi: int) -> list[int]:
        return [d for d in range(max(self.today, lo), min(self.end, hi) + 1)
                if d not in self.busy and d not in self.festivals]

    # ----- requirements -----
    def chain(self, w: Way, owner: str = "") -> list[Unlock]:
        """Everything a way needs that isn't done, each once, prerequisites first."""
        if w.source.on is not None:  # a cart visit: `owner` keeps two bundles' purchases apart
            return [Unlock(f"cart:{owner}:{w.source.label}", f"buy it from {w.source.label}", w.source.cost,
                           how="the Traveling Cart: in the Forest, 6 AM to 8 PM")]
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

    def _way_rank(self, w: Way) -> tuple:
        return self.way_gold(w), len(w.unlocks), w.earliest

    def pick(self, s: Slot) -> Way | None:
        """The way you picked; else the cheapest viable way (then the soonest); the planner's own pick if none is
        viable."""
        chosen = next((w for w in s.ways if w.source.label == self.s.picks.get(s.name)), None)
        if chosen:
            return chosen
        ok = [w for w in s.ways if self.viable(w)]
        if ok:
            return min(ok, key=self._way_rank)
        return s.best

    def machines(self, bc: str) -> int:
        """How many of a machine you have: in hand or in chests, and placed."""
        name = (self.farm.data.asset("Data/BigCraftables").get(bc) or {}).get("Name", bc)
        return self.held.get(f"(BC){bc}", 0) + self.farm.save.machines.get(name, 0)

    def cave_day(self) -> int | None:
        """The morning Demetrius makes his offer: lifetime earnings past 25,000g (today if it's been made)."""
        if not self.cave:
            return None
        if self.farm.save.cave_choice:
            return self.today
        return self.result().earned_day(EARNINGS_TRIGGER)

    def cave_req(self, s: Slot) -> Req | None:
        """A free, likely way from the farm cave, if the choice gives this item in time."""
        if not self.cave or not s.item.startswith("(O)") or s.item[3:] not in gives(self.cave):
            return None
        start, nights = self.cave_day(), nights_for(self.cave, s.item)
        if start is None or nights is None or start + nights > self.end:
            return None
        cave = "fruit bats" if self.cave == "bats" else "mushroom boxes"
        ready = max(self.today, start + nights)
        return Req(f"{s.name} ({s.bundle}), from the {cave}", ready, self.end, [], 0)

    def slot_req(self, s: Slot) -> Req | None:
        if s.have:
            return None
        cave = self.cave_req(s) if self.s.picks.get(s.name, "cave") == "cave" else None  # unless you picked another
        if cave:
            return cave
        ripe = self.growing(s)
        if ripe is not None:  # already in the ground: it only has to finish
            return Req(f"{s.name} ({s.bundle})", ripe, self.end, [], 0, season="already growing")
        if s.item.removeprefix("(O)") in (WOOD, STONE, HARDWOOD):  # chopped and mined, so it costs days, not gold
            oid = s.item.removeprefix("(O)")
            gather = Unlock(f"gather:{s.bundle}:{oid}:{s.name}", f"gather {s.count} {s.name}", 0, [(oid, s.count)])
            return Req(f"{s.name} ({s.bundle})", self.today, self.end, [gather], 0)
        w = self.pick(s)
        if w is None:
            return Req(f"{s.name} ({s.bundle})", 1, 0, [], 0)
        req = self.way_req(s, w)
        if w.source.on is not None and s.name not in self.s.picks:  # the next-best way, should this visit not work
            for other in sorted((x for x in s.ways if x is not w and self.viable(x)), key=self._way_rank, reverse=True):
                req.fallback, tail = self.way_req(s, other), req.fallback
                req.fallback.fallback = tail
        return req

    def way_req(self, s: Slot, w: Way) -> Req:
        chain = self.chain(w, s.bundle)
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

    def growing(self, s: Slot) -> int | None:
        """The day enough of this slot's item will be ripe, if it's planted, in time, at a quality the slot takes."""
        if s.quality:
            return None
        days = sorted(c.days_left for c in self.farm.save.crops if f"(O){c.harvest_id}" == s.item and not c.dead)
        if len(days) < s.count:
            return None
        ripe = self.today + days[s.count - 1]
        return ripe if ripe <= self.end else None

    def bundle_reqs(self, rooms: set[str] | None = None) -> list[Req]:
        """For each open bundle, the cheapest ways to fill the slots it still needs."""
        out = []
        for _key, need, slots in self.planner.bundle_slots():
            if rooms and not any(s.room in rooms for s in slots):
                continue
            reqs = [r for s in slots if (r := self.slot_req(s))]
            have = sum(1 for s in slots if s.have)
            reqs.sort(key=lambda r: (r.label.split(" (")[0] not in self.s.picks,  # a way you picked stays in
                                     r.luck is not None, r.latest == 0, self.cost(r.chain)[0], r.earliest))
            out += reqs[:max(0, need - have)]
        return out

    def explain(self, reqs: list[Req]) -> None:
        """Say what the plan doesn't price: materials gathered as you go, and skills other than Farming."""
        seen, left, skills = set(), {}, []
        known = {WOOD, HARDWOOD, REFINED_QUARTZ, CLAY, *BOUGHT}
        for r in reqs:
            keys = {u.key for u in r.chain}
            for u in r.chain:
                if u.done or u.key in seen or u.key in self.have:
                    continue
                seen.add(u.key)
                for m, n in u.materials:
                    if m not in known and not (m == OAK_RESIN and "tap:oak" in keys):
                        left[m] = left.get(m, 0) + n
                m = SKILL_RE.match(u.how or "")
                if m and m.group(1).lower() != "farming":
                    skills.append(f"{u.label} needs {u.how}")
        if left:
            self.info.append("Not counted, gathered as you go: " +
                             ", ".join(f"{n:,} {self.farm.name(f'(O){m}')}" for m, n in left.items()))
        for s in skills:
            self.info.append(f"{s}: assumed reached in time")

    # ----- placing -----
    def cost(self, chain: list[Unlock]) -> tuple[int, int, list[str], list[str]]:
        """(gold, chop days, skill gates, problems) for the unlocks not already planned."""
        gold, wood, gates, problems = 0, 0, [], []
        hardwood = sum(n for u in chain if u.key not in self.have and not u.done for m, n in u.materials
                       if m == HARDWOOD)
        if hardwood:  # Hardwood comes from stumps, which need a Steel Axe
            axe = [u for u in self.planner.unlocks.chain("tool:Axe@2") if u.key not in self.have]
            chain = axe + [u for u in chain if u.key not in {a.key for a in axe}]
            wood += math.ceil(hardwood / self.s.hardwood_per_day) * self.s.wood_per_day
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
                    pass  # counted above: the axe and stump days
                elif mat == REFINED_QUARTZ:  # a Quartz and a Coal through the Furnace: Quartz from the Mines
                    gold += BOUGHT["382"] * n
                    gates.append(f"Mine {math.ceil(n / self.s.quartz_per_day)}")
                elif mat == CLAY:  # hoed up, best in the Mines' dirt; Clay in hand first
                    left = max(0, n - self.held.get(f"(O){CLAY}", 0))
                    if left:
                        gates.append(f"Mine {math.ceil(left / max(1, self.s.clay_per_day))}")
                # Oak Resin: the tapping step before it; anything else: Router.explain says it isn't counted
            m = SKILL_RE.match(u.how or "")
            if m:
                gates.append(f"{m.group(1)} {m.group(2)}")
            elif u.how and (u.how.startswith("buy it from") or "colour is random" in u.how or u.how == "mining"):
                pass
            elif u.how and not u.gold and not u.materials:
                if any(h in u.how or h in u.label for h in HARD):
                    problems.append(f"{u.label}: {u.how}")
                # other recipes (letters, events, Clint's Furnace): assumed to come in time
        wood = max(0, wood - self.wood_left)  # Wood you already hold goes first
        return gold, math.ceil(wood / self.s.wood_per_day) if wood else 0, gates, problems

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
        extra_mine = sum(int(g.split()[1]) for g in gates if g.startswith("Mine "))
        axe_days = sum(u.days for u in self.cost_extras(req.chain))
        # unlocks an earlier step already plans: wait for them, and don't count their days again
        planned = [u for u in req.chain if not u.done and u.key in self.have]
        after = max((self.have[u.key] for u in planned), default=0)
        lead = req.lead - sum(u.days for u in planned)
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
            if day is None or day > latest_ready - lead:
                return None, f"{req.label}: Farming {level} isn't reached in time with {self.sim.tiles} tiles"
            start = max(start, day)
        first = max(self.today, req.earliest - lead, start if start != req.earliest else 1)
        if latest_ready - lead < self.today:
            return None, f"{req.label}: too late, the last day to start was {self.farm.label(latest_ready - lead)}"
        if after + lead > latest_ready:
            return None, (f"{req.label}: not in time: waiting on an earlier step, it can't be ready before "
                          f"{self.farm.label(after + lead)}")
        why = {"days": 0, "cash": 0, "robin": 0, "clint": 0, "only": 0}
        for b in range(first, latest_ready - lead + 1):
            # the latest free days before it (after the Steel Axe, if Hardwood needs it)
            chop = self.free_days(self.today + axe_days, b - 1)[-chops:] if chops else []
            if len(chop) < chops:
                why["days"] += 1
                continue
            mine = self.mining_days(floor_need, b, extra_mine)
            if mine is None:
                why["days"] += 1
                continue
            if any(s < e2 and s2 < e for s, e in self.robin_jobs(req.chain, b) for s2, e2 in self.robin):
                why["robin"] += 1  # she's still on another job
                continue
            if any(s < e2 and s2 < e for s, e in self.clint_jobs(req.chain, b) for s2, e2 in self.clint):
                why["clint"] += 1  # he still has another tool
                continue
            if self.would_go_negative(b, gold, chop, mine):
                why["cash"] += 1
                continue
            ready = max(b, after, max(mine, default=0) + 1) + lead
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
            elif req.activity in ("forage", "social"):
                act = max(ready, req.earliest)  # picked up on the way: no day of its own
                if req.days is not None:
                    act = min((d for d in req.days if act <= d <= latest_ready), default=None)
                    if act is None:
                        why["only"] += 1
                        break  # starting later only makes it later
            needs = self.needs(req.chain, b, chop)
            first_day = min([b, *chop, *mine])
            last_start = latest_ready - lead - (b - first_day)  # chopping and mining come before it
            return Step(req.label, b, act or ready, gold, chop, mine, needs, req.season, act,
                        last=last_start), ""
        last = max(1, latest_ready - lead)
        if why["only"]:
            return None, (f"{req.label}: none of the days it can be done is left once the rest is ready "
                          f"(the last was {self.farm.label(max(req.days))})" if req.days else
                          f"{req.label}: none of the days it can be done is left")
        if why["clint"] and why["clint"] >= why["days"] + why["cash"] + why["robin"]:
            free = max(e for _s, e in self.clint)
            return None, f"{req.label}: Clint has another tool until {self.farm.label(free)} (one at a time)"
        if why["robin"] and why["robin"] >= why["days"] + why["cash"]:
            free = max(e for _s, e in self.robin)
            return None, f"{req.label}: Robin is busy building until {self.farm.label(free)} (one job at a time)"
        if gold and why["cash"] < why["days"] and self.would_go_negative(last, gold, []):
            why["cash"] = why["days"]  # even with every day free, the gold isn't there
        if why["cash"] >= why["days"]:
            short = min(x.cash for x in self.result([(last, gold)] if gold else []).days) if gold else 0
            if gold and short < 0:
                return None, f"{req.label}: about {-short:,}g short by {self.farm.label(last)}"
            return None, f"{req.label}: the cash is all committed by {self.farm.label(last)}"
        if floor_need and self.floor_by(last) < floor_need:
            return None, f"{req.label}: Mines floor {floor_need} isn't reached by {self.farm.label(last)}"
        return None, f"{req.label}: not enough Wood chopped by {self.farm.label(last)}"

    def place_any(self, req: Req, deadline: int) -> tuple[Step | None, Req | None, str]:
        """Place a requirement, or the first of its fallbacks that fits: (step, the one placed, why not)."""
        first_why = ""
        now: Req | None = req
        while now:
            step, why = self.place(now, deadline)
            if step is not None:
                if now is not req:
                    self.info.append(f"{req.label}: {req.season} won't work, so it's planned another way "
                                     f"({now.season or now.label})")
                return step, now, why
            first_why = first_why or why
            now = now.fallback
        return None, None, first_why

    def needs(self, chain: list[Unlock], day: int, chop: list[int] = ()) -> list[dict]:
        """The unlocks behind a step as the tree shows them: done already, planned for an earlier step, or new."""
        extras = self.cost_extras(chain)
        out, start = [], None
        # the axe upgrades come before the Hardwood days, the rest on the day itself
        t = max(self.today, min(chop) - sum(u.days for u in extras)) if extras and chop else day
        for i, u in enumerate(extras + chain):
            if i == len(extras):
                t = max(t, day)
            if u.done:
                state, when = "done", None
            elif u.key in self.have:
                state, when = "earlier", self.have[u.key]
                t = max(t, when)
            else:
                start = t
                t += u.days
                state, when = "new", t
            out.append({"key": u.key, "label": u.label, "state": state, "on": start if state == "new" else None,
                        "ready": self.farm.label(when) if when else "",
                        "gold": u.gold if state == "new" else 0, "how": u.how,
                        "materials": [f"{n} {self.farm.name(f'(O){m}')}" for m, n in u.materials]
                        if state == "new" else []})
        return out

    def would_go_negative(self, day: int, gold: int, days: list[int], mine: list[int] = ()) -> bool:
        """Spending `gold` on `day`, giving up fishing on `days` and mining on `mine` (which pays its own way):
        does the cash dip below zero any time?"""
        before = dict(self.busy)
        base = min(x.cash for x in self.result().days)
        for d in days:
            self.busy.setdefault(d, ("chop", ""))
        for d in mine:
            self.busy.setdefault(d, ("mine", ""))
        try:
            low = min(x.cash for x in self.result([(day, gold)] if gold else []).days)
            return low < 0 and low < base  # it's this purchase that would take the cash below zero
        finally:
            self.busy = before

    def floor_by(self, day: int) -> int:
        """Deepest floor reached before `day` with the mining days booked so far."""
        have = self.farm.when.mine_lowest
        trips = sum(1 for d, w in self.busy.items() if w[0] == "mine" and d < day)
        return have + self.pace.floors_per_week * trips

    def mining_days(self, floor: int, by: int, extra: int = 0) -> list[int] | None:
        """New mining days needed (before `by`) to have reached `floor`, plus `extra` days of gathering. One trip
        down a week at most, the latest free days first: cash is easier then."""
        have = self.floor_by(by)
        trips = math.ceil((floor - have) / self.pace.floors_per_week) if floor > have else 0
        free = self.free_days(max(self.today, self.year_start + MINES_OPEN), by - 1)
        taken = {(d - 1) // 7 for d, w in self.busy.items() if w[0] == "mine"}
        days: list[int] = []
        for d in reversed(free):
            if len(days) < trips and (d - 1) // 7 not in taken:
                days.append(d)
                taken.add((d - 1) // 7)
        if len(days) < trips:
            return None
        spare = [d for d in free if d not in days]
        if len(spare) < extra:
            return None
        return sorted(days + (spare[-extra:] if extra else []))

    def cost_extras(self, chain: list[Unlock]) -> list[Unlock]:
        """Unlocks a chain brings in that aren't in it: the Steel Axe for Hardwood."""
        if any(m == HARDWOOD for u in chain for m, _ in u.materials):
            return [u for u in self.planner.unlocks.chain("tool:Axe@2") if u.key not in self.have]
        return []

    def pay_vault(self, gold: int, out: Outcome, placed: list) -> None:
        res = self.result()
        day = next((d.day for d in res.days if self.result([(d.day, gold)]).lowest_from(d.day) >= 0), None)
        if day is None or day > out.deadline:
            out.problems.append(f"the Vault's {gold:,}g isn't there by {self.farm.label(out.deadline)}")
            out.misses.append((f"the Vault ({gold:,}g)", f"the gold isn't there by {self.farm.label(out.deadline)}"))
            return
        self.spends.append((day, gold))
        self.vault_day = day
        step = Step(f"pay the Vault ({gold:,}g)", day, day, gold)
        self.got.setdefault(VAULT_STEP, (step, self.current))
        placed.append((step, Req("vault", day, day, [], 0)))

    def robin_jobs(self, chain: list[Unlock], day: int) -> list[tuple[int, int]]:
        """The [order day, ready day) of each new building or house upgrade in a chain started on `day`."""
        return self._jobs(chain, day, ("building:", "kitchen", "house:"), "Robin finishes")

    def clint_jobs(self, chain: list[Unlock], day: int) -> list[tuple[int, int]]:
        """The [hand-in day, collect day) of each new tool upgrade in a chain started on `day` (the Steel Axe a
        Hardwood chain brings comes first)."""
        return self._jobs(self.cost_extras(chain) + chain, day, ("tool:",), "Clint finishes")

    def _jobs(self, chain: list[Unlock], day: int, keys: tuple[str, ...], ongoing: str) -> list[tuple[int, int]]:
        out, t = [], day
        for u in chain:
            if u.key in self.have:
                t = max(t, self.have[u.key])
            elif not u.done:
                start, t = t, t + u.days
                if u.key.startswith(keys) and not u.label.startswith(ongoing):
                    out.append((start, t))
        return out

    def commit(self, step: Step, req: Req) -> None:
        self.robin += self.robin_jobs(req.chain, step.day)
        self.clint += self.clint_jobs(req.chain, step.day)
        wood = sum(n for u in req.chain if u.key not in self.have and not u.done for m, n in u.materials if m == WOOD)
        self.wood_left = max(0, self.wood_left - wood)
        if step.gold:
            self.spends.append((step.day, step.gold))
        for d in step.chop_days:
            self.busy.setdefault(d, ("chop", self.current))
        for d in step.mine_days:
            self.busy.setdefault(d, ("mine", self.current))
        if req.activity == "fish":
            self.fish_days.setdefault(req.season, step.ready)
            self.busy.setdefault(step.ready, ("fish", self.current))
        t = step.day
        for u in req.chain + self.cost_extras(req.chain):
            if u.key in self.have:
                t = max(t, self.have[u.key])
            elif not u.done:
                t += u.days
                self.have[u.key] = t
        self.got.setdefault(req.label, (step, self.current))

    def objective(self, oid: str, tier: str, deadline: int | None = None) -> Outcome:
        label, default = CATALOG.get(oid, (oid, YEAR_DAYS))
        if deadline is None:
            deadline = self.year_start + default
            if deadline < self.today + 14:  # the usual date has (nearly) gone by: aim for the year's end instead
                deadline = self.end
        out = Outcome(oid, label, tier, deadline)
        self.current = oid
        self.outcomes[oid] = out
        if self.done(oid):
            out.status, out.finish = "done", self.today
            return out
        self.misses, self.info = [], []
        firsts = [self.outcomes[n] for n in (OBJECTIVES[oid].needs if oid in OBJECTIVES else ())
                  if n in self.outcomes]
        stuck = [o for o in firsts if o.status != "done" and (o.status != "ok" or o.finish is None)]
        if stuck:  # nothing here can happen until they do
            for o in stuck:
                out.misses.append((o.label, f"needed first, and it isn't planned in time ({o.status})"))
                out.problems.append(f"{o.label} comes first, and it isn't planned in time")
            out.status = "impossible"
            return out
        gate = max((o.finish or self.today for o in firsts), default=self.today)
        self.info += [f"{o.label} comes first: planned alongside this goal" for o in firsts if o.status != "done"]
        reqs, paid, notes = self.requirements(oid)
        reqs = [replace(q, earliest=max(q.earliest, gate)) for q in reqs]
        self.explain(reqs)
        out.info = self.info
        out.misses += self.misses
        out.problems += [f"{w}: {y}" for w, y in self.misses]
        out.problems += notes
        out.notes = list(notes)
        reqs.sort(key=lambda r: (r.latest or 0) - r.lead)
        placed: list[tuple[Step, Req]] = []
        desert = [r for r in reqs if any(u.key == "place:Desert" for u in r.chain)]
        reqs = [r for r in reqs if r not in desert]
        for r in reqs + ([None] if paid else []) + desert:
            if r is None:  # the Vault, after everything else and before the desert's items (it brings the bus)
                self.pay_vault(paid, out, placed)
                continue
            if r.label in self.got and self.got[r.label][1] != oid:  # another objective already gets this
                st, owner = self.got[r.label]
                placed.append((Step(st.label, st.day, st.ready, how=st.how, act=st.act, shared=owner,
                                    needs=[{**n, "state": "earlier", "gold": 0, "materials": []}
                                           for n in st.needs]), r))
                continue
            step, used, why = self.place_any(r, out.deadline)
            if step is None:
                out.problems.append(why)
                out.misses.append((r.label, why.removeprefix(f"{r.label}: ")))
            else:
                placed.append((step, used))
                self.commit(step, used)  # provisionally, so later requirements see it
        if self.vault_day is not None and oid == "cc":  # the bus is coming: slots only the desert fills
            done = {st.label for st, _ in placed}
            for r in self.bundle_reqs():
                if r.label in done or not any(u.key == "place:Desert" for u in r.chain):
                    continue
                step, used, why = self.place_any(r, out.deadline)
                if step:
                    placed.append((step, used))
                    self.commit(step, used)
                    out.problems = [p for p in out.problems if not p.startswith(r.label)]
                    out.misses = [m for m in out.misses if m[0] != r.label]
        pendant = next((st for st, _ in placed if st.label == "the Mermaid's Pendant"), None)
        if oid == "marriage" and pendant and self.wedding:
            d = pendant.ready + romance.WEDDING_DELAY
            while d in self.festivals:
                d += 1
            if d <= out.deadline:
                placed.append((Step(f"the wedding with {self.wedding}", d, d, how="three days after the proposal"),
                               Req("wedding", d, d, [], 0)))
            else:
                out.misses.append((f"the wedding with {self.wedding}", f"three days after, on {self.farm.label(d)}"))
                out.problems.append(f"the wedding: {self.farm.label(d)}")
        out.steps = [s for s, _ in sorted(placed, key=lambda p: p[0].day)]
        out.finish = max((s.ready for s in out.steps), default=None)
        if out.problems:
            out.status = "impossible" if any("only by luck" not in p for p in out.problems) else "luck"
        if oid == "greenhouse" and not out.problems and out.finish:
            self.greenhouse_day = out.finish + 1
        if oid == "seed_maker" and not out.problems and out.finish:
            self.seed_maker_day = out.finish
        return out




def _inherited(deadlines: dict[str, int] | None) -> dict[str, int]:
    """A goal's deadline holds for what has to come before it."""
    out = dict(deadlines or {})

    def pull(oid: str, day: int) -> None:
        for first in OBJECTIVES[oid].needs if oid in OBJECTIVES else ():
            out[first] = min(out.get(first, day), day)
            pull(first, out[first])

    for oid, day in list(out.items()):
        pull(oid, day)
    return out


def route(farm, targets: list[str], nice: list[str] = (), *, settings: Settings | None = None,
          deadlines: dict[str, int] | None = None, cave: str = "best", tiles: int | None = None) -> dict:
    """Plan targets (in order) then nice-to-haves (in order); what each achieves, when, and what can't be.
    `cave`: "bats" or "mushrooms", or "best" to plan both and keep the one that achieves more (targets first,
    then nice-to-haves, then the year's end cash)."""
    settings = settings or Settings()
    targets, nice = with_needs(targets, nice)
    deadlines = _inherited(deadlines)
    if tiles is not None:
        settings = Settings(**{**settings.__dict__, "tiles": tiles})
    if cave == "best" and getattr(farm.save, "cave_choice", 0):
        cave = {1: "bats", 2: "mushrooms"}[farm.save.cave_choice]  # already chosen in this save
    if cave == "best":
        plans = [_route(farm, targets, nice, settings, deadlines, c) for c in ("bats", "mushrooms")]

        def score(p):
            ok = [o["status"] == "ok" for o in p["objectives"]]
            return (sum(ok[:len(targets)]), sum(ok[len(targets):]), p["end_cash"])

        best = max(plans, key=score)
        best["cave_options"] = [{"cave": p["cave"], "targets_ok": score(p)[0], "nice_ok": score(p)[1],
                                 "end_cash": p["end_cash"], "offer": p["cave_day"]} for p in plans]
        return best
    return _route(farm, targets, nice, settings, deadlines, cave)


WEEKS = YEAR_DAYS // 7


def _route(farm, targets, nice, settings, deadlines, cave) -> dict:
    r = Router(farm, settings=settings, cave=cave)
    outcomes = [r.objective(o, "target", (deadlines or {}).get(o)) for o in targets]
    outcomes += [r.objective(o, "nice", (deadlines or {}).get(o)) for o in nice]
    res = r.result()

    def label(d):
        return farm.label(d) if d else ""

    def week(d):
        return min(WEEKS - 1, max(0, (d - 1 - r.year_start) // 7))

    matrix = []
    for o in outcomes:
        cells = [{"buy": [], "ready": [], "gold": 0, "days": {}} for _ in range(WEEKS)]
        for st in o.steps:
            if st.gold:
                c = cells[week(st.day)]
                c["buy"].append(st.label)
                c["gold"] += st.gold
            if st.ready:
                cells[week(st.ready)]["ready"].append(st.label)
        for d, (what, owner) in r.busy.items():
            if owner == o.id:
                c = cells[week(d)]["days"]
                c[what] = c.get(what, 0) + 1
        matrix.append({"id": o.id, "cells": cells})
    agenda = _agenda(farm, outcomes, r.today, res)
    tree = _tree(farm, outcomes, r.today, r.end)
    offer = r.cave_day() if farm.save.cave_choice else res.earned_day(EARNINGS_TRIGGER)
    return {
        "settings": settings.__dict__, "cave": cave, "cave_day": label(offer),
        "cave_chosen": bool(farm.save.cave_choice),  # the save has already made the choice
        "objectives": [{"id": o.id, "label": o.label, "tier": o.tier, "status": o.status,
                        "deadline": label(o.deadline), "finish": label(o.finish), "problems": o.problems,
                        "gold": sum(st.gold for st in o.steps),
                        "steps": [{"what": st.label, "day": label(st.day), "ready": label(st.ready),
                                   "gold": st.gold, "chop_days": len(st.chop_days),
                                   "mine_days": len(st.mine_days), "chop": _span(farm, st.chop_days),
                                   "mine": _span(farm, st.mine_days), "needs": st.needs, "how": st.how,
                                   "act": label(st.act), "n": st.day, "last": label(st.last),
                                   "slack": (st.last - r.today) if st.last is not None else None,
                                   "shared": CATALOG.get(st.shared, (st.shared,))[0] if st.shared else ""}
                                  for st in o.steps],
                        "misses": [{"what": w, "why": y} for w, y in o.misses], "notes": o.notes,
                        "info": o.info}
                       for o in outcomes],
        "weeks": [label(r.year_start + 1 + 7 * w) for w in range(WEEKS)],
        "today": label(r.today),
        "agenda": agenda,
        "tree": tree,
        "matrix": matrix,
        "cash": [{"day": d.day, "cash": d.cash, "earned": d.earned, "farming": d.level} for d in res.days],
        "end_cash": res.days[-1].cash if res.days else 0,
        "days": {k: sum(1 for w, _ in r.busy.values() if w == k) for k in ("chop", "mine", "fish")},
    }
