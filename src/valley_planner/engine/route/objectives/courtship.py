"""Marriage: hearts, the Bouquet, the Mermaid's Pendant."""

from __future__ import annotations

from ....facts import romance
from ...unlocks import Unlock
from ..model import Req
from .base import objective


def sweetheart(r) -> str | None:
    """Who to marry: the setting, or the romanceable villager you're closest to."""
    chars = r.farm.data.asset("Data/Characters")
    can = [k for k, v in chars.items() if v.get("CanBeRomanced")]
    if r.s.spouse in can:
        return r.s.spouse
    friends = r.farm.save.friends
    return max(can, key=lambda k: friends[k].points if k in friends else -1, default=None)


def _later(r, day: int | None) -> str:
    return f"not this year: about {r.farm.label(day)}" if day else "not within two years at this pace"


def _married(r) -> bool:
    return any(f.status in ("Married", "Engaged") for f in r.farm.save.friends.values())


@objective("marriage", "Marriage", 112, done=_married)
def courtship(r) -> tuple[list[Req], int, list[str]]:
    """Hearts by talking every day and two gifts a week, the Bouquet at 8 hearts, the Mermaid's Pendant at
    10 on a rainy day (after the first house upgrade, past the beach bridge); the wedding comes after."""
    name = sweetheart(r)
    if not name:
        return [], 0, ["no one to marry"]
    info = r.farm.data.asset("Data/Characters")[name]
    f = r.farm.save.friends.get(name)
    points, status = (f.points, f.status) if f else (0, "Friendly")
    seasons = ["spring", "summer", "fall", "winter"]
    bseason = (info.get("BirthSeason") or "").lower()
    birthday = seasons.index(bseason) * 28 + int(info.get("BirthDay") or 0) if bseason in seasons else None
    gift, notes, reqs = r.s.gift_points, [], []
    how = f"talk to {name} every day and give two gifts a week"
    day8 = r.today
    if status != "Dating":
        day8 = romance.points_day(points, 8 * romance.HEART, r.today, birthday=birthday, gift=gift,
                                  cap=romance.CAP_FRIEND)
        if day8 is None or day8 > r.end:
            r.misses = [(f"8 hearts with {name}", _later(r, day8))]
            return [], 0, []
        price = 2 * int((r.farm.data.asset("Data/Objects").get(romance.BOUQUET) or {}).get("Price") or 100)
        reqs.append(Req(f"8 hearts with {name}", day8, r.end, [], 0, "social", season=how))
        reqs.append(Req(f"a Bouquet for {name}", day8, r.end,
                        [Unlock("bouquet", "buy a Bouquet from Pierre", price)], 0, season=f"give it to {name}"))
        points = 8 * romance.HEART
    day10 = romance.points_day(points, 10 * romance.HEART, day8 + 1, birthday=birthday, gift=gift)
    if day10 is None or day10 > r.end:
        r.misses = [(f"10 hearts with {name}", _later(r, day10))]
        return reqs, 0, []
    reqs.append(Req(f"10 hearts with {name}", day10, r.end, [], 0, "social", season=how))
    rain = romance.rain_by(day10)
    if rain is None or rain > r.end:
        first = next((d for d in range(day10, day10 + romance.YEAR) if romance.rain_chance(d)), day10)
        r.misses = [("the Mermaid's Pendant",
                        f"the Old Mariner only comes when it rains, and it doesn't rain in winter: "
                        f"10 hearts on {r.farm.label(day10)}, the next chance of rain from "
                        f"{r.farm.label(first)}")]
        return reqs, 0, []
    pendant = 2 * int((r.farm.data.asset("Data/Objects").get(romance.PENDANT) or {}).get("Price") or 2500)
    chain = r.planner.unlocks.chain("kitchen") + r.planner.unlocks.chain("place:BeachTidePools") + \
        [Unlock("pendant", "buy the Mermaid's Pendant from the Old Mariner", pendant)]
    lead = sum(u.days for u in chain)
    reqs.append(Req("the Mermaid's Pendant", rain or day10, r.end, chain, lead, "social",
                    season=f"on a rainy day, the Old Mariner past the beach bridge; propose to {name}"))
    r.wedding = name
    return reqs, 0, notes
