"""Every way to get an item, and when — worked out from the game's data, not a hand-written list.

Each Source says what it is, the seasons it works in (None: any), the days
of the month (None: any), a game condition if the data gives one, what has
to be open or owned first (a place, a building, a machine, a recipe), how
many days it takes (growing, processing), its gold cost, and a chance when
it's random. Kinds:
- crop: grow it from its seed (Data/Crops), seeds from the shops that sell
  them (their conditions decide when).
- fish: a fishing spot's seasons (Data/Locations + Data/Fish).
- forage: a location's forage for the season (Data/Locations Forage).
- tree: a fruit tree's fruit (Data/FruitTrees).
- tapper: a wild tree's tap item (Data/WildTrees).
- animal: an animal's produce or deluxe produce (Data/FarmAnimals), which
  needs its building.
- machine: a machine rule whose output is this item (plain outputs only;
  flavoured goods are found from the ingredient side).
- shop: a shop entry that sells it (with its condition).
- cooking / crafting: a recipe that makes it.
- monster: a monster's drop chance (Data/Monsters).
- mine: gems and minerals from the Mines' rocks, nodes and geodes (which
  floors, and the geode tables, aren't modelled yet).
- dig: artifacts, from artifact spots, digging and fishing chests.
- cart: the Traveling Cart's random stock, about 10 picks from its pool.
Festival stalls take the festival's dates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property

from .access import place_open
from .conditions import SEASONS, When, split
from .places import Places

FESTIVAL_DAYS = {  # festival shop id part -> (season, first day, last day): the festivals' own dates
    "EggFestival": ("spring", 13, 13), "FlowerDance": ("spring", 24, 24), "Luau": ("summer", 11, 11),
    "DanceOfTheMoonlightJellies": ("summer", 28, 28), "StardewValleyFair": ("fall", 16, 16),
    "SpiritsEve": ("fall", 27, 27), "FestivalOfIce": ("winter", 8, 8), "FeastOfTheWinterStar": ("winter", 25, 25),
    "NightMarket": ("winter", 15, 17), "DesertFestival": ("spring", 15, 17)}
CART_POOL_SIZE = 334  # objects the cart's random slots can pick from (see econ.red-cabbage-cart)
CART_PICKS = 10
FESTIVAL_SHOP_PREFIX = "Festival_"


@dataclass(frozen=True)
class Source:
    kind: str
    label: str
    seasons: frozenset[str] | None = None
    days: tuple[int, int] | None = None  # day-of-month range
    condition: str = ""
    needs: tuple[str, ...] = ()  # "place:Desert", "building:Big Coop", "machine:(BC)12", "recipe:Maki Roll"
    lead: int = 0  # days from starting to having it (growing)
    cost: int = 0
    chance: float | None = None  # per try/day, when random
    inputs: tuple[tuple[str, int], ...] = ()  # items it takes (machines, recipes)
    notes: tuple[str, ...] = field(default=())

    def in_season(self, season: str) -> bool:
        return self.seasons is None or season in self.seasons


def _seasons(raw) -> frozenset[str] | None:
    vals = {str(x).lower() for x in (raw if isinstance(raw, (list, tuple, set, frozenset)) else [raw]) if x}
    return frozenset(vals) if vals else None


def _cond_seasons(condition: str | None) -> tuple[frozenset[str] | None, str]:
    """Pull SEASON / LOCATION_SEASON out of a condition: (seasons, the rest)."""
    found: set[str] = set()
    rest = []
    for tokens in split(condition or ""):
        key = tokens[0].upper()
        if key == "SEASON":
            found |= {t.lower() for t in tokens[1:]}
        elif key == "LOCATION_SEASON" and len(tokens) > 2:
            found |= {t.lower() for t in tokens[2:]}
        else:
            rest.append(" ".join(tokens))
    return (frozenset(found) if found else None), ", ".join(rest)


def _unq(item_id: str | None) -> str:
    return (item_id or "").removeprefix("(O)")


class Sources:
    def __init__(self, data, *, farm_type: int = 0):
        self.data = data
        self.farm_type = farm_type
        self.places = Places(data)

    def _name(self, oid: str) -> str:
        o = self.data.asset("Data/Objects").get(oid) or {}
        return self.data.text(o.get("DisplayName")) or o.get("Name") or oid

    @cached_property
    def index(self) -> dict[str, list[Source]]:
        """Unqualified object id -> its sources."""
        out: dict[str, list[Source]] = {}

        def add(oid: str, src: Source) -> None:
            out.setdefault(oid, []).append(src)

        shops = self.data.asset("Data/Shops")
        sold: dict[str, list[tuple[str, dict]]] = {}
        for sid, shop in shops.items():
            for e in shop.get("Items") or []:
                qid = (e.get("ItemId") or "").strip()
                if qid.startswith("(O)") and " " not in qid and not e.get("IsRecipe"):  # a recipe isn't the item
                    sold.setdefault(qid[3:], []).append((sid, e))
        for oid, entries in sold.items():
            for sid, e in entries:
                seasons, rest = _cond_seasons(e.get("Condition"))
                days = None
                desert = sid in ("Sandy", "DesertTrade", "Casino") or sid.startswith("DesertFestival")
                needs = ("place:Desert",) if desert else ()
                needs += ("place:Island",) if sid.startswith("Island") or sid == "VolcanoShop" else ()
                needs += ("place:Sewer",) if sid == "ShadowShop" else ()
                fest = next((v for k, v in FESTIVAL_DAYS.items() if k in sid), None)
                if fest:
                    seasons, days = frozenset({fest[0]}), (fest[1], fest[2])
                add(oid, Source("shop", _shop_label(sid), seasons, days, condition=rest, needs=needs,
                                cost=max(0, int(e.get("Price") or -1)) if (e.get("Price") or -1) >= 0 else 0,
                                notes=("festival stall",) if fest else ()))

        for seed, c in self.data.asset("Data/Crops").items():
            harvest = _unq(c.get("HarvestItemId"))
            if not harvest:
                continue
            seed_shops = [sid for sid, _ in sold.get(seed, [])]
            add(harvest, Source("crop", f"grow {self._name(seed)}", _seasons(c.get("Seasons")),
                                lead=sum(c.get("DaysInPhase") or []), inputs=((seed, 1),),
                                notes=tuple(f"seeds: {s}" for s in seed_shops[:4])))

        fish = self.data.asset("Data/Fish")
        for fid, raw in fish.items():  # crab-pot catches aren't in any fishing spot: any crab pot, any season
            f = raw.split("/")
            if len(f) > 4 and f[1] == "trap":
                add(fid, Source("crabpot", f"a crab pot ({f[4]} water)", needs=("recipe:Crab Pot",), lead=1))
        for loc, ldata in self.data.asset("Data/Locations").items():
            if loc in ("Default", "fishingGame", "Temp") or (loc.startswith("Farm_") and not self._farm_here(loc)):
                continue
            place = "Farm" if loc.startswith("Farm_") else loc
            for e in ldata.get("Fish") or []:
                oid = _unq(e.get("ItemId"))
                if oid not in fish:
                    continue
                seasons, rest = _cond_seasons(e.get("Condition"))
                seasons = _seasons(e.get("Season")) or seasons
                add(oid, Source("fish", f"fish at {self.places.name(place)}", seasons, condition=rest,
                                needs=(f"place:{place}",)))
            for e in ldata.get("Forage") or []:
                oid = _unq(e.get("ItemId"))
                if not oid:
                    continue
                seasons, rest = _cond_seasons(e.get("Condition"))
                add(oid, Source("forage", f"forage at {self.places.name(place)}", _seasons(e.get("Season")) or seasons,
                                condition=rest, needs=(f"place:{place}",), chance=e.get("Chance")))

        for tree, t in self.data.asset("Data/FruitTrees").items():
            for fr in t.get("Fruit") or []:
                oid = _unq(fr.get("ItemId"))
                if oid:
                    add(oid, Source("tree", f"{self._name(tree)} tree", _seasons(t.get("Seasons")), lead=28,
                                    inputs=((tree, 1),)))
        for tree, t in self.data.asset("Data/WildTrees").items():
            for tap in t.get("TapItems") or []:
                oid = _unq(tap.get("ItemId"))
                if oid:
                    add(oid, Source("tapper", f"a tapper on tree type {tree}", needs=("recipe:Tapper",),
                                    lead=int(tap.get("DaysUntilReady") or 0)))
        for kind, animal in self.data.asset("Data/FarmAnimals").items():
            for key, label in (("ProduceItemIds", ""), ("DeluxeProduceItemIds", " (deluxe)")):
                for p in animal.get(key) or []:
                    oid = _unq(p.get("ItemId"))
                    if oid:
                        add(oid, Source("animal", f"a {kind}{label}", needs=(f"animal:{kind}",
                                        f"building:{animal.get('RequiredBuilding') or animal.get('House')}"),
                                        cost=int(animal.get("PurchasePrice") or 0) * 2,
                                        lead=int(animal.get("DaysToMature") or 0)))
        from .machines import FLAVOR_BASE
        for mid, m in self.data.asset("Data/Machines").items():
            for rule in m.get("OutputRules") or []:
                for o in rule.get("OutputItem") or []:
                    item = (o.get("ItemId") or "").strip()
                    if item.startswith("FLAVORED_ITEM"):
                        kind = item.split()[1] if len(item.split()) > 1 else ""
                        tags = [t for trig in rule.get("Triggers") or [] for t in trig.get("RequiredTags") or []]
                        if kind in FLAVOR_BASE:
                            add(FLAVOR_BASE[kind], Source("machine", f"machine {mid}", needs=(f"machine:{mid}",),
                                                          notes=tuple(tags[:3])))
                        continue
                    if not item.startswith("(O)") or " " in item:
                        continue
                    trig = next((t for t in rule.get("Triggers") or [] if t.get("RequiredItemId")), None)
                    inputs = ((_unq(trig["RequiredItemId"]), trig.get("RequiredCount") or 1),) if trig else ()
                    add(item[3:], Source("machine", f"machine {mid}", needs=(f"machine:{mid}",), inputs=inputs,
                                         lead=max(1, int((rule.get("MinutesUntilReady") or 0) // 1600))
                                         if (rule.get("MinutesUntilReady") or 0) >= 1600 else 0))
        for kind, table in (("cooking", "Data/CookingRecipes"), ("crafting", "Data/CraftingRecipes")):
            for name, raw in self.data.asset(table).items():
                f = raw.split("/")
                if len(f) < 3 or (kind == "crafting" and len(f) > 3 and f[3] == "true"):
                    continue  # big craftables aren't objects
                out_id = f[2].split()[0] if f[2] else ""
                parts = f[0].split()
                inputs = tuple((parts[i], int(parts[i + 1])) for i in range(0, len(parts) - 1, 2))
                if out_id:
                    add(out_id, Source(kind, f"{kind} {name}", needs=(f"recipe:{name}",) +
                                       (("kitchen",) if kind == "cooking" else ()), inputs=inputs))
        for name, raw in self.data.asset("Data/Monsters").items():
            f = raw.split("/")
            drops = f[6].split() if len(f) > 6 else []
            for i in range(0, len(drops) - 1, 2):
                try:
                    chance = float(drops[i + 1])
                except ValueError:
                    continue
                if chance > 0:
                    add(drops[i], Source("monster", f"a {name}", chance=chance))
        from .mines import FLOORS
        for oid, (first, _last, how) in FLOORS.items():  # by floor: see facts/mines.py
            add(oid, Source("mine", f"the Mines, floor {first}+ ({how})",
                            needs=("place:UndergroundMine", f"floor:{first}")))
        for oid, o in self.data.asset("Data/Objects").items():
            if oid in FLOORS:
                continue
            if o.get("Type") == "Minerals" or int(o.get("Category") or 0) in (-2, -12):
                add(oid, Source("mine", "geodes from the Mines", needs=("place:UndergroundMine",)))
            elif o.get("Type") == "Arch":
                add(oid, Source("dig", "artifact spots, digging and fishing chests"))
        # Spawned by the game's code rather than its data
        for oid, chance in (("397", 0.2), ("393", 0.8)):  # Beach.DayUpdate: tide pools, 1 in 5 an urchin
            add(oid, Source("forage", "the Beach tide pools", needs=("place:BeachTidePools",), chance=chance))
        for oid in ("412", "416"):  # GameLocation.checkForBuriedItem: 8% of dug tiles off the farm in winter
            add(oid, Source("dig", "hoeing soil off the farm in winter", frozenset({"winter"}), chance=0.04))
        for oid, found in out.items():  # the same source from several rules is one source
            seen, unique = set(), []
            for src in found:
                key = (src.kind, src.label, src.seasons, src.days, src.condition, src.needs)
                if key not in seen:
                    seen.add(key)
                    unique.append(src)
            out[oid] = unique
        return out

    def _farm_here(self, loc: str) -> bool:
        from .fish import FARM_TYPES
        return loc == f"Farm_{FARM_TYPES.get(self.farm_type, 'Standard')}"

    def of(self, item: str, *, cart: bool = True) -> list[Source]:
        oid = _unq(item)
        found = list(self.index.get(oid, []))
        if cart and self._in_cart_pool(oid):
            found.append(Source("cart", "the Traveling Cart (random)", chance=CART_PICKS / CART_POOL_SIZE,
                                notes=("Fridays and Sundays, plus the Night Market and Desert Festival",)))
        return found

    def _in_cart_pool(self, oid: str) -> bool:
        o = self.data.asset("Data/Objects").get(oid) or {}
        cat = int(o.get("Category") or 0)
        return oid.isdigit() and 2 <= int(oid) <= 789 and int(o.get("Price") or 0) > 0 and cat < 0 and cat != -999 \
            and not o.get("ExcludeFromRandomSale") and o.get("Type") not in ("Quest", "Minerals", "Arch")

    def open_now(self, src: Source, w: When) -> tuple[bool, list[str]]:
        """Whether a source's places are open now; what's missing if not (other needs are left to the caller)."""
        missing = []
        for need in src.needs:
            if need.startswith("place:"):
                place = need[6:]
                ok, why = place_open("IslandSouth" if place == "Island" else place, w)
                if not ok:
                    missing.append(why or place)
        return not missing, missing


SHOP_NAMES = {"SeedShop": "Pierre's", "Joja": "JojaMart", "FishShop": "Willy's Fish Shop", "AnimalShop": "Marnie's",
              "Blacksmith": "Clint's", "Saloon": "the Saloon", "Sandy": "the Oasis", "Carpenter": "Robin's",
              "Hospital": "Harvey's Clinic", "AdventureShop": "the Adventurer's Guild", "Traveler": "the cart",
              "DesertTrade": "the Desert Trader", "Casino": "the Casino", "Dwarf": "the Dwarf", "Krobus": "Krobus",
              "IceCreamStand": "the ice cream stand", "ShadowShop": "Krobus", "Bookseller": "the bookseller"}


def _shop_label(shop_id: str) -> str:
    """'Festival_EggFestival_Pierre' -> 'Pierre at the Egg Festival'; 'SeedShop' -> "Pierre's"."""
    if shop_id in SHOP_NAMES:
        return SHOP_NAMES[shop_id]
    parts = shop_id.split("_")
    if parts[0] == "Festival" and len(parts) >= 3:
        return f"{' '.join(parts[2:])} at the {re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', parts[1])}"
    if parts[0] == "DesertFestival" and len(parts) >= 2:
        return f"{' '.join(parts[1:])} at the Desert Festival"
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", shop_id.replace("_", " "))


def seasons_text(s: Source) -> str:
    if s.seasons is None or set(s.seasons) >= set(SEASONS):
        return "any season"
    return ", ".join(x.capitalize() for x in SEASONS if x in s.seasons)
