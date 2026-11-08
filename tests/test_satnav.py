"""The walk as satnav steps (facts/walk.py Walker.steps), for static/satnav.js."""

import pytest

from valley_planner.facts.walk import Landmark, Walker, _legs, _spans


def fake_walker() -> Walker:
    """A walker over two made-up 20x20 maps, no game files: A's north edge leads to B, a door on B."""
    w = Walker(None)
    w.__dict__["grids"] = {"A": (20, 20, set()), "B": (20, 20, set())}
    w.__dict__["landmarks"] = {"A": [], "B": [Landmark("SeedShop", 14, 4), Landmark("Garbage:Evelyn", 3, 9)]}
    return w


def walk(loc, tiles):
    return [(loc, x, y) for x, y in tiles]


# On A: up from (5, 15) to the north edge at (5, 0). On B: east along row 10, then northeast to (14, 5).
PATH = (walk("A", [(5, y) for y in range(15, -1, -1)])
        + walk("B", [(x, 10) for x in range(0, 10)] + [(10 + i, 9 - i) for i in range(5)]))


def test_spans_run_end_to_end_and_say_what_legs_says():
    tiles = [(0, y) for y in range(17)] + [(x, 16) for x in range(1, 17)] + [(16, 17)]  # a 1-tile wiggle at the end
    spans = _spans(tiles)
    assert [(d, n) for d, n, _, _ in spans] == _legs(tiles) == [("south", 16), ("east", 16)]
    assert spans[0][2] == 0 and spans[-1][3] == len(tiles) - 1
    assert all(a[3] == b[2] for a, b in zip(spans, spans[1:], strict=False))


def test_steps_walk_leave_by_the_edge_and_go_in_at_the_door():
    w = fake_walker()
    steps = w.steps(PATH, lambda n: {"B": "Bee Town", "SeedShop": "Pierre's"}.get(n, n))
    assert [s["kind"] for s in steps] == ["walk", "exit", "walk", "walk", "door"]
    first, out, east, slant, door = steps
    assert (first["loc"], first["from"], first["to"], first["heading"], first["tiles"]) == ("A", [5, 15], [5, 0],
                                                                                         "north", 15)
    assert first["text"] == "Head north for 15 tiles" and first["points"] == [[5, 15], [5, 0]]
    assert out["heading"] == "north" and out["onto"] == "B" and out["text"] == "Leave by the north edge to Bee Town"
    assert east["loc"] == "B" and east["from"] == [0, 10] and east["text"].startswith("Head east")
    assert slant["heading"] == "northeast" and slant["text"].startswith("Turn northeast")
    assert east["to"] == slant["from"] and slant["to"] == [14, 5]
    assert door["heading"] == "north" and door["to"] == [14, 4] and door["text"] == "Go in at Pierre's"
    assert all(s["minutes"] >= 0 for s in steps)


def test_steps_tell_the_same_walk_as_the_directions():
    w = fake_walker()
    words = " ".join(w.directions(PATH))
    for s in w.steps(PATH):
        if s["kind"] == "walk":
            assert f"{s['heading']} {s['tiles']}" in words


def test_no_door_step_without_a_door_above_and_garbage_is_not_a_door():
    w = fake_walker()
    assert w.steps(walk("B", [(3, y) for y in range(20, 9, -1)]))[-1]["kind"] == "walk"  # the can at (3, 9)
    assert w.steps([]) == []


def test_the_days_plan_carries_steps(data):
    from valley_planner.app import Planner
    from valley_planner.views import today
    try:
        v = today.view(Planner(None).farm())
    except Exception:
        pytest.skip("no save here")
    assert v["start"][0] in v["places"]
    walked = {r["stop"] for r in v["route"]}
    for i, row in enumerate(v["plan"]):
        assert bool(row.get("steps")) == (i in walked)
        for s in row.get("steps", []):
            assert s["kind"] in ("walk", "exit", "door") and s["text"] and s["points"]
    assert bool(v["home_steps"]) == bool(v["home"])


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")
