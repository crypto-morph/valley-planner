"""When each level arrives, so nothing gets chased that comes anyway.

Farming is worked out from the crops in the ground, each harvest paying once, for what's left of the season; past
that it's an estimate from the size of your field, if you keep it planted. The other skills go at your own pace so
far. A level earned today plays its screen tonight, so its recipes are there the morning after.
"""

from __future__ import annotations

import math

from ..facts.conditions import date_of
from ..facts.skills import LEVELS, PICKS, RAISES_PRICES, UNLOCKS, harvest_xp, level_of
from .farm import Farm

SEASON_DAYS = 28
FIELD_XP_PER_DAY = 50 / SEASON_DAYS  # a tile a day, between Blueberry's 40 and Cranberry's 70 a month (an estimate)
HORIZON = 3 * 112  # no further than the end of Year 3


def _harvests(farm: Farm) -> dict[int, int]:
    """Farming XP by day from the crops planted now, to the end of this season."""
    w, s = farm.when, farm.save
    end = w.days_played + SEASON_DAYS - w.day
    objects = farm.data.asset("Data/Objects")
    out: dict[int, int] = {}
    for c in s.crops:
        if c.forage or c.dead or not c.harvest_id or c.harvest_id == "-1":
            continue
        xp = harvest_xp(int((objects.get(c.harvest_id) or {}).get("Price") or 0))
        info = farm.crops.get(c.seed_id) if c.seed_id else farm.crops.by_harvest.get(c.harvest_id)
        day = w.days_played + c.days_left
        while day <= end:
            out[day] = out.get(day, 0) + xp
            if not (info and info.regrow):
                break
            day += info.regrow
    return out


def _farming(farm: Farm) -> dict[int, tuple[int, bool]]:
    """Level -> (the day it's earned, whether that comes from crops already in the ground)."""
    w, s = farm.when, farm.save
    xp = s.experience.get("farming", 0)
    level = level_of(xp)
    tiles = sum(1 for c in s.crops if not c.forage)
    harvests = _harvests(farm)
    end = w.days_played + SEASON_DAYS - w.day
    out = {}
    for dp in range(w.days_played, min(w.days_played + HORIZON, HORIZON + 1)):
        if dp in harvests:
            xp += harvests[dp]
        elif dp > end and date_of(dp)[0] != "winter":
            xp += tiles * FIELD_XP_PER_DAY
        while level < len(LEVELS) and xp >= LEVELS[level]:
            level += 1
            out[level] = (dp, dp <= end)
    return out


def _at_your_pace(farm: Farm, skill: str) -> tuple[int, int] | None:
    """(next level, the day it's earned at the rate so far)."""
    w = farm.when
    xp = farm.save.experience.get(skill, 0)
    level = level_of(xp)
    if level >= len(LEVELS) or not xp:
        return None
    rate = xp / max(1, w.days_played - 1)
    return level + 1, w.days_played + math.ceil((LEVELS[level] - xp) / rate)


def _date(farm: Farm, day: int) -> str:
    """The year only when it isn't this one."""
    label = farm.label(day)
    return label.rsplit(",", 1)[0] if date_of(day)[2] == farm.when.year else label


def _row(farm: Farm, skill: str, level: int, day: int, how: str, sure: bool) -> dict:
    pick = PICKS.get((skill, level), "")
    if pick == "Artisan" and 1 not in farm.save.professions:
        pick = ""  # Artisan only follows Tiller
    return {"skill": skill, "level": level, "day": day, "date": _date(farm, day), "ready": _date(farm, day + 1),
            "unlocks": UNLOCKS[skill].get(level, ""), "pick": pick,
            "hold_bin": pick in RAISES_PRICES, "how": how, "sure": sure}


def forecast(farm: Farm) -> list[dict]:
    """Every coming Farming level, and the next level of the others, soonest first."""
    out = [_row(farm, "farming", lv, d, "from the crops in the ground" if sure else "if you keep the field planted",
                sure) for lv, (d, sure) in _farming(farm).items()]
    for skill in ("fishing", "foraging", "mining", "combat"):
        next_up = _at_your_pace(farm, skill)
        if next_up:
            out.append(_row(farm, skill, *next_up, "at your pace so far", False))
    return sorted(out, key=lambda r: r["day"])
