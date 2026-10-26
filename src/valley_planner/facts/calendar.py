"""What's on each day: festivals, birthdays, the cart, the bookseller, green rain and the Queen of Sauce.

How the game decides (1.6.15), in our words:
- Festivals: the days in Data/Festivals/FestivalDates; each festival's own
  file gives its map and hours ("Town/900 1400").
- Passive festivals (Data/PassiveFestivals): on their days when their
  condition holds (the Desert Festival needs the desert open); the calendar
  shows "???" for one whose condition fails. The Trout Derby (Summer 20-21)
  and SquidFest (Winter 12-13) are shown by the calendar's own code.
- Birthdays (Billboard.GetBirthdays): villagers who exist (their
  UnlockConditions hold: Kent from Year 2, Leo once he's on the mainland),
  unless their Calendar setting hides them always, or until you've met them
  (the Dwarf, Sandy, Krobus).
- The bookseller visits two days a season: a list of candidate days per
  season, one picked with a generator seeded from (year × 11, game id,
  season index), the other half the list further on.
- Green rain: one summer day a year, picked from 5, 6, 7, 14, 15, 16, 18, 23
  with a generator seeded from (year × 777, game id).
- Queen of Sauce: a new episode on Sundays, (days played % 224) / 7 (0 → 32),
  so the 32 episodes repeat every two years. Wednesday reruns (after day 7)
  pick, with the day's shop random, one of the episodes aired so far
  (weeks 1 to min((days played - 3) / 7, 32)) whose recipe you don't know —
  or any aired one if you know them all.
- The Traveling Cart: see cart.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .conditions import SEASONS, When, check
from .rng import NetRandom, day_save_random, random_seed

WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")  # day % 7
BOOKSELLER_DAYS = {"spring": (11, 12, 21, 22, 25), "summer": (9, 12, 18, 25, 27),
                   "fall": (4, 7, 8, 9, 12, 19, 22, 25), "winter": (5, 11, 12, 19, 22, 24)}
GREEN_RAIN_DAYS = (5, 6, 7, 14, 15, 16, 18, 23)
DERBIES = {("summer", 20): "TroutDerby", ("summer", 21): "TroutDerby",
           ("winter", 12): "SquidFest", ("winter", 13): "SquidFest"}
QOS_CYCLE = 224


@dataclass(frozen=True)
class Event:
    kind: str  # festival / passive / derby / birthday / cart / bookseller / green_rain / tv
    label: str
    detail: str = ""
    who: str | None = None  # villager, for birthdays
    start: int | None = None  # 900 = 9 AM
    end: int | None = None
    sure: bool = True  # False: depends on what you do before then (e.g. which recipes you learn)


def qos_sunday_episode(days_played: int) -> int:
    ep = days_played % QOS_CYCLE // 7
    return 32 if days_played % QOS_CYCLE == 0 else ep


def qos_rerun_episode(days_played: int, game_id: int, known: set[str], week_recipe: dict[int, str], *,
                      legacy: bool = False) -> int:
    aired = min((days_played - 3) // 7, 32)
    unknown = [w for w in range(1, aired + 1) if week_recipe.get(w) not in known]
    rng = day_save_random(days_played, game_id, legacy=legacy)
    if not unknown:
        return max(1, 1 + rng.next(aired))
    return unknown[rng.next(len(unknown))]


def bookseller_days(season: str, year: int, game_id: int, *, legacy: bool = False) -> tuple[int, int]:
    days = BOOKSELLER_DAYS[season]
    i = NetRandom(random_seed(year * 11, game_id, SEASONS.index(season), legacy=legacy)).next(len(days))
    return days[i], days[(i + len(days) // 2) % len(days)]


def green_rain_day(year: int, game_id: int, *, legacy: bool = False) -> int:
    return NetRandom(random_seed(year * 777, game_id, legacy=legacy)).choose(GREEN_RAIN_DAYS)


class Calendar:
    def __init__(self, data):
        self.data = data

    @cached_property
    def festivals(self) -> dict[tuple[str, int], tuple[str, str, int, int]]:
        """(season, day) -> (id, name, location, start, end)."""
        out = {}
        for key, name in self.data.asset("Data/Festivals/FestivalDates").items():
            season = next(s for s in SEASONS if key.startswith(s))
            fest = self.data.asset(f"Data/Festivals/{key}")
            where, _, hours = (fest.get("conditions") or "").partition("/")
            start, end = (int(x) for x in hours.split()[:2]) if hours else (None, None)
            out[(season, int(key[len(season):]))] = (key, self.data.text(fest.get("name") or name), where, start, end)
        return out

    @cached_property
    def passive(self) -> dict:
        return self.data.asset("Data/PassiveFestivals")

    @cached_property
    def characters(self) -> dict:
        return self.data.asset("Data/Characters")

    @cached_property
    def week_recipe(self) -> dict[int, str]:
        return {int(k): v.split("/")[0] for k, v in self.data.asset("Data/TV/CookingChannel").items()}

    def birthdays(self, when: When) -> list[str]:
        out = []
        for name, c in self.characters.items():
            if (c.get("BirthSeason") or "").lower() != when.season or c.get("BirthDay") != when.day:
                continue
            calendar = c.get("Calendar") or "AlwaysShown"
            if calendar == "HiddenAlways" or (calendar == "HiddenUntilMet" and name not in when.hearts):
                continue
            if check(c.get("UnlockConditions"), when) is False:
                continue
            out.append(name)
        return out

    def day(self, when: When, *, today_days_played: int | None = None) -> list[Event]:
        """Everything on `when`. `today_days_played`: the save's day, so later Wednesdays are marked unsure."""
        w, out = when, []
        fest = self.festivals.get((w.season, w.day))
        if fest:
            out.append(Event("festival", fest[1], fest[2], start=fest[3], end=fest[4]))
        for fid, p in self.passive.items():
            if (p.get("Season") or "").lower() != w.season or not p["StartDay"] <= w.day <= p["EndDay"]:
                continue
            if (w.season, w.day) in DERBIES and DERBIES[(w.season, w.day)] == fid:
                name = self.data.text(f"[LocalizedText Strings\\1_6_Strings:{fid}]") or fid
                out.append(Event("derby", name, start=p.get("StartTime")))
            elif p.get("ShowOnCalendar"):
                ok = check(p.get("Condition"), w)
                if ok is not False:
                    out.append(Event("passive", self.data.text(p.get("DisplayName")) or fid, start=p.get("StartTime"),
                                     sure=ok is True))
        for name in self.birthdays(w):
            c = self.characters[name]
            out.append(Event("birthday", f"{self.data.text(c.get('DisplayName')) or name}'s birthday", who=name))
        if w.day % 7 % 5 == 0:
            out.append(Event("cart", "Traveling Cart", "Cindersap Forest", start=600, end=2000))
        if w.game_id is not None:
            if w.day in bookseller_days(w.season, w.year, w.game_id, legacy=w.legacy_random):
                out.append(Event("bookseller", "Bookseller", "Pelican Town"))
            if w.season == "summer" and w.day == green_rain_day(w.year, w.game_id, legacy=w.legacy_random):
                out.append(Event("green_rain", "Green rain"))
        weekday = WEEKDAYS[w.day % 7]
        if weekday == "Sun":
            ep = qos_sunday_episode(w.days_played)
            out.append(Event("tv", f"Queen of Sauce: {self.week_recipe.get(ep, '?')}", f"episode {ep}"))
        elif weekday == "Wed" and w.days_played > 7 and w.game_id is not None:
            ep = qos_rerun_episode(w.days_played, w.game_id, w.cooking_recipes, self.week_recipe,
                                   legacy=w.legacy_random)
            later = today_days_played is not None and w.days_played > today_days_played
            out.append(Event("tv", f"Queen of Sauce rerun: {self.week_recipe.get(ep, '?')}", f"episode {ep}",
                             sure=not later))
        return out

    def days(self, when: When, count_days: int = 28):
        """(When, events) for each day from `when`. Later Wednesday reruns assume you watch every
        Sunday show before them (and so know its recipe); they stay marked unsure."""
        known = set(when.cooking_recipes)
        for dp in range(when.days_played, when.days_played + count_days):
            w = when.on(dp, cooking_recipes=set(known))
            yield w, self.day(w, today_days_played=when.days_played)
            if dp > when.days_played and w.day % 7 == 0:
                known.add(self.week_recipe.get(qos_sunday_episode(dp), ""))
