"""The Community Center plan: choosing the best way, day windows, and the sources it draws on."""

from valley_planner.engine.cc import Way, _best, _day_ok
from valley_planner.facts.access import place_open
from valley_planner.facts.conditions import When
from valley_planner.facts.sources import Source


def way(kind, earliest=None, blocked=(), odds=None, sure=True):
    return Way(Source(kind, kind), earliest, earliest, list(blocked), odds, sure)


def test_best_way_policy():
    fish, cart, goat = way("fish", 20), way("cart", odds=0.33), way("animal", 15, blocked=["a Goat"])
    assert _best([cart, fish, goat]) is fish  # a way you can use now beats luck and unlocks
    assert _best([cart, goat]) is goat  # an unlock beats unlikely luck…
    likely = way("cart", odds=0.9)
    assert _best([likely, goat]) is likely  # …but not likely luck
    maybe, sure = way("shop", 12, sure=False), way("fish", 14)
    assert _best([maybe, sure]) is sure
    assert _best([way("monster", None, blocked=["killing x"], odds=None, sure=False), cart]) is cart


def test_day_windows():
    w = When("fall", 1, 1, 57)
    stall = Source("shop", "Festival_EggFestival_Pierre", frozenset({"spring"}), (13, 13))
    assert _day_ok(stall, 13, w) and not _day_ok(stall, 14, w) and not _day_ok(stall, 13 + 28, w)
    y2 = Source("shop", "SeedShop", frozenset({"summer"}), condition="YEAR 2")
    assert _day_ok(y2, 29, w) is False and _day_ok(y2, 112 + 29, w) is True


def test_place_gates():
    w = When("fall", 1, 1, 57)
    assert place_open("Woods", w)[0] is False and place_open("Woods", When("fall", 1, 1, 57, axe_level=2))[0]
    assert place_open("Railroad", When("summer", 2, 1, 30))[0] is False and place_open("Railroad", w)[0]
    assert place_open("BeachTidePools", w)[0] is False
    assert place_open("BeachTidePools", When("fall", 1, 1, 57, flags={"beachBridgeFixed"}))[0]
    assert place_open("Desert", When("fall", 1, 1, 57, mail={"ccVault"}))[0]
