"""When each shop can be used: its door must be unlocked and (for most) its keeper at the counter (1.6.15).

There is no opening-hours table in the game. In our words:
- Doors: the outdoor maps give each shop's door a "LockedDoorWarp" tile
  action with an opening and closing time (GameLocation.lockedDoorWarp): you
  can go in from the opening time until just before the closing time. On a
  daytime festival (one starting before 7 PM) every door in the valley stays
  shut. Pierre's door is locked on Wednesdays until the Community Center is
  restored. Willy opens at 8 AM once he's sent his "new hours" letter. The
  town key opens valley doors at any hour. In Year 1, green rain leaves the
  doors in town and on the mountain unlocked all day.
- Counters: most shops open only when their keeper is in place
  (Utility.TryOpenShopMenu and the shop actions): Pierre on the tile behind
  his till; Gus anywhere behind the bar; Robin within 3 tiles of her counter;
  Marnie just behind hers (or any time once you've read the Animal
  Catalogue); Willy behind his counter; any villager behind the clinic desk;
  Clint and Sandy anywhere in their shop. Marlon's shop and JojaMart need
  no one.
- Where a keeper is comes from their schedule (schedules.py): they set off
  at each stop's time, so a window starts "about" then.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property

from .conditions import When, check, location_accessible
from .schedules import DaySchedule, Schedules, Situation, Stop

DAY_START, DAY_END = 600, 2600
DAYTIME_FESTIVAL_BEFORE = 1900
DOOR_MAPS = ("Town", "Mountain", "Forest", "Beach", "Desert")
OUTSIDE_VALLEY = {"SandyHouse"}  # the desert is its own place: valley festivals don't shut it
GREEN_RAIN_SHUT_MAPS = {"Beach", "Forest"}  # their doors keep their hours in green rain
WILLY_HOURS_MAIL = "willyHours"
ANIMAL_CATALOGUE_STAT = "Book_AnimalCatalogue"


def _rect(x: int, y: int, w: int, h: int) -> Callable[[Stop], bool]:
    return lambda s: x <= s.x < x + w and y <= s.y < y + h


@dataclass(frozen=True)
class Shop:
    id: str  # Data/Shops id
    name: str
    location: str  # the building
    owner: str | None  # who must be there: a villager, "Any" villager, or None (no one)
    at_counter: Callable[[Stop], bool] = lambda s: True  # given they're in `location`


SHOPS = (
    Shop("SeedShop", "Pierre's General Store", "SeedShop", "Pierre", _rect(4, 17, 1, 1)),
    Shop("Saloon", "The Stardrop Saloon", "Saloon", "Gus", _rect(9, 17, 10, 2)),
    Shop("Carpenter", "Carpenter's Shop", "ScienceHouse", "Robin", lambda s: ((s.x - 8) ** 2 + (s.y - 19) ** 2) <= 9),
    Shop("AnimalShop", "Marnie's Ranch", "AnimalShop", "Marnie", _rect(11, 14, 3, 1)),
    Shop("Blacksmith", "Blacksmith", "Blacksmith", "Clint"),
    Shop("FishShop", "Fish Shop", "FishShop", "Willy", lambda s: s.y <= 5),
    Shop("Hospital", "Harvey's Clinic", "Hospital", "Any", _rect(4, 15, 4, 1)),
    Shop("Sandy", "Oasis", "SandyHouse", "Sandy"),
    Shop("AdventureShop", "Adventurer's Guild", "AdventureGuild", None),
    Shop("Joja", "JojaMart", "JojaMart", None),
)


@dataclass(frozen=True)
class Door:
    map: str
    open: int
    close: int
    friend: str | None = None  # a villager whose friendship (points) lets you in outside winter
    friend_points: int = 0


@dataclass
class ShopDay:
    shop: Shop
    open: list[tuple[int, int]] = field(default_factory=list)  # windows when you can buy
    closed_why: str | None = None
    door: tuple[int, int] | None = None
    sure: bool = True  # False: a rain day whose schedule is a coin flip, or a keeper with two possible days


def _merge(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(windows):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        elif a < b:
            out.append((a, b))
    return out


def _intersect(windows: list[tuple[int, int]], lo: int, hi: int) -> list[tuple[int, int]]:
    return [(max(a, lo), min(b, hi)) for a, b in windows if min(b, hi) > max(a, lo)]


class Hours:
    def __init__(self, data):
        self.data = data
        self.schedules = Schedules(data)

    @cached_property
    def doors(self) -> dict[str, Door]:
        """Building -> its public door (the one without a friendship rule, if there are several)."""
        out: dict[str, Door] = {}
        for name in DOOR_MAPS:
            for layer in self.data.asset(f"Maps/{name}")["Layers"].values():
                for props in layer["Tiles"].values():
                    action = str(props.get("Action") or "").split()
                    if len(action) < 6 or action[0] != "LockedDoorWarp":
                        continue
                    door = Door(name, int(action[4]), int(action[5]),
                                action[6] if len(action) > 6 else None, int(action[7]) if len(action) > 7 else 0)
                    if action[3] not in out or (out[action[3]].friend_points and not door.friend_points):
                        out[action[3]] = door
        return out

    @cached_property
    def festivals(self) -> dict[tuple[str, int], tuple[str, int]]:
        out = {}
        for key, name in self.data.asset("Data/Festivals/FestivalDates").items():
            season = next(s for s in ("spring", "summer", "fall", "winter") if key.startswith(s))
            hours = (self.data.asset(f"Data/Festivals/{key}").get("conditions") or "").partition("/")[2].split()
            out[(season, int(key[len(season):]))] = (self.data.text(name), int(hours[0]) if hours else 900)
        return out

    def _windows(self, shop: Shop, npc: str, day: DaySchedule, when: When) -> list[tuple[int, int]]:
        """When `npc` is at `shop`'s counter on this schedule."""
        if day.start:
            here = day.start
        else:
            loc, x, y = self.schedules.home(npc, when)
            here = Stop(DAY_START, False, loc, x, y, 2)
        stops = [Stop(DAY_START, False, here.location, here.x, here.y, here.facing), *day.stops]
        out = []
        for i, st in enumerate(stops):
            end = stops[i + 1].time if i + 1 < len(stops) else DAY_END
            if st.location == shop.location and shop.at_counter(st):
                out.append((st.time, end))
        return _merge(out)

    def _keepers(self, shop: Shop, when: When) -> list[str]:
        if shop.owner != "Any":
            return [shop.owner]
        chars = self.data.asset("Data/Characters")
        return [n for n, c in chars.items()
                if self.schedules.raw(n) and check(c.get("UnlockConditions"), when) is not False]

    def day(self, shop: Shop, when: When, *, raining: bool | None = False, green_rain: bool = False,
            town_key: bool = False, stats: dict | None = None) -> ShopDay:
        out = ShopDay(shop)
        door = self.doors.get(shop.location)
        fest = self.festivals.get((when.season, when.day))
        in_valley = shop.location not in OUTSIDE_VALLEY
        if fest and fest[1] < DAYTIME_FESTIVAL_BEFORE and in_valley:
            out.closed_why = f"{fest[0]}: shops are shut"
            return out
        if shop.location == "JojaMart" and not location_accessible("JojaMart", when):
            out.closed_why = "JojaMart has closed for good"
            return out
        if shop.location == "SandyHouse" and not location_accessible("Desert", when):
            out.closed_why = "The desert isn't reachable yet (the bus needs repairing)"
            return out
        if shop.location == "SeedShop" and when.weekday == 3 and not town_key \
                and not location_accessible("CommunityCenter", when):
            out.closed_why = "Pierre's is shut on Wednesdays until the Community Center is restored"
            return out
        lo, hi = (door.open, door.close) if door else (DAY_START, DAY_END)
        if shop.location == "FishShop" and WILLY_HOURS_MAIL in when.mail:
            lo = 800
        if (town_key and in_valley) or (green_rain and when.year == 1 and door and door.map not in GREEN_RAIN_SHUT_MAPS
                                        and shop.location != "AdventureGuild"):
            lo, hi = DAY_START, DAY_END
        out.door = (lo, hi)
        if shop.owner is None or (shop.id == "AnimalShop" and (stats or {}).get(ANIMAL_CATALOGUE_STAT)):
            out.open = [(lo, hi)]
            return out
        windows = []
        for npc in self._keepers(shop, when):
            sit = Situation(when, hearts=when.hearts.get(npc, 0), raining=bool(raining), green_rain=green_rain)
            days = self.schedules.today(npc, sit)
            if raining is None:
                dry = self.schedules.today(npc, Situation(when, hearts=when.hearts.get(npc, 0)))
                wet = self.schedules.today(npc, Situation(when, hearts=when.hearts.get(npc, 0), raining=True))
                if [d.key for d in dry] != [d.key for d in wet]:
                    out.sure = False
                days = dry
            if len(days) > 1:
                out.sure = False
            windows += self._windows(shop, npc, days[0], when)
        out.open = _intersect(_merge(windows), lo, hi)
        if not out.open:
            out.closed_why = f"{shop.owner if shop.owner != 'Any' else 'No one'} isn't at the counter today"
        return out
