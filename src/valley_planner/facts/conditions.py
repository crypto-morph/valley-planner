"""The game's condition language (game state queries), for shop stock, forage, fish and more.

A condition is a comma-separated list of queries, all of which must hold; a
query is a key and space-separated arguments (quotes allowed), negated with a
leading "!". We evaluate the queries a save can answer for a given day and
return None — "can't tell" — for the rest (random rolls, the player's
position…), never a guess. Checked against StardewValley.GameStateQuery.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field, replace

from .rng import synced_random

SEASONS = ("spring", "summer", "fall", "winter")
WEEKDAYS = {"mon": 1, "monday": 1, "tue": 2, "tuesday": 2, "wed": 3, "wednesday": 3, "thu": 4, "thursday": 4,
            "fri": 5, "friday": 5, "sat": 6, "saturday": 6, "sun": 0, "sunday": 0}
SEASON_KEYS = {"SEASON", "LOCATION_SEASON"}


@dataclass
class When:
    """The day and farm a condition is checked against."""

    season: str
    day: int
    year: int
    days_played: int
    mail: set[str] = field(default_factory=set)  # received
    mailbox: set[str] = field(default_factory=set)
    mail_tomorrow: set[str] = field(default_factory=set)
    events_seen: set[str] = field(default_factory=set)
    crafting_recipes: set[str] = field(default_factory=set)
    cooking_recipes: set[str] = field(default_factory=set)
    skills: dict[str, int] = field(default_factory=dict)
    house_upgrade: int = 0
    mine_lowest: int = 0
    museum_count: int = 0
    hearts: dict[str, int] = field(default_factory=dict)
    game_id: int | None = None  # seeds SYNCED_RANDOM rolls
    legacy_random: bool = False
    world_fields: dict[str, int] = field(default_factory=dict)  # WORLD_STATE_FIELD values known for this day

    @classmethod
    def from_save(cls, save, *, season: str | None = None, day: int | None = None, year: int | None = None,
                  days_ahead: int = 0) -> When:
        return cls(
            season=season or save.season, day=day or save.day, year=year or save.year,
            days_played=save.days_played + days_ahead, mail=set(save.mail), mailbox=set(save.mailbox),
            mail_tomorrow=set(getattr(save, "mail_tomorrow", set())), events_seen=set(save.events_seen),
            crafting_recipes=set(save.crafting_recipes), cooking_recipes=set(save.cooking_recipes),
            skills=dict(save.skills), house_upgrade=save.house_upgrade,
            mine_lowest=max(getattr(save, "mine_lowest", 0), save.deepest_mine_level),
            museum_count=len(save.museum), hearts={k: f.hearts for k, f in save.friends.items()},
            game_id=int(save.unique_id) if str(save.unique_id or "").isdigit() else None,
            legacy_random=save.legacy_random)

    def on(self, days_played: int, **changes) -> When:
        """The same farm on another day (what the save knows stays as it is)."""
        season, day, year = date_of(days_played)
        return replace(self, season=season, day=day, year=year, days_played=days_played, **changes)

    @property
    def weekday(self) -> int:
        """0 Sunday … 6 Saturday; the 1st of every season is a Monday."""
        return self.day % 7

    def has_or_will_get_mail(self, key: str) -> bool:
        return key in self.mail or key in self.mailbox or key in self.mail_tomorrow


def date_of(days_played: int) -> tuple[str, int, int]:
    """Days played (1 = Spring 1, Year 1) -> (season, day, year)."""
    d = days_played - 1
    return SEASONS[d // 28 % 4], d % 28 + 1, d // 112 + 1


CC_RESTORED_EVENT = "191393"


def location_accessible(name: str, w: When) -> bool:
    """Game1.isLocationAccessible: the four places the game gates this way (others are always 'accessible')."""
    if name == "Desert":
        return "ccVault" in w.mail
    if name == "CommunityCenter":
        return CC_RESTORED_EVENT in w.events_seen
    if name == "JojaMart":
        return CC_RESTORED_EVENT not in w.events_seen
    if name == "Railroad":
        return w.days_played > 31
    return True


def split(condition: str) -> list[list[str]]:
    """'SEASON spring, !YEAR 2' -> [['SEASON', 'spring'], ['!YEAR', '2']] (commas inside quotes kept)."""
    parts, buf, quoted = [], [], False
    for ch in condition:
        if ch == '"':
            quoted = not quoted
        if ch == "," and not quoted:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    out = []
    for p in (p.strip() for p in parts):
        if p:
            try:
                out.append(shlex.split(p))
            except ValueError:
                out.append(p.split())
    return out


def _range(args: list[str], i: int, value: int) -> bool | None:
    try:
        lo = int(args[i])
        hi = int(args[i + 1]) if len(args) > i + 1 else 2**31 - 1
    except (ValueError, IndexError):
        return None
    return lo <= value <= hi


def _query(key: str, args: list[str], w: When) -> bool | None:
    if key in SEASON_KEYS:
        return w.season in {a.lower() for a in args}
    if key == "DAY_OF_WEEK":
        days = set()
        for a in args:
            if a.lstrip("-").isdigit():
                days.add(int(a) % 7)
            elif a.lower() in WEEKDAYS:
                days.add(WEEKDAYS[a.lower()])
            else:
                return None
        return w.weekday in days
    if key == "DAY_OF_MONTH":
        for a in args:
            if (a.isdigit() and int(a) == w.day) or (a.lower() == "even" and w.day % 2 == 0) \
                    or (a.lower() == "odd" and w.day % 2 == 1):
                return True
        return False
    if key == "SEASON_DAY":  # pairs of season, day
        pairs = list(zip(args[::2], args[1::2], strict=False))
        return any(s.lower() == w.season and d.isdigit() and int(d) == w.day for s, d in pairs)
    if key == "YEAR":
        return _range(args, 0, w.year)
    if key == "DAYS_PLAYED":
        return _range(args, 0, w.days_played)
    if key == "MINE_LOWEST_LEVEL_REACHED":
        return _range(args, 0, w.mine_lowest)
    if key == "LOCATION_ACCESSIBLE" and args:
        return location_accessible(args[0], w)
    if key == "IS_COMMUNITY_CENTER_COMPLETE":
        rooms = ("ccBoilerRoom", "ccCraftsRoom", "ccPantry", "ccFishTank", "ccVault", "ccBulletin")
        return all(r in w.mail for r in rooms) and "JojaMember" not in w.mail
    if key == "MUSEUM_DONATIONS":
        if len(args) > 2 or (len(args) == 2 and not args[1].lstrip("-").isdigit()):
            return None  # filtered by item type: needs each piece's data
        return _range(args, 0, w.museum_count)
    if key == "SYNCED_RANDOM":  # <interval> <key> <chance> [@addDailyLuck]
        if w.game_id is None or len(args) < 3 or any(a.lower() == "@adddailyluck" for a in args[3:]):
            return None
        rng = synced_random(args[0], args[1], game_id=w.game_id, days_played=w.days_played, season=w.season,
                            year=w.year, legacy=w.legacy_random)
        try:
            chance = float(args[2])
        except ValueError:
            return None
        return None if rng is None else rng.next_double() < chance
    if key == "WORLD_STATE_FIELD" and len(args) >= 2:
        if args[0] not in w.world_fields or not args[1].lstrip("-").isdigit():
            return None
        return _range(args, 1, w.world_fields[args[0]])
    # Player queries: single player, so Current/Host/Any/All all mean the farmer in the save
    if not args:
        return None
    rest = args[1:]
    if key == "PLAYER_HAS_MAIL":
        if not rest:
            return None
        kind = rest[1].lower() if len(rest) > 1 else "any"
        return {"received": rest[0] in w.mail, "mailbox": rest[0] in w.mailbox,
                "tomorrow": rest[0] in w.mail_tomorrow}.get(kind, w.has_or_will_get_mail(rest[0]))
    if key == "PLAYER_HAS_SEEN_EVENT":
        return any(e in w.events_seen for e in rest)
    if key == "PLAYER_HAS_CRAFTING_RECIPE":
        return " ".join(rest) in w.crafting_recipes
    if key == "PLAYER_HAS_COOKING_RECIPE":
        return " ".join(rest) in w.cooking_recipes
    if key == "PLAYER_FARMHOUSE_UPGRADE":
        return _range(rest, 0, w.house_upgrade)
    if key.startswith("PLAYER_BASE_") and key.endswith("_LEVEL"):
        skill = key[len("PLAYER_BASE_"):-len("_LEVEL")].lower()
        return _range(rest, 0, w.skills.get(skill, 0)) if skill in w.skills else None
    if key == "PLAYER_HEARTS" and rest and rest[0] not in ("Any", "AnyDateable"):
        return _range(rest, 1, w.hearts.get(rest[0], 0))
    return None  # random rolls, locations, items in hand…: can't tell from the save


def check(condition: str | None, when: When, *, ignore: set[str] = frozenset()) -> bool | None:
    """True / False, or None if any part can't be decided (and no other part already fails).
    `ignore`: query keys to treat as passing (e.g. seasons, for Pierre's Missing Stock List)."""
    if not condition:
        return True
    unknown = False
    for tokens in split(condition):
        raw = tokens[0]
        negate = raw.startswith("!")
        key = raw.lstrip("!").upper()
        if key in ignore:
            continue
        if key == "TRUE":
            result = True
        elif key == "FALSE":
            result = False
        elif key == "ANY":  # any of its quoted sub-conditions
            subs = [check(c, when, ignore=ignore) for c in tokens[1:]]
            result = True if True in subs else (None if None in subs else False)
        else:
            result = _query(key, tokens[1:], when)
        if result is None:
            unknown = True
            continue
        if result == negate:
            return False
    return None if unknown else True
