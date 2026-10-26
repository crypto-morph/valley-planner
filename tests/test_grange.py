"""The Fair's grange display: Lewis's score and the best nine."""

from valley_planner.facts.grange import Entry, best, prize, score


def e(name, q, cat, price):
    return Entry(f"(O){name}", name, q, cat, price)


def test_item_points():
    assert e("Cloth", 0, -26, 470).points == 6  # 1 + 20/90/200 marks + 300 (below gold) + 400 (normal only)
    assert e("Amaranth", 2, -75, 247).points == 6  # gold: 3 + three marks
    assert e("Bass", 4, -4, 250).points == 8  # iridium counts as 4, so +5
    assert e("Weed", 0, -999, 10).points == 1


def test_score_kinds_and_empty_slots():
    nine = [e("A", 0, -75, 10)] * 9
    assert score(nine) == 14 + 9 + 5 + 9  # one kind, full display
    assert score(nine[:7]) == 14 + 7 + 5 + 9 - 4  # two empty slots
    six = [e(str(c), 0, c, 10) for c in (-75, -79, -5, -2, -4, -80, -7)] + [e("B", 0, -26, 10)] * 2
    assert score(six) == 14 + 9 + 30 + 9  # kinds stop counting at six
    assert prize(90) == ("1st", 1000) and prize(74) == ("3rd", 250) and prize(10) == ("4th", 50)


def test_best_trades_kinds_against_points():
    great = e("Bass", 4, -4, 250)  # 8 points
    veg = e("Parsnip", 0, -75, 35)  # 2 points, but a second kind
    picked = best([(great, 20), (veg, 5)])
    assert picked.count(veg) == 1 and picked.count(great) == 8  # one parsnip for its +5, the rest bass
    assert score(picked) == 14 + 8 * 8 + 2 + 10 + 9
