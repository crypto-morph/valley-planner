"""Story requests that come by letter (1.6.15): a villager asks for one thing, for a good reward.

In our words (Data/mail, Data/Quests, Game1.newDayAfterFade's mail check):
- On the morning of a date, mail keyed `season_day_year` (e.g. `summer_20_1`, Summer 20 of Year 1) goes in the
  mailbox if it exists. Some of those letters carry `%item quest <id>`: reading it starts that quest.
- An ItemDelivery quest's fifth field is "<who> <item> [count]" and its seventh the gold reward.
- A letter for a date in a year you've passed never comes again, so only dates still ahead (or a letter still
  unread in the mailbox) are worth keeping stock for. Once read, the quest is in the save's quest log, which
  the planner already holds items for.

Keeping one of the asked-for item ready means handing it over the day the letter arrives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .conditions import SEASONS

DATED = re.compile(r"^(spring|summer|fall|winter)_(\d+)_(\d+)$")
QUEST = re.compile(r"%item quest (\d+)")


@dataclass(frozen=True)
class Letter:
    key: str  # the mail key, e.g. "summer_20_1"
    days_played: int  # the morning it arrives
    quest: str
    title: str
    who: str
    item: str  # qualified id
    count: int
    reward: int


def letters(data) -> list[Letter]:
    """Every dated letter that asks for an item, soonest first."""
    mail, quests = data.asset("Data/mail") or {}, data.asset("Data/Quests") or {}
    out = []
    for key, text in mail.items():
        when, ask = DATED.match(key), QUEST.search(text or "")
        if not when or not ask:
            continue
        parts = (quests.get(ask.group(1)) or "").split("/")
        if parts[0] != "ItemDelivery" or len(parts) < 7:
            continue
        who, item, *rest = parts[4].split()
        season, day, year = when.group(1), int(when.group(2)), int(when.group(3))
        out.append(Letter(key, (year - 1) * 112 + SEASONS.index(season) * 28 + day, ask.group(1), parts[1], who,
                          item if item.startswith("(") else f"(O){item}", int(rest[0]) if rest else 1,
                          int(parts[6] or 0)))
    return sorted(out, key=lambda x: x.days_played)


def coming(data, save, today: int) -> list[Letter]:
    """The letters still to come for this save: dated today or later and not read, or waiting in the mailbox."""
    return [x for x in letters(data) if x.key not in save.mail and (x.days_played >= today or x.key in save.mailbox)]
