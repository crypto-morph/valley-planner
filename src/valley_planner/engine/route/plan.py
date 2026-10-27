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
import re
from dataclasses import dataclass, field

from ...facts import romance
from ...facts.bundles import VAULT
from ...facts.cave import EARNINGS_TRIGGER, gives, nights_for
from ..cc import Planner, Slot, Way
from ..unlocks import Unlock
from .simulate import YEAR_DAYS, Farmsim

WOOD, STONE, HARDWOOD = "388", "390", "709"
@dataclass
class Settings:
    """The planning choices, all tunable from the page."""
    tiles: int = 80  # tiles farmed
    wood_per_day: int = 100  # Wood from a day spent chopping
    floors_per_day: int = 8  # Mines floors gained in a day spent mining
    hardwood_per_day: int = 12  # the Secret Woods' six large stumps, two Hardwood each
    fish_gold: int = 300  # a spare day spent fishing, sold at normal quality
    mine_gold: int = 200  # ore, gems, geodes and minerals sold from a day in the Mines
    float: int = 500  # cash never spent on seeds
    quartz_per_day: int = 6  # Quartz found in a day in the Mines (for Refined Quartz)
    gift_points: int = 80  # friendship from each gift to your sweetheart (loved 80, liked 45)
    spouse: str = ""  # who to marry; empty: whoever you're closest to
    jars: int = 10  # Preserves Jars to have
    kegs: int = 10  # Kegs to have
    tappers: int = 5  # Tappers put on oaks for the Kegs' Oak Resin
    clay_per_day: int = 10  # Clay from a day hoeing the Mines' dirt (about one tile in seven gives some)


WOOD_PER_DAY = Settings.wood_per_day
FLOORS_PER_DAY = Settings.floors_per_day

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
    "stable": ("A horse", 112),
    "sprinklers": ("Quality Sprinklers for the field", 112),
    "house_2": ("The second house upgrade", 112),
    "marriage": ("Marriage", 112),
    "deluxe_barn": ("A Deluxe Barn", 112),
    "deluxe_coop": ("A Deluxe Coop", 112),
    "silo": ("A Silo", 112),
    "axe_steel": ("A Steel Axe (the Secret Woods)", 112),
    "pickaxe_steel": ("A Steel Pickaxe", 112),
    "can_steel": ("A Steel Watering Can", 112),
    "mines_bottom": ("The bottom of the Mines (Skull Key)", 112),
    "skull_cavern": ("The Skull Cavern", 112),
    "jars": ("Preserves Jars", 112),
    "kegs": ("Kegs", 112),
    "house_3": ("The cellar (third house upgrade)", 112),
}
UNLOCK_GOALS = {  # objectives that are one unlock: (its key, what the route calls it)
    "stable": ("building:Stable", "the Stable"),
    "house_2": ("house:2", "the second house upgrade"),
    "house_3": ("house:3", "the third house upgrade (the cellar)"),
    "deluxe_barn": ("building:Deluxe Barn", "a Deluxe Barn"),
    "deluxe_coop": ("building:Deluxe Coop", "a Deluxe Coop"),
    "silo": ("building:Silo", "a Silo"),
    "axe_steel": ("tool:Axe@2", "a Steel Axe"),
    "pickaxe_steel": ("tool:Pickaxe@2", "a Steel Pickaxe"),
    "can_steel": ("tool:WateringCan@2", "a Steel Watering Can"),
    "mines_bottom": ("floor:120", "Mines floor 120 (the Skull Key)"),
}
MACHINE_GOALS = {"jars": ("15", "Preserves Jars"), "kegs": ("12", "Kegs")}  # objective -> (big craftable, plural)
QUARTZ, REFINED_QUARTZ, SPRINKLER = "80", "338", "621"
CLAY, OAK_RESIN, TAPPER = "330", "725", "105"
SPRINKLER_TILES = 8  # a Quality Sprinkler waters the eight tiles around it
SKULL_KEY_FLOOR = 120  # the Mines' last floor: its chest holds the Skull Key
BUS_TICKET = 500  # BusStop.TicketPrice
VAULT_STEP = "the Vault"  # the requirement the Vault's gold is shared under


@dataclass
class Step:
    label: str
    day: int  # when it's bought / done
    ready: int  # when it's in hand
    gold: int = 0
    chop_days: list[int] = field(default_factory=list)
    mine_days: list[int] = field(default_factory=list)
    needs: list[dict] = field(default_factory=list)  # the unlocks behind it, prerequisites first
    how: str = ""  # the way it's got (a shop, a fishing spot, an animal)
    act: int | None = None  # a day spent getting it (fishing), if any
    shared: str = ""  # already planned for this other objective
    last: int | None = None  # the last day it can start and still be in time


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
    misses: list[tuple[str, str]] = field(default_factory=list)  # (requirement, why it can't be planned)
    notes: list[str] = field(default_factory=list)  # problems that aren't one requirement's
    info: list[str] = field(default_factory=list)  # how it's been planned, worth knowing


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
        self.vault_day: int | None = None
        self.got: dict[str, tuple[Step, str]] = {}  # requirement -> its step, and the objective that planned it
        self.held = farm.held()
        self.wood_left = self.held.get(f"(O){WOOD}", 0)  # Wood in hand, used before any chopping
        self.fish_days: dict[str, int] = {}
        self.wedding: str | None = None  # who the route marries, once the Pendant is placed
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

    def done(self, oid: str) -> bool:
        s = self.farm.save
        cc = bool(s.areas_complete) and all(s.areas_complete)
        if oid == "marriage":
            return any(f.status in ("Married", "Engaged") for f in s.friends.values())
        if oid == "mines_bottom" and "HasSkullKey" in s.mail:
            return True
        if oid == "skull_cavern":  # Skull Cavern floors are kept as 120 + the floor
            return getattr(s, "deepest_mine_level", 0) > SKULL_KEY_FLOOR
        if oid in UNLOCK_GOALS:
            return self.planner.unlocks.get(UNLOCK_GOALS[oid][0]).done
        if oid in MACHINE_GOALS:
            return self.machines(MACHINE_GOALS[oid][0]) >= getattr(self.s, oid)
        return {"greenhouse": "ccPantry" in s.mail, "seed_maker": bool(s.machines.get("Seed Maker")),
                "kitchen": s.house_upgrade >= 1, "cc": cc,
                "sprinklers": self.held.get(f"(O){SPRINKLER}", 0) >= self.sprinklers()}.get(oid, False)

    def machines(self, bc: str) -> int:
        """How many of a machine you have: in hand or in chests, and placed."""
        name = (self.farm.data.asset("Data/BigCraftables").get(bc) or {}).get("Name", bc)
        return self.held.get(f"(BC){bc}", 0) + self.farm.save.machines.get(name, 0)

    def sprinklers(self) -> int:
        return math.ceil(self.s.tiles / SPRINKLER_TILES)

    def sweetheart(self) -> str | None:
        """Who to marry: the setting, or the romanceable villager you're closest to."""
        chars = self.farm.data.asset("Data/Characters")
        can = [k for k, v in chars.items() if v.get("CanBeRomanced")]
        if self.s.spouse in can:
            return self.s.spouse
        friends = self.farm.save.friends
        return max(can, key=lambda k: friends[k].points if k in friends else -1, default=None)

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
        cave = self.cave_req(s)
        if cave:
            return cave
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
            if vault and self.vault_day is not None:  # another goal already pays it
                return self.bundle_reqs() + [Req(VAULT_STEP, self.vault_day, self.end, [], 0)], 0, []
            return self.bundle_reqs(), vault, []
        if oid == "kitchen":
            u = self.planner.unlocks.get("kitchen")
            return [Req("the kitchen", self.today, self.end, [u], u.days)], 0, []
        if oid == "seed_maker":
            u = self.planner.unlocks.get("machine:(BC)25")
            u.how = "Farming level 9"
            return [Req("a Seed Maker", self.today, self.end, [u], 0)], 0, []
        if oid in UNLOCK_GOALS:
            key, label = UNLOCK_GOALS[oid]
            u = self.planner.unlocks.chain(key)
            if key.startswith("tool:"):
                self.info.append("Clint takes one tool at a time, for two days, and you're without it meanwhile")
                if "WateringCan" in key:
                    self.info.append("Leave the can with Clint on a rainy day, or once sprinklers do the watering")
            return [Req(label, self.today, self.end, u, sum(x.days for x in u))], 0, []
        if oid in MACHINE_GOALS:
            return self.machine_reqs(oid)
        if oid == "skull_cavern":
            return self.skull_cavern()
        if oid == "sprinklers":
            n = self.sprinklers() - self.farm.held().get(f"(O){SPRINKLER}", 0)
            recipe = self.planner.unlocks.chain("recipe:Quality Sprinkler")
            craft = Unlock("craft:sprinklers", f"craft {n} Quality Sprinklers", 0,
                           [("335", n), ("336", n), (REFINED_QUARTZ, n)],
                           after=[u.key for u in recipe])
            self.info.append("Bars are priced as ore bought from Clint (Year 1); mining your own saves gold "
                             "but costs days")
            return [Req(f"{n} Quality Sprinklers", self.today, self.end, recipe + [craft], 0)], 0, []
        if oid == "marriage":
            return self.courtship()
        return [], 0, [f"unknown objective {oid}"]

    def crafted(self, bc: str, n: int, plural: str) -> list[Unlock]:
        """The recipe (if it isn't known) and crafting n of a machine."""
        m = self.planner.unlocks.get(f"machine:(BC){bc}")
        recipe = [u for k in m.after for u in self.planner.unlocks.chain(k)]
        return recipe + [Unlock(f"craft:{bc}", f"craft {n} {plural}", 0, [(x, k * n) for x, k in m.materials],
                                after=[u.key for u in recipe])]

    def tap_days(self, item: str) -> int | None:
        """Days a Tapper takes to give `item` on the wild tree that gives it (Data/WildTrees)."""
        for t in self.farm.data.asset("Data/WildTrees").values():
            for tap in t.get("TapItems") or []:
                if (tap.get("ItemId") or "").removeprefix("(O)") == item and not tap.get("Condition"):
                    return int(tap.get("DaysUntilReady") or 0)
        return None

    def machine_reqs(self, oid: str) -> tuple[list[Req], int, list[str]]:
        """Craft the machines still missing; Kegs need an Oak Resin each, from Tappers on oak trees first."""
        bc, plural = MACHINE_GOALS[oid]
        n = getattr(self.s, oid) - self.machines(bc)
        reqs, chain = [], []
        if oid == "kegs":
            resin = max(0, n - self.held.get(f"(O){OAK_RESIN}", 0))
            days = self.tap_days(OAK_RESIN)
            if resin and days:
                taps = max(1, min(self.s.tappers, resin))
                have = self.held.get(f"(BC){TAPPER}", 0)
                chain = self.crafted(TAPPER, taps - have, "Tappers") if taps > have else []
                rounds = math.ceil(resin / taps)
                chain.append(Unlock("tap:oak", f"tap {taps} oak trees for {resin} Oak Resin", 0, [], days * rounds,
                                    [u.key for u in chain[-1:]],
                                    how=f"a Tapper on a grown oak gives one Oak Resin every {days} days"))
                reqs.append(Req(f"{resin} Oak Resin", self.today, self.end, list(chain), sum(u.days for u in chain)))
                self.info.append(f"{resin} Oak Resin from {taps} Tappers takes {rounds * days} days "
                                 f"({rounds} round{'s' if rounds > 1 else ''}); more Tappers (a setting) shorten it")
                placed = self.farm.save.machines.get("Tapper", 0)
                if placed:
                    self.info.append(f"Your {placed} placed Tapper{'s' if placed > 1 else ''} aren't counted: one "
                                     f"moved onto an oak saves crafting one")
        chain += self.crafted(bc, n, plural)
        if any(m == "382" for u in chain for m, _ in u.materials):
            self.info.append("Coal is priced at Clint's; mining it or a Charcoal Kiln saves gold but costs days")
        reqs.append(Req(f"{n} {plural}", self.today, self.end, chain, sum(u.days for u in chain)))
        return reqs, 0, []

    def skull_cavern(self) -> tuple[list[Req], int, list[str]]:
        """The Skull Key from the Mines' floor 120, then the bus to the Desert, which needs the Vault."""
        u = self.planner.unlocks
        chain = u.chain(f"floor:{SKULL_KEY_FLOOR}") + u.chain("place:Desert") + \
            [Unlock("bus_ticket", "buy a bus ticket to the Desert", BUS_TICKET)]
        paid = 0
        if not u.get("place:Desert").done:
            if self.vault_day is None:
                paid = sum(b.gold or 0 for b in self.farm.bundles.in_area(VAULT) if not b.done)
                self.info.append(f"The bus to the Desert only runs once the Community Center's Vault is done: "
                                 f"{paid:,}g in its bundles, planned here (the Community Center goal shares it). "
                                 f"You can pay it once you can read the Junimos' notes")
            else:
                self.info.append("The bus comes with the Vault, already planned for another goal")
        return [Req("the Skull Cavern", self.today, self.end, chain, sum(x.days for x in chain))], paid, []

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

    def _later(self, day: int | None) -> str:
        return f"not this year: about {self.farm.label(day)}" if day else "not within two years at this pace"

    def courtship(self) -> tuple[list[Req], int, list[str]]:
        """Hearts by talking every day and two gifts a week, the Bouquet at 8 hearts, the Mermaid's Pendant at
        10 on a rainy day (after the first house upgrade, past the beach bridge); the wedding comes after."""
        name = self.sweetheart()
        if not name:
            return [], 0, ["no one to marry"]
        info = self.farm.data.asset("Data/Characters")[name]
        f = self.farm.save.friends.get(name)
        points, status = (f.points, f.status) if f else (0, "Friendly")
        seasons = ["spring", "summer", "fall", "winter"]
        bseason = (info.get("BirthSeason") or "").lower()
        birthday = seasons.index(bseason) * 28 + int(info.get("BirthDay") or 0) if bseason in seasons else None
        gift, notes, reqs = self.s.gift_points, [], []
        how = f"talk to {name} every day and give two gifts a week"
        day8 = self.today
        if status != "Dating":
            day8 = romance.points_day(points, 8 * romance.HEART, self.today, birthday=birthday, gift=gift,
                                      cap=romance.CAP_FRIEND)
            if day8 is None or day8 > self.end:
                self.misses = [(f"8 hearts with {name}", self._later(day8))]
                return [], 0, []
            price = 2 * int((self.farm.data.asset("Data/Objects").get(romance.BOUQUET) or {}).get("Price") or 100)
            reqs.append(Req(f"8 hearts with {name}", day8, self.end, [], 0, "social", season=how))
            reqs.append(Req(f"a Bouquet for {name}", day8, self.end,
                            [Unlock("bouquet", "buy a Bouquet from Pierre", price)], 0, season=f"give it to {name}"))
            points = 8 * romance.HEART
        day10 = romance.points_day(points, 10 * romance.HEART, day8 + 1, birthday=birthday, gift=gift)
        if day10 is None or day10 > self.end:
            self.misses = [(f"10 hearts with {name}", self._later(day10))]
            return reqs, 0, []
        reqs.append(Req(f"10 hearts with {name}", day10, self.end, [], 0, "social", season=how))
        rain = romance.rain_by(day10)
        if rain is None or rain > self.end:
            first = next((d for d in range(day10, day10 + romance.YEAR) if romance.rain_chance(d)), day10)
            self.misses = [("the Mermaid's Pendant",
                            f"the Old Mariner only comes when it rains, and it doesn't rain in winter: "
                            f"10 hearts on {self.farm.label(day10)}, the next chance of rain from "
                            f"{self.farm.label(first)}")]
            return reqs, 0, []
        pendant = 2 * int((self.farm.data.asset("Data/Objects").get(romance.PENDANT) or {}).get("Price") or 2500)
        chain = self.planner.unlocks.chain("kitchen") + self.planner.unlocks.chain("place:BeachTidePools") + \
            [Unlock("pendant", "buy the Mermaid's Pendant from the Old Mariner", pendant)]
        lead = sum(u.days for u in chain)
        reqs.append(Req("the Mermaid's Pendant", rain or day10, self.end, chain, lead, "social",
                        season=f"on a rainy day, the Old Mariner past the beach bridge; propose to {name}"))
        self.wedding = name
        return reqs, 0, notes

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
        why = {"days": 0, "cash": 0}
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
            if self.would_go_negative(b, gold, chop + mine):
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
            needs = self.needs(req.chain, b, chop)
            first_day = min([b, *chop, *mine])
            last_start = latest_ready - lead - (b - first_day)  # chopping and mining come before it
            return Step(req.label, b, act or ready, gold, chop, mine, needs, req.season, act,
                        last=last_start), ""
        last = max(1, latest_ready - lead)
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

    def would_go_negative(self, day: int, gold: int, days: list[int]) -> bool:
        """Spending `gold` on `day` and giving up fishing on `days`: does the cash dip below zero any time?"""
        before = dict(self.busy)
        base = min(x.cash for x in self.result().days)
        for d in days:
            self.busy.setdefault(d, ("chop", ""))
        try:
            low = min(x.cash for x in self.result([(day, gold)] if gold else []).days)
            return low < 0 and low < base  # it's this purchase that would take the cash below zero
        finally:
            self.busy = before

    def floor_by(self, day: int) -> int:
        """Deepest floor reached before `day` with the mining days booked so far."""
        have = self.farm.when.mine_lowest
        return have + self.s.floors_per_day * sum(1 for d, w in self.busy.items() if w[0] == "mine" and d < day)

    def mining_days(self, floor: int, by: int, extra: int = 0) -> list[int] | None:
        """New mining days needed (before `by`) to have reached `floor`, plus `extra` days of gathering."""
        have = self.floor_by(by)
        n = extra + (math.ceil((floor - have) / self.s.floors_per_day) if floor > have else 0)
        if not n:
            return []
        # the latest free days before it: cash is easier then
        days = self.free_days(max(self.today, self.year_start + MINES_OPEN), by - 1)[-n:]
        return days if len(days) == n else None

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

    def commit(self, step: Step, req: Req) -> None:
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
        if self.done(oid):
            out.status, out.finish = "done", self.today
            return out
        self.misses, self.info = [], []
        reqs, paid, notes = self.requirements(oid)
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
            step, why = self.place(r, out.deadline)
            if step is None:
                out.problems.append(why)
                out.misses.append((r.label, why.removeprefix(f"{r.label}: ")))
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


AGENDA_DAYS = 7
SOON, NOW = 14, 7  # days to spare: up to NOW is this week's, up to SOON is soon


def _urgency(slack: int | None) -> str:
    if slack is None:
        return "plenty"
    return "now" if slack <= NOW else "soon" if slack <= SOON else "plenty"


def _tree(farm, outcomes: list[Outcome], today: int, end: int) -> dict:
    """The route as a tech tree: a lane per goal, weekly columns from today, and in each lane rows of cards, each
    row one thing the goal needs with its steps left to right (chop, build, buy, then the item). A card that
    serves more than one goal says which."""
    n_cols = max(1, (end - today) // 7 + 1)

    def col(d):
        return min(n_cols - 1, max(0, (d - today) // 7))

    columns = [{"label": _week_label(farm, today + 7 * i, min(end, today + 7 * i + 6)), "gold": 0}
               for i in range(n_cols)]
    names = {o.id: o.label for o in outcomes}
    # who else uses what a step brings: unlocks planned "earlier", and whole requirements shared
    users: dict[str, list[dict]] = {}
    shared_by: dict[str, list[dict]] = {}
    for o in outcomes:
        for st in o.steps:
            if st.shared:
                shared_by.setdefault(st.label, []).append({"goal": o.label, "why": st.label})
                continue
            for n in st.needs:
                if n["state"] == "earlier":
                    users.setdefault(n["key"], []).append({"goal": o.label, "why": st.label})
    synergy: dict[str, dict] = {}
    lanes = []
    for o in outcomes:
        steps = []
        for st in o.steps:
            own = {"goal": o.label, "why": st.label}
            item = st.label.split(" (")[0]
            if st.shared:
                steps.append([{"col": col(st.ready), "tag": "SHARED", "title": item, "urgency": "shared",
                               "detail": f"planned under {names.get(st.shared, st.shared)}", "gold": 0,
                               "helps": [], "waits": []}])
                continue
            urgency = "daily" if st.how.startswith("talk to") else _urgency(
                None if st.last is None else st.last - today)
            cards: list[dict] = []
            new = [n for n in st.needs if n["state"] == "new"]
            hard = any(m.endswith(" Hardwood") for n in new for m in n["materials"])
            if st.chop_days:
                cards.append({"col": col(min(st.chop_days)), "tag": "CHOP",
                              "title": f"{'Wood and Hardwood' if hard else 'Wood'}, {len(st.chop_days)} days",
                              "detail": _span(farm, st.chop_days)})
            if st.mine_days:
                cards.append({"col": col(min(st.mine_days)), "tag": "MINE",
                              "title": f"The Mines, {len(st.mine_days)} days", "detail": _span(farm, st.mine_days)})
            for n in new:
                cost = ", ".join(([f"{n['gold']:,}g"] if n["gold"] else []) + n["materials"])
                verb = _verb(n)
                helps = [own] + users.get(n["key"], [])
                cards.append({"col": col(n["on"] if n["on"] is not None else st.day), "tag": verb,
                              "title": _thing(n["label"]).removeprefix("a ").removeprefix("the ")[:1].upper()
                              + _thing(n["label"]).removeprefix("a ").removeprefix("the ")[1:],
                              "detail": "; ".join(x for x in (cost, f"ready {n['ready']}" if n["ready"] else "") if x),
                              "gold": n["gold"], "helps": helps if len(helps) > 1 else []})
                if len(helps) > 1:
                    synergy.setdefault(n["key"], {"what": _thing(n["label"]), "goals": helps})
            if not new and st.gold:
                cards.append({"col": col(st.day), "tag": "BUY", "title": item, "detail": f"{st.gold:,}g",
                              "gold": st.gold})
            if st.how or not new:
                helps = [own] + shared_by.get(st.label, [])
                tag = "FARM CAVE" if "from the fruit bats" in st.label or "from the mushroom" in st.label \
                    else _tag(st.how)
                cards.append({"col": col(st.act or st.ready), "tag": tag, "title": item, "final": True,
                              "detail": f"{st.how} · {farm.label(st.act or st.ready)}" if st.how
                              else farm.label(st.ready), "helps": helps if len(helps) > 1 else []})
                if len(helps) > 1:
                    synergy.setdefault(st.label, {"what": item, "goals": helps})
            waits = [f"waits for {n['label']}" + (f", ready {n['ready']}" if n["ready"] else "")
                     for n in st.needs if n["state"] == "earlier"]
            merged: dict[int, dict] = {}
            for c in cards:  # one card per week: steps in the same week read as one
                m = merged.get(c["col"])
                if m is None:
                    merged[c["col"]] = {"gold": 0, "helps": [], "waits": [], **c, "urgency": urgency}
                elif m["tag"] == "CHOP":  # chopping first, then what the Wood is for, the same week
                    chopped = f"after chopping {m['title'].replace(', ', ' for ')} ({m['detail']})"
                    merged[c["col"]] = {"gold": 0, "helps": [], "waits": [], **c, "urgency": urgency,
                                        "tag": f"CHOP, THEN {c['tag']}",
                                        "detail": "; ".join(x for x in (chopped, c["detail"]) if x)}
                else:
                    if not c.get("final"):
                        m["tag"] = m["tag"] if m["tag"] == c["tag"] else f"{m['tag']} + {c['tag']}"
                        m["title"] += f", {c['title']}"
                    m["detail"] = "; ".join(x for x in (m["detail"], c["detail"]) if x)
                    m["gold"] += c.get("gold", 0)
                    m["helps"] = m["helps"] or c.get("helps", [])
            row = [merged[k] for k in sorted(merged)]
            if row and waits:
                row[-1]["waits"] = waits
            steps.append(row)
            for c in row:
                columns[c["col"]]["gold"] += c["gold"]
        rows: list[list[dict]] = []
        spans: list[list[tuple[int, int]]] = []
        for cards in steps:  # pack: a row takes the next thing whose weeks don't overlap it
            lo, hi = cards[0]["col"], cards[-1]["col"]
            for i, taken in enumerate(spans):
                if all(hi < a or lo > b for a, b in taken):
                    rows[i] += cards
                    taken.append((lo, hi))
                    break
            else:
                rows.append(list(cards))
                spans.append([(lo, hi)])
        for row in rows:
            row.sort(key=lambda c: c["col"])
        lanes.append({"id": o.id, "rows": rows})
    for lane in lanes:
        for row in lane["rows"]:
            for c in row:
                c["helps"] = _by_goal(c["helps"])
                c.pop("final", None)
    for x in synergy.values():
        x["goals"] = _by_goal(x["goals"])
    return {"columns": columns, "lanes": lanes,
            "synergy": [x for x in synergy.values() if len(x["goals"]) > 1]}


def _by_goal(helps: list[dict]) -> list[dict]:
    """[{goal, why}] -> [{goal, why: 'a, b'}], one per goal, in order."""
    out: dict[str, list[str]] = {}
    for h in helps:
        whys = out.setdefault(h["goal"], [])
        why = h["why"].split(" (")[0]
        if why not in whys:
            whys.append(why)
    return [{"goal": g, "why": ", ".join(w)} for g, w in out.items()] if len(out) > 1 else []


def _verb(n: dict) -> str:
    key = n["key"]
    if key.startswith(("building:", "kitchen", "house:")) or n["label"].startswith("repair"):
        return "BUILD"
    if key.startswith("tool:"):
        return "UPGRADE"
    if key.startswith("recipe:"):
        return "RECIPE"
    if key.startswith("craft:"):
        return "CRAFT"
    if key.startswith("tap:"):
        return "TAP"
    return "BUY" if n["gold"] or n["label"].startswith("buy") else "GET"


def _week_label(farm, a: int, b: int) -> str:
    la, lb = farm.label(a).split(", Year")[0], farm.label(b).split(", Year")[0]
    if la.split()[0] == lb.split()[0]:
        return f"{la}–{lb.split()[1]}"
    return f"{la} – {lb}"


def _tag(how: str) -> str:
    for word, tag in (("fish", "FISH"), ("forage", "FORAGE"), ("hoeing", "DIG"), ("cooking", "COOK"),
                      ("talk", "EVERY DAY"), ("Mariner", "BUY"), ("tree", "PICK"), ("three days", "WEDDING"),
                      ("give", "GIVE"), ("Goat", "PRODUCE"), ("Duck", "PRODUCE"), ("Cow", "PRODUCE"),
                      ("Chicken", "PRODUCE"), ("Rabbit", "PRODUCE"), ("Pig", "PRODUCE"), ("Sheep", "PRODUCE")):
        if word in how:
            return tag
    return "GET" if how else "DONE"


def _agenda(farm, outcomes: list[Outcome], today: int, res) -> list[dict]:
    """The route's next week as things to do on the day, each saying which goal it serves."""
    out: list[dict] = []
    end = today + AGENDA_DAYS

    def add(d, kind, text, why, goal, gold=0):
        if today <= d < end:
            out.append({"n": d, "day": farm.label(d), "kind": kind, "text": text, "why": why, "goal": goal,
                        "gold": gold})

    saving = None
    for o in outcomes:
        for st in o.steps:
            if st.shared:
                continue
            new = [n for n in st.needs if n["state"] == "new"]
            first = _thing(new[0]["label"]) if new else st.label
            hard = any(m.endswith(" Hardwood") for n in new for m in n["materials"])
            for d in st.chop_days:
                why = f"for {first}" if _bare(first) == _bare(st.label) else f"for {first}, for {st.label}"
                add(d, "chop", "Chop Hardwood (Secret Woods) and Wood" if hard else "Chop Wood all day", why, o.label)
            for d in st.mine_days:
                add(d, "mine", "Go down the Mines", f"deeper floors for {st.label}", o.label)
            for n in new:
                cost = ", ".join(([f"{n['gold']:,}g"] if n["gold"] else []) + n["materials"])
                text = n["label"][0].upper() + n["label"][1:] + (f": {cost}" if cost else "")
                add(n["on"], "buy", text, f"for {st.label}", o.label, n["gold"])
                if n["gold"] and today <= n["on"] < today + 2 * AGENDA_DAYS and saving is None \
                        and farm.save.money < n["gold"]:
                    saving = (n, st, o)
            if not new and st.gold:
                add(st.day, "buy", f"Buy {st.label}: {st.gold:,}g", "", o.label, st.gold)
            if st.act:
                add(st.act, "fish", st.how[0].upper() + st.how[1:] if st.how else "Fish", f"for {st.label}", o.label)
            elif st.how and not new and not st.gold:
                add(st.ready, "get", f"Get {st.label.split(' (')[0]}: {st.how}", f"for {st.label}", o.label)
    for o in outcomes:  # courting: every day until the proposal
        if o.id == "marriage" and o.status != "done":
            who = next((st.label.removeprefix("10 hearts with ") for st in o.steps
                        if st.label.startswith("10 hearts with ")), None)
            if who:
                add(today, "people", f"Talk to {who}; a gift on two days each week",
                    "friendship toward the Bouquet and the Mermaid's Pendant", o.label)
    if saving:
        n, st, o = saving
        out.append({"n": today, "day": farm.label(today), "kind": "save",
                    "text": f"Save up {n['gold']:,}g for {_thing(n['label'])} "
                            f"by {farm.label(n['on'])}",
                    "why": f"you have {farm.save.money:,}g; it's for {st.label}", "goal": o.label, "gold": n["gold"]})
    out.sort(key=lambda a: (a["n"], a["kind"] != "save"))
    return out


def _bare(label: str) -> str:
    """'the Stable' and 'a Stable' alike."""
    return re.sub(r"^(a|an|the) ", "", label.lower())


def _thing(label: str) -> str:
    """'build a Big Barn' -> 'a Big Barn'."""
    for verb in ("build ", "buy ", "upgrade "):
        label = label.removeprefix(verb)
    return label


def _span(farm, days: list[int]) -> str:
    """'Fall 22 – Fall 25' for a run of days, or the first and last of scattered ones."""
    if not days:
        return ""
    days = sorted(days)
    return farm.label(days[0]) if len(days) == 1 else f"{farm.label(days[0])} – {farm.label(days[-1])}"


def _season(d: int) -> int:
    return (d - 1) // 28


def route(farm, targets: list[str], nice: list[str] = (), *, settings: Settings | None = None,
          deadlines: dict[str, int] | None = None, cave: str = "best", tiles: int | None = None) -> dict:
    """Plan targets (in order) then nice-to-haves (in order); what each achieves, when, and what can't be.
    `cave`: "bats" or "mushrooms", or "best" to plan both and keep the one that achieves more (targets first,
    then nice-to-haves, then the year's end cash)."""
    settings = settings or Settings()
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
