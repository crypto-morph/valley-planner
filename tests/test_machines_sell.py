"""Machines (rules, flavored prices, timing) and sale prices — small fake data, plus the real game."""

import pytest

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
    from valley_planner.gamedata import GameData
    m = Machines(GameData(GAME))
    cases = {("(BC)12", "(O)258"): ("(O)348", 150, 10000), ("(BC)12", "(O)262"): ("(O)346", 200, 1750),
             ("(BC)15", "(O)24"): ("(O)342", 120, 4000), ("(BC)24", "(O)180"): ("(O)306", 190, 180),
             ("(BC)16", "(O)184"): ("(O)424", 230, 200), ("(BC)17", "(O)440"): ("(O)428", 470, 240)}
    for (machine, item), want in cases.items():
        o = m.output(machine, Input(item))
        assert (o.item, o.price, o.minutes) == want, (machine, item)
    assert m.output("(BC)24", Input("(O)174")).quality == 2  # large egg: gold mayonnaise
    seed = m.output("(BC)25", Input("(O)24"))
    assert (seed.item, seed.stack, seed.minutes) == ("(O)472", (1, 3), 20)
