"""Morning: what happens today, what to react to, and what to get done, plus the week ahead.

"Happening today" is the day itself: a birthday (with a loved gift you hold, and which chest it's in), a
festival, the Queen of Sauce, the Traveling Cart (and anything on it your bundles need), the bookseller, the
Saloon's dish, shops that are shut, the weather today and tomorrow, and the spirits' mood (the TV fortune:
TV.getFortuneForecast, luck below -0.07 / -0.02, above 0.02 / 0.07, the extremes at ±0.12).
"Get done" is the farm and the errands: crops ready or dry, crops that won't finish before the season ends,
Community Center items with a last safe day close, things you hold for open bundles, the museum, geodes.
The route's own steps for today are added by the page from the Route tab's goals.
"""

from __future__ import annotations

from ..engine import cc
from . import crops, errands
from .farm import Farm

SOON = 3  # days: a last safe day this close goes in "get done"
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEATHER = {"sun": "sunny", "rain": "rain", "storm": "a storm", "snow": "snow", "wind": "windy",
           "green rain": "green rain"}


def luck_words(luck: float) -> tuple[str, str]:
    """(the spirits' mood, what it means) from the day's luck, on the TV fortune's thresholds."""
    if luck <= -0.12:
        return "very unhappy", "a bad day for the Mines, geodes and fishing treasure"
    if luck < -0.07:
        return "unhappy", "a poor day for the Mines and geodes"
    if luck < -0.02:
        return "a little unhappy", "slightly worse odds in the Mines"
    if luck <= 0.02:
        return "neutral", ""
    if luck >= 0.12:
        return "very happy", "the best day for the Mines, geodes and fishing treasure"
    if luck > 0.07:
        return "happy", "a good day for the Mines and cracking geodes"
    return "in good humour", "slightly better odds in the Mines"


def view(farm: Farm, agenda: list[dict] | None = None) -> dict:
    """`agenda`: the route's steps (from plan.route), so today's purchases and chopping join the day."""
    s, w = farm.save, farm.when
    held = farm.held()
    today: list[dict] = []

    def where(qid: str) -> str:
        places = [p for p in farm.where_held(qid) if p != "your backpack"]
        return f" ({', '.join(places)})" if places else ""

    for e in farm.calendar.day(w, today_days_played=w.days_played):
        if e.kind == "birthday" and e.who:
            loved = [q for q in held if farm.gifts.giftable(q) and farm.gifts.taste(e.who, q) == "love"]
            liked = [q for q in held if farm.gifts.giftable(q) and farm.gifts.taste(e.who, q) == "like"]
            if loved:
                text = f"Loved gift you hold: {farm.name(loved[0])}{where(loved[0])}" + (
                    f"; also {', '.join(farm.name(q) for q in loved[1:3])}" if len(loved) > 1 else "")
            elif liked:
                text = f"Nothing you hold is loved; liked: {farm.name(liked[0])}{where(liked[0])}"
            else:
                text = "Nothing you hold is loved or liked"
            today.append({"kind": "birthday", "title": e.label, "text": text + ". A birthday gift counts 8 times."})
        elif e.kind in ("festival", "passive", "derby"):
            hours = f"{_time(e.start)}–{_time(e.end)}" if e.start and e.end else ""
            today.append({"kind": "festival", "title": e.label,
                          "text": " · ".join(x for x in (farm.place(e.detail) if e.detail else "", hours) if x)})
        elif e.kind == "tv":
            recipe = e.label.split(": ", 1)[-1]
            known = recipe in s.cooking_recipes
            today.append({"kind": "tv", "title": f"{e.label}, on TV today",
                          "text": "you already know it" if known else "watch it to learn the recipe"})
        elif e.kind == "cart":
            today.append(_cart(farm))
        elif e.kind in ("bookseller", "green_rain"):
            today.append({"kind": e.kind, "title": e.label, "text": farm.place(e.detail) if e.detail else ""})
    if s.dish_of_the_day:
        qid, n = s.dish_of_the_day
        today.append({"kind": "dish", "title": f"The Saloon's dish of the day: {farm.name(qid)}",
                      "text": f"{n} this morning"})
    for x in [x for x in farm.hours_today() if x["closed"] and "desert" not in x["closed"].lower()][:3]:
        today.append({"kind": "closed", "title": f"{x['shop']} is shut today", "text": x["closed"]})

    mine = crops.mine(farm)
    rain_now = s.weather in ("rain", "storm", "green rain")
    weather = {"today": WEATHER.get(s.weather, s.weather),
               "tomorrow": WEATHER.get(s.weather_tomorrow, s.weather_tomorrow),
               "note": "the rain waters your crops today" if rain_now
               else "rain tomorrow, so no watering then" if s.weather_tomorrow in ("rain", "storm") else ""}
    mood, means = luck_words(s.daily_luck)

    do: list[dict] = []
    if mine["ready"]:
        do.append({"kind": "crops", "title": f"Harvest {mine['ready']} ready crops", "text": ""})
    if mine["thirsty"] and not mine["rain"]:
        do.append({"kind": "crops", "title": f"Water {mine['thirsty']} crops",
                   "text": "they won't grow tonight otherwise"})
    if mine["missed"]:
        do.append({"kind": "crops", "title": "Some crops weren't watered yesterday",
                   "text": ", ".join(f"{n} {name}" for name, n in mine["missed"].items()) + ": a day lost"})
    if mine["dies"]:
        left = 28 - (w.days_played - 1) % 28
        do.append({"kind": "crops", "title": f"{mine['dies']} crops won't ripen before {w.season.title()} ends",
                   "text": f"{left} day{'s' if left != 1 else ''} left: don't spend more on them"})
    for t in crops.fruit_trees(farm):
        if t["first_n"] and 0 < t["first_n"] - w.days_played <= SOON and not t["on_tree"]:
            do.append({"kind": "tree", "title": f"Your {t['fruit']} tree: {t['text']}", "text": t["where"]})
    plan = cc.plan(farm)
    for slot in plan["slots"]:
        b = slot["best"]
        if not b or slot["status"] in ("have", "stuck") or not b.get("last_start"):
            continue
        last = _day_number(b["last_start"])
        if last is not None and last - w.days_played <= SOON:
            do.append({"kind": "cc", "title": f"{slot['name']} for the {slot['bundle']} bundle",
                       "text": f"{b['label']}: last safe day {b['last_start']}"})
    turn_in = sum(len(r["items"]) for r in errands.community_center(farm)["rooms"])
    if turn_in:
        do.append({"kind": "errand", "errand": "cc", "title": f"Take {turn_in} things to the Community Center",
                   "text": "you hold them for open bundles"})
    museum = len(errands.gunther(farm)["take"])
    if museum:
        do.append({"kind": "errand", "errand": "gunther", "title": f"Donate {museum} new finds to Gunther",
                   "text": "the museum doesn't have them yet"})
    geodes = errands.clint(farm)["geodes"]
    if geodes:
        n = sum(g["held"] for g in geodes)
        do.append({"kind": "errand", "errand": "clint", "title": f"Crack {n} geode{'s' if n != 1 else ''} at Clint's",
                   "text": "a lucky day for it" if s.daily_luck > 0.02 else ""})

    week = []
    for d, events in farm.calendar.days(w, 8):
        if d.days_played == w.days_played:
            continue
        for e in events:
            week.append({"date": farm.label(d.days_played).rsplit(",", 1)[0], "kind": e.kind, "label": e.label,
                         "sure": e.sure})
    todays = [a for a in agenda or [] if a["n"] == w.days_played]
    events = farm.calendar.day(w, today_days_played=w.days_played)
    return {"date": farm.label(w.days_played), "weekday": WEEKDAYS[(w.days_played - 1) % 7],
            "day": _schedule(farm, do, todays, events), "route": todays,
            "weather": s.weather, "tomorrow": s.weather_tomorrow, "weather_words": weather,
            "money": s.money, "luck": s.daily_luck, "mood": mood, "mood_means": means,
            "today": today, "do": do, "first": today + do, "week": week,
            "cc": {"deadline": plan["deadline"], "counts": plan["counts"], "gold": plan["gold"],
                   "bundles_done": sum(b.done for b in farm.bundles.all), "bundles": len(farm.bundles.all)}}


DAY_START, DAY_END, EVENING = 600, 2600, 2000
ERRAND = 60  # minutes allowed for walking to a shop and back and doing the business (a planning choice)


def _minutes(t: int) -> int:
    return t // 100 * 60 + t % 100


def _clock(m: int) -> int:
    return m // 60 * 100 + m % 60


def _schedule(farm: Farm, do: list[dict], todays: list[dict], events) -> dict:
    """A suggested order for the day: the farm first, then each errand inside its shop's hours (the earliest to
    close first), then the spare hours for the route's chopping or for earning, then the evening. Shops open
    today are listed with their hours. The order is a planning suggestion; the hours are the game's."""
    hours = {x["id"]: x for x in farm.hours_today()}
    blocks: list[dict] = []
    chores = [x["title"] for x in do if x["kind"] == "crops" and not x["title"].startswith(tuple("0123456789"))]
    chores = [c for c in chores if c.startswith(("Water", "Harvest"))]
    ripe = {t["fruit"] for t in crops.fruit_trees(farm) if t["on_tree"]}
    chores += [f"Pick: {x['title']}" for x in do  # your own trees, when there's fruit on them
               if x["kind"] == "cc" and " tree" in x["text"] and x["title"].split(" for ")[0] in ripe]
    t = _minutes(DAY_START)
    fest = next((e for e in events if e.kind == "festival" and e.start), None)
    if chores:
        end = t + min(180, 60 + 30 * len(chores))
        blocks.append({"start": _clock(t), "end": _clock(end), "title": "On the farm", "lines": chores,
                       "urgency": "now" if any(c.startswith("Water") for c in chores) else "soon"})
        t = end
    errands = [(a["shop"], a["text"], "soon") for a in todays if a.get("shop")]
    errands += [("Blacksmith", x["title"], "plenty") for x in do if x.get("errand") == "clint"]
    dish = farm.save.dish_of_the_day
    placed_shops = set()
    for shop, text, urgency in sorted(errands, key=lambda e: (hours.get(e[0], {}).get("spans") or [[0, 9999]])[0][1]):
        spans = (hours.get(shop) or {}).get("spans") or []
        for a, b in spans:
            start = max(t, _minutes(a))
            if start + ERRAND <= _minutes(b) and not (fest and _minutes(fest.start) <= start < _minutes(fest.end)):
                same = next((x for x in blocks if x.get("shop") == shop), None)
                if same:
                    same["lines"].append(text)
                else:
                    blocks.append({"start": _clock(start), "end": _clock(start + ERRAND),
                                   "title": hours[shop]["shop"], "lines": [text], "urgency": urgency, "shop": shop})
                    t = start + ERRAND
                placed_shops.add(shop)
                break
        else:
            name = hours.get(shop, {}).get("shop", shop)
            blocks.append({"start": None, "end": None, "title": text, "lines": [f"{name} isn't open in time today"],
                           "urgency": "now", "shop": shop})
    if fest:
        blocks.append({"start": fest.start, "end": fest.end, "title": fest.label,
                       "lines": [farm.place(fest.detail)] if fest.detail else [], "urgency": "plenty"})
    evening = _minutes(EVENING)
    spare_end = min(evening, _minutes(fest.start)) if fest and _minutes(fest.start) > t else evening
    if spare_end - t >= 60:
        busy = [a["text"] for a in todays if a["kind"] in ("chop", "mine", "fish", "get")]
        save = next((a for a in todays if a["kind"] == "save"), None)
        lines = busy or ["fish, forage or mine for gold" + (f": {save['text'][0].lower()}{save['text'][1:]}"
                                                           if save else "")]
        blocks.append({"start": _clock(t), "end": _clock(spare_end), "title": "The route" if busy else "Spare",
                       "lines": lines, "urgency": "soon" if busy else "spare"})
    if dish and (hours.get("Saloon") or {}).get("spans"):
        blocks.append({"start": EVENING, "end": EVENING + 100, "title": "The Saloon",
                       "lines": [f"{farm.name(dish[0])}, today's dish ({dish[1]} this morning)"], "urgency": "plenty"})
    shops = [{"id": x["id"], "name": x["shop"], "spans": x["spans"], "label": ", ".join(x["open"])}
             for x in hours.values() if x["spans"]]
    closed = [{"name": x["shop"], "why": x["closed"]} for x in hours.values() if not x["spans"] and x["closed"]]
    blocks.sort(key=lambda b: (b["start"] is None, b["start"] or 0))
    return {"from": DAY_START, "to": DAY_END, "blocks": blocks, "shops": shops, "closed": closed}


def _cart(farm: Farm) -> dict:
    """The cart today, and anything on it a bundle still needs."""
    days = farm.cart.days(farm.when, count_days=1, guarantee=farm.save.cart_guarantee)
    want = {s["item"] for s in cc.plan(farm)["slots"] if s["status"] != "have"}
    hits = [f"{i.name} ({i.price:,}g)" for d in days for i in d.items if i.item in want]
    place = " & ".join(farm.place(p) for p in days[0].place.split(" & ")) if days else "the Forest"
    return {"kind": "cart", "title": f"The Traveling Cart is at {place}, 6 AM to 8 PM",
            "text": f"It has what a bundle needs: {', '.join(hits)}" if hits else "nothing your bundles need today"}


def _time(t: int) -> str:
    h, m = divmod(t, 100)
    return f"{(h - 1) % 12 + 1}{f':{m:02d}' if m else ''} {'AM' if h < 12 or h == 24 else 'PM'}"


def _day_number(label: str) -> int | None:
    """'Fall 18, Year 1' -> days played."""
    try:
        season_day, year = label.split(", Year ")
        season, day = season_day.split()
        i = ("Spring", "Summer", "Fall", "Winter").index(season)
        return (int(year) - 1) * 112 + i * 28 + int(day)
    except ValueError:
        return None
