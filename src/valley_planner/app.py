"""The planner's web app: a small local server for one player's own save.

It reads the newest save by default (or the one you pick) and re-reads it
when the game writes a new one. Nothing leaves your computer.
"""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .discover import find_game, find_saves_root, list_saves
from .engine import cc, todo
from .gamedata import GameData
from .views import ask, calendar, cart, crops, errands, extras, keep, layout, month, morning, picking, romance, sell
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
        self._textures = None

    @property
    def textures(self):
        """The game's pictures, decoded on demand (see pictures.py)."""
        from .pictures import shared
        if self._textures is None:
            self._textures = shared(self.data.install.content, self.data.cache)
        return self._textures

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


class RouteAsk(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["greenhouse", "seed_maker"])
    nice: list[str] = Field(default_factory=lambda: ["kitchen", "cc"])
    cave: str = "best"
    start: str = "save"  # "save": from today in the chosen save; "fresh": a new farm on Spring 1
    settings: dict = Field(default_factory=dict)


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
                "date": f.label(f.save.days_played) if f else None,
                "seasonal_errands": errands.seasonal(f) if f else []}

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

    @app.get("/api/cart/tab")
    def cart_tab(spouse: str = "") -> dict:
        return cart.tab(p().farm(), spouse)

    @app.get("/api/cart/search")
    def cart_search(q: str = "") -> dict:
        return cart.search(p().farm(), q[:40])

    @app.get("/api/sell")
    def sell_view(rules: str = "", declined: str = "") -> dict:
        """`rules`: the keep rules' modes (views/keep.py) as 'id:mode,...'; `declined`: Today's questions said no to."""
        return sell.view(p().farm(), keep.parse(rules), declined=frozenset(filter(None, declined.split(","))))

    @app.get("/api/romance")
    def romance_view(target: str = "") -> dict:
        return romance.view(p().farm(), target)

    @app.get("/api/month")
    def month_view(offset: int = 0, spouse: str = "") -> dict:
        return month.view(p().farm(), offset, spouse)

    @app.get("/api/picking")
    def picking_view() -> dict:
        farm = p().farm()
        return {"waiting": picking.waiting(farm), "giants": picking.giants(farm), "plans": picking.plans(farm),
                "legend": picking.LEGEND}

    @app.get("/api/extras")
    def extras_view() -> list[dict]:
        return extras.view(p().farm())

    @app.get("/api/layout")
    def layout_view(crops: int | None = None) -> dict:
        return layout.view(p().farm(), crops)

    @app.get("/api/watch")
    def watch_view() -> dict:
        return {"cabbage": month.red_cabbage(p().farm())}

    @app.get("/api/morning")
    def morning_view() -> dict:
        return morning.view(p().farm())

    @app.get("/api/today")
    def today_view(time: int | None = None, energy: int | None = None, where: str = "", done: str = "",
                   spouse: str = "", goals: str = "", declined: str = "", rules: str = "",
                   plant_all: bool = False) -> dict:
        """The day's timed plan; time, energy and where for a recalculation from wherever you are. `goals`: the
        Goals page's ask (JSON), so the day follows your route (what to hold back for an earlier goal).
        `declined`: the ids of the day's questions (views/asks.py) you said no to, comma separated; `rules`: the
        keep rules' modes (views/keep.py), as 'id:mode,...'."""
        from .views import today
        route = None
        if goals:
            try:
                route = planned(RouteAsk.model_validate_json(goals))
            except ValueError:
                route = None
        ticked = set(filter(None, done.split(",")))
        farm, pl = p().farm(), p()
        store = todo.pace_file(pl.path().parent.name) if pl.path() else None
        pace = today.learned_pace(store, farm.save.days_played, None) if store else None
        if store and time is not None and ticked:
            ratio = today.pace_ratio(today.view(farm, spouse=spouse, pace=pace), time, ticked)
            pace = today.learned_pace(store, farm.save.days_played, ratio)
        return today.view(farm, time=time, energy=energy, where=where or None, done=ticked, spouse=spouse, pace=pace,
                          route=route, declined=frozenset(filter(None, declined.split(","))),
                          rules=keep.parse(rules), plant_all=plant_all)

    @app.get("/api/cook")
    def cook_view() -> dict:
        from .views import cook
        return cook.view(p().farm())

    @app.get("/api/quests")
    def quests_view() -> dict:
        from .views import quests
        return quests.view(p().farm())

    @app.post("/api/morning")
    def morning_with_route(ask: RouteAsk) -> dict:
        """The morning, with the route's steps for today (the Route tab's goals) slotted into the day."""
        from .engine.route.plan import route
        farm, targets, nice, settings, cave = route_args(ask)
        farm = p().farm()  # the morning is always the save's day
        agenda = route(farm, targets, nice, settings=settings, cave=cave)["agenda"] if targets or nice else []
        return morning.view(farm, agenda)

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

    @app.get("/api/errand/{name}")
    def errand(name: str) -> dict:
        if name not in errands.ERRANDS:
            raise HTTPException(404, f"No errand called {name}")
        return errands.ERRANDS[name](p().farm())

    @app.get("/api/route/objectives")
    def route_objectives() -> dict:
        from .engine.route.plan import CATALOG, Settings
        try:
            farm = p().farm()
            chars, friends = farm.data.asset("Data/Characters"), farm.save.friends
        except HTTPException:
            chars, friends = p().data.asset("Data/Characters"), {}
        spouses = [{"name": k, "hearts": friends[k].points // 250 if k in friends else 0}
                   for k, c in chars.items() if c.get("CanBeRomanced")]
        return {"objectives": [{"id": k, "label": v[0]} for k, v in CATALOG.items()],
                "settings": Settings().__dict__, "spouses": spouses}

    def route_args(ask: RouteAsk) -> tuple:
        """(farm, targets, nice, settings, cave) from the page's ask, unknown goals and settings dropped."""
        from .engine.route.plan import CATALOG, Settings
        from .engine.route.start import new_farm
        known = set(CATALOG)
        kinds = {k: type(v) for k, v in Settings().__dict__.items()}
        settings = Settings(**{k: kinds[k](v) for k, v in ask.settings.items() if k in kinds})
        cave = ask.cave if ask.cave in ("best", "bats", "mushrooms") else "best"
        farm = p().farm() if ask.start == "save" and p().path() is not None else new_farm(p().data)
        return (farm, [t for t in ask.targets if t in known],
                [n for n in ask.nice if n in known and n not in ask.targets], settings, cave)

    memo: dict[tuple, dict] = {}

    def planned(ask: RouteAsk) -> dict:
        """The goals route for this ask, remembered until the save changes (Today, the Wood note and Goals share
        it)."""
        from .engine.route.plan import route
        path = p().path() if ask.start == "save" else None
        key = (str(path), path.stat().st_mtime if path else 0, ask.model_dump_json())
        if key not in memo:
            if len(memo) > 8:
                memo.clear()
            farm, targets, nice, settings, cave = route_args(ask)
            memo[key] = route(farm, targets, nice, settings=settings, cave=cave)
        return memo[key]

    @app.post("/api/route")
    def route_view(ask: RouteAsk) -> dict:
        """The rest of this year (from the save, or a fresh farm) planned for these targets (in order) and
        nice-to-haves (in order)."""
        return planned(ask)

    @app.post("/api/today/wood")
    def wood_view(ask: RouteAsk, trees: int = 0) -> dict:
        """The Wood note from your goals' own dates: the next job you're short for, how soon, and the schedule."""
        from .views.today import wood_plan, wood_uses
        return {"note": wood_plan(p().farm(), wood_uses(planned(ask)), trees)}

    @app.post("/api/needs")
    def needs_view(ask: RouteAsk) -> dict:
        """Everything these goals take, added up: gold, materials and days, what each is for, and every way
        to get the items that have more than one."""
        from .engine.route.needs import needs
        farm, targets, nice, settings, cave = route_args(ask)
        return needs(farm, targets, nice, settings=settings, cave=cave)

    @app.get("/api/ask")
    def ask_search(q: str = "") -> dict:
        return ask.search(p().farm(), q[:40])

    @app.get("/api/ask/item/{qid}")
    def ask_item(qid: str) -> dict:
        return ask.item(p().farm(), qid)

    @app.get("/api/ask/villager/{name}")
    def ask_villager(name: str) -> dict:
        return ask.villager(p().farm(), name)

    @app.get("/map.html")
    def map_page() -> FileResponse:
        """A page for looking at one map: /map.html?loc=Farm&x=61&y=21&r=8 (no x/y: the whole map)."""
        return FileResponse(STATIC / "map.html")

    @app.get("/world.html")
    def world_page() -> FileResponse:
        """Today on the valley's maps: places of interest and the planned walk (static/world.js)."""
        return FileResponse(STATIC / "world.html")

    @app.get("/satnav.html")
    def satnav_page() -> FileResponse:
        """Today as a satnav: one instruction at a time on the map (static/satnav.js)."""
        return FileResponse(STATIC / "satnav.html")

    @app.get("/api/world")
    def world_view(time: int | None = None, energy: int | None = None, where: str = "", done: str = "",
                   spouse: str = "") -> dict:
        """Today's places of interest and the planned walk, by map (views/world.py); same asks as /api/today."""
        from .views import today, world
        farm, pl = p().farm(), p()
        store = todo.pace_file(pl.path().parent.name) if pl.path() else None
        pace = today.learned_pace(store, farm.save.days_played, None) if store else None
        return world.view(farm, time=time, energy=energy, where=where or None,
                          done=set(filter(None, done.split(","))), spouse=spouse, pace=pace)

    @app.get("/api/tex/{asset:path}")
    def texture(asset: str, v: str = "") -> Response:
        """A picture from the game's Content folder as PNG, e.g. /api/tex/Maps/spring_town.png. Nothing outside it."""
        from .pictures import NotAllowed
        from .xnb.reader import XnbError
        if not asset.endswith(".png"):
            raise HTTPException(404, "Textures are served as .png")
        try:
            png = p().textures.png(asset[:-4])
        except NotAllowed as e:
            raise HTTPException(400, str(e)) from e
        except (FileNotFoundError, XnbError) as e:
            raise HTTPException(404, f"No picture called {asset[:-4]}") from e
        cache = "max-age=31536000, immutable" if v else "no-cache"
        return Response(png, media_type="image/png", headers={"Cache-Control": cache})

    def map_for(location: str, season: str) -> tuple[str, str, Farm | None]:
        """(map asset, season, the save's Farm) for a location, from the chosen save when there is one."""
        from .pictures import NotAllowed, map_asset
        pl = p()
        try:
            farm = pl.farm()
        except HTTPException:
            farm = None
        try:
            asset = map_asset(location, farm.save.farm_type if farm else 0)
            pl.textures.path(asset)
        except NotAllowed as e:
            raise HTTPException(400, str(e)) from e
        except FileNotFoundError as e:
            raise HTTPException(404, f"No map for {location}") from e
        return asset, (season or (farm.save.season if farm else "spring")).lower(), farm

    @app.get("/api/map/{location}")
    def map_view(location: str, season: str = "") -> JSONResponse:
        """A map's tile sheets and layers, ready for static/map.js to draw. (Sent as it is: big lists of plain
        numbers don't need FastAPI's slow encoder.)"""
        from .pictures import map_draw
        asset, season, _farm = map_for(location, season)
        return JSONResponse({"location": location, **map_draw(p().textures, asset, season)})

    @app.get("/api/map/{location}/sprites")
    def map_sprites(location: str, season: str = "") -> JSONResponse:
        """What the save has standing on that map today (crops, dirt, trees, objects, buildings…) as sprites."""
        from .pictures import map_facts
        from .views.scene import scene
        asset, season, farm = map_for(location, season)
        if farm is None:
            raise HTTPException(404, "No save found; set VALLEY_PLANNER_SAVES to your Saves folder")
        season, outdoors, front = map_facts(p().textures, asset, season)
        return JSONResponse(scene(farm, p().textures, location, season, outdoors=outdoors, front=front))

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def always_fresh(request, call_next):
        """The page and its files are checked with the server on every load (a quick 'not changed' when they
        haven't), so an update shows at once instead of a browser's cached copy."""
        response = await call_next(request)
        pages = ("/", "/map.html", "/world.html", "/satnav.html")
        if request.url.path in pages or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response
    return app
