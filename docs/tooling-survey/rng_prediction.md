# Stardew Valley RNG prediction tools and libraries (1.6 focus)

Method note: GitHub metadata (licence, language, last push) was pulled with the GitHub API on 2026-10-26. The MouseyPounds Stardew Predictor source was cloned and read to see how it seeds each prediction. The approaches are described below; no code is copied. stardewvalleywiki.com sat behind a Cloudflare challenge (HTTP 403) the whole session, so the wiki pages named in the brief (Traveling Cart, Weather, Modding:Migrate to 1.6) could not be read directly. Wherever these notes describe the game's 1.6 seeding, the evidence is how the reference implementations behave, plus their own comments naming the game methods they copy. It is not the wiki text.

## Which tools and libraries exist, and their licence, repo, last update and language

### Takeaway
The reference tool is MouseyPounds' Stardew Predictor: JavaScript, MIT licence, supports 1.6 since v5.0.0 (March 2024), and still maintained in 2026. Around it sits a group of seed searchers and seed crackers, most of them MIT. One exception is Underscore76's C# SeedFinding, the speedrunners' library, which has no licence, so its code cannot be reused.

### Cited Findings
- **MouseyPounds/stardew-predictor**: JavaScript, MIT, 135 stars, last push 2026-01-25. Hosted at mouseypounds.github.io/stardew-predictor. Its README says it "simulates the random number generator used in Stardew Valley and makes 'predictions' about the game either from the Game ID or by reading the save file". Dependencies: jQuery, BigInteger.js, js-xxhash, pako. — [GitHub repo](https://github.com/MouseyPounds/stardew-predictor)
  - Changelog: v5.0.0 "Support for Stardew Valley 1.6" (26 Mar 2024); v5.0.1 "Update cart item lists for 1.6.3 patch"; v5.0.7 "One more seed overflow fix, changes for patch 1.6.4, support for compressed Switch saves" (18 Apr 2024); v5.0.8 (20 Apr 2024). After that come small PRs only (Bookseller-days fix May 2025, wiki-link fix Jan 2026). — [README/changelog](https://github.com/MouseyPounds/stardew-predictor/blob/master/README.md)
  - The README says "All changed & added content from version 1.6 should be supported; 1.6-specific features will only appear in the results if either the save is detected to be from that version or the app is launched with a URL id parameter." — [README](https://github.com/MouseyPounds/stardew-predictor)
  - It points to BlaDe's Map Predictor (a Nexus mod) for artifact spots, giant crops and mine ladders. That is a SMAPI mod, not a standalone library. — [README](https://github.com/MouseyPounds/stardew-predictor)
- **techmunk/stardew-predictor**: a fork of MouseyPounds, JavaScript, MIT, 0 stars, last push 2021-02-21. It predates 1.6, so it is stale for 1.6. — [GitHub](https://github.com/techmunk/stardew-predictor)
- **davidmhammond/stardew-predictor-ext** ("Extended Stardew Predictor"): JavaScript, MIT, last push 2026-09-09. Adds a Maps tab but needs the complete unpacked game asset files. — [GitHub](https://github.com/davidmhammond/stardew-predictor-ext); [forum thread](https://forums.stardewvalley.net/threads/extended-stardew-predictor.45326/latest)
- **Underscore76/SeedFinding**: "C# tools for finding SDV seeds". No licence is declared (GitHub reports none). Last push 2026-05-10. Covers Remixed Bundle scanning, Traveling Cart scanning (`TravelingCart.GetStock(gameSeed, day)`) and location forage. Built on .NET 5 "to be in line with Stardew Valley". Claimed speed is about 1.8M cart seeds/s in parallel (about 20 minutes for the full int32 space). — [GitHub](https://github.com/Underscore76/SeedFinding); [TravelingCart README](https://github.com/Underscore76/SeedFinding/blob/main/TravelingCart/README.md)
- **Underscore76/StardewSeedApp**: C#, an AWS experiment for a seed-finding site, last updated 2024-09. — [GitHub](https://github.com/Underscore76/StardewSeedApp)
- **Bla-De/StardewSeedScripts**: Python, MIT, 24 stars, last push 2023-06-24. "Scripts to assist in finding good seeds for various Stardew Valley Speedruns". Last pushed before 1.6 (1.5 era). — [GitHub](https://github.com/Bla-De/StardewSeedScripts)
- **CuiYinYin2023/StardewSeedSearcher**: C# (.NET minimal API) with a vanilla JS front end, MIT, 38 stars, last push 2026-06-15. Description: "For Stardew Valley 1.6". Feature modules: WeatherPredictor, FairyPredictor, MineChestPredictor, MonsterLevelPredictor, TravelingCartPredictor, DesertFestivalPredictor. Every check takes a `useLegacyRandom` flag. — [GitHub](https://github.com/CuiYinYin2023/StardewSeedSearcher)
- **skyswordw/StardewSeedSearcher-Web**: TypeScript/React, MIT, last push 2026-09-10. A port of CuiYinYin's searcher. It states support for SDV 1.6.15 on "PC / Android / iOS" and says it does not yet cover Switch random logic. It ships oracle fixtures and parity tests (`fixtures:check`, `parity:sample`). — [GitHub](https://github.com/skyswordw/StardewSeedSearcher-Web)
- **Haruko386-UnOfficIal/StardewSeedSearcher**: JavaScript, MIT, "For Stardew Valley 1.6", last push 2026-04. — [GitHub](https://github.com/Haruko386-UnOfficIal/StardewSeedSearcher)
- **Oshawk/stardew-seed-cracker**: Rust (WASM web app), MIT, last push 2026-04-19. "A tool to crack Stardew Valley seeds based on traveling cart information". Supports PC and Switch, versions 1.6.15 and 1.5.6. — [GitHub](https://github.com/Oshawk/stardew-seed-cracker)
- **T-Dub-98683/switch_stardew_seed_finder**: JavaScript, MIT, last push 2026-02-07. Brute-forces the Game ID from the first 4 cart slots (item, price, qty) on Switch 1.6, then links to MouseyPounds with `?id=<gameId>&dp=<daysPlayed>`. — [GitHub](https://github.com/T-Dub-98683/switch_stardew_seed_finder)
- Smaller or unlicensed repos turned up by search but not assessed: dmdiehr/StardewSeedSearch (C#, no licence, 2025-12), jc-gc/stardew-seed-search (JS), 0xyunn/stardew-seed-finder (JS), MELnRose/StardewSeedFinderScripts. — [GitHub search "stardew seed"](https://github.com/search?q=stardew+seed&type=repositories)
- The 1.6 forum thread on seed finding mentions a browser-based Switch seed cracker that works from cart stock, says it "works only on Stardew 1.6", and points PC users with save access to MouseyPounds instead. Another user found Underscore76's C# tools hard to use without C# experience. — [Forum: Looking for help finding seeds for 1.6](https://forums.stardewvalley.net/threads/looking-for-help-finding-seeds-for-1-6.30074/latest)

### Inferences
- For an open-source planner, MouseyPounds (MIT, JS), CuiYinYin and its TS port (MIT), and Oshawk (MIT, Rust) can all be reused under MIT terms: keep the copyright notice and licence text. Underscore76/SeedFinding and dmdiehr have no licence, so they default to all rights reserved. Read them for understanding only.
- The TS port's oracle/parity fixtures look like the best ready-made test vectors for checking an independent implementation (MIT).

### Gaps
- No Python library maintained for 1.6 was found. Bla-De's scripts predate 1.6.
- Speedrun.com resources were not checked. Search results did not surface them.

## What each tool predicts, and how accurate it is on 1.6

### Takeaway
MouseyPounds covers the widest ground in 1.6. Its tabs: Traveling Cart (including the Y1 Red Cabbage guarantee and the 1.6 extras), Krobus, Sandy, geodes/troves/mystery boxes, mines, mine chests, night events, train, Winter Star, Green Rain plus a rain-only weather calendar, garbage cans, Bookseller, Calico Jack, crane game, enchantments, Raccoon, prize tickets, statues, wallpaper, makeovers and gem birds. User reports on 1.6 are mostly positive. The known failures: Switch saves (a different RNG), mine-level drift within a session, geode counts misread from some saves, and an unexplained cart mismatch.

### Cited Findings
- The predictor's tabs, from its index.html: book(seller), Calico Jack, crane, makeover, enchant, trash, gem birds, geode, Krobus, mines, mine chest, mystery box, night, prize, raccoon, Sandy, statue, train, cart, wallpaper, green rain, Winter Star. A Resort tab is commented out. — [index.html](https://github.com/MouseyPounds/stardew-predictor/blob/master/index.html)
- **Seeding helper:** the predictor's `getRandomSeed` comments say it "Calculates seed value based on logic of StardewValley.Utility.CreateRandomSeed()". Without legacy RNG it hashes up to five int32 values (each taken mod 2147483647) with xxHash32 ("JS implementation of StardewValley.Utility.GetDeterministicHashCode()"). With `useLegacyRandom` on, it sums the values mod 2147483647. Strings such as "cart_fez" are turned into ints by xxHash32 of their UTF-8 bytes. A comment notes that "The standard DaySave wrapper sets a = days played and b = gameID/2". — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- **Traveling Cart (1.6):** a dedicated `predictCart_1_6` function. The base RNG is seeded from (daysPlayed, gameID/2). It draws 10 random objects, each with a price of max(Next(1,11)*100, Next(3,6)*basePrice) and a 10% chance of qty 5. Then come one furniture item, the seasonal special (Rare Seed in spring/summer when none was rolled; otherwise a Rarecrow at 40%), Coffee Bean (25%), catalogues, a tea set, and a skill book (5%). Each extra uses its own "synced" RNG seeded from (hash of a key such as "cart_rarecrow", gameID, day). Some extras depend on save state: the Joja catalogue needs `ccComplete`, and one item is "Only possible in Year 25 or later". — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- **Year 1 Red Cabbage guarantee:** the predictor reads `visitsUntilY1Guarantee` from the save. It reverse-engineers the originally rolled count by adding back cart visits (Fridays and Sundays, plus Night Market days 99–101) and inserts Red Cabbage on the visit where the count reaches 0. A value of -99 means "not rolled yet", in which case it rolls Next(2,31) from a seed of 12×gameID. The comment says the guarantee "can only reliably look forward". — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- The guarantee comes from the "Guarantee Year 1 Completable" advanced game option, which makes Red Cabbage seeds sell at least once at the cart in year 1. Third-party sources date the option to 1.5. — [Sportskeeda](https://www.sportskeeda.com/esports/how-get-red-cabbage-stardew-valley); [wiki: Red Cabbage Seeds](https://stardewvalleywiki.com/Red_Cabbage_Seeds)
- **Geodes, troves, mystery boxes, enchantments (1.6):** seeded from (geodesCracked count, gameID/2, the player's UniqueMultiplayerID/2). When no player IDs are found, the UI warns: "predictions will not be reliable for game version >= 1.6". 1.5-era saves use gameID/2 + numCracked. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- 1.6.4 patch notes: "The order of mystery box rewards is now randomized per-player instead of per-save", and "Fixed 'use legacy randomization' option applied inconsistently when loading a save". — [Stardew Valley 1.6.4 patch notes](https://www.stardewvalley.net/stardew-valley-1-6-4/)
- **Night events (1.6):** logic is "from StardewValley.Utility.pickFarmEvent()". The RNG is seeded from (daysPlayed+1, gameID/2) and discards 10 doubles. If the greenhouse is unlocked there is an extra windstorm roll. Then Fairy (1%, not winter), Witch (1%, day>20), Meteor (1%, day>5), Stone Owl (0.5%), Strange Capsule (0.8%, year>1). Day 30 is always the earthquake. The predictor does not model the +0.007 fairy chance from a fully grown fairy rose ("too volatile for us"). — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- **Weather (1.6):** shown inside the Green Rain tab. Comments cite `Utility.getDayOfGreenRainThisSummer()`, Data/LocationContexts and `getWeatherModificationsForDate()`. Fixed days: days 1, 2 and 4 are sunny, day 3 rains, each season's day 1 is sunny, and festival days are fixed. Spring and fall rain when a synced RNG seeded from (hash "location_weather", gameID, daysPlayed−1) gives NextDouble() < 0.183. Summer: the green rain day is picked from {5,6,7,14,15,16,18,23} with a seed of (year×777, gameID); days 13 and 26 are storms; other days rain at 0.12 + 0.003×(dayOfMonth−1), seeded from (daysPlayed−1, gameID/2, hash "summer_rain_chance"). Winter is not predicted. Legend: "'Rain' could become Storm" and "'Sun' could become Wind or Snow". So the tool predicts only whether a day is wet, not the exact weather type. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- CuiYinYin's WeatherPredictor uses the same structure: fixed year-1 spring days, festival days sunny, summer 13/26 storms, green rain from a 777-based seed, and a "location_weather" hash for spring and fall. It skips winter. Its FairyPredictor counts a fairy only if the next day is not rainy. — [WeatherPredictor.cs](https://github.com/CuiYinYin2023/StardewSeedSearcher/blob/main/StardewSeedSearcher/Features/WeatherPredictor.cs); [FairyPredictor.cs](https://github.com/CuiYinYin2023/StardewSeedSearcher/blob/main/StardewSeedSearcher/Features/FairyPredictor.cs)
  - Discrepancy: CuiYinYin seeds green rain with (777, gameID) in all cases. MouseyPounds uses (year×777, gameID). They agree in year 1 only. A searcher may only care about year 1.
- **Winter Star (1.6):** seeded from (gameID/2, year, the player's UniqueMultiplayerID) using BigInteger arithmetic. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js). A user (Jan 2026) reported "100% accuracy so far" but different gift assignments for two saves with the same seed. A follow-up found that predictions matched exactly whenever both the seed and UniqueMultiplayerID matched. — [Forum: Web Apps thread](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393/latest)
- **Krobus:** 1.6 uses (daysPlayed, gameID/2), plus a "krobus_bread" synced RNG. **Train:** (daysPlayed, gameID/2). **Garbage:** (daysPlayed, gameID/2, 777 + hash of the can ID), plus synced seeds such as "garbage_joja". — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- **1.6 accuracy reports (forum, 2026):**
  - Feb 2026: a user reported "the predictor being completely off for the traveling cart" on a day they needed a truffle. No reply.
  - Jun 2026: monster/mushroom floor predictions were right at the start of the day but became "more inaccurate" as days passed; restarting after a save fixed it. Another user found pepper rex floors that were not listed.
  - Jun 2026: the geode count read as 0 on a save with 25 geodes, all cracked with a Geode Crusher; worked around with a URL parameter.
  - Jul 2026: geode predictions were "completly wrong" on a modded Switch save but correct on PC 1.6.15: "I think that the switch version has different rng". A Switch RNG module was shared (Jun 2026) and has not been merged.
  - A request for Ginger Island weather got no reply.
  - Source for all of the above: [Forum: Web Apps thread, latest page](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393/latest)
- Seeds give different results on different platforms. — [Forum: Is there a benefit to Legacy Randomization?](https://forums.stardewvalley.net/threads/is-there-a-benefit-to-legacy-randomization.53314/latest); this is consistent with Oshawk shipping separate PC and Switch modes ([GitHub](https://github.com/Oshawk/stardew-seed-cracker)) and with the TS port excluding Switch ([GitHub](https://github.com/skyswordw/StardewSeedSearcher-Web)).

### Inferences
- **Depend only on the save's seed and day:** cart base stock, train, night-event rolls (apart from the fairy-rose bonus and greenhouse state), the wet/dry weather flag, and the green rain day.
- **Depend on player actions:** geodes, troves and mystery boxes key off the per-player cracked count, so the next N geodes are predictable but tied to that count, not to a date. Mines can drift within a session, which suggests some mine RNG draws from state that changes during play. Night events are suppressed or replaced by player state such as greenhouse, weddings and births. Rain totems override weather.
- The Feb 2026 cart mismatch is a single, unexplained report. Possible causes include the Switch platform, a mod-altered item list, or a wrong days-played offset. None of these is confirmed.

### Gaps
- Fishing treasure, artifact spot contents and Ginger Island weather: no 1.6 predictor for these was found. MouseyPounds defers artifact digging to BlaDe's Map Predictor mod.
- Whether storms, wind and snow are deterministic in 1.6 (the predictor shows them only as "could become") could not be confirmed. The wiki's Weather page was unreachable.

## Can Traveling Cart stock and future weather be predicted exactly in 1.6 from the save, and with what inputs?

### Takeaway
On PC/mobile 1.6, yes for the cart, with high confidence. The base 10 items, prices and quantities, the furniture item, the seasonal special and most 1.6 extras are a pure function of uniqueIDForThisGame, the day number and the legacy-RNG flag. The Y1 Red Cabbage slot is predictable forward from `visitsUntilY1Guarantee`, and a few extras depend on save state. Weather is predictable only as rain/no-rain for spring, summer and fall: storm, wind and snow subtypes are not, winter is not predicted, and a rain totem can override it.

### Cited Findings
- The cart base RNG uses CreateRandomSeed(daysPlayed, uniqueIDForThisGame/2). It is xxHash32-based by default and an additive sum when `useLegacyRandom` is true. The predictor reads `useLegacyRandom` from the save XML and lets a URL parameter (`leg=1`) override it. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- Inputs the predictor reads from the save:
  - gameID (`uniqueIDForThisGame`)
  - daysPlayed, plus a manual `dayAdjust`
  - `useLegacyRandom`
  - `visitsUntilY1Guarantee`
  - per-player `geodesCracked` and UniqueMultiplayerID (`mp_ids`)
  - deepest mine level
  - CC completion, greenhouse unlocked, Qi crops active
  - game version, which switches between the 1.5 and 1.6 logic
  - Source: [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- The cart's item pool comes from the game's object data, which the predictor embeds. v5.0.1 had to "Update cart item lists for 1.6.3 patch", so the pool changes between patches. — [README](https://github.com/MouseyPounds/stardew-predictor)
- Legacy randomization is optional, can only be enabled when starting a new game, and the in-game text warns most players to leave it off. — [Destructoid](https://destructoid.com/?p=487305); [Steam discussion](https://steamcommunity.com/app/413150/discussions/0/4290314417248874002)
- A forum commenter said legacy randomization "is sort of a mock 1.5 RNG ... not exactly 1.5 RNG, and not all rng changes are reverted, the cart is still the 'fixed' 1.6 version" (community claim, not official). — [Steam discussion via search summary](https://steamcommunity.com/app/413150/discussions/0/4290314417248874002); unverified against code. The predictor itself applies the legacy additive seed to every seed it computes.
- Pathoschild (Oct 2025): "Stardew Valley 1.6+ generally fixes issues where state could leak between contexts", and "Changing your save ID shouldn't affect the actual probabilities". — [Forum: Petition to bring back Dynamic Seeds](https://forums.stardewvalley.net/threads/petition-to-bring-back-dynamic-seeds.35276/post-156677)
- Multiplayer: day-based predictions (cart, weather, night, train) use only the shared gameID. Per-player predictions (geodes, mystery boxes, enchantments, Winter Star) need each farmhand's UniqueMultiplayerID. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js); [Forum Winter Star report](https://forums.stardewvalley.net/threads/web-apps-stardew-checkup-predictor-and-fair-helper.28393/latest)
- The C#/.NET `System.Random` (the subtractive Knuth generator) must be reproduced exactly. MouseyPounds's cs-random.js describes itself as a JS implementation of the C# PRNG published in Microsoft's reference source (referencesource.microsoft.com, random.cs). — [cs-random.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/cs-random.js)

### Inferences
- For the planner's Traveling Cart probabilities (Red Cabbage, Rabbit's Foot and others), a deterministic replacement is feasible. The inputs are `uniqueIDForThisGame`, `stats.daysPlayed` (the day being predicted, counting Fridays, Sundays and Night Market days 99–101 of each year), `useLegacyRandom`, `visitsUntilY1Guarantee` (Red Cabbage) and `ccComplete`. Rabbit's Foot (object 446) sits inside the 2–789 random-object range, so it would come out of the base 10 draws. This is inferred from the ID range; the per-item exclusion list was not checked.
- Weather can become deterministic only for rain/no-rain on future days. Storms (outside the fixed summer 13/26), wind and snow should stay probabilistic, and a player using a rain totem invalidates the forecast.
- Night events remain partly probabilistic: fairy-rose bonus, and player-state overrides.
- Switch saves need a different RNG. Without platform detection, the planner should mark predictions as "PC/mobile only".

### Gaps
- `visitsUntilY1Guarantee` values other than -99 and ≥0 (for example -1 when the option is off or already fulfilled) are inferred, not confirmed.
- The exact rules for which objects are excluded from the 1.6 cart pool were not extracted.

## Documentation of 1.6 RNG seeding for a clean-room implementation

### Takeaway
No single public write-up of 1.6 seeding was reachable. The wiki migration page could not be fetched, and searches for `CreateDaySaveRandom` turned up nothing useful. The most usable fact-level description is in the comments of the MIT-licensed predictor: CreateRandomSeed hashes up to five int32 values with xxHash32 unless legacy RNG is on, in which case it adds them mod int32 max; string keys are hashed with xxHash32 over UTF-8; and System.Random comes from the .NET reference source.

### Cited Findings
- Predictor comments name the game methods being copied: `Utility.CreateRandomSeed()`, `Utility.GetDeterministicHashCode()` (string and int-array overloads), the "DaySave" wrapper (days played, gameID/2), `Utility.pickFarmEvent()`, `Utility.getDayOfGreenRainThisSummer()` and `getWeatherModificationsForDate()`, plus the Data/LocationContexts weather rules. — [stardew-predictor.js](https://github.com/MouseyPounds/stardew-predictor/blob/master/stardew-predictor.js)
- CuiYinYin's searcher keeps the hashing in a separate `Core/HashHelper.cs` (MIT), with a `GetRandomSeed(..., useLegacyRandom)` signature that mirrors the game's. — [GitHub tree](https://github.com/CuiYinYin2023/StardewSeedSearcher)
- The 1.6 modding migration guide exists on the wiki and says 1.6 makes "fundamental changes to the game code", but it could not be read here. — [Modding:Migrate to Stardew Valley 1.6](https://stardewvalleywiki.com/Modding:Migrate_to_Stardew_Valley_1.6); a related diff is at [Special:Diff/152406](https://www.stardewvalleywiki.com/Special:Diff/152406)
- The xxHash32 spec and the .NET reference-source Random algorithm are both public. The predictor uses pierrec/js-xxhash. — [README](https://github.com/MouseyPounds/stardew-predictor)

### Inferences
- A clean-room implementation is realistic. It needs three published algorithms: .NET System.Random, xxHash32 with seed 0 over little-endian int32 arrays, and xxHash32 over UTF-8 strings. Add the per-feature seed recipes (which values and which constants) taken from the game's data and the predictors' comments. The TS port's oracle fixtures could check correctness. All of these sources are MIT, so reusing code with attribution is also allowed.
- The seed recipes amount to facts about game behaviour rather than creative expression. A rewrite would still be prudent, though, and an MIT notice already covers direct reuse.

### Gaps
- The wiki's Traveling Cart, Weather and Migrate-to-1.6 RNG sections could not be read: Cloudflare blocked them, and web.archive.org was unavailable to the fetch tool. Re-check these by hand.
- The official 1.6.0 changelog wording on RNG and legacy randomization was not found.
