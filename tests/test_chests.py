"""Chests named by how they look: the colour bar's colours, plain when none was picked."""

from valley_planner.facts.chests import colour_name, describe, ordinal


def test_chest_names():
    assert colour_name(0, 170, 0) == "green" and colour_name(255, 117, 195) == "pink"
    assert colour_name(0, 0, 0) == ""  # no colour picked
    assert colour_name(1, 168, 2) == "green"  # off the bar: the nearest
    assert describe("130", 0, 0, 0) == "plain chest" and describe("BigChest", 85, 85, 255) == "blue big chest"
    assert describe("232", 255, 0, 0) == "red stone chest"
    assert [ordinal(i, 2) for i in range(2)] == ["left", "right"]
    assert [ordinal(i, 4) for i in range(4)] == ["leftmost", "2nd from the left", "3rd from the left", "rightmost"]
