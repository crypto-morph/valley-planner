"""The farm's cash and farming XP day by day, given what has to be bought and when.

Planning choices (all tunable): you farm up to `tiles` tiles, planted with
the season's best-paying crop you can buy (free once there's a Seed
Maker); seeds are bought when the cash is there, keeping back what's due
in the next week; a harvest is paid the next morning (the shipping bin);
crops die at the end of their season; the greenhouse, once repaired, adds
its tiles in every season. Normal quality throughout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...facts.conditions import SEASONS
from .economy import CropRate, best, harvest_xp, level_for
from .start import START_SEEDS

YEAR_DAYS = 112
RESERVE_DAYS = 7
GREENHOUSE_TILES = 120


@dataclass
class Day:
    day: int
    cash: int
    xp: int
    tiles: int
    level: int


@dataclass
class Result:
    days: list[Day] = field(default_factory=list)

    def cash(self, d: int) -> int:
        return self.days[d - 1].cash

    def lowest_from(self, d: int) -> int:
        return min(x.cash for x in self.days[d - 1:]) if d <= len(self.days) else 0

    def level_day(self, level: int) -> int | None:
        return next((x.day for x in self.days if x.level >= level), None)


def season_of(d: int) -> str:
    return SEASONS[(d - 1) // 28 % 4]


class Farmsim:
    def __init__(self, farm, *, tiles: int = 60, start_cash: int = 500):
        self.farm = farm
        self.tiles = tiles
        self.start_cash = start_cash
        self._rates: dict[tuple[str, bool], CropRate | None] = {}

    def rate(self, season: str, free: bool) -> CropRate | None:
        key = (season, free)
        if key not in self._rates:
            self._rates[key] = best(self.farm, season, free_seeds=free)
        return self._rates[key]

    def run(self, spends: list[tuple[int, int]], *, seed_maker_day: int | None = None,
            greenhouse_day: int | None = None, days: int = YEAR_DAYS) -> Result:
        """`spends`: (day, gold) bought that morning."""
        crops = self.farm.crops
        cash, xp = self.start_cash, 0
        due: dict[int, int] = {}
        for d, g in spends:
            due[d] = due.get(d, 0) + g
        pay: dict[int, int] = {}  # income arriving that morning
        growing: list[list] = []  # [ripe day, harvest id, regrow, season end, count, xp each, gold each, indoor]
        out = Result()
        parsnip = crops.by_seed.get("472")
        for d in range(1, days + 1):
            cash += pay.pop(d, 0)
            cash -= due.get(d, 0)
            season = season_of(d)
            season_end = ((d - 1) // 28 + 1) * 28
            # harvest
            for g in growing:
                if g[0] == d:
                    pay[d + 1] = pay.get(d + 1, 0) + g[6] * g[4]
                    xp += g[5] * g[4]
                    g[0] = d + g[2] if g[2] else 0
            growing = [g for g in growing if g[0] and (g[7] or g[0] <= g[3])]
            if d == 1 and parsnip:  # the 15 Parsnip Seeds you start with
                growing.append(self._planting(parsnip, d, START_SEEDS, season_end, False))
            free_seeds = seed_maker_day is not None and d >= seed_maker_day
            reserve = sum(g for x, g in due.items() if d < x <= d + RESERVE_DAYS)
            outdoor_used = sum(g[4] for g in growing if not g[7])
            r = self.rate(season, free_seeds) if season != "winter" else None
            if r and outdoor_used < self.tiles and d + r.first_harvest <= season_end:
                n = self.tiles - outdoor_used
                price = 0 if free_seeds else r.seed_price
                if price:
                    n = min(n, max(0, (cash - reserve) // price))
                if n > 0:
                    cash -= n * price
                    growing.append(self._planting_rate(r, d, n, season_end, False))
            if greenhouse_day is not None and d >= greenhouse_day:
                inside = sum(g[4] for g in growing if g[7])
                gr = self.rate("summer", free_seeds) or r
                if gr and inside < GREENHOUSE_TILES:
                    n = GREENHOUSE_TILES - inside
                    price = 0 if free_seeds else gr.seed_price
                    if price:
                        n = min(n, max(0, (cash - reserve) // price))
                    if n > 0:
                        cash -= n * price
                        growing.append(self._planting_rate(gr, d, n, YEAR_DAYS * 2, True))
            out.days.append(Day(d, cash, xp, outdoor_used, level_for(xp)))
        return out

    def _planting(self, info, d: int, n: int, season_end: int, indoor: bool) -> list:
        """The starting Parsnips."""
        item = self.farm.items.get(info.harvest)
        price = item.price if item else 0
        return [d + info.grow, info.harvest, info.regrow, season_end, n, harvest_xp(price), price, indoor]

    @staticmethod
    def _planting_rate(r: CropRate, d: int, n: int, season_end: int, indoor: bool) -> list:
        return [d + r.first_harvest, r.harvest, r.regrow, season_end, n, r.xp_each, round(r.per_harvest), indoor]
