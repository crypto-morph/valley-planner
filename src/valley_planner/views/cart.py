"""The Traveling Cart: what it sells on its coming days, and when a given item turns up."""

from __future__ import annotations

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
