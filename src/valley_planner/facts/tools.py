"""What tools, food and bedtime cost in energy, from the game's own sums (1.6.15).

- Watering can: each use costs 2 x (charge + 1) - 0.1 x Farming level and waters 1, 3, 5, 9 or 18 tiles by
  charge (WateringCan.DoFunction, Tool.tilesAffected), so charging is cheaper a tile.
- Hoe: 2 - 0.1 x Farming a swing whatever the charge, because the cost is taken before the charge is read
  (Hoe.DoFunction).
- Axe: 2 - 0.1 x Foraging a swing. A tree has 10 health and its stump 5; the axe does 1 / 1.25 / 1.67 / 2.5 / 5 to
  a tree and 2 / 2.5 / 3.34 / 5 / 10 to a stump by upgrade (Tree.performToolAction).
- Fishing rod: 8 - 0.1 x Fishing a cast, caught or not.
- Food: ceil(2.5 x Edibility) + quality x Edibility (Object.staminaRecoveredOnConsumption).
- Bed: up to midnight costs nothing. After it, tomorrow is capped at max - (1 - (2600 - time) / 200) x max / 2, the
  time read as HHMM, so 12:50am to 1:00am is a big step. You keep more if you went to bed with more. Touching 0
  halves tomorrow (max / 2 + 1) unless a Muscle Remedy, the spouse's kiss or a level-up that night clears it, and a
  level-up fills you whatever (Farmer.dayupdate, LevelUpMenu).
"""

from __future__ import annotations

import math

TILES = (1, 3, 5, 9, 18)  # by charge
MINUTES = (1.6, 0.96, 0.75, 0.55, 0.36)  # a tile, steps included, at a person's pace (ends measured, middle estimated)
TREE_HEALTH, STUMP_HEALTH = 10, 5
AXE = (1, 1.25, 1.67, 2.5, 5)
AXE_STUMP = (2, 2.5, 3.34, 5, 10)


def _charge(level: int, tiles: int) -> int:
    """The biggest charge the tool has that the job fills."""
    level = max(0, min(level, len(TILES) - 1))
    return max((p for p in range(level + 1) if TILES[p] <= max(1, tiles)), default=0)


def water(level: int, farming: int, tiles: int) -> tuple[float, float]:
    """(energy, minutes) a tile, charging the can as far as the job allows."""
    p = _charge(level, tiles)
    return (2 * (p + 1) - 0.1 * farming) / TILES[p], MINUTES[p]


def hoe(level: int, farming: int, tiles: int) -> tuple[float, float]:
    p = _charge(level, tiles)
    return (2 - 0.1 * farming) / TILES[p], MINUTES[p]


def tree(axe: int, foraging: int) -> float:
    axe = max(0, min(axe, len(AXE) - 1))
    swings = math.ceil(TREE_HEALTH / AXE[axe] - 1e-9) + math.ceil(STUMP_HEALTH / AXE_STUMP[axe] - 1e-9)
    return swings * (2 - 0.1 * foraging)


def cast(fishing: int) -> float:
    return 8 - 0.1 * fishing


def food(edibility: int, quality: int = 0) -> int:
    return math.ceil(2.5 * edibility) + quality * edibility


def wake(max_energy: int, bed: int, energy: float, *, exhausted: bool = False, level_up: bool = False) -> int:
    """Tomorrow morning's energy for a bedtime (HHMM, 2600 = 2am)."""
    if level_up:
        return max_energy
    start = max_energy // 2 + 1 if exhausted else max_energy
    if bed > 2400:
        start -= (1 - (2600 - min(2600, bed)) / 200) * (max_energy // 2)
    return int(start if exhausted else max(start, energy))
