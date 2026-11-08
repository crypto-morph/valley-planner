"""The Bookseller: his visit days and his seeded stock, on small fake shops plus the real game when it's here."""

import pytest
from shared import shared_data

from valley_planner.discover import find_game
from valley_planner.facts.bookseller import Bookseller, visit_days, visits
from valley_planner.facts.conditions import When
from valley_planner.facts.rng import NetRandom, day_save_random, random_seed

GAME_ID = 452453427
SKILL = ["(O)SkillBook_0", "(O)SkillBook_1", "(O)SkillBook_2", "(O)SkillBook_3", "(O)SkillBook_4"]


def test_visit_days_follow_the_seeded_pick():
    spring = (11, 12, 21, 22, 25)
    i = NetRandom(random_seed(2 * 11, GAME_ID, 0)).next(5)
    assert visit_days(GAME_ID, 2, "spring") == tuple(sorted((spring[i], spring[(i + 2) % 5])))
    for season in ("spring", "summer", "fall", "winter"):
        a, b = visit_days(GAME_ID, 1, season)
        assert a < b
    assert len(visits(GAME_ID, 1, 112)) == 8  # two a season


class Data:
    def __init__(self, items, trades=()):
        self.tables = {"Data/Shops": {"Bookseller": {"Items": list(items)}, "BooksellerTrade": {"Items": list(trades)}},
                       "Data/Objects": {}, "Data/BigCraftables": {}}

    def asset(self, name):
        return self.tables[name]

    def text(self, value):
        return value


def entry(i, **kw):
    return {"Id": i, "Price": 1000, "AvailableStock": 1, **kw}


def test_avoid_repeat_picks_among_the_rest():
    shop = Data([entry("A", RandomItemId=SKILL), entry("B", RandomItemId=SKILL, AvoidRepeat=True),
                 entry("C", RandomItemId=SKILL, AvoidRepeat=True), entry("D", ItemId="(O)Book_Speed", Price=15000)])
    w = When("summer", 12, 2, 152, game_id=GAME_ID)
    got = [i.item for i in Bookseller(shop).day(w).items]
    r = day_save_random(152, GAME_ID)
    first = SKILL[r.next(5)]
    rest = [s for s in SKILL if s != first]
    second = rest[r.next(4)]
    rest.remove(second)
    assert got == [first, second, rest[r.next(3)], "(O)Book_Speed"]
    assert len(set(got)) == 4


def test_player_conditions_are_maybe_later_and_doubt_later_rolls():
    shop = Data([entry("Speed2", ItemId="(O)Book_Speed2", Condition="PLAYER_STAT Current Book_Speed 1"),
                 entry("Maybe", RandomItemId=SKILL, Condition="PLAYER_STAT Current Book_Horse 1"),
                 entry("After", RandomItemId=SKILL)])
    w = When("summer", 12, 2, 152, game_id=GAME_ID)
    today = Bookseller(shop).day(w, {"Book_Speed": 1}, today=True).items
    assert [i.entry for i in today] == ["Speed2", "After"] and all(i.sure for i in today)
    later = Bookseller(shop).day(w, {}, today=False).items
    assert [(i.entry, i.sure) for i in later] == [("Speed2", False), ("Maybe", False), ("After", False)]


def test_trades_cost_a_book_not_money():
    shop = Data([], [{"Id": "J", "RandomItemId": ["(O)CaveJelly", "(O)RiverJelly"], "MinStack": 3,
                      "TradeItemId": "Book_Roe", "TradeItemAmount": 1, "Condition": "PLAYER_STAT Current Book_Roe 1"}])
    w = When("summer", 12, 2, 152, game_id=GAME_ID, mail={"read_a_book"})
    d = Bookseller(shop).day(w, {"Book_Roe": 1})
    (t,) = d.trades
    assert d.trade_open and (t.price, t.stack, t.trade_item, t.trade_amount) == (0, 3, "(O)Book_Roe", 1)


GAME = find_game()


@pytest.mark.game
@pytest.mark.skipif(GAME is None, reason="Stardew Valley isn't installed here")
def test_real_shop_reads():
    data = shared_data()
    w = When("summer", 12, 2, 152, game_id=GAME_ID, world_fields={"GoldenWalnutsFound": 0})
    d = Bookseller(data).day(w, {}, today=True)
    names = [i.name for i in d.items]
    assert "Price Catalogue" in names and "Queen Of Sauce Cookbook" not in names
    skill = [i for i in d.items if i.entry.startswith("RandomSkillBook")]
    assert len({i.item for i in skill if i.entry != "RandomSkillBook1"}) == len(
        [i for i in skill if i.entry != "RandomSkillBook1"])  # AvoidRepeat keeps 2nd and 3rd apart
    assert all(i.sure for i in d.items) and not d.trade_open
