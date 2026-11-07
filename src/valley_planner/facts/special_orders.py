"""Lewis's Special Orders board (the town board, not Qi's) on the coming Mondays, worked out the way the game rolls it.

When it changes: overnight into days 1, 8, 15 and 22 of every season (the
Mondays), after the day count and the season have moved on, the game throws
the board away and deals two new orders. The board stands in town only from
day 58 (Fall 2, Year 1), but it is dealt from the start, so the save always
holds one.

How it deals (SpecialOrder.UpdateAvailableSpecialOrders, 1.6.15), in our words:
- Every Data/SpecialOrders entry with an empty OrderType, in data order, is
  a candidate if it can start now: not already completed (unless
  repeatable); not a month-long order once it's day 16 or later; its
  RequiredTags hold; its Condition holds; and it isn't an order the farm has
  taken (an order taken stays "taken" through the Monday its time runs out:
  the board is dealt before failed orders are cleared away).
- A second list drops the completed ones (the repeatable ones that are left).
- One generator seeded from (game id, days played × 1.3) picks an order from
  the second list, then draws Next() as that order's own seed; twice, taking
  the first pick out of both lists. If the second list runs dry, it's refilled
  from the first.
- The order itself (GetSpecialOrder): a generator seeded from its own seed
  walks the order's RandomizedElements in turn: of the values whose
  RequiredTags hold, it picks one; a "PICK_ITEM a, b, c" value then picks one
  of those items too. The objectives' text and the money reward are filled
  in from those picks (a reward of "{Crop:Price}" is that item's sell price
  with the farm's professions at the time it's dealt, so we use today's).

Tags (SpecialOrder.CheckTag): season_<s> the season that Monday;
mail_<id> mail had or coming; event_<id> an event seen; knows_<npc> met;
island the boat trip taken (seenBoatJourney); completed_<id>, rule_<id>,
dropbox_<id> depend on other orders; NOT_IMPLEMENTED and anything unknown fail.

What we assume, and say so: from now until each Monday, the farm takes and
completes no orders (the ones it has now run out on their due date), and
nothing new is seen or received. A forecast is marked unsure, slot by slot,
when something that could still happen before that Monday would change it:
seeing an event or getting mail a tag asks for, taking an order (from the
board now or a forecast one), or completing one. `depends_on` names those
things. A tag the farm can't meet before then (island, while Willy hasn't
even invited you into his back room) isn't counted as one.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from .conditions import When, check, date_of
from .rng import MBIG, NetRandom, random_seed
from .sell import Farmer, f32, sell_price

TOWN = ""  # the OrderType of Lewis's board
BOARD_DAYS = (1, 8, 15, 22)
BOARD_OPENS = 58  # IsSpecialOrdersBoardUnlocked: days played >= 58
DAY_SCALE = 1.3
LATE_MONTH_DAY = 16  # from this day of the month, month-long orders aren't dealt
STONE = "(O)390"  # fuzzyItemSearch prefers this one of the items named Stone
MAX_SCENARIOS = 50_000  # past this many what-ifs, a board is called unsure without checking

IN, LIST2, OUT = "in", "list2", "out"  # a candidate in both lists / only the refill list / neither


@dataclass(frozen=True)
class Order:
    key: str  # Data/SpecialOrders key
    requester: str  # NPC internal name
    name: str  # the order's title
    requirement: str  # the objectives in words, with the randomized picks filled in
    reward: int  # gold (money rewards only; mail, friendship and the like aren't counted)
    duration: str  # Week, TwoWeeks, Month…
    last_day: int  # days played: the last day to finish it if taken
    seed: int  # its generationSeed
    items: tuple[str, ...] = ()  # qualified ids of the items it picked (PICK_ITEM), the ones to keep
    sure: bool = True
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Board:
    days_played: int  # the Monday it's dealt
    orders: tuple[Order, ...]
    depends_on: tuple[str, ...] = ()  # what could still change it, in words

    @property
    def date(self) -> tuple[str, int, int]:
        return date_of(self.days_played)

    @property
    def label(self) -> str:
        season, day, year = self.date
        return f"{season.capitalize()} {day}, Year {year}"

    @property
    def opens(self) -> int:
        """The first day the board can be read this week (it stands in town from day 58)."""
        return max(self.days_played, BOARD_OPENS)

    @property
    def visible(self) -> bool:
        """Whether this board is ever up in town (one dealt before Fall 1, Year 1 is replaced unseen)."""
        return self.days_played + 6 >= BOARD_OPENS

    @property
    def sure(self) -> bool:
        return all(o.sure for o in self.orders)


# --- what the save holds beyond Save ---------------------------------------------------


@dataclass(frozen=True)
class OrderState:
    completed: frozenset[str]  # completedSpecialOrders
    accepted_this_week: bool  # a town order was taken from this week's board
    board: tuple[tuple[str, int], ...]  # this week's town board: (key, generationSeed)


def order_state(save) -> OrderState:
    """Read from the save file: Save doesn't carry the completed orders or the board's seeds."""
    return _order_state(str(save.path), save.mtime)


@lru_cache(maxsize=8)
def _order_state(path: str, _mtime: float) -> OrderState:
    text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    m = re.search(r"<completedSpecialOrders>(.*?)</completedSpecialOrders>", text, re.S)
    completed = frozenset(re.findall(r"<string>([^<]*)</string>", m.group(1))) if m else frozenset()
    m = re.search(r"<acceptedSpecialOrderTypes>(.*?)</acceptedSpecialOrderTypes>", text, re.S)
    accepted = bool(m and re.search(r"<string\s*/>|<string></string>", m.group(1)))
    board = []
    m = re.search(r"<availableSpecialOrders>(.*?)</availableSpecialOrders>", text, re.S)
    for chunk in re.findall(r"<SpecialOrder>(.*?)</SpecialOrder>", m.group(1), re.S) if m else []:
        kind = re.search(r"<orderType>([^<]*)</orderType>", chunk)
        key = re.search(r"<questKey>([^<]*)</questKey>", chunk)
        seed = re.search(r"<generationSeed>(-?\d+)</generationSeed>", chunk)
        if key and seed and not (kind and kind.group(1).strip()):
            board.append((key.group(1), int(seed.group(1))))
    return OrderState(completed, accepted, tuple(board))


# --- the calendar -------------------------------------------------------------------------


def is_board_day(days_played: int) -> bool:
    return date_of(days_played)[1] in BOARD_DAYS


def last_board_day(days_played: int) -> int:
    """The Monday this week's board was dealt (today, if today is one)."""
    day = date_of(days_played)[1]
    return days_played - (day - 1) % 7


def board_days(after: int, count: int) -> list[int]:
    """The next `count` Mondays after `after` (days played)."""
    first = last_board_day(after) + 7
    return [first + 7 * i for i in range(count)]


def due_date(days_played: int, duration: str) -> int | None:
    """SpecialOrder.SetDuration for an order dealt that day, as the game's 0-based day count (WorldDate.TotalDays).
    The order is up when that day starts, so it's also the last day (days played) to finish it."""
    season_start = days_played - date_of(days_played)[1] + 1
    week_start = season_start - 1 + (date_of(days_played)[1] - 1) // 7 * 7  # TotalDays of the week's day 0, +1
    return {"Week": week_start + 7, "TwoWeeks": week_start + 14, "Month": season_start - 1 + 28,
            "OneDay": days_played, "TwoDays": days_played + 1, "ThreeDays": days_played + 2}.get(duration)


def taken_at(due: int, monday: int) -> bool:
    """A taken order (not completed) still counts as taken when that Monday's board is dealt."""
    return due >= monday - 1


# --- tags --------------------------------------------------------------------------------


def _tag(tag: str, w: When, *, completed: frozenset[str], maybe_completed: set[str], can_reach_island: bool,
         ) -> bool | None:
    """CheckTag on a future day: True / False, or None when it's false now but could come true by then."""
    if tag == "NOT_IMPLEMENTED":
        return False
    if tag.startswith(("rule_", "dropbox_")):
        return None  # these follow the orders taken
    if tag.startswith("completed_"):
        key = tag[len("completed_"):]
        return True if key in completed else (None if key in maybe_completed else False)
    if tag.startswith("season_"):
        return w.season == tag[len("season_"):]
    if tag.startswith("mail_"):
        return True if w.has_or_will_get_mail(tag[len("mail_"):]) else None
    if tag.startswith("event_"):
        return True if tag[len("event_"):] in w.events_seen else None
    if tag == "island":
        return True if w.has_or_will_get_mail("seenBoatJourney") else (None if can_reach_island else False)
    if tag.startswith("knows_"):
        return True if tag[len("knows_"):] in w.hearts else None
    return False


def check_tags(tags: str | None, w: When, **kw) -> bool | None:
    """SpecialOrder.CheckTags in three values: a definite failure wins over a maybe."""
    unsure = False
    for raw in (tags or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        want = not raw.startswith("!")
        got = _tag(raw.lstrip("!"), w, **kw)
        if got is None:
            unsure = True
        elif got != want:
            return False
    return None if unsure else True


# --- dealing -----------------------------------------------------------------------------


def deal(samples: list[int], first: list[str], refill: list[str]) -> list[tuple[str, int]]:
    """The two picks of UpdateAvailableSpecialOrders from the generator's samples, in order (4 are enough)."""
    lst, lst2, it, out = list(first), list(refill), iter(samples), []
    for _ in range(2):
        if not lst:
            if not lst2:
                break
            lst = list(lst2)
        key = lst[int(next(it) * (1.0 / MBIG) * len(lst))]
        out.append((key, next(it)))
        lst.remove(key)
        if key in lst2:
            lst2.remove(key)
    return out


def board_samples(game_id: int, days_played: int, *, legacy: bool = False) -> list[int]:
    rng = NetRandom(random_seed(game_id, days_played * DAY_SCALE, legacy=legacy))
    return [rng.next() for _ in range(4)]


def _lists(states: dict[str, str], keys: list[str]) -> tuple[list[str], list[str]]:
    return [k for k in keys if states[k] == IN], [k for k in keys if states[k] in (IN, LIST2)]


# --- one order ------------------------------------------------------------------------


class _Orders:
    def __init__(self, data, save):
        self.data = data
        self.save = save
        self.orders = data.asset("Data/SpecialOrders")
        self.strings = data.asset("Strings/SpecialOrderStrings") or {}
        self.objects = data.asset("Data/Objects")
        self.farmer = Farmer.from_save(save)

    def localize(self, text: str) -> str:
        """MakeLocalizationReplacements: [Key] -> Strings/SpecialOrderStrings, innermost-last first."""
        text = (text or "").strip()
        while (i := text.rfind("[")) >= 0:
            j = text.find("]", i)
            if j < 0:
                break
            text = text[:i] + str(self.strings.get(text[i + 1:j], "")) + text[j + 1:]
        return text

    def item_id(self, name: str) -> str | None:
        """PICK_ITEM's lookup: an item id, else the first Objects entry by name (fuzzyItemSearch)."""
        name = name.strip()
        if name in self.objects:
            return f"(O){name}"
        if self.objects.get(STONE[3:], {}).get("Name") == name:
            return STONE
        squash = name.lower().replace(" ", "")
        exact = next((k for k, o in self.objects.items() if o.get("Name") == name), None)
        loose = next((k for k, o in self.objects.items() if (o.get("Name") or "").lower().replace(" ", "") == squash),
                     None)
        found = exact or loose
        return f"(O){found}" if found else None

    def item_name(self, qid: str) -> str:
        o = self.objects.get(qid[3:], {})
        return self.data.text(o.get("DisplayName")) or o.get("Name") or qid

    def item_price(self, qid: str) -> int:
        o = self.objects.get(qid[3:], {})
        return sell_price(int(o.get("Price") or 0), 0, self.farmer, qid, o.get("Name") or "", o.get("Category"),
                          o.get("Type") or "", profit_margin=self.save.profit_margin)

    def parse(self, text: str, picked: dict[str, str], chosen: dict[str, str]) -> str:
        """SpecialOrder.Parse: {Element} / {Element:Field} filled from the picks."""
        text = self.localize(text)
        while (i := text.rfind("{")) >= 0:
            j = text.find("}", i)
            if j < 0:
                break
            inner = text[i + 1:j]
            name, _, field = inner.partition(":")
            value = inner
            if name in picked:
                qid = picked[name]
                value = {"Text": self.item_name(qid), "TextPlural": self.item_name(qid),
                         "TextPluralCapitalized": self.item_name(qid),
                         "Tags": "id_" + qid[1:].replace(")", "_").lower(),
                         "Price": str(self.item_price(qid))}.get(field, value)
            elif name in chosen:
                value = self.localize(chosen[name])
            if field:
                parts = value.split("|")
                for k in range(0, len(parts) - 1, 2):
                    if parts[k] == field:
                        value = parts[k + 1]
                        break
            text = text[:i] + value + text[j + 1:]
        return text

    def make(self, key: str, seed: int, monday: int, w: When, tag_kw: dict) -> Order:
        """GetSpecialOrder for an order dealt on that Monday."""
        data = self.orders[key]
        rng = NetRandom(random_seed(seed))
        picked: dict[str, str] = {}
        chosen: dict[str, str] = {}
        sure, notes = True, []
        elements = data.get("RandomizedElements") or []
        used = repr((data.get("Objectives"), data.get("Rewards")))
        for n, element in enumerate(elements):
            values = element.get("Values") or []
            checks = [check_tags(v.get("RequiredTags"), w, **tag_kw) for v in values]
            if None in checks and (f"{{{element['Name']}" in used or n + 1 < len(elements)):
                sure = False
                notes.append(f"{element['Name']} depends on tags that could change")
            options = [i for i, ok in enumerate(checks) if ok]
            if not options:
                continue  # ChooseFrom on nothing draws nothing
            value = values[rng.choose(options)].get("Value") or ""
            chosen[element["Name"]] = value
            if value.startswith("PICK_ITEM"):
                items = [self.item_id(t) for t in value[len("PICK_ITEM"):].split(",") if t.strip()]
                if None in items:
                    sure = False
                    notes.append(f"couldn't place every item in {element['Name']}")
                qid = rng.choose(items)
                if qid:
                    picked[element["Name"]] = qid
        objectives = [self.parse(o.get("Text") or "", picked, chosen).rstrip(".") for o in data.get("Objectives") or []]
        gold = 0
        for r in data.get("Rewards") or []:
            if (r.get("Type") or "").strip() != "Money":
                continue
            d = r.get("Data") or {}
            try:
                amount = int(self.parse(d.get("Amount") or "0", picked, chosen))
                mult = float(self.parse(d["Multiplier"], picked, chosen)) if d.get("Multiplier") else 1.0
            except ValueError:
                sure = False
                notes.append("couldn't work out the money reward")
                continue
            gold += int(f32(f32(amount) * f32(mult)))
            if "Price" in (d.get("Amount") or "") + (d.get("Multiplier") or ""):
                notes.append("reward follows the item's sell price with today's professions")
        duration = data.get("Duration") or ""
        due = due_date(monday, duration)
        return Order(key=key, requester=data.get("Requester") or "", name=self.localize(data.get("Name") or key),
                     requirement="; ".join(o for o in objectives if o), reward=gold, duration=duration,
                     last_day=due if due is not None else monday, seed=seed, items=tuple(picked.values()),
                     sure=sure, notes=tuple(notes))


# --- the forecast -----------------------------------------------------------------------


def _who(maker: _Orders, key: str) -> str:
    d = maker.orders.get(key) or {}
    return f"{maker.localize(d.get('Name') or key)} ({d.get('Requester') or key})"


def forecast(save, data, *, mondays: int = 8) -> list[Board]:
    """The town board for the next `mondays` Mondays after the save's day (boards dealt before day 52 are
    replaced unseen, so their orders can't be taken; they're listed all the same).

    Assumes the farm takes and completes no order before then (see the module notes); each order's
    `sure` is False when something that could still happen would change that slot, and the board's
    `depends_on` says what."""
    if not str(save.unique_id or "").lstrip("-").isdigit():
        return []
    game_id = int(save.unique_id)
    state = order_state(save)
    maker = _Orders(data, save)
    town = [k for k, v in maker.orders.items() if (v.get("OrderType") or "").strip() == TOWN]
    base_when = When.from_save(save)
    can_reach_island = save.has_mail("willyBackRoomInvitation", "seenBoatJourney") or "seenBoatJourney" in getattr(
        save, "mail_tomorrow", set())

    # What could be taken before a Monday: key -> due dates (one per board it might be dealt on)
    takeable: dict[str, set[int]] = {}
    dealt = last_board_day(save.days_played)
    if not state.accepted_this_week and dealt + 6 >= BOARD_OPENS:  # it can still be read this week
        for key, _seed in state.board:
            if key in maker.orders:
                due = due_date(dealt, maker.orders[key].get("Duration") or "")
                if due is not None:
                    takeable.setdefault(key, set()).add(due)
    active = {o["key"]: o for o in save.special_orders if (o.get("type") or "") == TOWN}

    boards = []
    for monday in board_days(save.days_played, mondays):
        w = base_when.on(monday)
        maybe_completed = set(active) | set(takeable)
        tag_kw = {"completed": state.completed, "maybe_completed": maybe_completed,
                  "can_reach_island": can_reach_island}
        options: dict[str, list[str]] = {}  # key -> its possible states, the assumed one first
        why: dict[str, list[str]] = {}
        for key in town:
            d = maker.orders[key]
            repeatable = bool(d.get("Repeatable"))
            if w.day >= LATE_MONTH_DAY and d.get("Duration") == "Month":
                options[key] = [OUT]
                continue
            elig = check_tags(d.get("RequiredTags"), w, **tag_kw)
            if elig is not False:
                cond = check(d.get("Condition"), w)
                elig = False if cond is False else (None if (cond is None or elig is None) else True)
            if elig is False:
                options[key] = [OUT]
                continue
            done = OUT if not repeatable else LIST2
            if key in state.completed:
                base = done
            elif key in active and taken_at(int(active[key].get("due_date") or 0), monday):
                base = OUT
            else:
                base = IN
            if elig is None:
                base = OUT
            states = [base]
            reasons = []
            if elig is None:
                states.append(IN if key not in state.completed else done)
                reasons.append(f"{_who(maker, key)}: its tags or condition could come to hold")
            if key in active and key not in state.completed and active[key].get("state") == "InProgress":
                states.append(done)
                reasons.append(f"finishing {_who(maker, key)} (taken now)")
            if key in takeable:
                if any(taken_at(due, monday) for due in takeable[key]):
                    states.append(OUT)
                states.append(done)
                reasons.append(f"taking or finishing {_who(maker, key)}")
            options[key] = list(dict.fromkeys(states))
            if len(options[key]) > 1:
                why[key] = reasons

        samples = board_samples(game_id, monday, legacy=save.legacy_random)
        base_states = {k: v[0] for k, v in options.items()}
        picks = deal(samples, *_lists(base_states, town))
        varying = [k for k, v in options.items() if len(v) > 1]
        slot_sure = [True] * len(picks)
        possible: set[str] = {k for k, _ in picks}
        depends: list[str] = []
        for k in varying:  # one at a time, for the words
            for alt in options[k][1:]:
                other = deal(samples, *_lists({**base_states, k: alt}, town))
                possible |= {p for p, _ in other}
                if other != picks:
                    depends.extend(why[k])
                    break
        combos = 1
        for k in varying:
            combos *= len(options[k])
        if combos > MAX_SCENARIOS:
            slot_sure = [False] * len(picks)
        else:
            for combo in itertools.product(*(options[k] for k in varying)):
                other = deal(samples, *_lists({**base_states, **dict(zip(varying, combo, strict=True))}, town))
                possible |= {p for p, _ in other}
                for i, pick in enumerate(picks):
                    if i >= len(other) or other[i] != pick:
                        slot_sure[i] = False
                if len(other) != len(picks):
                    slot_sure = [False] * len(picks)
        orders = []
        for i, (key, seed) in enumerate(picks):
            o = maker.make(key, seed, monday, w, tag_kw)
            if not slot_sure[i] and o.sure:
                o = replace(o, sure=False)
            orders.append(o)
        if not all(slot_sure) and not depends:  # only changes together would alter it
            depends = [r for k in varying for r in why[k]]
        boards.append(Board(monday, tuple(orders), tuple(dict.fromkeys(depends))))
        for key in possible if boards[-1].visible else ():  # orders that might be dealt here might be taken
            due = due_date(monday, maker.orders[key].get("Duration") or "")
            if due is not None:
                takeable.setdefault(key, set()).add(due)
    return boards


def this_week(save, data) -> Board:
    """This week's board as the game dealt it, worked out again from the save (a check on the forecast).
    Orders completed since Monday aren't put back, so a board can differ when one was."""
    monday = last_board_day(save.days_played)
    if not str(save.unique_id or "").lstrip("-").isdigit():
        return Board(monday, ())
    game_id = int(save.unique_id)
    state = order_state(save)
    maker = _Orders(data, save)
    w = When.from_save(save).on(monday)
    tag_kw = {"completed": state.completed, "maybe_completed": set(), "can_reach_island": False}
    first, refill = [], []
    active = {o["key"]: o for o in save.special_orders if (o.get("type") or "") == TOWN}
    for key, d in maker.orders.items():
        if (d.get("OrderType") or "").strip() != TOWN:
            continue
        if key in state.completed and not d.get("Repeatable"):
            continue
        if w.day >= LATE_MONTH_DAY and d.get("Duration") == "Month":
            continue
        if not check_tags(d.get("RequiredTags"), w, **tag_kw) or check(d.get("Condition"), w) is not True:
            continue
        if key in active and taken_at(int(active[key].get("due_date") or 0), monday):
            continue
        refill.append(key)
        if key not in state.completed:
            first.append(key)
    picks = deal(board_samples(game_id, monday, legacy=save.legacy_random), first, refill)
    return Board(monday, tuple(maker.make(k, s, monday, w, tag_kw) for k, s in picks))
