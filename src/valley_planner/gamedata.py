"""The game's own data, read from the player's install and cached per game version.

`GameData(install).asset("Data/Crops")` decodes Content/Data/Crops.xnb once,
then serves it from the cache (JSON under the user's cache folder, one folder
per game version, so an update refreshes everything). Names in the data are
often "[LocalizedText Strings\\Objects:Parsnip_Name]"; `text()` resolves them
from the game's own string files.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from functools import cached_property
from pathlib import Path

from .discover import GAMEDATA_DLL, GameInstall
from .xnb.reader import XnbReader
from .xnb.schema import Schema

GAME_DLL = "Stardew Valley.dll"
LOCALIZED = re.compile(r"^\[LocalizedText (?P<file>[^:\]]+):(?P<key>[^\]\s]+)(?P<args>[^\]]*)\]$")


def cache_root(env: dict | None = None, platform: str | None = None) -> Path:
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if env.get("VALLEY_PLANNER_CACHE"):
        return Path(env["VALLEY_PLANNER_CACHE"])
    if platform == "win32":
        return Path(env.get("LOCALAPPDATA") or Path.home() / "AppData/Local") / "ValleyPlanner" / "cache"
    if platform == "darwin":
        return Path.home() / "Library/Caches/ValleyPlanner"
    return Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "valley-planner"


def game_version(install: GameInstall) -> str:
    """The game's file version, e.g. '1.6.15.24356', from its own executable assembly."""
    import dnfile

    dll = install.dll_dir / GAME_DLL
    try:
        info = dnfile.dnPE(str(dll), fast_load=True)
        info.parse_data_directories(directories=[2])  # resources
        fixed = info.VS_FIXEDFILEINFO[0]
        ms, ls = fixed.FileVersionMS, fixed.FileVersionLS
        return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:  # noqa: BLE001 — fall back to the file's size and date
        st = (install.dll_dir / GAMEDATA_DLL).stat()
        return f"unknown-{st.st_size}-{int(st.st_mtime)}"


class GameData:
    def __init__(self, install: GameInstall, cache: Path | None = None):
        self.install = install
        self.version = game_version(install)
        self.cache = (cache or cache_root()) / self.version
        self._memory: dict[str, object] = {}
        self._lock = threading.Lock()

    @cached_property
    def _reader(self) -> XnbReader:
        return XnbReader(Schema([self.install.dll_dir / GAMEDATA_DLL]))

    def asset(self, name: str):
        """A content asset by its game path without extension, e.g. 'Data/Crops' or 'Strings/Objects'."""
        key = name.replace("\\", "/")
        with self._lock:
            if key in self._memory:
                return self._memory[key]
            cached = self.cache / f"{key}.json"
            if cached.is_file():
                value = json.loads(cached.read_text(encoding="utf-8"))
            else:
                value = self._reader.read(self.install.content / f"{key}.xnb")
                cached.parent.mkdir(parents=True, exist_ok=True)
                tmp = cached.with_suffix(".tmp")
                tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                tmp.replace(cached)
            self._memory[key] = value
            return value

    def has(self, name: str) -> bool:
        return (self.install.content / f"{name}.xnb").is_file()

    def assets_in(self, folder: str) -> list[str]:
        """Asset names in a content folder, e.g. 'Characters/schedules'."""
        base = self.install.content / folder
        return sorted(f"{folder}/{p.stem}" for p in base.glob("*.xnb")) if base.is_dir() else []

    def text(self, value: str | None) -> str | None:
        """Resolve '[LocalizedText Strings\\Objects:Parsnip_Name]' to the English text; other strings pass through."""
        if not value:
            return value
        m = LOCALIZED.match(value.strip())
        if not m:
            return value
        strings = self.asset(m.group("file").replace("\\", "/"))
        return strings.get(m.group("key"), value) if isinstance(strings, dict) else value
