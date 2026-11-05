"""What's in each of the town's garbage cans on any day, worked out from the save the way the game rolls it (1.6.15).

How a can is rolled (GameLocation.TryGetGarbageItem, in our words): each can has its own generator for the day,
seeded from (days played, game id / 2, 777 + hash of the can's id). It skips forward twice: Next(0, 100) gives a
count of NextDouble() to throw away. The next NextDouble() is the can's roll: below the base chance (0.2, plus the
day's luck, plus 0.2 with the Book_Trash book read) lets ordinary entries through. Then BeforeAll, the can's own
Items and AfterAll are walked in order, and the first entry that passes wins. An entry marked IgnoreBaseChance can
win on a failed roll, so a can that failed is still not quite certain to be empty, once the rare drops unlock.
RANDOM conditions draw on the can's generator, left to right, only if the queries before them passed, and
SYNCED_RANDOM ones on their own day generator. The picked item's RandomItemId and stack roll on the can's
generator after that.

What can be known ahead:
- Nothing in a can's seed depends on the player, so the rolls are fixed for a save and a day, whichever order the
  cans are opened in.
- The one input that isn't is the day's luck. It's rolled overnight from a generator seeded with the player's step
  count, so it can't be worked out in advance. Today's is in the save, so today is exact. For any other day we try
  every luck the game can roll (-0.100 to 0.100 evenly, plus the Special Charm) and report the share that fill the
  can: `odds` 1 means it has something however the day turns out, 0 that it's empty, and in between it hangs on luck.
- Other days use today's state of the farm (stats, mail, active special orders). The dish of the day isn't known
  ahead. Opening cans raises trashCansChecked, which unlocks the rare entries at 20 and 50; those draw after the
  can's roll, so that can't change whether the roll passed, only the rare drop itself.

The Desert Festival's can isn't here: it's only there for three days, in the desert, and always has Calico Eggs.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass
from functools import cached_property, lru_cache

from .cart import _apply
from .conditions import When, check, split
from .rng import NetRandom, day_save_random, hash_text, synced_random

CANS = {  # the "Action Garbage" tiles on the Town map
    "JodiAndKent": "1 Willow Lane",
    "EmilyAndHaley": "2 Willow Lane",
    "Evelyn": "1 River Road",
    "Mayor": "the Mayor's Manor",
    "Museum": "the Museum",
    "Blacksmith": "the Blacksmith",
    "Saloon": "the Saloon",
    "JojaMart": "JojaMart",
}
LUCKS = tuple(k / 1000 for k in range(-100, 101))  # Next(-100, 101) / 1000: every value equally likely
CHARM = 0.025
SEASON_POOL = ("68", "66", "78", "80", "86", "152", "167", "153", "420")
DEEP_40 = ("62", "70", "72", "84", "422")
DEEP_80 = ("64", "60", "82")
VAULT = ("88", "90", "164", "165")
FURNACE = ("334", "335", "336", "338")
SEASON_ITEMS = {
    "spring": ("16", "18", "20", "22", "129", "131", "132", "136", "137", "142", "143", "145", "147", "148", "152",
               "167", "267"),
    "summer": ("128", "130", "132", "136", "138", "142", "144", "145", "146", "149", "150", "155", "396", "398",
               "402", "267"),
    "fall": ("404", "406", "408", "410", "129", "131", "132", "136", "137", "139", "140", "142", "143", "148", "150",
             "154", "155", "269"),
    "winter": ("412", "414", "416", "418", "130", "131", "132", "136", "140", "141", "144", "146", "147", "150",
               "151", "154", "269"),
}


def _f32(x: float) -> float:
    """The game adds these chances as single-precision floats."""
    return struct.unpack("f", struct.pack("f", x))[0]


_split = lru_cache(maxsize=None)(lambda condition: tuple(map(tuple, split(condition))))


@dataclass(frozen=True)
class Loot:
    item: str | None  # qualified id; None for a dish not known ahead
    name: str
    stack: int = 1
    rare: bool = False  # one of the entries that ignore the base chance

    @property
    def label(self) -> str:
        return f"{self.stack} {self.name}" if self.stack > 1 else self.name


@dataclass(frozen=True)
class CanDay:
    can: str
    place: str
    odds: float  # share of the possible lucks that fill it (0 or 1 when the luck is known)
    loot: Loot | None  # the most likely thing in it


class _Roll:
    """One can on one day, for trying different lucks. Everything luck doesn't touch is worked out once."""

    def __init__(self, cans: GarbageCans, can: str, when: When, save):
        self.cans, self.can, self.when, self.save = cans, can, when, save
        rng = day_save_random(when.days_played, when.game_id, 777 + hash_text(can), legacy=when.legacy_random)
        for _ in range(2):
            for _ in range(rng.next(0, 100)):
                rng.next_double()
        self.roll = rng.next_double()
        self.rng = rng
        self.synced: dict[str, float] = {}
        self.read_book = bool(save.stats.get("Book_Trash"))

    def _synced(self, key: str) -> float:
        if key not in self.synced:
            w = self.when
            self.synced[key] = synced_random("day", key, game_id=w.game_id, days_played=w.days_played, season=w.season,
                                             year=w.year, legacy=w.legacy_random).next_double()
        return self.synced[key]

    def _holds(self, condition: str | None, rng: NetRandom, luck: float) -> bool:
        for tokens in _split(condition or ""):
            key, args = tokens[0].lstrip("!").upper(), tokens[1:]
            lucky = any(a.lower() == "@adddailyluck" for a in args)
            if key == "RANDOM":
                result = rng.next_double() < (_f32(float(args[0]) + _f32(luck)) if lucky else _f32(float(args[0])))
            elif key == "SYNCED_RANDOM":
                chance = _f32(float(args[2]) + _f32(luck)) if lucky else _f32(float(args[2]))
                result = self._synced(args[1]) < chance
            elif key == "PLAYER_STAT":
                result = self.save.stats.get(args[1], 0) >= int(args[2])
            elif key == "PLAYER_SPECIAL_ORDER_RULE_ACTIVE":
                result = any(r in self.cans.active_rules(self.save) for r in args[1:])
            else:
                known = check(" ".join(tokens), self.when)
                if known is None:
                    raise ValueError(f"garbage can condition not supported: {condition}")
                if not known:
                    return False
                continue
            if result == tokens[0].startswith("!"):
                return False
        return True

    def _season_item(self, rng: NetRandom) -> str:
        s, pool = self.save, list(SEASON_POOL)
        if s.deepest_mine_level > 40:
            pool += DEEP_40
        if s.deepest_mine_level > 80:
            pool += DEEP_80
        if "ccVault" in s.mail:
            pool += VAULT
        if "Furnace" in s.crafting_recipes:
            pool += FURNACE
        if "Quartz Globe" in s.crafting_recipes:
            pool.append("339")
        return f"(O){rng.choose(pool + list(SEASON_ITEMS[self.when.season]))}"

    def _resolve(self, entry: dict, rng: NetRandom) -> Loot:
        qid = rng.choose(entry["RandomItemId"]) if entry.get("RandomItemId") else entry.get("ItemId")
        rare = bool(entry.get("IgnoreBaseChance"))
        if qid == "DISH_OF_THE_DAY":
            dish = self.save.dish_of_the_day if self.when.days_played == self.save.days_played else None
            if not dish:
                return Loot(None, "the day's dish", rare=rare)
            return Loot(dish[0], self.cans.name(dish[0]), rare=rare)
        if qid == "RANDOM_BASE_SEASON_ITEM":
            qid = self._season_item(rng)
        stack = int(_apply(1, entry.get("StackModifiers"), entry.get("StackModifierMode") or "Stack", rng))
        return Loot(qid, self.cans.name(qid), stack, rare)

    def at(self, luck: float) -> Loot | None:
        chance = _f32(self.cans.base_chance(self.can) + _f32(luck))
        if self.read_book:
            chance = _f32(chance + _f32(0.2))
        passed = self.roll < chance
        rng = self.rng.clone()
        for entries in self.cans.entries(self.can):
            for entry in entries:
                if (passed or entry.get("IgnoreBaseChance")) and self._holds(entry.get("Condition"), rng, luck):
                    return self._resolve(entry, rng)
        return None


class GarbageCans:
    def __init__(self, data):
        self.data = data

    @cached_property
    def table(self) -> dict:
        return self.data.asset("Data/GarbageCans")

    @cached_property
    def objects(self) -> dict:
        return self.data.asset("Data/Objects")

    @cached_property
    def furniture(self) -> dict:
        return self.data.asset("Data/Furniture")

    def name(self, qid: str) -> str:
        kind, _, iid = qid[1:].partition(")")
        if kind == "O" and iid in self.objects:
            o = self.objects[iid]
            return self.data.text(o.get("DisplayName")) or o.get("Name") or iid
        return {"(H)66": "Garbage Hat", "(F)TrashCatalogue": "Trash Catalogue"}.get(qid, qid)

    def base_chance(self, can: str) -> float:
        own = (self.table["GarbageCans"].get(can) or {}).get("BaseChance", -1)
        return own if own > 0 else self.table["DefaultBaseChance"]

    def entries(self, can: str) -> tuple[list, list, list]:
        own = (self.table["GarbageCans"].get(can) or {}).get("Items") or []
        return self.table.get("BeforeAll") or [], own, self.table.get("AfterAll") or []

    @cached_property
    def order_rules(self) -> dict[str, set[str]]:
        orders = self.data.asset("Data/SpecialOrders") if self.data.has("Data/SpecialOrders") else {}
        return {k: {r.strip() for r in (o.get("SpecialRule") or "").split(",")} for k, o in orders.items()}

    def active_rules(self, save) -> set[str]:
        return {r for o in save.special_orders if o.get("state") == "InProgress"
                for r in self.order_rules.get(o["key"], ())}

    def day(self, save, when: When) -> list[CanDay]:
        """Every can on `when`: exact for the save's own day, odds over the possible lucks for any other."""
        out = []
        for can, place in CANS.items():
            roll = _Roll(self, can, when, save)
            if when.days_played == save.days_played:
                results = [roll.at(save.daily_luck)]
            else:
                charm = CHARM if "HasSpecialCharm" in save.mail else 0
                results = [roll.at(luck + charm) for luck in LUCKS]
            found = [r for r in results if r]
            loot = Counter(found).most_common(1)[0][0] if found else None
            out.append(CanDay(can, place, len(found) / len(results), loot))
        return out
