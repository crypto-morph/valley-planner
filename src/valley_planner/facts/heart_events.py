"""Someone's heart events: where and when each can start, from Data/Events (1.6.15).

An event starts when you walk into its map and its conditions hold: the key reads "id/f Name points/t from to/
w sunny/p Name/n mail", meaning at least that many friendship points, inside that time, in that weather, with
them in the room, once that letter has come. None of a sweetheart's events gate the Bouquet, the Pendant or a
proposal; they're worth a little friendship, and a couple of answers cost a lot.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

HEART = 250
# A few answers worth knowing before you're asked, in our own words: what's at stake in the event.
ADVICE = {
    "34": "Back her up kindly when she's upset (+50); blaming George costs 50.",
    "36": "Say you enjoyed the meal (+50); asking to take the rest away costs 50.",
    "181928": "When she asks about children, say you'd love to. The other answer costs 1,500 points.",
    "38": "Don't turn her down at the spa: that costs 1,500 points.",
}


@dataclass(frozen=True)
class HeartEvent:
    id: str
    location: str
    points: int
    start: int | None  # 900 = 9 AM
    end: int | None
    weather: str  # "sunny", "rainy" or ""
    present: bool  # they have to be in the room
    mail: str

    @property
    def hearts(self) -> int:
        return self.points // HEART


def _parse(location: str, key: str, name: str) -> HeartEvent | None:
    parts = key.split("/")
    points, start, end, weather, present, mail = None, None, None, "", False, ""
    for p in parts[1:]:
        t = p.split()
        if t[0] == "f" and len(t) >= 3 and t[1] == name:
            points = int(t[2]) if t[2].isdigit() else None
        elif t[0] == "t" and len(t) >= 3:
            start, end = int(t[1]), int(t[2])
        elif t[0] == "w" and len(t) >= 2:
            weather = t[1]
        elif t[0] == "p" and len(t) >= 2 and t[1] == name:
            present = True
        elif t[0] == "n" and len(t) >= 2:
            mail = t[1]
    return HeartEvent(parts[0], location, points, start, end, weather, present, mail) if points else None


@lru_cache(maxsize=4)
def _all(content: str) -> tuple[str, ...]:
    from pathlib import Path
    return tuple(sorted(p.stem for p in (Path(content) / "Data" / "Events").glob("*.xnb") if "." not in p.stem))


def events(data, name: str) -> list[HeartEvent]:
    """Their heart events, lowest first."""
    out = []
    for location in _all(str(data.install.content)):
        for key in data.asset(f"Data/Events/{location}") or {}:
            if f"f {name} " in key:
                e = _parse(location, key, name)
                if e:
                    out.append(e)
    return sorted(out, key=lambda e: e.points)
