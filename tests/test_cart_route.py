"""The cart in the route: once the seed is known, a visit is a dated purchase that competes with the long way."""

import pytest
from shared import shared_data

from valley_planner.engine.route.plan import Router, route
from valley_planner.engine.route.start import new_farm

GAME_ID = "453557957"


@pytest.fixture(scope="module")
def data():
    try:
        return shared_data()
    except RuntimeError:
        pytest.skip("no game here")


def farm_on(data, days_played=1, money=None, *, seed=GAME_ID):
    from valley_planner.facts.conditions import date_of
    f = new_farm(data, unique_id=seed or "1")
    s = f.save
    s.mtime = 1.0 if seed else 0.0
    s.days_played = days_played
    s.season, s.day, s.year = date_of(days_played)
    s.money = s.money if money is None else money
    return f


def visits_of(farm, item):
    return [d.days_played for d, _ in farm.cart.calendar(farm.when, count_days=112).get(item, [])]


def bundle_item_on_the_cart(farm):
    """An open slot the cart sells, its long way dearest, so the cart is the one to beat."""
    r = Router(farm, cave="bats")
    found = []
    for _k, _n, slots in r.planner.bundle_slots():
        for s in slots:
            carts = [w for w in s.ways if w.source.on is not None]
            longs = [w for w in s.ways if w.source.on is None and r.viable(w)]
            if carts and longs:
                gap = min(r.way_gold(w) for w in longs) - carts[0].source.cost
                found.append((gap, s))
    return r, max(found, key=lambda x: x[0])[1]


def test_a_known_seed_turns_the_carts_odds_into_dated_visits(data):
    farm = farm_on(data)
    item = next(iter(farm.cart.calendar(farm.when, count_days=112)))
    planner = Router(farm, cave="bats").planner
    ways = [w for w in planner.ways(item) if w.source.on is not None]
    assert ways and all(w.earliest == w.latest_start == w.source.on and w.odds is None for w in ways)
    assert [w.source.on for w in ways] == [d for d in visits_of(farm, item) if d <= planner.deadline]
    assert not [w for w in planner.ways(item) if w.source.kind == "cart"]


def test_with_no_seed_the_cart_stays_a_chance(data):
    farm = farm_on(data, seed="")
    r = Router(farm, cave="bats")
    ways = r.planner.ways("(O)430")  # Truffle
    assert any(w.odds for w in ways if w.source.kind == "cart") and not [w for w in ways if w.source.on]


def test_the_cheaper_visit_beats_the_long_way_with_it_behind_as_the_fallback(data):
    farm = farm_on(data)
    r, slot = bundle_item_on_the_cart(farm)
    w = r.pick(slot)
    req = r.slot_req(slot)
    if w.source.on is not None:
        assert req.earliest == req.latest == w.source.on and req.fallback is not None
    else:  # the long way really is cheaper for every slot on this seed
        assert r.way_gold(w) <= min(x.source.cost for x in slot.ways if x.source.on is not None)


def test_a_missed_visit_stops_being_offered(data):
    farm = farm_on(data)
    item, days = next((k, v) for k, v in farm.cart.calendar(farm.when, count_days=112).items() if len(v) >= 1)
    last = days[-1][0].days_played
    later = farm_on(data, last + 1)
    assert not [w for w in Router(later, cave="bats").planner.ways(item) if w.source.on]


def test_a_visit_you_cant_afford_falls_back(data):
    from valley_planner.engine.route.model import Req
    from valley_planner.engine.unlocks import Unlock
    r = Router(farm_on(data, money=0), cave="bats")
    dear = Req("x", 5, 5, [Unlock("cart:x", "buy it", 10**7)], 0, season="the cart")
    dear.fallback = Req("x", 1, 112, [Unlock("cheap", "buy it", 0)], 0, season="the long way")
    step, used, _why = r.place_any(dear, 112)
    assert step is not None and used is dear.fallback
    assert any("the cart won't work" in i and "the long way" in i for i in r.info)
    alone = Req("y", 5, 5, [Unlock("cart:y", "buy it", 10**7)], 0, season="the cart")
    assert r.place_any(alone, 112)[0] is None


def test_the_whole_route_runs_on_a_known_seed(data):
    v = route(farm_on(data), ["cc"], ["marriage"], cave="bats")
    bought = [s for o in v["objectives"] for s in o["steps"] for n in s["needs"] if n["key"].startswith("cart:")]
    assert all(s["ready"] for s in bought)


def test_a_cart_visit_is_not_a_deadline_while_another_way_is_open():
    from valley_planner.engine.cc import Way, _best
    from valley_planner.facts.sources import Source
    visit = Way(Source("cart_day", "the cart", on=5), 5, 5)
    crop = Way(Source("crop", "grow it"), 40, 100)
    assert _best([visit, crop]) is crop
    assert _best([visit, Way(Source("animal", "a Chicken"), 30, 100, blocked=["a Coop"])]).source.kind == "animal"
    assert _best([visit]) is visit


def test_a_crop_in_the_ground_only_has_to_finish(data):
    from types import SimpleNamespace

    from valley_planner.engine.cc import Slot
    farm = farm_on(data)
    farm.save.crops = [SimpleNamespace(harvest_id="190", days_left=7, dead=False)]
    r = Router(farm, cave="bats")
    slot = Slot("Spring Crops", "Pantry", "(O)190", "Cauliflower", 1, 0, False, [])
    req = r.slot_req(slot)
    assert req.earliest == r.today + 7 and req.chain == []
    gold = Slot("Quality Crops", "Pantry", "(O)190", "Cauliflower", 1, 2, False, [])
    assert r.growing(gold) is None
