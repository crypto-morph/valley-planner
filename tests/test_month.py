"""Rain ahead, and the watch on Red Cabbage."""

from types import SimpleNamespace as NS

from valley_planner.engine import cc
from valley_planner.facts.conditions import date_of
from valley_planner.facts.weather import forecast
from valley_planner.views import month

GAME_ID = 453557957


def wet_days(start, end):
    return [date_of(d)[:2] for d in range(start, end) if forecast(d, GAME_ID, festival=False)[0] in ("rain", "storm")]


def test_rain_is_known_for_the_rest_of_the_year():
    """Spring 24 and Summer 11 roll wet but are festivals, which the calendar passes in; see the next test."""
    assert wet_days(23, 29) == [("spring", 24), ("spring", 26), ("spring", 28)]
    assert wet_days(29, 57) == [("summer", d) for d in (11, 13, 19, 21, 26)]
    assert wet_days(57, 85) == [("fall", d) for d in (7, 8, 12, 17, 21, 26)]


def test_forced_days():
    assert forecast(3, GAME_ID) == ("rain", True)
    assert forecast(2, GAME_ID) == ("sun", True) and forecast(29, GAME_ID) == ("sun", True)
    assert forecast(24, GAME_ID, festival=True) == ("sun", True)
    assert forecast(28 + 13, GAME_ID) == ("storm", True)


def visit(dp, item, price, place="Forest"):
    return NS(days_played=dp, place=place), NS(name=item, price=price, item=item)


def farm(*, held=(), seeds=(), today=22, money=1000, cart=None, needed=True, crops=()):
    where = {month.CABBAGE: list(held), month.CABBAGE_SEEDS: list(seeds)}
    bundle = NS(open_ingredients=[NS(item=month.CABBAGE)] if needed else [])
    return NS(when=NS(days_played=today), save=NS(money=money, crops=list(crops), cart_guarantee=-1),
              bundles=NS(all=[bundle]), where_held=lambda q: where.get(q, []), place=lambda p: p,
              label=lambda d: f"{date_of(d)[0].title()} {date_of(d)[1]}, Year {date_of(d)[2]}",
              cart=NS(calendar=lambda when, **kw: cart or {}))


def test_done_means_no_watch():
    assert month.red_cabbage(farm(needed=False)) is None


def test_held_stays_quiet_and_says_where():
    w = month.red_cabbage(farm(held=["the dark red chest"]))
    assert w["state"] == "held" and not w["banner"] and "dark red chest" in w["text"]


def test_a_week_out_raises_the_banner_and_counts_the_gold():
    cart = {month.CABBAGE: [visit(29, "Red Cabbage", 1500)]}
    w = month.red_cabbage(farm(cart=cart))
    assert w["banner"] and w["level"] == "amber" and w["days_left"] == 7 and "500g short" in w["text"]
    assert not month.red_cabbage(farm(cart=cart, today=21))["banner"]
    assert month.red_cabbage(farm(cart=cart, today=29))["level"] == "red"


def test_seeds_too_late_to_grow_dont_count():
    cart = {month.CABBAGE_SEEDS: [visit(28 + 20, "Red Cabbage Seeds", 300)]}
    assert month.red_cabbage(farm(cart=cart))["state"] == "pierre"
    cart = {month.CABBAGE_SEEDS: [visit(28 + 19, "Red Cabbage Seeds", 300)]}
    assert month.red_cabbage(farm(cart=cart))["state"] == "coming"


def test_nothing_in_year_one_says_so_plainly():
    w = month.red_cabbage(farm(cart={month.CABBAGE: [visit(190, "Red Cabbage", 900)]}))
    assert w["state"] == "pierre" and not w["banner"]


def slot(count=1, status="ok", kind="crop"):
    return {"count": count, "status": status, "best": {"kind": kind}}


def test_the_cart_is_for_what_nothing_else_can_get():
    """1 Wood for 600g, when the bundle wants 99 and the trees are free: never."""
    assert not cc.cart_only(slot(count=99), 1)
    assert not cc.cart_only(slot(), 5)
    assert not cc.cart_only(slot(status="blocked", kind="machine"), 5)
    assert cc.cart_only(slot(kind="cart_day"), 1)
    assert not cc.cart_only(slot(count=2, kind="cart_day"), 1)
