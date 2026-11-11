# Stardew Valley calculators and planning tools (survey as of Oct 2026), mapped against Valley Planner

Scope: web calculators and planners for crops, artisan goods, fish, forage, NPC schedules, gifts, food and layouts. SMAPI mods are listed only as reference points, because Valley Planner is vanilla and save-driven and must not depend on mods. "Pushed" dates come from the GitHub API (`pushed_at`) on 2026-10-26. A push date is not always a content update: exnil was pushed in 2024 but its last commit is from 2017.

## Which tools exist, what they compute, save-reading, 1.6 support, maintenance, licence, repo

### Takeaway
The best-maintained open-source tools for 1.6 are Thorinair's Stardew-Profits (MIT, crop and artisan profit, updated April 2026), stardew.app (MIT, a perfection tracker that reads saves), MouseyPounds' Checkup and Predictor (MIT, read saves), and rickselby's Stardew Helpers (villager schedule calendar and forage finder, no licence, active Oct 2026). The broadest 1.6.15 feature set is on Stardew Valley Sprinkler, which is closed and "All rights reserved". Older tools have stalled before 1.6: the exnil Crop Planner has no 1.6 crops, and Stardew Planner v3 last changed in July 2024. Apart from layout importers and trackers, almost no tool uses the save to personalise *recommendations*. Valley Planner's main point of difference is ranking from the save.

### Cited Findings

**Crop profit calculators**
- Thorinair/Stardew-Profits: crop profit calculator and visualiser, live at thorinair.github.io/Stardew-Profits. MIT licence, 220 stars, last pushed 2026-04-15. — [GitHub repo](https://github.com/Thorinair/Stardew-Profits)
- Stardew-Profits v1.6.0 (2024-03-29) added the 1.6 seeds and crops, ROI calculations, an "Equipment" count for Jars and Kegs, Keg aging and Seeds as a produce type. Later 2024 releases added Process & Replant (v1.6.2), seeds kept for next year (v1.6.7), Dehydrator calculations and an "Excess" option for Jars and Kegs (v1.6.10), and the Artisan bonus on Jars, Casks and Kegs (v1.6.11). — [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html)
- Stardew-Profits 2026 releases: v1.7.0 (2026-02-04) added an optional prediction model, Mill as a produce type, lower-quality crops used first for seeds and artisan goods, and Tiller dropped when the level is reduced. v1.7.3 fixed aging and the Powdermelon price. v1.7.5 (2026-04-15) fixed Speed-Gro rounding, which had gone the wrong way. — [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html)
- Stardew-Profits' `js/data.js` contains Powdermelon, Broccoli, Carrot, Hyper Speed-Gro, Deluxe Fertilizer and a "Greenhouse" season entry. I found this by grepping the raw file. — [data.js](https://github.com/Thorinair/Stardew-Profits/blob/master/js/data.js)
- Forks of Stardew-Profits: nikkehsolaris/Stardew-Profits-Extended (MIT, supports the SVE, PH, LASV and LoC mods, last pushed 2023-11-01); Skitterling/Expanded-Profits (SVE); RealSweetPanda/Stardew-Profits-Customizable; davidmcguiredesign/stardew-profits-shoelace. — [Extended repo](https://github.com/nikkehsolaris/Stardew-Profits-Extended), [Expanded-Profits](https://github.com/Skitterling/Expanded-Profits), [Customizable](https://github.com/RealSweetPanda/Stardew-Profits-Customizable), [shoelace](https://github.com/davidmcguiredesign/stardew-profits-shoelace)
- polarstoat/stardew-crop-profits: models the in-game date, quality chances from farming level and fertilizer, Tiller and Agriculturist, buying seeds versus using a Seed Maker, and minimum and average profit formulas. MIT, last pushed 2023-02-18, so it predates 1.6. Live at polarstoat.github.io/stardew-crop-profits. — [GitHub](https://github.com/polarstoat/stardew-crop-profits)
- hakshi/StardewCrops: React/TS chart that takes farming level, fertilizer and growth days. No licence, last pushed 2023-11-22, predates 1.6. — [GitHub](https://github.com/hakshi/StardewCrops)
- cat-wates/stardew-calculator: Java console app that takes balance, farming level, professions, tile count, fertilizer and season, and reports a projected balance. It is close in concept to "Earn faster", but it is a console app. — [GitHub](https://github.com/cat-wates/stardew-calculator)

**Crop planners and schedulers**
- exnil/crop_planner: multi-year crop planning, plan import/export, greenhouse plans kept separate from outdoor plans, seasonal statistics. Crop data was extracted from Crops.xnb and ObjectInformation.xnb with XNBNode. MIT, 117 stars. — [README](https://github.com/exnil/crop_planner)
- exnil/crop_planner status: last commit 2017-03-19, even though the repo was pushed 2024-03-26. Its config.json has no Carrot, Summer Squash, Broccoli or Powdermelon (from grepping the file), so it is effectively pre-1.6 and unmaintained. — [commits](https://github.com/exnil/crop_planner/commits), [config.json](https://github.com/exnil/crop_planner/blob/master/config.json)
- mschult2/stardew-planner (stardewcropplanner.com): Blazor WASM app that approximates the most profitable planting schedule from available gold, field tiles, crops, start day and season length. It uses a "heuristic decision tree simulation, with caching and bucketing", because millions of schedules are possible. No licence, last pushed 2025-12-13. — [README](https://github.com/mschult2/stardew-planner)
- stardewcropplanner.com failed to load when I fetched it ("An unhandled error has occurred"), so I could not confirm 1.6 crop coverage. — [site](https://www.stardewcropplanner.com/)
- LDaham/stardew-valley-scheduler: browser planner on the 112-day cyclic calendar. It has memos with countdowns, auto-flagged festivals, birthdays and crop deadlines, lookups for crops, fish, shops and gifts, achievement, bundle and museum tracking, and an optional Min-Max walkthrough. MIT. Some data comes from the Wiki (CC BY-NC-SA 3.0), and the Min-Max guide is adapted from a GPL-3.0 guide. Posted 2026-06-28. Data is kept in local storage with JSON export. — [forum post](https://forums.stardewvalley.net/threads/stardew-valley-scheduler-a-free-browser-based-cyclic-calendar-planner.53087/)
- "Stardew Valley Calculator" (forum, ~2025, beta): crafting-ingredient planner with a Crop Planner and shareable lists. — [forum thread](https://forums.stardewvalley.net/threads/stardew-valley-calculator.50728/)
- A crafting-materials calculator (hosted on GameWith, Jan 2025) and a "Should I Sashimi This Fish?" tool (Aug 2025), which weighs fish quality and profession. — [crafting thread](https://forums.stardewvalley.net/threads/i-made-a-tool-to-simplify-crafting-calculations.36525/), [sashimi thread](https://forums.stardewvalley.net/threads/just-made-a-%E2%80%9Cshould-i-sashimi-this-fish-%E2%80%9D-tool-%E2%80%93-check-it-out-%F0%9F%8D%A3.43939/)

**Multi-tool suites**
- Stardew Valley Sprinkler (stardewvalleysprinkler.com/tools): 34 tools, among them a Profit Calculator (with ROI), a Processing Throughput Planner (Dehydrator, Fish Smoker, Keg and Jar queues, pickup timing, coal, minimum machine counts; 1.6.15), a Fish Pond Workbench (vanilla 1.6.15 and SVE), a Giant Crops calculator and demonstrator, an Ancient Fruit (greenhouse) planner, a Tea Sapling calculator, a Traveling Cart predictor, a Community Center Deadline Planner (planting cutoffs, fishing windows, building lead times, remixed bundles), a Farm + Island layout planner, a Ginger Island Walnut planner, an NPC Gift Tool, an NPC Schedule Atlas (maps and filters), a Social Gift Route Optimizer (daily gift routes from schedules), a Fishing Lab (fishing-zone tiles, Specific Bait, Fish Smoker value; 1.6.15), a Mastery/Books/Trinkets lab, an RNG predictor, a Save Perfection Roadmap (local save) and a Save Clinic (reads saves). — [tools page](https://stardewvalleysprinkler.com/tools)
- Sprinkler licence: footer reads "© 2025 Stardew Valley Sprinkler. All rights reserved." No repo or author is given, the site carries ads, and it does not say whether the Save Clinic uploads saves. — [tools page](https://stardewvalleysprinkler.com/tools)
- rickselby/stardew-helpers (stardew.selbysaurus.me): a Villager Calendar (pick a villager and a date to see possible schedules; rain, closed buildings and friendship can override them) and a Forage Finder. "Updated for 1.6." Ruby, no licence file, last pushed 2026-10-24. — [site](https://stardew.selbysaurus.me/calendar), [repo](https://github.com/rickselby/stardew-helpers)
- Valley Ledger (stardewplanner.xyz): 12×8 layout grid, bundle checklist sample, small gift lookup and crop margin calculator. Data is "tied to 1.6.15 PC", verified 2026-08-11. No save upload, local storage only. No repo or licence. — [site](https://stardewplanner.xyz/)

**Save readers and trackers**
- communitycenter/stardew.app: perfection tracker built on Next.js and MySQL with Discord login. It tracks "All 1.6 content", fish with location info, shipping with crop info, villagers with gift info, recipes, museum, bundles, walnuts, secret notes and journal scraps. MIT, 213 stars, last pushed 2026-08-09. — [README](https://github.com/communitycenter/stardew.app)
- stardew.app's fishing tracker shows best spots, seasons and weather per fish. A third-party listing says it supports "1.6 through 1.6.9". I did not verify this against the site. — [stardew.app/fishing](https://stardew.app/fishing)
- MouseyPounds/stardew-checkup: checks progress from a save file. MIT, 254 stars, last pushed 2024-05-09. — [repo](https://github.com/MouseyPounds/stardew-checkup), [site](https://mouseypounds.github.io/stardew-checkup/)
- MouseyPounds/stardew-predictor: simulates the game RNG from the Game ID or the save. It predicts special mine levels, vendor stock, geodes, the train schedule and more. v5.0.0 (2024-03-26) added 1.6 support, and v5.0.7 covered patch 1.6.4 and compressed Switch saves. MIT, last pushed 2026-01-25. Uses jQuery, BigInteger.js, JS xxHash and pako. — [README](https://github.com/MouseyPounds/stardew-predictor)
- MouseyPounds/stardew-fair-helper: Fall Fair display picker. MIT, last pushed 2020-12-28, so stale. — [repo](https://github.com/MouseyPounds/stardew-fair-helper)
- gucci-on-fleek/Stardew-Valley-Item-Finder: finds items in a save and runs entirely in the browser. Licence NOASSERTION (custom or unclear), last pushed 2024-11-16. — [repo](https://github.com/gucci-on-fleek/Stardew-Valley-Item-Finder)
- iGoodie/stardew-save-analyzer: save analyser and tracker. No licence, last pushed 2025-07-19. colecrouter/stardew-save-editor: online save editor, NOASSERTION licence, last pushed 2026-10-26. — [analyzer](https://github.com/iGoodie/stardew-save-analyzer), [editor](https://github.com/colecrouter/stardew-save-editor)

**Fishing**
- brokencygnus/stardew-fishing-calc: bite chance per fish, including trash. Inputs are season (or Magic Bait), location (including mine floors and Ginger Island areas), time, rain, training rod, the Extended Family quest, Trout Derby, Squid Fest, fishing level, luck buff, water depth, Curiosity Lure and targeted bait. GPL-3.0, last pushed 2024-05-25. The README says the Caldera and some minor locations are missing. — [README](https://github.com/brokencygnus/stardew-fishing-calc), [site](https://brokencygnus.github.io/stardew-fishing-calc/home)
- Other fishing repos (timers, bubble predictors, minigame analysis) are not planners: sistudios13/StardewFishingTimer, rvcx/stardew-bubbles, chi-feng/stardew-fishing-analysis. — [GitHub search results for "stardew fishing"](https://github.com/search?q=stardew+fishing&type=repositories)

**NPC schedules and gifts**
- Schedule Viewer (mod by BinaryLip): shows NPCs' schedules for the current day from current world conditions. Supports 1.6 and custom NPCs. GPL-3.0, last pushed 2024-11-26. It needs SMAPI, so it is not usable by Valley Planner. — [repo](https://github.com/BinaryLip/ScheduleViewer), [Nexus](https://www.nexusmods.com/stardewvalley/mods/19305)
- Lookup Anything (Pathoschild): in-game cursor lookups that include fish and NPC info. Requires 1.6.15+. Source is in Pathoschild/StardewMods, MIT, 957 stars, pushed 2026-05-10. — [Nexus](https://www.nexusmods.com/stardewvalley/mods/541), [repo](https://github.com/Pathoschild/StardewMods)
- Small schedule web apps: djtanner/stardew-schedules (React, no licence, 2025-02) and Huskyn1nja/StardewScheduleHelper (placeholder README, 2026-06). — [djtanner](https://github.com/djtanner/stardew-schedules), [Huskyn1nja](https://github.com/Huskyn1nja/StardewScheduleHelper)
- Gift tools are mostly small or abandoned: felipefoschiera/stardew-gift-helper (MIT, 2022), tangpadon/Stardew-Gifts-Guide-APP (MIT, Android, 2026-10), buildwithari/stardew-gifts (no licence, 2026-04). — [GitHub search results for "stardew gift"](https://github.com/search?q=stardew+gift&type=repositories)

**Layout planners**
- Stardew Planner v3 (hpeinar/planner_v3; stardew.info's page title is "Stardew Planner V3"): beta rewrite with real sprites and mobile work in progress. No licence, last pushed 2024-07-05. — [README](https://github.com/hpeinar/planner_v3)
- The official forum guide to the Stardew Planner says you can upload a PC or mobile save to start planning. The post is about 6 years old. — [forum guide](https://forums.stardewvalley.net/threads/how-to-share-your-farm-and-use-stardew-planner.152/)
- stardew.build: free layout builder covering all eight farms, buildings, crops, sprinklers and scarecrows with coverage checks, interiors, previews of all four seasons, save import, and share links. No account needed. Repo, licence, author and 1.6 status are not stated, and it does not mention Ginger Island or the greenhouse. — [site](https://stardew.build/)

**Cask and artisan**
- jdarksun/stardew-cask-profitability: Python that outputs cask-productivity tables for the wiki. CC0-1.0, 2024-08. — [repo](https://github.com/jdarksun/stardew-cask-profitability)
- Thorinair's Stardew-Profits models Keg and Jar outputs, aging, Dehydrator and Mill (see above). Sprinkler's Throughput Planner models machine queues and counts. — [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html), [Sprinkler](https://stardewvalleysprinkler.com/tools)

### Inferences
- No dedicated, maintained open-source tool for cask aging or for energy/food ranking turned up. Food ranking appears only inside trackers and wiki tables, so Valley Planner's Food tab and farm-cave advisor look unduplicated.
- Every crop optimiser except cat-wates' console app is generic: you type in level, fertilizer and gold. Valley Planner's ranking from the save, using real money, tiles, professions and date, has no maintained open-source equivalent. The closest is mschult2's scheduler, which takes gold and tiles by hand.
- brokencygnus covers Trout Derby, Squid Fest and targeted bait, which shows it models 1.6 fishing, though its README does not say "1.6".

### Gaps
- I could not verify stardewcropplanner.com's 1.6 crop coverage because the page errored. stardew.build's 1.6 status and code licence are also unknown.
- I did not open the stardew.info planner's source to see whether its save import handles 1.6 saves.
- rickselby/stardew-helpers has no licence file, so the terms are unknown, which in practice means all rights reserved.
- I found no evidence of Stardew Valley Sprinkler's authorship or privacy handling for save uploads. Its privacy policy was not fetched.
- I did not survey r/StardewValley directly; search returned no Reddit threads. Tools posted only on Reddit may be missing.

## Which features do they offer that Valley Planner lacks?

### Takeaway
The main gaps are these: greenhouse and Ginger Island planning; true multi-season or multi-year schedule optimisation; machine throughput, cask and Dehydrator/Mill modelling; fish pond planning; full fishing bite-probability modelling; NPC schedule maps and gift routes; RNG prediction (cart, geodes, mine floors); giant crops; and layout and sprinkler coverage. Valley Planner already covers single-season ranking, Speed-Gro timing, sell-price professions and today's schedule.

### Cited Findings
- Greenhouse: exnil keeps greenhouse plans separate from farm plans, and Stardew-Profits has a Greenhouse season. Sprinkler has an Ancient Fruit greenhouse planner and a Farm + Island layout planner. — [exnil README](https://github.com/exnil/crop_planner), [data.js](https://github.com/Thorinair/Stardew-Profits/blob/master/js/data.js), [Sprinkler](https://stardewvalleysprinkler.com/tools)
- Multi-season and multi-year: exnil does multi-year plans. mschult2 searches planting schedules across the season with a heuristic decision tree. — [exnil](https://github.com/exnil/crop_planner), [mschult2](https://github.com/mschult2/stardew-planner)
- Artisan and processing: Stardew-Profits has Keg aging, a Jar/Keg equipment count with an "Excess" option, Dehydrator, Mill, Process & Replant, and seeds for next year. Sprinkler has throughput queues, pickup timing, coal and minimum machine counts. — [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html), [Sprinkler](https://stardewvalleysprinkler.com/tools)
- Quality and fertilizer modelling: polarstoat models quality odds from farming level and fertilizer, and offers minimum versus average profit. Stardew-Profits uses lower-quality crops first for artisan goods and seeds, and added a prediction model in v1.7.0. — [polarstoat](https://github.com/polarstoat/stardew-crop-profits), [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html)
- Fish ponds: Sprinkler's Fish Pond Workbench. — [Sprinkler](https://stardewvalleysprinkler.com/tools)
- Fishing probabilities: brokencygnus gives per-fish bite percentages with depth, luck, Curiosity Lure and targeted bait. Sprinkler's Fishing Lab handles zone tiles, Specific Bait and smoker value. — [brokencygnus](https://brokencygnus.github.io/stardew-fishing-calc/home), [Sprinkler](https://stardewvalleysprinkler.com/tools)
- NPC maps and routing: Sprinkler has an NPC Schedule Atlas with maps and a Social Gift Route Optimizer. selbysaurus lets you pick any date, not just today. — [Sprinkler](https://stardewvalleysprinkler.com/tools), [selbysaurus](https://stardew.selbysaurus.me/calendar)
- Forage: selbysaurus Forage Finder. — [selbysaurus](https://stardew.selbysaurus.me/calendar)
- RNG prediction from the save (cart stock, geodes, mine floors, train): MouseyPounds' Predictor and Sprinkler's Traveling Cart Toolkit. — [Predictor](https://github.com/MouseyPounds/stardew-predictor), [Sprinkler](https://stardewvalleysprinkler.com/tools)
- Deadlines: Sprinkler's Community Center Deadline Planner gives planting cutoffs, fishing windows and building lead times. The LDaham Scheduler auto-flags crop deadlines. — [Sprinkler](https://stardewvalleysprinkler.com/tools), [Scheduler post](https://forums.stardewvalley.net/threads/stardew-valley-scheduler-a-free-browser-based-cyclic-calendar-planner.53087/)
- Layout: stardew.build checks sprinkler and scarecrow coverage across all eight farms and imports saves. — [stardew.build](https://stardew.build/)
- Other niches: giant crops, Tea Saplings, Mastery/Books/Trinkets, Golden Walnuts. — [Sprinkler](https://stardewvalleysprinkler.com/tools)

### Inferences
- The gaps that fit Valley Planner's save-driven model best are greenhouse and Ginger Island fields as extra field plans, a next-season or multi-season view, machine-count and cask-aging advice in Sell/hold, Fish finder bite odds, and any-date schedules in Villagers. Layout drawing and RNG prediction are better linked out to.

### Gaps
- I did not test whether any of these tools models 1.6 Mastery perks (for example, the Farming Mastery quality boost) in profit maths. Only Sprinkler mentions Mastery, and only as thresholds.

## Are any data or algorithms reusable, or worth linking out to?

### Takeaway
MIT code can be reused with attribution: Stardew-Profits' crop data and profit formula, stardew.app's 1.6 data scripts, MouseyPounds' save parsing and RNG (Predictor), and Pathoschild's StardewMods gift-taste and lookup logic. brokencygnus's fishing maths and the Schedule Viewer logic are GPL-3.0, so reading them is safe but copying code would bring GPL obligations. Sprinkler and selbysaurus have no licence that permits reuse and should only be linked. Wiki text is CC BY-NC-SA 3.0. Extracting from the game's own content files is the cleanest data source.

### Cited Findings
- MIT: Thorinair/Stardew-Profits, exnil/crop_planner, polarstoat/stardew-crop-profits, communitycenter/stardew.app, MouseyPounds checkup, predictor and fair-helper, Pathoschild/StardewMods, LDaham scheduler. — [Stardew-Profits](https://github.com/Thorinair/Stardew-Profits), [exnil](https://github.com/exnil/crop_planner), [polarstoat](https://github.com/polarstoat/stardew-crop-profits), [stardew.app](https://github.com/communitycenter/stardew.app), [predictor](https://github.com/MouseyPounds/stardew-predictor), [checkup](https://github.com/MouseyPounds/stardew-checkup), [StardewMods](https://github.com/Pathoschild/StardewMods), [Scheduler post](https://forums.stardewvalley.net/threads/stardew-valley-scheduler-a-free-browser-based-cyclic-calendar-planner.53087/)
- GPL-3.0: brokencygnus/stardew-fishing-calc and BinaryLip/ScheduleViewer. — [fishing calc](https://github.com/brokencygnus/stardew-fishing-calc), [ScheduleViewer](https://github.com/BinaryLip/ScheduleViewer)
- CC0: jdarksun cask-profitability tables. — [repo](https://github.com/jdarksun/stardew-cask-profitability)
- No licence or unclear: rickselby/stardew-helpers, mschult2/stardew-planner, hpeinar/planner_v3, hakshi/StardewCrops, iGoodie analyzer (no licence); Item Finder and colecrouter save editor (NOASSERTION). Sprinkler is "All rights reserved". — [GitHub API metadata for each repo, retrieved 2026-10-26; Sprinkler footer](https://stardewvalleysprinkler.com/tools)
- Wiki-derived data carries CC BY-NC-SA 3.0, as the LDaham Scheduler notes. That licence is non-commercial and share-alike, which matters if Valley Planner bundles wiki-sourced tables. — [Scheduler post](https://forums.stardewvalley.net/threads/stardew-valley-scheduler-a-free-browser-based-cyclic-calendar-planner.53087/)
- Data-extraction precedent: exnil built crop data from the game's Crops.xnb and ObjectInformation.xnb with XNBNode. stardew.app generates its data with TypeScript and Python scripts. — [exnil README](https://github.com/exnil/crop_planner), [stardew.app README](https://github.com/communitycenter/stardew.app)
- MouseyPounds' Predictor uses JS xxHash and BigInteger.js to replicate the 1.6 RNG from the save or Game ID. This is a reference implementation for any day-seeded prediction. — [README](https://github.com/MouseyPounds/stardew-predictor)
- Stardew-Profits' changelog is a list of known pitfalls worth testing against: Speed-Gro rounding direction (v1.7.5), Hops making Pale Ale rather than Wine (v1.7.2), the Artisan bonus on Casks, Kegs and Jars (v1.6.11), Broccoli regrow time (v1.6.9), and the Powdermelon price (v1.7.3). — [changes.html](https://github.com/Thorinair/Stardew-Profits/blob/master/changes.html)

### Inferences
- Worth linking rather than rebuilding: stardew.build or Stardew Planner for layouts, MouseyPounds' Predictor for cart, geode and mine RNG, brokencygnus for full bite odds, and Sprinkler's Fish Pond and Throughput tools (link only, closed source). stardew.app is the place for perfection tracking.
- Worth cross-checking or reusing: Stardew-Profits' data.js and formulas (MIT) as a test oracle for Earn faster and Sell/hold, and Pathoschild's MIT code for gift-taste resolution. Those mod sources show game logic and can be read without depending on SMAPI at runtime.
- Before copying any GPL code, the project's own licence needs checking for compatibility. Reimplementing from the game data avoids the issue.

### Gaps
- I did not inspect the internal file layout of stardew.app's data (fish, villager JSON) or Stardew-Profits' formula code line by line, so how much can be lifted directly is unconfirmed.
- I did not determine whether stardew.app's hosted data includes 1.6.15 changes or only up to 1.6.9.
