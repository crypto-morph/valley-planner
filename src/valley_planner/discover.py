"""Find the player's own Stardew Valley install and save folder — Windows, macOS, Linux and WSL.

Nothing here is copied from the game: we only look where Steam and GOG put it,
and where the game writes its saves. Overrides: VALLEY_PLANNER_GAME (the install
folder) and VALLEY_PLANNER_SAVES (the Saves folder).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

GAME_DIR = "Stardew Valley"
GAMEDATA_DLL = "StardewValley.GameData.dll"
GAME_ENV, SAVES_ENV = "VALLEY_PLANNER_GAME", "VALLEY_PLANNER_SAVES"


@dataclass(frozen=True)
class GameInstall:
    root: Path  # the install folder
    content: Path  # its Content folder (holds Data/*.xnb)
    dll_dir: Path  # where StardewValley.GameData.dll lives (describes the data classes)


def is_wsl() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def wsl_path(win: str) -> Path:
    """'D:\\SteamLibrary' -> /mnt/d/SteamLibrary."""
    m = re.match(r"^([A-Za-z]):[\\/]*(.*)$", win)
    if not m:
        return Path(win)
    return Path("/mnt", m.group(1).lower(), *re.split(r"[\\/]+", m.group(2)) if m.group(2) else [])


def steam_libraries(steam_root: Path, to_local=lambda p: Path(p)) -> list[Path]:
    """The Steam root plus every library listed in its libraryfolders.vdf."""
    out = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for raw in re.findall(r'"path"\s+"([^"]+)"', text):
        lib = to_local(raw.replace("\\\\", "\\"))
        if lib not in out:
            out.append(lib)
    return out


def _registry(key: str, value: str, hive: str = "HKEY_CURRENT_USER") -> str | None:
    try:
        import winreg  # Windows only
    except ImportError:
        return None
    try:
        with winreg.OpenKey(getattr(winreg, hive), key) as k:
            return str(winreg.QueryValueEx(k, value)[0])
    except OSError:
        return None


def _steam_roots(home: Path, platform: str, wsl: bool) -> list[tuple[Path, object]]:
    """(Steam root, how to turn its library paths into local ones)."""
    roots: list[tuple[Path, object]] = []
    if platform == "win32":
        reg = _registry(r"Software\Valve\Steam", "SteamPath")
        for p in filter(None, [reg, r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]):
            roots.append((Path(p), Path))
    elif platform == "darwin":
        roots.append((home / "Library/Application Support/Steam", Path))
    else:
        for p in (".local/share/Steam", ".steam/steam", ".steam/root",
                  ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
            roots.append((home / p, Path))
        if wsl:
            for p in ("/mnt/c/Program Files (x86)/Steam", "/mnt/c/Program Files/Steam"):
                roots.append((Path(p), wsl_path))
    return roots


def _gog_dirs(platform: str, wsl: bool) -> list[Path]:
    if platform == "win32":
        reg = _registry(r"SOFTWARE\WOW6432Node\GOG.com\Games\1453375253", "path", "HKEY_LOCAL_MACHINE")
        return [Path(p) for p in filter(None, [reg, r"C:\Program Files (x86)\GOG Galaxy\Games\Stardew Valley",
                                                r"C:\GOG Games\Stardew Valley"])]
    if platform == "darwin":
        return [Path("/Applications/Stardew Valley.app")]
    if wsl:
        return [Path("/mnt/c/Program Files (x86)/GOG Galaxy/Games/Stardew Valley"),
                Path("/mnt/c/GOG Games/Stardew Valley")]
    return [Path.home() / "GOG Games/Stardew Valley"]


def as_install(root: Path) -> GameInstall | None:
    """`root` if it holds the game's content and data classes (Windows/Linux layout, or a macOS bundle)."""
    for content, dlls in (
        (root / "Content", root),
        (root / "Contents/Resources/Content", root / "Contents/MacOS"),
        (root / "Contents/Resources/Content", root / "Contents/Resources"),
    ):
        if (content / "Data" / "Crops.xnb").is_file() and (dlls / GAMEDATA_DLL).is_file():
            return GameInstall(root, content, dlls)
    return None


def find_game(env: dict | None = None, home: Path | None = None, platform: str | None = None,
              wsl: bool | None = None) -> GameInstall | None:
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    platform = sys.platform if platform is None else platform
    wsl = is_wsl() if wsl is None else wsl
    if env.get(GAME_ENV):
        return as_install(Path(env[GAME_ENV]))
    for steam, to_local in _steam_roots(home, platform, wsl):
        for lib in steam_libraries(steam, to_local):
            found = as_install(lib / "steamapps" / "common" / GAME_DIR)
            if found:
                return found
    for d in _gog_dirs(platform, wsl):
        found = as_install(d)
        if found:
            return found
    return None


def save_roots(env: dict | None = None, home: Path | None = None, platform: str | None = None,
               wsl: bool | None = None) -> list[Path]:
    """Where saves may be, best first. The first that exists wins (see find_saves_root)."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    platform = sys.platform if platform is None else platform
    wsl = is_wsl() if wsl is None else wsl
    out: list[Path] = []
    for key in (SAVES_ENV, "STARDEW_SAVES"):
        if env.get(key):
            out.append(Path(env[key]))
    if platform == "win32":
        out.append(Path(env.get("APPDATA") or home / "AppData/Roaming") / "StardewValley" / "Saves")
    else:
        out.append(Path(env.get("XDG_CONFIG_HOME") or home / ".config") / "StardewValley" / "Saves")
        if wsl:  # every Windows user's saves, most recently played first
            users = sorted(Path("/mnt/c/Users").glob("*/AppData/Roaming/StardewValley/Saves"),
                           key=_newest_save_time, reverse=True)
            out.extend(users)
    return out


def _newest_save_time(saves: Path) -> float:
    try:
        return max((p.stat().st_mtime for p in saves.iterdir() if p.is_dir()), default=0.0)
    except OSError:
        return 0.0


def find_saves_root(**kw) -> Path | None:
    return next((p for p in save_roots(**kw) if p.is_dir()), None)


def list_saves(root: Path) -> list[Path]:
    """Save files (Saves/<Farm>_<id>/<Farm>_<id>), most recently played first."""
    saves = [d / d.name for d in root.iterdir() if d.is_dir() and (d / d.name).is_file()]
    return sorted(saves, key=lambda p: p.stat().st_mtime, reverse=True)
