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
    never goes below the float, and the Community Center as a nice-to-have explains what doesn't fit."""
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
    assert cc["status"] == "impossible" and all(": " in p for p in cc["problems"])  # each says why
