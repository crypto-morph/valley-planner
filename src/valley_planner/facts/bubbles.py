"""Where and when fish bubbles rise (GameLocation.performTenMinuteUpdate, 1.6.15).

In our words: every outdoor map rolls at each 10-minute tick, from a generator seeded with the day, the save, the
time and the map's width, so a roll owes nothing to what the player has done. With no bubbles up, a coin-flip then
two tries at a random tile: open water, fishable, and 2 to 4 tiles from land. With bubbles up, they end once they've
lasted over an hour, at a chance of 10% plus a little more each minute. Casting into them cuts the wait for a bite to
a quarter.
"""

from __future__ import annotations

from dataclasses import dataclass

from .rng import day_save_random

MAPS = ("Town", "Forest", "Mountain", "Beach")
LAST_TICK = 2600
FIRST_TICK = 610


@dataclass(frozen=True)
class Spell:
    location: str
    tile: tuple[int, int]
    start: int  # game time, 610..2600
    end: int  # when they stop; LAST_TICK if they last the day


def _ticks():
    t = FIRST_TICK
    while t <= LAST_TICK:
        yield t
        t += 50 if t % 100 == 50 else 10


def _minutes_between(a: int, b: int) -> int:
    return (b // 100 * 60 + b % 100) - (a // 100 * 60 + a % 100)


def _tiles(raw: list[str]) -> set[tuple[int, int]]:
    return {tuple(int(v) for v in t.split(",")) for t in raw}


def _distance_to_land(x: int, y: int, water: set, w: int, h: int) -> int:
    """FishingRod.distanceToLand: the first square ring around the tile with land on it (off the map doesn't count)."""
    for r in range(1, 6):
        ring = [(x + dx, y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if max(abs(dx), abs(dy)) == r]
        if any(0 <= a < w and 0 <= b < h and (a, b) not in water for a, b in ring):
            return r
    return 6


def forecast(data, location: str, days_played: int, game_id: int, *, legacy: bool = False) -> list[Spell]:
    m = data.asset(f"Maps/{location}")
    back = m["Layers"]["Back"]
    w, h = back["Width"], back["Height"]
    water, barred = _tiles(m["Water"]), _tiles(m["NoFishing"]) | _tiles(m["Rubble"])
    out: list[Spell] = []
    tile, since = None, 0
    for t in _ticks():
        r = day_save_random(days_played, game_id, t, w, legacy=legacy)
        if tile is None:
            if r.next_double() >= 0.5:
                continue
            for _ in range(2):
                p = (r.next(0, w), r.next(0, h))
                if p not in water or p in barred or not 1 < _distance_to_land(*p, water, w, h) < 5:
                    continue
                r.next_double()  # the Fish Frenzy roll
                tile, since = p, t
                break
        else:
            lasted = _minutes_between(since, t)
            if r.next_double() < 0.1 + lasted / 1800 and lasted > 60:
                out.append(Spell(location, tile, since, t))
                tile = None
    if tile is not None:
        out.append(Spell(location, tile, since, LAST_TICK))
    return out
