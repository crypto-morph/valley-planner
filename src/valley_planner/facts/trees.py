"""Fruit trees: when a sapling is grown and when its fruit comes (FruitTree.dayUpdate, 1.6.15).

In our words: each night a tree takes a day off its days-to-grow, unless something stands on one of the eight
tiles around it (most objects, a crop, a path or a building; grass and artifact spots are fine). The night it
reaches none it's grown, and that same night, and every night after while its season lasts, it adds a fruit,
up to three. In the greenhouse (and on the island farm) it fruits whatever the season.
"""

from __future__ import annotations

from .conditions import SEASONS

MAX_FRUIT = 3


def season_of(day: int) -> str:
    return SEASONS[(day - 1) // 28 % 4]


def schedule(today: int, days_left: int, seasons: list[str], on_tree: int = 0, indoor: bool = False,
             horizon: int = 2 * 112) -> dict:
    """{grown, first, fruit_by}: the morning it's grown, the first morning with fruit on it (None if not within
    `horizon` days), and the fruit on it by its season's last day this time round. Days are days played."""
    grown = today + days_left
    if days_left <= 0 and on_tree:
        first = today
    else:
        first = next((d for d in range(max(grown, today + 1), today + horizon)
                      if indoor or season_of(d) in seasons), None)
    fruit_by = None
    if first is not None:
        end = first if indoor else ((first - 1) // 28 + 1) * 28
        fruit_by = min(MAX_FRUIT, on_tree + (end - first + 1) - (1 if first == today and on_tree else 0))
    return {"grown": grown, "first": first, "fruit_by": fruit_by}
