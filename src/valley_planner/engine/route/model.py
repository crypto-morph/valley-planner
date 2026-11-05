"""What the route's parts share: the settings, the materials it prices, and its requirements and steps."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..unlocks import Unlock

WOOD, STONE, HARDWOOD = "388", "390", "709"
QUARTZ, REFINED_QUARTZ = "80", "338"
CLAY, OAK_RESIN, TAPPER = "330", "725", "105"
VAULT_STEP = "the Vault"  # the requirement the Vault's gold is shared under


@dataclass
class Settings:
    """The planning choices, all tunable from the page."""
    tiles: int = 80  # tiles farmed
    wood_per_day: int = 100  # Wood from a day spent chopping
    floors_per_week: int = 10  # Mines floors to aim for each week: follows your pace once the save shows one
    hardwood_per_day: int = 12  # the Secret Woods' six large stumps, two Hardwood each
    fish_gold: int = 300  # a spare day spent fishing, sold at normal quality
    mine_gold: int = 200  # ore, gems, geodes and minerals sold from a day in the Mines
    float: int = 500  # cash never spent on seeds
    quartz_per_day: int = 6  # Quartz found in a day in the Mines (for Refined Quartz)
    gift_points: int = 80  # friendship from each gift to your sweetheart (loved 80, liked 45)
    spouse: str = ""  # who to marry; empty: whoever you're closest to
    picks: dict = field(default_factory=dict)  # item name -> the way you chose (a source label, or "cave")
    jars: int = 10  # Preserves Jars to have
    kegs: int = 10  # Kegs to have
    tappers: int = 5  # Tappers put on oaks for the Kegs' Oak Resin
    clay_per_day: int = 10  # Clay from a day hoeing the Mines' dirt (about one tile in seven gives some)



WOOD_PER_DAY = Settings.wood_per_day

MINES_OPEN = 5  # the landslide clears on day 5
BOUGHT = {"334": 5 * 75 + 150, "335": 5 * 150 + 150, "336": 5 * 400 + 150, "382": 150,  # Clint, Year 1
          "378": 75, "380": 150, "384": 400}
DATE_GATES = {"place:UndergroundMine": 5, "place:Railroad": 31}  # places that simply open on a day
HARD = ("Island", "quest", "Rusty Key", "Willy's boat")  # gates the route can't plan in Year 1
SKILL_RE = re.compile(r"^(Farming|Fishing|Foraging|Mining|Combat) level (\d+)", re.I)


@dataclass
class Step:
    label: str
    day: int  # when it's bought / done
    ready: int  # when it's in hand
    gold: int = 0
    chop_days: list[int] = field(default_factory=list)
    mine_days: list[int] = field(default_factory=list)
    needs: list[dict] = field(default_factory=list)  # the unlocks behind it, prerequisites first
    how: str = ""  # the way it's got (a shop, a fishing spot, an animal)
    act: int | None = None  # a day spent getting it (fishing), if any
    shared: str = ""  # already planned for this other objective
    last: int | None = None  # the last day it can start and still be in time


@dataclass
class Outcome:
    id: str
    label: str
    tier: str
    deadline: int
    status: str = "ok"  # ok / late / impossible
    finish: int | None = None
    steps: list[Step] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    misses: list[tuple[str, str]] = field(default_factory=list)  # (requirement, why it can't be planned)
    notes: list[str] = field(default_factory=list)  # problems that aren't one requirement's
    info: list[str] = field(default_factory=list)  # how it's been planned, worth knowing


@dataclass
class Req:
    label: str
    earliest: int
    latest: int
    chain: list[Unlock]
    lead: int
    activity: str | None = None  # fish / forage / mine: a day spent getting it
    luck: float | None = None
    season: str = ""  # the way's label: fishing at one place in one season shares a day
    fallback: Req | None = None  # what to do instead if this can't be placed (a cart visit you can't afford)
