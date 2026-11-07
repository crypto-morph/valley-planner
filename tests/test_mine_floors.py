"""Mines floor kinds by day: infested, slime, quarry, mushroom and dark floors from the seeded rolls."""

from collections import Counter

from valley_planner.facts.mine_day import dark_floors
from valley_planner.facts.mine_floors import (
    FloorKind,
    floor_kind,
    floor_kinds,
    infested_ahead,
    skull_infest_chance,
)

GID = 324842137
DAYS = range(1, 301)
NEVER = [*range(1, 6), *range(30, 46), *range(70, 86), *range(110, 121)]
ELIGIBLE = [f for f in range(1, 121) if f % 5 and 5 < f % 40 < 30 and f % 40 != 19]


def test_floors_that_never_infest_without_the_swapped_maps():
    for d in DAYS:
        assert not any(k.must_kill for k in floor_kinds(d, GID, NEVER).values())


def test_infestation_rate_and_split():
    kinds = Counter(k.infested for d in DAYS for k in floor_kinds(d, GID, ELIGIBLE).values())
    n = len(DAYS) * len(ELIGIBLE)
    hit = kinds["monsters"] + kinds["slimes"]
    assert abs(hit / n - 0.044) < 0.004
    assert abs(kinds["monsters"] / hit - 0.5) < 0.08
    assert "dinos" not in kinds


def test_oil_of_garlic_stops_it_in_the_mines():
    for d in range(1, 150):
        assert not infested_ahead(d, GID, 0, 120, garlic=True)


def test_quarry_floors_only_after_the_crafts_room_and_never_infested():
    assert not any(k.quarry for d in range(1, 150) for k in floor_kinds(d, GID, range(1, 121)).values())
    quarry = [k for d in DAYS for k in floor_kinds(d, GID, range(1, 121), quarry_open=True).values() if k.quarry]
    assert quarry and all(not k.must_kill and not k.dark and not k.mushroom for k in quarry)
    assert all(k.map % 5 and k.map % 40 > 1 for k in quarry)
    # opening the Quarry doesn't change which floors are infested (that roll comes first)
    for d in range(1, 100):
        a = [k.floor for k in infested_ahead(d, GID, 0, 120)]
        assert a == [k.floor for k in infested_ahead(d, GID, 0, 120, quarry_open=True)]


def test_dark_matches_mine_day_where_both_apply():
    floors = [f for f in range(3, 120) if f % 5 and f % 40 <= 30 and f < 110]
    for d in range(1, 100):
        kinds = floor_kinds(d, GID, floors)
        lit_by_roll = [f for f in floors if kinds[f].dark or kinds[f].quarry or kinds[f].must_kill]
        assert set(dark_floors(d, GID, floors)) <= set(lit_by_roll)
        assert [f for f in floors if kinds[f].dark] == [f for f in dark_floors(d, GID, floors)
                                                         if not kinds[f].quarry]


def test_always_dark_stretches():
    for d in range(1, 50):
        kinds = floor_kinds(d, GID, [*range(31, 40), *range(110, 120)])
        assert all(k.dark for k in kinds.values() if not k.quarry)


def test_mushroom_floors_only_in_the_lava_levels():
    floors = Counter(k.floor for d in DAYS for k in floor_kinds(d, GID, range(1, 121)).values() if k.mushroom)
    assert floors and all(80 < f < 120 and f % 5 for f in floors)


def test_swapped_maps_once_the_bottom_is_reached():
    maps = Counter(k.map for d in DAYS for k in floor_kinds(d, GID, range(1, 121), reached_bottom=True).values())
    alt = sum(v for m, v in maps.items() if 40 <= m <= 60)
    assert 0.02 < alt / (len(DAYS) * 96) < 0.07  # 6% of the 96 floors not divisible by 5
    assert maps[53] < maps[52] / 3  # only by a re-roll
    assert all(m < 40 or m == 120 for m in Counter(
        k.map for d in range(1, 100) for k in floor_kinds(d, GID, range(1, 121)).values()))


def test_maps():
    kinds = floor_kinds(1, GID, [1, 10, 20, 40, 47, 60, 80, 100, 120])
    assert {f: k.map for f, k in kinds.items()} == {1: 1, 10: 10, 20: 20, 40: 10, 47: 7, 60: 20, 80: 10,
                                                     100: 20, 120: 120}


def test_infested_ahead_walks_from_the_elevator():
    for d in range(1, 150):
        ahead = infested_ahead(d, GID, 20, 10)
        assert all(21 <= k.floor <= 30 and k.must_kill for k in ahead)
        assert ahead == [k for k in floor_kinds(d, GID, range(21, 31)).values() if k.must_kill]


def test_skull_cavern_is_only_sure_when_not_infested():
    kinds = [floor_kind(d, GID, 150) for d in DAYS]
    hit = [k for k in kinds if k.must_kill]
    assert hit and all(not k.sure for k in hit)
    assert {k.infested for k in hit} <= {"monsters", "slimes", "dinos"}
    assert all(k.sure and skull_infest_chance(k) == 0 for k in kinds if not k.must_kill)
    assert all(0.5 < skull_infest_chance(k) <= 1 for k in hit)
    assert not any(k.quarry for k in kinds)
    assert floor_kind(1, GID, 220) == FloorKind(220, 10, None, dark=floor_kind(1, GID, 220).dark)


def test_legacy_random_differs():
    a = [k.floor for d in range(1, 60) for k in infested_ahead(d, GID, 0, 120)]
    b = [k.floor for d in range(1, 60) for k in infested_ahead(d, GID, 0, 120, legacy=True)]
    assert a != b
