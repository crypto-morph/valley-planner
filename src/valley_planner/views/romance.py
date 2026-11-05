"""The Romance tab: hearts with your chosen partner, and what you hold that would raise them.

From the game (facts/romance.py, facts/gifts.py): friendship points, a heart every 250; talking gives 20 once
a day, a gift 80 loved / 45 liked (×8 on their birthday), two gifts a week counted from Sunday. Someone you
could date stops at 8 hearts and 249 points until given a Bouquet; dating, at 10 hearts and 249 until the
Mermaid's Pendant. Only gifts you actually hold are listed, at the taste the game itself resolves for them.
"""

from __future__ import annotations

from ..facts import romance
from .farm import Farm, date_label


def partners(farm: Farm) -> list[dict]:
    s = farm.save
    out = []
    for name, c in farm.data.asset("Data/Characters").items():
        if not c.get("CanBeRomanced"):
            continue
        f = s.friends.get(name)
        out.append({"name": name, "display": farm.data.text(c.get("DisplayName")) or name,
                    "hearts": f.hearts if f else 0, "status": f.status if f else "Friendly"})
    return sorted(out, key=lambda p: (-p["hearts"], p["name"]))


def view(farm: Farm, target: str = "") -> dict:
    s, w = farm.save, farm.when
    people = partners(farm)
    if not target or target not in {p["name"] for p in people}:
        return {"partners": people, "target": None}

    c = farm.data.asset("Data/Characters").get(target) or {}
    f = s.friends.get(target)
    points = f.points if f else 0
    status = f.status if f else "Friendly"
    hearts = points // romance.HEART
    dating = status == "Dating"
    settled = status in ("Engaged", "Married")  # the Pendant (or the ring itself) already has them past the cap
    cap = None if settled else (romance.CAP_DATING if dating else romance.CAP_FRIEND)
    at_cap = cap is not None and points >= cap

    bseason = (c.get("BirthSeason") or "").lower()
    birthday_today = bseason == w.season and c.get("BirthDay") == w.day

    gifts = []
    for qid, n in farm.held().items():
        if not n or not farm.gifts.giftable(qid):
            continue
        taste = farm.gifts.taste(target, qid)
        if taste not in ("love", "like"):
            continue
        gain = romance.GIFT["loved" if taste == "love" else "liked"] * (romance.BIRTHDAY if birthday_today else 1)
        gifts.append({"name": farm.name(qid), "held": n, "taste": taste, "points": gain,
                      "where": farm.where_held(qid)})
    gifts.sort(key=lambda g: (-g["points"], g["name"]))

    points_to_next = 0 if at_cap else min(cap, (hearts + 1) * romance.HEART) - points if cap is not None \
        else (hearts + 1) * romance.HEART - points

    unlock = None
    if at_cap:
        objects = farm.data.asset("Data/Objects")
        if dating:
            price = 2 * int((objects.get(romance.PENDANT) or {}).get("Price") or 2500)
            unlock = {"item": "the Mermaid's Pendant", "gold": price,
                      "how": "the Old Mariner, past the beach bridge, on a rainy day before 7 PM (once your "
                             "house has had its first upgrade)"}
        else:
            price = 2 * int((objects.get(romance.BOUQUET) or {}).get("Price") or 100)
            unlock = {"item": "a Bouquet", "gold": price,
                      "how": "Pierre's General Store, once you have 8 hearts with anyone you could date"}

    return {"partners": people, "target": target, "name": farm.data.text(c.get("DisplayName")) or target,
            "hearts": hearts, "points": points, "status": status, "dating": dating, "settled": settled,
            "at_cap": at_cap, "cap_hearts": (cap // romance.HEART) if cap is not None else None,
            "next_heart": hearts + 1, "points_to_next": max(0, points_to_next),
            "gifts_this_week": f.gifts_this_week if f else 0,
            "gifts_left": max(0, romance.GIFTS_PER_WEEK - (f.gifts_this_week if f else 0)),
            "gifted_today": bool(f and f.gifts_today), "talked_today": bool(f and f.talked_today),
            "birthday_today": birthday_today,
            "birthday": date_label(bseason, c.get("BirthDay") or 0) if bseason else "",
            "gifts": gifts, "unlock": unlock}
