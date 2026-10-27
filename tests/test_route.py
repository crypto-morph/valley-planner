"""The route engine: the crop economy, the farm simulation and the XP levels."""

from valley_planner.engine.route.economy import XP_FOR_LEVEL, harvest_xp, level_for


def test_xp_rules():
    assert harvest_xp(35) == 8 and harvest_xp(250) == 27  # Parsnip, Melon: 16·ln(0.018·price + 1)
    assert XP_FOR_LEVEL[9] == 10000 and level_for(9999) == 8 and level_for(10000) == 9 and level_for(0) == 0
