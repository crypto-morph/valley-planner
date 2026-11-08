"""What happens on the farm overnight, tonight and the nights to come (1.6.15).

In our words (Utility.pickFarmEvent, then the event's setUp):
- The roll is made after the date moves on, so it uses the morning's days played, date, year and weather.
- One generator, seeded from (days played, game id / 2) (the day's shop random), skips 10 numbers. Then, in order,
  the first match wins:
  1. a wedding that morning: no farm event at all;
  2. the morning of day 31: the earthquake (the railroad opens);
  3. Community Center / Joja work finished that day (cc<Room> / joja<Room> mail for tomorrow), Leo moving;
  4. after the Community Center cutscene, a rainy morning: JojaMart is abandoned (unless it already was or the
     movie theater is done); Willy's boat fixed once its three parts are in; the golden parrots, once paid for;
  5. with the Pantry done (ccPantry), one number < 0.1, and the big tree hasn't fallen yet: the windstorm;
  6. without sawQiPlane, once the first billboard prize ticket is had or days played is over 50: Mr. Qi's plane;
  7. a number < 0.01 (0.017 if a fairy rose matured that night), not winter, not the 1st: the crop fairy;
  8. a number < 0.01, days played over 20: the witch;
  9. a number < 0.01, days played over 5: a meteorite;
  10. a number < 0.005: the stone owl;
  11. a number < 0.008, year 2 on, Got_Capsule not had: the strange capsule (Got_Capsule is set right there).
  Steps 5-11 always draw their number when reached (step 5 only with the Pantry done), so the Pantry being done
  shifts every later roll.
- Where it lands uses a second generator seeded from (game id, days played):
  - meteorite: x = Next(5, map width - 20), y = Next(5, map height - 4); it lands as a 2x2 rock at x..x+1, y..y+1,
    but the game first checks the 3x3 area x..x+2, y-1..y+1: no building, big stump/log/boulder, object, or tile
    the map blocks, and no water in x..x+2, y..y+1. Trees, grass and dirt don't stop it (it clears them). If any
    of that fails, the night is quiet: nothing else happens instead.
  - owl statue and strange capsule: up to 50 tiles x = Next(5, width - 4), y = Next(5, height - 4); the first
    one an item could be placed on wins (no object, crop, tree, bush, big rock, building, animal, water or
    map-blocked tile). If none of the 50 is free, a quiet night.
  - crop fairy: the Farm's growing crops (not dead, not wild seeds, not yet in their last phase), by x then y,
    one chosen with Next(count). Rain that morning cancels it, as does having no growing crop.
  - witch: each Big or Deluxe Coop that isn't full and holds under 50 objects takes it with chance 0.8 (the last
    one that passes wins); failing that a Slime Hutch with slimes and no Slime Ball, on a coin flip.
- What this can't see, and so assumes unchanged from the save: mail that arrives later (a Community Center room
  finished, the Pantry, the billboard prize ticket), a Rain Totem, and the farm itself. Personal events (a baby,
  Marnie's animals giving birth, the spouse asking for a child) only come on a night with no farm event and roll
  their own numbers, so they don't change anything here and aren't forecast. Single player only: farmhands'
  weddings also stop the roll.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import weather
from .conditions import date_of
from .rng import NetRandom, day_save_random, random_seed
from .walk import Walker

CLUMPS = {"600": "stump", "602": "log", "622": "meteorite", "672": "boulder", "752": "boulder", "754": "boulder",
          "756": "boulder", "758": "boulder"}
COOPS = ("Big Coop", "Deluxe Coop")
SLIME_HUTCH = "Slime Hutch"
SLIME_BALL = "83"  # big craftable
OBJECT_LIMIT = 50  # the witch skips a coop with this many objects in it
BUSH_WIDTH = {1: 2, 2: 3, 4: 2}  # by bush size; the rest are one tile
TRIES = 50  # owl statue and capsule placement attempts
WILD_SEED_ROW = 23  # crops sprite row of wild seeds (isWildSeedCrop)
CC_WORK = ("leoMoved", "jojaPantry", "ccPantry", "jojaVault", "ccVault", "jojaBoilerRoom", "ccBoilerRoom",
           "jojaCraftsRoom", "ccCraftsRoom", "jojaFishTank", "ccFishTank", "ccMovieTheaterJoja", "jojaMovieTheater",
           "ccMovieTheater")
CC_CUTSCENE = "191393"
NO_LETTER = "%&NL&%"
WET = ("rain", "storm", "green rain")
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
Tile = tuple[int, int]


@dataclass(frozen=True)
class Night:
    days_played: int  # the morning it's found
    kind: str | None  # meteorite, fairy, witch, owl, capsule, windstorm, qi plane, earthquake, world change, wedding
    tile: Tile | None = None  # meteorite (top-left of the 2x2), owl statue, capsule; the crop the fairy picks
    what: str = ""  # the fairy's crop, the witch's building, what blocks a meteorite…
    lands: bool = True  # with the farm as it is now, it happens (False: the game calls it off; a quiet night)
    sure: bool = True  # False when it hangs on farm state that may change before then (crops, a clearable tile…)

    @property
    def label(self) -> str:
        season, day, year = date_of(self.days_played)
        return f"{season.capitalize()} {day}, Year {year}"


# --- the roll -------------------------------------------------------------------------


def pick(days_played: int, game_id: int, *, mail=frozenset(), mail_tomorrow=frozenset(), events_seen=frozenset(),
         raining: bool = False, wedding: bool = False, fairy_rose: bool = False, parrots_done: bool = False,
         legacy: bool = False) -> str | None:
    """Utility.pickFarmEvent for the night before the morning `days_played`; `mail` is had or arriving."""
    rng = day_save_random(days_played, game_id, legacy=legacy)
    for _ in range(10):
        rng.next_double()
    season, day, year = date_of(days_played)
    if wedding:
        return "wedding"
    if days_played == 31:
        return "earthquake"
    tomorrow = {m.removesuffix(NO_LETTER) for m in mail_tomorrow}
    if any(m in tomorrow for m in CC_WORK):
        return "world change"
    if CC_CUTSCENE in events_seen and raining and not {"abandonedJojaMartAccessible", "ccMovieTheater"} & mail:
        return "world change"
    if {"willyBoatTicketMachine", "willyBoatHull", "willyBoatAnchor"} <= mail and "willyBoatFixed" not in mail:
        return "world change"
    if "activateGoldenParrotsTonight" in mail and not parrots_done:
        return "world change"
    if "ccPantry" in mail and rng.next_double() < 0.1 and "raccoonTreeFallen" not in mail:
        return "windstorm"
    if "sawQiPlane" not in mail and ("gotFirstBillboardPrizeTicket" in mail or days_played > 50):
        return "qi plane"
    if rng.next_double() < 0.01 + (0.007 if fairy_rose else 0) and season != "winter" and day != 1:
        return "fairy"
    if rng.next_double() < 0.01 and days_played > 20:
        return "witch"
    if rng.next_double() < 0.01 and days_played > 5:
        return "meteorite"
    if rng.next_double() < 0.005:
        return "owl"
    if rng.next_double() < 0.008 and year > 1 and "Got_Capsule" not in mail:
        return "capsule"
    return None


AFTER = {"capsule": "Got_Capsule", "windstorm": "raccoonTreeFallen", "qi plane": "sawQiPlane"}


def place_random(game_id: int, days_played: int, *, legacy: bool = False) -> NetRandom:
    """The generator the events place themselves with: Rand(game id, days played)."""
    return NetRandom(random_seed(game_id, days_played, legacy=legacy))


def meteor_tile(game_id: int, days_played: int, width: int, height: int, *, legacy: bool = False) -> Tile:
    rng = place_random(game_id, days_played, legacy=legacy)
    return rng.next(5, width - 20), rng.next(5, height - 4)


def statue_tiles(game_id: int, days_played: int, width: int, height: int, *, legacy: bool = False) -> list[Tile]:
    """The 50 tiles the owl statue or the capsule tries, in order."""
    rng = place_random(game_id, days_played, legacy=legacy)
    return [(rng.next(5, width - 4), rng.next(5, height - 4)) for _ in range(TRIES)]


def meteor_area(tile: Tile) -> tuple[list[Tile], list[Tile]]:
    """(tiles that must be open, tiles that must be dry) for a meteorite at `tile`."""
    x, y = tile
    return ([(x + dx, y + dy) for dx in range(3) for dy in (-1, 0, 1)],
            [(x + dx, y + dy) for dx in range(3) for dy in (0, 1)])


# --- the farm as the save has it ---------------------------------------------------------


@dataclass
class Building:
    type: str
    x: int
    y: int
    w: int
    h: int
    animals: int = 0  # living here
    room: int = 0  # animals it holds
    objects: int = 0  # inside
    slimes: int = 0
    slime_ball: bool = False

    def covers(self, t: Tile) -> bool:
        return self.x <= t[0] < self.x + self.w and self.y <= t[1] < self.y + self.h


@dataclass
class FarmState:
    width: int
    height: int
    walls: set[Tile]  # tiles the map blocks (from the map, never change)
    water: set[Tile]
    buildings: list[Building] = field(default_factory=list)
    clumps: dict[Tile, str] = field(default_factory=dict)  # every tile a big stump/log/boulder covers -> name
    objects: dict[Tile, str] = field(default_factory=dict)
    solid: dict[Tile, str] = field(default_factory=dict)  # trees past the seed, fruit trees, bushes
    planted: dict[Tile, str] = field(default_factory=dict)  # dirt with a crop -> what it grows
    growing: list[tuple[Tile, str]] = field(default_factory=list)  # what the fairy can pick, by x then y
    animals: set[Tile] = field(default_factory=set)  # animals outside on the Farm

    def building_at(self, t: Tile) -> Building | None:
        return next((b for b in self.buildings if b.covers(t)), None)

    def meteor_blocker(self, t: Tile) -> str | None:
        """Farm.isTileOpenBesidesTerrainFeatures, as words: what stops a meteorite here, or None."""
        if b := self.building_at(t):
            return b.type
        if t in self.clumps:
            return self.clumps[t]
        if t in self.animals:
            return None
        if t in self.objects:
            return self.objects[t]
        return "the map" if self._off(t) else None

    def placement_blocker(self, t: Tile) -> str | None:
        """GameLocation.CanItemBePlacedHere for a big craftable, as words."""
        if self._off(t):
            return "the map"
        if t in self.water:
            return "water"
        for found in (self.planted, self.objects, self.clumps, self.solid):
            if t in found:
                return "a crop" if found is self.planted else found[t]
        if t in self.animals:
            return "an animal"
        b = self.building_at(t)
        return b.type if b else None

    def permanent(self, why: str | None) -> bool:
        return why in ("the map", "water")

    def _off(self, t: Tile) -> bool:
        return not (0 <= t[0] < self.width and 0 <= t[1] < self.height) or t in self.walls


def _tag(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _child(el, name: str):
    """A child element by name, any case (the save writes some names both ways)."""
    if el is None:
        return None
    return next((c for c in el if _tag(c).lower() == name.lower()), None)


def _text(el, name: str, default: str = "") -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None and c.text else default


def _num(el, name: str) -> int:
    try:
        return int(float(_text(el, name, "0")))
    except ValueError:
        return 0


def _kids(el) -> list:
    return list(el) if el is not None else []


def _items(el):
    for item in _kids(el):
        k, v = _child(item, "key"), _child(item, "value")
        if k is not None and v is not None:
            yield k, v


def _vec(el) -> Tile | None:
    v = _child(el, "Vector2") if el is not None and _child(el, "X") is None else el
    return None if v is None or _child(v, "X") is None else (_num(v, "X"), _num(v, "Y"))


def _first(el):
    """A dictionary value's single wrapped element (<value><Object …>), or the value itself."""
    kids = list(el)
    return kids[0] if len(kids) == 1 and list(kids[0]) else el


def _farm_location(root):
    for loc in _kids(_child(root, "locations")):
        if _text(loc, "name") == "Farm":
            return loc
    return None


def _building(b) -> Building:
    btype = _text(b, "buildingType")
    inside = _child(b, "indoors")
    objects = list(_items(_child(inside, "objects")))
    names = {_text(_first(v), "itemId") or _text(_first(v), "parentSheetIndex") for _k, v in objects}
    return Building(btype, _num(b, "tileX"), _num(b, "tileY"), _num(b, "tilesWide"), _num(b, "tilesHigh"),
                    animals=len(_kids(_child(inside, "animalsThatLiveHere"))), room=_num(b, "maxOccupants"),
                    objects=len(objects),
                    slimes=len(_kids(_child(inside, "characters"))), slime_ball=SLIME_BALL in names)


def _crop(dirt) -> tuple[bool, str] | None:
    """(the fairy could pick it, harvest id) for a crop in this dirt, or None."""
    crop = _child(dirt, "crop")
    if crop is None or crop.attrib.get(XSI + "nil") == "true" or not list(crop):
        return None
    phases = _kids(_child(crop, "phaseDays"))
    wild = _num(crop, "rowInSpriteSheet") == WILD_SEED_ROW and not _text(crop, "overrideTexturePath")
    growing = (_text(crop, "dead") != "true" and not wild and _num(crop, "currentPhase") < len(phases) - 1)
    return growing, _text(crop, "indexOfHarvest")


def farm_state(save, data) -> FarmState:
    """The Farm's blockers, crops and buildings as the save has them (read from the save file)."""
    return _farm_state(Path(save.path), getattr(save, "mtime", 0.0), save.farm_type, data)


def map_state(data, farm_type: int = 0) -> FarmState:
    """An empty farm: just the map's size, the tiles it blocks and its water."""
    walker = Walker(data, farm_type)
    width, height, walls = walker.grids["Farm"]
    water = {tuple(int(v) for v in t.split(",")) for t in data.asset(f"Maps/{walker.farm_map}").get("Water", [])}
    return FarmState(width, height, set(walls), water)


@lru_cache(maxsize=4)
def _farm_state(path: Path, _mtime: float, farm_type: int, data) -> FarmState:
    state = map_state(data, farm_type)
    objects_data = data.asset("Data/Objects")
    farm = _farm_location(ET.parse(path).getroot())  # noqa: S314 — the player's own local save
    if farm is None:
        return state
    state.buildings = [_building(b) for b in _kids(_child(farm, "buildings")) if _text(b, "buildingType")]
    for clump in _kids(_child(farm, "resourceClumps")):
        x, y = _vec(_child(clump, "tile")) or (0, 0)
        name = CLUMPS.get(_text(clump, "parentSheetIndex"), "giant crop")
        for dx in range(max(1, _num(clump, "width"))):
            for dy in range(max(1, _num(clump, "height"))):
                state.clumps[(x + dx, y + dy)] = name
    for k, v in _items(_child(farm, "objects")):
        if (t := _vec(k)) is not None:
            state.objects[t] = _text(_first(v), "name") or "something"
    for k, v in _items(_child(farm, "terrainFeatures")):
        t, feature = _vec(k), _first(v)
        kind = feature.attrib.get(XSI + "type", "") or _tag(feature)
        if t is None:
            continue
        if kind == "HoeDirt" and (crop := _crop(feature)) is not None:
            name = (objects_data.get(crop[1]) or {}).get("Name") or crop[1]
            state.planted[t] = name
            if crop[0]:
                state.growing.append((t, name))
        elif kind == "FruitTree" or (kind == "Tree" and _num(feature, "growthStage") > 0):
            state.solid[t] = "a tree"
    state.growing.sort()
    for feature in _kids(_child(farm, "largeTerrainFeatures")):
        if (t := _vec(_child(feature, "tilePosition"))) is not None:
            for dx in range(BUSH_WIDTH.get(_num(feature, "size"), 1)):
                state.solid[(t[0] + dx, t[1])] = "a bush"
    for _k, v in _items(_child(farm, "animals")):
        pos = _child(_first(v), "Position")
        if pos is not None:
            state.animals.add(((_num(pos, "X") + 32) // 64, (_num(pos, "Y") + 32) // 64))
    return state


def meteor_blockers(save, data, tile: Tile, state: FarmState | None = None) -> list[tuple[Tile, str]]:
    """What, on the farm as it is now, would stop a meteorite landing at `tile`: [] when it's clear."""
    state = state or farm_state(save, data)
    must_open, must_dry = meteor_area(tile)
    out = [(t, why) for t in must_open if (why := state.meteor_blocker(t))]
    out += [(t, "water") for t in must_dry if t in state.water]
    return out


# --- each night, placed -------------------------------------------------------------------


def _meteor(night: int, game_id: int, state: FarmState, legacy: bool) -> Night:
    tile = meteor_tile(game_id, night, state.width, state.height, legacy=legacy)
    blocks = meteor_blockers(None, None, tile, state)
    if not blocks:
        return Night(night, "meteorite", tile)
    stuck = all(state.permanent(why) for _t, why in blocks)
    what = ", ".join(sorted({why for _t, why in blocks}))
    return Night(night, "meteorite", tile, what=f"blocked by {what}", lands=False, sure=stuck)


def _statue(kind: str, night: int, game_id: int, state: FarmState, legacy: bool) -> Night:
    sure = True
    for t in statue_tiles(game_id, night, state.width, state.height, legacy=legacy):
        why = state.placement_blocker(t)
        if why is None:
            return Night(night, kind, t, sure=sure)
        sure = sure and state.permanent(why)  # clearing an earlier tile would move it there
    return Night(night, kind, lands=False, what="no free tile", sure=sure)


def _fairy(night: int, game_id: int, state: FarmState, raining: bool, legacy: bool) -> Night:
    if raining:
        return Night(night, "fairy", lands=False, what="rain calls it off")
    if not state.growing:
        return Night(night, "fairy", lands=False, what="no growing crop", sure=False)
    tile, crop = place_random(game_id, night, legacy=legacy).choose(state.growing)
    return Night(night, "fairy", tile, what=crop, sure=False)


def _witch(night: int, game_id: int, state: FarmState, golden: bool, legacy: bool) -> Night:
    rng = place_random(game_id, night, legacy=legacy)
    target = None
    for b in state.buildings:
        if b.type in COOPS and b.animals < b.room and b.objects < OBJECT_LIMIT \
                and rng.next_double() < 0.8:
            target = b
            if golden:
                rng.next_double()  # the golden witch: same coop, a different gift
    if target is None:
        for b in state.buildings:
            if b.type == SLIME_HUTCH and b.slimes > 0 and rng.next_double() < 0.5 and not b.slime_ball:
                target = b
    if target is None:
        return Night(night, "witch", lands=False, what="no coop or slime hutch for her", sure=False)
    return Night(night, "witch", (target.x, target.y), what=target.type, sure=False)


@lru_cache(maxsize=4)
def _world(path: Path, _mtime: float, spouse: str | None) -> tuple[int | None, bool]:
    """(days played of the morning of a wedding already set, golden parrots already active), from the save file."""
    root = ET.parse(path).getroot()  # noqa: S314 — the player's own local save
    parrots = any(_tag(e) == "activatedGoldenParrot" and (e.text or "").strip() == "true" for e in root.iter())
    return _wedding_day(root, spouse), parrots


def _wedding_day(root, spouse: str | None) -> int | None:
    if not spouse:
        return None
    for k, v in _items(_child(_child(root, "player"), "friendshipData")):
        if "".join(k.itertext()).strip() != spouse:
            continue
        friendship = _first(v)
        if _text(friendship, "Status") != "Engaged":
            return None
        date = _child(friendship, "WeddingDate")
        if date is None or not list(date):
            return None
        season = _text(date, "Season").lower()
        seasons = ("spring", "summer", "fall", "winter")
        index = seasons.index(season) if season in seasons else _num(date, "SeasonIndex")
        return (_num(date, "Year") - 1) * 112 + index * 28 + _num(date, "DayOfMonth")
    return None


def nights(save, data, *, count: int = 28, festivals=None) -> list[Night]:
    """Tonight (ending in tomorrow morning) and the `count` - 1 nights after it, in order.

    `festivals` is a set of (season, day) with fixed sunny weather; read from the game data when not given.
    """
    game_id, legacy = int(save.unique_id), save.legacy_random
    if festivals is None:
        from .calendar import Calendar
        festivals = set(Calendar(data).festivals)
    state = farm_state(save, data)
    mail = set(save.mail) | set(save.mailbox)
    tomorrow = set(save.mail_tomorrow)
    wedding, parrots = _world(Path(save.path), getattr(save, "mtime", 0.0), save.spouse)
    rose = any(c.harvest_id == "595" and c.ready for c in save.crops)
    out = []
    for night in range(save.days_played + 1, save.days_played + 1 + count):
        season, day, _ = date_of(night)
        if night == save.days_played + 1:
            sky, sky_sure = save.weather_tomorrow, True
        else:
            sky, sky_sure = weather.forecast(night, game_id, festival=(season, day) in festivals, legacy=legacy)
        args = dict(mail=frozenset(mail | {m.removesuffix(NO_LETTER) for m in tomorrow}), mail_tomorrow=tomorrow,
                    events_seen=frozenset(save.events_seen), raining=sky in WET, wedding=night == wedding,
                    parrots_done=parrots, legacy=legacy)
        kind = pick(night, game_id, **args)
        rose_matters = pick(night, game_id, fairy_rose=True, **args) != kind
        if rose_matters and rose:  # a fairy rose grown today will most likely still be there tonight
            kind = "fairy"
        result = _place(kind, night, game_id, state, sky in WET, "Farm_Eternal" in mail, legacy)
        if rose_matters or (not sky_sure and (kind == "fairy" or CC_CUTSCENE in save.events_seen)):
            result = Night(result.days_played, result.kind, result.tile, result.what, result.lands, sure=False)
        out.append(result)
        mail |= {m.removesuffix(NO_LETTER) for m in tomorrow}
        tomorrow = set()
        if kind in AFTER:
            mail.add(AFTER[kind])
    return out


def _place(kind: str | None, night: int, game_id: int, state: FarmState, raining: bool, golden: bool,
           legacy: bool) -> Night:
    if kind == "meteorite":
        return _meteor(night, game_id, state, legacy)
    if kind in ("owl", "capsule"):
        return _statue(kind, night, game_id, state, legacy)
    if kind == "fairy":
        return _fairy(night, game_id, state, raining, legacy)
    if kind == "witch":
        return _witch(night, game_id, state, golden, legacy)
    return Night(night, kind)
