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


def test_a_birthday_gift_is_the_cheapest_loved_else_liked_and_never_a_bundle_item(monkeypatch):
    from types import SimpleNamespace

    from valley_planner.views import keep

    tastes = {"(O)18": "like", "(O)66": "like", "(O)266": "love", "(O)20": "like"}
    prices = {"18": 30, "66": 100, "266": 260, "20": 60}
    farm = SimpleNamespace(
        data=SimpleNamespace(asset=lambda name: {k: {"Price": v} for k, v in prices.items()}),
        held=lambda: {"(O)18": 1, "(O)66": 3, "(O)266": 1, "(O)20": 2},
        gifts=SimpleNamespace(giftable=lambda q: True, taste=lambda npc, q: tastes[q]))
    reserved = []
    monkeypatch.setattr(keep, "_bundles", lambda farm, s: reserved)  # what the bundle plan sets aside
    monkeypatch.setattr(keep, "_requests", lambda farm, s: [])
    assert keep.birthday_gift(farm, "Jas") == ("(O)266", "love")  # loved beats a cheaper liked one
    reserved.append(keep.Claim("(O)266", 1, "Dye bundle"))
    assert keep.birthday_gift(farm, "Jas") == ("(O)18", "like")  # the Red Cabbage is the Dye bundle's
