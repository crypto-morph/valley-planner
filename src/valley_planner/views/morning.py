"""Morning: what happens today, what to react to, and what to get done, plus the week ahead.

"Happening today" is the day itself: a birthday (with a loved gift you hold, and which chest it's in), a
festival, the Queen of Sauce, the Traveling Cart (and anything on it your bundles need), the bookseller, the
Saloon's dish, shops that are shut, the garbage cans with something in them (exact today, odds for the week
ahead, since a future day's luck can't be known), the weather today and tomorrow, and the spirits' mood (the TV
fortune: TV.getFortuneForecast, luck below -0.07 / -0.02, above 0.02 / 0.07, the extremes at ±0.12).
"Get done" is the farm and the errands: crops ready or dry, crops that won't finish before the season ends,
Community Center items with a last safe day close, things you hold for open bundles, the museum, geodes.
The route's own steps for today are added by the page from the Route tab's goals.

"Priorities" is a short, ranked list of things with a clock on them that aren't already in today's plan (the
dayline below handles today's own chores): a Community Center item's last safe day, a special order or quest
running out, a birthday tomorrow, gold still short of the Community Center with its deadline close. The tag
on each is the days left, in Route's own words ("this week" = now, "1-2 weeks" = soon). Two sources have no
clock at all — anyone capped on hearts for want of a Bouquet or the Pendant, and the single best "worth
getting" machine from the Sell tab — and sort to the bottom, styled plainly so they don't read as urgent.
Each points at its tab (or opens the errand card) for the full picture.
"""

from __future__ import annotations

import re

from ..engine import cc
from ..facts import romance
from ..facts.conditions import clock_of as _clock
from ..facts.conditions import minutes_of as _minutes
from . import crops, errands, sell
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
        elif e.kind == "bookseller":
            from .month import bookseller_text  # month imports morning
            today.append({"kind": e.kind, "title": e.label, "text": bookseller_text(farm, s.days_played)[0],
                          "spots": [{"loc": "Town", "x": 109, "y": 27, "label": "Bookseller"}]})
        elif e.kind == "green_rain":
            today.append({"kind": e.kind, "title": e.label, "text": farm.place(e.detail) if e.detail else ""})
    if s.dish_of_the_day:
        qid, n = s.dish_of_the_day
        saloon = next((x for x in farm.hours_today() if x["id"] == "Saloon"), {})
        today.append({"kind": "dish", "title": f"The Saloon's dish of the day: {farm.name(qid)}",
                      "text": f"{n} this morning" + (f", but the Saloon is out of reach ({saloon['closed']})"
                                                    if saloon.get("closed") else "")})
    today.append(_bins(farm))
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
    jobs = dict(getattr(s, "building_days", {}))
    if getattr(s, "house_upgrade_days", 0):
        jobs["house upgrade"] = s.house_upgrade_days
    for name, left in jobs.items():
        do.append({"kind": "building", "title": f"Robin is still building your {name}",
                   "text": ("ready tomorrow" if left == 1 else f"ready in {left} days")
                   + ": she can't take another job until then"})
    for t in crops.fruit_trees(farm):
        if t["first_n"] and 0 < t["first_n"] - w.days_played <= SOON and not t["on_tree"]:
            do.append({"kind": "tree", "title": f"Your {t['fruit']} tree: {t['text']}", "text": t["where"]})
    orders = special_orders(farm)
    for o in orders:
        today.append({"kind": "order", "title": f"Special order: {o['name']} ({o['who']})", "text": o["text"]})
        if o["hunt"]:
            do.append({"kind": "order", "title": "Hunt the prismatic slime in the Mines", "text": o["hunt"]})
    plan = cc.plan(farm)
    growing = _growing(farm)
    for slot in plan["slots"]:
        b = slot["best"]
        if not b or slot["status"] in ("have", "stuck") or not b.get("last_start") or slot["name"] in growing:
            continue
        if _out_of_reach(b):
            continue
        last = _day_number(b["last_start"])
        if last is not None and last - w.days_played <= SOON:
            do.append({"kind": "cc", "title": f"{slot['name']} for the {slot['bundle']} bundle",
                       "text": f"{b['label']}: last safe day {b['last_start']}"})
    fest = farm.hours.festivals.get((w.season, w.day))
    town_shut = bool(fest and fest[2] == "Town" and fest[1] >= 1900)  # the evening festival keeps you out of town
    later = f" (not until {_time(fest[1])}: {fest[0]})" if town_shut else ""
    turn_in = 0  # the bundles can't be filled until the Wizard's lets you read the Junimos' notes
    if "canReadJunimoText" in s.mail:
        turn_in = sum(1 for r in errands.community_center(farm)["rooms"] for i in r["items"] if i["open"])
    if turn_in:
        do.append({"kind": "errand", "errand": "cc", "title": f"Take {turn_in} things to the Community Center",
                   "text": "you hold them for open bundles" + later})
    museum = len(errands.gunther(farm)["take"])
    if museum:
        do.append({"kind": "errand", "errand": "gunther", "title": f"Donate {museum} new finds to Gunther",
                   "text": "the museum doesn't have them yet" + later})
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
        bins = _bins_ahead(farm, d.days_played)
        if bins:
            week.append({"date": farm.label(d.days_played).rsplit(",", 1)[0], "kind": "bins", "label": bins,
                         "sure": True})
    todays = [a for a in agenda or [] if a["n"] == w.days_played]
    todays += [{"kind": "deliver", "text": o["deliver"], "shop": "", "n": w.days_played}
               for o in orders if o["deliver"]]
    from . import quests as quest_view  # quests reads this module's helpers
    log = quest_view.view(farm)
    todays += [{"kind": "deliver", "text": f"{q['deliver_to']}: bring {q['who']} the {q['item']} ({q['title']})",
                "shop": "", "n": w.days_played} for q in log["quests"] if q["deliver_to"]]
    for q in log["quests"]:
        if q["days_left"] is not None and q["days_left"] <= 1 and not q["deliver_to"]:
            when = "last day" if q["days_left"] <= 0 else "ends tomorrow"
            do.append({"kind": "quest", "title": f"{q['title']}: {when}", "text": q["objective"]})
    todays += [{"kind": "mine", "text": "the Mines: hunt the prismatic slime on slime floors (1–29, 41–79)",
                "shop": "", "n": w.days_played} for o in orders if o["hunt"]]
    events = farm.calendar.day(w, today_days_played=w.days_played)
    cc_info = {"deadline": plan["deadline"], "counts": plan["counts"], "gold": plan["gold"],
              "bundles_done": sum(b.done for b in farm.bundles.all), "bundles": len(farm.bundles.all)}
    return {"date": farm.label(w.days_played), "weekday": WEEKDAYS[(w.days_played - 1) % 7],
            "day": _schedule(farm, do, todays, events), "route": todays, "quests": log,
            "weather": s.weather, "tomorrow": s.weather_tomorrow, "weather_words": weather,
            "money": s.money, "luck": s.daily_luck, "mood": mood, "mood_means": means,
            "today": today, "do": do, "first": today + do, "week": week, "cc": cc_info,
            "priorities": _priorities(farm, mine, plan, cc_info, orders, log, held)}


SEVERITY = {"now": 0, "soon": 1, "plenty": 2}
MAX_PRIORITIES = 6
DEADLINE_WINDOW = 13  # a deadline further out than this (Route's own "2+ weeks spare") isn't worth a card yet
WORTH_GETTING = 200  # a "worth getting" hint has to clear this much gold to be worth a mention


def _severity(days: int) -> str:
    """Route's own bands, so the same colour means the same thing on both tabs: this week, 1-2 weeks, more."""
    return "now" if days <= 6 else "soon" if days <= DEADLINE_WINDOW else "plenty"


def _tag(days: int) -> str:
    return "TODAY" if days <= 0 else "TOMORROW" if days == 1 else f"{days} DAYS"


def _priorities(farm: Farm, mine: dict, plan: dict, cc_info: dict, orders: list[dict], quests_log: dict,
                held: dict) -> list[dict]:
    """A short, ranked list of things with a clock on them, not already covered by today's dayline. Sources
    with no clock (a capped romance partner, the best unowned machine from Sell) sort last and carry no
    day-count tag, so they don't compete for attention with what's actually running out."""
    w = farm.when
    out: list[dict] = []

    def add(kind: str, severity: str, title: str, text: str, tag: str, **link) -> None:
        out.append({"kind": kind, "severity": severity, "title": title, "text": text, "tag": tag, **link})

    if mine["dies"]:
        left = 28 - (w.days_played - 1) % 28
        add("crops", _severity(left), f"{mine['dies']} crops won't ripen before {w.season.title()} ends",
            "don't spend more on them", _tag(left), tab="crops")

    growing = _growing(farm)
    for slot in plan["slots"]:
        b = slot["best"]
        if not b or slot["status"] in ("have", "stuck") or not b.get("last_start") or slot["name"] in growing:
            continue
        if _out_of_reach(b):
            continue
        last = _day_number(b["last_start"])
        gate = [u["label"] for u in b.get("unlock") or [] if u.get("gold") or u.get("days")]
        if gate and last is not None:
            ready = _day_number(b.get("earliest_after_unlock") or "")
            if ready is not None and ready > last:
                continue  # the gate can't open before the season ends: nothing to rush for this year
            lead = sum(u.get("days") or 0 for u in b["unlock"])
            last -= lead  # the upgrade has to start this many days earlier
        days = None if last is None else last - w.days_played
        if days is not None and 0 <= days <= DEADLINE_WINDOW:
            text = b["label"] + (f", once you have {' and '.join(gate)} ({b['unlock_gold']:,}g)" if gate else "")
            add("cc", _severity(days), f"{slot['name']} for the {slot['bundle']} bundle", text, _tag(days),
                errand="cc")
    if cc_info["bundles_done"] < cc_info["bundles"] and cc_info["gold"]["short"] > 0:
        deadline = _day_number(cc_info["deadline"])
        days = None if deadline is None else deadline - w.days_played
        if days is not None and 0 <= days <= DEADLINE_WINDOW:
            add("cc", _severity(days), f"{cc_info['gold']['short']:,}g short of the Community Center",
                "the Vault and what's left to unlock", _tag(days), errand="cc")

    for o in orders:
        if o["days_left"] is not None and 0 <= o["days_left"] <= DEADLINE_WINDOW:
            add("order", _severity(o["days_left"]), f"{o['name']} ({o['who']})", o["text"].split(" · ")[0],
                _tag(o["days_left"]))

    for q in quests_log["quests"]:
        if q["days_left"] is not None and not q["deliver_to"] and 0 <= q["days_left"] <= DEADLINE_WINDOW:
            add("quest", _severity(q["days_left"]), q["title"], q["objective"], _tag(q["days_left"]))

    for npc in farm.calendar.birthdays(w.on(w.days_played + 1)):
        has = any(farm.gifts.giftable(q) and farm.gifts.taste(npc, q) in ("love", "like") for q in held)
        add("birthday", "soon", f"{npc}'s birthday tomorrow",
            "you hold a gift for them" if has else "you hold nothing they love or like yet", "TOMORROW")

    for p in _capped_partners(farm):
        item = "the Mermaid's Pendant" if p["dating"] else "a Bouquet"
        add("romance", "plenty", f"{p['name']} is capped at {p['hearts']}♥", f"give them {item} to raise it further",
            "CAPPED", tab="romance", target=p["name"])

    hints = [h for h in sell.view(farm)["hints"] if _can_build(farm, h)]
    if hints and hints[0]["gain_total"] >= WORTH_GETTING:
        h = hints[0]
        add("sell", "plenty", f"Worth getting: a {h['machine']}",
            f"about {h['gain_total']:,}g more on the {h['name']} you already hold", "NO DEADLINE",
            tab="sell", anchor="sell-hints-panel")

    out.sort(key=lambda p: SEVERITY[p["severity"]])
    return out[:MAX_PRIORITIES]


def _capped_partners(farm: Farm) -> list[dict]:
    """Anyone you could date (or are dating) who's hit the friendship cap and needs a Bouquet or the Pendant."""
    s = farm.save
    out = []
    for name, c in farm.data.asset("Data/Characters").items():
        if not c.get("CanBeRomanced"):
            continue
        f = s.friends.get(name)
        if not f or f.status in ("Engaged", "Married"):
            continue
        dating = f.status == "Dating"
        if f.points >= (romance.CAP_DATING if dating else romance.CAP_FRIEND):
            out.append({"name": name, "hearts": f.hearts, "dating": dating})
    return out


DAY_START, DAY_END, EVENING = 600, 2600, 2000
ERRAND = 60  # minutes allowed for walking to a shop and back and doing the business (a planning choice)


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
            why = hours.get(shop, {}).get("closed") or f"{name} isn't open in time today"
            blocks.append({"start": None, "end": None, "title": text, "lines": [f"not today: {why}"],
                           "urgency": "now", "shop": shop})
    if fest:
        blocks.append({"start": fest.start, "end": fest.end, "title": fest.label,
                       "lines": [farm.place(fest.detail)] if fest.detail else [], "urgency": "plenty"})
    evening = _minutes(EVENING)
    spare_end = min(evening, _minutes(fest.start)) if fest and _minutes(fest.start) > t else evening
    if spare_end - t >= 60:
        picked = any(c.startswith("Pick: ") for c in chores)  # the farm block already picks your own trees
        busy = [a["text"] for a in todays if a["kind"] in ("chop", "mine", "fish", "get", "deliver")
                and not (picked and " tree" in a["text"])]
        save = next((a for a in todays if a["kind"] == "save"), None)
        lines = busy or ["fish, forage or mine for gold" + (f": {save['text'][0].lower()}{save['text'][1:]}"
                                                           if save else "")]
        title = "Spare" if not busy else "The route" if any(a["kind"] != "deliver" for a in todays
                                                             if a["text"] in busy) else "Errands"
        blocks.append({"start": _clock(t), "end": _clock(spare_end), "title": title,
                       "lines": lines, "urgency": "soon" if busy else "spare"})
    if dish and _minutes(((hours.get("Saloon") or {}).get("spans") or [[0, 0]])[-1][1]) > _minutes(EVENING):
        blocks.append({"start": EVENING, "end": EVENING + 100, "title": "The Saloon",
                       "lines": [f"{farm.name(dish[0])}, today's dish ({dish[1]} this morning)"], "urgency": "plenty"})
    shops = [{"id": x["id"], "name": x["shop"], "spans": x["spans"], "label": ", ".join(x["open"])}
             for x in hours.values() if x["spans"]]
    closed = [{"name": x["shop"], "why": x["closed"]} for x in hours.values() if not x["spans"] and x["closed"]]
    blocks.sort(key=lambda b: (b["start"] is None, b["start"] or 0))
    return {"from": DAY_START, "to": DAY_END, "blocks": blocks, "shops": shops, "closed": closed}


PRISMATIC_ORDER = "Wizard2"  # its slimes only turn prismatic while this order is active
PRISMATIC_BASE, PRISMATIC_FLOOR = 0.012, 0.01  # MineShaft.populateLevel: per slime, + luck / 10, at least 1%
HOMES = {"Wizard": "the Wizard's tower", "Lewis": "Mayor Lewis's house", "Robin": "Robin's", "Pierre": "Pierre's",
         "Clint": "Clint's", "Willy": "Willy's shop", "Demetrius": "Robin's", "Gus": "the Saloon",
         "Caroline": "Pierre's", "Emily": "the Saloon", "Evelyn": "1 River Road", "Gunther": "the museum",
         "Marnie": "Marnie's Ranch", "Pam": "the trailer", "Harvey": "the clinic", "Linus": "Linus's tent"}


def special_orders(farm: Farm) -> list[dict]:
    """The special orders you've taken that are still running: what's next, and the days left."""
    strings = farm.data.asset("Strings/SpecialOrderStrings") or {}

    def text(token: str) -> str:
        return strings.get(token.strip("[]"), token) if token.startswith("[") else token
    out, today = [], farm.when.days_played
    for o in getattr(farm.save, "special_orders", []):
        if o["state"] != "InProgress":
            continue
        left = o["due_date"] - today
        nxt = next((ob for ob in o["objectives"] if ob["current"] < ob["max"]), None)
        step = text(nxt["text"]) if nxt else "everything's done: hand it in"
        if nxt and nxt["max"] > 1:
            step += f" ({nxt['current']} of {nxt['max']})"
        who = o["requester"]
        place = HOMES.get(who, who)
        hunt = ""
        if o["key"] == PRISMATIC_ORDER and nxt and nxt["type"] == "SlayObjective":
            chance = max(PRISMATIC_FLOOR, PRISMATIC_BASE + farm.save.daily_luck / 10)
            hunt = (f"each slime on a floor you enter has a {chance:.1%} chance today (luck moves it), one per floor "
                    "at most; re-entering a floor rolls again, and slime infestations are the best bet")
        deliver = f"{place}: {step[0].lower()}{step[1:]}" if nxt and nxt["type"] == "DeliverObjective" else ""
        when = "last day today" if left <= 0 else f"{left} days left"
        out.append({"key": o["key"], "name": text(o["name"]), "who": f"the {who}" if who == "Wizard" else who,
                    "text": f"next: {step} · {when} (until {farm.label(o['due_date'])})",
                    "hunt": hunt, "deliver": deliver, "days_left": left})
    return out


def _growing(farm: Farm) -> set[str]:
    """What's already in the ground, by name: a slot for one of these isn't waiting on you to start it."""
    return {farm.name(f"(O){c.harvest_id}") for c in farm.save.crops if not c.dead and not c.forage}


def _can_build(farm: Farm, hint: dict) -> bool:
    """False while a step needs a skill level you haven't reached."""
    for st in hint["steps"]:
        m = re.match(r"(\w+) level (\d+)", st.get("how") or "", re.I)
        if m and farm.save.skills.get(m.group(1).lower(), 0) < int(m.group(2)):
            return False
    return True


def _out_of_reach(way: dict) -> bool:
    """A way through the Desert or the Island: not somewhere you can go yet, so no deadline to worry about."""
    return any(word in str(x) for x in way.get("blocked") or [] for word in ("bus", "boat"))


def _can_item(can) -> str:
    return f"{can.loot.label} or {can.other.label}" if can.other else can.loot.label


def _bins(farm: Farm) -> dict:
    """The garbage cans with something in them today: exact, since today's luck is in the save."""
    full = [c for c in farm.bins.day(farm.save, farm.when) if c.loot]
    if not full:
        return {"kind": "bins", "title": "Every garbage can is empty today", "text": ""}
    n = len(full)
    marks = {m.name.removeprefix("Garbage:"): m for m in farm.walker.landmarks.get("Town", [])
             if m.name.startswith("Garbage:")}
    return {"kind": "bins", "title": f"{n} garbage can{'s have' if n != 1 else ' has'} something today",
            "text": " · ".join(f"{c.place}: {_can_item(c)}" for c in full),
            "spots": [{"loc": "Town", "x": marks[c.can].x, "y": marks[c.can].y, "label": c.place}
                      for c in full if c.can in marks]}


def _bins_ahead(farm: Farm, days_played: int) -> str:
    """Another day's cans: certain ones first, then those that hang on the day's luck, likeliest first."""
    cans = sorted((c for c in farm.bins.day(farm.save, farm.when.on(days_played)) if c.loot), key=lambda c: -c.odds)
    parts = [f"{c.place}: {_can_item(c)}" + ("" if c.odds == 1 else f" ({round(c.odds * 100)}%)") for c in cans]
    return f"Bins: {', '.join(parts)}" if parts else ""


CART_TILE = (23, 10)  # Forest.GetTravelingMerchantCartTile without a TravelingCartPosition map property


def _cart_counter(farm: Farm) -> dict:
    """Where you stand to buy: the cart's counter is 4 east and 1 south of its tile; you stand just below."""
    raw = (farm.data.asset("Maps/Forest").get("Properties") or {}).get("TravelingCartPosition")
    x, y = (int(v) for v in str(raw).split()[:2]) if raw else CART_TILE
    return {"x": x + 4, "y": y + 2}


def _cart(farm: Farm) -> dict:
    """The cart today, and anything on it a bundle still needs."""
    days = list(farm.cart.days(farm.when, count_days=1, guarantee=farm.save.cart_guarantee))
    want = {s["item"]: s for s in cc.plan(farm)["slots"] if s["status"] != "have"}
    hits = [f"{i.name} ({i.price:,}g)" for d in days for i in d.items
            if i.item in want and cc.cart_only(want[i.item], i.stock)]
    place = " & ".join(farm.place(p) for p in days[0].place.split(" & ")) if days else "the Forest"
    spots = [{"loc": "Forest", **_cart_counter(farm), "label": "Cart"}] if days and "Forest" in days[0].place else []
    return {"kind": "cart", "title": f"The Traveling Cart is at {place}, 6 AM to 8 PM",
            "text": f"Only the cart has this in time: {', '.join(hits)}" if hits
            else "nothing you can't get elsewhere", "spots": spots}


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
