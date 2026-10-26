"""The Stardew Valley Fair's grange display: Lewis's score, and the best display from what you hold (1.6.15).

How Lewis scores it (Event.judgeGrange), in our words: 14, plus for each
of the nine items its quality + 1 (iridium counts as 4, so +5) and a point
for each sale-price mark it reaches — 20g, 90g, 200g, 300g (below gold
only) and 400g (normal quality only), using the item's real sale price for
you; plus 5 for each different kind of item, up to 30 — vegetables,
fruit, animal goods (eggs, milk, meat, -18), gems and minerals, fish,
forage / flowers / syrups, cooking, artisan goods; plus 9 - 2 for each
empty slot. 90 wins (1,000 star tokens), 75 is second (500), 60 third
(250), else fourth (50). Mayor Lewis's shorts on the display skip the
judging (750). Any small object can go on it, one per slot; the same item
can fill several slots. Only what's in your backpack at the Fair counts.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = 14
SLOTS = 9
PRICE_MARKS = (20, 90, 200)
KINDS = {-75: "vegetables", -79: "fruit", -18: "animal goods", -14: "animal goods", -6: "animal goods",
         -5: "animal goods", -12: "gems and minerals", -2: "gems and minerals", -4: "fish",
         -81: "forage, flowers and syrups", -80: "forage, flowers and syrups", -27: "forage, flowers and syrups",
         -7: "cooking", -26: "artisan goods"}
MAX_KINDS = 6
PRIZES = ((90, "1st", 1000), (75, "2nd", 500), (60, "3rd", 250))
FOURTH = ("4th", 50)


@dataclass(frozen=True)
class Entry:
    item: str  # qualified id
    name: str
    quality: int
    category: int | None
    price: int  # its sale price for you

    @property
    def points(self) -> int:
        p = self.quality + 1
        p += sum(1 for m in PRICE_MARKS if self.price >= m)
        if self.price >= 300 and self.quality < 2:
            p += 1
        if self.price >= 400 and self.quality < 1:
            p += 1
        return p

    @property
    def kind(self) -> str | None:
        return KINDS.get(self.category)


def score(entries: list[Entry]) -> int:
    filled = entries[:SLOTS]
    kinds = {e.kind for e in filled if e.kind}
    return BASE + sum(e.points for e in filled) + min(30, 5 * len(kinds)) + 9 - 2 * (SLOTS - len(filled))


def prize(points: int) -> tuple[str, int]:
    return next(((place, tokens) for need, place, tokens in PRIZES if points >= need), FOURTH)


def best(candidates: list[tuple[Entry, int]]) -> list[Entry]:
    """The highest-scoring nine from (entry, how many you hold). Each kind is worth 5 once, so: try every
    count of kinds k (0-6), each kind shown by its best item, the rest of the slots by the best items left."""
    pool = sorted(((e, n) for e, n in candidates if n > 0), key=lambda en: -en[0].points)
    top_of_kind: dict[str, Entry] = {}
    for e, _ in pool:
        if e.kind and e.kind not in top_of_kind:
            top_of_kind[e.kind] = e
    kinds = sorted(top_of_kind.values(), key=lambda e: -e.points)
    choice: list[Entry] = []
    for k in range(min(MAX_KINDS, len(kinds)) + 1):
        picked = list(kinds[:k])
        left = {id(e): n for e, n in pool}
        for e in picked:
            left[id(e)] -= 1
        for e, _ in pool:
            while len(picked) < SLOTS and left[id(e)] > 0:
                picked.append(e)
                left[id(e)] -= 1
        if not choice or score(picked) > score(choice):
            choice = picked
    return choice
