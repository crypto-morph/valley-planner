"""Harvest quality by day, and giant crops overnight: the seeded rolls, checked against harvests in real saves."""

from collections import Counter
from pathlib import Path

import pytest
from shared import shared_data

from valley_planner.facts.harvest import giant_roll, giant_tonight, harvest_quality, quality_ahead, quality_boost
from valley_planner.save import Crop, Save

ANTROPIC = 453557957
MUGGLETON = 452013745

# Strawberries picked on days played 21 (Antropic), Farming 4 -> 5 part way (18 XP each from 1899: the 14th
# pick reaches 2150, so 14 rolls at 4, 13 at 5). The chest gained 23 normal (one an extra), 4 silver, 1 gold.
STRAWBERRIES = [(55, 22), (55, 23), (56, 24), (57, 24), (58, 24), (60, 22), (61, 24), (62, 24), (62, 25), (63, 21),
                (63, 22), (63, 23), (63, 25), (64, 22), (64, 25), (65, 21), (65, 22), (65, 23), (66, 21), (66, 22),
                (66, 25), (71, 19), (71, 20), (71, 21), (71, 22), (71, 24), (71, 25)]
# Parsnips picked on days played 23 (Muggleton), Farming 4, Speed-Gro: 12 normal and 2 gold reached the chests
# (the silver ones were shipped, so only normal and gold are checkable).
PARSNIPS = [(65, 21), (65, 22), (65, 23), (66, 19), (67, 19), (68, 19), (69, 19), (69, 20), (70, 19), (71, 19),
            (71, 22), (72, 19), (72, 21), (72, 22), (73, 19), (73, 21), (73, 22), (73, 23), (74, 19)]


def test_fertilizer_boost():
    assert [quality_boost(f) for f in ("", "(O)368", "(O)369", "(O)919", "919", "(O)465")] == [0, 1, 2, 3, 3, 0]


def test_strawberries_match_the_chest():
    both = [(harvest_quality(x, y, 21, ANTROPIC, 4), harvest_quality(x, y, 21, ANTROPIC, 5)) for x, y in STRAWBERRIES]
    fixed = Counter(a for a, b in both if a == b)
    assert fixed == Counter({0: 22, 1: 3, 2: 1})
    assert [ab for ab in both if ab[0] != ab[1]] == [(0, 1)]  # picked after the level-up: the 4th silver


def test_parsnips_match_the_chest():
    got = Counter(harvest_quality(x, y, 23, MUGGLETON, 4) for x, y in PARSNIPS)
    assert (got[0], got[2]) == (12, 2)


def test_deluxe_is_never_normal_and_clamps_hold():
    qs = [harvest_quality(x, 5, 30, ANTROPIC, 3, 3) for x in range(200)]
    assert 0 not in qs and 4 in qs
    assert all(harvest_quality(x, 5, 30, ANTROPIC, 10, 2, max_quality=0) == 0 for x in range(50))
    assert all(harvest_quality(x, 5, 30, ANTROPIC, 0, 0, min_quality=1) >= 1 for x in range(50))


def test_gold_rate_follows_the_formula():
    g = 0.2 * 0.8 + 0.2 * 2 * (10 / 12) + 0.01  # Farming 8, Quality Fertilizer
    n = 20000
    gold = sum(harvest_quality(x, y, d, ANTROPIC, 8, 2) == 2 for x in range(20) for y in range(20) for d in range(50))
    assert abs(gold / n - g) < 0.015


def test_giant_roll():
    assert giant_roll(61, 21, 25, ANTROPIC, "Cauliflower")
    assert not giant_roll(61, 21, 24, ANTROPIC, "Cauliflower")
    assert not giant_roll(61, 21, 25, ANTROPIC, "Melon")  # the key is part of the seed
    assert giant_roll(61, 21, 24, ANTROPIC, "Cauliflower", chance=1.0)
    rate = sum(giant_roll(x, y, 25, ANTROPIC, "Melon") for x in range(100) for y in range(100)) / 10000
    assert 0.007 < rate < 0.013


# --- with a made-up save (ids and short names only; no game needed) ----------------------------------------


class Data:
    def __init__(self):
        self.assets = {
            "Data/GiantCrops": {"Cauliflower": {"FromItemId": "(O)190", "Chance": 0.009999999776482582,
                                                "TileSize": {"X": 3, "Y": 3}}},
            "Data/Crops": {"474": {"Seasons": ["Spring"], "HarvestItemId": "190"},
                           "473": {"Seasons": ["Spring"], "HarvestItemId": "188", "RegrowDays": 3}},
            "Data/Objects": {"190": {"Name": "Cauliflower"}, "188": {"Name": "Green Bean"}},
        }

    def asset(self, name):
        return self.assets[name]


def crop(tile, harvest="190", seed="474", days_left=0, **kw):
    return Crop(harvest_id=harvest, seed_id=seed, location=kw.pop("location", "Farm"), tile=tile,
                days_left=days_left, grown=None, ready=days_left == 0, dead=kw.pop("dead", False),
                watered=kw.pop("watered", False), fertilizer=kw.pop("fertilizer", ""), regrows=kw.pop("regrows", False),
                forage=False, in_pot=False)


def save_on(days_played, crops, game_id=ANTROPIC):
    return Save(path=Path("x"), mtime=0.0, game_version="1.6.15", farmer="F", farm="F", season="spring", day=1,
                year=1, days_played=days_played, money=0, total_earned=0, unique_id=str(game_id),
                legacy_random=False, weather="sun", weather_tomorrow="sun", daily_luck=0.0, crops=crops,
                skills={"farming": 5})


def square(x, y, **kw):
    return [crop((x + i, y + j), **({"days_left": 3} if (i, j) != (0, 0) else kw)) for j in range(3) for i in range(3)]


def test_quality_ahead_matches_the_roll_and_stops_at_the_season():
    s = save_on(22, [crop((67, 19), "188", "473", regrows=True), crop((5, 5), days_left=2)])
    (a,) = quality_ahead(s, Data(), days=7)  # the unripe one is left out
    assert a.name == "Green Bean" and a.days_played == tuple(range(22, 29))
    assert a.qualities == tuple(harvest_quality(67, 19, d, ANTROPIC, 5) for d in range(22, 29))
    assert a.best_day == a.days_played[a.qualities.index(max(a.qualities))]
    late = quality_ahead(save_on(27, [crop((67, 19))]), Data(), days=5)[0]
    assert late.days_played == (27, 28) and late.cut_short == "dies when Summer starts"


def test_giant_tonight_ready_incomplete_and_overlapping():
    data = Data()
    full = giant_tonight(save_on(24, square(61, 21)), data)
    assert full.days_played == 25 and [h.tile for h in full.ready] == [(61, 21)] and not full.incomplete
    assert full.ready[0].sure and not full.ready[0].ripens_tonight
    gap = giant_tonight(save_on(24, square(61, 21)[:-2]), data)
    assert not gap.ready and gap.incomplete[0].missing == ((62, 23), (63, 23))
    assert not giant_tonight(save_on(23, square(61, 21)), data).ready  # another night's roll
    later = giant_tonight(save_on(22, square(61, 21, days_left=3)), data, night=3)
    assert [h.tile for h in later.ready] == [(61, 21)] and later.ready[0].ripens_tonight
    assert not giant_tonight(save_on(22, square(61, 21, days_left=4)), data, night=3).ready  # not grown by then
    # (65, 26) and (66, 25) both hit that night and their squares share tiles: only one can form
    tiles = {c.tile for c in square(65, 26) + square(66, 25)}
    both = [crop(t, days_left=0 if t in ((65, 26), (66, 25)) else 3) for t in sorted(tiles)]
    two = giant_tonight(save_on(24, both), data)
    assert {h.tile for h in two.ready} == {(65, 26), (66, 25)} and not any(h.sure for h in two.ready)


def test_no_giant_off_the_farm_or_out_of_season():
    data = Data()
    shed = [crop(c.tile, location="Greenhouse") for c in square(61, 21)]
    assert not giant_tonight(save_on(24, shed), data).ready
    # into Summer 1 the spring crop dies before it can grow
    assert not giant_tonight(save_on(28, square(61, 21)), data).ready


# --- with the game's own data ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    try:
        return shared_data()
    except RuntimeError:
        pytest.skip("no game here")


def test_real_giant_crop_data(data):
    keys = set(data.asset("Data/GiantCrops"))
    assert {"Cauliflower", "Melon", "Pumpkin"} <= keys
    s = save_on(24, square(61, 21))
    assert [h.key for h in giant_tonight(s, data).ready] == ["Cauliflower"]
    (a,) = quality_ahead(save_on(22, [crop((61, 21), fertilizer="(O)368")]), data, days=3)
    assert a.name == "Cauliflower" and a.qualities == tuple(harvest_quality(61, 21, d, ANTROPIC, 5, 1)
                                                            for d in (22, 23, 24))
