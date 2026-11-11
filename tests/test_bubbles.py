"""Bubbles and pan spots (facts/bubbles.py): the shore distance on a made-up map, then the day's rolls."""

import pytest

from valley_planner.facts import bubbles
from valley_planner.facts.bubbles import Day, distance_to_land


def _lake(w=30, h=30, land=()):
    """All water but the given land tiles."""
    return {(x, y) for x in range(w) for y in range(h)} - set(land), w, h


def test_distance_to_land_counts_rings_from_zero():
    for ring, want in ((1, 0), (2, 1), (3, 2), (4, 3), (5, 5)):
        water, w, h = _lake(land=[(15 + ring, 15)])
        assert distance_to_land(15, 15, water, w, h) == want
    water, w, h = _lake()
    assert distance_to_land(15, 15, water, w, h) == 5  # no land at all
    assert distance_to_land(0, 0, water, w, h) == 5  # off the map isn't land


def test_rings_go_round_from_the_top_left():
    assert list(bubbles._ring(5, 5, 1)) == [(4, 4), (5, 4), (6, 4), (6, 5), (6, 6), (5, 6), (4, 6), (4, 5)]


def test_the_walkable_shore_looks_only_at_the_first_land_tile_of_a_ring():
    # the first land met in ring 1 (top-left) is boxed in; the other ring-1 land isn't looked at, so ring 2 decides
    boxed = (14, 14)
    walls = {(boxed[0] + dx, boxed[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy}
    water, w, h = _lake(land=[boxed, (16, 16), *walls])
    assert distance_to_land(15, 15, water, w, h) == 0
    assert distance_to_land(15, 15, water, w, h, closed=walls) == 1  # (13, 13) is the first land in ring 2
    # a water neighbour counts as somewhere to stand: the game checks the land tile for water, not the neighbour
    water, w, h = _lake(land=[(16, 15)])
    assert distance_to_land(15, 15, water, w, h, closed=set()) == 0


class _Data:
    """A map that's a lake with a sandy rim, for the rolls without the game's files."""

    def __init__(self, w=40, h=40):
        water = [f"{x},{y}" for x in range(3, w - 3) for y in range(3, h - 3)]
        self.map = {"Layers": {"Back": {"Width": w, "Height": h}}, "Water": water, "NoFishing": [], "Rubble": [],
                    "Built": [], "Closed": []}

    def asset(self, name):
        return {} if name == "Data/Locations" else self.map


def test_pan_spots_wait_for_the_fish_tank_and_skip_the_beach():
    data = _Data()
    plain, tank = Day(100, 123456789), Day(100, 123456789, fish_tank=True)
    assert bubbles.pan_spots(data, "Town", plain) == []
    assert bubbles.pan_spots(data, "Beach", tank) == []
    spots = bubbles.pan_spots(data, "Town", tank)
    assert spots and all(s.start <= s.end for s in spots)
    water = {tuple(int(v) for v in t.split(",")) for t in data.map["Water"]}
    assert all(distance_to_land(*s.tile, water, 40, 40, set()) <= 1 for s in spots)
    assert all(a.end <= b.start for a, b in zip(spots, spots[1:], strict=False))  # one at a time
    # the bubbles draw first from each tick's generator, so the pan rolls never move them
    assert bubbles.spells(data, "Town", plain) == bubbles.spells(data, "Town", tank)


def test_only_the_riverland_farm_bubbles():
    data = _Data()
    assert bubbles.spells(data, "Farm", Day(100, 123456789)) == []
    assert bubbles.spells(data, "Farm", Day(100, 123456789, river_farm=True))


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")


def test_pan_spots_rise_by_the_shore_once_the_fish_tank_is_done(data):
    day = Day(228, 324842137, fish_tank=True)
    for loc in ("Town", "Mountain", "Forest", "Farm", "IslandNorth"):
        m = data.asset(f"Maps/{bubbles.map_name(data, loc)}")
        water, built = bubbles._tiles(m["Water"]), bubbles._tiles(m["Built"])
        spots = bubbles.pan_spots(data, loc, day)
        assert spots, loc
        assert all(s.tile in water and s.tile not in built for s in spots)
        if loc == "IslandNorth":
            assert all(4 <= s.tile[0] < 15 and 45 <= s.tile[1] < 70 for s in spots)
    assert bubbles.pan_spots(data, "Town", day) == bubbles.pan_spots(data, "Town", day)  # seeded
    assert bubbles.pan_spots(data, "Town", Day(229, 324842137, fish_tank=True)) != bubbles.pan_spots(data, "Town", day)


def test_bubbles_rise_two_to_four_tiles_out(data):
    m = data.asset("Maps/Mountain")
    water, w, h = bubbles._tiles(m["Water"]), m["Layers"]["Back"]["Width"], m["Layers"]["Back"]["Height"]
    spells = bubbles.forecast(data, "Mountain", 4, 453557957)
    assert spells and all(1 < distance_to_land(*s.tile, water, w, h) < 5 for s in spells)
