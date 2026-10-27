"""The Calendar tab: what's on each coming day, and today's shop hours."""

from __future__ import annotations

from ..facts.calendar import WEEKDAYS
from ..facts.hours import SHOPS
from ..facts.schedules import time_label
from .farm import Farm, date_label


def days(farm: Farm, count: int = 28) -> dict:
    out = []
    for w, events in farm.calendar.days(farm.when, count):
        out.append({"date": date_label(w.season, w.day, w.year), "weekday": WEEKDAYS[w.day % 7],
                    "today": w.days_played == farm.when.days_played,
                    "events": [{"kind": e.kind, "label": e.label, "detail": _detail(farm, e), "sure": e.sure,
                                "start": time_label(e.start) if e.start else "",
                                "end": time_label(e.end) if e.end else ""} for e in events]})
    return {"days": out}


def _detail(farm: Farm, e) -> str:
    """Festival places are location names ("Town"); everything else is already words."""
    return farm.place(e.detail) if e.kind == "festival" and e.detail else e.detail


def shop_hours(farm: Farm, ahead: int = 0) -> dict:
    w = farm.when.on(farm.when.days_played + ahead)
    raining = farm.save.wet if ahead == 0 else None
    rows = []
    for shop in SHOPS:
        d = farm.hours.day(shop, w, raining=raining, green_rain=ahead == 0 and farm.save.weather == "green rain",
                           stats=farm.save.stats)
        rows.append({"id": shop.id, "shop": shop.name, "spans": [list(x) for x in d.open],
                     "open": [f"{time_label(a)} – {time_label(b)}" for a, b in d.open],
                     "closed": d.closed_why or "", "sure": d.sure})
    return {"date": date_label(w.season, w.day, w.year), "shops": rows}
