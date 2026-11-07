"""What today in the Mines holds, from the save and the day's seed (1.6.15). What each floor gives is in mines.py.

- Dark floors: MineShaft.chooseLevelType rolls DaySave(days played, floor, 4 x floor): under 0.3 makes it dark (and
  rolls once more for the shade), then under 0.15 makes it dark too. On a dark floor, ore floors not divisible by 5
  get an old miner's path from the ladder with ore beside it, about twice a plain floor's ore.
- Ladders: each stone broken rolls 0.02 + 1 / stones left + daily luck / 5, plus 0.04 once no monsters are left
  (MineShaft.checkStoneForItems), so luck and clearing the monsters both shorten the hunt. A floor that already has a
  ladder never makes one from stones.
- Coal carts: the minecarts on floors 12, 18, 28 and 38 (and the floors that reuse those maps) give 6 Coal once,
  refilled each year (MineShaft.checkAction tile 194; the save counts what's left per floor, 1 if never visited).
- Iron: from floor 41, on floors not divisible by 5.
"""

from __future__ import annotations

from .rng import day_save_random

CART_FLOORS = (12, 18, 28, 38, 52, 58, 68, 78, 92, 98, 108, 118)
CART_COAL = 6
IRON_FROM = 41
DARK, DARK_AGAIN = 0.3, 0.15
FLOOR_STONES = 60  # a typical floor (a planning figure)


def dark_floors(days_played: int, game_id: int, floors, *, legacy: bool = False) -> list[int]:
    """The floors that are dark today, among those that can carry the ore path."""
    out = []
    for f in floors:
        if f % 5 == 0 or f <= 2:
            continue
        r = day_save_random(days_played, game_id, days_played, f, 4 * f, legacy=legacy)  # DaysPlayed is seed A too
        dark = r.next_double() < DARK
        if dark:
            r.next_double()  # the shade
        if r.next_double() < DARK_AGAIN and f > 5:
            dark = True
        if dark:
            out.append(f)
    return out


def full_carts(carts_left: dict[int, int], deepest: int) -> list[int]:
    """Cart floors within reach that still hold their Coal."""
    return [f for f in CART_FLOORS if f <= deepest + 5 and carts_left.get(f, 1) > 0]


def stones_to_ladder(luck: float, *, cleared: bool = False, stones: int = FLOOR_STONES) -> float:
    """Expected stones broken before a ladder appears."""
    expected, none_yet = 0.0, 1.0
    for k in range(stones):
        left = stones - k - 1
        p = min(1.0, 0.02 + 1 / max(1, left) + luck / 5 + (0.04 if cleared else 0))
        expected += none_yet
        none_yet *= 1 - p
    return expected


def luck_words(luck: float) -> str:
    plain, cleared = round(stones_to_ladder(luck)), round(stones_to_ladder(luck, cleared=True))
    mood = "good luck" if luck > 0.02 else "poor luck" if luck < -0.02 else "ordinary luck"
    return f"{mood}: a ladder every {plain} stones or so, {cleared} once the monsters are dead, so kill them first"
