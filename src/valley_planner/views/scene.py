"""What stands on a map today, from the save: hoed dirt, crops, trees, grass, bushes, big rocks and logs, objects,
machines and buildings — as sprites for static/map.js to draw over the map's tiles (1.6.15 draw rules).

A sprite is {"tex": asset, "src": [x, y, w, h], "x", "y", "z"}, plus "flip" (mirror it) and "tint" ([r, g, b]:
multiply its colours) when needed. x, y is its top-left in map pixels (16 to a tile, the game's own art scale);
z orders them: lower first. Hoed dirt and things lying flat get z below 0, so they sit under everything.

In our words (the game's draw code, positions converted from its 64-pixel tiles to 16):
- Hoed dirt (HoeDirt.DrawOptimized): TerrainFeatures/hoeDirt (Mountain: hoeDirtDark; outdoors in winter:
  hoeDirtSnow), a 16x16 piece picked by which sides have dirt next door (north 1, east 2, south 4, west 8, through
  the game's draw guide), and when watered a second piece 64 pixels right, picked by which watered dirt is next door.
- Crops (Crop.getSourceRect, updateDrawMath): 16x32 from the crop's texture (TileSheets/crops unless the crop says);
  the row's top is (row / 2) * 32, with 128 added across for odd rows; the column is phase + 1 (a seed, phase 0,
  shows column 0 on tiles where x * 7 + y * 11 is even), or 6 when fully grown and ready, 7 while regrowing; dead
  crops are column 12 + (x * 7 + y * 11) % 4 of row 384. Fiber's row moves down one in fall and two in winter. The
  sprite's foot is the tile's bottom; until the last phase it's nudged by (x * 11 + y * 7) % 10 - 5 game pixels
  across and (y * 11 + x * 7) % 10 - 5 down (not down for raised crops, not at all for paddy or raised ones). A
  freshly watered seed is tinted (180, 100, 200). Flower colours: a second 16x32 from the column after, tinted.
- Objects (Object.draw): 16x16 from Maps/springobjects (or the item's own texture) at the tile; sprite index i is
  at ((i % columns) * 16, (i / columns) * 16). Big craftables are 16x32 from TileSheets/Craftables, foot on the
  tile, the next index when showing their "on" frame.
- Fences (Fence.draw): 16x32 from the fence's texture, the piece picked from the neighbours of the same fence.
- Trees (Tree.draw): a seed, sprout or sapling from the tree's seasonal texture; grown, a 48x96 top whose trunk is
  on the tile and a 16x32 stump under it. Fruit trees (FruitTree.draw): 48x80 by stage, grown a 48x64 top for the
  season and a 48x32 stump. Grass (Grass.draw): up to four 15x20 tufts, placed with the game's own seeded numbers.
  Bushes (Bush.setUpSourceRect): by size and season from TileSheets/bushes, foot on the tile's bottom.
- Big rocks, stumps and logs (ResourceClump.draw): w x h tiles of Maps/springobjects from their sprite index; giant
  crops (GiantCrop.draw) from their texture, one tile taller than they stand.
- Buildings (Building.draw, getSourceRect): the building's texture (or skin), its SourceRect (the whole texture when
  empty), moved down a whole rect per farmhouse upgrade (up to 2), across/down per season by its SeasonOffset, and
  up one rect for a greenhouse not yet repaired; drawn with its bottom-left at the bottom-left of its footprint plus
  DrawOffset; then its draw layers (mailbox, animal doors…) at DrawPosition from the sprite's top-left.
Not drawn yet: animals, people, furniture, fertilizer, fruit on trees, machines' held items, chest colours, the
shipping bin's lid, shadows, flooring paths, a building under construction (drawn finished).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from ..facts.night_events import XSI, _child, _first, _items, _kids, _num, _tag, _text, _vec
from ..facts.rng import NetRandom, random_seed

SEASONS = ("spring", "summer", "fall", "winter")
DIRT_GUIDE = {0: 0, 8: 15, 2: 13, 1: 12, 4: 4, 9: 11, 3: 9, 5: 8, 6: 1, 12: 3, 10: 14, 7: 5, 15: 6, 13: 7, 11: 10,
              14: 2}
NEIGHBOURS = ((0, -1, 1), (1, 0, 2), (0, 1, 4), (-1, 0, 8))  # north, east, south, west
FENCE_GUIDE = {0: 5, 10: 9, 100: 10, 1000: 3, 500: 5, 1010: 8, 1100: 6, 1500: 3, 600: 0, 510: 2, 110: 7, 1600: 0,
               1610: 4, 1510: 2, 1110: 7, 610: 4}
SEED_TINT = [180, 100, 200]
FIBER = "771"


def crop_source(row: int, phase: int, *, phase_to_show: int = -1, full_grown: bool = False, day_of_phase: int = 0,
                dead: bool = False, number: int = 0, harvest: str = "", season: str = "spring") -> list[int]:
    """Crop.getSourceRect: the 16x32 piece of the crop sheet for this crop; `number` is x * 7 + y * 11."""
    if dead:
        return [192 + number % 4 * 16, 384, 16, 32]
    if harvest == FIBER:
        row += {"fall": 1, "winter": 2}.get(season, 0)
    if full_grown:
        column = 6 if day_of_phase <= 0 else 7
    else:
        shown = phase_to_show if phase_to_show != -1 else phase
        column = shown + (-1 if shown == 0 and number % 2 == 0 else 0) + 1
    return [min(240, column * 16 + (128 if row % 2 else 0)), row // 2 * 32, 16, 32]


def standard_rect(index: int, texture_width: int, w: int = 16, h: int = 16) -> list[int]:
    """Game1.getSourceRectForStandardTileSheet."""
    columns = max(1, texture_width // w)
    return [index % columns * w, index // columns * h, w, h]


def _bool(el, name: str) -> bool:
    return _text(el, name).lower() == "true"


def _float(el, name: str) -> float:
    try:
        return float(_text(el, name, "0"))
    except ValueError:
        return 0.0


def _location(root, name: str):
    for loc in _kids(_child(root, "locations")):
        if _text(loc, "name") == name:
            return loc
    return None


class Scene:
    def __init__(self, data, textures, location: str, season: str, *, outdoors: bool = True, game_id: int = 0,
                 days_played: int = 0, house_upgrade: int = 0, greenhouse_fixed: bool = True, raining: bool = False):
        self.data, self.tex, self.location = data, textures, location
        self.season = season if season in SEASONS else "spring"
        self.season_index = SEASONS.index(self.season)
        self.outdoors = outdoors
        self.raining = raining and outdoors  # rain waters every outdoor tile, though the save doesn't say so
        self.game_id, self.days_played = game_id, days_played
        self.house_upgrade, self.greenhouse_fixed = house_upgrade, greenhouse_fixed
        self.sprites: list[dict] = []

    def add(self, tex: str | None, src, x: float, y: float, z: float, *, flip: bool = False, tint=None) -> None:
        if not tex:
            return
        s = {"tex": tex.replace("\\", "/"), "src": [int(v) for v in src], "x": round(x, 2), "y": round(y, 2),
             "z": round(z, 3)}
        if flip:
            s["flip"] = True
        if tint:
            s["tint"] = list(tint)
        self.sprites.append(s)

    def width(self, tex: str) -> int:
        try:
            return self.tex.size(tex.replace("\\", "/"))[0]
        except (FileNotFoundError, ValueError):
            return 0

    # --- terrain features ----------------------------------------------------------------------

    def dirt(self, dirt: dict[tuple[int, int], object]) -> None:
        tex = "TerrainFeatures/hoeDirtDark" if self.location == "Mountain" else "TerrainFeatures/hoeDirt"
        if self.season == "winter" and self.outdoors:
            tex = "TerrainFeatures/hoeDirtSnow"
        watered = set(dirt) if self.raining else {t for t, el in dirt.items() if _num(el, "state") == 1}
        for (x, y), _el in dirt.items():
            near = sum(bit for dx, dy, bit in NEIGHBOURS if (x + dx, y + dy) in dirt)
            pos = DIRT_GUIDE[near]
            self.add(tex, [pos % 4 * 16, pos // 4 * 16, 16, 16], x * 16, y * 16, -2)
            if (x, y) in watered:
                wet = DIRT_GUIDE[sum(bit for dx, dy, bit in NEIGHBOURS if (x + dx, y + dy) in watered)]
                self.add(tex, [wet % 4 * 16 + 64, wet // 4 * 16, 16, 16], x * 16, y * 16, -1.9)

    def crop(self, x: int, y: int, crop, watered: bool) -> None:
        if crop is None or crop.attrib.get(XSI + "nil") == "true" or not list(crop):
            return
        number = x * 7 + y * 11
        if _bool(crop, "forageCrop"):
            which = _num(crop, "whichForageCrop") or 1
            wx, wy = (x * 11 + y * 7) % 10 - 5, (y * 11 + x * 7) % 10 - 5
            self.add("LooseSprites/Cursors", [(x * 51 + y * 77) % 3 * 16, 128 + which * 16, 16, 16],
                     x * 16 + wx / 4, y * 16 + wy / 4, y * 16 + 8 + wy / 4)
            return
        phases = len(_kids(_child(crop, "phaseDays")))
        phase = _num(crop, "currentPhase")
        row = _num(crop, "rowInSpriteSheet")
        raised = _bool(crop, "raisedSeeds")
        seed = _text(crop, "seedIndex")
        paddy = bool((self.data.asset("Data/Crops").get(seed) or {}).get("IsPaddyCrop"))
        dark = not paddy and not raised  # shouldDrawDarkWhenWatered
        last = phase >= phases - 1
        wx = 0 if (not dark or last) else (x * 11 + y * 7) % 10 - 5
        wy = 0 if (raised or last) else (y * 11 + x * 7) % 10 - 5
        dead = _bool(crop, "dead")
        src = crop_source(row, phase, phase_to_show=int(_text(crop, "phaseToShow", "-1") or -1),
                          full_grown=_bool(crop, "fullGrown"), day_of_phase=_num(crop, "dayOfCurrentPhase"),
                          dead=dead, number=number, harvest=_text(crop, "indexOfHarvest"), season=self.season)
        tex = _text(crop, "overrideTexturePath") or "TileSheets/crops"
        left, top, z = x * 16 + wx / 4, y * 16 - 16 + wy / 4, y * 16 + 8 + wy / 4
        flip = _bool(crop, "flip")
        tint = SEED_TINT if watered and phase == 0 and dark else None
        self.add(tex, src, left, top, z, flip=flip, tint=tint)
        colour = _child(crop, "tintColor")
        rgba = [_num(colour, k) for k in ("R", "G", "B", "A")] if colour is not None else [255] * 4
        if rgba[3] > 0 and rgba[:3] != [255, 255, 255] and last and not dead:
            column = (6 if _num(crop, "dayOfCurrentPhase") <= 0 else 7) if _bool(crop, "fullGrown") else phase + 2
            self.add(tex, [column * 16 + (128 if row % 2 else 0), row // 2 * 32, 16, 32], left, top, z + 0.01,
                     flip=flip, tint=rgba[:3])

    def tree(self, x: int, y: int, el) -> None:
        data = self.data.asset("Data/WildTrees").get(_text(el, "treeType"))
        if not data or not data.get("Textures"):
            return
        tex = next((t["Texture"] for t in data["Textures"]
                    if (t.get("Season") or "").lower() in ("", self.season) and not t.get("Condition")),
                   data["Textures"][0]["Texture"])
        stage, flip = _num(el, "growthStage"), _bool(el, "flipped")
        bottom = y * 16 + 16
        if stage < 5:
            src = {0: [32, 128, 16, 16], 1: [0, 128, 16, 16], 2: [16, 128, 16, 16]}.get(stage, [0, 96, 16, 32])
            self.add(tex, src, x * 16, bottom - src[3], bottom if stage else -1, flip=flip)
            return
        moss = _bool(el, "hasMoss")
        if not _bool(el, "stump"):
            alt = (data.get("UseAlternateSpriteWhenSeedReady") and _bool(el, "hasSeed")) or \
                (data.get("UseAlternateSpriteWhenNotShaken") and not _bool(el, "wasShakenToday"))
            self.add(tex, [96 if moss else 48 if alt else 0, 0, 48, 96], x * 16 - 16, y * 16 - 80, bottom + 0.2,
                     flip=flip)
        self.add(tex, [32 + (96 if moss else 0), 96, 16, 32], x * 16, y * 16 - 16, bottom, flip=flip)

    def fruit_tree(self, x: int, y: int, el) -> None:
        data = self.data.asset("Data/FruitTrees").get(_text(el, "treeId"))
        if not data:
            return
        tex, row = data.get("Texture") or "TileSheets/fruitTrees", data.get("TextureSpriteRow") or 0
        stage, flip, bottom = _num(el, "growthStage"), _bool(el, "flipped"), y * 16 + 16
        if stage < 4:
            v = max(-8.0, min(64.0, math.sin(x * 200 / (math.pi * 2)) * -16)) / 2
            self.add(tex, [min(stage, 3) * 48, row * 80, 48, 80], x * 16 - 16 + v / 4, y * 16 - 68 + v / 4, bottom,
                     flip=flip)
            return
        if not _bool(el, "stump"):
            self.add(tex, [(12 + self.season_index * 3) * 16, row * 80, 48, 64], x * 16 - 16, y * 16 - 64,
                     bottom + 0.2, flip=flip)
        self.add(tex, [384, row * 80 + 48, 48, 32], x * 16 - 16, y * 16 - 16, bottom - 0.1, flip=flip)

    def grass(self, x: int, y: int, el, front: bool) -> None:
        kind = _num(el, "grassType")
        offset = {1: (0, 20, 40, 80 if self.outdoors else 0)[self.season_index], 2: 60, 3: 80, 4: 100,
                  7: (160, 180, 200, 220 if self.outdoors else 160)[self.season_index]}.get(kind, (kind + 1) * 20)
        rng = NetRandom(random_seed(self.game_id, self.days_played / 28.0, x * 7.0, y * 11.0))
        picks = []
        for _ in range(4):  # Grass.setUpRandom
            weed, o1, o2, o3, o4 = rng.next(3), rng.next(-2, 3), rng.next(-2, 3), rng.next(-2, 3), rng.next(-2, 3)
            if front:
                o2, o4 = o2 - 7, o4 - 7
            flip = rng.next_double() < 0.5
            rng.next_double()  # shake
            picks.append((weed, o1, o2, o3, o4, flip))
        for i in range(min(4, _num(el, "numberOfWeeds"))):
            weed, _o1, _o2, o3, o4, flip = picks[i]
            left, top = x * 16 + i % 2 * 8 + o3 - 1, y * 16 + i // 2 * 8 + o4 - 7.5
            self.add("TerrainFeatures/grass", [weed * 15, offset, 15, 20], left, top, top + 17.5 - 1 + 0.001 * left,
                     flip=flip)

    def bush(self, el) -> None:
        t = _vec(_child(el, "tilePosition"))
        if t is None:
            return
        x, y = t
        size, town, extra = _num(el, "size"), _bool(el, "townBush"), _num(el, "tileSheetOffset")
        s = self.season_index
        if size == 0:
            src = [s * 32 + extra * 16, 224, 16, 32]
        elif size == 1:
            if town:
                src = [s * 32, 96, 32, 32]
            else:
                n, w = s * 64 + extra * 32, self.width("TileSheets/bushes") or 1
                src = [n % w, n // w * 48, 32, 48]
        elif size == 2:
            if town and s < 2:
                src = [48, 176, 48, 48]
            else:
                src = [[0, 128], [0, 128], [48, 128], [0, 176]][s] + [48, 48]
        else:
            return  # tea bushes and walnut bushes: not yet
        self.add("TileSheets/bushes", src, x * 16, y * 16 + 16 - src[3], y * 16 + 20, flip=_bool(el, "flipped"))

    def clump(self, el) -> None:
        t = _vec(_child(el, "tile"))
        if t is None:
            return
        x, y = t
        w, h = max(1, _num(el, "width")), max(1, _num(el, "height"))
        if el.attrib.get(XSI + "type") == "GiantCrop":
            data = self.data.asset("Data/GiantCrops").get(_text(el, "id"))
            if data:
                size = data.get("TileSize") or {"X": 3, "Y": 3}
                pos = data.get("TexturePosition") or {"X": 0, "Y": 0}
                self.add(data["Texture"], [pos["X"], pos["Y"], 16 * size["X"], 16 * (size["Y"] + 1)], x * 16,
                         y * 16 - 16, (y + size["Y"]) * 16)
            return
        tex = _text(el, "textureName") or "Maps/springobjects"
        src = standard_rect(_num(el, "parentSheetIndex"), self.width(tex))
        self.add(tex, [src[0], src[1], w * 16, h * 16], x * 16, y * 16, (y + 1) * 16 + x / 1000)

    # --- objects and buildings ----------------------------------------------------------------

    def objects(self, placed: dict[tuple[int, int], object]) -> None:
        fences = {t: _text(o, "itemId") for t, o in placed.items() if o.attrib.get(XSI + "type") == "Fence"}
        for (x, y), o in placed.items():
            item = _text(o, "itemId") or _text(o, "parentSheetIndex")
            kind = o.attrib.get(XSI + "type", "")
            if kind == "Fence":
                data = self.data.asset("Data/Fences").get(item)
                if not data or _bool(o, "isGate"):
                    continue
                total = sum(v for (dx, dy, v) in ((1, 0, 100), (-1, 0, 10), (0, 1, 500), (0, -1, 1000))
                            if fences.get((x + dx, y + dy)) == item)
                piece = FENCE_GUIDE.get(total, 5)
                tex = data["Texture"]
                self.add(tex, standard_rect(piece, self.width(tex), 16, 32), x * 16, y * 16 - 16, y * 16 + 8)
            elif _bool(o, "bigCraftable") and self.chest(x, y, o, item):
                continue
            elif _bool(o, "bigCraftable"):
                data = self.data.asset("Data/BigCraftables").get(item)
                if not data:
                    continue
                tex = data.get("Texture") or "TileSheets/Craftables"
                index = int(data.get("SpriteIndex") or 0) + (1 if _bool(o, "showNextIndex") else 0)
                self.add(tex, standard_rect(index, self.width(tex), 16, 32), x * 16, y * 16 - 16,
                         (y + 1) * 16 - 6 + x / 1000)
            else:
                data = self.data.asset("Data/Objects").get(item)
                if not data:
                    continue
                tex = data.get("Texture") or "Maps/springobjects"
                self.add(tex, standard_rect(int(data.get("SpriteIndex") or 0), self.width(tex)), x * 16, y * 16,
                         y * 16 + 8 + x / 1000, flip=_bool(o, "flipped"))

    def chest(self, x: int, y: int, o, item: str) -> bool:
        """Chest.draw for a Chest or Big Chest painted a colour: a tinted body and lid, a plain trim strip and lid
        shine. False when it's not one (an unpainted chest draws like any big craftable)."""
        frames = {"130": (168, 46, 38), "BigChest": (312, 16, 8)}.get(item)
        colour = _child(o, "playerChoiceColor")
        rgb = [_num(colour, k) for k in ("R", "G", "B")] if colour is not None else [0, 0, 0]
        if frames is None or rgb == [0, 0, 0]:
            return False
        tex = "TileSheets/Craftables"
        body, shine, lid = frames
        closed = int(_text(o, "startingLidFrame") or 0) or int(self.data.asset("Data/BigCraftables")[item]
                                                               .get("SpriteIndex") or 0) + 1
        w, z = self.width(tex), (y + 1) * 16 - 6 + x / 1000
        self.add(tex, standard_rect(body, w, 16, 32), x * 16, y * 16 - 16, z, tint=rgb)
        self.add(tex, [0, body // 8 * 32 + 53, 16, 11], x * 16, y * 16 + 5, z + 0.002)
        self.add(tex, standard_rect(closed + shine, w, 16, 32), x * 16, y * 16 - 16, z + 0.002)
        self.add(tex, standard_rect(closed + lid, w, 16, 32), x * 16, y * 16 - 16, z + 0.001, tint=rgb)
        return True

    def building(self, b) -> None:
        kind = _text(b, "buildingType")
        data = self.data.asset("Data/Buildings").get(kind)
        if not data:
            return
        tex = data.get("Texture")
        skin = _text(b, "skinId")
        for s in data.get("Skins") or []:
            if s.get("Id") == skin and s.get("Texture"):
                tex = s["Texture"]
        if not tex:
            return
        r = data.get("SourceRect") or {}
        src = [r.get("X", 0), r.get("Y", 0), r.get("Width", 0), r.get("Height", 0)]
        if not src[2] or not src[3]:
            try:
                w, h = self.tex.size(tex.replace("\\", "/"))
            except (FileNotFoundError, ValueError):
                return
            src = [0, 0, w, h]
        else:
            if kind == "Farmhouse":
                src[1] += src[3] * min(self.house_upgrade, 2)
            off = data.get("SeasonOffset") or {}
            src[0] += off.get("X", 0) * self.season_index
            src[1] += off.get("Y", 0) * self.season_index
            if kind == "Greenhouse" and not self.greenhouse_fixed:
                src[1] -= src[3]
        tx, ty, th = _num(b, "tileX"), _num(b, "tileY"), _num(b, "tilesHigh")
        ox, oy = (float(v) for v in str(data.get("DrawOffset") or "0, 0").split(","))
        left, top = tx * 16 + ox, (ty + th) * 16 + oy - src[3]
        base = (ty + th) * 16
        z = base - float(data.get("SortTileOffset") or 0) * 16
        self.add(tex, src, left, top, z)
        door = _float(b, "animalDoorOpenAmount")
        for layer in data.get("DrawLayers") or []:
            if layer.get("OnlyDrawIfChestHasContents"):
                continue
            lr = layer.get("SourceRect") or {}
            lsrc = [lr.get("X", 0), lr.get("Y", 0), lr.get("Width", 0), lr.get("Height", 0)]
            off = data.get("SeasonOffset") or {}
            lsrc[0] += off.get("X", 0) * self.season_index
            lsrc[1] += off.get("Y", 0) * self.season_index
            px, py = (float(v) for v in str(layer.get("DrawPosition") or "0, 0").split(","))
            adoor = layer.get("AnimalDoorOffset") or {}
            px, py = px + adoor.get("X", 0) * door, py + adoor.get("Y", 0) * door
            lz = -1.5 if layer.get("DrawInBackground") else base - float(layer.get("SortTileOffset") or 0) * 16 + 0.25
            self.add(layer.get("Texture") or tex, lsrc, left + px, top + py, lz)

    # --- a whole location -----------------------------------------------------------------------

    def read(self, loc, front: set[tuple[int, int]] = frozenset()) -> list[dict]:
        dirt: dict[tuple[int, int], object] = {}
        for k, v in _items(_child(loc, "terrainFeatures")):
            t, f = _vec(k), _first(v)
            if t is None:
                continue
            kind = f.attrib.get(XSI + "type", "") or _tag(f)
            if kind == "HoeDirt":
                dirt[t] = f
                self.crop(t[0], t[1], _child(f, "crop"), _num(f, "state") == 1)
            elif kind == "Tree":
                self.tree(*t, f)
            elif kind == "FruitTree":
                self.fruit_tree(*t, f)
            elif kind == "Grass":
                self.grass(*t, f, t in front)
        self.dirt(dirt)
        for f in _kids(_child(loc, "largeTerrainFeatures")):
            if f.attrib.get(XSI + "type") == "Bush":
                self.bush(f)
        for c in _kids(_child(loc, "resourceClumps")):
            self.clump(c)
        placed = {}
        for k, v in _items(_child(loc, "objects")):
            if (t := _vec(k)) is not None:
                placed[t] = _first(v)
        self.objects(placed)
        for b in _kids(_child(loc, "buildings")):
            if not _bool(b, "isMoving"):
                self.building(b)
        self.sprites.sort(key=lambda s: s["z"])
        return self.sprites


@lru_cache(maxsize=8)
def _root(path: Path, _mtime: float):
    return ET.parse(path).getroot()  # noqa: S314 — the player's own local save


def scene(farm, textures, location: str, season: str | None = None, *, outdoors: bool = True,
          front: set[tuple[int, int]] = frozenset()) -> dict:
    """{"sprites": [...], "textures": {asset: url}} for one location in the save (empty if it isn't there).
    Remembered until the save changes."""
    s = farm.save
    key = (str(s.path), s.mtime, location, season, outdoors, id(textures))
    if key in _MEMO:
        return _MEMO[key]
    if len(_MEMO) > 16:
        _MEMO.clear()
    _MEMO[key] = out = _scene(farm, textures, location, season, outdoors=outdoors, front=front)
    return out


_MEMO: dict[tuple, dict] = {}


def _scene(farm, textures, location: str, season: str | None, *, outdoors: bool, front: set[tuple[int, int]]) -> dict:
    s = farm.save
    root = _root(Path(s.path), s.mtime)
    loc = _location(root, location)
    try:
        game_id = int(s.unique_id)
    except (TypeError, ValueError):
        game_id = 0
    farm_loc = _location(root, "Farm")
    sc = Scene(farm.data, textures, location, (season or s.season).lower(), outdoors=outdoors, game_id=game_id,
               days_played=s.days_played, house_upgrade=s.house_upgrade,
               raining=bool(s.wet) and location != "Greenhouse" and not location.startswith("Island"),
               greenhouse_fixed=_bool(farm_loc, "greenhouseUnlocked") if farm_loc is not None else False)
    sprites = sc.read(loc, front) if loc is not None else []
    urls = {}
    for sp in sprites:
        if sp["tex"] not in urls:
            try:
                urls[sp["tex"]] = textures.url(sp["tex"])
            except (FileNotFoundError, ValueError):
                urls[sp["tex"]] = None
    return {"location": location, "season": sc.season, "raining": sc.raining,
            "sprites": [sp for sp in sprites if urls[sp["tex"]]],
            "textures": {k: v for k, v in urls.items() if v}}
