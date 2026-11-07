"""Pictures of the game's places, drawn in the browser from the player's own installed game files.

Nothing here is kept in the planner: textures are decoded from the game's Content folder when asked for (then cached
as PNG beside the decoded data, under the user's cache folder) and served only to the local page.

- `Textures.png(asset)`: a Texture2D asset ("Maps/spring_outdoorsTileSheet") as PNG. Only files inside Content.
- `map_draw(data, location, season)`: a map's tile sheets and layers, ready to draw (see static/map.js).

Maps, in our words (GameLocation.updateSeasonalTileSheets, SortLayers):
- Outdoor maps (the "Outdoors" map property; not the Desert) swap every tile sheet image whose file name starts
  "spring_", "summer_", "fall_" or "winter_" for the current season's. A map's "SeasonOverride" property fixes
  its season.
- Layers draw in four groups: Back, Buildings (both under people and things), Front, AlwaysFront (over them). A
  group holds its layer and any named with a number after it (Back2…), lowest number first. Paths is never drawn.
- A sheet's image is named relative to the map's own folder (so "spring_town" is Maps/spring_town).
"""

from __future__ import annotations

import posixpath
import re
import threading
from functools import lru_cache
from pathlib import Path

from .xnb.reader import XnbReader, _Stream
from .xnb.tbin import read_tbin
from .xnb.texture import encode_png, read_texture

SEASONS = ("spring", "summer", "fall", "winter")
GROUPS = ("Back", "Buildings", "Front", "AlwaysFront")
ASSET = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ .'/-]*$")
LOCATION = re.compile(r"^[A-Za-z0-9_]+$")
FARM_MAPS = {0: "Farm", 1: "Farm_Fishing", 2: "Farm_Foraging", 3: "Farm_Mining", 4: "Farm_Combat",
             5: "Farm_FourCorners", 6: "Farm_Island", 7: "Farm_Ranching"}


class NotAllowed(ValueError):
    """An asked-for asset that isn't a plain path inside the game's Content folder."""


def clean_asset(asset: str) -> str:
    """'Maps\\spring_town' -> 'Maps/spring_town'; refuses anything that could leave the Content folder."""
    name = asset.replace("\\", "/").strip()
    if name.endswith(".png"):
        name = name[:-4]
    parts = name.split("/")
    if not ASSET.match(name) or any(p in ("", ".", "..") for p in parts):
        raise NotAllowed(f"not a content asset: {asset!r}")
    return name


class Textures:
    """Texture2D assets as PNG, decoded once per file version."""

    def __init__(self, content: Path, cache: Path | None = None):
        self.content = Path(content)
        self.cache = cache
        self._root = self.content.resolve()
        self._memory: dict[str, tuple[float, int, int, bytes]] = {}
        self._listings: dict[Path, dict[str, str]] = {}
        self._found: dict[str, tuple[Path, float]] = {}
        self._lock = threading.Lock()

    def path(self, asset: str) -> Path:
        return self._info(clean_asset(asset))[0]

    def _info(self, name: str) -> tuple[Path, float]:
        """(file, modified time), remembered: the game's files don't change while it runs, and looking is slow on a
        Windows drive from WSL."""
        hit = self._found.get(name)
        if hit is None:
            p = self._find(name)
            hit = self._found[name] = (p, p.stat().st_mtime)
        return hit

    def _find(self, name: str) -> Path:
        p = (self.content / f"{name}.xnb").resolve()
        if not p.is_relative_to(self._root):
            raise NotAllowed(f"not a content asset: {name!r}")
        if not p.is_file():
            p = self._any_case(name)
        return p

    def _any_case(self, name: str) -> Path:
        """The data sometimes names a file in another case ("TileSheets\\Crops"); Windows doesn't mind, others do."""
        here = self.content
        parts = f"{name}.xnb".split("/")
        for part in parts:
            if (here / part).exists():
                here = here / part
                continue
            with self._lock:
                listing = self._listings.get(here)
                if listing is None:
                    listing = self._listings[here] = {c.name.lower(): c.name for c in here.iterdir()} \
                        if here.is_dir() else {}
            found = listing.get(part.lower())
            if found is None:
                raise FileNotFoundError(name)
            here = here / found
        if not here.is_file():
            raise FileNotFoundError(name)
        return here

    def stamp(self, asset: str) -> int:
        """The file's modified time, for cache-busting URLs."""
        return int(self._info(clean_asset(asset))[1])

    def get(self, asset: str) -> tuple[int, int, bytes]:
        """(width, height, PNG bytes)."""
        name = clean_asset(asset)
        p, mtime = self._info(name)
        with self._lock:
            hit = self._memory.get(name)
            if hit and hit[0] == mtime:
                return hit[1:]
        disk = self.cache / "pictures" / f"{name}.png" if self.cache else None
        if disk and disk.is_file() and disk.stat().st_mtime >= mtime:
            png = disk.read_bytes()
            w, h = int.from_bytes(png[16:20], "big"), int.from_bytes(png[20:24], "big")
        else:
            w, h, px = read_texture(p.read_bytes())
            png = encode_png(w, h, px)
            if disk:
                disk.parent.mkdir(parents=True, exist_ok=True)
                tmp = disk.with_name(f"{disk.name}.{threading.get_ident()}.tmp")
                tmp.write_bytes(png)
                tmp.replace(disk)
        with self._lock:
            self._memory[name] = (mtime, w, h, png)
        return w, h, png

    def png(self, asset: str) -> bytes:
        return self.get(asset)[2]

    def size(self, asset: str) -> tuple[int, int]:
        w, h, _ = self.get(asset)
        return w, h

    def url(self, asset: str) -> str:
        name = clean_asset(asset)
        return f"/api/tex/{name}.png?v={self.stamp(name)}"


def map_asset(location: str, farm_type: int = 0) -> str:
    if not LOCATION.match(location):
        raise NotAllowed(f"not a location: {location!r}")
    return f"Maps/{FARM_MAPS.get(farm_type, 'Farm')}" if location == "Farm" else f"Maps/{location}"


def seasonal_name(image: str, season: str) -> str:
    """GameLocation.GetSeasonalTilesheetName: 'spring_town' in fall -> 'fall_town'."""
    folder, file = posixpath.split(image)
    if file.startswith(tuple(f"{s}_" for s in SEASONS)):
        file = season + file[file.index("_"):]
    return posixpath.join(folder, file) if folder else file


def layer_order(ids) -> list[tuple[str, str]]:
    """[(layer id, group)] in the order the game draws them; layers outside the four groups are left out."""
    out = []
    for group in GROUPS:
        found = []
        for lid in ids:
            if lid.startswith(group):
                rest = lid[len(group):]
                if rest == "" or re.fullmatch(r"-?\d+", rest):
                    found.append((int(rest or 0), lid))
        out += [(lid, group) for _n, lid in sorted(found)]
    return out


def _tbin_bytes(path: Path) -> bytes:
    s = _Stream(XnbReader(None).payload(path.read_bytes()))
    for _ in range(s.int7()):
        s.string()
        s.take(4)
    s.int7()  # shared resources
    s.int7()  # the map's reader index
    return s.take(s.unpack("<i", 4))


@lru_cache(maxsize=16)
def _read_map(path: Path, _mtime: float):
    return read_tbin(_tbin_bytes(path), tiles=True)


def _map(textures: Textures, asset: str):
    path = textures.path(asset)
    return _read_map(path, textures.stamp(asset))


def map_facts(textures: Textures, asset: str, season: str = "spring") -> tuple[str, bool, set[tuple[int, int]]]:
    """(the map's season, whether it's outdoors, the tiles with something on its Front layer)."""
    m = _map(textures, asset)
    season = str(m.properties.get("SeasonOverride") or season).lower()
    front = m.layers.get("Front")
    tiles = {(i % front.width, i // front.width) for i, v in enumerate(front.tiles or []) if v >= 0} if front else set()
    return (season if season in SEASONS else "spring"), "Outdoors" in m.properties, tiles


def map_draw(textures: Textures, asset: str, season: str = "spring") -> dict:
    """What static/map.js needs to draw a map: its size, sheets (with the season's images) and layers in order."""
    m = _map(textures, asset)
    season, outdoors, _front = map_facts(textures, asset, season)
    seasonal = outdoors and not asset.endswith("/Desert")
    folder = posixpath.dirname(asset)
    sheets = []
    for sh in m.sheets:
        image = seasonal_name(sh.image, season) if seasonal else sh.image
        tex = None
        for candidate in (posixpath.normpath(posixpath.join(folder, image)), image,
                          posixpath.normpath(posixpath.join(folder, sh.image))):
            try:
                textures.path(candidate)
            except (FileNotFoundError, NotAllowed):
                continue
            tex = candidate
            break
        sheets.append({"id": sh.id, "tex": tex, "url": None, "columns": sh.columns,
                       "tile": [sh.tile_width, sh.tile_height]})
    back = m.layers.get("Back") or next(iter(m.layers.values()))
    layers = [{"id": lid, "group": group, "tiles": m.layers[lid].tiles}
              for lid, group in layer_order(m.layers) if m.layers[lid].width == back.width]
    used = {v >> 16 for layer in layers for v in set(layer["tiles"] or ()) if v >= 0}
    for i in used:  # only the sheets something is drawn from get a picture (Paths' never does)
        if i < len(sheets) and sheets[i]["tex"]:
            sheets[i]["url"] = textures.url(sheets[i]["tex"])
    return {"map": asset, "width": back.width, "height": back.height, "tile": 16, "season": season,
            "sheets": sheets, "layers": layers}


def item_icon(textures: Textures, data, qid: str) -> dict | None:
    """Where an item's own picture sits in the game's sheets, for a CSS sprite: {url, x, y, w, h, sw, sh}
    (sheet width and height). Objects are 16x16, big craftables 16x32. None if it can't be found."""
    kind, _, item = qid.partition(")")
    kind, item = kind.lstrip("("), item or qid
    if kind not in ("O", "BC"):
        return None
    table, tex, h = (("Data/Objects", "Maps/springobjects", 16) if kind == "O"
                     else ("Data/BigCraftables", "TileSheets/Craftables", 32))
    entry = data.asset(table).get(item)
    if not entry:
        return None
    tex = str(entry.get("Texture") or tex).replace("\\", "/")
    try:
        sw, sh = textures.size(tex)
        url = textures.url(tex)
    except (FileNotFoundError, ValueError, NotAllowed):
        return None
    index = int(entry.get("SpriteIndex") or 0)
    cols = max(1, sw // 16)
    return {"url": url, "x": index % cols * 16, "y": index // cols * h, "w": 16, "h": h, "sw": sw, "sh": sh}


_SHARED: dict[tuple, Textures] = {}


def shared(content: Path, cache: Path | None) -> Textures:
    """One Textures per game install, so the page's pictures and the views' icons share a memory cache."""
    key = (str(content), str(cache))
    if key not in _SHARED:
        _SHARED[key] = Textures(content, cache)
    return _SHARED[key]
