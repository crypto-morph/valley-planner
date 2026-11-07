"""What each artifact spot (the wiggling worms) and seed spot holds today (1.6.15).

In our words (Object.performToolAction, then GameLocation.digUpArtifactSpot):
- Hoeing either kind of spot first counts it (stat ArtifactSpotsDug + 1), then, once that count is over 2, rolls
  for the Book of Defense ("Jack Be Nimble, Jack Be Thick") from a generator seeded (days played, game id / 2,
  -x * 7, y * 777, Treasure Totems used * 777): a hit when the number is under 0.008 + 0.002 * the count (0.013
  once the book has dropped before). The count grows with each spot dug, so which spot is dug first matters.
- A seed spot then takes from that same generator: Next(2, 4) seeds, plus one more while a number is under
  0.1 + daily luck. The seeds are the season's Raccoon seeds (Carrot, Summer Squash, Broccoli, Powdermelon), the
  next season's after day 23 in spring and day 20 in the other seasons.
- An artifact spot uses its own generator, seeded (days played, game id / 2, x * 2000, y, totems * 777), and draws
  in this order, every draw counting:
  1. with sawQiPlane mail: a number < 0.05 + luck / 2 gives Next(1, 3) Mystery Boxes;
  2. rare finds: with farming mastery a number < 0.009 * (1 + luck) gives a Golden Animal Cracker; after day 2 a
     number < 0.018 gives a cosmetic item (hat, shirt or furniture), then a number < 0.0054 gives skill book
     Next(5);
  3. the Data/Locations "Default" ArtifactSpots then the location's own, stably sorted by Precedence. Each entry
     draws for its Chance (none when Chance >= 1), then checks its Condition (whose RANDOM queries draw too, in
     order, stopping at the first false part), then resolves its item: a RandomItemId list picks with Next(n); a
     query such as LOST_BOOK_OR_ITEM (Lost Book until 21 found), SECRET_NOTE_OR_ITEM or
     RANDOM_ARTIFACT_FOR_DIG_SPOT (each Arch object, in data order, with a chance for this location — doubled by
     the Archaeologist hoe — draws until one hits) then draws Next(1) for its pick; a stack range draws
     Next(min, max + 1); stack modifiers' conditions draw. The Generous hoe adds a coin flip for a second copy.
     The first entry that gives an item ends the list unless it says ContinueOnDrop.
- Ginger Island spots first roll on their own generator (days played, game id / 2, x * 2000, y): a Golden Coconut
  (only once one has been cracked, < 0.1), else Taro Tuber Next(2, 5) (< 0.33), else an Artifact Trove Next(1, 3)
  (< 0.15). The Desert Festival's spots give Next(3, 7) Calico Eggs the same way first.
- Seasons for LOCATION_SEASON: the island and the desert are always summer.
- A spot not dug today is gone or re-rolled tomorrow (the seed has days played in it).

Unsure (the spot is marked sure=False):
- a Secret Note (Journal Scrap on the island) once you have the Magnifying Glass and notes are left to find: the
  game decides with its own unseeded random, so the drop is "note or the fallback item";
- the Book of Defense when today's dig order changes the answer, and a seed spot's count on your first two digs
  ever (whether the book roll draws at all);
- a cosmetic item (rare): what it is, and everything after it;
- a condition we can't read from the save; luck and mining levels are taken without food buffs; a single player
  is assumed (luck is the average of online farmers); the hoe is assumed to be the one in the backpack (if they
  differ in enchantments the spot is unsure).
"""

from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from .conditions import When, _query, split
from .rng import NetRandom, day_save_random

ARTIFACT_SPOT, SEED_SPOT = "590", "SeedSpot"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
ISLAND_TYPES = {"IslandLocation", "IslandNorth", "IslandSouth", "IslandSouthEast", "IslandSouthEastCave", "IslandWest",
                "IslandEast", "IslandShrine", "IslandForestLocation", "IslandFarmCave", "IslandHut", "IslandSecret",
                "IslandFieldOffice", "Caldera", "VolcanoDungeon"}
DESERT = {"Desert", "SkullCave", "DesertFestival"}
FARM_KEYS = {0: "Standard", 1: "Riverland", 2: "Forest", 3: "Hilltop", 4: "Wilderness", 5: "FourCorners", 6: "Beach",
             7: "MeadowlandsFarm"}  # 7: a data-defined farm; Meadowlands is the only one in the base game
RACCOON_SEEDS = {"spring": "CarrotSeeds", "summer": "SummerSquashSeeds", "fall": "BroccoliSeeds",
                 "winter": "PowdermelonSeeds"}
SEASONS = ("spring", "summer", "fall", "winter")
JOURNAL_INDEX = 1000
LOST_BOOKS = 21
RESOLVERS = ("LOST_BOOK_OR_ITEM", "SECRET_NOTE_OR_ITEM", "RANDOM_ARTIFACT_FOR_DIG_SPOT")


@dataclass(frozen=True)
class Drop:
    id: str  # qualified, e.g. "(O)330"; "" for something we can't name
    name: str
    count: int = 1
    sure: bool = True  # False: may not come, or may be something else (see the spot's notes)


@dataclass(frozen=True)
class Spot:
    location: str
    tile: tuple[int, int]
    kind: str  # "artifact" or "seed"
    drops: tuple[Drop, ...]
    sure: bool
    notes: tuple[str, ...] = ()  # why it isn't sure
    reachable: bool | None = True  # False: a place you can't get to today; None: not known (deeper island areas)


@dataclass
class Digger:
    """What a dig reads: the day, the farm and the farmer."""

    days_played: int
    game_id: int
    season: str
    day: int
    legacy: bool = False
    luck: float = 0.0  # Farmer.DailyLuck (charm included, clamped)
    totems: int = 0  # Treasure Totems used (ever)
    mail: frozenset = frozenset()
    luck_level: int = 0
    mining_level: int = 0
    farming_mastery: bool = False  # stat mastery_0
    lost_books: int = 0
    coconut_cracked: bool = False
    island_bridge: bool = False  # IslandNorth's bridge fixed
    orders: frozenset = frozenset()  # special orders in progress (keys)
    rules: frozenset = frozenset()  # their special rules
    notes_left: int = 0  # Secret Notes still to find, less the ones in the backpack
    journal_left: int = 0  # Journal Scraps likewise
    archaeologist: bool | None = False  # None: the backpack's hoes differ
    generous: bool | None = False
    farm_key: str = "Standard"
    dug: int = 0  # stat ArtifactSpotsDug this morning
    digs_today: int = 1  # spots there are to dig today (all kinds): bounds the dig count for the book
    when: When | None = None  # for other condition queries

    @property
    def magnifying(self) -> bool:
        return "HasMagnifyingGlass" in self.mail


class _Unsure(Exception):
    pass


def _season_here(location: str, xsi_type: str, d: Digger) -> str:
    if xsi_type in ISLAND_TYPES or location.startswith("Island"):
        return "summer"
    return "summer" if location in DESERT else d.season


def _condition(cond: str | None, r: NetRandom, location: str, xsi_type: str, d: Digger, notes: list) -> bool:
    """GameStateQuery.CheckConditions with the dig's random: in order, stopping at the first false part."""
    if not cond or cond == "TRUE":
        return True
    if cond == "FALSE":
        return False
    for tokens in split(cond):
        negate = tokens[0].startswith("!")
        key, args = tokens[0].lstrip("!").upper(), tokens[1:]
        if key == "RANDOM":
            chance = _f32(float(args[0])) + (_f32(d.luck) if any(a.lower() == "@adddailyluck" for a in args) else 0)
            result = r.next_double() < _f32(chance)
        elif key == "LOCATION_SEASON" and args and args[0].lower() == "here":
            result = _season_here(location, xsi_type, d) in {a.lower() for a in args[1:]}
        elif key == "PLAYER_LOCATION_NAME":
            result = any(a.lower() == location.lower() for a in args[1:])
        elif key == "PLAYER_SPECIAL_ORDER_ACTIVE":
            result = any(a in d.orders for a in args[1:])
        elif key == "PLAYER_SPECIAL_ORDER_RULE_ACTIVE":
            result = any(a in d.rules for a in args[1:])
        elif key in ("PLAYER_LUCK_LEVEL", "PLAYER_MINING_LEVEL") and len(args) >= 2:
            level = d.luck_level if key == "PLAYER_LUCK_LEVEL" else d.mining_level
            hi = int(args[2]) if len(args) > 2 else 2**31 - 1
            result = int(args[1]) <= level <= hi
        elif key == "IS_ISLAND_NORTH_BRIDGE_FIXED":
            result = d.island_bridge
        elif key == "PLAYER_HAS_MAIL" and len(args) >= 2 and d.when is None:
            result = args[1] in d.mail
        elif key == "DAYS_PLAYED" and args:
            hi = int(args[1]) if len(args) > 1 else 2**31 - 1
            result = int(args[0]) <= d.days_played <= hi
        else:
            result = _query(key, args, d.when) if d.when is not None else None
            if result is None:
                notes.append(f"can't tell '{' '.join(tokens)}'")
                raise _Unsure
        if result == negate:
            return False
    return True


def _f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def _stack(entry: dict, r: NetRandom, location: str, xsi_type: str, d: Digger, notes: list, base: int = 1) -> int:
    """ItemQueryResolver.ApplyItemFields: the stack size, then its modifiers."""
    lo, hi = entry.get("MinStack", -1), entry.get("MaxStack", -1)
    n = base
    if lo == -1 and hi == -1:
        n = base
    elif hi > 1:
        lo = max(lo, 1)
        n = r.next(lo, max(hi, lo) + 1)
    elif lo > 1:
        n = lo
    mods = entry.get("StackModifiers") or []
    if mods:
        value = None
        for m in mods:
            amount = m.get("Amount", 0.0)
            if m.get("RandomAmount"):
                amount = r.choose(m["RandomAmount"])
            if not _condition(m.get("Condition"), r, location, xsi_type, d, notes):
                continue
            cur = n if value is None else value
            mod = m.get("Modification", "Add")
            value = {"Add": cur + amount, "Subtract": cur - amount, "Multiply": cur * amount,
                     "Divide": cur / amount if amount else cur, "Set": amount}.get(mod, cur)
        n = int(value if value is not None else n)
    return n


def _resolve(entry: dict, r: NetRandom, location: str, xsi_type: str, d: Digger, objects: dict,
             notes: list) -> list[tuple[str, bool]] | None:
    """The entry's item: [(qualified id, sure)] — two choices when the game decides with its own random — or None."""
    pick = entry.get("ItemId")
    if entry.get("RandomItemId"):
        pick = r.choose(entry["RandomItemId"])
    if not pick:
        return None
    key, _, args = pick.strip().partition(" ")
    if key not in RESOLVERS:
        return [(_qualify(pick), True)]
    if key == "LOST_BOOK_OR_ITEM":
        got = [("(O)102", True)] if d.lost_books < LOST_BOOKS else ([(_qualify(args), True)] if args else None)
    elif key == "SECRET_NOTE_OR_ITEM":
        island = xsi_type in ISLAND_TYPES
        left = d.journal_left if island else d.notes_left
        fallback = [(_qualify(args), True)] if args else None
        if (island or d.magnifying) and left > 0:
            note = "(O)842" if island else "(O)79"
            what = "a Journal Scrap" if island else "a Secret Note"
            notes.append(f"{what} may come instead (the game's own random)")
            got = [(note, False)] + ([(fallback[0][0], False)] if fallback else [])
        else:
            got = fallback
    else:  # RANDOM_ARTIFACT_FOR_DIG_SPOT
        mult = 2 if d.archaeologist else 1
        got = None
        for qid, obj in objects.items():
            if obj.get("Type") != "Arch":
                continue
            chance = (obj.get("ArtifactSpotChances") or {}).get(location)
            if chance is None:
                continue
            chance = _f32(mult * chance)
            if chance >= 1 or r.next_double() < chance:
                got = [(f"(O){qid}", True)]
                break
    if not got:
        return None
    r.next(1)  # the query's random pick among its one result
    return got


def _qualify(item_id: str) -> str:
    item_id = item_id.strip()
    return item_id if item_id.startswith("(") else f"(O){item_id}"


def _location_entries(location: str, locations: dict, farm_key: str) -> list[dict]:
    """Default's entries plus the location's, stably sorted by Precedence (GameLocation.GetData)."""
    if location == "Farm":
        own = locations.get(f"Farm_{farm_key}") or locations.get("Farm_Standard") or {}
    else:
        own = locations.get(location) or {}
    entries = list((locations.get("Default") or {}).get("ArtifactSpots") or [])
    entries += list(own.get("ArtifactSpots") or [])
    return sorted(entries, key=lambda e: e.get("Precedence", 0))


def dig_artifact(location: str, x: int, y: int, d: Digger, locations: dict, objects: dict, *,
                 xsi_type: str = "") -> tuple[list[Drop], bool, list[str]]:
    """GameLocation.digUpArtifactSpot (with the island's and desert festival's extras): (drops, sure, notes)."""
    drops: list[Drop] = []
    notes: list[str] = []
    sure = True
    if xsi_type in ISLAND_TYPES:
        ri = day_save_random(d.days_played, d.game_id, x * 2000, y, legacy=d.legacy)
        if d.coconut_cracked and ri.next_double() < 0.1:
            drops.append(Drop("(O)791", "", 1))
        elif ri.next_double() < 0.33:
            drops.append(Drop("(O)831", "", ri.next(2, 5)))
        elif ri.next_double() < 0.15:
            drops.append(Drop("(O)275", "", ri.next(1, 3)))
    elif location == "DesertFestival":
        rf = day_save_random(d.days_played, d.game_id, x * 2000, y, legacy=d.legacy)
        drops.append(Drop("(O)CalicoEgg", "", rf.next(3, 7)))

    r = day_save_random(d.days_played, d.game_id, x * 2000, y, d.totems * 777, legacy=d.legacy)
    if "sawQiPlane" in d.mail and r.next_double() < 0.05 + d.luck / 2.0:
        drops.append(Drop("(O)MysteryBox", "", r.next(1, 3)))
    # Utility.trySpawnRareObject(who, spot, here, 9.0, 1.0, -1, r)
    if d.farming_mastery and r.next_double() < 0.001 * 9.0 * (1.0 + d.luck * 1.0):
        drops.append(Drop("(O)GoldenAnimalCracker", "", 1))
    if d.days_played > 2 and r.next_double() < 0.002 * 9.0:
        drops.append(Drop("", "a cosmetic item (hat, shirt or furniture)", 1, sure=False))
        notes.append("a rare cosmetic item: which one, and what follows it, isn't worked out")
        return drops, False, notes
    if d.days_played > 2 and r.next_double() < 0.0006 * 9.0:
        drops.append(Drop(f"(O)SkillBook_{r.next(5)}", "", 1))

    if d.generous is None or d.archaeologist is None:
        sure = False
        notes.append("your hoes have different enchantments: worked out for the first one")
        d = replace(d, generous=bool(d.generous), archaeologist=bool(d.archaeologist))
    try:
        for entry in _location_entries(location, locations, d.farm_key):
            chance = entry.get("Chance", 1.0)
            if chance < 1.0 and not r.next_double() < chance:
                continue
            if not _condition(entry.get("Condition"), r, location, xsi_type, d, notes):
                continue
            got = _resolve(entry, r, location, xsi_type, d, objects, notes)
            if got is None:
                continue
            n = _stack(entry, r, location, xsi_type, d, notes)
            for qid, ok in got:
                drops.append(Drop(qid, "", n, sure=ok))
            if not all(ok for _q, ok in got):
                sure = False
            if d.generous and entry.get("ApplyGenerousEnchantment", True) and r.next_double() < 0.5:
                extra = _stack(entry, r, location, xsi_type, d, notes)
                drops.append(Drop(got[0][0], "", extra, sure=got[0][1]))
            if not entry.get("ContinueOnDrop", False):
                break
    except _Unsure:
        sure = False
    return drops, sure, notes


def book_roll(x: int, y: int, d: Digger) -> NetRandom:
    """The generator Object.performToolAction makes for the spot: the book roll, then a seed spot's seeds."""
    return day_save_random(d.days_played, d.game_id, -x * 7, y * 777, d.totems * 777, legacy=d.legacy)


def dig_book(r: NetRandom, d: Digger) -> tuple[bool | None, bool]:
    """(the Book of Defense drops: True / False / None if dig order decides, the roll drew for sure).
    The dig count is between dug + 1 (dug first today) and dug + digs_today (dug last)."""
    first, last = d.dug + 1, d.dug + max(1, d.digs_today)
    if last <= 2:
        return False, True
    if first <= 2:  # draws only if enough other spots are dug first
        r.next_double()
        return None, False
    roll = r.next_double()
    if "DefenseBookDropped" in d.mail:
        return roll < 0.008 + 0.005, True
    lo, hi = 0.008 + first * 0.002, 0.008 + last * 0.002
    return (True if roll < lo else False if roll >= hi else None), True


def raccoon_seed(season: str, day: int) -> str:
    """Utility.getRaccoonSeedForCurrentTimeOfYear: this season's, or the next's late in the season."""
    i = SEASONS.index(season)
    if day > (23 if season == "spring" else 20):
        i = (i + 1) % 4
    return f"(O){RACCOON_SEEDS[SEASONS[i]]}"


def dig_seed(r: NetRandom, d: Digger) -> int:
    n = r.next(2, 4)
    while r.next_double() < 0.1 + d.luck:
        n += 1
    return n


def dig(location: str, tile: tuple[int, int], kind: str, d: Digger, locations: dict, objects: dict, *,
        xsi_type: str = "") -> Spot:
    """One spot, hoed today."""
    x, y = tile
    notes: list[str] = []
    r2 = book_roll(x, y, d)
    book, drew_sure = dig_book(r2, d)
    drops: list[Drop] = []
    sure = True
    if book is not False:
        drops.append(Drop("(O)Book_Defense", "", 1, sure=book is True))
        if book is None:
            sure = False
            notes.append("the Book of Defense depends on how many spots you dig before this one")
    if kind == "seed":
        drops.append(Drop(raccoon_seed(d.season, d.day), "", dig_seed(r2, d), sure=drew_sure))
        if not drew_sure:
            sure = False
            notes.append("the seed count depends on whether this is your first or second spot ever")
    else:
        got, ok, why = dig_artifact(location, x, y, d, locations, objects, xsi_type=xsi_type)
        drops += got
        sure = sure and ok
        notes += why
    return Spot(location, tile, kind, tuple(drops), sure, tuple(notes))


# --- from the save -----------------------------------------------------------------------------------------


def _tag(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _child(el, name: str):
    if el is None:
        return None
    return next((c for c in el if _tag(c).lower() == name.lower()), None)


def _kids(el) -> list:
    return list(el) if el is not None else []


def _text(el, name: str, default: str = "") -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None and c.text else default


def _num(el, name: str, default: float = 0) -> float:
    try:
        return float(_text(el, name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class _Raw:
    spots: tuple  # (location, xsi type, kind, tile)
    totems: int
    lost_books: int
    coconut: bool
    bridge: bool
    luck_raw: float
    luck_level: int
    notes_seen: frozenset
    held: dict  # "(O)79"/"(O)842" -> how many in the backpack
    hoes: tuple  # (archaeologist, generous) per hoe in the backpack
    orders: frozenset
    rules: frozenset


@lru_cache(maxsize=4)
def _raw(path: Path, _mtime: float) -> _Raw:
    root = ET.parse(path).getroot()  # noqa: S314 — the player's own local save
    player = _child(root, "player")
    spots, bridge = [], False
    for loc in _kids(_child(root, "locations")):
        name, xtype = _text(loc, "name"), loc.attrib.get(XSI + "type", "")
        if name == "IslandNorth":
            bridge = _text(loc, "bridgeFixed") == "true"
        for item in _kids(_child(loc, "objects")):
            k, v = _child(item, "key"), _child(item, "value")
            vec, obj = _child(k, "Vector2"), (_child(v, "Object") if v is not None else None)
            if vec is None or obj is None:
                continue
            oid = (_text(obj, "itemId") or _text(obj, "parentSheetIndex")).removeprefix("(O)")
            if oid in (ARTIFACT_SPOT, SEED_SPOT) and _text(obj, "bigCraftable") != "true":
                spots.append((name, xtype, "seed" if oid == SEED_SPOT else "artifact",
                              (int(_num(vec, "X")), int(_num(vec, "Y")))))
    held: dict[str, int] = {}
    hoes = []
    for it in _kids(_child(player, "items")):
        if it.attrib.get(XSI + "nil") == "true":
            continue
        if it.attrib.get(XSI + "type") == "Hoe":
            kinds = {e.attrib.get(XSI + "type", "") for e in _kids(_child(it, "enchantments"))}
            hoes.append(("ArchaeologistEnchantment" in kinds, "GenerousEnchantment" in kinds))
        oid = _text(it, "itemId")
        if oid in ("79", "842", "(O)79", "(O)842"):
            held[_qualify(oid)] = held.get(_qualify(oid), 0) + int(_num(it, "stack", 1))
    orders, rules = set(), set()
    for so in _kids(_child(root, "specialOrders")):
        if _text(so, "questState") == "InProgress":
            orders.add(_text(so, "questKey"))
            rules.update(r.strip() for r in _text(so, "specialRule").split(",") if r.strip())
    seen = frozenset(int(c.text) for c in _kids(_child(player, "secretNotesSeen")) if (c.text or "").strip().isdigit())
    return _Raw(tuple(spots), int(_num(root, "treasureTotemsUsed")), int(_num(root, "lostBooksFound")),
                _text(root, "goldenCoconutCracked") == "true", bridge, _num(root, "dailyLuck"),
                int(_num(player, "luckLevel")), seen, held, tuple(hoes), frozenset(orders), frozenset(rules))


def digger(save, data, raw: _Raw | None = None) -> Digger:
    """The dig's inputs from a save (read again from the file for what Save doesn't keep)."""
    raw = raw or _raw(Path(save.path), getattr(save, "mtime", 0.0))
    mail = frozenset(save.mail)
    luck = max(-0.20000000298023224, min(0.20000000298023224,
                                         raw.luck_raw + (_f32(0.025) if "HasSpecialCharm" in mail else 0.0)))
    notes = [int(k) for k in (data.asset("Data/SecretNotes") or {}) if str(k).lstrip("-").isdigit()]
    plain = {n for n in notes if n < JOURNAL_INDEX}
    journal = {n for n in notes if n >= JOURNAL_INDEX}
    hoes = set(raw.hoes) or {(False, False)}
    arch = {h[0] for h in hoes}
    gen = {h[1] for h in hoes}
    stats = save.stats
    return Digger(
        days_played=save.days_played, game_id=int(save.unique_id), season=save.season, day=save.day,
        legacy=save.legacy_random, luck=luck, totems=raw.totems, mail=mail, luck_level=raw.luck_level,
        mining_level=save.skills.get("mining", 0), farming_mastery=stats.get("mastery_0", 0) != 0,
        lost_books=raw.lost_books, coconut_cracked=raw.coconut, island_bridge=raw.bridge,
        orders=raw.orders, rules=raw.rules,
        notes_left=len(plain - raw.notes_seen) - raw.held.get("(O)79", 0),
        journal_left=len(journal - raw.notes_seen) - raw.held.get("(O)842", 0),
        archaeologist=arch.pop() if len(arch) == 1 else None, generous=gen.pop() if len(gen) == 1 else None,
        farm_key=FARM_KEYS.get(save.farm_type, "Standard"), dug=stats.get("ArtifactSpotsDug", 0),
        digs_today=max(1, len(raw.spots)), when=When.from_save(save))


def _named(drop: Drop, objects: dict, data) -> Drop:
    if drop.name or not drop.id:
        return drop
    obj = objects.get(drop.id.removeprefix("(O)")) if drop.id.startswith("(O)") else None
    name = (data.text(obj.get("DisplayName")) if obj and data is not None else None) or (obj or {}).get("Name")
    return replace(drop, name=name or drop.id)


def reachable(location: str, d: Digger, festivals: dict | None = None) -> bool | None:
    """Whether you can walk to the spot's place today. The game spawns spots on Ginger Island and in the Desert
    Festival's map long before (or after) you can go there."""
    has = d.mail.__contains__
    if location == "DesertFestival":
        fest = (festivals or {}).get("DesertFestival") or {}
        on = (str(fest.get("Season", "")).lower() == d.season
              and fest.get("StartDay", 0) <= d.day <= fest.get("EndDay", -1))
        return on and has("ccVault")
    if location == "Desert":
        return has("ccVault")
    if location == "Railroad":
        return d.days_played > 31
    if location.startswith("Island") or location in ("Caldera", "VolcanoDungeon"):
        if not has("willyBoatFixed"):
            return False
        if location in ("IslandSouth", "IslandSouthEast"):
            return True
        if location == "IslandWest":
            return has("Island_Turtle")
        if location == "IslandNorth":
            return has("Island_FirstParrot")
        return None
    return True


def spots(save, data) -> list[Spot]:
    """Every artifact spot and seed spot in the save, with what hoeing it today gives."""
    raw = _raw(Path(save.path), getattr(save, "mtime", 0.0))
    d = digger(save, data, raw)
    locations, objects = data.asset("Data/Locations"), data.asset("Data/Objects")
    festivals = data.asset("Data/PassiveFestivals") if data.has("Data/PassiveFestivals") else {}
    out = []
    for location, xtype, kind, tile in raw.spots:
        s = dig(location, tile, kind, d, locations, objects, xsi_type=xtype)
        out.append(replace(s, drops=tuple(_named(x, objects, data) for x in s.drops),
                           reachable=reachable(location, d, festivals)))
    return out

