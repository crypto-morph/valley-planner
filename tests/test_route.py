"""The route engine: the crop economy, the farm simulation and the XP levels."""

from valley_planner.engine.route.economy import XP_FOR_LEVEL, harvest_xp, level_for


def test_xp_rules():
    assert harvest_xp(35) == 8 and harvest_xp(250) == 27  # Parsnip, Melon: 16·ln(0.018·price + 1)
    assert XP_FOR_LEVEL[9] == 10000 and level_for(9999) == 8 and level_for(10000) == 9 and level_for(0) == 0


import pytest  # noqa: E402

from valley_planner.discover import find_game  # noqa: E402

GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_fresh_year_route():
    """On a fresh farm with 80 tiles, the greenhouse (by Fall 28) and the Seed Maker fit as targets, the cash
    never goes below zero, and the Community Center as a nice-to-have says what it's left waiting on."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.simulate import FLOAT
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    v = route(new_farm(GameData(GAME)), ["greenhouse", "seed_maker"], ["kitchen", "cc"], tiles=80)
    by_id = {o["id"]: o for o in v["objectives"]}
    assert by_id["greenhouse"]["status"] == "ok" and by_id["seed_maker"]["status"] == "ok"
    assert min(c["cash"] for c in v["cash"]) >= 0
    assert FLOAT >= 0
    cc = by_id["cc"]
    assert v["cave"] == "bats"  # the fruit bats save the saplings' cost and come early
    assert cc["status"] in ("luck", "impossible") and all(": " in p for p in cc["problems"])  # each says why
    assert any("Red Cabbage" in p and "luck" in p for p in cc["problems"])  # Year 1: only the cart


def test_cave_odds():
    from valley_planner.facts.cave import BATS, MUSHROOMS, nightly, nights_for
    # bats: about 1.9 fruit a night; a Pomegranate is 3.6% of them (one in five fruit is a tree fruit,
    # nine in ten of those one of five kinds)
    assert 0.06 < nightly(BATS, "637") < 0.075
    assert 20 <= nights_for(BATS, "637") <= 25
    assert nights_for(MUSHROOMS, "637") is None and nightly(MUSHROOMS, "422") > 0.13  # six boxes, 2.5% each


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_route_tree():
    """Each step carries what's behind it in order, and a requirement two goals share is planned once."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    v = route(new_farm(GameData(GAME)), ["greenhouse"], ["cc"], tiles=80, cave="bats")
    gh, cc = v["objectives"]
    built = [n for st in gh["steps"] for n in st["needs"] if n["state"] == "new"]
    assert built and all(n["ready"] for n in built)
    shared = [st for st in cc["steps"] if st["shared"]]
    assert shared and all(st["shared"] == "The greenhouse" and st["gold"] == 0 for st in shared)
    assert {st["what"] for st in shared} <= {st["what"] for st in gh["steps"]}


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_route_agenda():
    """The next week of the route, as days to act on, each naming the goal it serves."""
    from valley_planner.engine.route.plan import AGENDA_DAYS, route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    v = route(new_farm(GameData(GAME)), ["greenhouse", "seed_maker"], [], tiles=80, cave="bats")
    assert v["agenda"] and all(1 <= a["n"] < 1 + AGENDA_DAYS and a["goal"] and a["text"] for a in v["agenda"])
    assert [a["n"] for a in v["agenda"]] == sorted(a["n"] for a in v["agenda"])


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_more_goals():
    """A horse, sprinklers and marriage on a fresh farm: the wedding comes three days after the Pendant, which
    waits for the kitchen and the beach bridge; the Stable waits for a Steel Axe."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    v = route(new_farm(GameData(GAME)), ["stable", "marriage"], ["sprinklers"], tiles=80, cave="bats")
    by = {o["id"]: o for o in v["objectives"]}
    stable = by["stable"]["steps"][0]
    assert by["stable"]["status"] == "ok" and stable["needs"][0]["label"].startswith("a Copper Axe")
    m = by["marriage"]
    assert m["status"] == "ok"
    labels = [st["what"] for st in m["steps"]]
    assert labels[-1].startswith("the wedding with") and "the Mermaid's Pendant" in labels
    pendant = next(st for st in m["steps"] if st["what"] == "the Mermaid's Pendant")
    assert {n["label"] for n in pendant["needs"]} >= {"the kitchen (house upgrade)", "repair the beach bridge"}


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_tech_tree():
    """The tree: weekly columns from today, each lane's rows in week order without two cards in one week, cards
    coloured by the days they have to spare, and a step two goals use names both."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    v = route(new_farm(GameData(GAME)), ["greenhouse"], ["cc"], tiles=80, cave="bats")
    t = v["tree"]
    assert t["columns"][0]["label"].startswith("Spring 1") and len(t["columns"]) == 16
    for lane in t["lanes"]:
        for row in lane["rows"]:
            cols = [c["col"] for c in row]
            assert cols == sorted(cols) and len(set(cols)) == len(cols)
            assert all(c["urgency"] in ("plenty", "soon", "now", "daily", "shared") for c in row)
    both = [x for x in t["synergy"] if {g["goal"] for g in x["goals"]} >= {"The greenhouse", "The Community Center"}]
    assert both
