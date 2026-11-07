"""Lewis's Special Orders board: the dealing rule on its own, then against real saves (when the game is here)."""

from types import SimpleNamespace

import pytest

from valley_planner.facts import special_orders as so
from valley_planner.facts.conditions import When

ANTROPIC = 453557957
MCCLARKIES = 452453427
TOWN_ORDERS = ["Willy", "Pam", "Pierre", "Robin", "Emily", "Demetrius", "Demetrius2", "Gus", "Lewis", "Wizard", "Clint",
               "Linus", "Evelyn", "Wizard2", "Robin2", "Gunther", "Caroline", "Willy2"]


# --- the rule, no game needed --------------------------------------------------------------


def test_board_days_are_the_mondays():
    assert [d for d in range(1, 57) if so.is_board_day(d)] == [1, 8, 15, 22, 29, 36, 43, 50]
    assert so.last_board_day(22) == 22 and so.last_board_day(28) == 22 and so.last_board_day(29) == 29
    assert so.board_days(22, 3) == [29, 36, 43]
    assert so.board_days(21, 2) == [22, 29]


def test_due_dates_follow_set_duration():
    # McClarkies, Year 2: Emily (a week) dealt Spring 22 is due on TotalDays 140, Lewis (a month) too
    assert so.due_date(134, "Week") == 140
    assert so.due_date(113, "Month") == 140
    assert so.due_date(64, "TwoWeeks") == 77  # Fall 8, Year 1: up to Fall 21
    # a week-long order taken is still "taken" when the next Monday's board is dealt
    assert so.taken_at(140, 141) and not so.taken_at(140, 148)


def test_the_board_is_open_from_fall_2():
    assert not so.Board(50, ()).visible
    assert so.Board(57, ()).visible and so.Board(57, ()).opens == 58
    assert so.Board(64, ()).opens == 64


def eligible(out=(), list2=()):
    first = [k for k in TOWN_ORDERS if k not in out and k not in list2]
    return first, [k for k in TOWN_ORDERS if k not in out]


def test_deal_matches_a_saved_board():
    # Antropic, Spring 22 Year 1: month orders are out from day 16, Emily's event not seen, no island
    samples = so.board_samples(ANTROPIC, 22)
    first, refill = eligible(out={"Pierre", "Lewis", "Evelyn", "Emily", "Caroline", "Willy2"})
    assert so.deal(samples, first, refill) == [("Wizard2", 1195795682), ("Robin", 8944944)]


def test_deal_drops_completed_and_taken_orders():
    # McClarkies, Spring 22 Year 2: Wizard and Wizard2 done, Clint (repeatable) done, Lewis taken,
    # and one more order from the week before still taken; only that history gives the saved board
    samples = so.board_samples(MCCLARKIES, 134)
    out = {"Pierre", "Lewis", "Evelyn", "Caroline", "Willy2", "Wizard", "Wizard2"}
    assert so.deal(samples, *eligible(out=out | {"Robin"}, list2={"Clint"})) == [
        ("Emily", 246246335), ("Robin2", 1461851638)]
    assert so.deal(samples, *eligible(out=out, list2={"Clint"}))[0][0] != "Emily"


def test_deal_refills_from_the_completed_repeatables():
    samples = [0, 11, 0, 22]
    assert so.deal(samples, [], ["Clint", "Gus"]) == [("Clint", 11), ("Gus", 22)]
    assert so.deal(samples, ["Robin"], ["Robin", "Clint"]) == [("Robin", 11), ("Clint", 22)]
    assert so.deal(samples, [], []) == []


def test_tags_in_three_values():
    w = When(season="summer", day=8, year=1, days_played=36, events_seen={"992559"}, mail={"gusGiantOmelet"},
             hearts={"Emily": 2})
    kw = {"completed": frozenset({"Wizard"}), "maybe_completed": {"Robin"}, "can_reach_island": False}
    assert so.check_tags("season_summer, event_992559", w, **kw) is True
    assert so.check_tags("!season_winter", w, **kw) is True
    assert so.check_tags("season_spring, event_1", w, **kw) is False  # a definite no wins over a maybe
    assert so.check_tags("event_1", w, **kw) is None  # not seen yet, could be
    assert so.check_tags("!mail_gusGiantOmelet", w, **kw) is False
    assert so.check_tags("island", w, **kw) is False
    assert so.check_tags("island", w, **{**kw, "can_reach_island": True}) is None
    assert so.check_tags("completed_Wizard", w, **kw) is True
    assert so.check_tags("completed_Robin", w, **kw) is None
    assert so.check_tags("completed_Gus", w, **kw) is False
    assert so.check_tags("knows_Emily", w, **kw) is True
    assert so.check_tags("NOT_IMPLEMENTED", w, **kw) is False
    assert so.check_tags("", w, **kw) is True


def test_order_state_reads_the_save(tmp_path):
    xml = ("<SaveGame><availableSpecialOrders><SpecialOrder><generationSeed>42</generationSeed><questKey>Robin"
           "</questKey><orderType /></SpecialOrder><SpecialOrder><generationSeed>-7</generationSeed><questKey>"
           "QiChallenge5</questKey><orderType>Qi</orderType></SpecialOrder></availableSpecialOrders>"
           "<completedSpecialOrders><string>Wizard</string><string>Clint</string></completedSpecialOrders>"
           "<acceptedSpecialOrderTypes><string /></acceptedSpecialOrderTypes></SaveGame>")
    path = tmp_path / "Farm_1"
    path.write_text(xml, encoding="utf-8")
    state = so.order_state(SimpleNamespace(path=path, mtime=path.stat().st_mtime))
    assert state.completed == {"Wizard", "Clint"}
    assert state.accepted_this_week
    assert state.board == (("Robin", 42),)


# --- against the game and real saves ------------------------------------------------------


@pytest.fixture(scope="module")
def data():
    from valley_planner.app import Planner
    try:
        return Planner(None).data
    except RuntimeError:
        pytest.skip("no game here")


@pytest.fixture(scope="module")
def saves(data):
    """Every 1.6.15 save file here (current and _old), read."""
    from valley_planner.discover import find_saves_root
    from valley_planner.save import read_save
    root = find_saves_root()
    if root is None:
        pytest.skip("no saves here")
    out = {}
    for folder in root.iterdir():
        for path in (folder / folder.name, folder / f"{folder.name}_old"):
            if not path.is_file():
                continue
            try:
                save = read_save(path, data)
            except Exception:  # noqa: BLE001 — someone else's odd file isn't this test's business
                continue
            if save.game_version == "1.6.15":
                out[path.name] = save
    if not out:
        pytest.skip("no 1.6.15 saves here")
    return out


def test_this_week_matches_the_saved_board(data, saves):
    """Where nothing's been done with orders (so the save still holds what the board was dealt from)."""
    checked = 0
    for name, save in saves.items():
        state = so.order_state(save)
        if state.completed or save.special_orders or not state.board:
            continue
        board = so.this_week(save, data)
        assert [(o.key, o.seed) for o in board.orders] == list(state.board), name
        town = [o for o in save.special_orders_board if not o["type"]]  # Save's list holds Qi's orders too
        for order, saved in zip(board.orders, town, strict=True):
            assert order.reward == saved["money"], (name, order.key)
            assert order.last_day == saved["due_date"], (name, order.key)
            assert order.requirement and "[" not in order.requirement and "{" not in order.requirement
        checked += 1
    if not checked:
        pytest.skip("no save without order history")


def test_a_sure_forecast_comes_true(data, saves):
    """A save's _old copy, a Monday earlier: what it was sure of is on the newer save's board."""
    checked = 0
    for name, newer in saves.items():
        older = saves.get(f"{name}_old")
        if older is None or so.last_board_day(newer.days_played) <= older.days_played:
            continue
        upcoming = so.forecast(older, data, mondays=1)[0]
        assert upcoming.days_played == so.last_board_day(newer.days_played)
        saved = so.order_state(newer).board
        for slot, order in enumerate(upcoming.orders):
            if order.sure:
                assert (order.key, order.seed) == saved[slot], name
                checked += 1
    if not checked:
        pytest.skip("no save pair across a Monday")


def test_forecast_shape(data, saves):
    save = next(iter(saves.values()))
    boards = so.forecast(save, data, mondays=8)
    assert len(boards) == 8
    assert [b.days_played for b in boards] == so.board_days(save.days_played, 8)
    for b in boards:
        assert 1 <= len(b.orders) <= 2
        assert len({o.key for o in b.orders}) == len(b.orders)
        for o in b.orders:
            assert o.name and o.requester and o.reward >= 0 and o.last_day >= b.days_played
            if not o.sure:
                assert b.depends_on or o.notes


def test_picked_items_resolve(data):
    save = SimpleNamespace(professions=[], events_seen=set(), stats={}, profit_margin=1.0)
    orders = so._Orders(data, save)
    assert orders.item_id("Stone") == "(O)390"
    assert orders.item_id("Wood") == "(O)388"
    assert orders.item_id("Pumpkin") == "(O)276"
    assert orders.item_price("(O)138") == 65  # Rainbow Trout: Demetrius pays ten times it
