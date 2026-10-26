"""The game's random numbers and the Traveling Cart: known values, small fake shops, plus the real game."""

import pytest

from valley_planner.discover import find_game
from valley_planner.facts.cart import Cart
from valley_planner.facts.conditions import When, check, date_of
from valley_planner.facts.rng import NetRandom, random_seed, xxhash32


def test_net_random_matches_dotnet():
    r = NetRandom(12345)  # values from .NET's System.Random(12345)
    assert (r.next(), r.next(10), r.next_double(), r.next(3, 6)) == (143337951, 0, 0.7747651351498278, 4)


def test_xxhash32_reference_vectors():
    assert xxhash32(b"") & 0xFFFFFFFF == 0x02CC5D05
    assert xxhash32(b"abc") & 0xFFFFFFFF == 0x32D153FF
    assert xxhash32(b"Nobody inspects the spammish repetition") & 0xFFFFFFFF == 0xE2293B2F


def test_seed_keeps_sign_and_legacy_adds():
    assert random_seed(1, 2, legacy=True) == 3
    assert random_seed(-5, legacy=True) == -5  # modulo keeps the sign, like C#
    assert random_seed(-5) != random_seed(5)


def test_synced_random_condition_needs_the_game_id():
    w = When("fall", 5, 1, 61)
    assert check("SYNCED_RANDOM day cart_rarecrow 0.4", w) is None
    w.game_id = 452453427
    assert check("SYNCED_RANDOM day cart_rarecrow 0.4", w) in (True, False)
    assert check("SYNCED_RANDOM tick x 0.5", w) is None
    w.world_fields = {"VisitsUntilY1Guarantee": 0}
    assert check("WORLD_STATE_FIELD VisitsUntilY1Guarantee 0 0", w) is True


class Data:
    def __init__(self, **tables):
        self.tables = {"Data/Furniture": {}, "Data/BigCraftables": {}, "Data/PassiveFestivals": {
            "NightMarket": {"Season": "Winter", "StartDay": 15, "EndDay": 17, "Condition": ""}}, **tables}

    def asset(self, name):
        return self.tables[name]

    def text(self, value):
        return value


OBJECTS = {str(i): {"Name": f"Thing {i}", "Price": 10 * i, "Category": -75, "Type": "Basic"} for i in range(2, 40)}
OBJECTS["5"] = {"Name": "Quest thing", "Price": 50, "Category": -75, "Type": "Quest"}
OBJECTS["7"] = {"Name": "Litter", "Price": 0, "Category": -999, "Type": "Litter"}
OBJECTS["9"] = {"Name": "Hidden", "Price": 90, "Category": -75, "Type": "Basic", "ExcludeFromRandomSale": True}
OBJECTS["11"] = {"Name": "No category", "Price": 90, "Category": 0, "Type": "Basic"}
RANDOM = {"Id": "RandomObjects", "ItemId": "RANDOM_ITEMS (O) 2 30 @requirePrice @isRandomSale", "MaxItems": 4,
          "PerItemCondition": "ITEM_HAS_EXPLICIT_OBJECT_CATEGORY Target, !ITEM_CATEGORY Target -999, "
                              "!ITEM_OBJECT_TYPE Target Quest Minerals Arch",
          "AvailableStock": 1, "AvoidRepeat": True, "UseObjectDataPrice": True, "PriceModifierMode": "Maximum",
          "PriceModifiers": [{"Modification": "Set", "RandomAmount": [100.0, 200.0]},
                             {"Modification": "Multiply", "RandomAmount": [3.0, 4.0]}],
          "AvailableStockModifiers": [{"Condition": "RANDOM 0.5", "Modification": "Set", "Amount": 5.0}]}
GUARANTEED = {"Id": "(O)20", "ItemId": "(O)20", "Price": 1000, "AvailableStock": 1,
              "Condition": "WORLD_STATE_FIELD VisitsUntilY1Guarantee 0 0"}


def shuffled(seed_days, game_id):
    """The game's rule, by hand: one Next() per object in data order, stable sort, then filter."""
    from valley_planner.facts.rng import day_save_random
    r = day_save_random(seed_days, game_id)
    keyed = sorted(((r.next(), oid) for oid in OBJECTS), key=lambda k: k[0])
    keep = [oid for _, oid in keyed if 2 <= int(oid) <= 30 and oid not in ("5", "7", "9", "11")][:4]
    rolls = [((100, 200)[r.next(2)], (3, 4)[r.next(2)], r.next_double() < 0.5) for _ in keep]
    return [(f"(O){oid}", max(a, OBJECTS[oid]["Price"] * m), 5 if five else 1)
            for oid, (a, m, five) in zip(keep, rolls, strict=True)]


def test_random_objects_follow_the_game_order():
    cart = Cart(Data(**{"Data/Objects": OBJECTS, "Data/Shops": {"Traveler": {"Items": [RANDOM]}}}))
    w = When("fall", 5, 1, 61, game_id=452453427)
    got = [(i.item, i.price, i.stock) for i in cart.stock(w)]
    assert got == shuffled(61, 452453427)


def test_an_undecidable_entry_is_left_out_and_casts_doubt():
    unknown = {**RANDOM, "Id": "Maybe", "Condition": "PLAYER_HAS_ITEM Current 74", "MaxItems": 1}
    cart = Cart(Data(**{"Data/Objects": OBJECTS, "Data/Shops": {"Traveler": {"Items": [unknown, GUARANTEED]}}}))
    w = When("fall", 5, 1, 61, game_id=1, world_fields={"VisitsUntilY1Guarantee": 0})
    (only,) = cart.stock(w)
    assert only.item == "(O)20" and only.sure is False


def test_guarantee_counts_down_on_cart_and_night_market_days():
    cart = Cart(Data(**{"Data/Objects": OBJECTS, "Data/Shops": {"Traveler": {"Items": [GUARANTEED]}}}))
    w = When("winter", 13, 1, 97, game_id=1)  # Winter 13: today isn't a cart day
    days = list(cart.days(w, count_days=8, guarantee=2))
    assert [(d.day, d.place) for d in days] == [(14, "Forest"), (15, "NightMarket"), (16, "NightMarket"),
                                                (17, "NightMarket"), (19, "Forest")]
    assert [d.day for d in days if d.items] == [15]  # 2 -> 1 on the 14th, 0 on the 15th
    assert date_of(97) == ("winter", 13, 1)


GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_cart_seen_in_a_game():
    """A cart a player saw in 1.6.15 (game id 452453427, Fall 5 Year 1), item for item."""
    from valley_planner.gamedata import GameData
    data = GameData(GAME)
    if not data.version.startswith("1.6.15"):
        pytest.skip("observed on 1.6.15")
    w = When("fall", 5, 1, 61, game_id=452453427, world_fields={"VisitsUntilY1Guarantee": -1})
    got = [(i.name, i.price, i.stock) for i in Cart(data).stock(w)]
    assert got == [("Cauliflower Seeds", 300, 1), ("Clam", 400, 1), ("Spaghetti", 360, 1), ("Mussel", 400, 1),
                   ("Chub", 800, 1), ("Copper Bar", 600, 1), ("Cheese Cauliflower", 1500, 5),
                   ("Eggplant Parmesan", 800, 1), ("Stuffing", 800, 1), ("Escargot", 800, 1),
                   ("'Spires'", 250, 1), ("Rarecrow", 4000, 1)]
