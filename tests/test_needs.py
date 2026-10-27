"""What it all takes: the goals' needs added up, each unlock once, and every way to get each item."""

import pytest

from valley_planner.discover import find_game, find_saves_root

GAME, SAVES = find_game(), find_saves_root()
ALL = (["greenhouse", "seed_maker"], ["kitchen", "cc", "stable", "sprinklers", "house_2", "marriage"])
pytestmark = [pytest.mark.game, pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")]


@pytest.fixture(scope="module")
def fresh():
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    return new_farm(GameData(GAME))


@pytest.fixture(scope="module")
def saved():
    if SAVES is None:
        pytest.skip("no save here")
    from valley_planner.app import Planner
    return Planner(None).farm()


def _check(v: dict) -> None:
    """Totals are the sum of their breakdown; a choice has 2+ ways and at most one is the route's."""
    for r in v["resources"]:
        assert r["total"] == sum(g["amount"] for g in r["breakdown"]), r["id"]
        assert all(g["amount"] == sum(i["amount"] for i in g["items"]) for g in r["breakdown"])
        assert r["short"] == max(0, r["total"] - r["have"] - (r["expected"] or 0))
    for c in v["choices"]:
        assert len(c["options"]) >= 2, c["item"]
        assert sum(o["state"] == "planned" for o in c["options"]) <= 1
        assert sum(o["planned"] for o in c["options"]) <= 1


def test_vault_counted_once(fresh):
    """The bus to the Desert is the Vault's gold: counted as the Vault, never again for what the desert gives."""
    from valley_planner.engine.route.needs import needs
    v = needs(fresh, ["cc"], cave="bats")
    _check(v)
    gold = v["resources"][0]
    items = [i for g in gold["breakdown"] for i in g["items"]]
    vault = [i for i in items if i["label"] == "The Vault"]
    assert len(vault) == 1
    assert vault[0]["amount"] == sum(b.gold or 0 for b in fresh.bundles.in_area(4) if not b.done)
    desert = vault[0]["how"].split(": ", 1)[1].split(", ")
    assert desert and not any(i["label"] in desert for i in items)


def test_shared_unlock_once(fresh):
    """The kitchen comes before the second house upgrade: paid once, under the first goal, with `also`."""
    from valley_planner.engine.route.needs import needs
    from valley_planner.engine.unlocks import Unlocks
    u = Unlocks(fresh)
    v = needs(fresh, ["kitchen"], ["house_2"], cave="bats")
    _check(v)
    gold = {g["goal"]: g for g in v["resources"][0]["breakdown"]}
    assert gold["kitchen"]["amount"] == u.get("kitchen").gold
    axe = sum(x.gold for x in u.chain("tool:Axe@2"))  # Hardwood needs a Steel Axe
    assert gold["house_2"]["amount"] == u.get("house:2").gold + axe
    assert gold["kitchen"]["items"][0]["also"] == ["The second house upgrade"]
    assert gold["kitchen"]["also"] == ["The second house upgrade"]


def test_misses_counted(saved):
    """What the route can't place this year still counts, marked as not this year."""
    from valley_planner.engine.route.needs import needs
    from valley_planner.engine.route.plan import route
    v = needs(saved, *ALL)
    _check(v)
    plan = {o["id"]: o for o in route(saved, *ALL)["objectives"]}
    items = [(g["goal"], i) for r in v["resources"] for g in r["breakdown"] for i in g["items"]]
    for oid, o in plan.items():
        if o["misses"] and o["status"] != "done":
            assert any(goal == oid and not i["this_year"] for goal, i in items), oid
    if plan["marriage"]["status"] != "done" and any(m["what"] == "the Mermaid's Pendant"
                                                     for m in plan["marriage"]["misses"]):
        assert any(i["label"] == "The Mermaid's Pendant" and not i["this_year"] for _, i in items)
    assert [g["id"] for g in v["goals"]] == ALL[0] + ALL[1]
    assert v["days_left"] == v["days"]["left"]


def test_needs_endpoint(fresh):
    from fastapi.testclient import TestClient

    from valley_planner.app import create_app
    client = TestClient(create_app())
    v = client.post("/api/needs", json={"targets": ["greenhouse"], "nice": ["cc"], "start": "fresh"}).json()
    assert {"today", "end", "days_left", "goals", "resources", "days", "choices"} <= set(v)
    assert [r["id"] for r in v["resources"][:4]] == ["gold", "wood", "stone", "hardwood"]
    _check(v)
    assert any(o["planned"] for c in v["choices"] for o in c["options"])


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_a_picked_way_is_planned():
    """Picking another way for an item plans with it: the choice shows it ticked, and its chain's gold goes."""
    from valley_planner.engine.route.needs import needs
    from valley_planner.engine.route.plan import Settings
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    base = needs(farm, ["greenhouse"], [], settings=Settings(tiles=80), cave="bats")
    choice = next(c for c in base["choices"] if any(o.get("pick") and not o.get("planned") for o in c["options"]))
    other = next(o for o in choice["options"] if o.get("pick") and not o.get("planned"))
    v = needs(farm, ["greenhouse"], [], settings=Settings(tiles=80, picks={choice["item"]: other["pick"]}), cave="bats")
    after = next(c for c in v["choices"] if c["item"] == choice["item"])
    assert after["picked"] == other["pick"]
    assert next(o for o in after["options"] if o.get("pick") == other["pick"])["planned"]
