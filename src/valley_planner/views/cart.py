"""The Traveling Cart: what it sells on its coming days, and when a given item turns up."""

from __future__ import annotations

import re

from .farm import Farm


def _place(farm: Farm, place: str) -> str:
    return " & ".join(farm.place(p) for p in place.split(" & "))


def _day(farm: Farm, d) -> dict:
    return {"date": d.label, "place": _place(farm, d.place),
            "items": [{"item": i.item, "name": i.name, "price": i.price,
                       "stock": i.stock if i.stock < 2**31 - 1 else None, "sure": i.sure} for i in d.items]}


def upcoming(farm: Farm, count_days: int = 14) -> dict:
    days = farm.cart.days(farm.when, count_days=count_days, guarantee=farm.save.cart_guarantee)
    return {"days": [_day(farm, d) for d in days]}


def search(farm: Farm, text: str, count_days: int = 224) -> dict:
    """Cart days (over the next two years by default) selling anything whose name contains `text`."""
    needle = text.strip().lower()
    hits = []
    if needle:
        for d in farm.cart.days(farm.when, count_days=count_days, guarantee=farm.save.cart_guarantee):
            for i in d.items:
                if needle in i.name.lower():
                    hits.append({"date": d.label, "place": _place(farm, d.place), "name": i.name, "price": i.price,
                                 "sure": i.sure})
    return {"query": text, "hits": hits}


def _choice(farm: Farm, bundle: str, item: str) -> str:
    """For a bundle that takes N of its items: "" when every remaining item is needed, else what else could fill
    it ("needs 4 more of 8: Maple Syrup, Oak Resin… would do instead")."""
    b = next((b for b in farm.bundles.all if b.display == bundle and not b.done), None)
    if b is None:
        return ""
    left = [i for i in b.ingredients if not i.given]
    need = b.slots - (len(b.ingredients) - len(left))
    if need >= len(left):
        return ""
    others = [farm.name(i.item) for i in left if i.item and i.item != item]
    return (f"it needs {need} more of these {len(left)}, so {', '.join(others[:4])}"
            + ("…" if len(others) > 4 else "") + " could do instead")


VISITS = 6  # cart visits the Cart tab looks ahead (about three weeks: Fridays and Sundays)


def tab(farm: Farm, spouse: str = "") -> dict:
    """The Cart tab: each coming visit's stock with what matters marked. A bundle item is flagged "buy here" only
    when the cart is the plan's one way to it (cc.cart_only); otherwise it says how the plan gets it instead.
    Gifts your sweetheart loves or likes are marked too."""
    from ..engine import cc
    from .month import red_cabbage
    slots = {}
    for s in cc.plan(farm)["slots"]:
        if s["status"] != "have":
            slots.setdefault(s["item"], []).append(s)
    held = farm.held()
    days = list(farm.cart.days(farm.when, count_days=VISITS * 4, guarantee=farm.save.cart_guarantee))[:VISITS]
    out = []
    for d in days:
        rows = []
        for i in d.items:
            stock = i.stock if i.stock < 2**31 - 1 else None
            tags = []
            for s in slots.get(i.item, []):
                best = s.get("best") or {}
                # only a place you can't reach yet (the Desert's bus, the island's boat) makes the cart worth it;
                # a machine or animal you haven't got yet is just a step on the plan
                blocked = [b for b in best.get("blocked") or [] if any(w in str(b) for w in ("bus", "boat"))]
                buy = cc.cart_only(s, stock or 99) or bool(blocked) and (stock or 99) >= s["count"]
                choice = _choice(farm, s["bundle"], i.item)
                if buy and choice:  # one of several: skipping it costs nothing if the others come
                    tags.append({"kind": "maybe", "text": f"{s['bundle']} bundle, optional", "why": choice})
                    continue
                why = (f"needed, and without it the bundle waits for {blocked[0]}"
                       if blocked and best.get("kind") != "cart_day"
                       else "only the cart has it in time" if buy else f"or {best.get('label', 'another way')}")
                why = re.sub(r"\ba ([AEIOU])", r"an \1", why)
                tags.append({"kind": "buy" if buy else "cc", "text": f"{s['bundle']} bundle", "why": why})
            taste = farm.gifts.taste(spouse, i.item) if spouse and i.item.startswith("(O)") else None
            if taste == "love":
                tags.append({"kind": "gift", "text": f"{spouse} loves it", "why": "a loved gift: 80 friendship"})
            rows.append({"item": i.item, "name": farm.name(i.item) if i.item.startswith("(O)") else i.name,
                         "price": i.price, "stock": stock, "sure": i.sure, "held": held.get(i.item, 0),
                         "icon": farm.icon(i.item), "tags": tags})
        rows.sort(key=lambda r: (not any(t["kind"] == "buy" for t in r["tags"]), not r["tags"], r["price"]))
        buy = [r for r in rows if any(t["kind"] == "buy" for t in r["tags"])]
        out.append({"date": d.label, "place": _place(farm, d.place), "days_away": d.days_played - farm.when.days_played,
                    "items": rows, "buy": len(buy), "buy_gold": sum(r["price"] for r in buy),
                    "marked": sum(1 for r in rows if r["tags"])})
    return {"money": farm.save.money, "visits": out, "cabbage": red_cabbage(farm)}
