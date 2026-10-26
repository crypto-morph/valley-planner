"""The planner's web app: a small local server for one player's own save.

It reads the newest save by default (or the one you pick) and re-reads it
when the game writes a new one. Nothing leaves your computer.
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .discover import find_game, find_saves_root, list_saves
from .engine import cc, todo
from .gamedata import GameData
from .views import ask, calendar, cart, crops, morning, sell
from .views.farm import Farm

STATIC = Path(__file__).parent / "static"


class Planner:
    """The game data, the chosen save, and the Farm read from it (cached until the file changes)."""

    def __init__(self, data: GameData | None = None, saves_root: Path | None = None):
        game = find_game() if data is None else None
        if data is None and game is None:
            raise RuntimeError("Stardew Valley wasn't found; set VALLEY_PLANNER_GAME to its folder")
        self.data = data or GameData(game)
        self.saves_root = saves_root or find_saves_root()
        self.chosen: str | None = None
        self._farm: tuple[tuple, Farm] | None = None
        self._lock = threading.Lock()

    def saves(self) -> list[Path]:
        return list_saves(self.saves_root) if self.saves_root else []

    def path(self) -> Path | None:
        saves = self.saves()
        if self.chosen:
            return next((p for p in saves if p.name == self.chosen), None)
        return saves[0] if saves else None

    def farm(self) -> Farm:
        path = self.path()
        if path is None:
            raise HTTPException(404, "No save found; set VALLEY_PLANNER_SAVES to your Saves folder")
        stamp = (str(path), path.stat().st_mtime)
        with self._lock:
            if self._farm is None or self._farm[0] != stamp:
                self._farm = (stamp, Farm.load(self.data, path))
            return self._farm[1]


def create_app(planner: Planner | None = None) -> FastAPI:
    app = FastAPI(title="Valley Planner")
    state: dict = {"planner": planner}

    def p() -> Planner:
        if state["planner"] is None:
            state["planner"] = Planner()
        return state["planner"]

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/meta")
    def meta() -> dict:
        pl = p()
        path = pl.path()
        f = pl.farm() if path else None
        return {"game_version": pl.data.version, "saves_root": str(pl.saves_root or ""),
                "save": path.name if path else None, "following_newest": pl.chosen is None,
                "farm": f.save.farm if f else None, "player": f.save.farmer if f else None,
                "date": f.label(f.save.days_played) if f else None}

    @app.get("/api/saves")
    def saves() -> dict:
        pl = p()
        return {"chosen": pl.chosen, "saves": [s.name for s in pl.saves()]}

    @app.put("/api/saves/chosen")
    def choose(name: str | None = None) -> dict:
        pl = p()
        if name and name not in {s.name for s in pl.saves()}:
            raise HTTPException(404, f"No save named {name}")
        pl.chosen = name or None
        return saves()

    @app.get("/api/crops")
    def crops_view() -> dict:
        f = p().farm()
        return {"countdown": crops.countdown(f), "mine": crops.mine(f)}

    @app.get("/api/calendar")
    def calendar_view(days: int = 28) -> dict:
        return calendar.days(p().farm(), max(1, min(days, 112)))

    @app.get("/api/hours")
    def hours_view(ahead: int = 0) -> dict:
        return calendar.shop_hours(p().farm(), max(0, min(ahead, 27)))

    @app.get("/api/cart")
    def cart_view(days: int = 14) -> dict:
        return cart.upcoming(p().farm(), max(1, min(days, 56)))

    @app.get("/api/cart/search")
    def cart_search(q: str = "") -> dict:
        return cart.search(p().farm(), q[:40])

    @app.get("/api/sell")
    def sell_view(loved: bool = True, liked: bool = False, help_wanted: bool = True, seeds: bool = True) -> dict:
        return sell.view(p().farm(), {"loved": loved, "liked": liked, "help_wanted": help_wanted, "seeds": seeds})

    @app.get("/api/morning")
    def morning_view() -> dict:
        return morning.view(p().farm())

    @app.get("/api/plan")
    def plan_view(deadline: int | None = None) -> dict:
        return cc.plan(p().farm(), deadline)

    @app.get("/api/todo")
    def todo_view() -> dict:
        pl = p()
        f = pl.farm()
        return todo.today(f, todo.DayLog(pl.path().parent.name))

    @app.put("/api/todo/tick")
    def todo_tick(task: str, done: bool = True) -> dict:
        pl = p()
        f = pl.farm()
        rec = todo.DayLog(pl.path().parent.name).tick(f.save.days_played, task, done)
        if rec is None:
            raise HTTPException(404, "No list for today yet")
        return {"ticks": rec["ticks"]}

    @app.get("/api/ask")
    def ask_search(q: str = "") -> dict:
        return ask.search(p().farm(), q[:40])

    @app.get("/api/ask/item/{qid}")
    def ask_item(qid: str) -> dict:
        return ask.item(p().farm(), qid)

    @app.get("/api/ask/villager/{name}")
    def ask_villager(name: str) -> dict:
        return ask.villager(p().farm(), name)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
