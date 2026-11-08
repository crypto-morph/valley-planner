"""One GameData for the whole test run: decoding the game's content costs seconds, and it never changes mid-run."""

from functools import cache

from valley_planner.discover import find_game
from valley_planner.gamedata import GameData


@cache
def shared_data() -> GameData:
    """The local game's data, built once; RuntimeError when there's no game here (as Planner(None) raises)."""
    game = find_game()
    if game is None:
        raise RuntimeError("Stardew Valley wasn't found; set VALLEY_PLANNER_GAME to its folder")
    return GameData(game)
