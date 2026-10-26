"""Where villagers go each day, from Characters/schedules, decided the way the game does (1.6.15).

Which schedule (NPC.TryLoadSchedule), in our words: the first of these keys
that exists wins — even if what it says turns out empty.
  GreenRain (Year 1 green-rain day) · a passive festival: <Id>_<day of it>,
  then <Id> (married: marriage_ in front) · married: marriage_<season>_<day>,
  marriageJob (Penny Tue/Wed/Fri; Maru and Harvey Tue/Thu), marriage_<weekday>
  if it isn't raining — and nothing else · otherwise <season>_<day>,
  <day>_<hearts…1>, <day>, Pam's "bus" (once the bus is fixed), when raining
  "rain2" or "rain" (a coin flip the save can't predict), <season>_<weekday>_<h>
  for h = hearts, hearts-2 … > 0, <season>_<weekday>, <weekday>_<h> likewise,
  <weekday>, <season>, spring_<weekday>, spring.

Reading one (NPC.parseMasterScheduleImpl): stops are "/"-separated —
time (an "a" prefix: arrive by then), location (left out: stay where you
are), x, y, facing (left out: down), then an animation and/or a quoted line.
"<time> bed" means the last stop of their default (else spring) schedule —
or home; married villagers' "bed" is the Bus Stop on the way home. A first
command "GOTO <key>" swaps schedules ("season" = today's, "no_schedule" =
stay put); "MAIL <id>" skips the next command when the host has that mail
or world-state flag; "NOT friendship <npc> <hearts>…" switches the day to
"spring" if anyone has those hearts. Only JojaMart and the Railroad have
stand-in spots (<Loc>_Replacement) when closed; a Community Center stop
before it's restored switches the whole day to "default" (else "spring").
Times run past midnight as 2400+ (2530 = 1:30 AM).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from .conditions import When, check, location_accessible

WEEKDAY_SHORT = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")  # day % 7


@dataclass(frozen=True)
class Stop:
    time: int  # 600..2600
    arrive_by: bool  # "a" prefix: they set off earlier to be there by then
    location: str
    x: int
    y: int
    facing: int
    behavior: str | None = None


@dataclass(frozen=True)
class DaySchedule:
    key: str | None  # the schedule key chosen (None: no schedule — they stay home)
    stops: tuple[Stop, ...]
    chance: float = 1.0  # rain days: rain2 and rain are a 50/50 the save can't predict
    start: Stop | None = None  # a "0 <location> x y" entry: where they begin the day (else their home)


def time_label(t: int) -> str:
    """600 -> '6:00 AM', 1330 -> '1:30 PM', 2530 -> '1:30 AM'."""
    h, m = divmod(t, 100)
    h %= 24
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


@dataclass
class Situation:
    """What the schedule choice depends on, beyond the date."""

    when: When
    hearts: int = 0
    married: bool = False
    raining: bool = False
    green_rain: bool = False
    world_state: frozenset[str] = frozenset()


class Schedules:
    def __init__(self, data):
        self.data = data

    @cached_property
    def characters(self) -> dict:
        return self.data.asset("Data/Characters")

    def raw(self, npc: str) -> dict[str, str]:
        name = "LeoMainland" if npc == "Leo" else npc
        if not self.data.has(f"Characters/schedules/{name}"):
            return {}
        return self.data.asset(f"Characters/schedules/{name}")

    def home(self, npc: str, when: When) -> tuple[str, int, int]:
        for h in (self.characters.get(npc) or {}).get("Home") or []:
            if check(h.get("Condition"), when) is not False:
                tile = h.get("Tile") or {}
                return h.get("Location") or "Town", int(tile.get("X", 0)), int(tile.get("Y", 0))
        return "Town", 0, 0

    @cached_property
    def passive_festivals(self) -> dict:
        return self.data.asset("Data/PassiveFestivals")

    def _get(self, raw: dict[str, str], key: str) -> tuple[str, str] | None:
        """Keys match regardless of case."""
        if key in raw:
            return key, raw[key]
        lowered = key.lower()
        return next(((k, v) for k, v in raw.items() if k.lower() == lowered), None)

    def candidates(self, npc: str, s: Situation) -> list[str]:
        """Schedule keys in the order the game tries them (the rain pair included)."""
        w = s.when
        wd = WEEKDAY_SHORT[w.day % 7]
        keys: list[str] = []
        if s.green_rain and w.year == 1:
            keys.append("GreenRain")
        for fid, fest in self.passive_festivals.items():
            if (fest.get("Season") or "").lower() == w.season and fest["StartDay"] <= w.day <= fest["EndDay"] \
                    and check(fest.get("Condition"), w) is not False:
                n = w.day - fest["StartDay"] + 1
                pre = "marriage_" if s.married else ""
                keys += [f"{pre}{fid}_{n}", f"{pre}{fid}"]
        if s.married:
            keys.append(f"marriage_{w.season}_{w.day}")
            if (npc == "Penny" and wd in ("Tue", "Wed", "Fri")) or (npc in ("Maru", "Harvey") and wd in ("Tue", "Thu")):
                keys.append("marriageJob")
            if not s.raining:
                keys.append(f"marriage_{wd}")
            return keys
        keys.append(f"{w.season}_{w.day}")
        keys += [f"{w.day}_{h}" for h in range(s.hearts, 0, -1)]
        keys.append(str(w.day))
        if npc == "Pam" and "ccVault" in w.mail:
            keys.append("bus")
        if s.raining:
            keys += ["rain2", "rain"]
        keys += [f"{w.season}_{wd}_{h}" for h in range(s.hearts, 0, -2)] + [f"{w.season}_{wd}"]
        keys += [f"{wd}_{h}" for h in range(s.hearts, 0, -2)] + [wd, w.season, f"spring_{wd}", "spring"]
        return keys

    def today(self, npc: str, s: Situation) -> list[DaySchedule]:
        """The day's schedule; two on a rainy day when the villager has both rain2 and rain."""
        raw = self.raw(npc)
        if not raw:
            return [DaySchedule(None, ())]
        found = []
        for key in self.candidates(npc, s):
            hit = self._get(raw, key)
            if not hit:
                continue
            if hit[0].lower() == "rain2":
                found.append((hit[0], 0.5))
                continue  # the other half of the coin flip falls through to the next key that exists
            found.append((hit[0], 0.5 if found else 1.0))
            break
        if not found:
            return [DaySchedule(None, ())]
        out = []
        for k, p in found:
            stops = self.parse(npc, k, s)
            start = next((st for st in stops if st.time == 0), None)
            out.append(DaySchedule(k, tuple(st for st in stops if st.time != 0), p, start))
        return out

    def parse(self, npc: str, key: str, s: Situation, _visited: tuple[str, ...] = ()) -> tuple[Stop, ...]:
        raw = self.raw(npc)
        if key.lower() in (v.lower() for v in _visited):
            return ()  # the game stops a GOTO loop with an empty day
        visited = (*_visited, key)
        hit = self._get(raw, key)
        if not hit:
            return () if key == "spring" else self.parse(npc, "spring", s, visited)
        commands = [c.strip() for c in hit[1].split("/") if c.strip()]
        if not commands:
            return ()

        def goto(target: str) -> tuple[Stop, ...]:
            if target.lower() == "season":
                target = s.when.season if self._get(raw, s.when.season) else "spring"
            if target.lower() == "no_schedule":
                return ()
            return self.parse(npc, target if self._get(raw, target) else "spring", s, visited)

        first = commands[0].split()
        i = 0
        if "GOTO" in commands[0]:
            return goto(first[1] if len(first) > 1 else "spring")
        if "NOT" in commands[0] and len(first) > 1 and first[1].lower() == "friendship":
            pairs = first[2:]
            for other, need in zip(pairs[::2], pairs[1::2], strict=False):
                if need.isdigit() and s.when.hearts.get(other, 0) >= int(need):
                    return self.parse(npc, "spring", s, visited)
            i = 1
        elif "MAIL" in commands[0]:
            mail = first[1] if len(first) > 1 else ""
            i = 2 if (mail in s.when.mail or mail in s.world_state) else 1
        if i < len(commands) and "GOTO" in commands[i]:
            parts = commands[i].split()
            return goto(parts[1] if len(parts) > 1 else "spring")

        home = self.home(npc, s.when)
        loc = "BusStop" if s.married else home[0]
        stops: list[Stop] = []
        for cmd in commands[i:]:
            t = cmd.split()
            if len(t) < 2:
                continue
            arrive = t[0].startswith("a")
            try:
                time = int(t[0].lstrip("a"))
            except ValueError:
                continue
            behavior = None
            if t[1] == "bed":
                if s.married:
                    where, x, y, facing = "BusStop", 9, 23, 3
                else:
                    where, x, y, facing = self._bed(npc, home)
                behavior = f"{npc.lower()}_sleep"
            else:
                k = 1
                if t[1].lstrip("-").isdigit():
                    where = loc  # location left out: stay in the same place
                else:
                    where, k = t[1], 2
                try:
                    x, y = int(t[k]), int(t[k + 1])
                except (ValueError, IndexError):
                    continue
                k += 2
                facing = 2
                if len(t) > k and t[k].lstrip("-").isdigit():
                    facing = int(t[k])
                    k += 1
                if len(t) > k and not t[k].startswith('"'):
                    behavior = t[k]
                swap = self._closed(where, raw, s.when)
                if swap == "fallback":
                    fallback = "default" if self._get(raw, "default") else "spring"
                    return self.parse(npc, fallback, s, visited)
                if swap:
                    where, x, y, facing = swap
            if time == 0:  # sets where they start the day (today() splits it out)
                loc = where
            stops.append(Stop(time, arrive, where, x, y, facing, behavior))
            loc = where
        return tuple(stops)

    def _bed(self, npc: str, home: tuple[str, int, int]) -> tuple[str, int, int, int]:
        raw = self.raw(npc)
        for key in ("default", "spring"):
            hit = self._get(raw, key)
            if hit:
                last = [c.strip() for c in hit[1].split("/") if c.strip()][-1].split()
                if len(last) > 3 and last[2].lstrip("-").isdigit() and last[3].lstrip("-").isdigit():
                    return last[1], int(last[2]), int(last[3]), 2
                break
        return home[0], home[1], home[2], 2

    def _closed(self, where: str, raw: dict, w: When):
        """NPC.changeScheduleForLocationAccessibility: a stand-in spot, 'fallback', or None (open)."""
        if where in ("JojaMart", "Railroad") and not location_accessible(where, w):
            hit = self._get(raw, f"{where}_Replacement")
            if not hit:
                return "fallback"
            p = hit[1].split()
            return p[0], int(p[1]), int(p[2]), int(p[3])
        if where == "CommunityCenter" and not location_accessible(where, w):
            return "fallback"
        return None
