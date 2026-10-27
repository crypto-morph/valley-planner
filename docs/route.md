# The route: planning a year forward

The facts layer answers "what is true" and the views answer "what's possible from today". The route
answers the question a player actually has in Spring: **what to do, and when, so the goal is met in
time** — planning backwards from the deadline and forwards with the cash and materials you'll have.

Goal (first): the Community Center by the end of Year 1, on a fresh farm. The engine starts from any
state, so it can serve a save part-way through later.

## Why

A first run with the reactive planner (McClarkies, Year 1) showed the gaps: cash ran down to 17g in
mid-spring; the Coop came on Summer 4 and the Barn on Summer 23; the Big Coop, kitchen and Steel Axe
never came, so Duck Feather, Goat Milk, Wool, Truffle, Woodskip and Fried Egg were blocked by fall.
Nothing had said in spring that a Big Coop was needed by early summer, or to bank Wood for it.

## Stages

1. **Requirements** (`engine/route/needs.py`): every bundle slot, its best route and its lead time from
   the game's rules — seasonal windows, growing days, build days, animals growing up, friendship, and
   enough luck for 80% on deluxe produce (duck 33 days, rabbit 46, goat 19, cow and chicken 16, from
   `Data/FarmAnimals` and `FarmAnimal.dayUpdate`).
2. **Backwards from the deadline**: each requirement's latest start, and the gold and materials due by
   then (buildings, animals, tools, the kitchen, the bridge).
3. **Day types** (a planning choice): each day has one main activity besides chores — farm, fish, mine,
   chop or forage — with typical yields; crops are planned for the tiles you can water and afford.
4. **Forward simulation**: cash and materials day by day; shortfalls found weeks ahead and fixed by
   moving purchases, changing what's planted, or adding fishing / chopping days.
5. **The route**: weekly targets ("by Spring 25: 2,000g and 300 Wood for the Coop") that Morning and
   To-do read from.

Rules stay facts (checked against the game, in `rules/registry.json`); choices — confidence levels,
day yields, crop preferences — are marked as planning choices and can be tuned.
