"""Energy from the game's own sums, and the Mines day."""

import pytest

from valley_planner.facts import mine_day as mines
from valley_planner.facts import tools

GAME_ID = 453557957


def test_a_charged_can_is_cheaper_a_tile_and_a_charged_hoe_costs_one_swing():
    assert tools.water(0, 0, 50) == (2, 1.6)
    assert tools.water(1, 0, 50)[0] == pytest.approx(4 / 3)
    assert tools.water(1, 0, 2)[0] == 2  # too few tiles to fill a charge
    assert tools.hoe(4, 0, 100)[0] == pytest.approx(2 / 18)


def test_trees_by_axe():
    assert tools.tree(0, 0) == 26  # 10 swings and 3 on the stump
    assert tools.tree(4, 10) == 3


def test_food_counts_quality():
    assert tools.food(10) == 25 and tools.food(10, 2) == 45


@pytest.mark.parametrize(("bed", "morning"), [(2400, 270), (2450, 236), (2500, 202), (2600, 135)])
def test_bedtime(bed, morning):
    assert tools.wake(270, bed, 0) == morning


def test_you_keep_more_than_the_cap_but_not_when_exhausted_unless_you_level():
    assert tools.wake(270, 2500, 230) == 230
    assert tools.wake(270, 2400, 230, exhausted=True) == 136
    assert tools.wake(270, 2600, 0, exhausted=True, level_up=True) == 270


def test_dark_floors_on_spring_22():
    """The deep dive's list for this save, worked out separately."""
    got = mines.dark_floors(22, GAME_ID, range(41, 80))
    assert got == [41, 44, 46, 49, 53, 54, 57, 59, 61, 62, 63, 73, 74]


def test_luck_and_clearing_shorten_the_hunt():
    assert mines.stones_to_ladder(0.1) < mines.stones_to_ladder(0) < mines.stones_to_ladder(-0.1)
    assert mines.stones_to_ladder(0, cleared=True) < mines.stones_to_ladder(0)


def test_carts_full_until_used():
    assert mines.full_carts({12: 0, 38: 0, 3: 1}, 40) == [18, 28]
