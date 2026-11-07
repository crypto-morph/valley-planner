"""The pack list: who buys what, and what goes in the bag for the day's stops."""

from types import SimpleNamespace

import pytest

from valley_planner.facts.buyers import Buyers
from valley_planner.save import Item


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")


@pytest.fixture(scope="module")
def farm():
    from valley_planner.app import Planner
    try:
        return Planner(None).farm()
    except Exception:
        pytest.skip("no save here")


def test_shops_buy_what_the_game_says(data):
    b = Buyers(data)
    assert "SeedShop" in b.of(-75) and "SeedShop" in b.of(-81)  # crops and forage
    assert b.of(-4) == ["FishShop"]
    assert "Blacksmith" in b.of(-2) and "Blacksmith" in b.of(-12)
    assert b.of(-16) == ["Carpenter"] and b.of(-28) == ["AdventureShop"]
    assert b.of(None) == []


def stop(sid, kind="shop"):
    return {"id": sid, "kind": kind, "title": sid}


def test_tools_stay_only_if_a_stop_needs_them(farm):
    from valley_planner.views import pack
    town = pack.build(farm, [stop("pierre")])
    mines = pack.build(farm, [stop("mines", "mine")])
    bag = [i.name for i in farm.save.items if i.where == "Backpack"]
    if "Pickaxe" in bag:
        assert "Pickaxe" in town["leave"] and "Pickaxe" in mines["tools"] and "Pickaxe" not in mines["leave"]
    assert mines["slots"]["free_on_purpose"] == 3


def test_the_bag_never_overfills_and_what_will_not_fit_is_shipped(farm, monkeypatch):
    from valley_planner.views import pack, sell
    rows = [{"id": f"(O){i}", "name": f"Thing {i}", "each": 10 + i, "count": 1, "category": -75, "q": 0, "where": ["chest"]}
            for i in range(30)]
    monkeypatch.setattr(sell, "default", lambda _f: {"sell": rows})
    monkeypatch.setattr(farm.save, "items", [Item(id=str(i), name=f"Thing {i}", stack=1, quality=0, where="Farm chest")
                                             for i in range(30)])
    v = pack.build(farm, [stop("pierre")])
    assert v["slots"]["used"] <= v["slots"]["max"]
    assert v["dropped"] and "Thing 0" in v["dropped"]  # the cheapest goes first
    assert "Thing 29" in next(s for s in v["stops"] if s["stop"] == "Pierre's")["items"]


def test_with_no_shop_on_the_route_spares_go_in_the_bin(farm, monkeypatch):
    from valley_planner.views import pack, sell
    rows = [{"id": "(O)129", "name": "Anchovy", "each": 30, "count": 2, "category": -4, "q": 0, "where": ["chest"]}]
    monkeypatch.setattr(sell, "default", lambda _f: {"sell": rows})
    monkeypatch.setattr(farm.save, "items", [Item(id="129", name="Anchovy", stack=2, quality=0, where="Farm chest")])
    v = pack.build(farm, [stop("pierre")])
    assert [{k: x[k] for k in ("name", "gold", "item", "count", "each")} for x in v["ship"]] == [
        {"name": "2 Anchovy", "gold": 60, "item": "Anchovy", "count": 2, "each": 30}]


def test_a_gift_is_a_like_and_never_something_dear(farm, monkeypatch):
    from valley_planner.views import pack
    monkeypatch.setattr(farm, "gifts", SimpleNamespace(giftable=lambda _q: True,
                                                       taste=lambda _w, q: "love" if q == "(O)72" else "like"))
    spare = [{"id": "(O)72", "name": "Diamond", "each": 750, "count": 1},
             {"id": "(O)20", "name": "Leek", "each": 60, "count": 2}]
    row, taste = pack._gift(farm, "Penny", spare)
    assert row["name"] == "Leek" and taste == "like"


def test_chests_decide_what_you_can_carry(farm, monkeypatch):
    from valley_planner.views import errands, pack, sell
    wood = Item(id="388", name="Wood", stack=99, quality=0, where="CommunityCenter chest")
    stone = Item(id="390", name="Stone", stack=99, quality=0, where="Farm chest")
    onion = Item(id="399", name="Spring Onion", stack=5, quality=0, where="Mine chest", category=-81)
    monkeypatch.setattr(farm.save, "items", [wood, stone, onion])
    monkeypatch.setattr(errands, "community_center", lambda _f: {"rooms": [{"items": [
        {"name": "Wood", "count": 99, "open": True}, {"name": "Stone", "count": 99, "open": True}]}]})
    rows = [{"id": "(O)399", "name": "Spring Onion", "each": 8, "count": 5, "category": -81, "q": 0, "where": []}]
    monkeypatch.setattr(sell, "default", lambda _f: {"sell": rows})
    v = pack.build(farm, [stop("cc"), stop("pierre")])
    cc = next(s for s in v["stops"] if s["stop"] == "Community Center")
    assert cc["there"] == ["99 Wood"] and cc["items"] == ["99 Stone"]
    assert v["slots"]["used"] == 1  # the Wood is already there
    assert v["left_behind"][0]["items"] == ["5 Spring Onion"]
    assert not [s for s in v["stops"] if s["stop"] == "Pierre's"]  # the onions aren't reachable
    mines = pack.build(farm, [stop("mines", "mine"), stop("pierre")])
    assert not mines["left_behind"] and "5 Spring Onion" in next(
        s for s in mines["stops"] if s["stop"] == "Pierre's")["items"]
