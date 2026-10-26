"""Crops from Data/Crops: growth, seasons, harvests and quality odds.

From StardewValley.Crop.harvest / newDay and HoeDirt (checked against 1.6.15):
- Quality: g = 0.2·(Farming/10) + 0.2·fert·((Farming+2)/12) + 0.01, where fert
  is 0 (none), 1 Basic, 2 Quality, 3 Deluxe Fertilizer. Deluxe first rolls
  iridium at g/2; then gold at g; then silver at min(0.75, 2g) — always silver
  with Deluxe, so a Deluxe crop is never normal quality. The result is held to
  the crop's HarvestMinQuality/HarvestMaxQuality. Only the first item of a
  harvest gets that quality; extra items are normal.
- Quantity: a whole number from HarvestMinStack to HarvestMaxStack, the
  maximum raised by floor(Farming x HarvestMaxIncreasePerFarmingLevel); then
  one more each time a roll under min(0.9, ExtraHarvestChance) succeeds.
- Growth: sum(DaysInPhase) watered nights; RegrowDays > 0 means it keeps
  producing. Outdoors a crop dies at the change of season unless the next
  season is one of its Seasons; a crop listing all four never dies of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

FERTILIZER_QUALITY = {"368": 1, "369": 2, "919": 3}  # Basic, Quality, Deluxe Fertilizer
SEASONS = ("spring", "summer", "fall", "winter")


def gold_chance(farming: int, fertilizer: int = 0) -> float:
    return 0.2 * (farming / 10) + 0.2 * fertilizer * ((farming + 2) / 12) + 0.01


def quality_odds(farming: int, fertilizer: int = 0, min_quality: int = 0, max_quality: int = 4) -> dict[int, float]:
    """Chance of each quality (0 normal, 1 silver, 2 gold, 4 iridium) for a harvest's first item."""
    g = gold_chance(farming, fertilizer)
    silver_roll = min(0.75, g * 2)
    iridium = g / 2 if fertilizer >= 3 else 0.0
    gold = (1 - iridium) * g
    rest = 1 - iridium - gold
    silver = rest if fertilizer >= 3 else rest * silver_roll
    odds = {4: iridium, 2: gold, 1: silver, 0: rest - silver}
    clamped: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.0, 4: 0.0}
    for q, p in odds.items():
        held = max(min_quality, min(max_quality, q))
        held = held if held in clamped else max(k for k in clamped if k <= held)
        clamped[held] += p
    return clamped


@dataclass(frozen=True)
class CropInfo:
    seed: str  # unqualified seed id
    harvest: str  # unqualified harvest item id
    seasons: tuple[str, ...]
    phases: tuple[int, ...]
    regrow: int  # days between harvests; 0 = a single harvest
    raised: bool  # trellis
    paddy: bool
    needs_water: bool
    min_stack: int
    max_stack: int
    stack_per_level: float
    extra_chance: float
    min_quality: int
    max_quality: int

    @property
    def grow(self) -> int:
        return sum(self.phases)

    def max_harvest(self, farming: int) -> int:
        top = max(self.min_stack, self.max_stack)
        return top + int(farming * self.stack_per_level) if self.stack_per_level > 0 else top

    def expected_stack(self, farming: int) -> float:
        """Average items per harvest: the min..max range, plus the repeated extra-item rolls."""
        p = min(0.9, self.extra_chance)
        return (self.min_stack + self.max_harvest(farming)) / 2 + (p / (1 - p) if p > 0 else 0.0)

    def survives_into(self, season: str) -> bool:
        return season in self.seasons

    @property
    def plantable(self) -> bool:
        """An empty season list means it can't grow outdoors at all."""
        return bool(self.seasons)


class Crops:
    def __init__(self, data):
        self.data = data

    @cached_property
    def by_seed(self) -> dict[str, CropInfo]:
        out = {}
        for seed, c in self.data.asset("Data/Crops").items():
            out[seed] = CropInfo(
                seed=seed, harvest=(c.get("HarvestItemId") or "").removeprefix("(O)"),
                seasons=tuple(s.lower() for s in c.get("Seasons") or ()), phases=tuple(c.get("DaysInPhase") or ()),
                regrow=max(0, int(c.get("RegrowDays") or 0)), raised=bool(c.get("IsRaised")),
                paddy=bool(c.get("IsPaddyCrop")), needs_water=c.get("NeedsWatering", True) is not False,
                min_stack=int(c.get("HarvestMinStack") or 1), max_stack=int(c.get("HarvestMaxStack") or 1),
                stack_per_level=float(c.get("HarvestMaxIncreasePerFarmingLevel") or 0),
                extra_chance=float(c.get("ExtraHarvestChance") or 0),
                min_quality=int(c.get("HarvestMinQuality") or 0),
                max_quality=int(c.get("HarvestMaxQuality") if c.get("HarvestMaxQuality") is not None else 4))
        return out

    @cached_property
    def by_harvest(self) -> dict[str, CropInfo]:
        """Harvest item id -> its crop (the first seed, if two grow the same thing)."""
        out: dict[str, CropInfo] = {}
        for info in self.by_seed.values():
            out.setdefault(info.harvest, info)
        return out

    def get(self, seed: str) -> CropInfo | None:
        return self.by_seed.get(seed.removeprefix("(O)"))
