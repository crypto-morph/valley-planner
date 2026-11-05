"""How fast the player goes down the Mines: a weekly target that follows what the save shows.

The plan starts from a target (10 floors a week: the bottom, floor 120, in twelve weeks) with one trip down each
week. Once there's enough to go on, the target moves halfway towards the pace the save shows, so a player who's
ahead gets an earlier plan and one who's behind gets an honest one.

A save only records the deepest floor, not the days spent in the Mines, so this can't tell a slow player from one
who's been busy elsewhere. It's a planning choice, and the note says what it's based on.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import MINES_OPEN

BOTTOM = 120
MIN_FLOORS = 5  # below the first elevator stop there's nothing to go on
MIN_WEEKS = 2
SLOWEST, FASTEST = 5, 40  # floors a week: a bad patch shouldn't wreck the plan, nor a good one promise too much


@dataclass(frozen=True)
class Pace:
    floors_per_week: int
    target: int
    observed: float | None = None  # floors a week since the Mines opened, once that means something

    @classmethod
    def of(cls, when, target: int) -> Pace:
        floors = when.mine_lowest
        weeks = (when.days_played - MINES_OPEN) / 7
        if floors < MIN_FLOORS or floors >= BOTTOM or weeks < MIN_WEEKS:
            return cls(target, target)
        observed = floors / weeks
        return cls(max(SLOWEST, min(FASTEST, round((target + observed) / 2))), target, observed)

    @property
    def note(self) -> str:
        if self.observed is None:
            return f"Planned at {self.floors_per_week} Mines floors a week, one trip down each week"
        return (f"Planned at {self.floors_per_week} Mines floors a week, one trip down each week: your target of "
                f"{self.target}, moved towards the {self.observed:.0f} a week your save shows")
