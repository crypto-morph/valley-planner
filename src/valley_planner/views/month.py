"""The Calendar: a month of everything that can be known ahead, and the watch on Red Cabbage.

Red Cabbage is the one Community Center item that can't be grown in Year 1 from a shop: Pierre sells the seeds from
Summer of Year 2, so before then it's the cart or nothing. So it has its own watch: what you hold, the next visit
that sells the crop or seeds you can still plant, and a banner for the week before that visit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..engine import cc
from ..facts import night_events, special_orders, weather
from ..facts.conditions import date_of
from . import crops, levels, picking
from .farm import Farm
from .morning import _bins_ahead

CABBAGE = "(O)266"
CABBAGE_SEEDS = "(O)485"
CABBAGE_DAYS = 9  # Data/Crops 485: 2 + 1 + 2 + 2 + 2
LAST_PLANT = 28 - CABBAGE_DAYS  # the last summer day that still ripens
BANNER_DAYS = 7
SEASON_DAYS = 28
YEAR_DAYS = 112
PIERRE_SUMMER = YEAR_DAYS + SEASON_DAYS + 1  # Summer 1 of Year 2, when Pierre stocks the seeds
MONTHS_AHEAD = 7  # the cart forecast below looks two years out
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")  # day 1 of every month is a Monday
BINS_AHEAD = 7  # further out, the odds depend on too many mornings' luck


@dataclass(frozen=True)
class Visit:
    days_played: int
    name: str
    price: int
    seeds: bool
    place: str


def _place(farm: Farm, place: str) -> str:
    return " & ".join(farm.place(p) for p in place.split(" & "))


def _cart_calendar(farm: Farm) -> dict:
    return farm.cart.calendar(farm.when, count_days=(MONTHS_AHEAD + 1) * SEASON_DAYS,
                              guarantee=farm.save.cart_guarantee)


def _plantable(days_played: int) -> bool:
    """Seeds are worth buying if there's still a summer ahead to grow them in, this year."""
    season, day, _ = date_of(days_played)
    return season == "spring" or (season == "summer" and day <= LAST_PLANT)


def _visits(farm: Farm) -> list[Visit]:
    cal = _cart_calendar(farm)
    out = [Visit(d.days_played, i.name, i.price, False, _place(farm, d.place)) for d, i in cal.get(CABBAGE, [])]
    out += [Visit(d.days_played, i.name, i.price, True, _place(farm, d.place)) for d, i in cal.get(CABBAGE_SEEDS, [])
            if _plantable(d.days_played)]
    return sorted(out, key=lambda v: v.days_played)


def _needed(farm: Farm) -> bool:
    return any(i.item == CABBAGE for b in farm.bundles.all for i in b.open_ingredients)


def _pierre(farm: Farm) -> dict:
    return {"state": "pierre", "banner": False, "level": "plain", "title": "No Red Cabbage at the cart in Year 1",
            "text": "The Dye bundle has to wait: Pierre sells the seeds from Summer of Year 2, ripe 9 days after "
                    f"planting. Plant by Summer {LAST_PLANT}."}


def red_cabbage(farm: Farm) -> dict | None:
    """Where you stand on the one item the cart alone can save you. None once the Dye bundle has it."""
    if not _needed(farm):
        return None
    w, s = farm.when, farm.save
    where = farm.where_held(CABBAGE)
    if where:
        return {"state": "held", "banner": False, "level": "green", "title": "You have your Red Cabbage",
                "text": f"It's in {', '.join(where)}. Don't sell it: it goes in the Dye bundle at the Community "
                        "Center's Bulletin Board."}
    if any(c.harvest_id == CABBAGE[3:] and not c.dead for c in s.crops):
        return {"state": "held", "banner": False, "level": "green", "title": "Your Red Cabbage is growing",
                "text": "Keep one for the Dye bundle, and don't sell it."}
    seeds = farm.where_held(CABBAGE_SEEDS)
    if seeds:
        return {"state": "held", "banner": False, "level": "green", "title": "You have Red Cabbage Seeds",
                "text": f"They're in {', '.join(seeds)}. Plant one by Summer {LAST_PLANT}, for the Dye bundle."}
    visits = [v for v in _visits(farm) if v.days_played < PIERRE_SUMMER or w.days_played >= PIERRE_SUMMER]
    if not visits:
        return _pierre(farm)
    v = visits[0]
    days = v.days_played - w.days_played
    date = farm.label(v.days_played).rsplit(",", 1)[0]
    short = v.price - s.money
    what = f"{v.name} {v.price:,}g, 6 AM to 8 PM at {v.place}"
    if v.seeds:
        what += f". Plant by Summer {LAST_PLANT}"
    money = f" You're {short:,}g short, so keep your gold." if short > 0 else f" Keep {v.price:,}g aside."
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    return {"state": "coming", "banner": days <= BANNER_DAYS, "level": "red" if days <= 1 else "amber",
            "days_left": days, "date": date, "title": f"Red Cabbage at the cart {when}, {date}",
            "text": f"{what}.{money} It's the only way to finish the Dye bundle before Year 2."}


def _spouse_free(farm: Farm, spouse: str) -> bool:
    f = farm.save.friends.get(spouse) if spouse else None
    return bool(f) and f.status not in ("Engaged", "Married")


def _last_rain(farm: Farm, first: int, spouse: str) -> int | None:
    """The last rainy day of this month's year, when the Old Mariner still matters: no rain comes in winter."""
    if not _spouse_free(farm, spouse):
        return None
    w = farm.when
    start = (first - 1) // YEAR_DAYS * YEAR_DAYS + 1
    wet = [d for d in range(max(start, w.days_played), start + YEAR_DAYS) if _weather(farm, d)[0] in ("rain", "storm")]
    return wet[-1] if wet else None


def _weather(farm: Farm, dp: int) -> tuple[str, bool]:
    season, day, _ = date_of(dp)
    return weather.forecast(dp, farm.when.game_id, festival=(season, day) in farm.calendar.festivals,
                            legacy=farm.when.legacy_random)


def _item(kind: str, title: str, text: str = "", *, important: bool = False, sure: bool = True) -> dict:
    return {"kind": kind, "title": title, "text": text, "important": important, "sure": sure}


def _events(farm: Farm, dp: int, spouse: str) -> list[dict]:
    """The calendar's own events for a day, in the words the page needs."""
    w = farm.when
    out = []
    known = farm.save.cooking_recipes
    for e in farm.calendar.day(w.on(dp), today_days_played=w.days_played):
        if e.kind == "tv":
            if e.label.split(": ", 1)[-1] not in known:
                out.append(_item("tv", e.label, "A recipe you don't know yet", sure=e.sure))
        elif e.kind == "birthday":
            if e.who == spouse:
                f = farm.save.friends.get(spouse)
                dating = f and f.status in ("Dating", "Engaged", "Married")
                out.append(_item("birthday", e.label, "A birthday gift counts 8 times."
                                 + ("" if dating else " Give the Bouquet first: without it hearts stop at 8."),
                                 important=True))
            else:
                out.append(_item("birthday", e.label, "A gift today counts 8 times."))
        elif e.kind == "cart":
            continue  # the cart row below says what's on it
        else:
            out.append(_item(e.kind, e.label, farm.place(e.detail) if e.kind == "festival" and e.detail else e.detail,
                             sure=e.sure))
    return out


def _cart(farm: Farm, dp: int, stock: dict, watch: dict | None, wants: dict) -> list[dict]:
    day = date_of(dp)[1]
    if day % 7 % 5 and not stock.get(dp):
        return []
    lines, names, urgent = [], [], False
    for item, price, name, left in stock.get(dp, []):
        if item in (CABBAGE, CABBAGE_SEEDS):
            if watch and watch["state"] != "held" and (item == CABBAGE or _plantable(dp)):
                lines.append(f"{name}, {price:,}g: the Dye bundle needs it and nowhere else sells it")
                names.append(name)
                urgent = True
            continue
        slot = wants.get(item)
        if slot and cc.cart_only(slot, left):
            lines.append(f"{name}, {price:,}g, for the {slot['bundle']} bundle: nothing else gets it in time")
            names.append(name)
            urgent = True
    title = f"Cart: {', '.join(names)}" if urgent else "Traveling Cart"
    return [_item("cart", title, ". ".join(lines) or "Nothing you can't get elsewhere", important=urgent)]


def _ripe(farm: Farm, dp: int, rows: list[dict]) -> list[dict]:
    today = farm.when.days_played
    return [_item("crops", f"{r['count']} {r['crop']} ripe", r["location"]) for r in rows
            if r["status"] in ("growing", "dies") and today + r["in_days"] == dp]


def _rain(farm: Farm, dp: int, spouse: str, last: int | None) -> list[dict]:
    kind, sure = _weather(farm, dp)
    if kind not in ("rain", "storm"):
        return []
    free = _spouse_free(farm, spouse)
    text = "No watering today."
    if free:
        text += " The Old Mariner is past the Beach bridge."
    if dp == last:
        return [_item(kind, "Last rain of the year", text + " After this it takes a Rain Totem or next Spring for "
                      "the Mermaid's Pendant.", important=True)]
    return [_item(kind, "Storm" if kind == "storm" else "Rain", text, sure=sure)]


def _season_end(farm: Farm, dp: int, dies: int) -> list[dict]:
    season, day, _ = date_of(dp)
    if day != SEASON_DAYS or season == "winter":
        return []
    lost = f"{dies} of your crops die" if dies and dp - farm.when.days_played < SEASON_DAYS else "crops die"
    return [_item("season", f"Last day of {season.title()}",
                  f"Out-of-season {lost} tonight. Harvest, place any Sprinklers on empty dirt, and sell first.",
                  important=True)]


def _level(row: dict) -> dict:
    what = f"{row['unlocks']} from {row['ready']}" if row["unlocks"] else ""
    if row["pick"]:
        what = f"Choose {row['pick']} at bedtime." + (" Hold your goods out of the bin tonight: its prices start "
                                                      "tomorrow." if row["hold_bin"] else "")
    return _item("level", f"{row['skill'].title()} {row['level']}", f"{what} {row['how'].capitalize()}.".strip(),
                 important=bool(row["pick"]), sure=row["sure"])


NIGHT_WORDS = {
    "meteorite": ("A meteorite lands on the farm overnight", "Break it with a Steel Pickaxe or better: Iridium Ore,"
                  " Stone and Coal, sometimes a Prismatic Shard."),
    "fairy": ("A crop fairy visits overnight", "She ripens a patch of one crop. Keep it watered."),
    "witch": ("The witch flies over", "She puts a Void Egg in a coop, if you have one."),
    "owl": ("An owl statue appears", "A small statue on the farm, to keep or sell."),
    "capsule": ("A strange capsule lands", "Something odd on the farm, worth a look."),
    "earthquake": ("The earthquake", "The landslide to the Railroad and the spa clears."),
    "windstorm": ("A windstorm", "It knocks something down on the farm."),
    "qi plane": ("Mr. Qi's plane flies over", "After it, Mystery Boxes start turning up."),
}


def _nights(farm: Farm, first: int) -> dict[int, dict]:
    """This month's overnight farm events, by the morning they land. They assume no Community Center room is
    finished before then: finishing the Pantry shifts every later night."""
    w = farm.when
    end = first + SEASON_DAYS - 1
    if end < w.days_played + 1:
        return {}
    out = {}
    for n in night_events.nights(farm.save, farm.data, count=end - w.days_played,
                                 festivals=set(farm.calendar.festivals)):
        if n.kind not in NIGHT_WORDS or not first <= n.days_played <= end:
            continue
        title, text = NIGHT_WORDS[n.kind]
        if n.kind == "meteorite" and not n.lands:
            text = f"Only if its landing spot is clear: right now it's {n.what or 'blocked'}." + " Clear it to get one."
        out[n.days_played] = _item("night", title, text, important=n.kind in ("meteorite", "fairy"),
                                   sure=n.sure)
    return out


BIG_ORDER = 2500  # gold that makes a board day worth marking


def _boards(farm: Farm, first: int) -> dict[int, dict]:
    """Lewis's board on the Mondays you can see it this month: what it will ask, if nothing changes first."""
    end = first + SEASON_DAYS - 1
    weeks = max(0, (end - farm.when.days_played) // 7 + 1)
    out = {}
    for b in special_orders.forecast(farm.save, farm.data, mondays=weeks) if weeks else []:
        if not b.visible or not b.orders or not first <= b.opens <= end:
            continue
        lines = [f"{o.requester}: {o.requirement}, {o.reward:,}g" for o in b.orders]
        rich = any(o.reward >= BIG_ORDER for o in b.orders)
        out[b.opens] = _item("order", "Special orders board", ". ".join(lines) + ". You can take one at a time.",
                             important=rich, sure=b.sure)
    return out


def _quests(farm: Farm, dp: int, log: list[dict]) -> list[dict]:
    today = farm.when.days_played
    return [_item("quest", q["title"], "Last day") for q in log
            if q.get("days_left") is not None and today + q["days_left"] == dp]


def _closest(farm: Farm) -> str:
    """Who "whoever you're closest to" means today, as the route's own setting does."""
    romantic = [n for n, c in farm.data.asset("Data/Characters").items() if c.get("CanBeRomanced")]
    known = [n for n in romantic if n in farm.save.friends]
    return max(known, key=lambda n: farm.save.friends[n].points, default="")


def view(farm: Farm, offset: int = 0, spouse: str = "") -> dict:
    from . import quests
    w = farm.when
    spouse = spouse or _closest(farm)
    offset = max(0, min(offset, MONTHS_AHEAD))
    first = ((w.days_played - 1) // SEASON_DAYS + offset) * SEASON_DAYS + 1
    season, _, year = date_of(first)
    watch = red_cabbage(farm)
    plan = cc.plan(farm)
    wants = {s["item"]: s for s in plan["slots"] if s["status"] != "have"}
    stock: dict[int, list] = {}
    cal = _cart_calendar(farm)
    for item in {*wants, CABBAGE, CABBAGE_SEEDS}:
        for d, i in cal.get(item, []):
            stock.setdefault(d.days_played, []).append((item, i.price, i.name, i.stock))
    mine = crops.mine(farm)
    log = quests.view(farm)["quests"]
    last = _last_rain(farm, first, spouse)
    coming = levels.forecast(farm)
    giants = picking.giants(farm) if offset == 0 else []
    nights = _nights(farm, first)
    boards = _boards(farm, first)
    days = []
    for dp in range(first, first + SEASON_DAYS):
        past = dp < w.days_played
        items: list[dict] = []
        if not past:
            items = (_events(farm, dp, spouse) + _cart(farm, dp, stock, watch, wants) + _ripe(farm, dp, mine["rows"])
                     + _rain(farm, dp, spouse, last) + _quests(farm, dp, log)
                     + [_level(r) for r in coming if r["day"] == dp]
                     + ([nights[dp]] if dp in nights else []) + ([boards[dp]] if dp in boards else [])
                     + [_item("giant", f"Giant {g['crop']} possible", g["text"], important=g["complete"],
                              sure=False) for g in giants if g["days_played"] == dp]
                     + _season_end(farm, dp, mine["dies"]))
            if w.days_played <= dp <= w.days_played + BINS_AHEAD:
                bins = _bins_ahead(farm, dp)
                if bins:
                    items.append(_item("bins", bins.split(":", 1)[0], bins.split(": ", 1)[-1]))
            items.sort(key=lambda x: not x["important"])
        days.append({"day": dp - first + 1, "date": farm.label(dp).rsplit(",", 1)[0], "today": dp == w.days_played,
                     "past": past, "items": items})
    return {"label": f"{season.title()}, Year {year}", "offset": offset, "max_offset": MONTHS_AHEAD,
            "weekdays": list(WEEKDAYS), "days": days, "watch": watch,
            "important": [{"day": d["day"], "date": d["date"], "title": x["title"], "kind": x["kind"]}
                          for d in days for x in d["items"] if x["important"]]}
