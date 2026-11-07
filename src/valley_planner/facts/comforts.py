"""Small comforts: the spa, the horse, heaters and truffles (1.6.15).

The spa, in our words (Farmer.Update while swimming, GameLocation "PoolEntrance", Mountain.railroadAreaBlocked):
- Stepping into the bathhouse pool starts a 800 ms timer; then, every 100 ms you stand still in the water (not
  moving, no menu open in single player), energy and health each go up by 1, to their maximums.
- The game steps 16 ms a tick, so a point takes 7 ticks (112 ms) and the first one 51 ticks. A game minute is
  700 ms, so the water gives about 6.25 energy (and health) a game minute: a full bar of 270 in about 45 minutes.
- The bathhouse door is a plain Warp on the Railroad, with no opening hours: it's open every day, all day, from
  the day the railroad opens (the boulder goes when 31 days have been played: Summer 3 of year 1).
  `spa_minutes` says how long a refill takes.

The horse, in our words (Data/Buildings "Stable", Farmer.getMovementSpeed, Farmer.addedSpeed):
- Robin builds a Stable for its gold and materials in its BuildDays (`stable`); the horse comes with it.
- Running is speed 5; riding is 5 + 4.6 (+0.4 the day it ate a carrot, +0.5 with the horse book read): 1.92 times
  as fast. Speed buffs count either way; the two speed books (+0.25 each) only count on foot.
  `horse_minutes_saved` turns tiles of a route into game minutes saved, at the planner's walking pace.

Heaters, in our words (FarmAnimal.updatePerTenMinutes):
- From 6pm, every 10 minutes the clock shows, an animal indoors in winter whose happiness is above 150 gains its
  HappinessDrain (Data/FarmAnimals: 3 to 10) if its building has a Heater, and loses it if not. At 150 or below
  the heater does nothing. So a heater only keeps happy animals happy through winter evenings; it doesn't warm
  up unhappy ones, and it does nothing before 6pm or outside winter. `winter_evening` plays it out.

Truffles, in our words (FarmAnimal.behaviors, DigUpProduce, dayUpdate):
- Overnight a pig is given today's truffle (seeded by the pig's id and the day: most fed, happy pigs get one).
- During the day, only outdoors, not raining, not winter, and adult, each tick (on or off screen) has a
  0.0002 chance, from the game's unseeded random, to dig: about one try every 114 game minutes. It fails if any
  corner of the pig stands on grass, a tree, flooring or an object, so pigs need bare ground.
- After a dig the pig keeps its truffle for another with chance friendship/1500 (seeded by id, day and time),
  so a pig at full hearts finds about three a day; 0.2% of digs are a Truffle Crab instead.
- When it digs isn't predictable; whether it has a truffle that day is, but needs its id, fullness and happiness.

Unsure: the 16 ms tick is the game's fixed 60 frames a second; a slow computer that drops frames stretches the
real seconds but not these game-minute sums. Festival days and the bathhouse aren't checked. The horse is wider
than the farmer, so a few gaps the walker uses may not fit it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .walk import MINUTES_PER_TILE, NEW_PLAYER_PACE

# --- the spa ---
TICK_MS = 16  # the game's step at 60 frames a second
MS_PER_GAME_MINUTE = 700
SPA_FIRST_TICKS = 800 // TICK_MS + 1  # the timer has to drop below 0: 51 ticks
SPA_EVERY_TICKS = 100 // TICK_MS + 1  # 7 ticks a point
SPA_ENERGY_PER_MINUTE = MS_PER_GAME_MINUTE / (SPA_EVERY_TICKS * TICK_MS)  # 6.25
SPA_OPENS_DAYS_PLAYED = 31  # Summer 3, year 1
SPA_ADVICE = ("The spa (the Railroad, from Summer 3) is open all day, every day. Stand still in the pool: "
              "about 6 energy and 6 health a game minute, a full bar in under an hour.")


def spa_minutes(energy_now: float, energy_max: float) -> int:
    """Game minutes standing still in the pool to fill energy back up (health refills at the same rate)."""
    points = math.ceil(energy_max - energy_now)
    if points <= 0:
        return 0
    ticks = SPA_FIRST_TICKS + SPA_EVERY_TICKS * (points - 1)
    return math.ceil(ticks * TICK_MS / MS_PER_GAME_MINUTE)


def spa_open(days_played: int) -> bool:
    return days_played >= SPA_OPENS_DAYS_PLAYED


# --- the horse ---
RUN_SPEED = 5.0
HORSE_BONUS = 4.6
CARROT_BONUS = 0.4  # the horse ate a carrot today
HORSE_BOOK_BONUS = 0.5  # "Horse: The Book" read
STABLE = "Stable"


@dataclass(frozen=True)
class Stable:
    gold: int
    days: int
    materials: tuple[tuple[str, int], ...]  # (qualified item id, amount)
    builder: str


def stable(data) -> Stable:
    """What Robin asks for a Stable, from Data/Buildings."""
    b = data.asset("Data/Buildings")[STABLE]
    return Stable(int(b.get("BuildCost") or 0), int(b.get("BuildDays") or 0),
                  tuple((m["ItemId"], int(m["Amount"])) for m in b.get("BuildMaterials") or []),
                  str(b.get("Builder") or "Robin"))


def horse_speed_ratio(*, carrot: bool = False, book: bool = False) -> float:
    """How many times faster riding is than running (no buffs): 1.92, up to 2.1."""
    return (RUN_SPEED + HORSE_BONUS + CARROT_BONUS * carrot + HORSE_BOOK_BONUS * book) / RUN_SPEED


def horse_minutes_per_tile(*, carrot: bool = False, book: bool = False) -> float:
    return MINUTES_PER_TILE / horse_speed_ratio(carrot=carrot, book=book)


def horse_minutes_saved(tiles: float, *, pace: float = NEW_PLAYER_PACE, carrot: bool = False,
                        book: bool = False) -> float:
    """Game minutes saved riding a route of `tiles` (Walker.tiles) instead of walking it, at the same pace."""
    return tiles * pace * (MINUTES_PER_TILE - horse_minutes_per_tile(carrot=carrot, book=book))


HORSE_ADVICE = ("A Stable lets you ride at nearly twice walking speed; a carrot a day adds a little. "
                "The horse waits outside doors, so it pays on long outdoor trips, not short hops.")

# --- heaters ---
HEATER_FROM = 1800
HEATER_ABOVE = 150  # happiness the heater (or its lack) matters above
HEATER_ADVICE = ("A heater only matters in winter after 6pm, and only for happy animals (above 150 of 255): "
                 "with one they keep gaining, without one they slide down to 150. Fill the hay and pet them.")


def evening_checks(bedtime: int) -> int:
    """How many 10-minute happiness checks happen from 6pm until `bedtime` (HHMM, after midnight as 2400+)."""
    if bedtime < HEATER_FROM:
        return 0
    minutes = (bedtime // 100 * 60 + bedtime % 100) - (HEATER_FROM // 100 * 60)
    return minutes // 10 + 1


def winter_evening(happiness: int, drain: int, *, heater: bool, checks: int) -> int:
    """An indoor animal's happiness after `checks` winter-evening checks."""
    for _ in range(checks):
        if happiness <= HEATER_ABOVE:
            break
        happiness = max(0, min(255, happiness + (drain if heater else -drain)))
    return happiness


# --- truffles ---
TRUFFLE_DIG_CHANCE = 0.0002  # each tick, outdoors
TRUFFLE_KEEP_PER_FRIENDSHIP = 1 / 1500
TRUFFLE_CRAB_CHANCE = 0.002
TRUFFLE_ADVICE = ("Pigs dig truffles only outside on dry days outside winter, and only on bare ground: no grass, "
                  "paths or objects under them. Let them out early; the more they like you, the more they find.")


def truffle_minutes_between_digs() -> float:
    """The average game minutes an outdoor pig takes to try a dig (it isn't seeded, so only an average)."""
    return 1 / TRUFFLE_DIG_CHANCE * TICK_MS / MS_PER_GAME_MINUTE


def truffle_can_dig(*, outdoors: bool, raining: bool, season: str, adult: bool = True) -> bool:
    return outdoors and not raining and season != "winter" and adult


def truffles_expected(friendship: int, minutes_out: float | None = None) -> float:
    """About how many truffles a pig with today's truffle digs: 1 / (1 - keep), capped by the time it's out."""
    keep = min(1.0, max(0, friendship) * TRUFFLE_KEEP_PER_FRIENDSHIP)
    most = 1 / (1 - keep) if keep < 1 else math.inf
    if minutes_out is None:
        return most
    return min(most, minutes_out / truffle_minutes_between_digs())
