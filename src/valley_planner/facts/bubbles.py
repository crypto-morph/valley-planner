"""Where and when fish bubbles rise, and where ore shimmers for the pan (GameLocation.performTenMinuteUpdate and
performOrePanTenMinuteUpdate, IslandNorth.performOrePanTenMinuteUpdate, FishingRod.distanceToLand; 1.6.15).

In our words: every outdoor map rolls at each 10-minute tick, from a generator seeded with the day, the save, the
time and the map's width, so a roll owes nothing to where the player is. The bubbles roll first and the pan spot
then rolls from the same generator, so both are replayed together on every map, in the game's order:

- Bubbles, with none up: a coin-flip (drawn on the Farm too, but only the Riverland farm goes on), then two tries at
  a random tile: open water, fishable, and 2 to 4 tiles from land. A spot found rolls for a Fish Frenzy (1%, 0.8% on
  the Beach; Town, Forest, Mountain and Beach only, from day 5, before 11 PM, not on a festival day, once you've
  caught three kinds of fish or it's past day 15), and a frenzy draws once more to pick the fish.
- Bubbles, with some up: they end at 10% plus minutes up / 1800, once they've lasted over an hour (two in a frenzy).
  Casting into them cuts the wait for a bite to a quarter.
- Pan spot, only once the host has the Fish Tank done (ccFishTank) and never on the Beach: with none up, a coin-flip
  then up to eight tries at a random tile that's open water, has no Buildings tile, and has land at most one tile
  away whose first such tile (going round the ring) touches somewhere you could stand. With one up, it goes at 10%
  a tick. Ginger Island's north tries three times, only in its west river (x 4-14, y 45-69), with no standing check,
  and its spot goes at 20%.
- Distance to land counts square rings out from the tile: land in the first ring is 0, the second 1, up to 3 in the
  fourth; land only in the fifth ring, or none, is 5. Off the map isn't land.
- Both reset at the start of the day. The pan spot also goes the moment someone pans it, and the game never rolls
  another while one is up, so a forecast of later spots holds only until you pan.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .rng import day_save_random

MAPS = ("Town", "Forest", "Mountain", "Beach")  # where the bubbles are shown
# where a pan spot can rise: every outdoor map with water by the shore (the Beach and the night market excepted)
PAN_MAPS = ("Farm", "Town", "Forest", "Mountain", "Woods", "Desert",
            "IslandNorth", "IslandWest", "IslandSouth", "IslandSouthEast")
FRENZY_MAPS = ("Town", "Forest", "Mountain", "Beach")
LAST_TICK = 2600
FIRST_TICK = 610


@dataclass(frozen=True)
class Spell:
    location: str
    tile: tuple[int, int]
    start: int  # game time, 610..2600
    end: int  # when they stop; LAST_TICK if they last the day
    frenzy: bool = False  # a Fish Frenzy rolled (if the fish it picks is a fish), so they last at least two hours


@dataclass(frozen=True)
class PanSpot:
    location: str
    tile: tuple[int, int]
    start: int
    end: int  # when it goes by itself; LAST_TICK if it lasts the day. Panning it ends it at once.


@dataclass(frozen=True)
class Day:
    """What the rolls need beyond the map: the seed and the few facts of the day they check."""
    days_played: int
    game_id: int
    legacy: bool = False
    fish_kinds: int = 0  # kinds of fish caught (a frenzy waits for three, or day 15)
    festival: bool = False  # a festival today
    river_farm: bool = False  # the Riverland farm: the only farm that bubbles
    farm_map: str = "Farm"
    fish_tank: bool = False  # the host has ccFishTank
    placed: frozenset = frozenset()  # (map, x, y) with an object on: not open water

    @classmethod
    def from_save(cls, save, data) -> Day:
        from .walk import FARM_MAPS
        festival = f"{save.season}{save.day}" in data.asset("Data/Festivals/FestivalDates")
        return cls(save.days_played, int(save.unique_id), save.legacy_random, len(save.fish_caught), festival,
                   save.farm_type == 1, FARM_MAPS.get(save.farm_type, "Farm"), "ccFishTank" in save.mail,
                   frozenset((loc, x, y) for loc, tiles in save.placed.items() for x, y in tiles))


def _ticks():
    t = FIRST_TICK
    while t <= LAST_TICK:
        yield t
        t += 50 if t % 100 == 50 else 10


def _minutes_between(a: int, b: int) -> int:
    return (b // 100 * 60 + b % 100) - (a // 100 * 60 + a % 100)


def _tiles(raw: list[str]) -> set[tuple[int, int]]:
    return {tuple(int(v) for v in t.split(",")) for t in raw}


def _ring(x: int, y: int, r: int):
    """The square ring r tiles out, in the game's order: along the top, down the right, back along the bottom, up
    the left."""
    left, top, right, bottom = x - r, y - r, x + r, y + r
    yield from ((i, top) for i in range(left, right + 1))
    yield from ((right, j) for j in range(top + 1, bottom + 1))
    yield from ((i, bottom) for i in range(right - 1, left - 1, -1))
    yield from ((left, j) for j in range(bottom - 1, top, -1))


def distance_to_land(x: int, y: int, water: set, w: int, h: int, closed: set | None = None) -> int:
    """FishingRod.distanceToLand, 0..5. With `closed` (the map's unpassable tiles), the walkable-shore variant: the
    first land tile met in a ring must touch (8 ways round) a tile you could stand on, else the next ring is tried.
    The game checks the land tile itself for water there, not the neighbour, so a water neighbour counts."""
    for r in range(1, 6):
        land = next(((a, b) for a, b in _ring(x, y, r) if 0 <= a < w and 0 <= b < h and (a, b) not in water), None)
        if land is None:
            continue
        if closed is not None and all((land[0] + dx, land[1] + dy) in closed
                                      for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
            continue
        return r - 1 if r < 5 else 5
    return 5


def map_name(data, location: str, farm_map: str = "Farm") -> str:
    if location == "Farm":
        return farm_map
    path = ((data.asset("Data/Locations").get(location) or {}).get("CreateOnLoad") or {}).get("MapPath") or location
    return path.replace("\\", "/").removeprefix("Maps/")


@lru_cache(maxsize=128)
def roll(data, location: str, day: Day) -> tuple[tuple[Spell, ...], tuple[PanSpot, ...]]:
    """The whole day's bubbles and pan spots on one map, as the host's game rolls them."""
    m = data.asset(f"Maps/{map_name(data, location, day.farm_map)}")
    back = m["Layers"]["Back"]
    w, h = back["Width"], back["Height"]
    water, rubble = _tiles(m["Water"]), _tiles(m["Rubble"])
    no_fish, built, closed = _tiles(m["NoFishing"]), _tiles(m.get("Built", [])), _tiles(m.get("Closed", []))
    placed = {(x, y) for loc, x, y in day.placed if loc == location}
    total_days = day.days_played - 1  # Game1.Date.TotalDays counts from 0
    north = location == "IslandNorth"
    pan_tries, xs, ys, pan_shore, pan_ends = (3, (4, 15), (45, 70), None, 0.2) if north else \
        (8, (0, w), (0, h), closed, 0.1)

    def open_water(p):
        return p in water and p not in rubble and p not in placed

    spells: list[Spell] = []
    pans: list[PanSpot] = []
    tile = since = frenzy = None
    pan = pan_since = None
    for t in _ticks():
        r = day_save_random(day.days_played, day.game_id, t, w, legacy=day.legacy)
        if tile is None:
            if r.next_double() < 0.5 and (location != "Farm" or day.river_farm):
                for _ in range(2):
                    p = (r.next(0, w), r.next(0, h))
                    if not open_water(p) or p in no_fish or not 1 < distance_to_land(*p, water, w, h) < 5:
                        continue
                    frenzy = (r.next_double() < (0.008 if location == "Beach" else 0.01) and total_days > 3
                              and location in FRENZY_MAPS and t < 2300
                              and (day.fish_kinds > 2 or total_days > 14) and not day.festival)
                    if frenzy:
                        r.next(500)  # the frenzy's fish (whether it really is a fish isn't seeded)
                    tile, since = p, t
                    break
        else:
            lasted = _minutes_between(since, t)
            if r.next_double() < 0.1 + lasted / 1800 and lasted > (120 if frenzy else 60):
                spells.append(Spell(location, tile, since, t, frenzy))
                tile = None
        if day.fish_tank and (north or location != "Beach") and pan is None and r.next_double() < 0.5:
            for _ in range(pan_tries):
                p = (r.next(*xs), r.next(*ys))
                if open_water(p) and distance_to_land(*p, water, w, h, pan_shore) <= 1 and p not in built:
                    pan, pan_since = p, t
                    break
        elif pan is not None and r.next_double() < pan_ends:
            pans.append(PanSpot(location, pan, pan_since, t))
            pan = None
    if tile is not None:
        spells.append(Spell(location, tile, since, LAST_TICK, frenzy))
    if pan is not None:
        pans.append(PanSpot(location, pan, pan_since, LAST_TICK))
    return tuple(spells), tuple(pans)


def spells(data, location: str, day: Day) -> list[Spell]:
    """The day's bubbles on one map."""
    return list(roll(data, location, day)[0])


def forecast(data, location: str, days_played: int, game_id: int, *, legacy: bool = False) -> list[Spell]:
    """The day's bubbles on one map, from the seed alone: as on a save with no Fish Frenzy possible yet."""
    return spells(data, location, Day(days_played, game_id, legacy))


def pan_spots(data, location: str, day: Day) -> list[PanSpot]:
    """The day's pan spots on one map, if nobody pans them; none before the Fish Tank is done."""
    return list(roll(data, location, day)[1]) if day.fish_tank else []
