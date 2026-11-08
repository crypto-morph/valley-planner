"""When to pick a ripe crop, and which ripe crops turn giant overnight (1.6.15).

Quality, in our words (Crop.harvest):
- The roll's random is seeded from (x * 7, y * 11, days played, game id),
  nothing else: not the farmer, not luck, not the time of day. So a tile's
  quality on a given date is fixed, and each date gives the tile a fresh roll.
- With g = 0.2 * Farming/10 + 0.2 * boost * (Farming + 2)/12 + 0.01, where
  boost is 1 Basic, 2 Quality, 3 Deluxe Fertilizer (0 otherwise, Speed-Gro
  included): Deluxe only first draws "< g/2" for iridium; then "< g" gold;
  then "< min(0.75, 2g)" silver (always silver with Deluxe); else normal.
  The result is clamped to the crop's HarvestMinQuality..HarvestMaxQuality.
- Farming is the level at that moment, buffs included: a level gained or a
  food buff mid-harvest changes the rest of the rolls.
- Extra items (stack, ExtraHarvestChance, the rare double harvest) are drawn
  after quality from the same random and come out normal quality; they don't
  change the first item's quality. Regrowing crops roll the same way.

Giant crops, in our words (Crop.newDay -> TryGrowGiantCrop):
- Overnight, a crop that was watered (or needs no water) grows, then, if it
  is now in its last phase, rolls for every Data/GiantCrops entry made from
  its harvest (Chance < 1): seeded (days played, game id / 2, x, y, hash of
  the entry's key), hit when NextDouble() < Chance (0.01). Days played is
  already the new day's: the count goes up before locations update.
- On a hit, every tile of the TileSize square (3x3, the crop at top-left)
  must be hoed dirt holding a crop with the same harvest. Only the top-left
  crop has to be grown and watered; the others can be any age, even dead.
  Then the nine crops become one giant crop.
- Only on the Farm (or a map with AllowGiantCrops, which no 1.6.15 map has).
- An out-of-season outdoor crop dies before it grows, so the first night of
  a new season never rolls for the old season's crops.
Unsure: when two hit squares overlap, only the one the game reaches first
forms, and that order (the location's terrain features) isn't known here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..gamedata import GameData
from ..save import Crop, Save
from .conditions import date_of
from .rng import NetRandom, day_save_random, hash_text, random_seed

_BOOST = {"368": 1, "369": 2, "919": 3}  # Basic, Quality, Deluxe Fertilizer
_SEASONLESS = ("Greenhouse",)  # indoors: seasons don't apply
_ISLAND = "Island"  # Ginger Island places are always summer


def quality_boost(fertilizer: str) -> int:
    """HoeDirt.GetFertilizerQualityBoostLevel."""
    return _BOOST.get(fertilizer.removeprefix("(O)"), 0)


def harvest_quality(x: int, y: int, days_played: int, game_id: int, farming: int, boost: int = 0, *,
                    min_quality: int = 0, max_quality: int | None = None, legacy: bool = False) -> int:
    """The quality of the crop picked at tile (x, y) on that day: 0 normal, 1 silver, 2 gold, 4 iridium."""
    r = NetRandom(random_seed(x * 7.0, y * 11.0, days_played, game_id, legacy=legacy))
    g = 0.2 * (farming / 10.0) + 0.2 * boost * ((farming + 2.0) / 12.0) + 0.01
    if boost >= 3 and r.next_double() < g / 2.0:
        q = 4
    elif r.next_double() < g:
        q = 2
    elif r.next_double() < min(0.75, g * 2.0) or boost >= 3:
        q = 1
    else:
        q = 0
    return max(min_quality, min(q, q if max_quality is None else max_quality))


def giant_roll(x: int, y: int, days_played: int, game_id: int, key: str, chance: float = 0.009999999776482582, *,
               legacy: bool = False) -> bool:
    """Whether the crop at top-left tile (x, y) wins its giant roll for the Data/GiantCrops entry `key`, on the
    night that starts day `days_played` (tonight is the save's days played + 1). Chance >= 1 always wins."""
    if chance >= 1:
        return True
    return day_save_random(days_played, game_id, x, y, hash_text(key), legacy=legacy).next_double() < chance


# --- from the save -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ahead:
    location: str
    tile: tuple[int, int]
    harvest_id: str
    name: str
    fertilizer: str  # qualified id, "" if none
    regrows: bool | None
    days_played: tuple[int, ...]  # the days covered, today first
    qualities: tuple[int, ...]  # quality if picked on each of those days
    cut_short: str = ""  # why the window ends early ("dies when Summer starts"), "" if it doesn't

    @property
    def today(self) -> int:
        return self.qualities[0]

    @property
    def best(self) -> int:
        return max(self.qualities)

    @property
    def best_day(self) -> int:
        """The first day (days played) with the best quality."""
        return self.days_played[self.qualities.index(self.best)]

    @property
    def worth_waiting(self) -> bool:
        return self.best > self.today


@dataclass(frozen=True)
class GiantHit:
    key: str  # the Data/GiantCrops entry, e.g. "Cauliflower"
    location: str
    tile: tuple[int, int]  # the top-left crop
    harvest_id: str
    days_played: int  # the day the giant crop would be there in the morning
    missing: tuple[tuple[int, int], ...]  # square tiles without a same-crop crop now
    ripens_tonight: bool  # top-left not ripe yet but grows into its last phase that night (if watered)
    watered: bool  # top-left watered this morning (else it needs water before that night)
    overlaps: tuple[tuple[int, int], ...] = ()  # other hits whose squares share tiles: only one can form

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def sure(self) -> bool:
        return not self.overlaps


@dataclass(frozen=True)
class GiantNight:
    days_played: int
    ready: tuple[GiantHit, ...]  # the square is filled now
    incomplete: tuple[GiantHit, ...]  # the roll hits but the square lacks crops (`missing`)


def _game_id(save: Save) -> int:
    if not str(save.unique_id or "").isdigit():
        raise ValueError("the save has no game id, so its rolls can't be worked out")
    return int(save.unique_id)


def _seasons(crop: Crop, crops_data: dict) -> set[str] | None:
    """The seasons a crop lives in where seasons apply; None where they don't (or unknown)."""
    if crop.location in _SEASONLESS or crop.location.startswith(_ISLAND):
        return None
    row = crops_data.get(crop.seed_id)
    if not row or not row.get("Seasons"):
        return None
    return {s.lower() for s in row["Seasons"]}


def _harvestable(crop: Crop) -> bool:
    return crop.ready and not crop.dead and not crop.forage and bool(crop.harvest_id) and crop.tile is not None


def quality_ahead(save: Save, data: GameData, *, days: int = 5, farming: int | None = None) -> list[Ahead]:
    """For each ripe crop, the quality it gives if picked on each of the next `days` days (today first), at
    today's Farming level (or `farming`) and the tile's fertilizer. The window stops early when the crop would die
    as its season ends."""
    gid, legacy = _game_id(save), save.legacy_random
    level = save.skills.get("farming", 0) if farming is None else farming
    crops_data = data.asset("Data/Crops")
    objects = data.asset("Data/Objects")
    out = []
    for c in save.crops:
        if not _harvestable(c):
            continue
        row = crops_data.get(c.seed_id) or {}
        lo, hi = row.get("HarvestMinQuality") or 0, row.get("HarvestMaxQuality")
        seasons = _seasons(c, crops_data)
        dps, cut = [], ""
        for dp in range(save.days_played, save.days_played + max(1, days)):
            season = date_of(dp)[0]
            if dps and seasons is not None and season not in seasons:
                cut = f"dies when {season.capitalize()} starts"
                break
            dps.append(dp)
        x, y = c.tile
        qs = tuple(harvest_quality(x, y, dp, gid, level, quality_boost(c.fertilizer), min_quality=lo,
                                   max_quality=hi, legacy=legacy) for dp in dps)
        out.append(Ahead(c.location, c.tile, c.harvest_id, objects.get(c.harvest_id, {}).get("Name", c.harvest_id),
                         c.fertilizer, c.regrows, tuple(dps), qs, cut))
    return out


def _giant_entries(data: GameData) -> dict[str, list[tuple[str, dict]]]:
    """Unqualified harvest id -> [(key, entry)] in data order."""
    by_crop: dict[str, list[tuple[str, dict]]] = {}
    for key, entry in data.asset("Data/GiantCrops").items():
        crop_id = str(entry.get("FromItemId") or "")
        if crop_id.startswith("(O)") or "(" not in crop_id:
            by_crop.setdefault(crop_id.removeprefix("(O)"), []).append((key, entry))
    return by_crop


def giant_tonight(save: Save, data: GameData, *, night: int = 1) -> GiantNight:
    """Giant crops the Farm grows on a coming night: night 1 is tonight (into tomorrow), night 2 the one after.
    Counts crops that are in their last phase by that night if watered every night, left unpicked; assumes the
    other crops stay as they are now."""
    gid, legacy = _game_id(save), save.legacy_random
    dp = save.days_played + night
    season = date_of(dp)[0]
    crops_data = data.asset("Data/Crops")
    entries = _giant_entries(data)
    planted = {c.tile: c.harvest_id for c in save.crops
               if c.location == "Farm" and not c.in_pot and c.tile is not None and not c.forage}
    hits: list[tuple[GiantHit, set[tuple[int, int]]]] = []
    for c in save.crops:
        if c.location != "Farm" or c.in_pot or c.dead or c.forage or c.tile is None:
            continue
        if c.harvest_id not in entries or c.days_left > night:
            continue
        seasons = _seasons(c, crops_data)
        if seasons is not None and season not in seasons:
            continue
        x, y = c.tile
        for key, entry in entries[c.harvest_id]:
            if entry.get("Condition"):
                continue  # a game-state condition we don't check: none in 1.6.15
            if not giant_roll(x, y, dp, gid, key, entry.get("Chance", 1.0), legacy=legacy):
                continue
            size = entry.get("TileSize") or {"X": 3, "Y": 3}
            square = {(x + i, y + j) for j in range(size["Y"]) for i in range(size["X"])}
            missing = tuple(sorted(t for t in square if planted.get(t) != c.harvest_id))
            hits.append((GiantHit(key, c.location, c.tile, c.harvest_id, dp, missing,
                                  ripens_tonight=not c.ready, watered=c.watered or save.wet), square))
            if not missing:
                break  # it forms; an entry whose square isn't filled lets the next entry try
    ready = [(h, sq) for h, sq in hits if h.complete]
    marked = []
    for h, sq in ready:
        others = tuple(o.tile for o, osq in ready if o is not h and osq & sq)
        marked.append(replace(h, overlaps=others))
    return GiantNight(dp, tuple(marked), tuple(h for h, _ in hits if not h.complete))
