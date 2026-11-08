"""Questions the day asks you: keep something back for a reason the planner can't weigh for you?

Each is {id, text, why, keep: [qualified id, lowest quality, count]}. The answer is yes unless you say no: the
sell plan (views/sell.py) holds what each question keeps, so what to sell and what to take follow the answer.
An id names the occasion (e.g. "luau:1", Year 1's Luau), so an answer lasts until that day.

The Luau, in our words (Event.governorTaste): the soup's score comes from the best ingredient you add; a gold
crop worth 160g or more (or a silver one worth 300g that's good to eat) is the top tier, +120 friendship with
everyone in town you've met; a decent one (worth 100g, or good to eat) is the middle tier, +60.
"""

from __future__ import annotations

from dataclasses import dataclass

from .farm import Farm

LUAU_DAY = 11  # Summer 11
QUALITY_WORDS = {1: "silver ", 2: "gold ", 4: "iridium "}


@dataclass(frozen=True)
class Ask:
    id: str
    text: str
    why: str
    keep: tuple[str, int, int]  # qualified id, the lowest quality that will do, how many
    label: str = ""  # why it's kept, for the Sell tab

    def view(self) -> dict:
        return {"id": self.id, "text": self.text, "why": self.why}


def _luau_pick(farm: Farm) -> tuple[int, int, str, int] | None:
    """(friendship, price, qualified id, quality) of the best thing you hold for the soup, or None."""
    objects = farm.data.asset("Data/Objects")
    best = None
    for it in farm.save.items:
        o = objects.get(it.qualified_id.removeprefix("(O)")) if it.qualified_id.startswith("(O)") else None
        if not o or it.category == -7 or int(o.get("Edibility") or -300) == -300:
            continue
        price, edible = int(o.get("Price") or 0), int(o.get("Edibility") or 0)
        if (it.quality >= 2 and price >= 160) or (it.quality == 1 and price >= 300 and edible > 10):
            score = 120
        elif edible >= 20 or price >= 100 or (it.quality >= 1 and price >= 70):
            score = 60
        else:
            continue
        if not best or (score, price) > best[:2]:
            best = (score, price, it.qualified_id, it.quality)
    return best


def luau(farm: Farm) -> Ask | str | None:
    """Before the Luau: keep the best thing you hold for the soup? A plain note when you hold nothing good."""
    s = farm.save
    if s.season != "summer" or s.day > LUAU_DAY:
        return None
    best = _luau_pick(farm)
    if not best:
        return ("The Luau on Summer 11: keep a gold crop worth 160g or more for the soup, for +120 with everyone in"
                " town.")
    score, price, qid, quality = best
    name = QUALITY_WORDS.get(quality, "") + farm.name(qid)
    return Ask(f"luau:{s.year}", f"Keep a {name} for the Luau soup?",
               f"On Summer {LUAU_DAY} it gives +{score} with everyone in town you've met; selling it gives {price}g "
               "or so. Say no and it goes in today's selling.", (qid, quality, 1),
               f"the Luau soup on Summer {LUAU_DAY} (+{score} with everyone in town)")


def asks(farm: Farm) -> list[Ask]:
    return [a for a in (luau(farm),) if isinstance(a, Ask)]


def notes(farm: Farm) -> list[str]:
    """What the questions say when there's nothing to ask about yet."""
    return [a for a in (luau(farm),) if isinstance(a, str)]
