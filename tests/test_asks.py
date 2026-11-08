"""Today's questions (views/asks.py): a yes keeps the thing back from selling, a no lets it go."""

import pytest
from shared import shared_data

from valley_planner.discover import find_game, find_saves_root

GAME, SAVES = find_game(), find_saves_root()


@pytest.mark.game
@pytest.mark.skipif(GAME is None or SAVES is None, reason="needs the game and a save")
def test_a_no_puts_the_luau_pick_back_on_sale():
    from valley_planner.app import Planner
    from valley_planner.views import asks, sell
    try:
        farm = Planner(shared_data()).farm()
    except Exception:
        pytest.skip("no save here")
    luau = next((a for a in asks.asks(farm) if a.id.startswith("luau:")), None)
    if luau is None:
        pytest.skip("not Luau time in this save")
    qid, q, n = luau.keep
    name = farm.name(qid)

    def selling(declined):
        v = sell.view(farm, declined=declined)
        return sum(r["count"] for r in v["sell"] if r["id"] == qid and r["q"] == q), v

    yes, v = selling(frozenset())
    no, _ = selling(frozenset({luau.id}))
    assert no == yes + n
    assert any(r["name"] == name and "luau soup" in r["why"].lower() for r in v["keep"])


@pytest.mark.game
@pytest.mark.skipif(GAME is None or SAVES is None, reason="needs the game and a save")
def test_the_bag_never_takes_what_the_sell_plan_holds_back():
    from valley_planner.app import Planner
    from valley_planner.views import sell, today
    try:
        farm = Planner(shared_data()).farm()
    except Exception:
        pytest.skip("no save here")
    words = {0: "", 1: "silver", 2: "gold", 4: "iridium"}
    offered = {(r["name"], words.get(r["q"], "")): r["count"] for r in sell.default(farm)["sell"]}
    for st in today.view(farm)["pack"]["stops"]:
        if st["key"] in ("pierre", "willy"):
            for r in st["rows"]:
                for f in r["from"]:
                    assert f["take"] <= offered.get((r["name"], f.get("quality", "")), 0), (st["key"], r)
