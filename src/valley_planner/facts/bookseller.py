"""The Bookseller: which days he comes each season, and what he sells and trades on a visit (1.6.15).

When he comes, in our words (Utility.getDaysOfBooksellerThisSeason):
- Two days every season, every year from Spring Year 1; nothing unlocks him.
  Each season has a list of candidate days (Spring 11 12 21 22 25, Summer
  9 12 18 25 27, Fall 4 7 8 9 12 19 22 25, Winter 5 11 12 19 22 24); one is
  picked with Next(count) on a generator seeded from (year * 11, game id,
  season index), the other is half the list further on (wrapping). None of
  the candidates is a festival day.
- Where: his van in the north-east of Pelican Town, north of JojaMart (the
  counter is the Town tiles 109-110, 26). He is there all day: the morning
  message says he's in town, and the counter works whenever you're in Town.
- Reading any book once (mail flag "read_a_book") adds "Trade" to his
  counter; before that, clicking him opens the buy shop straight away.

What he sells (Data/Shops "Bookseller", built by ShopBuilder.GetShopStock):
- One generator per opening, seeded from (days played, game id / 2) — the
  same as every shop — so the stock is fixed for the day.
- Entries are taken in order; a failed condition skips an entry without
  touching the generator. SYNCED_RANDOM day <key> <chance> conditions roll
  their own generator (hash of the key, game id, days played), so each roll
  (the Purple Book 25%, a 3rd skill book 60%, a 2nd 80%, an extra Foraging
  skill book 33%) is fixed for the day.
- RandomItemId picks one with Next(count). With AvoidRepeat the choice is
  among the options not already in the shop (every item stocked so far is
  remembered, AvoidRepeat or not).
- Prices are the entry's Price; books take no profit margin (only category
  -74 seeds and saplings do), and the shop has no price modifiers.
- Conditions on the player (PLAYER_STAT Book_Speed, golden walnuts found)
  are read from the save as it is now: for a later day they're shown, not
  sure, when they'd hold only if you read that book / find those walnuts.

His trades (Data/Shops "BooksellerTrade"): the same seeded generator, its own
opening; an entry gives MinStack of an item for a book you have read (the
book itself is the price, never money).

Unsure:
- Not yet checked against a stock seen in the game (no save here was made
  on a Bookseller day with the shop open). The rules are the shared shop
  rules the Traveling Cart test (cart.py) checks item for item.
- Golden walnuts found isn't read from the save: unless `world_fields`
  gives GoldenWalnutsFound, the Queen of Sauce Cookbook is shown not sure.
"""

from __future__ import annotations

from dataclasses import dataclass

from .calendar import bookseller_days
from .cart import _apply
from .conditions import When, check, date_of, split
from .rng import NetRandom, day_save_random

SHOP = "Bookseller"
TRADE_SHOP = "BooksellerTrade"
TRADE_UNLOCK_MAIL = "read_a_book"
LANDMARK = "his van in the north-east of Pelican Town, north of JojaMart"
PLAYER_KEYS = {"PLAYER_STAT", "WORLD_STATE_FIELD"}  # true now or later depending on what you do


@dataclass(frozen=True)
class BookItem:
    item: str  # qualified id
    name: str
    price: int  # gold; 0 for a trade
    stock: int  # how many you can take (2**31 - 1: no limit)
    entry: str  # the Data/Shops entry Id
    condition: str = ""  # the entry's condition, as the data has it
    sure: bool = True  # False: depends on something not known yet (see `why`)
    why: str = ""
    trade_item: str = ""  # trades: the book you give
    trade_amount: int = 0
    stack: int = 1  # trades: how many you get


@dataclass(frozen=True)
class BooksellerDay:
    days_played: int
    season: str
    day: int
    year: int
    items: tuple[BookItem, ...]
    trades: tuple[BookItem, ...]
    trade_open: bool  # he offers "Trade" (you've read a book)

    @property
    def label(self) -> str:
        return f"{self.season.capitalize()} {self.day}, Year {self.year}"


def visit_days(game_id: int, year: int, season: str, *, legacy: bool = False) -> tuple[int, int]:
    """His two days this season, earlier first."""
    return tuple(sorted(bookseller_days(season.lower(), year, game_id, legacy=legacy)))


def visits(game_id: int, from_days_played: int, count_days: int = 112, *, legacy: bool = False) -> list[int]:
    """Days played of each visit from `from_days_played` (included) for `count_days`."""
    out = []
    for dp in range(from_days_played, from_days_played + count_days):
        season, day, year = date_of(dp)
        if day in visit_days(game_id, year, season, legacy=legacy):
            out.append(dp)
    return out


def _stat_check(tokens: list[str], stats: dict[str, int]) -> bool | None:
    """PLAYER_STAT <player> <stat> <min> [max]."""
    if len(tokens) < 4:
        return None
    try:
        lo = int(tokens[3])
        hi = int(tokens[4]) if len(tokens) > 4 else 2**31 - 1
    except ValueError:
        return None
    return lo <= stats.get(tokens[2], 0) <= hi


def _condition(condition: str | None, when: When, stats: dict[str, int], today: bool) -> tuple[bool | None, str]:
    """(holds, why not sure). False only when it certainly fails that day."""
    if not condition:
        return True, ""
    unknown, why = False, []
    for tokens in split(condition):
        negate = tokens[0].startswith("!")
        key = tokens[0].lstrip("!").upper()
        if key == "PLAYER_STAT":
            result = _stat_check(tokens, stats)
        else:
            result = check(" ".join([key, *tokens[1:]]), when)
        if result is not None and negate:
            result = not result
        if result is None:
            unknown = True
            why.append(" ".join(tokens))
        elif result is False:
            if key in PLAYER_KEYS and not today:
                unknown = True  # might hold by then
                why.append(f"if {' '.join(tokens)} by then")
            else:
                return False, ""
    return (None, "; ".join(why)) if unknown else (True, "")


class Bookseller:
    def __init__(self, data):
        self.data = data

    def _name(self, qid: str) -> str:
        kind, _, iid = qid[1:].partition(")")
        table = {"O": "Data/Objects", "BC": "Data/BigCraftables"}.get(kind)
        if table:
            row = (self.data.asset(table) or {}).get(iid)
            if row:
                return self.data.text(row.get("DisplayName")) or row.get("Name") or qid
        return qid

    def _shop(self, shop_id: str, when: When, stats: dict[str, int], today: bool) -> tuple[BookItem, ...]:
        shop = self.data.asset("Data/Shops")[shop_id]
        rng = day_save_random(when.days_played, when.game_id or 0, legacy=when.legacy_random)
        seen: set[str] = set()
        rolls_sure = True
        out: list[BookItem] = []
        for entry in shop.get("Items") or []:
            ok, why = _condition(entry.get("Condition"), when, stats, today)
            if ok is False:
                continue
            if ok is None:  # maybe there: work it out on a copy, and doubt later rolls if it drew
                probe = rng.clone()
                got = self._entry(shop, entry, probe, set(seen))
                if probe.draws != rng.draws:
                    rolls_sure = False
                out += [_item(g, entry, self._name(g[0]), False, why) for g in got]
                continue
            draws = rng.draws
            got = self._entry(shop, entry, rng, seen)
            sure = rolls_sure or rng.draws == draws
            out += [_item(g, entry, self._name(g[0]), sure, "" if sure else "an earlier maybe-item rolls first")
                    for g in got]
        return tuple(out)

    @staticmethod
    def _entry(shop: dict, entry: dict, rng: NetRandom, seen: set[str]) -> list[tuple[str, int, int]]:
        """One entry's (item, price, stock), drawing as the game does."""
        options = entry.get("RandomItemId")
        if options:
            if entry.get("AvoidRepeat") and seen:
                options = [o for o in dict.fromkeys(options) if o not in seen]  # Enumerable.Except: distinct
            if not options:
                return []
            picks = [rng.choose(options)]
        elif (entry.get("ItemId") or "").startswith("("):
            picks = [entry["ItemId"]]
        else:
            raise ValueError(f"bookseller item query not supported: {entry.get('ItemId')}")
        out = []
        for qid in picks:
            price = entry.get("Price", -1)
            if price < 0:  # every entry here sets a Price, or is a trade (no money)
                if not entry.get("TradeItemId"):
                    raise ValueError(f"bookseller price for {qid} not supported")
                price = 0
            if not entry.get("IgnoreShopPriceModifiers"):
                price = _apply(price, shop.get("PriceModifiers"), shop.get("PriceModifierMode"), rng)
            price = _apply(price, entry.get("PriceModifiers"), entry.get("PriceModifierMode"), rng)
            stock = entry.get("AvailableStock", -1)
            stock = int(_apply(stock, entry.get("AvailableStockModifiers"), entry.get("AvailableStockModifierMode"),
                               rng))
            repeat = qid in seen
            seen.add(qid)
            if repeat and entry.get("AvoidRepeat"):
                continue
            out.append((qid, int(price), stock if stock >= 0 else 2**31 - 1))
        return out

    def day(self, when: When, stats: dict[str, int] | None = None, *, today: bool = True) -> BooksellerDay:
        """His shop and trades on `when` (whether or not he's in town that day)."""
        stats = stats or {}
        return BooksellerDay(when.days_played, when.season, when.day, when.year,
                             self._shop(SHOP, when, stats, today), self._shop(TRADE_SHOP, when, stats, today),
                             TRADE_UNLOCK_MAIL in when.mail)


def _item(got: tuple[str, int, int], entry: dict, name: str, sure: bool, why: str) -> BookItem:
    qid, price, stock = got
    trade = entry.get("TradeItemId") or ""
    return BookItem(qid, name, 0 if trade else price, stock, entry.get("Id") or qid, entry.get("Condition") or "",
                    sure, why, f"(O){trade}" if trade and not trade.startswith("(") else trade,
                    int(entry.get("TradeItemAmount") or 0) if trade else 0, max(1, int(entry.get("MinStack") or 1)))


def stock(day: int | When, save, data, *, world_fields: dict[str, int] | None = None) -> BooksellerDay:
    """What he sells and trades on `day` (days played, or a When) for this save.
    Player conditions use the save as it is now; on a later day they're shown not sure if they'd need reading
    a book first."""
    base = When.from_save(save)
    dp = day.days_played if isinstance(day, When) else int(day)
    when = day if isinstance(day, When) else base.on(dp)
    if world_fields:
        when = when.on(when.days_played, world_fields={**when.world_fields, **world_fields})
    return Bookseller(data).day(when, dict(save.stats), today=dp == save.days_played)
