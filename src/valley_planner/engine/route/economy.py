"""What farming earns on a fresh farm: gold and farming XP per tile per day, season by season.

From the game: each crop's growing days and regrowth (Data/Crops), the
seeds a regular shop sells that season and year (Data/Shops conditions),
the harvest's sale price for this farmer, and the XP each harvest gives
(Crop.harvest: 16·ln(0.018·price + 1), rounded, once per harvest however
many drop). The XP levels are Farmer.getBaseExperienceForLevel.

Planning choices: a tile is replanted as soon as it's free; a crop counts
only if it ripens before its season ends; normal quality (a cautious
floor); the best crop per season by gold per tile-day. Seeds are free once
there's a Seed Maker (it turns a crop into 1-3 seeds).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ...facts.conditions import SEASONS, When, location_accessible
from ...facts.sell import sell_price
from ...views.farm import REGULAR_SEED_SHOPS, Farm

XP_FOR_LEVEL = (0, 100, 380, 770, 1300, 2150, 3300, 4800, 6900, 10000, 15000)
SEASON_DAYS = 28
SHOP_PLACE = {"Sandy": "Desert", "Joja": "JojaMart"}


def harvest_xp(price: int) -> int:
    return round(16 * math.log(0.018 * price + 1))


def level_for(xp: float) -> int:
    return max(i for i, need in enumerate(XP_FOR_LEVEL) if xp >= need)


@dataclass(frozen=True)
class CropRate:
    crop: str
    seed: str
    seed_price: int
    gold_per_tile_day: float  # after seed costs
    xp_per_tile_day: float
    gold_free_seeds: float  # with a Seed Maker
    first_harvest: int  # days after planting
    harvest: str = ""  # harvest item id
    per_harvest: float = 0.0  # gold per tile per harvest (the average stack at its sale price)
    regrow: int = 0
    xp_each: int = 0


def season_rates(farm: Farm, season: str, year: int = 1) -> list[CropRate]:
    """Every crop you can plant from a regular shop on day 1 of `season`, best gold per tile-day first."""
    w: When = farm.when.on((year - 1) * 112 + SEASONS.index(season) * SEASON_DAYS + 1)
    sold: dict[str, int] = {}
    for o in farm.shops.offers(w, profit_margin=farm.save.profit_margin):
        if o.shop in REGULAR_SEED_SHOPS and o.available is not False and o.price and not o.recipe \
                and location_accessible(SHOP_PLACE.get(o.shop, ""), w):
            oid = o.item.removeprefix("(O)")
            sold[oid] = min(sold.get(oid, o.price), o.price)
    out = []
    for seed, c in farm.crops.by_seed.items():
        if seed not in sold or season not in c.seasons or not c.harvest:
            continue
        info = farm.items.get(c.harvest)
        if not info or c.grow >= SEASON_DAYS:
            continue
        each = sell_price(info.price, 0, farm.farmer, f"(O){c.harvest}", info.name, info.category,
                          profit_margin=farm.save.profit_margin)
        stack = c.expected_stack(farm.save.skills.get("farming", 0))
        days = SEASON_DAYS - 1  # planted on day 1, harvested by day 28
        if c.regrow:
            harvests = 1 + max(0, (days - c.grow) // c.regrow)
            plantings = 1
        else:
            harvests = plantings = days // c.grow
        gold = harvests * stack * each
        xp = harvests * harvest_xp(info.price)
        out.append(CropRate(farm.name(f"(O){c.harvest}"), farm.name(f"(O){seed}"), sold[seed],
                            (gold - plantings * sold[seed]) / days, xp / days, gold / days, c.grow,
                            c.harvest, stack * each, c.regrow, harvest_xp(info.price)))
    out.sort(key=lambda r: -r.gold_per_tile_day)
    return out


def best(farm: Farm, season: str, year: int = 1, *, free_seeds: bool = False) -> CropRate | None:
    rates = season_rates(farm, season, year)
    if not rates:
        return None
    return max(rates, key=lambda r: r.gold_free_seeds if free_seeds else r.gold_per_tile_day)
