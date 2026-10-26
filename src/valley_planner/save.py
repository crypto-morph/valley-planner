"""Read a Stardew Valley save (1.6) into plain data. Never writes.

Fields are read from their exact place in the save (the SaveGame root, the
host <player>, or a named location), not from the first matching tag
anywhere. Where the save only stores an id, the game's own data fills in the
rest (`GameData`, optional): whether a crop regrows, which fruit a tree
grows, which placed objects are machines, names shared by two items.

See rules/registry.json, area "Save file", for what each field means and
what it was checked against.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

XSI = "{http://www.w3.org/2001/XMLSchema-instance}"
SEASONS = ("spring", "summer", "fall", "winter")
CC_ROOMS = ("Pantry", "Crafts Room", "Fish Tank", "Boiler Room", "Vault", "Bulletin Board")  # areasComplete order
CC_ROOM_MAIL = {"Pantry": "ccPantry", "Crafts Room": "ccCraftsRoom", "Fish Tank": "ccFishTank",
                "Boiler Room": "ccBoilerRoom", "Vault": "ccVault", "Bulletin Board": "ccBulletin"}
OBJECT_TYPES = ("Object", "ColoredObject")  # preserves and coloured flowers are ColoredObject in 1.6
QUALITY = {0: "normal", 1: "silver", 2: "gold", 4: "iridium"}


# --- small XML helpers ------------------------------------------------------------


def _tag(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _type(el: ET.Element) -> str:
    return el.attrib.get(XSI + "type", "")


def _nil(el: ET.Element | None) -> bool:
    return el is None or el.attrib.get(XSI + "nil") == "true"


def _child(el: ET.Element | None, name: str) -> ET.Element | None:
    if el is None:
        return None
    return next((c for c in el if _tag(c) == name), None)


def _text(el: ET.Element | None, name: str, default: str = "") -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None and c.text else default


def _int(el: ET.Element | None, name: str, default: int = 0) -> int:
    raw = _text(el, name)
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(el: ET.Element | None, name: str) -> bool:
    return _text(el, name).lower() == "true"


def _strings(el: ET.Element | None) -> list[str]:
    """<x><string>a</string>…</x> or <x><int>…</int>…</x> -> values."""
    return [(c.text or "").strip() for c in (el if el is not None else []) if c.text and c.text.strip()]


def _dict(el: ET.Element | None):
    """XML-serialized dictionary: <item><key>…</key><value>…</value></item> -> (key element, value element)."""
    for item in el if el is not None else []:
        k, v = _child(item, "key"), _child(item, "value")
        if k is not None and v is not None:
            yield k, v


def _flat(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


# --- data -------------------------------------------------------------------------


@dataclass
class Item:
    id: str  # unqualified id, e.g. "342"; "" for tools and the like
    name: str
    stack: int
    quality: int  # 0 normal, 1 silver, 2 gold, 4 iridium
    where: str  # "Backpack", "Farm chest", "FarmHouse fridge", …
    price: int | None = None  # the item's own base price (preserves depend on what went in)
    category: int | None = None
    type: str = ""  # "Basic", "Arch", "Minerals", "Fish", …
    big: bool = False  # big craftable (machines, chests…)
    preserve: str = ""  # Wine / Jelly / Pickle / Juice / … for artisan goods
    preserved_id: str = ""  # what went in
    spawned: bool = False  # found as forage (the Tiller bonus skips foraged fruit)
    uses: int = 0  # tackle wear

    @property
    def qualified_id(self) -> str:
        return f"({'BC' if self.big else 'O'}){self.id}" if self.id else ""


@dataclass
class Crop:
    harvest_id: str
    seed_id: str
    location: str
    tile: tuple[int, int] | None
    days_left: int  # until harvestable; 0 = ready
    grown: int | None  # days of growth so far (None once fully grown) — to spot a missed watering
    ready: bool
    dead: bool
    watered: bool
    fertilizer: str  # qualified id, "" if none
    regrows: bool | None  # from Data/Crops RegrowDays; None without game data
    forage: bool  # Spring Onion / Ginger patches: harvestable forage, not a planted crop
    in_pot: bool


@dataclass
class Friend:
    points: int
    gifts_this_week: int
    gifts_today: int
    talked_today: bool
    status: str  # Friendly, Dating, Engaged, Married, Divorced
    roommate: bool

    @property
    def hearts(self) -> int:
        return self.points // 250


@dataclass
class Save:
    path: Path
    mtime: float
    game_version: str
    farmer: str
    farm: str
    season: str
    day: int
    year: int
    days_played: int
    money: int
    total_earned: int
    unique_id: str  # seeds the game's random numbers (forecasts)
    legacy_random: bool
    weather: str  # sun, rain, storm, snow, wind, green rain
    weather_tomorrow: str
    daily_luck: float
    items: list[Item] = field(default_factory=list)
    crops: list[Crop] = field(default_factory=list)
    mail: set[str] = field(default_factory=set)  # received
    mailbox: set[str] = field(default_factory=set)  # arrived, not read yet
    mail_tomorrow: set[str] = field(default_factory=set)  # arrives tomorrow morning
    world_state: set[str] = field(default_factory=set)
    events_seen: set[str] = field(default_factory=set)
    stats: dict[str, int] = field(default_factory=dict)  # the named stats (books read, etc.)
    flags: set[str] = field(default_factory=set)  # world facts kept on locations, e.g. "beachBridgeFixed"
    skills: dict[str, int] = field(default_factory=dict)
    professions: list[int] = field(default_factory=list)
    max_stamina: int = 270
    max_items: int = 12
    house_upgrade: int = 0
    deepest_mine_level: int = 0
    mine_lowest: int = 0  # lowest Mines level anyone reached (shop conditions use this)
    cave_choice: int = 0  # 0 not chosen yet, 1 fruit bats, 2 mushrooms
    axe_level: int = 0
    rod_level: int = -1  # -1 no rod; 0 Bamboo, 1 Training, 2 Fiberglass, 3 Iridium, 4 Advanced Iridium
    friends: dict[str, Friend] = field(default_factory=dict)
    spouse: str | None = None
    cooking_recipes: set[str] = field(default_factory=set)
    crafting_recipes: set[str] = field(default_factory=set)
    fish_caught: dict[str, int] = field(default_factory=dict)  # unqualified id -> count
    museum: set[str] = field(default_factory=set)  # donated item ids
    bundle_data: dict[str, str] = field(default_factory=dict)  # "Pantry/0" -> definition
    bundle_slots: dict[int, list[bool]] = field(default_factory=dict)
    areas_complete: list[bool] = field(default_factory=list)
    buildings: Counter = field(default_factory=Counter)  # built, including ones under construction
    animals: list[dict] = field(default_factory=list)
    hay: int = 0
    fruit_trees: list[dict] = field(default_factory=list)
    machines: Counter = field(default_factory=Counter)  # placed, by name (things Data/Machines lists)
    sprinklers: Counter = field(default_factory=Counter)
    crab_pots: int = 0
    quests: list[dict] = field(default_factory=list)
    special_orders: list[dict] = field(default_factory=list)  # accepted
    special_orders_board: list[dict] = field(default_factory=list)  # Lewis's board this week
    qi_orders_board: list[dict] = field(default_factory=list)
    cart_guarantee: int = -1  # Traveling Cart visits until the Year-1 Red Cabbage Seeds (-1 off/used)
    shipped: dict[str, int] = field(default_factory=dict)  # basicShipped: id -> count
    profit_margin: float = 1.0  # the farm's profit-margin setting (player difficultyModifier)
    farm_type: int = 0  # whichFarm: 0 Standard, 1 Riverland, 2 Forest, 3 Hilltop, 4 Wilderness, 5 Four Corners, 6 Beach

    # --- questions everything else asks --------------------------------------------

    def has_mail(self, *keys: str, unread_ok: bool = True) -> bool:
        """Received, or (by default) sitting unread in the mailbox."""
        return any(k in self.mail or (unread_ok and k in self.mailbox) for k in keys)

    @property
    def wet(self) -> bool:
        """Rain-type weather (rain, storm, green rain): outdoor crops are watered, rain fish bite."""
        return self.weather in ("rain", "storm", "green rain")

    def room_complete(self, room: str) -> bool:
        """Either route: the CC sets areasComplete, the CC and Joja both send cc<Room> mail."""
        i = CC_ROOMS.index(room)
        return bool(i < len(self.areas_complete) and self.areas_complete[i]) or self.has_mail(
            CC_ROOM_MAIL[room], unread_ok=False)

    def totals(self) -> dict[str, int]:
        out: dict[str, int] = defaultdict(int)
        for it in self.items:
            out[it.name] += it.stack
        return dict(out)

    def count(self, item_id: str, min_quality: int = 0) -> int:
        return sum(it.stack for it in self.items if it.id == item_id and not it.big and it.quality >= min_quality)


# --- reading ------------------------------------------------------------------------


def _location_name(el: ET.Element, parents: dict) -> str:
    cur = parents.get(el)
    while cur is not None:
        if _tag(cur) in ("GameLocation", "indoors"):
            name = _text(cur, "name") or _text(cur, "uniqueName")
            if name:
                return name
        cur = parents.get(cur)
    return "?"


def _item(el: ET.Element, where: str, names: dict[str, str]) -> Item | None:
    if _nil(el) or not len(el):
        return None
    xtype = _type(el)
    name = _text(el, "name") or _text(el, "Name")
    if not name:
        return None
    is_object = xtype in OBJECT_TYPES or (not xtype and _child(el, "itemId") is not None)
    big = _bool(el, "bigCraftable")
    raw_id = (_text(el, "itemId") or _text(el, "parentSheetIndex")) if (is_object or big) else ""
    item_id = raw_id.removeprefix("(O)").removeprefix("(BC)")
    if item_id in names and not big and not _text(el, "preserve"):
        name = names[item_id]  # two items share this name (white/brown eggs…)
    price = _int(el, "price", -1) if is_object else -1
    category = _text(el, "category")
    return Item(
        id=item_id, name=name, stack=max(1, _int(el, "stack", 1)), quality=_int(el, "quality"), where=where,
        price=price if price >= 0 else None, category=int(category) if category.lstrip("-").isdigit() else None,
        type=_text(el, "type"), big=big, preserve=_text(el, "preserve"),
        preserved_id=_text(el, "preservedParentSheetIndex").removeprefix("(O)"),
        spawned=_bool(el, "isSpawnedObject"), uses=_int(el, "uses"),
    )


def _containers(root: ET.Element, player: ET.Element, parents: dict):
    """(label, <items> element) for everywhere the player keeps things."""
    yield "Backpack", _child(player, "items")
    for loc_items in (el for el in root.iter() if _tag(el) == "fridge"):  # FarmHouse / IslandFarmHouse / Cabin
        yield f"{_location_name(loc_items, parents)} fridge", _child(loc_items, "items")
    for el in root.iter():
        if _tag(el) == "Object" and _type(el) == "Chest":
            yield f"{_location_name(el, parents)} chest", _child(el, "items")
        elif _tag(el) == "heldObject" and _type(el) == "Chest":  # auto-grabbers
            yield f"{_location_name(el, parents)} auto-grabber", _child(el, "items")
    for _k, v in _dict(_child(root, "globalInventories")):  # Junimo chests share one inventory
        yield "Junimo chest", _child(v, "ArrayOfItem") or v


def _weather(root: ET.Element) -> tuple[str, str, bool]:
    """Today's and tomorrow's weather where the farm is (locationWeather 'Default')."""
    names = {"Sun": "sun", "Rain": "rain", "Storm": "storm", "Snow": "snow", "Wind": "wind",
             "GreenRain": "green rain", "Festival": "sun", "Wedding": "sun"}
    for k, v in _dict(_child(root, "locationWeather")):
        if _flat(k) != "Default":
            continue
        lw = _child(v, "LocationWeather") or v
        today = _flat(_child(lw, "weather")) if _child(lw, "weather") is not None else ""
        tomorrow = _flat(_child(lw, "weatherForTomorrow")) if _child(lw, "weatherForTomorrow") is not None else ""
        green = _flat(_child(lw, "isGreenRain")) == "true" if _child(lw, "isGreenRain") is not None else False
        today = "GreenRain" if green else today
        return names.get(today, today.lower() or "sun"), names.get(tomorrow, tomorrow.lower()), True
    # Older saves: root flags only
    if _bool(root, "isSnowing"):
        today = "snow"
    elif _bool(root, "isLightning"):
        today = "storm"
    elif _bool(root, "isRaining"):
        today = "rain"
    else:
        today = "wind" if _bool(root, "isDebrisWeather") else "sun"
    legacy = {"0": "sun", "1": "rain", "2": "wind", "3": "storm", "4": "sun", "5": "snow", "6": "sun"}  # 1.5 codes
    raw = _text(root, "weatherForTomorrow")
    return today, legacy.get(raw, raw.lower()), False


def _tool_level(player: ET.Element, xtype: str, root: ET.Element) -> int:
    """Highest upgradeLevel among owned tools of this type; one at Clint's counts as the tier it left at."""
    level = -1
    for el in root.iter():
        if _type(el) == xtype and _tag(el) in ("Item", "Tool") and not _nil(el):
            level = max(level, _int(el, "upgradeLevel"))
    upgrading = _child(player, "toolBeingUpgraded")
    if not _nil(upgrading) and _type(upgrading) == xtype:
        level = max(level, _int(upgrading, "upgradeLevel") - 1)
    return level


def _regrow_days(crop: ET.Element, seed: str, harvest: str, forage: bool, crops_data: dict) -> int | None:
    """Days between harvests (0 = single harvest). 1.6 saves leave it to Data/Crops (by seed); older
    saves recorded it on the crop (regrowAfterHarvest, -1 = never). Wild-seed crops have no entry: single."""
    if forage:
        return 0
    if seed and seed in crops_data:
        return crops_data[seed].get("RegrowDays", 0)
    old = _text(crop, "regrowAfterHarvest")
    if old.lstrip("-").isdigit():
        return max(0, int(old))
    if not crops_data:
        return None
    matches = [c.get("RegrowDays", 0) for c in crops_data.values() if c.get("HarvestItemId") == harvest]
    return matches[0] if matches else 0


def _order(so: ET.Element) -> dict:
    money = 0
    objectives = []
    for c in so:
        if _tag(c) == "objectives":
            objectives.append({"type": _type(c), "text": _text(c, "description"),
                               "current": _int(c, "currentCount"), "max": _int(c, "maxCount")})
        elif _tag(c) == "rewards" and _type(c).endswith("MoneyReward"):
            amount = _child(c, "amount")
            mult = _child(c, "multiplier")
            base = int(_flat(amount) or 0) if amount is not None else 0
            factor = float(_flat(mult) or 1) if mult is not None else 1.0
            money += int(base * factor)
    return {"key": _text(so, "questKey"), "requester": _text(so, "requester"), "name": _text(so, "questName"),
            "type": _text(so, "orderType"), "state": _text(so, "questState"), "due_date": _int(so, "dueDate"),
            "objectives": objectives, "money": money}


def read_save(path: Path, data=None) -> Save:
    """`data`: a GameData for the derived fields (regrowing crops, tree fruit, machines, shared names)."""
    path = Path(path)
    root = ET.parse(path).getroot()  # noqa: S314 — the player's own local save
    player = _child(root, "player")
    parents = {c: p for p in root.iter() for c in p}
    locations = {_text(loc, "name"): loc for loc in _child(root, "locations") or []}

    objects = data.asset("Data/Objects") if data else {}
    crops_data = data.asset("Data/Crops") if data else {}
    machines_data = data.asset("Data/Machines") if data else {}
    trees_data = data.asset("Data/FruitTrees") if data else {}
    big_names = {f"(BC){k}": v.get("Name") for k, v in (data.asset("Data/BigCraftables") if data else {}).items()}

    # Items that share a name (176/180 "Egg", 174/182 "Large Egg"…): tell the later ones apart by id
    shared: dict[str, str] = {}
    by_name: dict[str, list[str]] = defaultdict(list)
    for oid, o in objects.items():
        by_name[o.get("Name", "")].append(oid)
    for name, ids in by_name.items():
        if len(ids) > 1 and name:
            for oid in sorted(ids, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else 0, x))[1:]:
                shared[oid] = f"{name} ({oid})"
    shared.update({"180": "Egg (Brown)", "182": "Large Egg (Brown)"})  # the game's own wording for these two

    items = []
    for where, container in _containers(root, player, parents):
        for el in container if container is not None else []:
            it = _item(el, where, shared)
            if it:
                items.append(it)

    weather, tomorrow, _ = _weather(root)
    stats = _child(player, "stats")
    days_played = _int(stats, "daysPlayed")
    if not days_played:
        for k, v in _dict(_child(stats, "Values")):
            if _flat(k) == "daysPlayed":
                days_played = int(_flat(v) or 0)
    luck = float(_text(root, "dailyLuck", "0") or 0)
    stat_values = {_flat(k): int(_flat(v) or 0) for k, v in _dict(_child(stats, "Values"))
                   if (_flat(v) or "0").lstrip("-").isdigit()}

    mail = set(_strings(_child(player, "mailReceived")))
    friends = {}
    for k, v in _dict(_child(player, "friendshipData")):
        fr = _child(v, "Friendship") or v
        friends[_flat(k)] = Friend(_int(fr, "Points"), _int(fr, "GiftsThisWeek"), _int(fr, "GiftsToday"),
                                   _bool(fr, "TalkedToToday"), _text(fr, "Status", "Friendly"),
                                   _bool(fr, "RoommateMarriage"))

    fish = {}
    for k, v in _dict(_child(player, "fishCaught")):
        ints = [int(c.text) for c in v.iter() if _tag(c) == "int" and c.text and c.text.lstrip("-").isdigit()]
        fish[_flat(k).removeprefix("(O)")] = ints[0] if ints else 1

    museum = set()
    if (lib := locations.get("ArchaeologyHouse")) is not None:
        for _k, v in _dict(_child(lib, "museumPieces")):
            museum.add(_flat(v).removeprefix("(O)"))

    cc = locations.get("CommunityCenter")
    bundle_slots = {}
    for k, v in _dict(_child(cc, "bundles")):
        try:
            bundle_slots[int(_flat(k))] = [c.text == "true" for c in v.iter() if _tag(c) == "boolean"]
        except ValueError:
            continue
    areas = [c.text == "true" for c in (_child(cc, "areasComplete") or [])]
    bundle_data = {_flat(k): _flat(v) for k, v in _dict(_child(root, "bundleData"))}

    farm = locations.get("Farm")
    flags = {"beachBridgeFixed"} if _bool(locations.get("Beach"), "bridgeFixed") else set()
    buildings: Counter = Counter()
    animals = []
    for b in (_child(farm, "buildings") or []):
        btype = _text(b, "buildingType")
        if not btype:
            continue
        upgrading = _text(b, "upgradeName") if _int(b, "daysUntilUpgrade") > 0 else ""
        buildings[upgrading or btype] += 1  # Robin finishes construction and upgrades on her own
    seen_animals = set()
    for el in root.iter():  # each animal is stored twice (its building's list and its home's), once by id
        if _tag(el) == "FarmAnimal" and _text(el, "myID") not in seen_animals:
            seen_animals.add(_text(el, "myID"))
            animals.append({"id": _text(el, "myID"), "type": _text(el, "type"), "name": _text(el, "name"),
                            "friendship": _int(el, "friendshipTowardFarmer"), "happiness": _int(el, "happiness"),
                            "fullness": _int(el, "fullness"), "age": _int(el, "age"),
                            "days_owned": _int(el, "daysOwned"), "days_since_lay": _int(el, "daysSinceLastLay"),
                            "produce_quality": _int(el, "produceQuality"), "produce": _text(el, "currentProduce"),
                            "was_pet": _bool(el, "wasPet"), "cracker": _bool(el, "hasEatenAnimalCracker"),
                            "home": _text(el, "buildingTypeILiveIn")})

    fruit_trees = []
    for el in root.iter():
        if _type(el) != "FruitTree":
            continue
        tree = trees_data.get(_text(el, "treeId"), {})
        fruit_ids = [f.get("ItemId", "").removeprefix("(O)") for f in tree.get("Fruit") or [] if f.get("ItemId")]
        if not fruit_ids and _text(el, "indexOfFruit"):  # 1.5 saves name the fruit directly
            fruit_ids = [_text(el, "indexOfFruit")]
        fruit_trees.append({"sapling_id": _text(el, "treeId"), "location": _location_name(el, parents),
                            "fruit_ids": fruit_ids,
                            "fruit": [objects.get(f, {}).get("Name", f) for f in fruit_ids],
                            "days_left": max(0, _int(el, "daysUntilMature")),
                            "seasons": [s.lower() for s in tree.get("Seasons") or []]})

    house_upgrade = _int(player, "houseUpgradeLevel")
    machines: Counter = Counter()
    sprinklers: Counter = Counter()
    crab_pots = 0
    for el in root.iter():
        if _tag(el) != "Object" or _nil(el):
            continue
        if _type(el) == "CrabPot":
            crab_pots += 1
            continue
        qid = _text(el, "itemId") or _text(el, "parentSheetIndex")  # 1.5 saves have no itemId
        if _bool(el, "bigCraftable"):
            where = _location_name(el, parents)
            if where.startswith("Cellar") and not (where == "Cellar" and house_upgrade >= 3):
                continue  # the game pre-places casks in every cellar; yours opens with the third house upgrade
            qid = qid if qid.startswith("(") else f"(BC){qid}"
            if qid in machines_data:
                machines[big_names.get(qid) or _text(el, "name")] += 1
        elif _text(el, "name").endswith("Sprinkler"):
            sprinklers[_text(el, "name")] += 1

    crops = []
    for el in root.iter():
        if _tag(el) != "crop" or _nil(el) or not len(el):
            continue
        dirt = parents.get(el)
        if dirt is None or (_type(dirt) != "HoeDirt" and _tag(dirt) != "hoeDirt"):
            continue
        phases = [int(c.text) for c in (_child(el, "phaseDays") or []) if c.text and c.text.lstrip("-").isdigit()]
        cur, day_in = _int(el, "currentPhase"), _int(el, "dayOfCurrentPhase")
        full, dead = _bool(el, "fullGrown"), _bool(el, "dead")
        if phases and cur < len(phases) - 1:  # the last phase is the "grown" marker
            days_left = max(0, phases[cur] - day_in) + sum(phases[cur + 1:len(phases) - 1])
            grown = sum(phases[:cur]) + day_in
        else:  # fully grown; a regrowing crop counts dayOfCurrentPhase down to its next harvest
            days_left, grown = (max(0, day_in) if full else 0), None
        seed = _text(el, "seedIndex").removeprefix("(O)")
        forage = _bool(el, "forageCrop")
        harvest = _text(el, "indexOfHarvest").removeprefix("(O)")
        regrow = _regrow_days(el, seed, harvest, forage, crops_data)
        tile_el = _child(dirt, "Tile")
        tile = (int(float(_text(tile_el, "X") or 0)), int(float(_text(tile_el, "Y") or 0))) if tile_el is not None \
            else None
        in_pot = _tag(dirt) == "hoeDirt"
        crops.append(Crop(
            harvest_id=harvest, seed_id=seed,
            location=_location_name(dirt, parents), tile=tile, days_left=days_left, grown=grown,
            ready=days_left == 0 and not dead, dead=dead, watered=_int(dirt, "state") == 1,
            fertilizer=_text(dirt, "fertilizer"), regrows=None if regrow is None else regrow > 0,
            forage=forage, in_pot=in_pot))

    quests = []
    for q in _child(player, "questLog") or []:
        quests.append({"id": _text(q, "id"), "type": _type(q) or "Quest", "title": _text(q, "questTitle"),
                       "completed": _bool(q, "completed"), "daily": _bool(q, "dailyQuest"),
                       "days_left": _int(q, "daysLeft"), "target": _text(q, "target"),
                       "item_id": (_text(q, "ItemId") or _text(q, "item")).removeprefix("(O)"),
                       "count": _int(q, "number", 1), "reward": max(_int(q, "moneyReward"), _int(q, "reward"))})

    board = [_order(o) for o in _child(root, "availableSpecialOrders") or [] if _tag(o) == "SpecialOrder"]

    skills = {s: _int(player, f"{s}Level") for s in ("farming", "fishing", "foraging", "mining", "combat")}
    spouse = _text(player, "spouse") or None
    if spouse and friends.get(spouse) and friends[spouse].status == "Engaged":
        spouse = None  # engaged, not married yet

    return Save(
        path=path, mtime=path.stat().st_mtime, game_version=_text(root, "gameVersion"),
        farmer=_text(player, "name", "Farmer"), farm=_text(player, "farmName"),
        season=(_text(root, "currentSeason", "spring") or "spring").lower(),
        day=_int(root, "dayOfMonth", 1), year=_int(root, "year", 1), days_played=days_played,
        money=_int(player, "money"), total_earned=_int(player, "totalMoneyEarned"),
        unique_id=_text(root, "uniqueIDForThisGame"), legacy_random=_bool(root, "useLegacyRandom"),
        weather=weather, weather_tomorrow=tomorrow,
        daily_luck=max(-0.2, min(0.2, luck + (0.025 if "HasSpecialCharm" in mail else 0))),
        items=items, crops=crops, mail=mail, mailbox=set(_strings(_child(player, "mailbox"))),
        mail_tomorrow=set(_strings(_child(player, "mailForTomorrow"))),
        mine_lowest=_int(root, "mine_lowestLevelReached"),
        world_state=set(_strings(_child(root, "worldStateIDs"))),
        events_seen=set(_strings(_child(player, "eventsSeen"))), stats=stat_values, flags=flags,
        skills=skills, professions=[int(x) for x in _strings(_child(player, "professions")) if x.isdigit()],
        max_stamina=_int(player, "maxStamina", 270), max_items=_int(player, "maxItems", 12),
        house_upgrade=house_upgrade, deepest_mine_level=_int(player, "deepestMineLevel"),
        cave_choice=_int(player, "caveChoice"),
        axe_level=max(0, _tool_level(player, "Axe", root)), rod_level=_tool_level(player, "FishingRod", root),
        friends=friends, spouse=spouse,
        cooking_recipes={_flat(k) for k, _v in _dict(_child(player, "cookingRecipes"))},
        crafting_recipes={_flat(k) for k, _v in _dict(_child(player, "craftingRecipes"))},
        fish_caught=fish, museum=museum, bundle_data=bundle_data, bundle_slots=bundle_slots, areas_complete=areas,
        buildings=buildings, animals=animals, hay=_int(farm, "piecesOfHay"), fruit_trees=fruit_trees,
        machines=machines, sprinklers=sprinklers, crab_pots=crab_pots, quests=quests,
        special_orders=[_order(o) for o in _child(root, "specialOrders") or [] if _tag(o) == "SpecialOrder"],
        special_orders_board=[o for o in board if o["type"] != "QiChallenge"],
        qi_orders_board=[o for o in board if o["type"] == "QiChallenge"],
        cart_guarantee=_int(root, "visitsUntilY1Guarantee", -1),
        shipped={_flat(k).removeprefix("(O)"): int(_flat(v) or 0) for k, v in _dict(_child(player, "basicShipped"))},
        profit_margin=float(_text(player, "difficultyModifier", "1") or 1),
        farm_type=_int(root, "whichFarm"),
    )


def rusty_key(save: Save) -> bool:
    """1.6 keeps the Rusty Key as a mail flag (older saves had a player field, migrated on load)."""
    return save.has_mail("HasRustyKey", unread_ok=False)
