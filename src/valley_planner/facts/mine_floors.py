"""What kind each Mines floor is today, from the day's seed (1.6.15): infested, slime, quarry, mushroom, dark.

The rules in our words (MineShaft.loadLevel, then chooseLevelType):
- Map: a floor loads map floor % 40, except floors ending in 0 (map 10, or map 20 on floors 20, 60 and 100) and
  floor 120 (its own map). Once the Mines' lowest level reached is 120, floors not divisible by 5 roll
  DaySave(1293857 + 400 x floor): under 0.06 swaps in one of maps 40-60 (40, 47, 50 and 51 are mostly re-rolled
  once; then 53 is re-rolled to 52-60 outside the Skull Cavern, and 40 outside floors 1-10, 30-39 and 80-120,
  which can still land on 53). Maps 40, 47, 50 and 51 are never infested.
- Infested: DaySave(100 x floor), first draw under 0.044, on a map not divisible by 5 whose number % 40 is 6-29
  and not 19; the next draw (under 0.5) makes it a monster floor, otherwise a slime floor. Both must be cleared
  before a ladder shows: no stones, no ore. So floors 1-5, 30-45, 70-85 and 110-120 never are (without the
  swapped-in maps). Oil of Garlic (buff 23) on anyone online stops it in the Mines, not the Skull Cavern.
- Quarry floors (after the Crafts Room is done and the Quarry mine visited): floors up to 120 that were not infested
  draw once more from the same random, under 0.044, on a map not divisible by 5 with number % 40 above 1. A quarry
  floor is never infested (the game rolls 25% for it, then clears it).
- Lighting (DaySave(days played, floor, 4 x floor), as in mine_day.py): under 0.3 is dark from floor 3 (plus a shade
  draw), under 0.15 is dark from floor 6 (not 120); then under 0.035 is a mushroom floor on 81-119 not divisible
  by 5. Floors 31-39 and 110-119 are always dark. Dangerous mines skip the first lighting draw. Quarry floors are lit.
- Mushroom floors put mushrooms among the stones, so an infested one has none, and only the first time that floor
  is built that day (leave the Mines and come back and it is plain).
- Skull Cavern: the map comes from an unseeded random (and treasure rooms from luck and Game1.random), so only "not
  infested today" is certain; a floor whose first draw passes is infested on about 19 of 32 maps; past 126 a third
  draw (under 0.5) makes it a dinosaur floor instead.

Unsure:
- Nothing checks this against play yet: a save never holds the built floors, only the lowest level reached and the
  carts/chests left. The seeds and draw order are read from the decompiled code; the dark rolls (mine_day.py) were
  seen right in play, and they share the DaySave seeding.
- During Krobus's/the "Lowest level for order" special order the lowest level is the order's; we take what we're given.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rng import day_save_random

INFEST, QUARRY, ALT_MAP = 0.044, 0.044, 0.06
DARK, DARK_AGAIN, MUSHROOM = 0.3, 0.15, 0.035
NO_INFEST_MAPS = (40, 47, 50, 51)
FORCED_CHEST = (220, 320, 420)
SKULL_MAPS = [m for m in range(40) if m % 5]  # maps an ordinary Skull Cavern floor can load
_SKULL_INFESTABLE = sum(1 for m in SKULL_MAPS if 5 < m < 30 and m != 19) / len(SKULL_MAPS)


@dataclass(frozen=True)
class FloorKind:
    floor: int
    map: int | None  # the map number loaded (None: not knowable, Skull Cavern)
    infested: str | None  # "monsters", "slimes", "dinos" or None
    quarry: bool = False
    mushroom: bool = False
    dark: bool = False
    sure: bool = True  # False where an unseeded random could still change it

    @property
    def must_kill(self) -> bool:
        return self.infested is not None


def _area(floor: int) -> int:
    if floor > 120:
        return 121
    if floor >= 80:
        return 80
    if floor >= 40:
        return 40
    if 10 < floor < 30:
        return 10
    return 0


def _base_map(floor: int) -> int:
    if floor == 120:
        return 120
    num = 20 if floor % 40 % 20 == 0 and floor % 40 != 0 else 10 if floor % 10 == 0 else floor
    return num % 40


def _alt_map(days_played: int, game_id: int, floor: int, legacy: bool) -> int | None:
    """The swapped-in map 40-60, if today's roll picks one (only once the bottom has been reached)."""
    r = day_save_random(days_played, game_id, 1293857 + floor * 400, legacy=legacy)
    if r.next_double() >= ALT_MAP + (min(0.06, floor / 10000) if floor > 120 else 0):
        return None
    area = _area(floor)
    num = r.next(40, 61)
    if num in NO_INFEST_MAPS and r.next_double() < 0.75:
        num = r.next(40, 61)
    if num == 53 and area != 121:
        num = r.next(52, 61)
    if num == 40 and area not in (0, 80):
        num = r.next(52, 61)
    return num


def _infestable(num: int) -> bool:
    return num % 5 != 0 and 5 < num % 40 < 30 and num % 40 != 19 and num not in NO_INFEST_MAPS


def _dark_and_mushroom(days_played: int, game_id: int, floor: int, dangerous: bool, legacy: bool):
    r = day_save_random(days_played, game_id, days_played, floor, 4 * floor, legacy=legacy)  # DaysPlayed is seed A too
    dark = False
    if not dangerous:
        if r.next_double() < DARK and floor > 2:
            dark = True
            r.next_double()  # the shade
    if r.next_double() < DARK_AGAIN and floor > 5 and floor != 120:
        dark = True
    mushroom = r.next_double() < MUSHROOM and _area(floor) == 80 and floor % 5 != 0
    if floor < 120 and (floor % 40 > 30 or floor >= 110) and _area(floor) != 40:
        dark = True  # the always-dark stretches
    return dark, mushroom


def floor_kind(days_played: int, game_id: int, floor: int, *, reached_bottom: bool = False,
               quarry_open: bool = False, garlic: bool = False, dangerous: bool = False,
               legacy: bool = False) -> FloorKind:
    """One floor today. `reached_bottom`: the Mines' lowest level reached is 120 (save: mine_lowestLevelReached);
    `quarry_open`: Crafts Room done and the Quarry mine visited; `garlic`: Oil of Garlic active."""
    skull = floor > 120
    dark, mushroom = _dark_and_mushroom(days_played, game_id, floor, dangerous, legacy)
    if skull and floor in FORCED_CHEST:
        return FloorKind(floor, 10, None, dark=dark)
    num: int | None = None if skull else _base_map(floor)
    if (reached_bottom or skull) and floor > 1 and (num is None or (num != 10 and num % 5)):
        num = _alt_map(days_played, game_id, floor, legacy) or num
    r = day_save_random(days_played, game_id, floor * 100, legacy=legacy)
    if (not garlic or skull) and r.next_double() < INFEST and (num is None or _infestable(num)):
        kind = "monsters" if r.next_double() < 0.5 else "slimes"
        if skull and floor > 126 and r.next_double() < 0.5:
            kind = "dinos"
        sure = not skull or (num is not None and floor < 130)
        return FloorKind(floor, num, kind, dark=dark, sure=sure)
    if not skull and quarry_open and r.next_double() < QUARRY and num % 40 > 1 and num % 5:
        return FloorKind(floor, num, None, quarry=True)
    return FloorKind(floor, num, None, mushroom=mushroom, dark=dark)


def floor_kinds(days_played: int, game_id: int, floors, **kw) -> dict[int, FloorKind]:
    """Each floor's kind today (keywords as floor_kind)."""
    return {f: floor_kind(days_played, game_id, f, **kw) for f in floors}


def infested_ahead(days_played: int, game_id: int, elevator_floor: int, walk: int = 10, **kw) -> list[FloorKind]:
    """The must-clear floors among the next `walk` below the elevator floor the player starts from."""
    floors = range(elevator_floor + 1, elevator_floor + walk + 1)
    return [k for k in floor_kinds(days_played, game_id, floors, **kw).values() if k.must_kill]


def skull_infest_chance(kind: FloorKind) -> float:
    """How likely a Skull Cavern floor whose day roll passed really is infested (the map is drawn unseeded)."""
    if kind.sure:
        return 1.0 if kind.must_kill else 0.0
    return _SKULL_INFESTABLE if kind.map is None else 1.0
