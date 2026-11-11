"""What to keep back from selling: one ordered list of rules.

Each rule claims things you hold: "keep N of this, at this quality or better, because...". Rules claim in order,
each from what the rules above it left, the lowest quality first so the best stays free to sell. Whatever no rule
claims is sold, or put through a machine when that pays (views/sell.py).

Each rule has a mode: "always", "off", or for an occasion you might want to skip, "ask": Today asks a yes/no
question (views/asks.py), and a no lets it go. Settings come from the page as {rule id: mode}; anything not set
uses the rule's default.

Each rule also says what happens when you're short of cash, that is when the next few days need more gold than
you hold and what's free to sell would bring in (views/today.cash_needs): keep as usual, or let go. A rule that lets
go only gives up as much as covers the gap, the last rule first (views/sell.py). The page sets it as
{"<rule id>@short": "always" | "off"}.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ..facts import letters
from ..facts.help_wanted import raw_pool
from . import asks
from .farm import Farm

ALWAYS, ASK, OFF = "always", "ask", "off"


@dataclass(frozen=True)
class Claim:
    item: str  # qualified id
    count: int
    why: str
    min_quality: int = 0
    ask: str = ""  # the question (views/asks.py) it hangs on, if any: a no drops it


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    default: str
    modes: tuple[str, ...]
    claims: Callable[[Farm, set[str]], Iterable[Claim]]  # (farm, ids of things it may keep for gifts etc.)
    short: str = ALWAYS  # when the next few days need more gold than you have: keep as usual, or OFF to let it go


def _bundles(farm: Farm, _sellable) -> Iterable[Claim]:
    for (bkey, _), parts in farm.bundles.plan(farm.save.items).reserved.items():
        for qid, q, n in parts:
            yield Claim(qid, n, f"{farm.bundles.by_key[bkey].display} bundle", q)


def _requests(farm: Farm, _sellable) -> Iterable[Claim]:
    s = farm.save
    for q in s.quests:
        if q.get("item_id") and not q.get("completed"):
            yield Claim(f"(O){q['item_id']}", q.get("count") or 1,
                        f"{q.get('target') or 'a'} request: {q.get('title')}")
    seen = set()
    for x in letters.coming(farm.data, s, s.days_played):
        if x.item not in seen:  # the soonest letter for each thing
            seen.add(x.item)
            yield Claim(x.item, x.count, f"{x.who} asks for {'it' if x.count == 1 else x.count} by letter on "
                        f"{farm.label(x.days_played).rsplit(',', 1)[0]} ({x.title}"
                        + (f", {x.reward:,}g)" if x.reward else ")"))


def _museum(farm: Farm, _sellable) -> Iterable[Claim]:
    objects, s = farm.data.asset("Data/Objects"), farm.save
    for qid in {it.qualified_id for it in s.items if it.qualified_id.startswith("(O)")}:
        if (objects.get(qid[3:]) or {}).get("Type") in ("Arch", "Minerals") and qid[3:] not in s.museum:
            yield Claim(qid, 1, "the Museum: not donated yet")


def _festivals(farm: Farm, _sellable) -> Iterable[Claim]:
    for a in asks.asks(farm):
        qid, q, n = a.keep
        yield Claim(qid, n, a.label, q, a.id)


def birthday_gift(farm: Farm, npc: str) -> tuple[str, str] | None:
    """(qualified id, "love" or "like") of the gift to give: a loved one if you hold any, else a liked one, the
    cheapest you can spare; never what a bundle or an open request needs. None if you hold nothing they'd like."""
    objects, held = farm.data.asset("Data/Objects"), farm.held()
    needed: dict[str, int] = {}
    for c in [*_bundles(farm, set()), *_requests(farm, set())]:
        needed[c.item] = needed.get(c.item, 0) + c.count
    best = None
    for qid, n in held.items():
        if n <= needed.get(qid, 0) or not farm.gifts.giftable(qid):
            continue
        taste = farm.gifts.taste(npc, qid)
        if taste in ("love", "like"):
            rank = (taste != "love", int((objects.get(qid.removeprefix("(O)")) or {}).get("Price") or 0))
            if best is None or rank < best[0]:
                best = (rank, qid, taste)
    return (best[1], best[2]) if best else None


def _birthdays(farm: Farm, _sellable) -> Iterable[Claim]:
    w = farm.when
    for dp in range(w.days_played, w.days_played + 8):
        for npc in farm.calendar.birthdays(w.on(dp)):
            pick = birthday_gift(farm, npc)
            if pick:
                when = "today" if dp == w.days_played else farm.label(dp).rsplit(",", 1)[0]
                yield Claim(pick[0], 1, f"{npc}'s birthday ({when}): a {pick[1]}d gift")


def _seeds(farm: Farm, sellable: set[str]) -> Iterable[Claim]:
    objects, held = farm.data.asset("Data/Objects"), farm.held()
    for seed, c in farm.crops.by_seed.items():
        qid = f"(O){c.harvest}"
        if c.harvest and qid in sellable and objects.get(seed, {}).get("Category") == -74:
            yield Claim(qid, 1, "the Seed Maker" if held.get(f"(O){seed}") else
                        f"the Seed Maker: you have no {farm.name('(O)' + seed)}")


def _help_wanted(farm: Farm, sellable: set[str]) -> Iterable[Claim]:
    w, s = farm.when, farm.save
    pool = raw_pool(w.season, w.day, w.year, mine_lowest=w.mine_lowest, vault="ccVault" in s.mail,
                    crafting=set(s.crafting_recipes))
    for qid in sellable:
        if qid[3:] in pool:
            yield Claim(qid, 1, "Help Wanted might ask for it (pays 3x)")


def _names(people: list[str], most: int = 3) -> str:
    """'Abigail', 'Abigail and Emily', 'Abigail, Clint and Emily', 'Abigail, Clint, Emily and 2 more'."""
    shown = people[:most] + ([f"{len(people) - most} more"] if len(people) > most else [])
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def _villagers(farm: Farm) -> list[str]:
    return [n for n, c in farm.data.asset("Data/Characters").items() if c.get("BirthSeason")]


def _loved(farm: Farm, sellable: set[str]) -> Iterable[Claim]:
    people = _villagers(farm)
    for qid in sellable:
        if farm.gifts.giftable(qid):
            fans = [v for v in people if farm.gifts.taste(v, qid) == "love"]
            if fans:
                yield Claim(qid, min(4, 2 * len(fans)), f"a gift: loved by {_names(fans)}")


def _liked(farm: Farm, sellable: set[str]) -> Iterable[Claim]:
    people = _villagers(farm)
    for qid in sellable:
        if farm.gifts.giftable(qid):
            fans = [v for v in people if farm.gifts.taste(v, qid) == "like"]
            if fans:
                yield Claim(qid, 1, f"a gift: liked by {_names(fans)}")


RULES = [
    Rule("bundles", "Community Center bundles", ALWAYS, (ALWAYS, OFF), _bundles),
    Rule("requests", "Requests: open quests, and what a letter will ask for", ALWAYS, (ALWAYS, OFF), _requests),
    Rule("museum", "The Museum: the first of anything not donated yet", ALWAYS, (ALWAYS, OFF), _museum),
    Rule("festivals", "Festivals: the best thing for the Luau soup", ASK, (ASK, ALWAYS, OFF), _festivals),
    Rule("birthdays", "Birthdays in the next week: a gift each, loved if you have one", ALWAYS, (ALWAYS, OFF),
         _birthdays),
    Rule("seeds", "The Seed Maker: one of every crop, the lowest quality", ALWAYS, (ALWAYS, OFF), _seeds),
    Rule("help_wanted", "Help Wanted: one of each thing the board can ask for this season", ALWAYS, (ALWAYS, OFF),
         _help_wanted, OFF),
    Rule("loved", "Gifts a villager loves: 2 for each who loves it, up to 4", ALWAYS, (ALWAYS, OFF), _loved, OFF),
    Rule("liked", "Gifts a villager likes: 1", OFF, (ALWAYS, OFF), _liked, OFF),
    # claims nothing up front: views/sell.py keeps what's left after today's machine loads that a machine you own
    # turns into more, as much as your machines get through in the next 4 weeks (selling it raw loses money)
    Rule("machines", "Your machines: what they turn into more, for when one is free", ALWAYS, (ALWAYS, OFF),
         lambda _farm, _sellable: (), OFF),
]
BY_ID = {r.id: r for r in RULES}


def modes(settings: dict[str, str] | None = None) -> dict[str, str]:
    """Each rule's mode: the setting if it's one the rule allows, else its default."""
    settings = settings or {}
    return {r.id: settings.get(r.id) if settings.get(r.id) in r.modes else r.default for r in RULES}


def short_modes(settings: dict[str, str] | None = None) -> dict[str, str]:
    """What each rule does when you're short of cash: ALWAYS (keep as usual) or OFF (let it go as needed)."""
    settings = settings or {}
    return {r.id: settings.get(f"{r.id}@short") if settings.get(f"{r.id}@short") in (ALWAYS, OFF) else r.short
            for r in RULES}


def parse(text: str) -> dict[str, str]:
    """'liked:always,festivals:off' (the page's query string) -> {rule id: mode}."""
    return dict(p.split(":", 1) for p in text.split(",") if ":" in p)


def questions(farm: Farm, settings: dict[str, str] | None = None) -> list[asks.Ask]:
    """Today's yes/no questions: only from rules set to ask."""
    return asks.asks(farm) if modes(settings)["festivals"] == ASK else []
