"""Machines (rules, flavored prices, timing) and sale prices — small fake data, plus the real game."""

import pytest
from shared import shared_data

from valley_planner.discover import find_game
from valley_planner.facts.machines import Input, Machines, flavored_price, minutes_until_morning, ready_at
from valley_planner.facts.sell import Farmer, sell_price

OBJECTS = {
    "258": {"Name": "Blueberry", "Price": 50, "Category": -79, "Type": "Basic"},
    "262": {"Name": "Wheat", "Price": 25, "Category": -75, "Type": "Basic"},
    "348": {"Name": "Wine", "Price": 400, "Category": -26},
    "346": {"Name": "Beer", "Price": 200, "Category": -26},
    "306": {"Name": "Mayonnaise", "Price": 190, "Category": -26},
    "174": {"Name": "Large Egg", "Price": 95, "Category": -5, "ContextTags": ["egg_item", "large_egg_item"]},
    "176": {"Name": "Egg", "Price": 50, "Category": -5, "ContextTags": ["egg_item"]},
}
KEG = {"OutputRules": [
    {"Id": "Wheat", "Triggers": [{"Trigger": "ItemPlacedInMachine", "RequiredItemId": "(O)262", "RequiredCount": 1}],
     "OutputItem": [{"ItemId": "(O)346"}], "MinutesUntilReady": 1750},
    {"Id": "Wine", "Triggers": [{"Trigger": "ItemPlacedInMachine", "RequiredTags": ["category_fruits"], "RequiredCount": 1}],
     "OutputItem": [{"ItemId": "FLAVORED_ITEM Wine DROP_IN_ID"}], "MinutesUntilReady": 10000}]}
MAYO = {"OutputRules": [
    {"Id": "Large", "Triggers": [{"Trigger": "ItemPlacedInMachine", "RequiredTags": ["large_egg_item", "egg_item"]}],
     "OutputItem": [{"ItemId": "(O)306", "Quality": 2}], "MinutesUntilReady": 180},
    {"Id": "Egg", "Triggers": [{"Trigger": "ItemPlacedInMachine", "RequiredTags": ["egg_item", "!large_egg_item"]}],
     "OutputItem": [{"ItemId": "(O)306"}], "MinutesUntilReady": 180}],
    "ReadyTimeModifiers": [{"Condition": "PLAYER_HAS_PROFESSION Target 2", "Modification": "Multiply", "Amount": 0.5}]}


class Data:
    tables = {"Data/Objects": OBJECTS, "Data/Machines": {"(BC)12": KEG, "(BC)24": MAYO}, "Data/Crops": {}}

    def asset(self, name):
        return self.tables[name]


def test_rules_in_order_tags_and_flavors():
    m = Machines(Data())
    beer = m.output("(BC)12", Input("(O)262"))
    assert (beer.item, beer.price, beer.minutes) == ("(O)346", 200, 1750)  # the specific rule comes first
    wine = m.output("(BC)12", Input("(O)258"))
    assert (wine.item, wine.price, wine.preserved_id, wine.name) == ("(O)348", 150, "258", "Blueberry Wine")
    assert m.output("(BC)12", Input("(O)174")) is None
    gold = m.output("(BC)24", Input("(O)174"))
    plain = m.output("(BC)24", Input("(O)176"))
    assert (gold.quality, plain.quality) == (2, 0)
    assert m.output("(BC)24", Input("(O)176"), professions={2}).minutes == 90  # Coopmaster-style modifier
    assert not m.output("(BC)24", Input("(O)176")).sure  # can't tell the profession: unsure


def test_flavored_prices():
    assert [flavored_price(k, 50) for k in ("Wine", "Juice", "Jelly", "Pickle", "SmokedFish", "Bait")] == \
        [150, 112, 150, 150, 100, 5]
    assert flavored_price("Honey", 30, base_price=100) == 160 and flavored_price("Roe", 75) == 67
    assert flavored_price("AgedRoe", 75) == 134 and flavored_price("DriedFruit", 50) == 400


def test_machine_clock():
    assert minutes_until_morning(600) == 1600 and minutes_until_morning(2200) == 640
    assert ready_at(600, 10000) == (6, 1240)  # wine: 6 days and 400 minutes
    assert ready_at(600, 6000) == (3, 2600)  # juice: 2 AM on the third night
    assert ready_at(600, 4000) == (2, 1920)  # jelly and pickles
    assert ready_at(2300, 180) == (0, 2600) and ready_at(2330, 180) == (1, 600)  # 2 AM, or overnight
    assert ready_at(900, 30, overnight_only=True) == (1, 600)


def test_sell_prices():
    nobody, tiller = Farmer(), Farmer(professions={1})
    assert sell_price(50, 0, nobody, "(O)258", "Blueberry", -79) == 50
    assert sell_price(50, 2, nobody, "(O)258", "Blueberry", -79) == 75
    assert sell_price(50, 0, tiller, "(O)258", "Blueberry", -79) == 55
    assert sell_price(50, 0, tiller, "(O)258", "Blueberry", -79, spawned=True) == 50  # foraged fruit
    artisan_rancher = Farmer(professions={0, 4})
    assert sell_price(190, 0, artisan_rancher, "(O)306", "Mayonnaise", -26) == 319  # 190 x 1.2 x 1.4
    assert sell_price(80, 0, Farmer(professions={6, 8}), "(O)145", "Sunfish", -4) == 120
    assert sell_price(100, 0, nobody, "(O)24", "Parsnip", -75, profit_margin=0.25) == 25
    assert sell_price(10, 0, nobody, "(O)493", "Cranberry Seeds", -74) == 5
    assert sell_price(1, 0, nobody, "(O)1", "Thing", -75, profit_margin=0.25) == 1  # never below 1


GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_machines():
    m = Machines(shared_data())
    cases = {("(BC)12", "(O)258"): ("(O)348", 150, 10000), ("(BC)12", "(O)262"): ("(O)346", 200, 1750),
             ("(BC)15", "(O)24"): ("(O)342", 120, 4000), ("(BC)24", "(O)180"): ("(O)306", 190, 180),
             ("(BC)16", "(O)184"): ("(O)424", 230, 200), ("(BC)17", "(O)440"): ("(O)428", 470, 240)}
    for (machine, item), want in cases.items():
        o = m.output(machine, Input(item))
        assert (o.item, o.price, o.minutes) == want, (machine, item)
    assert m.output("(BC)24", Input("(O)174")).quality == 2  # large egg: gold mayonnaise
    seed = m.output("(BC)25", Input("(O)24"))
    assert (seed.item, seed.stack, seed.minutes) == ("(O)472", (1, 3), 20)


def test_a_machine_is_free_today_if_empty_or_done_before_the_day_ends(monkeypatch):
    from types import SimpleNamespace

    from valley_planner.views import sell
    monkeypatch.setattr(sell, "_machine_id", lambda _f, name: name)
    work = [{"name": "Preserves Jar", "holds": "Blackberry Jelly", "minutes": 190, "ready": False},
            {"name": "Keg", "holds": "Wine", "minutes": 9000, "ready": False},
            {"name": "Furnace", "holds": "", "minutes": 0, "ready": False}]
    free, busy = sell._free_today(SimpleNamespace(save=SimpleNamespace(machine_work=work, machines={})))
    assert free == {"Preserves Jar": 1, "Furnace": 1}  # the Keg's Wine takes days
    assert busy[0] == {"machine": "Preserves Jar", "holds": "Blackberry Jelly", "ready": False, "at": "9:10 AM",
                       "days": 0}
    assert busy[1]["days"] == 7 and busy[1]["at"] == ""


def test_the_machines_note_says_what_to_take_out_first():
    from valley_planner.views.today import machines_note
    assert machines_note({"process": []}) is None
    n = machines_note({"process": [{"name": "Cave Carrot", "count": 1, "machine": "Preserves Jar", "gain": 75}],
                       "machines": [{"machine": "Preserves Jar", "holds": "Blackberry Jelly", "ready": False,
                                     "at": "9:10 AM", "days": 0}]})
    assert n["text"] == ("Machines: 1 Cave Carrot in the Preserves Jar (take out the Blackberry Jelly first: ready "
                         "about 9:10 AM).")


def test_what_a_machine_improves_waits_for_it_up_to_what_it_gets_through(monkeypatch):
    from types import SimpleNamespace

    from valley_planner.views import sell
    jar = SimpleNamespace(uses=1, minutes=4000, days=0, name="Pickles")
    monkeypatch.setattr(sell, "_machine_id", lambda _f, name: name)
    monkeypatch.setattr(sell, "_machine_name", lambda _f, mid: mid)
    monkeypatch.setattr(sell, "_best_output", lambda *a, **k: ("Preserves Jar", 66, jar, 66))
    monkeypatch.setattr(sell, "item_sell_price", lambda it, *a, **k: 8)
    farm = SimpleNamespace(save=SimpleNamespace(machines={"Preserves Jar": 1}, profit_margin=1), farmer=None)
    onions = sell._Stack(SimpleNamespace(quality=0), 40)
    out = sell._queue(farm, [("(O)399", onions)], lambda q, it: True, None, {}, {})
    assert out == [("(O)399", (0, 10, 80), "the Preserves Jar when it's free: Pickles, +58g each", 58)]
    assert onions.left == 30  # one jar gets through 10 loads in 4 weeks; the rest can be sold


def test_short_of_cash_lets_go_only_what_covers_the_gap_last_rule_first(monkeypatch):
    from types import SimpleNamespace

    from valley_planner.views import sell
    monkeypatch.setattr(sell, "item_sell_price", lambda it, *a, **k: it.price)
    farm = SimpleNamespace(save=SimpleNamespace(profit_margin=1), farmer=None, name=lambda q: q)
    monkeypatch.setattr(sell, "QUALITY_WORD", {0: ""})
    onion = sell._Stack(SimpleNamespace(quality=0, price=8), 0)
    carrot = sell._Stack(SimpleNamespace(quality=0, price=25), 0)
    ruby = sell._Stack(SimpleNamespace(quality=0, price=250), 0)
    junk = sell._Stack(SimpleNamespace(quality=0, price=10), 2)  # free to sell: 20g
    stacks = [("onion", onion), ("carrot", carrot), ("ruby", ruby), ("junk", junk)]
    keep = {("onion", 0, "jar"): 10, ("carrot", 0, "jar"): 2, ("ruby", 0, "gift"): 1}
    kept_by = {"machines": {"count": 12, "value": 130}, "loved": {"count": 1, "value": 250},
               "bundles": {"count": 0, "value": 0}}
    holds = [(7, "loved", "ruby", 0, 1, "gift", 250, 0),
             (9, "machines", "carrot", 0, 2, "jar", 25, 54), (9, "machines", "onion", 0, 10, "jar", 8, 58)]
    out = sell._let_go(farm, 90, holds, stacks, lambda q, it: True, keep, kept_by,
                       {"loved": "off", "machines": "off", "bundles": "always"})
    # 70g to find: the machines' queue goes first, the smallest gain first (carrots), then onions; the gift stays
    assert [(x["name"], x["count"]) for x in out["let_go"]] == [("carrot", 2), ("onion", 3)]
    assert out["still_short"] == 0 and carrot.left == 2 and onion.left == 3 and ruby.left == 0
    assert keep == {("onion", 0, "jar"): 7, ("ruby", 0, "gift"): 1}


def test_plenty_of_cash_lets_nothing_go():
    from valley_planner.views import sell
    assert sell._let_go(None, 0, [], [], None, {}, {}, {}) is None
