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


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_new_goals_fresh():
    """Each new goal plans on a fresh farm, or says clearly why it can't."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    for g in ("deluxe_barn", "deluxe_coop", "silo", "axe_steel", "pickaxe_steel", "can_steel", "mines_bottom",
              "skull_cavern", "jars", "kegs", "house_3"):
        o = route(farm, [g], [], tiles=80, cave="bats")["objectives"][0]
        assert o["status"] == "ok" or (o["problems"] and all(": " in p for p in o["problems"])), (g, o)
        if o["status"] == "ok":
            assert o["steps"] and o["finish"], g
    house = route(farm, ["house_3"], [], tiles=80, cave="bats")["objectives"][0]
    assert house["status"] == "impossible" and "short" in house["problems"][0]  # 175,000g of upgrades in Year 1
    barn = route(farm, ["deluxe_barn"], [], tiles=80, cave="bats")["objectives"][0]
    assert [n["label"] for n in barn["steps"][0]["needs"]] == ["build a Barn", "build a Big Barn",
                                                                "build a Deluxe Barn"]
    assert any("Stone" in i for i in barn["info"])  # what isn't priced is said, not dropped


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_tool_level_from_save():
    """Tool chains start from the save's own levels: a Copper Pickaxe needs only the Steel step."""
    from valley_planner.engine.route.start import new_farm
    from valley_planner.engine.unlocks import Unlocks
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    farm.save.tool_levels = {**farm.save.tool_levels, "Pickaxe": 1, "WateringCan": 2}
    u = Unlocks(farm)
    assert [x.label for x in u.chain("tool:Pickaxe@2")] == ["a Steel Pickaxe from Clint"]
    assert u.get("tool:WateringCan@2").done and not u.get("tool:Axe@1").done
    steel = u.get("tool:Pickaxe@2")
    assert steel.gold == 5000 and steel.materials == [("335", 5)] and steel.days == 2


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_cellar_after_second_upgrade():
    from valley_planner.engine.route.start import new_farm
    from valley_planner.engine.unlocks import Unlocks
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    assert [x.key for x in Unlocks(farm).chain("house:3")] == ["kitchen", "house:2", "house:3"]
    farm.save.house_upgrade = 2
    cellar = Unlocks(farm).chain("house:3")
    assert [x.key for x in cellar] == ["house:3"] and cellar[0].gold == 100000 and not cellar[0].materials


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_kegs_wait_for_oak_resin():
    """Kegs need an Oak Resin each: Tappers on oaks first, a week a round, and the Kegs wait for it."""
    from valley_planner.engine.route.plan import Settings, route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    v = route(farm, ["kegs"], [], settings=Settings(kegs=10, tappers=5), tiles=80, cave="bats")
    o = v["objectives"][0]
    assert o["status"] == "ok"
    resin, kegs = o["steps"]
    assert resin["what"] == "10 Oak Resin" and kegs["what"] == "10 Kegs"
    tap = next(n for n in resin["needs"] if n["key"] == "tap:oak")
    assert "5 oak trees" in tap["label"] and tap["state"] == "new"
    assert resin["n"] + 14 <= next(c["day"] for c in v["cash"] if farm.label(c["day"]) == resin["ready"])
    assert any(n["key"] == "tap:oak" and n["state"] == "earlier" for n in kegs["needs"])
    assert kegs["n"] >= next(c["day"] for c in v["cash"] if farm.label(c["day"]) == resin["ready"])
    assert any("Foraging level 4" in i for i in o["info"])  # the Tapper recipe's skill isn't modelled: said so


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_skull_cavern_needs_the_vault():
    """The bus to the Desert needs the Vault: without its gold by the deadline the Skull Cavern can't be planned;
    with the Community Center planned first, the Vault is shared, not paid twice."""
    from valley_planner.engine.route.plan import route
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    farm = new_farm(GameData(GAME))
    o = route(farm, ["skull_cavern"], [], deadlines={"skull_cavern": 40}, tiles=80, cave="bats")["objectives"][0]
    assert o["status"] == "impossible" and any("Vault" in p for p in o["problems"])
    assert any("Vault" in i for i in o["info"])
    alone = route(farm, ["skull_cavern"], [], tiles=80, cave="bats")["objectives"][0]
    assert alone["status"] == "ok" and alone["steps"][0]["what"].startswith("pay the Vault")
    v = route(farm, ["skull_cavern"], ["cc"], tiles=80, cave="bats")
    sc, cc = v["objectives"]
    assert [st for st in cc["steps"] if st["what"].startswith("pay the Vault") and st["shared"] == "The Skull Cavern"]
    assert not [st for st in cc["steps"] if st["what"].startswith("pay the Vault") and not st["shared"]]


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_new_goals_done_from_save():
    """Placed machines and ones in chests both count; the Skull Key's mail or floor 120 is the Mines' bottom."""
    from valley_planner.engine.route.plan import Router
    from valley_planner.engine.route.start import new_farm
    from valley_planner.gamedata import GameData
    from valley_planner.save import Item
    farm = new_farm(GameData(GAME))
    farm.save.machines["Keg"] = 6
    farm.save.items.append(Item(id="12", name="Keg", stack=4, quality=0, where="Farm chest", big=True))
    farm.save.mail.add("HasSkullKey")
    farm.save.buildings["Deluxe Coop"] = 1
    r = Router(farm)
    assert r.machines("12") == 10 and r.done("kegs") and not r.done("jars")
    assert r.done("mines_bottom") and not r.done("skull_cavern") and r.done("deluxe_coop") and not r.done("silo")


def test_fruit_tree_schedule():
    """A tree grown overnight fruits that same night in season; out of season it waits for its season."""
    from valley_planner.facts.trees import schedule
    fall25 = 2 * 28 + 25
    apple = schedule(fall25, 1, ["fall"])
    assert apple["grown"] == apple["first"] == fall25 + 1 and apple["fruit_by"] == 3
    pom = schedule(fall25, 15, ["fall"])  # grown in winter: first fruit next Fall 1
    assert pom["grown"] == fall25 + 15 and pom["first"] == 112 + 2 * 28 + 1
    assert schedule(fall25, 0, ["fall"], on_tree=2)["first"] == fall25
    assert schedule(fall25, 3, ["spring"], indoor=True)["first"] == fall25 + 3
