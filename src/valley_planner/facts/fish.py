"""Where and when each fish bites, from Data/Fish and Data/Locations.

How the game decides (GameLocation.getFish and its helpers, 1.6.15), in our words:
- A location's catchable fish are its Data/Locations "Fish" spawn entries,
  plus — for entries whose ItemId is `LOCATION_FISH <place>` — the inheritable
  entries of that other place (farm maps, the Night Market, the Desert
  Festival borrow this way). The entry's own Id is just a key, not an item.
- Seasons come only from the spawn entry: its Season field, or a
  LOCATION_SEASON condition; with neither, it bites in every season. The
  season list in Data/Fish is never read when fishing.
- Data/Fish supplies the bite times (every start-end pair; start inclusive,
  end exclusive), the weather ('rainy' needs rain, storm or green rain;
  'sunny' fails only in rain — snow is dry; 'both') and the minimum fishing
  level, unless the spawn entry sets IgnoreFishDataRequirements.
- Rows whose second field is 'trap' are crab-pot catches: no season, time or
  weather, only ocean or freshwater.
- The Mines' code adds Stonefish (floor 20), Ice Pip (60) and Lava Eel (100).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property

from .conditions import SEASONS, When, check, split

PSEUDO_LOCATIONS = {"Default", "fishingGame", "Temp"}  # not real fishing spots
FARM_TYPES = {0: "Standard", 1: "Riverland", 2: "Forest", 3: "Hilltop", 4: "Wilderness", 5: "FourCorners",
              6: "Beach", 7: "MeadowlandsFarm"}
MINES_CODE_FISH = {"158": 20, "161": 60, "162": 100}  # MineShaft.getFish: Stonefish, Ice Pip, Lava Eel by floor


@dataclass(frozen=True)
class Spot:
    location: str
    area: str | None
    seasons: frozenset[str]
    condition: str  # the rest of the spawn condition (other than season), if any
    ignores_fish_data: bool  # time / weather / level from Data/Fish don't apply here
    min_level: int
    magic_bait: bool
    floor: int | None = None  # Mines floor, for the code-spawned ones


@dataclass
class FishInfo:
    id: str
    name: str
    trap: bool  # caught in a crab pot
    water: str | None  # crab pots: "ocean" / "freshwater"
    times: list[tuple[int, int]]  # [(600, 1900)]; end exclusive
    weather: str  # rainy / sunny / both
    min_level: int
    difficulty: int
    spots: list[Spot] = field(default_factory=list)

    def bites(self, spot: Spot, *, season: str, time: int | None = None, wet: bool | None = None,
              fishing_level: int | None = None) -> bool | None:
        """At this spot: True, False, or None when a missing input (time, weather) decides it."""
        if season not in spot.seasons:
            return False
        if fishing_level is not None and fishing_level < spot.min_level:
            return False
        if spot.ignores_fish_data or self.trap:
            return True
        if fishing_level is not None and fishing_level < self.min_level:
            return False
        if time is not None and not any(a <= time < b for a, b in self.times):
            return False
        if self.weather in ("rainy", "sunny"):
            if wet is None:
                return None
            if (self.weather == "rainy") != wet:
                return False
        return None if time is None and self.times and self.times != [(600, 2600)] else True


def _parse_fish(fid: str, raw: str) -> FishInfo:
    f = raw.split("/")
    if len(f) > 1 and f[1] == "trap":
        return FishInfo(fid, f[0], True, f[4] if len(f) > 4 else None, [], "both", 0, 0)
    nums = [int(x) for x in (f[5].split() if len(f) > 5 else [])]
    times = list(zip(nums[::2], nums[1::2], strict=False))
    return FishInfo(fid, f[0], False, None, times, f[7] if len(f) > 7 else "both",
                    int(f[12]) if len(f) > 12 and f[12].lstrip("-").isdigit() else 0,
                    int(f[1]) if f[1].isdigit() else 0)


def _season_of(entry: dict) -> tuple[frozenset[str], str]:
    """(seasons, the condition with its season parts taken out)."""
    seasons = {entry["Season"].lower()} if entry.get("Season") else set()
    rest = []
    for tokens in split(entry.get("Condition") or ""):
        key = tokens[0].upper()
        if key == "LOCATION_SEASON" and len(tokens) > 2:  # LOCATION_SEASON <location> <seasons…>
            seasons |= {s.lower() for s in tokens[2:]}
        else:
            rest.append(" ".join(tokens))
    return frozenset(seasons or SEASONS), ", ".join(rest)


class Fish:
    def __init__(self, data, farm_type: int = 0):
        self.data = data
        self.farm_type = farm_type

    @cached_property
    def by_id(self) -> dict[str, FishInfo]:
        fish = {fid: _parse_fish(fid, raw) for fid, raw in self.data.asset("Data/Fish").items()}
        locations = self.data.asset("Data/Locations")
        farm_here = f"Farm_{FARM_TYPES.get(self.farm_type, 'Standard')}"

        def entries(loc: str, inherited: bool = False, depth: int = 0):
            for e in (locations.get(loc) or {}).get("Fish") or []:
                item = (e.get("ItemId") or "").strip()
                if inherited and e.get("CanBeInherited") is False:
                    continue
                if item.startswith("LOCATION_FISH") and depth < 3:
                    parts = item.split()
                    if len(parts) > 1:
                        yield from entries(parts[1], True, depth + 1)
                    continue
                yield e

        for loc in locations:
            if loc in PSEUDO_LOCATIONS or (loc.startswith("Farm_") and loc != farm_here):
                continue
            where = "Farm" if loc == farm_here else loc
            for e in entries(loc):
                item = (e.get("ItemId") or "").strip()
                if not item.startswith("(O)"):
                    continue
                fid = item[3:]
                if fid not in fish:
                    continue
                seasons, cond = _season_of(e)
                fish[fid].spots.append(Spot(
                    location=where, area=e.get("FishAreaId"), seasons=seasons, condition=cond,
                    ignores_fish_data=bool(e.get("IgnoreFishDataRequirements")),
                    min_level=int(e.get("MinFishingLevel") or 0), magic_bait=bool(e.get("RequireMagicBait"))))
        for fid, floor in MINES_CODE_FISH.items():
            if fid in fish:
                fish[fid].spots.append(Spot("UndergroundMine", None, frozenset(SEASONS), "", False, 0, False, floor))
        return fish

    def by_name(self, name: str) -> FishInfo | None:
        lowered = name.lower()
        return next((f for f in self.by_id.values() if f.name.lower() == lowered), None)

    def open_spots(self, fish: FishInfo, when: When, *, include_conditional: bool = False) -> list[Spot]:
        """Spots whose season and extra condition allow it on `when` (conditions we can't judge: optional)."""
        out = []
        for s in fish.spots:
            if when.season not in s.seasons or s.magic_bait:
                continue
            ok = check(s.condition, when) if s.condition else True
            if ok or (ok is None and include_conditional):
                out.append(s)
        return out
