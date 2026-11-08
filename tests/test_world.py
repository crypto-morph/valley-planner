"""The world map page's data: the walk as lines per map, today's stops and places as pins."""

import pytest

from valley_planner.discover import find_game, find_saves_root
from valley_planner.facts.walk import polylines
from valley_planner.views.world import from_day


def test_a_walk_becomes_one_line_per_map_with_only_its_turns():
    path = [("Farm", 64, 16), ("Farm", 65, 16), ("Farm", 66, 16), ("Farm", 67, 17), ("Farm", 68, 18),
            ("Farm", 68, 19), ("Farm", 79, 17), ("BusStop", 11, 23), ("BusStop", 12, 23)]
    lines = polylines(path)
    assert [ln["loc"] for ln in lines] == ["Farm", "BusStop"]
    # east, then diagonal, then south: each straight run keeps only its ends; the exit tile stays last
    assert lines[0]["points"] == [[64, 16], [66, 16], [68, 18], [68, 19], [79, 17]]
    assert lines[1]["points"] == [[11, 23], [12, 23]]
    assert polylines([]) == [] and polylines([("Town", 1, 1)]) == [{"loc": "Town", "points": [[1, 1]]}]


def test_the_day_plan_becomes_numbered_stops_and_a_route():
    day = {"head": {"date": "Spring 3, Year 1"},
           "plan": [{"id": "water", "kind": "farm", "title": "Water 12", "why": "w", "time": "6:10 AM", "spot": None},
                    {"id": "pierre", "kind": "shop", "title": "Pierre's", "why": "seeds", "time": "9:00 AM",
                     "spot": ["Town", 43, 57]},
                    {"id": "festival", "kind": "festival", "title": "Egg Festival", "why": "", "time": "9:00 AM"}],
           "passing": [{"title": "Leek", "gold": 60, "stop": 1, "spot": ["BusStop", 28, 12]},
                       {"title": "Hoe the seed spot: 3 Seeds", "gold": 60, "stop": 3, "spot": ["Town", 1, 2]}],
           "bubbles": [{"place": "Pelican Town", "spells": ["11:10 AM to 12:30 PM, near the door"],
                        "spots": [{"loc": "Town", "x": 81, "y": 40, "label": "11:10 AM"}]}],
           "fishing": {"location": "Town", "fish": ["Catfish"]},
           "giant": {"kind": "plan", "crop": "Melon", "sow_by": "Summer 1", "text": "Sow here", "tile": [66, 26]},
           "route": [{"stop": 1, "lines": [{"loc": "Farm", "points": [[64, 16], [79, 17]]},
                                           {"loc": "Town", "points": [[0, 54], [43, 57]]}]},
                     {"stop": 3, "lines": [{"loc": "Town", "points": [[43, 57], [0, 54]]}]}]}
    pois, route, start = from_day(day)
    stops = [p for p in pois if p["kind"] == "stop"]
    assert [(p["n"], p["loc"], p["x"], p["y"]) for p in stops] == [(1, "Farm", 64, 16), (2, "Town", 43, 57)]
    leek, seeds = [p for p in pois if p["id"].startswith("passing:")]
    assert leek["kind"] == "forage" and "stop 2 (Pierre's)" in leek["why"]
    assert seeds["kind"] == "dig" and "way home" in seeds["why"]
    bubble = next(p for p in pois if p["kind"] == "bubbles")
    assert bubble["time"] == "11:10 AM to 12:30 PM" and "Catfish" in bubble["why"]
    assert next(p for p in pois if p["kind"] == "giant")["w"] == 3
    assert [r["home"] for r in route] == [False, True]
    assert start == {"loc": "Farm", "x": 64, "y": 16, "time": "6:10 AM"}
    assert from_day({})[2]["loc"] == "Farm"


GAME, SAVES = find_game(), find_saves_root()


@pytest.mark.game
@pytest.mark.skipif(GAME is None or SAVES is None, reason="needs the game and a save")
def test_the_world_endpoint_on_a_real_save():
    from fastapi.testclient import TestClient

    from valley_planner.app import create_app
    client = TestClient(create_app())
    try:
        r = client.get("/api/world")
    except Exception:  # noqa: BLE001
        pytest.skip("no readable save here")
    if r.status_code == 404:
        pytest.skip("no save here")
    v = r.json()
    assert {"locations", "pois", "villagers", "route", "exits", "start", "focus"} <= set(v)
    ids = {loc["id"] for loc in v["locations"]}
    assert {"Farm", "Town", "Forest", "Beach", "Mountain"} <= ids and v["focus"] in ids
    assert all({"id", "loc", "x", "y", "kind", "layer", "title", "why"} <= set(p) for p in v["pois"])
    assert len({p["id"] for p in v["pois"]}) == len(v["pois"])
    stops = [p["n"] for p in v["pois"] if p["kind"] == "stop"]
    assert stops == sorted(stops)
    for leg in v["route"]:
        for ln in leg["lines"]:
            assert ln["loc"] in ids and all(len(pt) == 2 for pt in ln["points"])
    assert client.get("/world.html").status_code == 200


def test_a_place_sums_its_goals_gold_and_activities():
    from valley_planner.views.world import summary
    pois = [{"loc": "Town", "layer": "route", "kind": "stop", "n": 3, "goal": "Community Center"},
            {"loc": "Town", "layer": "places", "kind": "forage", "gold": 60, "goal": "Spring Foraging bundle"},
            {"loc": "Town", "layer": "places", "kind": "bin", "gold": 15},
            {"loc": "Town", "layer": "places", "kind": "forage", "gold": 500, "reach": False},  # can't get there
            {"loc": "Town", "layer": "doors", "kind": "shop"},
            {"loc": "Beach", "layer": "places", "kind": "bubbles"}]
    s = summary(pois, "Town")
    assert s["goals"] == ["Community Center", "Spring Foraging bundle"] and s["gold"] == 75
    assert s["icons"] == ["forage", "bin"] and s["stops"] == [3]
    assert summary(pois, "Beach") == {"goals": [], "gold": 0, "icons": ["bubbles"], "stops": []}
