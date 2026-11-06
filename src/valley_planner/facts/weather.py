"""Rain on any day to come, worked out the way the game rolls it (1.6.15).

Each night the game decides the day after next's weather, in Data/LocationContexts order, with generators
seeded from the game id and the day, so no player action moves them:
- Spring and fall: rain if Rand(hash("location_weather"), game id, day - 1) rolls under 0.183.
- Summer: rain if DaySave(hash("summer_rain_chance")) on day - 1 rolls under 0.12 + 0.003 x day of month of the
  day before. Summer 2 has only the Storm line, which also needs a RANDOM .85 on the unseeded generator.
- Winter: snow, the same roll under 0.63.
Then Game1.getWeatherModificationsForDate overrides, in this order: sun on the 1st and the first four days, rain
on day 3, green rain, a storm on Summer 13 and 26, and no weather on a festival day.
Storm or plain rain is rolled on the unseeded generator, and a Rain Totem can change one day, so neither is here.
"""

from __future__ import annotations

from .calendar import green_rain_day
from .conditions import date_of
from .rng import day_save_random, hash_text, synced_random

SPRING_FALL_RAIN = 0.183
WINTER_SNOW = 0.63
SUMMER_RAIN = 0.12
SUMMER_RAIN_PER_DAY = 0.003
STORM_EVERY = 13  # Summer 13 and 26


def forecast(days_played: int, game_id: int, *, festival: bool = False, legacy: bool = False) -> tuple[str, bool]:
    """(weather, sure) for a day: sun, rain, storm, snow or green rain. Not sure only on Summer 2."""
    season, day, year = date_of(days_played)
    if festival:
        return "sun", True
    if season == "summer" and day % STORM_EVERY == 0:
        return "storm", True
    if season == "summer" and day == green_rain_day(year, game_id, legacy=legacy):
        return "green rain", True
    if days_played == 3:
        return "rain", True
    if day == 1 or days_played <= 4:
        return "sun", True
    before = days_played - 1
    if season == "summer":
        hit = day_save_random(before, game_id, hash_text("summer_rain_chance"), legacy=legacy).next_double() \
            < SUMMER_RAIN + SUMMER_RAIN_PER_DAY * (day - 1)
        return ("rain", day != 2) if hit else ("sun", True)
    roll = synced_random("day", "location_weather", game_id=game_id, days_played=before, season=season, year=year,
                         legacy=legacy).next_double()
    if season == "winter":
        return ("snow" if roll < WINTER_SNOW else "sun"), True
    return ("rain" if roll < SPRING_FALL_RAIN else "sun"), True
