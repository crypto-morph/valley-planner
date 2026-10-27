"""The farm cave: Demetrius's offer, and what fruit bats or mushroom boxes bring (1.6.15).

In our words:
- The offer is event 65: on the farm, 6 AM to noon, once lifetime earnings reach 25,000g (spending doesn't
  delay it). The choice is made once and can't be changed.
- Fruit bats (FarmCave.DayUpdate): every night, while a roll comes in under 0.66, one more fruit — about
  1.9 a night, every season. Each is Salmonberry, Spice Berry, Wild Plum or Blackberry (one in five each),
  or a tree fruit: Apple one time in ten, otherwise Apricot, Orange, Peach, Pomegranate or Cherry evenly.
- Mushrooms: six mushroom boxes (and a Dehydrator); each box makes one mushroom a day, the first of these
  rolls to come up: Purple 2.5%, Chanterelle 7.5%, Morel 9%, Red 15%, otherwise Common.
"""

from __future__ import annotations

EARNINGS_TRIGGER = 25000
BATS, MUSHROOMS = "bats", "mushrooms"

_MEAN_FRUIT = 0.66 / (1 - 0.66)  # the number of rolls under 0.66 before the first that isn't
_TREE = 0.2  # one in five fruit is a tree fruit
BAT_FRUIT: dict[str, float] = {  # chance a single fruit is this
    "296": 0.2, "396": 0.2, "406": 0.2, "410": 0.2,
    "613": _TREE * 0.1, **{str(i): _TREE * 0.9 / 5 for i in range(634, 639)},
}
BOXES = 6
_ORDER = (("422", 0.025), ("281", 0.075), ("257", 0.09), ("420", 0.15))
MUSHROOM: dict[str, float] = {}  # chance a box's mushroom is this
_left = 1.0
for _id, _p in _ORDER:
    MUSHROOM[_id] = _left * _p
    _left *= 1 - _p
MUSHROOM["404"] = _left


def nightly(choice: str, item: str) -> float:
    """Chance of at least one of `item` from the cave on a given day."""
    oid = item.removeprefix("(O)")
    if choice == BATS and oid in BAT_FRUIT:
        # a Poisson-like count of fruit: P(none of it) = (1 - p)^n averaged over the run's length
        p, keep = BAT_FRUIT[oid], 0.66
        return 1 - (1 - keep) / (1 - keep * (1 - p))
    if choice == MUSHROOMS and oid in MUSHROOM:
        return 1 - (1 - MUSHROOM[oid]) ** BOXES
    return 0.0


def nights_for(choice: str, item: str, confidence: float = 0.8) -> int | None:
    """Days of the cave running for `confidence` of at least one."""
    p = nightly(choice, item)
    if p <= 0:
        return None
    n, none = 0, 1.0
    while 1 - none < confidence and n < 400:
        n += 1
        none *= 1 - p
    return n


def gives(choice: str) -> set[str]:
    return set(BAT_FRUIT if choice == BATS else MUSHROOM)
