"""Chest colours (1.6.15), so a chest can be named the way the player sees it.

In our words: a chest's colour is one of twenty picked from the colour bar when it's open, stored in the save
as the chest's playerChoiceColor; none picked (black in the save) leaves it its plain wood or stone look
(DiscreteColorPicker.getColorFromSelection). The names here are ours.
"""

from __future__ import annotations

PALETTE: list[tuple[tuple[int, int, int], str]] = [  # the colour bar, left to right
    ((85, 85, 255), "blue"), ((119, 191, 255), "light blue"), ((0, 170, 170), "teal"),
    ((0, 234, 175), "aquamarine"), ((0, 170, 0), "green"), ((159, 236, 0), "lime"), ((255, 234, 18), "yellow"),
    ((255, 167, 18), "light orange"), ((255, 105, 18), "orange"), ((255, 0, 0), "red"), ((135, 0, 35), "dark red"),
    ((255, 173, 199), "light pink"), ((255, 117, 195), "pink"), ((172, 0, 198), "magenta"),
    ((143, 0, 255), "purple"), ((89, 11, 142), "dark purple"), ((64, 64, 64), "dark grey"), ((100, 100, 100), "grey"),
    ((200, 200, 200), "light grey"), ((254, 254, 254), "white"),
]
KINDS = {"130": "chest", "232": "stone chest", "BigChest": "big chest", "BigStoneChest": "big stone chest"}


def colour_name(r: int, g: int, b: int) -> str:
    """The colour's name, or "" for a chest left uncoloured. A colour off the bar (mods) takes the nearest."""
    if (r, g, b) == (0, 0, 0):
        return ""
    return min(PALETTE, key=lambda p: sum((x - y) ** 2 for x, y in zip(p[0], (r, g, b), strict=True)))[1]


def describe(item_id: str, r: int, g: int, b: int) -> str:
    """'green chest', 'plain chest', 'plain stone chest'."""
    kind = KINDS.get(item_id.removeprefix("(BC)"), "chest")
    return f"{colour_name(r, g, b) or 'plain'} {kind}"


def ordinal(i: int, n: int) -> str:
    """Which of n alike chests, counted from the left: 'left', 'right', '2nd from the left'."""
    if n == 2:
        return "left" if i == 0 else "right"
    return "leftmost" if i == 0 else "rightmost" if i == n - 1 else f"{_nth(i + 1)} from the left"


def _nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
