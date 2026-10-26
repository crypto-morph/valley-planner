"""Morning: a few things to do first today, what's coming this week, and the farm at a glance.

"Do first" gathers what can't wait: a birthday today (with a loved gift you
hold), crops ready or not yet watered, a Community Center slot whose last
safe day is close, the cart if it's here, and a shop that's shut today.
"""

from __future__ import annotations

from ..engine import cc
from . import crops
from .farm import Farm

SOON = 3  # days: a last safe day this close goes in "do first"


def view(farm: Farm) -> dict:
    s, w = farm.save, farm.when
    first: list[dict] = []
    today_events = farm.calendar.day(w, today_days_played=w.days_played)
    held = farm.held()
    for e in today_events:
        if e.kind == "birthday" and e.who:
            loved = [q for q in held if farm.gifts.giftable(q) and farm.gifts.taste(e.who, q) == "love"]
            first.append({"kind": "birthday", "title": e.label,
                          "text": f"You hold {', '.join(farm.name(q) for q in loved[:3])}, which they love." if loved
                          else "You hold nothing they love; a liked gift still counts double today."})
        elif e.kind == "cart":
            first.append({"kind": "cart", "title": "The Traveling Cart is in the Forest", "text": "6 AM to 8 PM"})
        elif e.kind in ("festival", "passive"):
            first.append({"kind": "festival", "title": e.label, "text": e.detail})
    mine = crops.mine(farm)
    if mine["ready"]:
        first.append({"kind": "crops", "title": f"Harvest {mine['ready']} ready crops", "text": ""})
    if mine["thirsty"] and not mine["rain"]:
        first.append({"kind": "crops", "title": f"Water {mine['thirsty']} crops",
                      "text": "they won't grow tonight otherwise"})
    plan = cc.plan(farm)
    urgent = []
    for slot in plan["slots"]:
        b = slot["best"]
        if not b or slot["status"] in ("have", "stuck") or not b.get("last_start"):
            continue
        last = _day_number(b["last_start"])
        if last is not None and last - w.days_played <= SOON:
            urgent.append({"kind": "cc", "title": f"{slot['name']} for the {slot['bundle']} bundle",
                           "text": f"{b['label']}: last safe day {b['last_start']}"})
    first += urgent
    closed = [x for x in farm.hours_today() if x["closed"] and "desert" not in x["closed"].lower()]
    for x in closed[:2]:
        first.append({"kind": "closed", "title": f"{x['shop']} is shut today", "text": x["closed"]})

    week = []
    for d, events in farm.calendar.days(w, 8):
        if d.days_played == w.days_played:
            continue
        for e in events:
            week.append({"date": farm.label(d.days_played).rsplit(",", 1)[0], "kind": e.kind, "label": e.label,
                         "sure": e.sure})
    return {"date": farm.label(w.days_played), "weather": s.weather, "tomorrow": s.weather_tomorrow,
            "money": s.money, "luck": s.daily_luck, "first": first, "week": week,
            "cc": {"deadline": plan["deadline"], "counts": plan["counts"],
                   "bundles_done": sum(b.done for b in farm.bundles.all), "bundles": len(farm.bundles.all)}}


def _day_number(label: str) -> int | None:
    """'Fall 18, Year 1' -> days played."""
    try:
        season_day, year = label.split(", Year ")
        season, day = season_day.split()
        i = ("Spring", "Summer", "Fall", "Winter").index(season)
        return (int(year) - 1) * 112 + i * 28 + int(day)
    except ValueError:
        return None
