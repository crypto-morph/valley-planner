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

## Milestones that pay for the rest

Some objectives come before individual bundle slots because they make everything after them cheaper:

- **The greenhouse by Fall 28.** It's the Pantry's reward (repaired the morning after the last Pantry
  bundle), and it lets crops grow through winter. Planned backwards it sets early dates: fruit-tree
  saplings planted by about Summer 1 (28 days to grow, then only their own season), a Coop and Barn,
  then a Big Coop or Big Barn by mid-summer (the Animal bundle's fifth item), the Farming levels for
  the Bee House (3), Preserves Jar (4) and Cheese Press (6), and the fall crops in time.
- **The Seed Maker as early as possible.** Farming 9 (10,000 XP; each harvest gives
  16·ln(0.018·price + 1), about 2-3 XP per tile per day whatever the crop), so it sets how many tiles to
  farm from Spring 1: about 70 kept planted reaches it by mid-summer. It needs 25 Wood, 10 Coal and a
  Gold Bar — in Year 1 Clint sells gold ore at 400g (copper 75g, iron 150g, coal 150g), so the bar can be
  bought for about 2,000g rather than mined. With it, seeds stop costing money and planting can grow.
- **Then the rest of the Community Center**, fitted around those.

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
