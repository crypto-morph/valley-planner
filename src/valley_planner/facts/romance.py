"""Courtship and marriage (1.6.15), in our words.

- Friendship points: 250 make a heart. Talking gives 20 a day (once a day). A gift loved gives 80, liked 45,
  neutral 20 (NPC.receiveGift), times 8 on their birthday; quality raises it a little. Two gifts a week, the
  count resetting on Sunday; a birthday gift doesn't count against it.
- Anyone you can date stops at 8 hearts and 249 points (2,249) until you give them a Bouquet; dating, they
  stop at 10 hearts and 249 (2,749) (Farmer.changeFriendship, Utility.GetMaximumHeartsForCharacter).
- Pierre sells the Bouquet once you have 8 hearts with anyone you could date; it costs twice its price.
- The Old Mariner stands on the far side of the beach bridge on rainy (or stormy) days before 7 PM. He sells
  the Mermaid's Pendant once you have 10 hearts with someone you're dating, but not until the house has had
  its first upgrade (Beach.checkAction).
- It rains (or storms) in spring and fall on 18.3% of days; in summer the chance is 12% + 0.3% per day of
  the month (none on the 1st); never in winter, which has snow (Data/LocationContexts, Default).
- The wedding is three days after the proposal, pushed on past any festival day (NPC, engagement).
"""

from __future__ import annotations

from .conditions import SEASONS

HEART = 250
TALK = 20
GIFT = {"loved": 80, "liked": 45, "neutral": 20}
GIFTS_PER_WEEK = 2
BIRTHDAY = 8
CAP_FRIEND = 8 * HEART + 249  # someone you could date, before the Bouquet
CAP_DATING = 10 * HEART + 249
BOUQUET, PENDANT = "458", "460"
WEDDING_DELAY = 3
YEAR = 112


def rain_chance(day: int) -> float:
    """Chance it rains or storms on this day (days played, from 1)."""
    season = SEASONS[(day - 1) // 28 % 4]
    dom = (day - 1) % 28 + 1
    if season in ("spring", "fall"):
        return 0.183
    if season == "summer":
        return 0 if dom == 1 else 0.12 + 0.003 * dom
    return 0.0


def rain_by(start: int, confidence: float = 0.8, limit: int = 2 * YEAR) -> int | None:
    """The first day by which there's `confidence` of at least one rainy day from `start` on."""
    dry = 1.0
    for d in range(start, start + limit):
        dry *= 1 - rain_chance(d)
        if 1 - dry >= confidence:
            return d
    return None


def points_day(points: int, target: int, start: int, *, birthday: int | None, gift: int = GIFT["loved"],
               cap: int = CAP_DATING, limit: int = 2 * YEAR) -> int | None:
    """The day friendship first reaches `target`, talking every day and giving two gifts each week (on its
    first two days) plus one on the birthday. `birthday` is the day of the year (1-112)."""
    if points >= target:
        return start
    for d in range(start, start + limit):
        gain = TALK
        if birthday and (d - 1) % YEAR + 1 == birthday:
            gain += gift * BIRTHDAY
        elif (d - 1) % 7 < GIFTS_PER_WEEK:  # Monday and Tuesday
            gain += gift
        points = min(cap, points + gain)
        if points >= target:
            return d
    return None
