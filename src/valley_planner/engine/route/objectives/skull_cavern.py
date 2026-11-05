"""The Skull Cavern: the Skull Key from the Mines' last floor, then a ride on the bus."""

from __future__ import annotations

from ...unlocks import Unlock
from ..model import Req
from .base import objective

SKULL_KEY_FLOOR = 120  # the Mines' last floor: its chest holds the Skull Key
BUS_TICKET = 500  # BusStop.TicketPrice


def _reached(r) -> bool:  # Skull Cavern floors are kept as 120 + the floor
    return getattr(r.farm.save, "deepest_mine_level", 0) > SKULL_KEY_FLOOR


@objective("skull_cavern", "The Skull Cavern", 112, done=_reached, needs=("mines_bottom", "bus"))
def skull_cavern(r):
    ticket = Unlock("bus_ticket", "buy a bus ticket to the Desert", BUS_TICKET)
    chain = r.planner.unlocks.chain("place:Desert") + [ticket]
    return [Req("the Skull Cavern", r.today, r.end, chain, sum(x.days for x in chain))], 0, []
